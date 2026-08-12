"""Correct architectural parity replay for standalone Resonance ContextGraph.

This is not a new scientific experiment. It replays immutable CG-5 and CG-11 sources
and requires the standalone package to reproduce the frozen World decision semantics.
CG-11 checkpoint parity includes every observable actually consumed by the frozen
stopping implementation: pair vector, selected-role event support, and selected-role
score margin.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from experiments.context_graph.run_cg6_adaptive_acquisition import (
    base_field,
    estimator,
    missions,
)
from experiments.context_graph.run_cg10_balanced_stopping import (
    choose_stop,
    stopping_observables,
)
from experiments.context_graph.run_context_graph_standalone_parity import (
    _acquire,
    _assert_close,
    _cg5_parity,
    _compare_context,
    _read_json,
    _scheduler_parity,
)
from resonance_world.context_graph_adapter import (
    checkpoint_from_live_contexts,
    choose_stopping_point,
    pair_from_live_context,
)
from resonance_world.context_graph_w3_endogenous import _expected_success


def _checkpoint_equal(
    world: dict[str, Any],
    standalone: Any,
    *,
    tolerance: float = 1e-14,
) -> bool:
    return (
        tuple(world["pair_vector"]) == standalone.pair_vector
        and int(world["minimum_selected_role_event_support"])
        == standalone.minimum_selected_role_event_support
        and abs(
            float(world["minimum_selected_role_score_margin"])
            - standalone.minimum_selected_role_score_margin
        )
        <= tolerance
    )


def _cg11_parity(
    *,
    capsules: Path,
    summary: dict[str, Any],
    config: dict[str, Any],
    frozen: dict[str, Any],
) -> dict[str, Any]:
    world_spec = estimator(config)
    mission_rows = missions(config)
    min_confidence = float(config["society"]["min_confidence"])
    context_budget = int(config["context"]["claim_budget_cap"])
    acquisition = config["acquisition"]
    checkpoints = [int(value) for value in acquisition["checkpoints"]]
    minimum_stop = int(acquisition["minimum_stop_budget"])
    hard_cap = int(acquisition["hard_stop_budget"])
    field_ids = [f"w3-source-seed-{int(seed)}" for seed in summary["seeds"]]

    context_mismatches: list[dict[str, Any]] = []
    checkpoint_mismatches: list[dict[str, Any]] = []
    scheduler_mismatches: list[dict[str, Any]] = []
    stopping_mismatches: list[dict[str, Any]] = []
    scheduler_steps = 0
    checkpoint_count = 0
    stop_budgets: list[int] = []
    stopped_expected_total = 0.0
    fixed_expected_total = 0.0
    field_differences: dict[str, float] = {}
    stopped_claim_total = 0
    stopped_bundle_total = 0
    decisions = 0

    candidate = {
        "stable_checkpoint_count": 2,
        "minimum_selected_role_event_support": 0,
        "minimum_selected_role_score_margin": 0.0,
    }

    for field_id in field_ids:
        base = base_field(capsules, field_id, config)
        measured_by_budget: dict[int, Any] = {}
        world_rows: list[dict[str, Any]] = []
        standalone_rows: list[Any] = []
        diag_by_budget: dict[int, dict[str, Any]] = {}

        for budget in checkpoints:
            measured, _events, diag = _acquire(
                base,
                config,
                policy="uniform_round_robin",
                budget=budget,
            )
            measured_by_budget[budget] = measured
            diag_by_budget[budget] = diag

            world_row = {
                "budget": budget,
                "event_count": budget,
                **stopping_observables(
                    measured,
                    mission_rows,
                    spec=world_spec,
                    min_confidence=min_confidence,
                    context_budget=context_budget,
                ),
            }
            standalone_row = checkpoint_from_live_contexts(
                claims=measured.claims,
                field_id=measured.field_id,
                as_of=measured.as_of,
                missions=mission_rows,
                supplemental_budget=budget,
                claim_budget=context_budget,
                min_confidence=min_confidence,
            )
            checkpoint_count += 1
            if not _checkpoint_equal(world_row, standalone_row):
                if len(checkpoint_mismatches) < 25:
                    checkpoint_mismatches.append(
                        {
                            "field_id": field_id,
                            "budget": budget,
                            "world_pair_vector": list(world_row["pair_vector"]),
                            "standalone_pair_vector": list(standalone_row.pair_vector),
                            "world_support": world_row[
                                "minimum_selected_role_event_support"
                            ],
                            "standalone_support": (
                                standalone_row.minimum_selected_role_event_support
                            ),
                            "world_margin": world_row[
                                "minimum_selected_role_score_margin"
                            ],
                            "standalone_margin": (
                                standalone_row.minimum_selected_role_score_margin
                            ),
                        }
                    )
            world_rows.append(world_row)
            standalone_rows.append(standalone_row)

            for mission in mission_rows:
                _compare_context(
                    field=measured,
                    mission=mission,
                    world_spec=world_spec,
                    budget=context_budget,
                    min_confidence=min_confidence,
                    label=f"cg11-checkpoint-{budget}",
                    mismatches=context_mismatches,
                )

        steps, scheduler_rows = _scheduler_parity(
            base,
            config,
            list(diag_by_budget[checkpoints[-1]]["selection_sequence"]),
        )
        scheduler_steps += steps
        scheduler_mismatches.extend(scheduler_rows)

        world_budget, world_reason = choose_stop(
            world_rows,
            candidate,
            minimum_budget=minimum_stop,
        )
        standalone_stop = choose_stopping_point(
            standalone_rows,
            checkpoints=tuple(checkpoints),
            minimum_budget=minimum_stop,
            hard_cap=hard_cap,
        )
        if standalone_stop.budget != world_budget:
            stopping_mismatches.append(
                {
                    "field_id": field_id,
                    "world_budget": world_budget,
                    "world_reason": world_reason,
                    "standalone_budget": standalone_stop.budget,
                    "standalone_reason": standalone_stop.reason,
                }
            )
        stop_budgets.append(standalone_stop.budget)

        stopped = measured_by_budget[standalone_stop.budget]
        fixed, _fixed_events, _fixed_diag = _acquire(
            base,
            config,
            policy="fixed_six_replay",
            budget=None,
        )
        field_stopped = 0.0
        field_fixed = 0.0

        for mission in mission_rows:
            stopped_pair = _compare_context(
                field=stopped,
                mission=mission,
                world_spec=world_spec,
                budget=context_budget,
                min_confidence=min_confidence,
                label="cg11-stopped",
                mismatches=context_mismatches,
            )
            fixed_pair = _compare_context(
                field=fixed,
                mission=mission,
                world_spec=world_spec,
                budget=context_budget,
                min_confidence=min_confidence,
                label="cg11-fixed6",
                mismatches=context_mismatches,
            )
            _pair, stopped_context = pair_from_live_context(
                claims=stopped.claims,
                field_id=stopped.field_id,
                as_of=stopped.as_of,
                mission=mission,
                claim_budget=context_budget,
                min_confidence=min_confidence,
            )
            stopped_claim_total += stopped_context.claim_cost
            stopped_bundle_total += len(stopped_context.events)

            stopped_expected = (
                _expected_success(stopped, mission, stopped_pair)
                if stopped_pair is not None
                and set(stopped_pair).issubset(stopped.current_members)
                else 0.0
            )
            fixed_expected = (
                _expected_success(fixed, mission, fixed_pair)
                if fixed_pair is not None and set(fixed_pair).issubset(fixed.current_members)
                else 0.0
            )
            stopped_expected_total += stopped_expected
            fixed_expected_total += fixed_expected
            field_stopped += stopped_expected
            field_fixed += fixed_expected
            decisions += 1

        field_differences[field_id] = (field_stopped - field_fixed) / len(mission_rows)

    if context_mismatches:
        raise AssertionError(f"context parity mismatches: {context_mismatches[:3]}")
    if checkpoint_mismatches:
        raise AssertionError(f"checkpoint parity mismatches: {checkpoint_mismatches[:3]}")
    if scheduler_mismatches:
        raise AssertionError(f"scheduler parity mismatches: {scheduler_mismatches[:3]}")
    if stopping_mismatches:
        raise AssertionError(f"stopping parity mismatches: {stopping_mismatches[:3]}")

    histogram = {str(key): value for key, value in sorted(Counter(stop_budgets).items())}
    frozen_diag = frozen["diagnostics"]
    if histogram != frozen_diag["stop_budget_histogram"]:
        raise AssertionError(
            f"CG-11 stop histogram drift: {histogram} != "
            f"{frozen_diag['stop_budget_histogram']}"
        )

    mean_stop = sum(stop_budgets) / len(stop_budgets)
    stopped_expected = stopped_expected_total / decisions
    fixed_expected = fixed_expected_total / decisions
    mean_claims = stopped_claim_total / decisions
    mean_bundles = stopped_bundle_total / decisions

    _assert_close("cg11 mean stop", mean_stop, frozen_diag["mean_stopping_probe_events"])
    _assert_close(
        "cg11 stopped expected success",
        stopped_expected,
        frozen["metrics"]["stopped_graph"]["mean_expected_success"],
    )
    _assert_close(
        "cg11 fixed6 expected success",
        fixed_expected,
        frozen["metrics"]["fixed6_graph"]["mean_expected_success"],
    )
    _assert_close(
        "cg11 mean claims",
        mean_claims,
        frozen["metrics"]["stopped_graph"]["mean_context_claims"],
    )
    _assert_close(
        "cg11 mean bundles",
        mean_bundles,
        frozen["metrics"]["stopped_graph"]["mean_complete_bundles"],
    )

    frozen_field = frozen["field_level_stopped_minus_fixed6_expected_success"]
    for field_id, value in field_differences.items():
        _assert_close(
            f"cg11 {field_id} stopped-fixed6",
            value,
            float(frozen_field[field_id]),
        )

    return {
        "fields": len(field_ids),
        "decisions": decisions,
        "checkpoint_observations_checked": checkpoint_count,
        "checkpoint_context_decisions_checked": (
            len(field_ids) * len(checkpoints) * len(mission_rows)
        ),
        "final_context_decisions_checked": len(field_ids) * 2 * len(mission_rows),
        "scheduler_steps_checked": scheduler_steps,
        "context_mismatches": 0,
        "checkpoint_observable_mismatches": 0,
        "scheduler_mismatches": 0,
        "stopping_mismatches": 0,
        "mean_stopping_probe_events": mean_stop,
        "stop_budget_histogram": histogram,
        "stopped_mean_expected_success": stopped_expected,
        "fixed6_mean_expected_success": fixed_expected,
        "mean_context_claims": mean_claims,
        "mean_complete_bundles": mean_bundles,
        "passed": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cg5-capsules", type=Path, required=True)
    parser.add_argument("--cg5-summary", type=Path, required=True)
    parser.add_argument("--cg5-config", type=Path, required=True)
    parser.add_argument("--cg5-frozen-result", type=Path, required=True)
    parser.add_argument("--cg11-capsules", type=Path, required=True)
    parser.add_argument("--cg11-summary", type=Path, required=True)
    parser.add_argument("--cg11-config", type=Path, required=True)
    parser.add_argument("--cg11-frozen-result", type=Path, required=True)
    parser.add_argument("--contextgraph-commit", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    cg5 = _cg5_parity(
        capsules=args.cg5_capsules,
        summary=_read_json(args.cg5_summary),
        config=_read_json(args.cg5_config),
        frozen=_read_json(args.cg5_frozen_result),
    )
    cg11 = _cg11_parity(
        capsules=args.cg11_capsules,
        summary=_read_json(args.cg11_summary),
        config=_read_json(args.cg11_config),
        frozen=_read_json(args.cg11_frozen_result),
    )
    result = {
        "version": "context-graph-standalone-parity-v0.2",
        "status": "architectural-parity-pass",
        "scientific_claim": False,
        "contextgraph_commit": args.contextgraph_commit,
        "source_experiments": {
            "cg5": "frozen-confirmatory-pass-replay-only",
            "cg11": "frozen-confirmatory-pass-replay-only",
        },
        "cg5": cg5,
        "cg11": cg11,
        "cg11_stopping_contract_note": (
            "Executed frozen evaluator required stable pair vector and a non-negative "
            "minimum selected-role score margin. The preregistration prose described "
            "pair stability alone; architectural parity follows executed behavior and "
            "records this discrepancy explicitly."
        ),
        "retirement_gate": {
            "standalone_semantics_match_frozen_world": True,
            "world_duplicate_runtime_can_be_deprecated": True,
            "frozen_experiment_records_must_remain": True,
        },
        "passed": True,
    }
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if "practice_by_skill" in text:
        raise AssertionError("hidden capability leaked into parity output")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
