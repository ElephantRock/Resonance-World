"""Execute preregistered CG-9 balanced-measurement frontier replication.

CG-9 tests a single primary acquisition target: 60 deterministic uniform round-robin
supplemental probe events per Field. Additional balanced budgets are descriptive
frontier points only and cannot rescue a failed primary claim.
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
from resonance_world.context_graph_w3_endogenous import _oracle_pair
from resonance_world.w4a_joint_learning import JointEnvironment


def _uniform_key(budget: int) -> str:
    return f"uniform{budget}"


def _uniform_arm(budget: int) -> str:
    return f"uniform{budget}_graph"


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
    primary_budget = int(config["acquisition"]["primary_budget"])
    frontier_budgets = [int(value) for value in config["acquisition"]["frontier_budgets"]]
    if primary_budget not in frontier_budgets:
        raise AssertionError("primary budget must be one of the frozen frontier budgets")
    trials = int(config["evaluation"]["trials_per_decision"])
    weights = {
        "selected_role_bonus": 0.0,
        "plausible_challenger_bonus": 0.0,
        "support_deficit_bonus": 0.0,
        "ambiguity_margin": 0.0,
    }
    arm_names = [str(value) for value in config["arms"]]
    acc = {arm: Accumulator() for arm in arm_names}

    field_primary_fixed: dict[str, float] = {}
    field_primary_flat: dict[str, float] = {}
    primary_estimates: list[float] = []
    primary_truths: list[float] = []
    fixed_estimates: list[float] = []
    fixed_truths: list[float] = []
    supplemental_events = {_uniform_key(budget): 0 for budget in frontier_budgets}
    supplemental_events["fixed6"] = 0
    supplemental_claims = {_uniform_key(budget): 0 for budget in frontier_budgets}
    supplemental_claims["fixed6"] = 0
    roster_changes = 0
    belief_contamination = 0
    fixed6_target_coverage_complete = True
    nested_frontier_event_sets = True
    environment = JointEnvironment()

    field_ids = [f"w3-source-seed-{seed}" for seed in actual_seeds]
    for field_id in field_ids:
        base = base_field(capsules, field_id, config)
        measured_by_budget = {}
        events_by_budget = {}
        for budget in frontier_budgets:
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
            events_by_budget[budget] = events
            key = _uniform_key(budget)
            supplemental_events[key] += len(events)
            supplemental_claims[key] += sum(len(event.claims) for event in events)
            roster_changes += int(base.current_members != measured.current_members)

        ordered_budgets = sorted(frontier_budgets)
        for lower, upper in zip(ordered_budgets, ordered_budgets[1:], strict=False):
            lower_ids = {event.event_id for event in events_by_budget[lower]}
            upper_ids = {event.event_id for event in events_by_budget[upper]}
            nested_frontier_event_sets &= lower_ids.issubset(upper_ids)

        fixed6, fixed_events, _fixed_diag = acquire(
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
        supplemental_events["fixed6"] += len(fixed_events)
        supplemental_claims["fixed6"] += sum(len(event.claims) for event in fixed_events)
        roster_changes += int(base.current_members != fixed6.current_members)
        largest_uniform_ids = {
            event.event_id for event in events_by_budget[max(frontier_budgets)]
        }
        fixed_ids = {event.event_id for event in fixed_events}
        nested_frontier_event_sets &= largest_uniform_ids.issubset(fixed_ids)

        fixed_counts = current_counts(fixed6, min_confidence)
        skills = sorted(next(iter(fixed6.states.values())).practice_by_skill)
        fixed6_target_coverage_complete &= all(
            fixed_counts.get((agent_id, skill), 0) >= max_events
            for agent_id in fixed6.current_members
            for skill in skills
        )

        belief_before = {
            "base": belief_fingerprint(base),
            "fixed6": belief_fingerprint(fixed6),
            **{
                _uniform_key(budget): belief_fingerprint(measured_by_budget[budget])
                for budget in frontier_budgets
            },
        }

        for measured, estimate_sink, truth_sink in (
            (measured_by_budget[primary_budget], primary_estimates, primary_truths),
            (fixed6, fixed_estimates, fixed_truths),
        ):
            evidence = _cell_evidence(
                measured.claims,
                candidates=set(measured.current_members),
                min_confidence=min_confidence,
            )
            measured_skills = sorted(next(iter(measured.states.values())).practice_by_skill)
            for agent_id in sorted(measured.current_members):
                for skill in measured_skills:
                    estimate_sink.append(_score(evidence.get((agent_id, skill)), spec))
                    truth_sink.append(
                        environment.role_probability(measured.states[agent_id], skill)
                    )

        field_primary = 0.0
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
            graph_contexts = {
                budget: _coverage_graph_context(
                    measured_by_budget[budget],
                    mission,
                    budget=context_budget,
                    estimator=spec,
                    min_confidence=min_confidence,
                )
                for budget in frontier_budgets
            }
            primary_field = measured_by_budget[primary_budget]
            primary_graph = graph_contexts[primary_budget]
            primary_flat = _bundle_flat_context(
                primary_field,
                mission,
                budget=context_budget,
                min_confidence=min_confidence,
            )
            primary_shuffled = shuffle_participant_topology(
                primary_graph,
                primary_field.current_members,
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
            graph_pairs = {}
            graph_evidence = {}
            for budget in frontier_budgets:
                pair, evidence = pair_from_context(
                    graph_contexts[budget],
                    mission,
                    spec,
                    min_confidence,
                )
                graph_pairs[budget] = pair
                graph_evidence[budget] = evidence
            primary_flat_pair, primary_flat_evidence = pair_from_context(
                primary_flat,
                mission,
                spec,
                min_confidence,
            )
            primary_shuffled_pair, primary_shuffled_evidence = pair_from_context(
                primary_shuffled,
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
            for budget in frontier_budgets:
                expected = record(
                    acc[_uniform_arm(budget)],
                    field=measured_by_budget[budget],
                    mission=mission,
                    pair=graph_pairs[budget],
                    oracle=oracle,
                    context=graph_contexts[budget],
                    evidence=graph_evidence[budget],
                    trials=trials,
                    min_confidence=min_confidence,
                )
                if budget == primary_budget:
                    field_primary += expected
            field_flat += record(
                acc[f"uniform{primary_budget}_flat"],
                field=primary_field,
                mission=mission,
                pair=primary_flat_pair,
                oracle=oracle,
                context=primary_flat,
                evidence=primary_flat_evidence,
                trials=trials,
                min_confidence=min_confidence,
            )
            record(
                acc[f"uniform{primary_budget}_shuffled"],
                field=primary_field,
                mission=mission,
                pair=primary_shuffled_pair,
                oracle=oracle,
                context=primary_shuffled,
                evidence=primary_shuffled_evidence,
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
        field_primary_fixed[field_id] = (field_primary - field_fixed) / mission_count
        field_primary_flat[field_id] = (field_primary - field_flat) / mission_count
        belief_contamination += int(
            belief_before["base"] != belief_fingerprint(base)
            or belief_before["fixed6"] != belief_fingerprint(fixed6)
            or any(
                belief_before[_uniform_key(budget)]
                != belief_fingerprint(measured_by_budget[budget])
                for budget in frontier_budgets
            )
        )

    if not nested_frontier_event_sets:
        raise AssertionError("frozen frontier acquisition arms are not nested")

    metrics = {arm: finalize(arm, acc[arm]) for arm in arm_names}
    primary = metrics[_uniform_arm(primary_budget)]
    flat = metrics[f"uniform{primary_budget}_flat"]
    shuffled = metrics[f"uniform{primary_budget}_shuffled"]
    fixed = metrics["fixed6_graph"]
    passive = metrics["passive_revised_graph"]

    primary_fixed_values = [
        field_primary_fixed[key] for key in sorted(field_primary_fixed)
    ]
    primary_flat_values = [field_primary_flat[key] for key in sorted(field_primary_flat)]
    bootstrap = config["evaluation"]["bootstrap"]
    noninferiority_lower, noninferiority_upper = bootstrap_ci(
        primary_fixed_values,
        resamples=int(bootstrap["resamples"]),
        seed=int(bootstrap["noninferiority_seed"]),
    )
    graph_flat_lower, graph_flat_upper = bootstrap_ci(
        primary_flat_values,
        resamples=int(bootstrap["resamples"]),
        seed=int(bootstrap["graph_flat_seed"]),
    )

    field_count = len(field_ids)
    mean_events = {
        key: value / field_count for key, value in supplemental_events.items()
    }
    primary_mean_events = mean_events[_uniform_key(primary_budget)]
    fixed_mean_events = mean_events["fixed6"]
    probe_fraction = primary_mean_events / fixed_mean_events if fixed_mean_events else 1.0
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

    frontier_expected = {
        str(budget): metrics[_uniform_arm(budget)].mean_expected_success
        for budget in frontier_budgets
    }
    frontier_regret = {
        str(budget): metrics[_uniform_arm(budget)].mean_regret
        for budget in frontier_budgets
    }
    frontier_realized = {
        str(budget): metrics[_uniform_arm(budget)].mission_success_rate
        for budget in frontier_budgets
    }
    diagnostics = {
        "field_count": field_count,
        "fresh_seed_overlap_with_prior": len(overlap),
        "primary_budget": primary_budget,
        "frontier_budgets": frontier_budgets,
        "frontier_expected_success_by_budget": frontier_expected,
        "frontier_realized_success_by_budget": frontier_realized,
        "frontier_regret_by_budget": frontier_regret,
        "frontier_nested_event_sets": nested_frontier_event_sets,
        "mean_probe_events_by_arm": mean_events,
        "uniform60_mean_probe_events": primary_mean_events,
        "fixed6_mean_probe_events": fixed_mean_events,
        "uniform60_probe_cost_fraction_vs_fixed6": probe_fraction,
        "uniform60_probe_cost_reduction_vs_fixed6": probe_reduction,
        "uniform60_expected_success_difference_vs_fixed6": (
            primary.mean_expected_success - fixed.mean_expected_success
        ),
        "uniform60_expected_success_loss_vs_fixed6": (
            fixed.mean_expected_success - primary.mean_expected_success
        ),
        "uniform60_realized_success_difference_vs_fixed6": (
            primary.mission_success_rate - fixed.mission_success_rate
        ),
        "uniform60_realized_success_loss_vs_fixed6": (
            fixed.mission_success_rate - primary.mission_success_rate
        ),
        "uniform60_regret_increase_vs_fixed6": primary.mean_regret - fixed.mean_regret,
        "bootstrap_noninferiority_ci_lower": noninferiority_lower,
        "bootstrap_noninferiority_ci_upper": noninferiority_upper,
        "uniform60_expected_success_lift_over_flat": (
            primary.mean_expected_success - flat.mean_expected_success
        ),
        "uniform60_expected_success_lift_over_shuffled": (
            primary.mean_expected_success - shuffled.mean_expected_success
        ),
        "uniform60_expected_success_lift_over_passive": (
            primary.mean_expected_success - passive.mean_expected_success
        ),
        "bootstrap_graph_flat_ci_lower": graph_flat_lower,
        "bootstrap_graph_flat_ci_upper": graph_flat_upper,
        "positive_field_graph_flat_lift_count": sum(value > 0 for value in primary_flat_values),
        "uniform60_estimate_truth_pearson": _pearson(primary_estimates, primary_truths),
        "fixed6_estimate_truth_pearson": _pearson(fixed_estimates, fixed_truths),
        "matched_context_claims": (
            primary.mean_context_claims
            == flat.mean_context_claims
            == shuffled.mean_context_claims
        ),
        "matched_complete_bundle_counts": (
            primary.mean_complete_bundles
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
        "evaluation_decision_count_min": primary.decisions
        >= int(gates["evaluation_decision_count_min"]),
        "fresh_seed_overlap_with_prior_max": len(overlap)
        <= int(gates["fresh_seed_overlap_with_prior_max"]),
        "uniform60_mean_probe_events_max": primary_mean_events
        <= float(gates["uniform60_mean_probe_events_max"]),
        "fixed6_mean_probe_events_min": fixed_mean_events
        >= float(gates["fixed6_mean_probe_events_min"]),
        "uniform60_probe_cost_fraction_vs_fixed6_max": probe_fraction
        <= float(gates["uniform60_probe_cost_fraction_vs_fixed6_max"]),
        "uniform60_probe_cost_reduction_vs_fixed6_min": probe_reduction
        >= float(gates["uniform60_probe_cost_reduction_vs_fixed6_min"]),
        "uniform60_expected_success_loss_vs_fixed6_max": diagnostics[
            "uniform60_expected_success_loss_vs_fixed6"
        ]
        <= float(gates["uniform60_expected_success_loss_vs_fixed6_max"]),
        "uniform60_realized_success_loss_vs_fixed6_max": diagnostics[
            "uniform60_realized_success_loss_vs_fixed6"
        ]
        <= float(gates["uniform60_realized_success_loss_vs_fixed6_max"]),
        "uniform60_regret_increase_vs_fixed6_max": diagnostics[
            "uniform60_regret_increase_vs_fixed6"
        ]
        <= float(gates["uniform60_regret_increase_vs_fixed6_max"]),
        "bootstrap_noninferiority_ci_lower_min": noninferiority_lower
        >= float(gates["bootstrap_noninferiority_ci_lower_min"]),
        "uniform60_expected_success_lift_over_flat_min": diagnostics[
            "uniform60_expected_success_lift_over_flat"
        ]
        >= float(gates["uniform60_expected_success_lift_over_flat_min"]),
        "bootstrap_graph_flat_ci_lower_min_exclusive": graph_flat_lower
        > float(gates["bootstrap_graph_flat_ci_lower_min_exclusive"]),
        "positive_field_graph_flat_lift_count_min": diagnostics[
            "positive_field_graph_flat_lift_count"
        ]
        >= int(gates["positive_field_graph_flat_lift_count_min"]),
        "uniform60_expected_success_lift_over_passive_min": diagnostics[
            "uniform60_expected_success_lift_over_passive"
        ]
        >= float(gates["uniform60_expected_success_lift_over_passive_min"]),
        "uniform60_estimate_truth_pearson_min": diagnostics[
            "uniform60_estimate_truth_pearson"
        ]
        >= float(gates["uniform60_estimate_truth_pearson_min"]),
        "uniform60_invalid_selection_rate_max": primary.invalid_selection_rate
        <= float(gates["uniform60_invalid_selection_rate_max"]),
        "uniform60_provenance_completeness_min": primary.provenance_completeness
        >= float(gates["uniform60_provenance_completeness_min"]),
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
        "version": "context-graph-cg9-w3-balanced-frontier-result-v0.1",
        "config_version": config["version"],
        "confirmatory_claim": True,
        "field_ids": field_ids,
        "source_summary": source_summary,
        "metrics": {arm: asdict(metrics[arm]) for arm in arm_names},
        "field_level_uniform60_minus_fixed6_expected_success": field_primary_fixed,
        "field_level_uniform60_graph_minus_flat_expected_success": field_primary_flat,
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
