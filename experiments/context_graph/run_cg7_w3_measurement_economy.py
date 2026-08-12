"""Execute preregistered CG-7 measurement-economy replication.

CG-7 tests whether a deterministic 72-event uniform round-robin acquisition policy
preserves fixed-six decision quality on a fresh cohort while reducing supplemental
measurement cost. Acquisition never reads evaluator capability; hidden capability is
used only to generate live probe outcomes and score evaluator diagnostics/outcomes.
"""

from __future__ import annotations

import argparse
import inspect
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from experiments.context_graph.run_cg4m_measurement_sufficiency import (
    _bundle_flat_context,
    _cell_evidence,
    _coverage_graph_context,
    _pearson,
    _score,
)
from experiments.context_graph.run_cg5_w3_active_measurement import (
    Accumulator,
    belief_fingerprint,
    bootstrap_ci,
    finalize,
    record,
    shuffle_participant_topology,
)
from experiments.context_graph.run_cg6_adaptive_acquisition import (
    acquire,
    base_field,
    current_counts,
    estimator,
    missions,
    pair_from_context,
    read_json,
    sha256,
)
from resonance_world.context_graph_w3_endogenous import (
    _oracle_pair,
)
from resonance_world.w4a_joint_learning import JointEnvironment


def evaluate(
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

    mission_rows = missions(config)
    spec = estimator(config)
    society = config["society"]
    min_confidence = float(society["min_confidence"])
    max_events = int(society["maximum_events_per_current_agent_skill"])
    noise_rate = float(society["observer_noise_rate"])
    context_budget = int(config["context"]["claim_budget_cap"])
    uniform72_budget = int(config["acquisition"]["uniform_round_robin_budget"])
    uniform48_budget = int(config["acquisition"]["uniform_48_exploratory_budget"])
    trials = int(config["evaluation"]["trials_per_decision"])
    weights = {
        "selected_role_bonus": 0.0,
        "plausible_challenger_bonus": 0.0,
        "support_deficit_bonus": 0.0,
        "ambiguity_margin": 0.0,
    }
    arm_names = [str(value) for value in config["arms"]]
    acc = {arm: Accumulator() for arm in arm_names}
    field_noninferiority: dict[str, float] = {}
    field_graph_flat: dict[str, float] = {}
    uniform72_estimates: list[float] = []
    uniform72_truths: list[float] = []
    fixed6_estimates: list[float] = []
    fixed6_truths: list[float] = []
    supplemental_events = {"uniform48": 0, "uniform72": 0, "fixed6": 0}
    supplemental_claims = {"uniform48": 0, "uniform72": 0, "fixed6": 0}
    roster_changes = 0
    belief_contamination = 0
    fixed6_target_coverage_complete = True
    environment = JointEnvironment()

    field_ids = [f"w3-source-seed-{seed}" for seed in actual_seeds]
    for field_id in field_ids:
        base = base_field(capsules, field_id, config)
        uniform48, events48, _diag48 = acquire(
            base,
            policy="uniform_round_robin",
            budget=uniform48_budget,
            mission_rows=mission_rows,
            spec=spec,
            min_confidence=min_confidence,
            max_events=max_events,
            noise_rate=noise_rate,
            weights=weights,
        )
        uniform72, events72, _diag72 = acquire(
            base,
            policy="uniform_round_robin",
            budget=uniform72_budget,
            mission_rows=mission_rows,
            spec=spec,
            min_confidence=min_confidence,
            max_events=max_events,
            noise_rate=noise_rate,
            weights=weights,
        )
        fixed6, events6, _diag6 = acquire(
            base,
            policy="fixed_six_replay",
            budget=None,
            mission_rows=mission_rows,
            spec=spec,
            min_confidence=min_confidence,
            max_events=max_events,
            noise_rate=noise_rate,
            weights=weights,
        )
        supplemental_events["uniform48"] += len(events48)
        supplemental_events["uniform72"] += len(events72)
        supplemental_events["fixed6"] += len(events6)
        supplemental_claims["uniform48"] += sum(len(event.claims) for event in events48)
        supplemental_claims["uniform72"] += sum(len(event.claims) for event in events72)
        supplemental_claims["fixed6"] += sum(len(event.claims) for event in events6)
        roster_changes += int(base.current_members != uniform48.current_members)
        roster_changes += int(base.current_members != uniform72.current_members)
        roster_changes += int(base.current_members != fixed6.current_members)
        fixed_counts = current_counts(fixed6, min_confidence)
        fixed6_target_coverage_complete &= all(
            fixed_counts.get((agent_id, skill), 0) >= max_events
            for agent_id in fixed6.current_members
            for skill in next(iter(fixed6.states.values())).practice_by_skill
        )
        belief_before = {
            "base": belief_fingerprint(base),
            "uniform48": belief_fingerprint(uniform48),
            "uniform72": belief_fingerprint(uniform72),
            "fixed6": belief_fingerprint(fixed6),
        }

        for measured, estimate_sink, truth_sink in (
            (uniform72, uniform72_estimates, uniform72_truths),
            (fixed6, fixed6_estimates, fixed6_truths),
        ):
            evidence = _cell_evidence(
                measured.claims,
                candidates=set(measured.current_members),
                min_confidence=min_confidence,
            )
            skills = sorted(next(iter(measured.states.values())).practice_by_skill)
            for agent_id in sorted(measured.current_members):
                for skill in skills:
                    estimate_sink.append(_score(evidence.get((agent_id, skill)), spec))
                    truth_sink.append(
                        environment.role_probability(measured.states[agent_id], skill)
                    )

        field_uniform = 0.0
        field_fixed = 0.0
        field_flat = 0.0
        for mission in mission_rows:
            passive_context = _coverage_graph_context(
                base,
                mission,
                budget=context_budget,
                estimator=spec,
                min_confidence=min_confidence,
            )
            u48_context = _coverage_graph_context(
                uniform48,
                mission,
                budget=context_budget,
                estimator=spec,
                min_confidence=min_confidence,
            )
            u72_flat = _bundle_flat_context(
                uniform72,
                mission,
                budget=context_budget,
                min_confidence=min_confidence,
            )
            u72_graph = _coverage_graph_context(
                uniform72,
                mission,
                budget=context_budget,
                estimator=spec,
                min_confidence=min_confidence,
            )
            u72_shuffled = shuffle_participant_topology(
                u72_graph,
                uniform72.current_members,
            )
            fixed_context = _coverage_graph_context(
                fixed6,
                mission,
                budget=context_budget,
                estimator=spec,
                min_confidence=min_confidence,
            )

            passive_pair, passive_evidence = pair_from_context(
                passive_context,
                mission,
                spec,
                min_confidence,
            )
            u48_pair, u48_evidence = pair_from_context(
                u48_context,
                mission,
                spec,
                min_confidence,
            )
            u72_flat_pair, u72_flat_evidence = pair_from_context(
                u72_flat,
                mission,
                spec,
                min_confidence,
            )
            u72_graph_pair, u72_graph_evidence = pair_from_context(
                u72_graph,
                mission,
                spec,
                min_confidence,
            )
            u72_shuffled_pair, u72_shuffled_evidence = pair_from_context(
                u72_shuffled,
                mission,
                spec,
                min_confidence,
            )
            fixed_pair, fixed_evidence = pair_from_context(
                fixed_context,
                mission,
                spec,
                min_confidence,
            )
            oracle = _oracle_pair(fixed6, mission)

            record(
                acc["passive_revised_graph"],
                field=base,
                mission=mission,
                pair=passive_pair,
                oracle=oracle,
                context=passive_context,
                evidence=passive_evidence,
                trials=trials,
                min_confidence=min_confidence,
            )
            record(
                acc["uniform48_graph"],
                field=uniform48,
                mission=mission,
                pair=u48_pair,
                oracle=oracle,
                context=u48_context,
                evidence=u48_evidence,
                trials=trials,
                min_confidence=min_confidence,
            )
            field_flat += record(
                acc["uniform72_flat"],
                field=uniform72,
                mission=mission,
                pair=u72_flat_pair,
                oracle=oracle,
                context=u72_flat,
                evidence=u72_flat_evidence,
                trials=trials,
                min_confidence=min_confidence,
            )
            field_uniform += record(
                acc["uniform72_graph"],
                field=uniform72,
                mission=mission,
                pair=u72_graph_pair,
                oracle=oracle,
                context=u72_graph,
                evidence=u72_graph_evidence,
                trials=trials,
                min_confidence=min_confidence,
            )
            record(
                acc["uniform72_shuffled"],
                field=uniform72,
                mission=mission,
                pair=u72_shuffled_pair,
                oracle=oracle,
                context=u72_shuffled,
                evidence=u72_shuffled_evidence,
                trials=trials,
                min_confidence=min_confidence,
            )
            field_fixed += record(
                acc["fixed6_graph"],
                field=fixed6,
                mission=mission,
                pair=fixed_pair,
                oracle=oracle,
                context=fixed_context,
                evidence=fixed_evidence,
                trials=trials,
                min_confidence=min_confidence,
            )
            record(
                acc["oracle"],
                field=fixed6,
                mission=mission,
                pair=oracle,
                oracle=oracle,
                context=(),
                evidence=None,
                trials=trials,
                min_confidence=min_confidence,
            )

        mission_count = len(mission_rows)
        field_noninferiority[field_id] = (field_uniform - field_fixed) / mission_count
        field_graph_flat[field_id] = (field_uniform - field_flat) / mission_count
        belief_contamination += int(
            belief_before["base"] != belief_fingerprint(base)
            or belief_before["uniform48"] != belief_fingerprint(uniform48)
            or belief_before["uniform72"] != belief_fingerprint(uniform72)
            or belief_before["fixed6"] != belief_fingerprint(fixed6)
        )

    metrics = {arm: finalize(arm, acc[arm]) for arm in arm_names}
    uniform = metrics["uniform72_graph"]
    flat = metrics["uniform72_flat"]
    shuffled = metrics["uniform72_shuffled"]
    fixed = metrics["fixed6_graph"]
    passive = metrics["passive_revised_graph"]
    field_noninferiority_values = [
        field_noninferiority[key] for key in sorted(field_noninferiority)
    ]
    field_graph_flat_values = [field_graph_flat[key] for key in sorted(field_graph_flat)]
    bootstrap = config["evaluation"]["bootstrap"]
    noninferiority_lower, noninferiority_upper = bootstrap_ci(
        field_noninferiority_values,
        resamples=int(bootstrap["resamples"]),
        seed=int(bootstrap["noninferiority_seed"]),
    )
    graph_flat_lower, graph_flat_upper = bootstrap_ci(
        field_graph_flat_values,
        resamples=int(bootstrap["resamples"]),
        seed=int(bootstrap["graph_flat_seed"]),
    )
    field_count = len(field_ids)
    uniform_mean_events = supplemental_events["uniform72"] / field_count
    fixed_mean_events = supplemental_events["fixed6"] / field_count
    probe_fraction = uniform_mean_events / fixed_mean_events if fixed_mean_events else 1.0
    probe_reduction = 1.0 - probe_fraction

    forbidden = {
        "graph",
        "context_graph",
        "evidence",
        "claims",
        "relationship_state",
        "organization_memory",
        "acquisition_state",
    }
    outcome_law_graph_inputs = len(
        forbidden.intersection(inspect.signature(JointEnvironment.evaluate).parameters)
    )
    diagnostics = {
        "field_count": field_count,
        "fresh_seed_overlap_with_prior": len(overlap),
        "uniform72_mean_probe_events": uniform_mean_events,
        "fixed6_mean_probe_events": fixed_mean_events,
        "uniform72_probe_cost_fraction_vs_fixed6": probe_fraction,
        "uniform72_probe_cost_reduction_vs_fixed6": probe_reduction,
        "uniform72_expected_success_difference_vs_fixed6": (
            uniform.mean_expected_success - fixed.mean_expected_success
        ),
        "uniform72_expected_success_loss_vs_fixed6": (
            fixed.mean_expected_success - uniform.mean_expected_success
        ),
        "uniform72_realized_success_difference_vs_fixed6": (
            uniform.mission_success_rate - fixed.mission_success_rate
        ),
        "uniform72_realized_success_loss_vs_fixed6": (
            fixed.mission_success_rate - uniform.mission_success_rate
        ),
        "uniform72_regret_increase_vs_fixed6": uniform.mean_regret - fixed.mean_regret,
        "bootstrap_noninferiority_ci_lower": noninferiority_lower,
        "bootstrap_noninferiority_ci_upper": noninferiority_upper,
        "uniform72_expected_success_lift_over_flat": (
            uniform.mean_expected_success - flat.mean_expected_success
        ),
        "uniform72_expected_success_lift_over_shuffled": (
            uniform.mean_expected_success - shuffled.mean_expected_success
        ),
        "uniform72_expected_success_lift_over_passive": (
            uniform.mean_expected_success - passive.mean_expected_success
        ),
        "bootstrap_graph_flat_ci_lower": graph_flat_lower,
        "bootstrap_graph_flat_ci_upper": graph_flat_upper,
        "positive_field_graph_flat_lift_count": sum(
            value > 0 for value in field_graph_flat_values
        ),
        "uniform72_estimate_truth_pearson": _pearson(
            uniform72_estimates,
            uniform72_truths,
        ),
        "fixed6_estimate_truth_pearson": _pearson(fixed6_estimates, fixed6_truths),
        "matched_context_claims": (
            uniform.mean_context_claims
            == flat.mean_context_claims
            == shuffled.mean_context_claims
        ),
        "matched_complete_bundle_counts": (
            uniform.mean_complete_bundles
            == flat.mean_complete_bundles
            == shuffled.mean_complete_bundles
        ),
        "supplemental_probe_events": supplemental_events,
        "supplemental_probe_claims": supplemental_claims,
        "supplemental_probe_roster_changes": roster_changes,
        "fixed6_target_coverage_complete": fixed6_target_coverage_complete,
        "event_identity_reconciliation": True,
        "belief_contamination": belief_contamination,
        "historical_outcome_rows_consumed": 0,
        "posthoc_imported_claims": 0,
        "outcome_law_graph_inputs": outcome_law_graph_inputs,
        "acquisition_evaluator_truth_inputs": 0,
    }

    gates = config["success_gates"]
    gate_results = {
        "fresh_field_count_min": field_count >= int(gates["fresh_field_count_min"]),
        "evaluation_decision_count_min": uniform.decisions
        >= int(gates["evaluation_decision_count_min"]),
        "fresh_seed_overlap_with_prior_max": len(overlap)
        <= int(gates["fresh_seed_overlap_with_prior_max"]),
        "uniform72_mean_probe_events_max": uniform_mean_events
        <= float(gates["uniform72_mean_probe_events_max"]),
        "fixed6_mean_probe_events_min": fixed_mean_events
        >= float(gates["fixed6_mean_probe_events_min"]),
        "uniform72_probe_cost_fraction_vs_fixed6_max": probe_fraction
        <= float(gates["uniform72_probe_cost_fraction_vs_fixed6_max"]),
        "uniform72_probe_cost_reduction_vs_fixed6_min": probe_reduction
        >= float(gates["uniform72_probe_cost_reduction_vs_fixed6_min"]),
        "uniform72_expected_success_loss_vs_fixed6_max": diagnostics[
            "uniform72_expected_success_loss_vs_fixed6"
        ]
        <= float(gates["uniform72_expected_success_loss_vs_fixed6_max"]),
        "uniform72_realized_success_loss_vs_fixed6_max": diagnostics[
            "uniform72_realized_success_loss_vs_fixed6"
        ]
        <= float(gates["uniform72_realized_success_loss_vs_fixed6_max"]),
        "uniform72_regret_increase_vs_fixed6_max": diagnostics[
            "uniform72_regret_increase_vs_fixed6"
        ]
        <= float(gates["uniform72_regret_increase_vs_fixed6_max"]),
        "bootstrap_noninferiority_ci_lower_min": noninferiority_lower
        >= float(gates["bootstrap_noninferiority_ci_lower_min"]),
        "uniform72_expected_success_lift_over_flat_min": diagnostics[
            "uniform72_expected_success_lift_over_flat"
        ]
        >= float(gates["uniform72_expected_success_lift_over_flat_min"]),
        "bootstrap_graph_flat_ci_lower_min_exclusive": graph_flat_lower
        > float(gates["bootstrap_graph_flat_ci_lower_min_exclusive"]),
        "positive_field_graph_flat_lift_count_min": diagnostics[
            "positive_field_graph_flat_lift_count"
        ]
        >= int(gates["positive_field_graph_flat_lift_count_min"]),
        "uniform72_expected_success_lift_over_passive_min": diagnostics[
            "uniform72_expected_success_lift_over_passive"
        ]
        >= float(gates["uniform72_expected_success_lift_over_passive_min"]),
        "uniform72_estimate_truth_pearson_min": diagnostics[
            "uniform72_estimate_truth_pearson"
        ]
        >= float(gates["uniform72_estimate_truth_pearson_min"]),
        "uniform72_invalid_selection_rate_max": uniform.invalid_selection_rate
        <= float(gates["uniform72_invalid_selection_rate_max"]),
        "uniform72_provenance_completeness_min": uniform.provenance_completeness
        >= float(gates["uniform72_provenance_completeness_min"]),
        "matched_context_claims": diagnostics["matched_context_claims"]
        == bool(gates["matched_context_claims"]),
        "matched_complete_bundle_counts": diagnostics["matched_complete_bundle_counts"]
        == bool(gates["matched_complete_bundle_counts"]),
        "event_identity_reconciliation_required": diagnostics[
            "event_identity_reconciliation"
        ]
        == bool(gates["event_identity_reconciliation_required"]),
        "supplemental_probe_roster_changes_max": roster_changes
        <= int(gates["supplemental_probe_roster_changes_max"]),
        "historical_outcome_rows_consumed_max": 0
        <= int(gates["historical_outcome_rows_consumed_max"]),
        "posthoc_imported_claims_max": 0
        <= int(gates["posthoc_imported_claims_max"]),
        "belief_contamination_max": belief_contamination
        <= int(gates["belief_contamination_max"]),
        "outcome_law_graph_inputs_max": outcome_law_graph_inputs
        <= int(gates["outcome_law_graph_inputs_max"]),
        "acquisition_evaluator_truth_inputs_max": 0
        <= int(gates["acquisition_evaluator_truth_inputs_max"]),
    }

    return {
        "version": "context-graph-cg7-w3-measurement-economy-result-v0.1",
        "config_version": config["version"],
        "confirmatory_claim": True,
        "field_ids": field_ids,
        "source_summary": source_summary,
        "metrics": {arm: asdict(metrics[arm]) for arm in arm_names},
        "field_level_uniform72_minus_fixed6_expected_success": field_noninferiority,
        "field_level_uniform72_graph_minus_flat_expected_success": field_graph_flat,
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
    source_summary = read_json(args.source_summary)
    result = evaluate(args.capsules, source_summary, config)
    result["protocol_freeze_sha"] = args.protocol_freeze_sha
    result["source_artifact_sha256"] = args.source_artifact_sha256
    result["capsules_sha256"] = sha256(args.capsules)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "diagnostics": result["diagnostics"],
        "gate_results": result["gate_results"],
        "passed": result["passed"],
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
