"""Execute preregistered CG-5 on a fresh W3-derived cohort.

Fresh private capsules instantiate hidden capability only. All decision evidence is
created online. The active measurement policy, estimator, retrieval policy, missions,
and gates are frozen before fresh source generation.
"""

from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import random
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


@dataclass(slots=True)
class Accumulator:
    decisions: int = 0
    successes: int = 0
    trials: int = 0
    expected: float = 0.0
    oracle_expected: float = 0.0
    regret: float = 0.0
    oracle_matches: int = 0
    invalid: int = 0
    context_claims: int = 0
    complete_bundles: int = 0
    provenance_claims: int = 0
    single_success_roles: int = 0
    selected_roles: int = 0
    role_gap: float = 0.0


@dataclass(frozen=True, slots=True)
class Metrics:
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


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def missions(config: dict[str, Any]) -> list[CG4Mission]:
    return [
        CG4Mission(
            mission_id=str(row["mission_id"]),
            lead_skill=str(row["lead_skill"]),
            support_skill=str(row["support_skill"]),
        )
        for row in config["missions"]
    ]


def estimator(config: dict[str, Any]) -> EstimatorSpec:
    row = config["estimator"]
    return EstimatorSpec(
        name=str(row["name"]),
        kind=str(row["kind"]),
        min_support=int(row["minimum_independent_event_support"]),
        fallback_score=float(row["fallback_score"]),
        z=float(row["z"]),
    )


def base_field(capsules: Path, field_id: str, config: dict[str, Any]) -> EndogenousField:
    row = config["society"]
    return build_endogenous_field(
        capsules_path=capsules,
        field_id=field_id,
        initial_roster_size=int(row["initial_roster_size"]),
        turnover_count=int(row["turnover_count"]),
        probes_per_skill=int(row["initial_probes_per_skill"]),
        skills_per_agent=int(row["initial_skills_per_agent"]),
        noise_rate=float(row["observation_noise_rate"]),
        rumor_count=int(row["rumor_count"]),
    )


def revised_pair(
    context: tuple[LiveClaim, ...],
    mission: CG4Mission,
    spec: EstimatorSpec,
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
    return _select_pair(candidates, mission, evidence, spec), evidence


def local_context(
    field: EndogenousField,
    mission: CG4Mission,
    budget: int,
    min_confidence: float,
) -> tuple[LiveClaim, ...]:
    output = list(_latest_active_membership_claims(field, min_confidence=min_confidence))
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
    return tuple(output[:budget])


def shuffle_participant_topology(
    context: tuple[LiveClaim, ...], current_members: frozenset[str]
) -> tuple[LiveClaim, ...]:
    agents = sorted(current_members)
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


def belief_fingerprint(field: EndogenousField) -> str:
    payload = json.dumps(field.belief_snapshot, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def selected_role_diagnostics(
    field: EndogenousField,
    mission: CG4Mission,
    pair: Pair | None,
    evidence: dict[tuple[str, str], CellEvidence] | None,
) -> tuple[int, int, float]:
    if pair is None or not set(pair).issubset(field.current_members):
        return 0, 0, 0.0
    environment = JointEnvironment()
    single_success = 0
    gaps = []
    for agent_id, skill in ((pair[0], mission.lead_skill), (pair[1], mission.support_skill)):
        best = max(
            environment.role_probability(field.states[candidate], skill)
            for candidate in field.current_members
        )
        selected = environment.role_probability(field.states[agent_id], skill)
        gaps.append(best - selected)
        if evidence is not None:
            cell = evidence.get((agent_id, skill))
            if cell is not None and cell.events == 1 and cell.successes == 1:
                single_success += 1
    return single_success, 2, sum(gaps) / 2.0


def record(
    acc: Accumulator,
    *,
    field: EndogenousField,
    mission: CG4Mission,
    pair: Pair | None,
    oracle: Pair,
    context: tuple[LiveClaim, ...],
    evidence: dict[tuple[str, str], CellEvidence] | None,
    trials: int,
    min_confidence: float,
) -> float:
    oracle_expected = _expected_success(field, mission, oracle)
    valid = pair is not None and set(pair).issubset(field.current_members)
    expected = _expected_success(field, mission, pair) if valid and pair is not None else 0.0
    successes = _evaluate_pair_trials(field, mission, pair, trials=trials)
    single, selected_roles, role_gap = selected_role_diagnostics(field, mission, pair, evidence)
    acc.decisions += 1
    acc.successes += successes
    acc.trials += trials
    acc.expected += expected
    acc.oracle_expected += oracle_expected
    acc.regret += oracle_expected - expected
    acc.oracle_matches += int(pair == oracle)
    acc.invalid += int(not valid)
    acc.context_claims += len(context)
    acc.complete_bundles += len(
        _canonical_event_bundles(context, min_confidence=min_confidence)
    )
    acc.provenance_claims += sum(bool(row.source_id and row.source_class) for row in context)
    acc.single_success_roles += single
    acc.selected_roles += selected_roles
    acc.role_gap += role_gap
    return expected


def finalize(arm: str, acc: Accumulator) -> Metrics:
    n = acc.decisions or 1
    return Metrics(
        arm=arm,
        decisions=acc.decisions,
        mission_success_rate=acc.successes / acc.trials if acc.trials else 0.0,
        mean_expected_success=acc.expected / n,
        mean_oracle_expected_success=acc.oracle_expected / n,
        mean_regret=acc.regret / n,
        oracle_pair_rate=acc.oracle_matches / n,
        invalid_selection_rate=acc.invalid / n,
        mean_context_claims=acc.context_claims / n,
        mean_complete_bundles=acc.complete_bundles / n,
        provenance_completeness=(
            acc.provenance_claims / acc.context_claims if acc.context_claims else 1.0
        ),
        selected_single_success_rate=(
            acc.single_success_roles / acc.selected_roles if acc.selected_roles else 0.0
        ),
        mean_selected_role_true_gap=acc.role_gap / n,
        successes=acc.successes,
        trials=acc.trials,
    )


def bootstrap_ci(values: list[float], *, resamples: int, seed: int) -> tuple[float, float]:
    rng = random.Random(seed)
    n = len(values)
    samples = sorted(
        sum(values[rng.randrange(n)] for _ in range(n)) / n for _ in range(resamples)
    )
    return samples[int(0.025 * resamples)], samples[int(0.975 * resamples) - 1]


def evaluate(capsules: Path, source_summary: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    expected_seeds = [int(value) for value in config["fresh_source"]["field_seeds"]]
    actual_seeds = [int(value) for value in source_summary["seeds"]]
    if actual_seeds != expected_seeds:
        raise AssertionError(f"fresh source seeds mismatch: {actual_seeds}")
    prohibited = {int(value) for value in config["fresh_source"]["prohibited_prior_seeds"]}
    overlap = sorted(prohibited.intersection(actual_seeds))
    if overlap:
        raise AssertionError(f"fresh source overlaps prior seeds: {overlap}")

    mission_rows = missions(config)
    spec = estimator(config)
    min_confidence = float(config["society"]["min_confidence"])
    budget = int(config["context"]["claim_budget_cap"])
    trials = int(config["evaluation"]["trials_per_decision"])
    target_events = int(config["society"]["target_independent_events_per_current_agent_skill"])
    noise_rate = float(config["society"]["observer_rule"]["scout_noise_rate"])
    arm_names = [str(value) for value in config["arms"]]
    acc = {arm: Accumulator() for arm in arm_names}
    field_lifts: dict[str, float] = {}
    estimates: list[float] = []
    truths: list[float] = []
    supplemental_events = 0
    supplemental_claims = 0
    duplicate_collapsed = 0
    roster_changes = 0
    belief_contamination = 0
    environment = JointEnvironment()

    field_ids = [f"w3-source-seed-{seed}" for seed in actual_seeds]
    for field_id in field_ids:
        base = base_field(capsules, field_id, config)
        active, event_diag = _supplement_field(
            base,
            target_events=target_events,
            min_confidence=min_confidence,
            noise_rate=noise_rate,
        )
        supplemental_events += int(event_diag["supplemental_events_added"])
        supplemental_claims += int(event_diag["supplemental_claims_added"])
        duplicate_collapsed += int(event_diag["duplicate_observer_bundles_collapsed"])
        roster_changes += int(base.current_members != active.current_members)
        belief_before = belief_fingerprint(active)
        field_revised = 0.0
        field_flat = 0.0

        full_evidence = _cell_evidence(
            active.claims,
            candidates=set(active.current_members),
            min_confidence=min_confidence,
        )
        for mission in mission_rows:
            for skill in mission.required_skills:
                for agent_id in sorted(active.current_members):
                    estimates.append(_score(full_evidence.get((agent_id, skill)), spec))
                    truths.append(environment.role_probability(active.states[agent_id], skill))

            oracle = _oracle_pair(active, mission)
            local = local_context(active, mission, budget, min_confidence)
            flat = _bundle_flat_context(
                active, mission, budget=budget, min_confidence=min_confidence
            )
            legacy = _compile_graph(
                active,
                mission,
                budget=budget,
                min_confidence=min_confidence,
                respect_temporal_order=True,
            )
            passive = _coverage_graph_context(
                base,
                mission,
                budget=budget,
                estimator=spec,
                min_confidence=min_confidence,
            )
            revised = _coverage_graph_context(
                active,
                mission,
                budget=budget,
                estimator=spec,
                min_confidence=min_confidence,
            )
            shuffled = shuffle_participant_topology(revised, active.current_members)

            local_pair, local_evidence = revised_pair(local, mission, spec, min_confidence)
            flat_pair, flat_evidence = revised_pair(flat, mission, spec, min_confidence)
            legacy_pair = _estimate_pair(
                legacy,
                mission,
                min_confidence=min_confidence,
                respect_temporal_order=True,
            )
            passive_pair, passive_evidence = revised_pair(passive, mission, spec, min_confidence)
            revised_pair_value, revised_evidence = revised_pair(
                revised, mission, spec, min_confidence
            )
            shuffled_pair, shuffled_evidence = revised_pair(
                shuffled, mission, spec, min_confidence
            )

            record(
                acc["local_only_active"],
                field=active,
                mission=mission,
                pair=local_pair,
                oracle=oracle,
                context=local,
                evidence=local_evidence,
                trials=trials,
                min_confidence=min_confidence,
            )
            field_flat += record(
                acc["bundle_flat_active"],
                field=active,
                mission=mission,
                pair=flat_pair,
                oracle=oracle,
                context=flat,
                evidence=flat_evidence,
                trials=trials,
                min_confidence=min_confidence,
            )
            record(
                acc["legacy_graph_active"],
                field=active,
                mission=mission,
                pair=legacy_pair,
                oracle=oracle,
                context=legacy,
                evidence=None,
                trials=trials,
                min_confidence=min_confidence,
            )
            record(
                acc["passive_revised_graph"],
                field=base,
                mission=mission,
                pair=passive_pair,
                oracle=_oracle_pair(base, mission),
                context=passive,
                evidence=passive_evidence,
                trials=trials,
                min_confidence=min_confidence,
            )
            field_revised += record(
                acc["revised_coverage_graph"],
                field=active,
                mission=mission,
                pair=revised_pair_value,
                oracle=oracle,
                context=revised,
                evidence=revised_evidence,
                trials=trials,
                min_confidence=min_confidence,
            )
            record(
                acc["shuffled_revised_graph"],
                field=active,
                mission=mission,
                pair=shuffled_pair,
                oracle=oracle,
                context=shuffled,
                evidence=shuffled_evidence,
                trials=trials,
                min_confidence=min_confidence,
            )
            record(
                acc["oracle"],
                field=active,
                mission=mission,
                pair=oracle,
                oracle=oracle,
                context=(),
                evidence=None,
                trials=trials,
                min_confidence=min_confidence,
            )

        field_lifts[field_id] = (field_revised - field_flat) / len(mission_rows)
        belief_contamination += int(belief_before != belief_fingerprint(active))

    metrics = {arm: finalize(arm, acc[arm]) for arm in arm_names}
    revised_metrics = metrics["revised_coverage_graph"]
    flat_metrics = metrics["bundle_flat_active"]
    shuffled_metrics = metrics["shuffled_revised_graph"]
    passive_metrics = metrics["passive_revised_graph"]
    field_values = [field_lifts[key] for key in sorted(field_lifts)]
    bootstrap = config["evaluation"]["bootstrap"]
    ci_lower, ci_upper = bootstrap_ci(
        field_values,
        resamples=int(bootstrap["resamples"]),
        seed=int(bootstrap["seed"]),
    )
    forbidden = {
        "graph",
        "context_graph",
        "evidence",
        "claims",
        "relationship_state",
        "organization_memory",
    }
    outcome_law_graph_inputs = len(
        forbidden.intersection(inspect.signature(JointEnvironment.evaluate).parameters)
    )

    diagnostics = {
        "field_count": len(field_ids),
        "fresh_seed_overlap_with_prior": len(overlap),
        "revised_expected_success_lift_over_bundle_flat": revised_metrics.mean_expected_success - flat_metrics.mean_expected_success,
        "revised_realized_success_lift_over_bundle_flat": revised_metrics.mission_success_rate - flat_metrics.mission_success_rate,
        "revised_regret_improvement_over_bundle_flat": flat_metrics.mean_regret - revised_metrics.mean_regret,
        "revised_expected_success_lift_over_shuffled": revised_metrics.mean_expected_success - shuffled_metrics.mean_expected_success,
        "revised_expected_success_lift_over_passive": revised_metrics.mean_expected_success - passive_metrics.mean_expected_success,
        "revised_estimate_truth_pearson": _pearson(estimates, truths),
        "positive_field_lift_count": sum(value > 0 for value in field_values),
        "bootstrap_expected_lift_ci_lower": ci_lower,
        "bootstrap_expected_lift_ci_upper": ci_upper,
        "matched_context_claims": revised_metrics.mean_context_claims == flat_metrics.mean_context_claims == shuffled_metrics.mean_context_claims,
        "matched_complete_bundle_counts": revised_metrics.mean_complete_bundles == flat_metrics.mean_complete_bundles == shuffled_metrics.mean_complete_bundles,
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
        "evaluation_decision_count_min": revised_metrics.decisions >= int(gates["evaluation_decision_count_min"]),
        "fresh_seed_overlap_with_prior_max": diagnostics["fresh_seed_overlap_with_prior"] <= int(gates["fresh_seed_overlap_with_prior_max"]),
        "revised_expected_success_lift_over_bundle_flat_min": diagnostics["revised_expected_success_lift_over_bundle_flat"] >= float(gates["revised_expected_success_lift_over_bundle_flat_min"]),
        "revised_realized_success_lift_over_bundle_flat_min": diagnostics["revised_realized_success_lift_over_bundle_flat"] >= float(gates["revised_realized_success_lift_over_bundle_flat_min"]),
        "revised_regret_improvement_over_bundle_flat_min": diagnostics["revised_regret_improvement_over_bundle_flat"] >= float(gates["revised_regret_improvement_over_bundle_flat_min"]),
        "revised_expected_success_lift_over_shuffled_min": diagnostics["revised_expected_success_lift_over_shuffled"] >= float(gates["revised_expected_success_lift_over_shuffled_min"]),
        "revised_expected_success_lift_over_passive_min": diagnostics["revised_expected_success_lift_over_passive"] >= float(gates["revised_expected_success_lift_over_passive_min"]),
        "revised_estimate_truth_pearson_min": diagnostics["revised_estimate_truth_pearson"] >= float(gates["revised_estimate_truth_pearson_min"]),
        "revised_selected_single_success_rate_max": revised_metrics.selected_single_success_rate <= float(gates["revised_selected_single_success_rate_max"]),
        "revised_invalid_selection_rate_max": revised_metrics.invalid_selection_rate <= float(gates["revised_invalid_selection_rate_max"]),
        "bundle_flat_complete_bundles_mean_min": flat_metrics.mean_complete_bundles >= float(gates["bundle_flat_complete_bundles_mean_min"]),
        "revised_complete_bundles_mean_min": revised_metrics.mean_complete_bundles >= float(gates["revised_complete_bundles_mean_min"]),
        "revised_provenance_completeness_min": revised_metrics.provenance_completeness >= float(gates["revised_provenance_completeness_min"]),
        "positive_field_lift_count_min": diagnostics["positive_field_lift_count"] >= int(gates["positive_field_lift_count_min"]),
        "bootstrap_expected_lift_ci_lower_min_exclusive": diagnostics["bootstrap_expected_lift_ci_lower"] > float(gates["bootstrap_expected_lift_ci_lower_min_exclusive"]),
        "matched_context_claims": diagnostics["matched_context_claims"] == bool(gates["matched_context_claims"]),
        "matched_complete_bundle_counts": diagnostics["matched_complete_bundle_counts"] == bool(gates["matched_complete_bundle_counts"]),
        "event_identity_reconciliation_required": diagnostics["event_identity_reconciliation"] == bool(gates["event_identity_reconciliation_required"]),
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
        "metrics": {arm: asdict(metrics[arm]) for arm in arm_names},
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

    config = read_json(args.config)
    if config.get("status") != "preregistered-before-fresh-cohort-generation":
        raise AssertionError("CG-5 protocol is not frozen")
    if config.get("confirmatory_claim") is not True:
        raise AssertionError("CG-5 confirmatory flag changed")
    result = evaluate(args.capsules, read_json(args.source_summary), config)
    result["protocol_freeze_sha"] = args.protocol_freeze_sha
    result["source_artifact_sha256"] = args.source_artifact_sha256
    result["capsules_sha256"] = sha256(args.capsules)
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
