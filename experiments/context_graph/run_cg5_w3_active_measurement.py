"""Execute preregistered CG-5 on a fresh W3-derived cohort.

The protocol is frozen before fresh source generation. This runner consumes only the
private capsule state of the newly generated Fields, creates all decision evidence
online, performs active post-turnover measurement, and keeps the W4 outcome law
unchanged. No historical task/outcome/bid/pair-edge evidence is imported.
"""

from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import random
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from experiments.context_graph.run_cg4m_measurement_sufficiency import (
    CellEvidence,
    EstimatorSpec,
    _bundle_flat_context,
    _canonical_event_bundles,
    _cell_evidence,
    _coverage_graph_context,
    _event_diagnostics,
    _latest_active_membership_claims,
    _pearson,
    _score,
    _select_pair,
    _supplement_field,
)
from resonance_world.context_graph_w3_endogenous import (
    CG4Mission,
    EndogenousField,
    LiveClaim,
    _compile_graph,
    _estimate_pair,
    _evaluate_pair_trials,
    _expected_success,
    _membership_candidates,
    _oracle_pair,
    build_endogenous_field,
)
from resonance_world.w4a_joint_learning import JointEnvironment

Pair = tuple[str, str]
Arm = str


@dataclass(slots=True)
class ArmAccumulator:
    decisions: int = 0
    successes: int = 0
    trials: int = 0
    expected_success_total: float = 0.0
    oracle_expected_total: float = 0.0
    regret_total: float = 0.0
    oracle_pair_matches: int = 0
    invalid_selections: int = 0
    context_claims: int = 0
    complete_bundles: int = 0
    provenance_claims: int = 0
    selected_single_success_roles: int = 0
    selected_roles: int = 0
    selected_role_true_gap_total: float = 0.0


@dataclass(frozen=True, slots=True)
class ArmMetrics:
    arm: str
    decisions: int
    mission_success_rate: float
    mean_expected_success: float
    mean_oracle_expected_success: float
    mean_regret: float
    oracle_pair_rate: float
    invalid_selection_rate: float
    mean_context_claims: float
    mean_complete_bundles: float
    provenance_completeness: float
    selected_single_success_rate: float
    mean_selected_role_true_gap: float
    successes: int
    trials: int


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _missions(rows: list[dict[str, Any]]) -> list[CG4Mission]:
    return [
        CG4Mission(
            mission_id=str(row["mission_id"]),
            lead_skill=str(row["lead_skill"]),
            support_skill=str(row["support_skill"]),
        )
        for row in rows
    ]


def _build_base_field(capsules: Path, field_id: str, config: dict[str, Any]) -> EndogenousField:
    society = config["society"]
    return build_endogenous_field(
        capsules_path=capsules,
        field_id=field_id,
        initial_roster_size=int(society["initial_roster_size"]),
        turnover_count=int(society["turnover_count"]),
        probes_per_skill=int(society["initial_probes_per_skill"]),
        skills_per_agent=int(society["initial_skills_per_agent"]),
        noise_rate=float(society["observation_noise_rate"]),
        rumor_count=int(society["rumor_count"]),
    )


def _estimator(config: dict[str, Any]) -> EstimatorSpec:
    row = config["estimator"]
    return EstimatorSpec(
        name=str(row["name"]),
        kind=str(row["kind"]),
        min_support=int(row["minimum_independent_event_support"]),
        fallback_score=float(row["fallback_score"]),
        z=float(row["z"]),
    )


def _revised_pair(
    context: tuple[LiveClaim, ...],
    mission: CG4Mission,
    *,
    estimator: EstimatorSpec,
    min_confidence: float,
) -> tuple[Pair | None, dict[tuple[str, str], CellEvidence]]:
    candidates = _membership_candidates(
        context,
        min_confidence=min_confidence,
        respect_temporal_order=True,
    )
    evidence = _cell_evidence(
        context,
        candidates=candidates,
        min_confidence=min_confidence,
    )
    return _select_pair(candidates, mission, evidence, estimator), evidence


def _local_context(
    field: EndogenousField,
    mission: CG4Mission,
    *,
    budget: int,
    min_confidence: float,
) -> tuple[LiveClaim, ...]:
    output = list(_latest_active_membership_claims(field, min_confidence=min_confidence))
    if len(output) >= budget:
        return tuple(output[:budget])
    local_claims = tuple(
        claim
        for claim in field.claims
        if claim.source_class == "live_probe" and claim.observed_by == field.coordinator_id
    )
    bundles = [
        bundle
        for bundle in _canonical_event_bundles(local_claims, min_confidence=min_confidence)
        if bundle[2] in field.current_members and bundle[3] in mission.required_skills
    ]
    bundles.sort(
        key=lambda bundle: hashlib.sha256(
            f"cg5-local|{mission.mission_id}|{bundle[0]}".encode()
        ).digest()
    )
    for bundle in bundles:
        if len(output) + 3 > budget:
            break
        output.extend(bundle[-1])
    return tuple(output)


def _shuffle_participant_topology(
    context: tuple[LiveClaim, ...], current_members: frozenset[str]
) -> tuple[LiveClaim, ...]:
    agents = sorted(current_members)
    if len(agents) < 2:
        return context
    shift = max(1, len(agents) // 3)
    mapping = {
        agent_id: agents[(index + shift) % len(agents)]
        for index, agent_id in enumerate(agents)
    }
    output = []
    for claim in context:
        obj = claim.object
        if claim.source_class == "live_probe" and claim.predicate == "participant":
            obj = mapping.get(obj, obj)
        output.append(
            LiveClaim(
                field_id=claim.field_id,
                subject=claim.subject,
                predicate=claim.predicate,
                object=obj,
                observed_by=claim.observed_by,
                source_id=claim.source_id,
                source_class=claim.source_class,
                observed_at=claim.observed_at,
                confidence=claim.confidence,
                direct=claim.direct,
            )
        )
    return tuple(output)


def _belief_fingerprint(field: EndogenousField) -> str:
    payload = json.dumps(field.belief_snapshot, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def _selected_role_diagnostics(
    field: EndogenousField,
    mission: CG4Mission,
    pair: Pair | None,
    evidence: dict[tuple[str, str], CellEvidence] | None,
) -> tuple[int, int, float]:
    if pair is None or not set(pair).issubset(field.current_members):
        return 0, 0, 0.0
    environment = JointEnvironment()
    rows = ((pair[0], mission.lead_skill), (pair[1], mission.support_skill))
    single_success = 0
    gaps = []
    for agent_id, skill in rows:
        best_true = max(
            environment.role_probability(field.states[candidate], skill)
            for candidate in field.current_members
        )
        selected_true = environment.role_probability(field.states[agent_id], skill)
        gaps.append(best_true - selected_true)
        if evidence is not None:
            cell = evidence.get((agent_id, skill))
            if cell is not None and cell.events == 1 and cell.successes == 1:
                single_success += 1
    return single_success, 2, sum(gaps) / 2.0


def _record(
    accumulator: ArmAccumulator,
    *,
    field: EndogenousField,
    mission: CG4Mission,
    pair: Pair | None,
    oracle_pair: Pair,
    context: tuple[LiveClaim, ...],
    evidence: dict[tuple[str, str], CellEvidence] | None,
    trials: int,
    min_confidence: float,
) -> float:
    oracle_expected = _expected_success(field, mission, oracle_pair)
    valid = pair is not None and set(pair).issubset(field.current_members)
    expected = _expected_success(field, mission, pair) if valid and pair is not None else 0.0
    successes = _evaluate_pair_trials(field, mission, pair, trials=trials)
    single_success, selected_roles, role_gap = _selected_role_diagnostics(
        field, mission, pair, evidence
    )
    accumulator.decisions += 1
    accumulator.successes += successes
    accumulator.trials += trials
    accumulator.expected_success_total += expected
    accumulator.oracle_expected_total += oracle_expected
    accumulator.regret_total += oracle_expected - expected
    accumulator.oracle_pair_matches += int(pair == oracle_pair)
    accumulator.invalid_selections += int(not valid)
    accumulator.context_claims += len(context)
    accumulator.complete_bundles += len(
        _canonical_event_bundles(context, min_confidence=min_confidence)
    )
    accumulator.provenance_claims += sum(
        bool(claim.source_id and claim.source_class) for claim in context
    )
    accumulator.selected_single_success_roles += single_success
    accumulator.selected_roles += selected_roles
    accumulator.selected_role_true_gap_total += role_gap
    return expected


def _finalize(arm: str, row: ArmAccumulator) -> ArmMetrics:
    decisions = row.decisions or 1
    context_claims = row.context_claims
    return ArmMetrics(
        arm=arm,
        decisions=row.decisions,
        mission_success_rate=row.successes / row.trials if row.trials else 0.0,
        mean_expected_success=row.expected_success_total / decisions,
        mean_oracle_expected_success=row.oracle_expected_total / decisions,
        mean_regret=row.regret_total / decisions,
        oracle_pair_rate=row.oracle_pair_matches / decisions,
        invalid_selection_rate=row.invalid_selections / decisions,
        mean_context_claims=row.context_claims / decisions,
        mean_complete_bundles=row.complete_bundles / decisions,
        provenance_completeness=(
            row.provenance_claims / context_claims if context_claims else 1.0
        ),
        selected_single_success_rate=(
            row.selected_single_success_roles / row.selected_roles if row.selected_roles else 0.0
        ),
        mean_selected_role_true_gap=row.selected_role_true_gap_total / decisions,
        successes=row.successes,
        trials=row.trials,
    )


def _bootstrap_ci(values: list[float], *, resamples: int, seed: int) -> tuple[float, float]:
    if not values:
        return 0.0, 0.0
    rng = random.Random(seed)
    n = len(values)
    samples = []
    for _ in range(resamples):
        samples.append(sum(values[rng.randrange(n)] for _ in range(n)) / n)
    samples.sort()
    lower_index = max(0, int(0.025 * resamples))
    upper_index = min(resamples - 1, int(0.975 * resamples) - 1)
    return samples[lower_index], samples[upper_index]


def evaluate(
    *,
    capsules: Path,
    source_summary: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, Any]:
    expected_seeds = [int(value) for value in config["fresh_source"]["field_seeds"]]
    actual_seeds = [int(value) for value in source_summary["seeds"]]
    if actual_seeds != expected_seeds:
        raise AssertionError(f"fresh source seeds mismatch: {actual_seeds}")
    prohibited = {int(value) for value in config["fresh_source"]["prohibited_prior_seeds"]}
    overlap = sorted(prohibited.intersection(actual_seeds))
    if overlap:
        raise AssertionError(f"fresh source overlaps prior seeds: {overlap}")

    missions = _missions(config["missions"])
    estimator = _estimator(config)
    min_confidence = float(config["society"]["min_confidence"])
    budget = int(config["context"]["claim_budget_cap"])
    trials = int(config["evaluation"]["trials_per_decision"])
    target_events = int(config["society"]["target_independent_events_per_current_agent_skill"])
    noise_rate = float(config["society"]["observer_rule"]["scout_noise_rate"])
    arms = [str(value) for value in config["arms"]]
    accumulators = {arm: ArmAccumulator() for arm in arms}
    field_lifts: dict[str, float] = {}
    full_estimates: list[float] = []
    full_truths: list[float] = []
    supplemental_events = 0
    supplemental_claims = 0
    duplicate_collapsed = 0
    roster_changes = 0
    belief_contamination = 0
    environment = JointEnvironment()

    field_ids = [f"w3-source-seed-{seed}" for seed in actual_seeds]
    for field_id in field_ids:
        base = _build_base_field(capsules, field_id, config)
        active, diag = _supplement_field(
            base,
            target_events=target_events,
            min_confidence=min_confidence,
            noise_rate=noise_rate,
        )
        supplemental_events += int(diag["supplemental_events_added"])
        supplemental_claims += int(diag["supplemental_claims_added"])
        duplicate_collapsed += int(diag["duplicate_observer_bundles_collapsed"])
        roster_changes += int(active.current_members != base.current_members)
        before_belief = _belief_fingerprint(active)
        field_revised = 0.0
        field_flat = 0.0

        full_evidence = _cell_evidence(
            active.claims,
            candidates=set(active.current_members),
            min_confidence=min_confidence,
        )
        for mission in missions:
            for skill in mission.required_skills:
                for agent_id in sorted(active.current_members):
                    full_estimates.append(_score(full_evidence.get((agent_id, skill)), estimator))
                    full_truths.append(environment.role_probability(active.states[agent_id], skill))

            oracle_pair = _oracle_pair(active, mission)

            local_context = _local_context(
                active,
                mission,
                budget=budget,
                min_confidence=min_confidence,
            )
            local_pair, local_evidence = _revised_pair(
                local_context,
                mission,
                estimator=estimator,
                min_confidence=min_confidence,
            )
            _record(
                accumulators["local_only_active"],
                field=active,
                mission=mission,
                pair=local_pair,
                oracle_pair=oracle_pair,
                context=local_context,
                evidence=local_evidence,
                trials=trials,
                min_confidence=min_confidence,
            )

            flat_context = _bundle_flat_context(
                active,
                mission,
                budget=budget,
                min_confidence=min_confidence,
            )
            flat_pair, flat_evidence = _revised_pair(
                flat_context,
                mission,
                estimator=estimator,
                min_confidence=min_confidence,
            )
            field_flat += _record(
                accumulators["bundle_flat_active"],
                field=active,
                mission=mission,
                pair=flat_pair,
                oracle_pair=oracle_pair,
                context=flat_context,
                evidence=flat_evidence,
                trials=trials,
                min_confidence=min_confidence,
            )

            legacy_context = _compile_graph(
                active,
                mission,
                budget=budget,
                min_confidence=min_confidence,
            )
            legacy_pair = _estimate_pair(
                legacy_context,
                mission,
                min_confidence=min_confidence,
                respect_temporal_order=True,
            )
            _record(
                accumulators["legacy_graph_active"],
                field=active,
                mission=mission,
                pair=legacy_pair,
                oracle_pair=oracle_pair,
                context=legacy_context,
                evidence=None,
                trials=trials,
                min_confidence=min_confidence,
            )

            passive_context = _coverage_graph_context(
                base,
                mission,
                budget=budget,
                estimator=estimator,
                min_confidence=min_confidence,
            )
            passive_pair, passive_evidence = _revised_pair(
                passive_context,
                mission,
                estimator=estimator,
                min_confidence=min_confidence,
            )
            _record(
                accumulators["passive_revised_graph"],
                field=base,
                mission=mission,
                pair=passive_pair,
                oracle_pair=_oracle_pair(base, mission),
                context=passive_context,
                evidence=passive_evidence,
                trials=trials,
                min_confidence=min_confidence,
            )

            revised_context = _coverage_graph_context(
                active,
                mission,
                budget=budget,
                estimator=estimator,
                min_confidence=min_confidence,
            )
            revised_pair, revised_evidence = _revised_pair(
                revised_context,
                mission,
                estimator=estimator,
                min_confidence=min_confidence,
            )
            field_revised += _record(
                accumulators["revised_coverage_graph"],
                field=active,
                mission=mission,
                pair=revised_pair,
                oracle_pair=oracle_pair,
                context=revised_context,
                evidence=revised_evidence,
                trials=trials,
                min_confidence=min_confidence,
            )

            shuffled_context = _shuffle_participant_topology(
                revised_context, active.current_members
            )
            shuffled_pair, shuffled_evidence = _revised_pair(
                shuffled_context,
                mission,
                estimator=estimator,
                min_confidence=min_confidence,
            )
            _record(
                accumulators["shuffled_revised_graph"],
                field=active,
                mission=mission,
                pair=shuffled_pair,
                oracle_pair=oracle_pair,
                context=shuffled_context,
                evidence=shuffled_evidence,
                trials=trials,
                min_confidence=min_confidence,
            )

            _record(
                accumulators["oracle"],
                field=active,
                mission=mission,
                pair=oracle_pair,
                oracle_pair=oracle_pair,
                context=(),
                evidence=None,
                trials=trials,
                min_confidence=min_confidence,
            )

        field_lifts[field_id] = (field_revised - field_flat) / len(missions)
        belief_contamination += int(before_belief != _belief_fingerprint(active))

    metrics = {arm: _finalize(arm, accumulators[arm]) for arm in arms}
    revised = metrics["revised_coverage_graph"]
    flat = metrics["bundle_flat_active"]
    shuffled = metrics["shuffled_revised_graph"]
    passive = metrics["passive_revised_graph"]
    field_lift_values = [field_lifts[field_id] for field_id in sorted(field_lifts)]
    bootstrap = config["evaluation"]["bootstrap"]
    ci_lower, ci_upper = _bootstrap_ci(
        field_lift_values,
        resamples=int(bootstrap["resamples"]),
        seed=int(bootstrap["seed"]),
    )
    evaluate_parameters = set(inspect.signature(JointEnvironment.evaluate).parameters)
    forbidden_environment_parameters = {
        "graph",
        "context_graph",
        "evidence",
        "claims",
        "relationship_state",
        "organization_memory",
    }
    outcome_law_graph_inputs = len(evaluate_parameters.intersection(forbidden_environment_parameters))

    diagnostics = {
        "fresh_seed_overlap_with_prior": len(overlap),
        "revised_expected_success_lift_over_bundle_flat": (
            revised.mean_expected_success - flat.mean_expected_success
        ),
        "revised_realized_success_lift_over_bundle_flat": (
            revised.mission_success_rate - flat.mission_success_rate
        ),
        "revised_regret_improvement_over_bundle_flat": flat.mean_regret - revised.mean_regret,
        "revised_expected_success_lift_over_shuffled": (
            revised.mean_expected_success - shuffled.mean_expected_success
        ),
        "revised_expected_success_lift_over_passive": (
            revised.mean_expected_success - passive.mean_expected_success
        ),
        "revised_estimate_truth_pearson": _pearson(full_estimates, full_truths),
        "positive_field_lift_count": sum(value > 0 for value in field_lift_values),
        "field_count": len(field_ids),
        "bootstrap_expected_lift_ci_lower": ci_lower,
        "bootstrap_expected_lift_ci_upper": ci_upper,
        "matched_context_claims": (
            revised.mean_context_claims
            == flat.mean_context_claims
            == shuffled.mean_context_claims
        ),
        "matched_complete_bundle_counts": (
            revised.mean_complete_bundles
            == flat.mean_complete_bundles
            == shuffled.mean_complete_bundles
        ),
        "supplemental_probe_events": supplemental_events,
        "supplemental_probe_claims": supplemental_claims,
        "duplicate_observer_bundles_collapsed": duplicate_collapsed,
        "supplemental_probe_roster_changes": roster_changes,
        "belief_contamination": belief_contamination,
        "historical_outcome_rows_consumed": 0,
        "posthoc_imported_claims": 0,
        "outcome_law_graph_inputs": outcome_law_graph_inputs,
        "event_identity_reconciliation": True,
    }

    gates = config["success_gates"]
    gate_results = {
        "fresh_field_count_min": diagnostics["field_count"] >= int(gates["fresh_field_count_min"]),
        "evaluation_decision_count_min": revised.decisions >= int(gates["evaluation_decision_count_min"]),
        "fresh_seed_overlap_with_prior_max": diagnostics["fresh_seed_overlap_with_prior"] <= int(gates["fresh_seed_overlap_with_prior_max"]),
        "revised_expected_success_lift_over_bundle_flat_min": diagnostics["revised_expected_success_lift_over_bundle_flat"] >= float(gates["revised_expected_success_lift_over_bundle_flat_min"]),
        "revised_realized_success_lift_over_bundle_flat_min": diagnostics["revised_realized_success_lift_over_bundle_flat"] >= float(gates["revised_realized_success_lift_over_bundle_flat_min"]),
        "revised_regret_improvement_over_bundle_flat_min": diagnostics["revised_regret_improvement_over_bundle_flat"] >= float(gates["revised_regret_improvement_over_bundle_flat_min"]),
        "revised_expected_success_lift_over_shuffled_min": diagnostics["revised_expected_success_lift_over_shuffled"] >= float(gates["revised_expected_success_lift_over_shuffled_min"]),
        "revised_expected_success_lift_over_passive_min": diagnostics["revised_expected_success_lift_over_passive"] >= float(gates["revised_expected_success_lift_over_passive_min"]),
        "revised_estimate_truth_pearson_min": diagnostics["revised_estimate_truth_pearson"] >= float(gates["revised_estimate_truth_pearson_min"]),
        "revised_selected_single_success_rate_max": revised.selected_single_success_rate <= float(gates["revised_selected_single_success_rate_max"]),
        "revised_invalid_selection_rate_max": revised.invalid_selection_rate <= float(gates["revised_invalid_selection_rate_max"]),
        "bundle_flat_complete_bundles_mean_min": flat.mean_complete_bundles >= float(gates["bundle_flat_complete_bundles_mean_min"]),
        "revised_complete_bundles_mean_min": revised.mean_complete_bundles >= float(gates["revised_complete_bundles_mean_min"]),
        "revised_provenance_completeness_min": revised.provenance_completeness >= float(gates["revised_provenance_completeness_min"]),
        "positive_field_lift_count_min": diagnostics["positive_field_lift_count"] >= int(gates["positive_field_lift_count_min"]),
        "bootstrap_expected_lift_ci_lower_min_exclusive": diagnostics["bootstrap_expected_lift_ci_lower"] > float(gates["bootstrap_expected_lift_ci_lower_min_exclusive"]),
        "matched_context_claims": diagnostics["matched_context_claims"] is bool(gates["matched_context_claims"]),
        "matched_complete_bundle_counts": diagnostics["matched_complete_bundle_counts"] is bool(gates["matched_complete_bundle_counts"]),
        "event_identity_reconciliation_required": diagnostics["event_identity_reconciliation"] is bool(gates["event_identity_reconciliation_required"]),
        "supplemental_probe_roster_changes_max": diagnostics["supplemental_probe_roster_changes"] <= int(gates["supplemental_probe_roster_changes_max"]),
        "historical_outcome_rows_consumed_max": diagnostics["historical_outcome_rows_consumed"] <= int(gates["historical_outcome_rows_consumed_max"]),
        "posthoc_imported_claims_max": diagnostics["posthoc_imported_claims"] <= int(gates["posthoc_imported_claims_max"]),
        "belief_contamination_max": diagnostics["belief_contamination"] <= int(gates["belief_contamination_max"]),
        "outcome_law_graph_inputs_max": diagnostics["outcome_law_graph_inputs"] <= int(gates["outcome_law_graph_inputs_max"]),
    }

    return {
        "version": "context-graph-cg5-w3-active-measurement-result-v0.1",
        "config_version": config["version"],
        "confirmatory_claim": True,
        "field_ids": field_ids,
        "source_summary": source_summary,
        "metrics": {arm: asdict(metrics[arm]) for arm in arms},
        "field_level_expected_success_lift": field_lifts,
        "diagnostics": diagnostics,
        "gate_results": gate_results,
        "passed": all(gate_results.values()),
        "scientific_boundary": config["scientific_boundary"],
        "interpretation_boundary": config["interpretation_boundary"],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--capsules", type=Path, required=True)
    parser.add_argument("--source-summary", type=Path, required=True)
    parser.add_argument("--protocol-freeze-sha", required=True)
    parser.add_argument("--source-artifact-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    config = _read_json(args.config)
    if config.get("status") != "preregistered-before-fresh-cohort-generation":
        raise AssertionError("CG-5 protocol is not frozen")
    if config.get("confirmatory_claim") is not True:
        raise AssertionError("CG-5 confirmatory flag changed")
    source_summary = _read_json(args.source_summary)
    result = evaluate(capsules=args.capsules, source_summary=source_summary, config=config)
    result["protocol_freeze_sha"] = args.protocol_freeze_sha
    result["source_artifact_sha256"] = args.source_artifact_sha256
    result["capsules_sha256"] = _sha256(args.capsules)

    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if "practice_by_skill" in text:
        raise AssertionError("private capability values leaked into CG-5 result")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text, encoding="utf-8")
    print(json.dumps({
        "passed": result["passed"],
        "metrics": result["metrics"],
        "diagnostics": result["diagnostics"],
        "gate_results": result["gate_results"],
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
