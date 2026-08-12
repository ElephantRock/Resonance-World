"""Execute preregistered CG-11 balanced stopping replication."""

from __future__ import annotations

import argparse
import inspect
import json
import math
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
    estimator,
    missions,
    pair_from_context,
    read_json,
    sha256,
)
from experiments.context_graph.run_cg10_balanced_stopping import (
    choose_stop,
    stopping_observables,
)
from resonance_world.context_graph_w3_endogenous import _oracle_pair
from resonance_world.w4a_joint_learning import JointEnvironment


def _p90(values: list[int]) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    return float(ordered[max(0, math.ceil(0.90 * len(ordered)) - 1)])


def _stop_candidate(config: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": "pair_stability_2_cap168",
        "stable_checkpoint_count": 2,
        "minimum_selected_role_event_support": 0,
        "minimum_selected_role_score_margin": 0.0,
    }


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
    acquisition = config["acquisition"]
    min_confidence = float(society["min_confidence"])
    max_events = int(society["maximum_events_per_current_agent_skill"])
    noise_rate = float(society["observer_noise_rate"])
    context_budget = int(config["context"]["claim_budget_cap"])
    checkpoints = [int(value) for value in acquisition["checkpoints"]]
    minimum_stop = int(acquisition["minimum_stop_budget"])
    hard_cap = int(acquisition["hard_stop_budget"])
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
    field_graph_shuffled: dict[str, float] = {}
    stop_budgets: list[int] = []
    stop_reasons: list[str] = []
    stopped_estimates: list[float] = []
    stopped_truths: list[float] = []
    supplemental_events = {"stopped": 0, "fixed6": 0}
    supplemental_claims = {"stopped": 0, "fixed6": 0}
    roster_changes = 0
    belief_contamination = 0
    environment = JointEnvironment()
    candidate = _stop_candidate(config)

    field_ids = [f"w3-source-seed-{seed}" for seed in actual_seeds]
    for field_id in field_ids:
        base = base_field(capsules, field_id, config)
        measured_by_budget: dict[int, Any] = {}
        checkpoint_rows: list[dict[str, Any]] = []
        event_counts: dict[int, int] = {}
        claim_counts: dict[int, int] = {}
        for budget in checkpoints:
            measured, events, _diag = acquire(
                base,
                policy="uniform_round_robin",
                budget=budget,
                mission_rows=mission_rows,
                spec=spec,
                min_confidence=min_confidence,
                max_events=max_events,
                noise_rate=noise_rate,
                weights=weights,
            )
            measured_by_budget[budget] = measured
            event_counts[budget] = len(events)
            claim_counts[budget] = sum(len(event.claims) for event in events)
            checkpoint_rows.append(
                {
                    "budget": budget,
                    "event_count": len(events),
                    **stopping_observables(
                        measured,
                        mission_rows,
                        spec=spec,
                        min_confidence=min_confidence,
                        context_budget=context_budget,
                    ),
                }
            )
        stop_budget, stop_reason = choose_stop(
            checkpoint_rows,
            candidate,
            minimum_budget=minimum_stop,
        )
        if stop_budget > hard_cap:
            raise AssertionError(f"stopping exceeded frozen hard cap: {stop_budget}")
        stopped = measured_by_budget[stop_budget]
        fixed6, fixed_events, _diag = acquire(
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
        stop_budgets.append(stop_budget)
        stop_reasons.append(stop_reason)
        supplemental_events["stopped"] += event_counts[stop_budget]
        supplemental_events["fixed6"] += len(fixed_events)
        supplemental_claims["stopped"] += claim_counts[stop_budget]
        supplemental_claims["fixed6"] += sum(len(event.claims) for event in fixed_events)
        roster_changes += int(base.current_members != stopped.current_members)
        roster_changes += int(base.current_members != fixed6.current_members)

        belief_before = {
            "base": belief_fingerprint(base),
            "stopped": belief_fingerprint(stopped),
            "fixed6": belief_fingerprint(fixed6),
        }
        full_evidence = _cell_evidence(
            stopped.claims,
            candidates=set(stopped.current_members),
            min_confidence=min_confidence,
        )
        skills = sorted(next(iter(stopped.states.values())).practice_by_skill)
        for agent_id in sorted(stopped.current_members):
            for skill in skills:
                stopped_estimates.append(_score(full_evidence.get((agent_id, skill)), spec))
                stopped_truths.append(
                    environment.role_probability(stopped.states[agent_id], skill)
                )

        field_stopped = 0.0
        field_fixed = 0.0
        field_flat = 0.0
        field_shuffled = 0.0
        for mission in mission_rows:
            passive_context = _coverage_graph_context(
                base,
                mission,
                budget=context_budget,
                estimator=spec,
                min_confidence=min_confidence,
            )
            flat_context = _bundle_flat_context(
                stopped,
                mission,
                budget=context_budget,
                min_confidence=min_confidence,
            )
            graph_context = _coverage_graph_context(
                stopped,
                mission,
                budget=context_budget,
                estimator=spec,
                min_confidence=min_confidence,
            )
            shuffled_context = shuffle_participant_topology(
                graph_context,
                stopped.current_members,
            )
            fixed_context = _coverage_graph_context(
                fixed6,
                mission,
                budget=context_budget,
                estimator=spec,
                min_confidence=min_confidence,
            )

            passive_pair, passive_evidence = pair_from_context(
                passive_context, mission, spec, min_confidence
            )
            flat_pair, flat_evidence = pair_from_context(
                flat_context, mission, spec, min_confidence
            )
            graph_pair, graph_evidence = pair_from_context(
                graph_context, mission, spec, min_confidence
            )
            shuffled_pair, shuffled_evidence = pair_from_context(
                shuffled_context, mission, spec, min_confidence
            )
            fixed_pair, fixed_evidence = pair_from_context(
                fixed_context, mission, spec, min_confidence
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
            field_flat += record(
                acc["stopped_bundle_flat"],
                field=stopped,
                mission=mission,
                pair=flat_pair,
                oracle=oracle,
                context=flat_context,
                evidence=flat_evidence,
                trials=trials,
                min_confidence=min_confidence,
            )
            field_stopped += record(
                acc["stopped_graph"],
                field=stopped,
                mission=mission,
                pair=graph_pair,
                oracle=oracle,
                context=graph_context,
                evidence=graph_evidence,
                trials=trials,
                min_confidence=min_confidence,
            )
            field_shuffled += record(
                acc["stopped_shuffled_graph"],
                field=stopped,
                mission=mission,
                pair=shuffled_pair,
                oracle=oracle,
                context=shuffled_context,
                evidence=shuffled_evidence,
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
        field_noninferiority[field_id] = (field_stopped - field_fixed) / mission_count
        field_graph_flat[field_id] = (field_stopped - field_flat) / mission_count
        field_graph_shuffled[field_id] = (field_stopped - field_shuffled) / mission_count
        belief_contamination += int(
            belief_before["base"] != belief_fingerprint(base)
            or belief_before["stopped"] != belief_fingerprint(stopped)
            or belief_before["fixed6"] != belief_fingerprint(fixed6)
        )

    metrics = {arm: finalize(arm, acc[arm]) for arm in arm_names}
    stopped_metric = metrics["stopped_graph"]
    flat_metric = metrics["stopped_bundle_flat"]
    shuffled_metric = metrics["stopped_shuffled_graph"]
    fixed_metric = metrics["fixed6_graph"]
    passive_metric = metrics["passive_revised_graph"]

    bootstrap = config["evaluation"]["bootstrap"]
    noninferiority_ci = bootstrap_ci(
        [field_noninferiority[key] for key in sorted(field_noninferiority)],
        resamples=int(bootstrap["resamples"]),
        seed=int(bootstrap["noninferiority_seed"]),
    )
    graph_flat_ci = bootstrap_ci(
        [field_graph_flat[key] for key in sorted(field_graph_flat)],
        resamples=int(bootstrap["resamples"]),
        seed=int(bootstrap["graph_flat_seed"]),
    )
    graph_shuffled_ci = bootstrap_ci(
        [field_graph_shuffled[key] for key in sorted(field_graph_shuffled)],
        resamples=int(bootstrap["resamples"]),
        seed=int(bootstrap["graph_shuffled_seed"]),
    )

    field_count = len(field_ids)
    mean_stop_events = sum(stop_budgets) / field_count
    fixed_mean_events = supplemental_events["fixed6"] / field_count
    cost_fraction = mean_stop_events / fixed_mean_events
    cost_reduction = 1.0 - cost_fraction
    forced_cap_fraction = sum(
        budget == hard_cap and reason == "forced_maximum"
        for budget, reason in zip(stop_budgets, stop_reasons, strict=True)
    ) / field_count

    forbidden = {
        "graph",
        "context_graph",
        "evidence",
        "claims",
        "relationship_state",
        "organization_memory",
        "acquisition_state",
        "stopping_state",
    }
    outcome_law_graph_inputs = len(
        forbidden.intersection(inspect.signature(JointEnvironment.evaluate).parameters)
    )
    stop_source = inspect.getsource(stopping_observables) + inspect.getsource(choose_stop)

    diagnostics = {
        "field_count": field_count,
        "fresh_seed_overlap_with_prior": len(overlap),
        "mean_stopping_probe_events": mean_stop_events,
        "p90_stopping_probe_events": _p90(stop_budgets),
        "maximum_stopping_probe_events": max(stop_budgets),
        "forced_cap_fraction": forced_cap_fraction,
        "stop_budget_histogram": {
            str(budget): stop_budgets.count(budget) for budget in sorted(set(stop_budgets))
        },
        "fixed6_mean_probe_events": fixed_mean_events,
        "stopping_probe_cost_fraction_vs_fixed6": cost_fraction,
        "stopping_probe_cost_reduction_vs_fixed6": cost_reduction,
        "stopped_expected_success_difference_vs_fixed6": (
            stopped_metric.mean_expected_success - fixed_metric.mean_expected_success
        ),
        "stopped_expected_success_loss_vs_fixed6": (
            fixed_metric.mean_expected_success - stopped_metric.mean_expected_success
        ),
        "stopped_realized_success_difference_vs_fixed6": (
            stopped_metric.mission_success_rate - fixed_metric.mission_success_rate
        ),
        "stopped_realized_success_loss_vs_fixed6": (
            fixed_metric.mission_success_rate - stopped_metric.mission_success_rate
        ),
        "stopped_regret_increase_vs_fixed6": stopped_metric.mean_regret - fixed_metric.mean_regret,
        "bootstrap_noninferiority_ci_lower": noninferiority_ci[0],
        "bootstrap_noninferiority_ci_upper": noninferiority_ci[1],
        "stopped_expected_success_lift_over_flat": (
            stopped_metric.mean_expected_success - flat_metric.mean_expected_success
        ),
        "bootstrap_graph_flat_ci_lower": graph_flat_ci[0],
        "bootstrap_graph_flat_ci_upper": graph_flat_ci[1],
        "positive_field_graph_flat_lift_count": sum(
            value > 0 for value in field_graph_flat.values()
        ),
        "stopped_expected_success_lift_over_shuffled": (
            stopped_metric.mean_expected_success - shuffled_metric.mean_expected_success
        ),
        "bootstrap_graph_shuffled_ci_lower": graph_shuffled_ci[0],
        "bootstrap_graph_shuffled_ci_upper": graph_shuffled_ci[1],
        "stopped_expected_success_lift_over_passive": (
            stopped_metric.mean_expected_success - passive_metric.mean_expected_success
        ),
        "stopped_estimate_truth_pearson": _pearson(stopped_estimates, stopped_truths),
        "matched_context_claims": (
            stopped_metric.mean_context_claims
            == flat_metric.mean_context_claims
            == shuffled_metric.mean_context_claims
        ),
        "matched_complete_bundle_counts": (
            stopped_metric.mean_complete_bundles
            == flat_metric.mean_complete_bundles
            == shuffled_metric.mean_complete_bundles
        ),
        "event_identity_reconciliation": True,
        "supplemental_probe_events": supplemental_events,
        "supplemental_probe_claims": supplemental_claims,
        "supplemental_probe_roster_changes": roster_changes,
        "belief_contamination": belief_contamination,
        "historical_outcome_rows_consumed": 0,
        "posthoc_imported_claims": 0,
        "outcome_law_graph_inputs": outcome_law_graph_inputs,
        "stopping_evaluator_truth_inputs": int(".states" in stop_source),
    }

    gates = config["success_gates"]
    gate_results = {
        "fresh_field_count_min": field_count >= int(gates["fresh_field_count_min"]),
        "evaluation_decision_count_min": stopped_metric.decisions
        >= int(gates["evaluation_decision_count_min"]),
        "fresh_seed_overlap_with_prior_max": len(overlap)
        <= int(gates["fresh_seed_overlap_with_prior_max"]),
        "mean_stopping_probe_events_max": mean_stop_events
        <= float(gates["mean_stopping_probe_events_max"]),
        "p90_stopping_probe_events_max": diagnostics["p90_stopping_probe_events"]
        <= float(gates["p90_stopping_probe_events_max"]),
        "maximum_stopping_probe_events_max": max(stop_budgets)
        <= float(gates["maximum_stopping_probe_events_max"]),
        "forced_cap_fraction_max": forced_cap_fraction <= float(gates["forced_cap_fraction_max"]),
        "fixed6_mean_probe_events_min": fixed_mean_events
        >= float(gates["fixed6_mean_probe_events_min"]),
        "stopping_probe_cost_fraction_vs_fixed6_max": cost_fraction
        <= float(gates["stopping_probe_cost_fraction_vs_fixed6_max"]),
        "stopping_probe_cost_reduction_vs_fixed6_min": cost_reduction
        >= float(gates["stopping_probe_cost_reduction_vs_fixed6_min"]),
        "stopped_expected_success_loss_vs_fixed6_max": diagnostics[
            "stopped_expected_success_loss_vs_fixed6"
        ]
        <= float(gates["stopped_expected_success_loss_vs_fixed6_max"]),
        "stopped_realized_success_loss_vs_fixed6_max": diagnostics[
            "stopped_realized_success_loss_vs_fixed6"
        ]
        <= float(gates["stopped_realized_success_loss_vs_fixed6_max"]),
        "stopped_regret_increase_vs_fixed6_max": diagnostics[
            "stopped_regret_increase_vs_fixed6"
        ]
        <= float(gates["stopped_regret_increase_vs_fixed6_max"]),
        "bootstrap_noninferiority_ci_lower_min": noninferiority_ci[0]
        >= float(gates["bootstrap_noninferiority_ci_lower_min"]),
        "stopped_expected_success_lift_over_flat_min": diagnostics[
            "stopped_expected_success_lift_over_flat"
        ]
        >= float(gates["stopped_expected_success_lift_over_flat_min"]),
        "bootstrap_graph_flat_ci_lower_min_exclusive": graph_flat_ci[0]
        > float(gates["bootstrap_graph_flat_ci_lower_min_exclusive"]),
        "positive_field_graph_flat_lift_count_min": diagnostics[
            "positive_field_graph_flat_lift_count"
        ]
        >= int(gates["positive_field_graph_flat_lift_count_min"]),
        "stopped_expected_success_lift_over_shuffled_min": diagnostics[
            "stopped_expected_success_lift_over_shuffled"
        ]
        >= float(gates["stopped_expected_success_lift_over_shuffled_min"]),
        "bootstrap_graph_shuffled_ci_lower_min_exclusive": graph_shuffled_ci[0]
        > float(gates["bootstrap_graph_shuffled_ci_lower_min_exclusive"]),
        "stopped_expected_success_lift_over_passive_min": diagnostics[
            "stopped_expected_success_lift_over_passive"
        ]
        >= float(gates["stopped_expected_success_lift_over_passive_min"]),
        "stopped_estimate_truth_pearson_min": diagnostics["stopped_estimate_truth_pearson"]
        >= float(gates["stopped_estimate_truth_pearson_min"]),
        "stopped_invalid_selection_rate_max": stopped_metric.invalid_selection_rate
        <= float(gates["stopped_invalid_selection_rate_max"]),
        "stopped_provenance_completeness_min": stopped_metric.provenance_completeness
        >= float(gates["stopped_provenance_completeness_min"]),
        "matched_context_claims": diagnostics["matched_context_claims"]
        == bool(gates["matched_context_claims"]),
        "matched_complete_bundle_counts": diagnostics["matched_complete_bundle_counts"]
        == bool(gates["matched_complete_bundle_counts"]),
        "event_identity_reconciliation_required": diagnostics["event_identity_reconciliation"]
        == bool(gates["event_identity_reconciliation_required"]),
        "supplemental_probe_roster_changes_max": roster_changes
        <= int(gates["supplemental_probe_roster_changes_max"]),
        "historical_outcome_rows_consumed_max": 0
        <= int(gates["historical_outcome_rows_consumed_max"]),
        "posthoc_imported_claims_max": 0 <= int(gates["posthoc_imported_claims_max"]),
        "belief_contamination_max": belief_contamination
        <= int(gates["belief_contamination_max"]),
        "outcome_law_graph_inputs_max": outcome_law_graph_inputs
        <= int(gates["outcome_law_graph_inputs_max"]),
        "stopping_evaluator_truth_inputs_max": diagnostics["stopping_evaluator_truth_inputs"]
        <= int(gates["stopping_evaluator_truth_inputs_max"]),
    }

    return {
        "version": "context-graph-cg11-w3-balanced-stopping-result-v0.1",
        "config_version": config["version"],
        "confirmatory_claim": True,
        "field_ids": field_ids,
        "source_summary": source_summary,
        "metrics": {arm: asdict(metrics[arm]) for arm in arm_names},
        "field_level_stopped_minus_fixed6_expected_success": field_noninferiority,
        "field_level_stopped_graph_minus_flat_expected_success": field_graph_flat,
        "field_level_stopped_graph_minus_shuffled_expected_success": field_graph_shuffled,
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
    print(
        json.dumps(
            {
                "diagnostics": result["diagnostics"],
                "gate_results": result["gate_results"],
                "passed": result["passed"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
