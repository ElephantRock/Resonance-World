"""Exploratory CG-8 coverage-constrained adaptive acquisition calibration.

CG-8 reuses only already-unblinded CG-5 and CG-7 source cohorts. It preserves the
CG-5 estimator, event reconciliation, context compiler, and decision assay. The only
new mechanism is a hard coverage constraint around the frozen CG-6 decision-adaptive
priority: every current-agent/skill cell must complete the same supplemental tier
before any cell can receive another event. Evaluator capability remains diagnostics-only.
"""

from __future__ import annotations

import argparse
import inspect
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from experiments.context_graph.run_cg4m_measurement_sufficiency import _pearson
from experiments.context_graph.run_cg6_adaptive_acquisition import (
    PolicyMetrics,
    ProbeEvent,
    base_field,
    choose_cell,
    estimator,
    evaluate_measured_field,
    evaluate_policy,
    materialize,
    missions,
    next_events,
    read_json,
    sha256,
    supplemental_table,
)
from resonance_world.context_graph_w3_endogenous import EndogenousField, LiveClaim
from resonance_world.w4a_joint_learning import JointEnvironment

Cell = tuple[str, str]


def acquire_constrained(
    field: EndogenousField,
    *,
    budget: int,
    mission_rows: list[Any],
    spec: Any,
    min_confidence: float,
    max_events: int,
    noise_rate: float,
    weights: dict[str, float],
) -> tuple[EndogenousField, list[ProbeEvent], dict[str, Any]]:
    """Acquire with a one-event maximum supplemental imbalance at every step."""
    table, _ordered = supplemental_table(
        field,
        max_events=max_events,
        min_confidence=min_confidence,
        noise_rate=noise_rate,
    )
    selected: list[ProbeEvent] = []
    selected_ids: set[str] = set()
    claims: list[LiveClaim] = list(field.claims)
    supplemental_counts = {cell: 0 for cell in table}
    peak_imbalance = 0
    sequence: list[dict[str, Any]] = []

    while len(selected) < budget:
        available = next_events(table, selected_ids)
        if not available:
            break
        floor = min(supplemental_counts.values())
        eligible = {
            cell: event
            for cell, event in available.items()
            if supplemental_counts[cell] == floor
        }
        if not eligible:
            raise AssertionError("coverage constraint found no eligible cell")
        cell = choose_cell(
            policy="decision_adaptive",
            field=field,
            claims=claims,
            available=eligible,
            mission_rows=mission_rows,
            spec=spec,
            min_confidence=min_confidence,
            weights=weights,
        )
        event = eligible[cell]
        selected.append(event)
        selected_ids.add(event.event_id)
        claims.extend(event.claims)
        supplemental_counts[cell] += 1
        imbalance = max(supplemental_counts.values()) - min(supplemental_counts.values())
        peak_imbalance = max(peak_imbalance, imbalance)
        if imbalance > 1:
            raise AssertionError(f"supplemental coverage imbalance exceeded one: {imbalance}")
        sequence.append(
            {
                "step": len(selected),
                "agent_id": cell[0],
                "skill": cell[1],
                "event_index": event.event_index,
                "supplemental_count_after": supplemental_counts[cell],
                "coverage_floor_after": min(supplemental_counts.values()),
                "coverage_ceiling_after": max(supplemental_counts.values()),
            }
        )

    if len(selected) != budget:
        raise AssertionError(f"requested {budget} events but acquired {len(selected)}")
    measured = materialize(field, selected)
    histogram: dict[str, int] = {}
    for value in supplemental_counts.values():
        key = str(value)
        histogram[key] = histogram.get(key, 0) + 1
    return measured, selected, {
        "selection_sequence": sequence,
        "supplemental_count_histogram": histogram,
        "minimum_supplemental_events_per_cell": min(supplemental_counts.values()),
        "maximum_supplemental_events_per_cell": max(supplemental_counts.values()),
        "final_supplemental_allocation_imbalance": (
            max(supplemental_counts.values()) - min(supplemental_counts.values())
        ),
        "peak_supplemental_allocation_imbalance": peak_imbalance,
        "cell_count": len(supplemental_counts),
    }


def evaluate_constrained_policy(
    base_fields: list[EndogenousField],
    *,
    budget: int,
    mission_rows: list[Any],
    spec: Any,
    min_confidence: float,
    context_budget: int,
    max_events: int,
    noise_rate: float,
    weights: dict[str, float],
    fixed_six_mean_cost: float,
    passive_graph_expected: float,
) -> tuple[PolicyMetrics, dict[str, Any]]:
    field_rows: dict[str, dict[str, Any]] = {}
    estimate_values: list[float] = []
    truth_values: list[float] = []
    total_events = 0
    acquisition_rows: dict[str, Any] = {}
    for base in base_fields:
        measured, events, acquisition = acquire_constrained(
            base,
            budget=budget,
            mission_rows=mission_rows,
            spec=spec,
            min_confidence=min_confidence,
            max_events=max_events,
            noise_rate=noise_rate,
            weights=weights,
        )
        row = evaluate_measured_field(
            measured,
            mission_rows,
            spec=spec,
            min_confidence=min_confidence,
            context_budget=context_budget,
        )
        field_rows[base.field_id] = {
            key: value for key, value in row.items() if key != "estimate_truth_pairs"
        }
        for estimate_value, truth_value in row["estimate_truth_pairs"]:
            estimate_values.append(float(estimate_value))
            truth_values.append(float(truth_value))
        total_events += len(events)
        acquisition_rows[base.field_id] = acquisition

    field_count = len(base_fields)
    decisions = field_count * len(mission_rows)
    mean_cost = total_events / field_count if field_count else 0.0

    def mean(name: str) -> float:
        return (
            sum(float(row[name]) for row in field_rows.values()) / field_count
            if field_count
            else 0.0
        )

    graph_expected = mean("graph_expected_success")
    flat_expected = mean("flat_expected_success")
    metrics = PolicyMetrics(
        policy="coverage_constrained_decision",
        budget=budget,
        fields=field_count,
        decisions=decisions,
        mean_graph_expected_success=graph_expected,
        mean_flat_expected_success=flat_expected,
        mean_oracle_expected_success=mean("oracle_expected_success"),
        mean_graph_regret=mean("graph_regret"),
        mean_selected_role_true_gap=mean("selected_role_true_gap"),
        estimate_truth_pearson=_pearson(estimate_values, truth_values),
        mean_supplemental_probe_events=mean_cost,
        total_supplemental_probe_events=total_events,
        probe_cost_fraction_vs_fixed_six=(
            mean_cost / fixed_six_mean_cost if fixed_six_mean_cost else 1.0
        ),
        graph_lift_over_cost_matched_flat=graph_expected - flat_expected,
        positive_field_graph_lift_count=sum(
            float(row["graph_minus_flat"]) > 0 for row in field_rows.values()
        ),
        decision_quality_gain_over_passive_per_probe=(
            (graph_expected - passive_graph_expected) / mean_cost if mean_cost else 0.0
        ),
    )
    constraint = {
        "maximum_final_supplemental_allocation_imbalance": max(
            int(row["final_supplemental_allocation_imbalance"])
            for row in acquisition_rows.values()
        ),
        "maximum_peak_supplemental_allocation_imbalance": max(
            int(row["peak_supplemental_allocation_imbalance"])
            for row in acquisition_rows.values()
        ),
        "minimum_supplemental_events_per_cell": min(
            int(row["minimum_supplemental_events_per_cell"])
            for row in acquisition_rows.values()
        ),
        "maximum_supplemental_events_per_cell": max(
            int(row["maximum_supplemental_events_per_cell"])
            for row in acquisition_rows.values()
        ),
        "all_fields_cell_count": sorted(
            {int(row["cell_count"]) for row in acquisition_rows.values()}
        ),
    }
    return metrics, {
        "fields": field_rows,
        "acquisition": acquisition_rows,
        "constraint": constraint,
    }


def standard_policy(
    base_fields: list[EndogenousField],
    *,
    policy: str,
    budget: int | None,
    mission_rows: list[Any],
    spec: Any,
    min_confidence: float,
    context_budget: int,
    max_events: int,
    noise_rate: float,
    weights: dict[str, float],
    fixed_six_mean_cost: float | None,
    passive_graph_expected: float | None,
) -> tuple[PolicyMetrics, dict[str, Any]]:
    return evaluate_policy(
        base_fields,
        policy=policy,
        budget=budget,
        mission_rows=mission_rows,
        spec=spec,
        min_confidence=min_confidence,
        context_budget=context_budget,
        max_events=max_events,
        noise_rate=noise_rate,
        weights=weights,
        fixed_six_mean_cost=fixed_six_mean_cost,
        passive_graph_expected=passive_graph_expected,
    )


def replay_checks(
    *,
    cg5_fields: list[EndogenousField],
    cg7_fields: list[EndogenousField],
    mission_rows: list[Any],
    spec: Any,
    min_confidence: float,
    context_budget: int,
    max_events: int,
    noise_rate: float,
    weights: dict[str, float],
    cg5_result: dict[str, Any],
    cg7_result: dict[str, Any],
) -> dict[str, Any]:
    cg5_fixed, _ = standard_policy(
        cg5_fields,
        policy="fixed_six_replay",
        budget=None,
        mission_rows=mission_rows,
        spec=spec,
        min_confidence=min_confidence,
        context_budget=context_budget,
        max_events=max_events,
        noise_rate=noise_rate,
        weights=weights,
        fixed_six_mean_cost=None,
        passive_graph_expected=None,
    )
    cg7_fixed, _ = standard_policy(
        cg7_fields,
        policy="fixed_six_replay",
        budget=None,
        mission_rows=mission_rows,
        spec=spec,
        min_confidence=min_confidence,
        context_budget=context_budget,
        max_events=max_events,
        noise_rate=noise_rate,
        weights=weights,
        fixed_six_mean_cost=None,
        passive_graph_expected=None,
    )
    cg7_uniform72, _ = standard_policy(
        cg7_fields,
        policy="uniform_round_robin",
        budget=72,
        mission_rows=mission_rows,
        spec=spec,
        min_confidence=min_confidence,
        context_budget=context_budget,
        max_events=max_events,
        noise_rate=noise_rate,
        weights=weights,
        fixed_six_mean_cost=cg7_fixed.mean_supplemental_probe_events,
        passive_graph_expected=None,
    )
    cg5_target = float(
        cg5_result["metrics"]["revised_coverage_graph"]["mean_expected_success"]
    )
    cg5_flat_target = float(
        cg5_result["metrics"]["bundle_flat_active"]["mean_expected_success"]
    )
    cg7_fixed_target = float(cg7_result["metrics"]["fixed6_graph"]["mean_expected_success"])
    cg7_uniform_target = float(
        cg7_result["metrics"]["uniform72_graph"]["mean_expected_success"]
    )
    return {
        "cg5": {
            "fixed6_event_count": cg5_fixed.total_supplemental_probe_events,
            "fixed6_expected_delta": cg5_fixed.mean_graph_expected_success - cg5_target,
            "fixed6_flat_delta": cg5_fixed.mean_flat_expected_success - cg5_flat_target,
            "event_count_exact": cg5_fixed.total_supplemental_probe_events == 3240,
            "expected_within_1e_12": abs(cg5_fixed.mean_graph_expected_success - cg5_target) <= 1e-12,
            "flat_within_1e_12": abs(cg5_fixed.mean_flat_expected_success - cg5_flat_target) <= 1e-12,
        },
        "cg7": {
            "fixed6_event_count": cg7_fixed.total_supplemental_probe_events,
            "fixed6_expected_delta": cg7_fixed.mean_graph_expected_success - cg7_fixed_target,
            "uniform72_expected_delta": cg7_uniform72.mean_graph_expected_success - cg7_uniform_target,
            "event_count_exact": cg7_fixed.total_supplemental_probe_events == 3240,
            "fixed6_expected_within_1e_12": abs(cg7_fixed.mean_graph_expected_success - cg7_fixed_target) <= 1e-12,
            "uniform72_expected_within_1e_12": abs(cg7_uniform72.mean_graph_expected_success - cg7_uniform_target) <= 1e-12,
        },
    }


def select_candidate(
    *,
    config: dict[str, Any],
    pooled_fixed: PolicyMetrics,
    pooled_constrained: dict[int, PolicyMetrics],
    pooled_uniform: dict[int, PolicyMetrics],
    cohort_fixed: dict[str, PolicyMetrics],
    cohort_constrained: dict[str, dict[int, PolicyMetrics]],
    constraint_rows: dict[int, dict[str, Any]],
) -> dict[str, Any]:
    rule = config["selection_rule"]
    selected: int | None = None
    checks: dict[str, Any] = {}
    for budget in [int(value) for value in rule["complexity_order"]]:
        row = pooled_constrained[budget]
        uniform = pooled_uniform[budget]
        retention = (
            row.mean_graph_expected_success / pooled_fixed.mean_graph_expected_success
            if pooled_fixed.mean_graph_expected_success
            else 0.0
        )
        pooled_loss = pooled_fixed.mean_graph_expected_success - row.mean_graph_expected_success
        per_cohort_loss = {
            cohort: cohort_fixed[cohort].mean_graph_expected_success
            - cohort_constrained[cohort][budget].mean_graph_expected_success
            for cohort in sorted(cohort_fixed)
        }
        role_gap_increase = (
            row.mean_selected_role_true_gap - pooled_fixed.mean_selected_role_true_gap
        )
        constraint = constraint_rows[budget]
        row_checks = {
            "expected_success_retention": retention
            >= float(rule["required_expected_success_retention_vs_fixed_six"]),
            "absolute_expected_success_loss": pooled_loss
            <= float(rule["maximum_absolute_expected_success_loss_vs_fixed_six"]),
            "per_cohort_expected_success_loss": max(per_cohort_loss.values())
            <= float(rule["maximum_per_cohort_expected_success_loss_vs_fixed_six"]),
            "graph_lift_over_cost_matched_flat": row.graph_lift_over_cost_matched_flat
            >= float(rule["minimum_graph_lift_over_cost_matched_flat"]),
            "positive_field_graph_lift_count": row.positive_field_graph_lift_count
            >= int(rule["minimum_positive_field_graph_lift_count"]),
            "lift_over_cost_matched_uniform": (
                row.mean_graph_expected_success - uniform.mean_graph_expected_success
            )
            >= float(rule["minimum_expected_success_lift_over_cost_matched_uniform"]),
            "selected_role_true_gap_increase": role_gap_increase
            <= float(rule["maximum_selected_role_true_gap_increase_vs_fixed_six"]),
            "probe_cost_fraction": row.probe_cost_fraction_vs_fixed_six
            <= float(rule["maximum_probe_cost_fraction_vs_fixed_six"]),
            "maximum_supplemental_allocation_imbalance": int(
                constraint["maximum_peak_supplemental_allocation_imbalance"]
            )
            <= int(rule["maximum_supplemental_allocation_imbalance"]),
            "minimum_supplemental_events_per_cell": int(
                constraint["minimum_supplemental_events_per_cell"]
            )
            >= int(rule["minimum_supplemental_events_per_cell"]),
        }
        checks[str(budget)] = {
            "checks": row_checks,
            "expected_success_retention": retention,
            "pooled_expected_success_loss": pooled_loss,
            "per_cohort_expected_success_loss": per_cohort_loss,
            "expected_success_lift_over_uniform": (
                row.mean_graph_expected_success - uniform.mean_graph_expected_success
            ),
            "constraint": constraint,
        }
        if selected is None and all(row_checks.values()):
            selected = budget
    return {
        "selected_budget": selected,
        "selection_passed": selected is not None,
        "checks": checks,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--cg5-capsules", type=Path, required=True)
    parser.add_argument("--cg5-summary", type=Path, required=True)
    parser.add_argument("--cg5-result", type=Path, required=True)
    parser.add_argument("--cg7-capsules", type=Path, required=True)
    parser.add_argument("--cg7-summary", type=Path, required=True)
    parser.add_argument("--cg7-result", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    config = read_json(args.config)
    cg5_summary = read_json(args.cg5_summary)
    cg7_summary = read_json(args.cg7_summary)
    cg5_result = read_json(args.cg5_result)
    cg7_result = read_json(args.cg7_result)
    predecessor = config["frozen_predecessors"]
    expected_cg5 = str(predecessor["cg5_capsules_sha256"])
    expected_cg7 = str(predecessor["cg7_capsules_sha256"])
    if sha256(args.cg5_capsules) != expected_cg5:
        raise AssertionError("CG-5 capsule hash mismatch")
    if sha256(args.cg7_capsules) != expected_cg7:
        raise AssertionError("CG-7 capsule hash mismatch")
    if str(cg5_summary["capsule_sha256"]) != expected_cg5:
        raise AssertionError("CG-5 summary capsule hash mismatch")
    if str(cg7_summary["capsule_sha256"]) != expected_cg7:
        raise AssertionError("CG-7 summary capsule hash mismatch")

    mission_rows = missions(config)
    spec = estimator(config)
    society = config["society"]
    min_confidence = float(society["min_confidence"])
    max_events = int(society["maximum_events_per_current_agent_skill"])
    noise_rate = float(society["observer_noise_rate"])
    context_budget = int(config["context"]["claim_budget_cap"])
    weights = {
        key: float(value)
        for key, value in config["acquisition"]["decision_adaptive_weights"].items()
    }

    cg5_ids = [f"w3-source-seed-{int(seed)}" for seed in cg5_summary["seeds"]]
    cg7_ids = [f"w3-source-seed-{int(seed)}" for seed in cg7_summary["seeds"]]
    if set(cg5_ids).intersection(cg7_ids):
        raise AssertionError("CG-5 and CG-7 calibration cohorts overlap")
    cg5_fields = [base_field(args.cg5_capsules, field_id, config) for field_id in cg5_ids]
    cg7_fields = [base_field(args.cg7_capsules, field_id, config) for field_id in cg7_ids]
    pooled_fields = cg5_fields + cg7_fields
    if len(pooled_fields) != int(config["evaluation"]["field_count"]):
        raise AssertionError("unexpected pooled field count")

    replay = replay_checks(
        cg5_fields=cg5_fields,
        cg7_fields=cg7_fields,
        mission_rows=mission_rows,
        spec=spec,
        min_confidence=min_confidence,
        context_budget=context_budget,
        max_events=max_events,
        noise_rate=noise_rate,
        weights=weights,
        cg5_result=cg5_result,
        cg7_result=cg7_result,
    )

    passive, _passive_detail = standard_policy(
        pooled_fields,
        policy="passive",
        budget=0,
        mission_rows=mission_rows,
        spec=spec,
        min_confidence=min_confidence,
        context_budget=context_budget,
        max_events=max_events,
        noise_rate=noise_rate,
        weights=weights,
        fixed_six_mean_cost=None,
        passive_graph_expected=None,
    )
    fixed, fixed_detail = standard_policy(
        pooled_fields,
        policy="fixed_six_replay",
        budget=None,
        mission_rows=mission_rows,
        spec=spec,
        min_confidence=min_confidence,
        context_budget=context_budget,
        max_events=max_events,
        noise_rate=noise_rate,
        weights=weights,
        fixed_six_mean_cost=None,
        passive_graph_expected=passive.mean_graph_expected_success,
    )
    fixed = PolicyMetrics(
        **{**asdict(fixed), "probe_cost_fraction_vs_fixed_six": 1.0}
    )

    cohort_fields = {"cg5": cg5_fields, "cg7": cg7_fields}
    cohort_fixed: dict[str, PolicyMetrics] = {}
    cohort_passive: dict[str, PolicyMetrics] = {}
    for cohort, fields in cohort_fields.items():
        row_passive, _ = standard_policy(
            fields,
            policy="passive",
            budget=0,
            mission_rows=mission_rows,
            spec=spec,
            min_confidence=min_confidence,
            context_budget=context_budget,
            max_events=max_events,
            noise_rate=noise_rate,
            weights=weights,
            fixed_six_mean_cost=None,
            passive_graph_expected=None,
        )
        row_fixed, _ = standard_policy(
            fields,
            policy="fixed_six_replay",
            budget=None,
            mission_rows=mission_rows,
            spec=spec,
            min_confidence=min_confidence,
            context_budget=context_budget,
            max_events=max_events,
            noise_rate=noise_rate,
            weights=weights,
            fixed_six_mean_cost=None,
            passive_graph_expected=row_passive.mean_graph_expected_success,
        )
        cohort_passive[cohort] = row_passive
        cohort_fixed[cohort] = row_fixed

    pooled_constrained: dict[int, PolicyMetrics] = {}
    pooled_uniform: dict[int, PolicyMetrics] = {}
    cohort_constrained: dict[str, dict[int, PolicyMetrics]] = {"cg5": {}, "cg7": {}}
    constraint_rows: dict[int, dict[str, Any]] = {}
    details: dict[str, Any] = {"fixed_six_replay": fixed_detail}
    for budget in [int(value) for value in config["acquisition"]["budget_candidates"]]:
        constrained, constrained_detail = evaluate_constrained_policy(
            pooled_fields,
            budget=budget,
            mission_rows=mission_rows,
            spec=spec,
            min_confidence=min_confidence,
            context_budget=context_budget,
            max_events=max_events,
            noise_rate=noise_rate,
            weights=weights,
            fixed_six_mean_cost=fixed.mean_supplemental_probe_events,
            passive_graph_expected=passive.mean_graph_expected_success,
        )
        uniform, uniform_detail = standard_policy(
            pooled_fields,
            policy="uniform_round_robin",
            budget=budget,
            mission_rows=mission_rows,
            spec=spec,
            min_confidence=min_confidence,
            context_budget=context_budget,
            max_events=max_events,
            noise_rate=noise_rate,
            weights=weights,
            fixed_six_mean_cost=fixed.mean_supplemental_probe_events,
            passive_graph_expected=passive.mean_graph_expected_success,
        )
        pooled_constrained[budget] = constrained
        pooled_uniform[budget] = uniform
        constraint_rows[budget] = constrained_detail["constraint"]
        details[f"coverage_constrained_decision_{budget}"] = constrained_detail
        details[f"uniform_round_robin_{budget}"] = uniform_detail
        for cohort, fields in cohort_fields.items():
            row, _ = evaluate_constrained_policy(
                fields,
                budget=budget,
                mission_rows=mission_rows,
                spec=spec,
                min_confidence=min_confidence,
                context_budget=context_budget,
                max_events=max_events,
                noise_rate=noise_rate,
                weights=weights,
                fixed_six_mean_cost=cohort_fixed[cohort].mean_supplemental_probe_events,
                passive_graph_expected=cohort_passive[cohort].mean_graph_expected_success,
            )
            cohort_constrained[cohort][budget] = row

    selection = select_candidate(
        config=config,
        pooled_fixed=fixed,
        pooled_constrained=pooled_constrained,
        pooled_uniform=pooled_uniform,
        cohort_fixed=cohort_fixed,
        cohort_constrained=cohort_constrained,
        constraint_rows=constraint_rows,
    )

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
    integrity = {
        **config["integrity"],
        "belief_contamination_from_retrieval": 0,
        "outcome_law_graph_inputs": outcome_law_graph_inputs,
        "acquisition_evaluator_truth_inputs": 0,
        "cohort_overlap": 0,
        "predecessor_replay": replay,
    }
    result = {
        "version": "context-graph-cg8-constrained-adaptive-calibration-result-v0.1",
        "config_version": config["version"],
        "status": "exploratory-calibration-complete",
        "confirmatory_claim": False,
        "field_ids": {"cg5": cg5_ids, "cg7": cg7_ids},
        "metrics": {
            "passive": asdict(passive),
            "fixed_six_replay": asdict(fixed),
            "coverage_constrained_decision": {
                str(budget): asdict(row)
                for budget, row in sorted(pooled_constrained.items())
            },
            "uniform_round_robin": {
                str(budget): asdict(row)
                for budget, row in sorted(pooled_uniform.items())
            },
            "cohort_fixed_six": {
                cohort: asdict(row) for cohort, row in sorted(cohort_fixed.items())
            },
            "cohort_constrained": {
                cohort: {
                    str(budget): asdict(row)
                    for budget, row in sorted(rows.items())
                }
                for cohort, rows in sorted(cohort_constrained.items())
            },
        },
        "selection": selection,
        "integrity": integrity,
        "interpretation_boundary": config["interpretation_boundary"],
        "details": details,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "selection": selection,
                "replay": replay,
                "fixed_six": asdict(fixed),
                "constrained": {
                    str(budget): asdict(row)
                    for budget, row in sorted(pooled_constrained.items())
                },
                "uniform": {
                    str(budget): asdict(row)
                    for budget, row in sorted(pooled_uniform.items())
                },
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
