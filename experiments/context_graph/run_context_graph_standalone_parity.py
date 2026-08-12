"""Replay frozen CG-5/CG-11 graph semantics through standalone ContextGraph.

This is an architectural parity harness, not a new scientific experiment. World hidden
capability is used only after standalone decisions have been produced, to verify that
those decisions reproduce the already-frozen expected-success records. No new source
societies are generated and no scientific threshold is changed.
"""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from experiments.context_graph.run_cg4m_measurement_sufficiency import (
    _canonical_event_bundles,
    _coverage_graph_context,
)
from experiments.context_graph.run_cg6_adaptive_acquisition import (
    acquire,
    base_field,
    current_counts,
    estimator,
    missions,
    pair_from_context,
    supplemental_table,
)
from experiments.context_graph.run_cg10_balanced_stopping import choose_stop
from resonance_world.context_graph_adapter import (
    choose_stopping_point,
    next_balanced_cell,
    pair_from_live_context,
)
from resonance_world.context_graph_w3_endogenous import (
    CG4Mission,
    EndogenousField,
    LiveClaim,
    _expected_success,
    _membership_candidates,
)

Pair = tuple[str, str] | None


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain an object")
    return value


def _pair_key(pair: Pair) -> str:
    return "none" if pair is None else f"{pair[0]}::{pair[1]}"


def _noise_rate(config: dict[str, Any]) -> float:
    society = config["society"]
    if "observer_noise_rate" in society:
        return float(society["observer_noise_rate"])
    observer = society.get("observer_rule", {})
    if "scout_noise_rate" in observer:
        return float(observer["scout_noise_rate"])
    return float(society["observation_noise_rate"])


def _max_events(config: dict[str, Any]) -> int:
    society = config["society"]
    if "maximum_events_per_current_agent_skill" in society:
        return int(society["maximum_events_per_current_agent_skill"])
    return int(society["target_independent_events_per_current_agent_skill"])


def _weights() -> dict[str, float]:
    return {
        "selected_role_bonus": 0.0,
        "plausible_challenger_bonus": 0.0,
        "support_deficit_bonus": 0.0,
        "ambiguity_margin": 0.0,
    }


def _event_signature(bundle: tuple[Any, ...]) -> tuple[str, str, str, float]:
    event_id, _observer, agent_id, skill, confidence, _time, claims = bundle
    outcome = next(claim.object for claim in claims if claim.predicate == "outcome")
    return event_id, agent_id, skill, outcome, confidence


def _compare_context(
    *,
    field: EndogenousField,
    mission: CG4Mission,
    world_spec: Any,
    budget: int,
    min_confidence: float,
    label: str,
    mismatches: list[dict[str, Any]],
) -> Pair:
    world_context = _coverage_graph_context(
        field,
        mission,
        budget=budget,
        estimator=world_spec,
        min_confidence=min_confidence,
    )
    world_pair, _world_evidence = pair_from_context(
        world_context,
        mission,
        world_spec,
        min_confidence,
    )
    world_candidates = _membership_candidates(
        world_context,
        min_confidence=min_confidence,
        respect_temporal_order=True,
    )
    world_events = {
        row[0]: _event_signature(row)[1:]
        for row in _canonical_event_bundles(
            world_context,
            min_confidence=min_confidence,
        )
    }

    standalone_pair, standalone = pair_from_live_context(
        claims=field.claims,
        field_id=field.field_id,
        as_of=field.as_of,
        mission=mission,
        claim_budget=budget,
        min_confidence=min_confidence,
    )
    standalone_events = {
        event.event_id: (
            event.participant,
            event.skill,
            event.outcome,
            event.confidence,
        )
        for event in standalone.events
    }

    checks = {
        "candidates": standalone.candidates == frozenset(world_candidates),
        "claim_cost": standalone.claim_cost == len(world_context),
        "events": standalone_events == world_events,
        "pair": standalone_pair == world_pair,
        "provenance": standalone.provenance_complete,
    }
    for name, passed in checks.items():
        if passed:
            continue
        if len(mismatches) < 25:
            mismatches.append(
                {
                    "label": label,
                    "field_id": field.field_id,
                    "mission_id": mission.mission_id,
                    "kind": name,
                }
            )
    return standalone_pair


def _acquire(
    field: EndogenousField,
    config: dict[str, Any],
    *,
    policy: str,
    budget: int | None,
) -> tuple[EndogenousField, list[Any], dict[str, Any]]:
    return acquire(
        field,
        policy=policy,
        budget=budget,
        mission_rows=missions(config),
        spec=estimator(config),
        min_confidence=float(config["society"]["min_confidence"]),
        max_events=_max_events(config),
        noise_rate=_noise_rate(config),
        weights=_weights(),
    )


def _scheduler_parity(
    field: EndogenousField,
    config: dict[str, Any],
    world_sequence: list[dict[str, Any]],
) -> tuple[int, list[dict[str, Any]]]:
    min_confidence = float(config["society"]["min_confidence"])
    table, _ordered = supplemental_table(
        field,
        max_events=_max_events(config),
        min_confidence=min_confidence,
        noise_rate=_noise_rate(config),
    )
    counts = current_counts(field, min_confidence)
    positions: dict[tuple[str, str], int] = defaultdict(int)
    mismatches: list[dict[str, Any]] = []

    for row in world_sequence:
        available = tuple(
            cell
            for cell, events in table.items()
            if positions[cell] < len(events)
        )
        standalone_cell = next_balanced_cell(
            field_id=field.field_id,
            available=available,
            reconciled_event_counts=counts,
        )
        world_cell = (str(row["agent_id"]), str(row["skill"]))
        if standalone_cell != world_cell and len(mismatches) < 10:
            mismatches.append(
                {
                    "field_id": field.field_id,
                    "step": int(row["step"]),
                    "standalone": list(standalone_cell),
                    "world": list(world_cell),
                }
            )
        event = table[standalone_cell][positions[standalone_cell]]
        if event.event_index != int(row["event_index"]) and len(mismatches) < 10:
            mismatches.append(
                {
                    "field_id": field.field_id,
                    "step": int(row["step"]),
                    "standalone_event_index": event.event_index,
                    "world_event_index": int(row["event_index"]),
                }
            )
        positions[standalone_cell] += 1
        counts[standalone_cell] = counts.get(standalone_cell, 0) + 1
    return len(world_sequence), mismatches


def _assert_close(name: str, actual: float, expected: float, *, tolerance: float = 1e-14) -> None:
    if not math.isclose(actual, expected, rel_tol=0.0, abs_tol=tolerance):
        raise AssertionError(f"{name}: {actual} != {expected}")


def _cg5_parity(
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
    field_ids = [f"w3-source-seed-{int(seed)}" for seed in summary["seeds"]]
    mismatches: list[dict[str, Any]] = []
    expected_total = 0.0
    claim_total = 0
    event_total = 0
    decisions = 0
    supplemental_events = 0

    for field_id in field_ids:
        base = base_field(capsules, field_id, config)
        measured, events, _diag = _acquire(base, config, policy="fixed_six_replay", budget=None)
        supplemental_events += len(events)
        for mission in mission_rows:
            pair = _compare_context(
                field=measured,
                mission=mission,
                world_spec=world_spec,
                budget=context_budget,
                min_confidence=min_confidence,
                label="cg5-fixed6",
                mismatches=mismatches,
            )
            standalone_pair, standalone_context = pair_from_live_context(
                claims=measured.claims,
                field_id=measured.field_id,
                as_of=measured.as_of,
                mission=mission,
                claim_budget=context_budget,
                min_confidence=min_confidence,
            )
            if pair != standalone_pair:
                raise AssertionError("internal standalone pair replay drift")
            if pair is None or not set(pair).issubset(measured.current_members):
                expected = 0.0
            else:
                expected = _expected_success(measured, mission, pair)
            expected_total += expected
            claim_total += standalone_context.claim_cost
            event_total += len(standalone_context.events)
            decisions += 1

    expected_mean = expected_total / decisions
    mean_claims = claim_total / decisions
    mean_events = event_total / decisions
    frozen_metric = frozen["metrics"]["revised_coverage_graph"]
    _assert_close("cg5 expected success", expected_mean, frozen_metric["mean_expected_success"])
    _assert_close("cg5 mean claims", mean_claims, frozen_metric["mean_context_claims"])
    _assert_close("cg5 mean bundles", mean_events, frozen_metric["mean_complete_bundles"])
    if supplemental_events != int(frozen["diagnostics"]["supplemental_probe_events"]):
        raise AssertionError("cg5 supplemental event count drift")
    if mismatches:
        raise AssertionError(f"cg5 standalone parity mismatches: {mismatches[:3]}")

    return {
        "fields": len(field_ids),
        "decisions": decisions,
        "context_mismatches": len(mismatches),
        "mean_expected_success": expected_mean,
        "mean_context_claims": mean_claims,
        "mean_complete_bundles": mean_events,
        "supplemental_probe_events": supplemental_events,
        "frozen_expected_success": frozen_metric["mean_expected_success"],
        "passed": True,
    }


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
    checkpoints = [int(value) for value in config["acquisition"]["checkpoints"]]
    field_ids = [f"w3-source-seed-{int(seed)}" for seed in summary["seeds"]]
    mismatches: list[dict[str, Any]] = []
    scheduler_mismatches: list[dict[str, Any]] = []
    scheduler_steps = 0
    stopping_mismatches = 0
    stop_budgets: list[int] = []
    stopped_expected_total = 0.0
    fixed_expected_total = 0.0
    decisions = 0
    field_differences: dict[str, float] = {}
    stopped_claim_total = 0
    stopped_event_total = 0

    for field_id in field_ids:
        base = base_field(capsules, field_id, config)
        measured_by_budget: dict[int, EndogenousField] = {}
        world_pair_vectors: dict[int, tuple[str, ...]] = {}
        standalone_pair_vectors: dict[int, tuple[str, ...]] = {}
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
            world_keys: list[str] = []
            standalone_keys: list[str] = []
            for mission in mission_rows:
                world_context = _coverage_graph_context(
                    measured,
                    mission,
                    budget=context_budget,
                    estimator=world_spec,
                    min_confidence=min_confidence,
                )
                world_pair, _world_evidence = pair_from_context(
                    world_context,
                    mission,
                    world_spec,
                    min_confidence,
                )
                standalone_pair = _compare_context(
                    field=measured,
                    mission=mission,
                    world_spec=world_spec,
                    budget=context_budget,
                    min_confidence=min_confidence,
                    label=f"cg11-checkpoint-{budget}",
                    mismatches=mismatches,
                )
                world_keys.append(_pair_key(world_pair))
                standalone_keys.append(_pair_key(standalone_pair))
            world_pair_vectors[budget] = tuple(world_keys)
            standalone_pair_vectors[budget] = tuple(standalone_keys)

        steps, scheduler_rows = _scheduler_parity(
            base,
            config,
            list(diag_by_budget[checkpoints[-1]]["selection_sequence"]),
        )
        scheduler_steps += steps
        scheduler_mismatches.extend(scheduler_rows)

        world_rows = [
            {
                "budget": budget,
                "pair_vector": world_pair_vectors[budget],
                "minimum_selected_role_event_support": 0,
                "minimum_selected_role_score_margin": 0.0,
            }
            for budget in checkpoints
        ]
        world_budget, _world_reason = choose_stop(
            world_rows,
            {
                "stable_checkpoint_count": 2,
                "minimum_selected_role_event_support": 0,
                "minimum_selected_role_score_margin": 0.0,
            },
            minimum_budget=int(config["acquisition"]["minimum_stop_budget"]),
        )
        standalone_stop = choose_stopping_point(
            (
                (budget, standalone_pair_vectors[budget])
                for budget in checkpoints
            ),
            checkpoints=tuple(checkpoints),
            minimum_budget=int(config["acquisition"]["minimum_stop_budget"]),
            hard_cap=int(config["acquisition"]["hard_stop_budget"]),
        )
        if standalone_stop.budget != world_budget:
            stopping_mismatches += 1
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
                mismatches=mismatches,
            )
            fixed_pair = _compare_context(
                field=fixed,
                mission=mission,
                world_spec=world_spec,
                budget=context_budget,
                min_confidence=min_confidence,
                label="cg11-fixed6",
                mismatches=mismatches,
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
            stopped_event_total += len(stopped_context.events)

            stopped_expected = (
                _expected_success(stopped, mission, stopped_pair)
                if stopped_pair is not None and set(stopped_pair).issubset(stopped.current_members)
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

    if mismatches:
        raise AssertionError(f"cg11 context parity mismatches: {mismatches[:3]}")
    if scheduler_mismatches:
        raise AssertionError(f"cg11 scheduler parity mismatches: {scheduler_mismatches[:3]}")
    if stopping_mismatches:
        raise AssertionError(f"cg11 stopping parity mismatches: {stopping_mismatches}")

    stopped_expected = stopped_expected_total / decisions
    fixed_expected = fixed_expected_total / decisions
    mean_stop = sum(stop_budgets) / len(stop_budgets)
    histogram = {str(key): value for key, value in sorted(Counter(stop_budgets).items())}
    mean_claims = stopped_claim_total / decisions
    mean_events = stopped_event_total / decisions

    frozen_diag = frozen["diagnostics"]
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
    _assert_close("cg11 mean stop", mean_stop, frozen_diag["mean_stopping_probe_events"])
    _assert_close(
        "cg11 mean claims",
        mean_claims,
        frozen["metrics"]["stopped_graph"]["mean_context_claims"],
    )
    _assert_close(
        "cg11 mean bundles",
        mean_events,
        frozen["metrics"]["stopped_graph"]["mean_complete_bundles"],
    )
    if histogram != frozen_diag["stop_budget_histogram"]:
        raise AssertionError(f"cg11 stopping histogram drift: {histogram}")

    frozen_field = frozen["field_level_stopped_minus_fixed6_expected_success"]
    for field_id, value in field_differences.items():
        _assert_close(f"cg11 {field_id} stopped-fixed6", value, float(frozen_field[field_id]))

    return {
        "fields": len(field_ids),
        "decisions": decisions,
        "checkpoint_context_decisions_checked": len(field_ids) * len(checkpoints) * len(mission_rows),
        "final_context_decisions_checked": len(field_ids) * 2 * len(mission_rows),
        "scheduler_steps_checked": scheduler_steps,
        "context_mismatches": len(mismatches),
        "scheduler_mismatches": len(scheduler_mismatches),
        "stopping_mismatches": stopping_mismatches,
        "mean_stopping_probe_events": mean_stop,
        "stop_budget_histogram": histogram,
        "stopped_mean_expected_success": stopped_expected,
        "fixed6_mean_expected_success": fixed_expected,
        "mean_context_claims": mean_claims,
        "mean_complete_bundles": mean_events,
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
        "version": "context-graph-standalone-parity-v0.1",
        "status": "architectural-parity-pass",
        "scientific_claim": False,
        "contextgraph_commit": args.contextgraph_commit,
        "source_experiments": {
            "cg5": "frozen-confirmatory-pass-replay-only",
            "cg11": "frozen-confirmatory-pass-replay-only",
        },
        "cg5": cg5,
        "cg11": cg11,
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
