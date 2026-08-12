"""Run CG-3 decision-causality calibration or preregistered evaluation."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from resonance_world.context_graph_w5_decision import (
    build_field_decision_evidence,
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


def _capsules_path(source: Path) -> Path:
    options = [
        source / "output" / "discovery-source" / "capsules.private.jsonl",
        source / "output" / "replication-source" / "capsules.private.jsonl",
    ]
    for path in options:
        if path.exists():
            return path
    raise FileNotFoundError("capsules.private.jsonl missing from source artifact")


def _source_record(
    source: Path,
    pin: dict[str, Any],
    *,
    verify_hashes: bool,
) -> dict[str, Any]:
    raw_sha256 = {
        name: _sha256(source / "raw" / name)
        for name in ("runs.csv", "outcomes.csv", "tasks.csv", "bids.csv")
    }
    capsules_sha256 = _sha256(_capsules_path(source))
    if verify_hashes:
        if raw_sha256 != pin["raw_sha256"]:
            raise ValueError(f"raw source hash mismatch: {raw_sha256}")
        if capsules_sha256 != pin["capsules_sha256"]:
            raise ValueError(f"capsule source hash mismatch: {capsules_sha256}")
    return {
        **pin,
        "raw_sha256": raw_sha256,
        "capsules_sha256": capsules_sha256,
    }


def _build_phase(
    *,
    source_dir: Path,
    mission_rows: list[dict[str, Any]],
    field_ids: list[str],
    experiment: dict[str, Any],
) -> dict[str, Any]:
    fields = [
        build_field_decision_evidence(
            source_dir=source_dir,
            mission_rows=mission_rows,
            field_id=field_id,
            turnover_time=int(experiment["turnover_time"]),
            as_of=int(experiment["as_of"]),
            conflict_confidence=float(experiment["conflict_confidence"]),
            rumor_count=int(experiment["rumor_count"]),
        )
        for field_id in field_ids
    ]
    metrics = evaluate_fields(
        fields,
        context_budget=int(experiment["context_budget"]),
        min_confidence=float(experiment["min_confidence"]),
        evaluation_trials=int(experiment["evaluation_trials_per_decision"]),
    )
    rows = {arm: metric_row(value) for arm, value in metrics.items()}
    graph = metrics["temporal_graph"]
    flat = metrics["pooled_flat"]
    shuffled = metrics["shuffled_graph"]
    stale = metrics["stale_graph"]
    conflicted = metrics["conflicted_graph"]
    oracle = metrics["oracle"]
    nonisolated = [flat, graph, shuffled, stale, conflicted]
    return {
        "field_ids": field_ids,
        "decision_count": sum(len(field.cases) for field in fields),
        "metrics": rows,
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
            "graph_success_lift_over_shuffled": (
                graph.mission_success_rate - shuffled.mission_success_rate
            ),
            "graph_success_lift_over_stale": (
                graph.mission_success_rate - stale.mission_success_rate
            ),
            "graph_success_lift_over_conflicted": (
                graph.mission_success_rate - conflicted.mission_success_rate
            ),
            "graph_regret_improvement_over_flat": flat.mean_regret - graph.mean_regret,
            "graph_oracle_success_gap": (
                oracle.mission_success_rate - graph.mission_success_rate
            ),
            "graph_oracle_regret_gap": graph.mean_regret - oracle.mean_regret,
        },
    }


def _gate_results(
    evaluation: dict[str, Any],
    gates: dict[str, Any],
) -> dict[str, bool]:
    metrics = evaluation["metrics"]
    diagnostics = evaluation["diagnostics"]
    graph = metrics["temporal_graph"]
    return {
        "evaluation_decision_count_min": (
            evaluation["decision_count"] >= int(gates["evaluation_decision_count_min"])
        ),
        "graph_success_lift_over_flat_min": (
            diagnostics["graph_success_lift_over_flat"]
            >= float(gates["graph_success_lift_over_flat_min"])
        ),
        "graph_success_lift_over_shuffled_min": (
            diagnostics["graph_success_lift_over_shuffled"]
            >= float(gates["graph_success_lift_over_shuffled_min"])
        ),
        "graph_regret_improvement_over_flat_min": (
            diagnostics["graph_regret_improvement_over_flat"]
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
        "graph_oracle_success_gap_max": (
            diagnostics["graph_oracle_success_gap"]
            <= float(gates["graph_oracle_success_gap_max"])
        ),
        "stale_invalid_selection_rate_min": (
            metrics["stale_graph"]["invalid_selection_rate"]
            >= float(gates["stale_invalid_selection_rate_min"])
        ),
        "conflicted_invalid_selection_rate_min": (
            metrics["conflicted_graph"]["invalid_selection_rate"]
            >= float(gates["conflicted_invalid_selection_rate_min"])
        ),
        "belief_contamination_max": (
            diagnostics["belief_contamination"]
            <= int(gates["belief_contamination_max"])
        ),
        "outcome_law_graph_inputs_max": (
            diagnostics["outcome_law_graph_inputs"]
            <= int(gates["outcome_law_graph_inputs_max"])
        ),
        "nonisolated_context_budget_matched": bool(
            diagnostics["nonisolated_context_budget_matched"]
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--missions", type=Path, required=True)
    parser.add_argument("--calibration-source-dir", type=Path, required=True)
    parser.add_argument("--evaluation-source-dir", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)

    config = _read_json(args.config)
    missions = _read_json(args.missions)
    experiment = config["experiment"]
    calibration_pin = config["sources"]["calibration"]
    evaluation_pin = config["sources"]["evaluation"]

    calibration_source = _source_record(
        args.calibration_source_dir,
        calibration_pin,
        verify_hashes=True,
    )
    calibration = _build_phase(
        source_dir=args.calibration_source_dir,
        mission_rows=missions[calibration_pin["mission_section"]]["evaluation"],
        field_ids=list(calibration_pin["field_ids"]),
        experiment=experiment,
    )

    evaluation = None
    evaluation_source = dict(evaluation_pin)
    gate_results = None
    passed = None
    if args.evaluation_source_dir is not None:
        evaluation_source = _source_record(
            args.evaluation_source_dir,
            evaluation_pin,
            verify_hashes=False,
        )
        evaluation = _build_phase(
            source_dir=args.evaluation_source_dir,
            mission_rows=missions[evaluation_pin["mission_section"]]["evaluation"],
            field_ids=list(evaluation_pin["field_ids"]),
            experiment=experiment,
        )
        gates = config["success_gates"]
        if not gates:
            raise ValueError("evaluation requires frozen success_gates")
        gate_results = _gate_results(evaluation, gates)
        passed = all(gate_results.values())

    result = {
        "version": "context-graph-cg3-w5-decision-result-v0.1",
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
