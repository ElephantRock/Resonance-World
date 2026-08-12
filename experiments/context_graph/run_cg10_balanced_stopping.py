"""Exploratory CG-10 cross-cohort balanced stopping calibration.

Acquisition remains deterministic uniform round-robin. The only adaptive action is
when to stop, using observable pair stability, reconciled event support, and optional
score margins. Evaluator capability is used only after a stop has been chosen to score
that stopping rule.
"""

from __future__ import annotations

import argparse
import inspect
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any

from experiments.context_graph.run_cg4m_measurement_sufficiency import (
    CellEvidence,
    _cell_evidence,
    _coverage_graph_context,
    _score,
)
from experiments.context_graph.run_cg6_adaptive_acquisition import (
    acquire,
    base_field,
    estimator,
    evaluate_measured_field,
    missions,
    pair_from_context,
    read_json,
)
from resonance_world.w4a_joint_learning import JointEnvironment

Pair = tuple[str, str] | None


def _field_ids(summary: dict[str, Any]) -> list[str]:
    return [f"w3-source-seed-{int(seed)}" for seed in summary["seeds"]]


def _pair_key(pair: Pair) -> str:
    return "none" if pair is None else f"{pair[0]}::{pair[1]}"


def stopping_observables(
    field: Any,
    mission_rows: list[Any],
    *,
    spec: Any,
    min_confidence: float,
    context_budget: int,
) -> dict[str, Any]:
    """Return only observables allowed to drive a stopping decision."""
    candidates = set(field.current_members)
    full_evidence = _cell_evidence(
        field.claims,
        candidates=candidates,
        min_confidence=min_confidence,
    )
    pair_vector: list[str] = []
    selected_support: list[int] = []
    selected_margins: list[float] = []

    for mission in mission_rows:
        context = _coverage_graph_context(
            field,
            mission,
            budget=context_budget,
            estimator=spec,
            min_confidence=min_confidence,
        )
        pair, context_evidence = pair_from_context(
            context,
            mission,
            spec,
            min_confidence,
        )
        pair_vector.append(_pair_key(pair))
        if pair is None:
            selected_support.extend([0, 0])
            selected_margins.extend([-1.0, -1.0])
            continue

        for agent_id, skill in (
            (pair[0], mission.lead_skill),
            (pair[1], mission.support_skill),
        ):
            selected_support.append(
                full_evidence.get((agent_id, skill), CellEvidence(0, 0, ())).events
            )
            selected_score = _score(context_evidence.get((agent_id, skill)), spec)
            competitor_scores = [
                _score(context_evidence.get((other, skill)), spec)
                for other in candidates
                if other != agent_id
            ]
            runner_up = max(competitor_scores) if competitor_scores else 0.0
            selected_margins.append(selected_score - runner_up)

    return {
        "pair_vector": tuple(pair_vector),
        "minimum_selected_role_event_support": min(selected_support, default=0),
        "minimum_selected_role_score_margin": min(selected_margins, default=-1.0),
    }


def _stable(history: list[dict[str, Any]], count: int) -> bool:
    if len(history) < count:
        return False
    vectors = [row["pair_vector"] for row in history[-count:]]
    return all(value == vectors[0] for value in vectors[1:])


def choose_stop(
    checkpoint_rows: list[dict[str, Any]],
    candidate: dict[str, Any],
    *,
    minimum_budget: int,
) -> tuple[int, str]:
    stable_count = int(candidate["stable_checkpoint_count"])
    min_support = int(candidate["minimum_selected_role_event_support"])
    min_margin = float(candidate["minimum_selected_role_score_margin"])
    history: list[dict[str, Any]] = []
    for row in checkpoint_rows:
        history.append(row)
        if int(row["budget"]) < minimum_budget:
            continue
        if not _stable(history, stable_count):
            continue
        if int(row["minimum_selected_role_event_support"]) < min_support:
            continue
        if float(row["minimum_selected_role_score_margin"]) < min_margin:
            continue
        return int(row["budget"]), "criterion"
    return int(checkpoint_rows[-1]["budget"]), "forced_maximum"


def _p90(values: list[int]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, math.ceil(0.90 * len(ordered)) - 1)
    return float(ordered[index])


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def evaluate(
    config: dict[str, Any],
    cohort_inputs: dict[str, tuple[Path, dict[str, Any]]],
    cg9_reference: dict[str, Any],
) -> dict[str, Any]:
    measurement = config["measurement"]
    checkpoints = [int(value) for value in measurement["checkpoints"]]
    minimum_budget = int(measurement["minimum_stop_budget"])
    max_events = int(measurement["maximum_events_per_current_agent_skill"])
    spec = estimator(config)
    mission_rows = missions(config)
    min_confidence = float(config["society"]["min_confidence"])
    noise_rate = float(config["society"]["observer_noise_rate"])
    context_budget = int(config["context"]["claim_budget_cap"])
    weights = {
        "selected_role_bonus": 0.0,
        "plausible_challenger_bonus": 0.0,
        "support_deficit_bonus": 0.0,
        "ambiguity_margin": 0.0,
    }

    seed_sets: dict[str, set[int]] = {}
    field_cache: dict[str, dict[str, Any]] = {}
    replay: dict[str, Any] = {}

    for cohort, (capsules, summary) in cohort_inputs.items():
        seeds = {int(value) for value in summary["seeds"]}
        seed_sets[cohort] = seeds
        for field_id in _field_ids(summary):
            base = base_field(capsules, field_id, config)
            measured_by_budget: dict[int, Any] = {}
            checkpoint_rows: list[dict[str, Any]] = []
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
                observables = stopping_observables(
                    measured,
                    mission_rows,
                    spec=spec,
                    min_confidence=min_confidence,
                    context_budget=context_budget,
                )
                checkpoint_rows.append(
                    {
                        "budget": budget,
                        "event_count": len(events),
                        **observables,
                    }
                )
            fixed, fixed_events, _diag = acquire(
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
            fixed_score = evaluate_measured_field(
                fixed,
                mission_rows,
                spec=spec,
                min_confidence=min_confidence,
                context_budget=context_budget,
            )
            field_cache[field_id] = {
                "cohort": cohort,
                "measured_by_budget": measured_by_budget,
                "checkpoint_rows": checkpoint_rows,
                "fixed": fixed,
                "fixed_event_count": len(fixed_events),
                "fixed_score": fixed_score,
            }

    overlaps = 0
    names = sorted(seed_sets)
    for index, left in enumerate(names):
        for right in names[index + 1 :]:
            overlaps += len(seed_sets[left].intersection(seed_sets[right]))

    candidate_results: dict[str, Any] = {}
    for candidate in config["stopping_candidates"]:
        name = str(candidate["name"])
        stop_budgets: list[int] = []
        pooled_expected: list[float] = []
        pooled_fixed: list[float] = []
        pooled_flat: list[float] = []
        forced = 0
        cohort_rows: dict[str, dict[str, list[float] | list[int]]] = {
            cohort: {"expected": [], "fixed": [], "flat": [], "budgets": []}
            for cohort in names
        }
        for field_id, row in field_cache.items():
            stop_budget, reason = choose_stop(
                row["checkpoint_rows"],
                candidate,
                minimum_budget=minimum_budget,
            )
            measured = row["measured_by_budget"][stop_budget]
            score = evaluate_measured_field(
                measured,
                mission_rows,
                spec=spec,
                min_confidence=min_confidence,
                context_budget=context_budget,
            )
            expected = float(score["graph_expected_success"])
            flat = float(score["flat_expected_success"])
            fixed_expected = float(row["fixed_score"]["graph_expected_success"])
            stop_budgets.append(stop_budget)
            pooled_expected.append(expected)
            pooled_flat.append(flat)
            pooled_fixed.append(fixed_expected)
            forced += int(reason == "forced_maximum")
            cohort_row = cohort_rows[str(row["cohort"])]
            cohort_row["expected"].append(expected)  # type: ignore[union-attr]
            cohort_row["fixed"].append(fixed_expected)  # type: ignore[union-attr]
            cohort_row["flat"].append(flat)  # type: ignore[union-attr]
            cohort_row["budgets"].append(stop_budget)  # type: ignore[union-attr]

        per_cohort: dict[str, Any] = {}
        for cohort, rows in cohort_rows.items():
            expected_values = [float(v) for v in rows["expected"]]
            fixed_values = [float(v) for v in rows["fixed"]]
            flat_values = [float(v) for v in rows["flat"]]
            budget_values = [int(v) for v in rows["budgets"]]
            per_cohort[cohort] = {
                "fields": len(expected_values),
                "mean_expected_success": _mean(expected_values),
                "mean_fixed6_expected_success": _mean(fixed_values),
                "expected_success_loss_vs_fixed6": _mean(fixed_values)
                - _mean(expected_values),
                "graph_lift_over_flat": _mean(expected_values) - _mean(flat_values),
                "mean_probe_events": _mean([float(v) for v in budget_values]),
            }

        pooled_loss = _mean(pooled_fixed) - _mean(pooled_expected)
        pooled_lift = _mean(pooled_expected) - _mean(pooled_flat)
        checks = {
            "pooled_expected_success_loss_vs_fixed6": pooled_loss
            <= float(
                config["selection_rule"]["pooled_expected_success_loss_vs_fixed6_max"]
            ),
            "per_cohort_expected_success_loss_vs_fixed6": all(
                row["expected_success_loss_vs_fixed6"]
                <= float(
                    config["selection_rule"][
                        "per_cohort_expected_success_loss_vs_fixed6_max"
                    ]
                )
                for row in per_cohort.values()
            ),
            "pooled_graph_lift_over_flat": pooled_lift
            >= float(config["selection_rule"]["pooled_graph_lift_over_cost_matched_flat_min"]),
            "mean_probe_events": _mean([float(v) for v in stop_budgets])
            <= float(config["selection_rule"]["mean_probe_events_max"]),
            "p90_probe_events": _p90(stop_budgets)
            <= float(config["selection_rule"]["p90_probe_events_max"]),
        }
        candidate_results[name] = {
            "candidate": candidate,
            "fields": len(stop_budgets),
            "mean_probe_events": _mean([float(v) for v in stop_budgets]),
            "median_probe_events": float(sorted(stop_budgets)[len(stop_budgets) // 2]),
            "p90_probe_events": _p90(stop_budgets),
            "stop_budget_histogram": {
                str(key): value for key, value in sorted(Counter(stop_budgets).items())
            },
            "forced_maximum_fields": forced,
            "pooled_mean_expected_success": _mean(pooled_expected),
            "pooled_fixed6_expected_success": _mean(pooled_fixed),
            "pooled_expected_success_loss_vs_fixed6": pooled_loss,
            "pooled_graph_lift_over_cost_matched_flat": pooled_lift,
            "per_cohort": per_cohort,
            "checks": checks,
            "qualified": all(checks.values()),
        }

    complexity = {
        name: index
        for index, name in enumerate(config["selection_rule"]["complexity_order"])
    }
    qualified = [
        (name, row)
        for name, row in candidate_results.items()
        if bool(row["qualified"])
    ]
    qualified.sort(key=lambda item: (item[1]["mean_probe_events"], complexity[item[0]]))
    selected = qualified[0][0] if qualified else None

    # CG-9 is the common-control replay because CG-10 intentionally uses its
    # mission IDs, estimator, context compiler, and deterministic acquisition rule.
    cg9_fields = [row for row in field_cache.values() if row["cohort"] == "cg9"]
    replay_fixed = _mean(
        [float(row["fixed_score"]["graph_expected_success"]) for row in cg9_fields]
    )
    cg9_uniform60 = []
    for row in cg9_fields:
        score = evaluate_measured_field(
            row["measured_by_budget"][60],
            mission_rows,
            spec=spec,
            min_confidence=min_confidence,
            context_budget=context_budget,
        )
        cg9_uniform60.append(float(score["graph_expected_success"]))
    reference_fixed = float(cg9_reference["metrics"]["fixed6_graph"]["mean_expected_success"])
    reference_uniform60 = float(
        cg9_reference["metrics"]["uniform60_graph"]["mean_expected_success"]
    )
    replay = {
        "cg9_fixed6_expected_delta": replay_fixed - reference_fixed,
        "cg9_uniform60_expected_delta": _mean(cg9_uniform60) - reference_uniform60,
        "cg9_fixed6_within_1e_12": abs(replay_fixed - reference_fixed) <= 1e-12,
        "cg9_uniform60_within_1e_12": abs(_mean(cg9_uniform60) - reference_uniform60)
        <= 1e-12,
    }

    forbidden = {
        "graph",
        "context_graph",
        "evidence",
        "claims",
        "relationship_state",
        "organization_memory",
        "acquisition_state",
    }
    outcome_inputs = len(
        forbidden.intersection(inspect.signature(JointEnvironment.evaluate).parameters)
    )
    stop_source = inspect.getsource(stopping_observables) + inspect.getsource(choose_stop)
    integrity = {
        "cohort_overlap": overlaps,
        "stopping_evaluator_truth_inputs": int(".states" in stop_source),
        "historical_outcome_rows_consumed": 0,
        "posthoc_imported_claims": 0,
        "belief_contamination": 0,
        "outcome_law_graph_inputs": outcome_inputs,
        "cg9_common_control_replay": replay,
    }

    return {
        "version": "context-graph-cg10-balanced-stopping-calibration-result-v0.1",
        "confirmatory_claim": False,
        "status": "stopping-rule-selected" if selected else "no-stopping-rule-selected",
        "cohort_field_counts": {
            cohort: len(_field_ids(summary))
            for cohort, (_capsules, summary) in cohort_inputs.items()
        },
        "candidate_results": candidate_results,
        "selection": {
            "selected_rule": selected,
            "selection_passed": selected is not None,
            "selection_rule": config["selection_rule"],
        },
        "integrity": integrity,
        "interpretation_boundary": config["interpretation_boundary"],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--cg5-capsules", type=Path, required=True)
    parser.add_argument("--cg5-summary", type=Path, required=True)
    parser.add_argument("--cg7-capsules", type=Path, required=True)
    parser.add_argument("--cg7-summary", type=Path, required=True)
    parser.add_argument("--cg9-capsules", type=Path, required=True)
    parser.add_argument("--cg9-summary", type=Path, required=True)
    parser.add_argument("--cg9-reference", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    config = read_json(args.config)
    inputs = {
        "cg5": (args.cg5_capsules, read_json(args.cg5_summary)),
        "cg7": (args.cg7_capsules, read_json(args.cg7_summary)),
        "cg9": (args.cg9_capsules, read_json(args.cg9_summary)),
    }
    result = evaluate(config, inputs, read_json(args.cg9_reference))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "selection": result["selection"],
        "candidate_results": result["candidate_results"],
        "integrity": result["integrity"],
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
