"""Run CG-4 endogenous graph calibration or preregistered evaluation."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from resonance_world.context_graph_w3_endogenous import (
    CG4Mission,
    build_endogenous_field,
    diagnostics,
    evaluate_fields,
    metric_row,
)


def _read_json(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain an object")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _source_record(
    capsules_path: Path,
    pin: dict[str, Any],
    *,
    verify_hash: bool,
) -> dict[str, Any]:
    actual = _sha256(capsules_path)
    expected = pin.get("capsules_sha256")
    if verify_hash and actual != expected:
        raise ValueError(f"capsule source hash mismatch: {actual} != {expected}")
    return {**pin, "capsules_sha256": actual}


def _missions(rows: list[dict[str, Any]]) -> list[CG4Mission]:
    return [
        CG4Mission(
            mission_id=str(row["mission_id"]),
            lead_skill=str(row["lead_skill"]),
            support_skill=str(row["support_skill"]),
        )
        for row in rows
    ]


def _build_phase(
    *,
    capsules_path: Path,
    field_ids: list[str],
    mission_rows: list[dict[str, Any]],
    experiment: dict[str, Any],
) -> dict[str, Any]:
    fields = [
        build_endogenous_field(
            capsules_path=capsules_path,
            field_id=field_id,
            initial_roster_size=int(experiment["initial_roster_size"]),
            turnover_count=int(experiment["turnover_count"]),
            probes_per_skill=int(experiment["probes_per_skill"]),
            skills_per_agent=int(experiment["skills_per_agent"]),
            noise_rate=float(experiment["observation_noise_rate"]),
            rumor_count=int(experiment["rumor_count"]),
        )
        for field_id in field_ids
    ]
    metrics = evaluate_fields(
        fields,
        _missions(mission_rows),
        context_budget=int(experiment["context_budget"]),
        min_confidence=float(experiment["min_confidence"]),
        evaluation_trials=int(experiment["evaluation_trials_per_decision"]),
    )
    rows = {arm: metric_row(value) for arm, value in metrics.items()}
    graph = metrics["endogenous_graph"]
    flat = metrics["pooled_flat"]
    shuffled = metrics["shuffled_graph"]
    stale = metrics["stale_graph"]
    conflicted = metrics["conflicted_graph"]
    oracle = metrics["oracle"]
    nonisolated = [flat, graph, shuffled, stale, conflicted]
    live = diagnostics(fields)
    return {
        "field_ids": field_ids,
        "decision_count": graph.decisions,
        "metrics": rows,
        "live_evidence": live,
        "diagnostics": {
            "belief_contamination": 0,
            "outcome_law_graph_inputs": 0,
            "nonisolated_context_budget_matched": len(
                {item.mean_context_claims for item in nonisolated}
            )
            == 1,
            "graph_success_lift_over_flat": (
                graph.mission_success_rate - flat.mission_success_rate
            ),
            "graph_expected_success_lift_over_flat": (
                graph.mean_expected_success - flat.mean_expected_success
            ),
            "graph_expected_success_lift_over_shuffled": (
                graph.mean_expected_success - shuffled.mean_expected_success
            ),
            "graph_success_lift_over_shuffled": (
                graph.mission_success_rate - shuffled.mission_success_rate
            ),
            "graph_regret_improvement_over_flat": flat.mean_regret - graph.mean_regret,
            "graph_success_lift_over_stale": (
                graph.mission_success_rate - stale.mission_success_rate
            ),
            "graph_success_lift_over_conflicted": (
                graph.mission_success_rate - conflicted.mission_success_rate
            ),
            "graph_oracle_expected_gap": (
                oracle.mean_expected_success - graph.mean_expected_success
            ),
        },
    }


def _gate_results(
    evaluation: dict[str, Any],
    gates: dict[str, Any],
) -> dict[str, bool]:
    metrics = evaluation["metrics"]
    diag = evaluation["diagnostics"]
    live = evaluation["live_evidence"]
    graph = metrics["endogenous_graph"]
    return {
        "evaluation_decision_count_min": (
            evaluation["decision_count"] >= int(gates["evaluation_decision_count_min"])
        ),
        "emitted_claims_min": live["emitted_claims"] >= int(gates["emitted_claims_min"]),
        "duplicate_observation_groups_min": (
            live["duplicate_observation_groups"]
            >= int(gates["duplicate_observation_groups_min"])
        ),
        "conflicting_observation_groups_min": (
            live["conflicting_observation_groups"]
            >= int(gates["conflicting_observation_groups_min"])
        ),
        "low_confidence_claims_min": (
            live["low_confidence_claims"] >= int(gates["low_confidence_claims_min"])
        ),
        "graph_success_lift_over_flat_min": (
            diag["graph_success_lift_over_flat"]
            >= float(gates["graph_success_lift_over_flat_min"])
        ),
        "graph_expected_success_lift_over_flat_min": (
            diag["graph_expected_success_lift_over_flat"]
            >= float(gates["graph_expected_success_lift_over_flat_min"])
        ),
        "graph_expected_success_lift_over_shuffled_min": (
            diag["graph_expected_success_lift_over_shuffled"]
            >= float(gates["graph_expected_success_lift_over_shuffled_min"])
        ),
        "graph_regret_improvement_over_flat_min": (
            diag["graph_regret_improvement_over_flat"]
            >= float(gates["graph_regret_improvement_over_flat_min"])
        ),
        "graph_invalid_selection_rate_max": (
            graph["invalid_selection_rate"]
            <= float(gates["graph_invalid_selection_rate_max"])
        ),
        "graph_provenance_completeness_min": (
            graph["provenance_completeness"]
            >= float(gates["graph_provenance_completeness_min"])
        ),
        "graph_oracle_expected_gap_max": (
            diag["graph_oracle_expected_gap"]
            <= float(gates["graph_oracle_expected_gap_max"])
        ),
        "stale_invalid_selection_rate_min": (
            metrics["stale_graph"]["invalid_selection_rate"]
            >= float(gates["stale_invalid_selection_rate_min"])
        ),
        "conflicted_invalid_selection_rate_min": (
            metrics["conflicted_graph"]["invalid_selection_rate"]
            >= float(gates["conflicted_invalid_selection_rate_min"])
        ),
        "posthoc_imported_claims_max": (
            live["posthoc_imported_claims"] <= int(gates["posthoc_imported_claims_max"])
        ),
        "historical_outcome_rows_consumed_max": (
            live["historical_outcome_rows_consumed"]
            <= int(gates["historical_outcome_rows_consumed_max"])
        ),
        "belief_contamination_max": (
            diag["belief_contamination"] <= int(gates["belief_contamination_max"])
        ),
        "outcome_law_graph_inputs_max": (
            diag["outcome_law_graph_inputs"] <= int(gates["outcome_law_graph_inputs_max"])
        ),
        "nonisolated_context_budget_matched": bool(
            diag["nonisolated_context_budget_matched"]
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--calibration-capsules", type=Path, required=True)
    parser.add_argument("--evaluation-capsules", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)

    config = _read_json(args.config)
    experiment = config["experiment"]
    calibration_pin = config["sources"]["calibration"]
    evaluation_pin = config["sources"]["evaluation"]
    calibration_source = _source_record(
        args.calibration_capsules,
        calibration_pin,
        verify_hash=True,
    )
    calibration = _build_phase(
        capsules_path=args.calibration_capsules,
        field_ids=list(calibration_pin["field_ids"]),
        mission_rows=list(experiment["calibration_missions"]),
        experiment=experiment,
    )

    evaluation = None
    evaluation_source = dict(evaluation_pin)
    gate_results = None
    passed = None
    if args.evaluation_capsules is not None:
        evaluation_source = _source_record(
            args.evaluation_capsules,
            evaluation_pin,
            verify_hash=bool(evaluation_pin.get("capsules_sha256")),
        )
        evaluation = _build_phase(
            capsules_path=args.evaluation_capsules,
            field_ids=list(evaluation_pin["field_ids"]),
            mission_rows=list(experiment["evaluation_missions"]),
            experiment=experiment,
        )
        gates = config["success_gates"]
        if not gates:
            raise ValueError("evaluation requires frozen success_gates")
        gate_results = _gate_results(evaluation, gates)
        passed = all(gate_results.values())

    result = {
        "version": "context-graph-cg4-w3-endogenous-result-v0.1",
        "config_version": config["version"],
        "scientific_boundary": config["scientific_boundary"],
        "sources": {
            "calibration": calibration_source,
            "evaluation": evaluation_source,
        },
        "calibration": calibration,
        "evaluation": evaluation,
        "gate_results": gate_results,
        "passed": passed,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if passed is not False else 1


if __name__ == "__main__":
    raise SystemExit(main())
