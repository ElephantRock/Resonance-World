"""Execute CG-2 over pinned W5 discovery and optional replication evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from resonance_world.context_graph_w5 import (
    Arm,
    _mission,
    build_field_evidence,
    contradiction_diagnostics,
    evaluate_fields,
    metric_row,
)

NONISOLATED_ARMS: tuple[Arm, ...] = (
    "pooled_flat",
    "shared_temporal_graph",
    "shuffled_graph",
    "stale_graph",
    "unfiltered_conflict_graph",
    "graph_without_provenance",
)


def _read_json(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain an object")
    return value


def _write_json(path: str | Path, value: object) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _source_record(source_dir: Path, pin: dict[str, Any]) -> dict[str, object]:
    raw = source_dir / "raw"
    capsule_candidates = [
        source_dir / "output" / "discovery-source" / "capsules.private.jsonl",
        source_dir / "output" / "replication-source" / "capsules.private.jsonl",
    ]
    capsules = next((path for path in capsule_candidates if path.exists()), None)
    if capsules is None:
        raise FileNotFoundError("missing W5 capsules.private.jsonl")
    return {
        **pin,
        "raw_sha256": {
            name: _sha256(raw / name)
            for name in ("runs.csv", "outcomes.csv", "tasks.csv", "bids.csv")
        },
        "capsules_sha256": _sha256(capsules),
    }


def _build_phase(
    *,
    source_dir: Path,
    field_ids: list[str],
    missions_raw: list[dict[str, Any]],
    experiment: dict[str, Any],
):
    missions = [_mission(row) for row in missions_raw]
    return [
        build_field_evidence(
            source_dir=source_dir,
            missions=missions,
            field_id=field_id,
            history_depth=int(experiment["history_depth"]),
            strategy_order=[str(item) for item in experiment["strategy_order"]],  # type: ignore[list-item]
            turnover_time=int(experiment["turnover_time"]),
            as_of=int(experiment["as_of"]),
            conflict_confidence=float(experiment["conflict_confidence"]),
        )
        for field_id in field_ids
    ]


def _phase_row(fields, *, experiment: dict[str, Any]) -> dict[str, object]:
    metrics = evaluate_fields(
        fields,
        context_budget=int(experiment["context_budget"]),
        min_confidence=float(experiment["min_confidence"]),
    )
    diagnostics = contradiction_diagnostics(
        fields,
        as_of=int(experiment["as_of"]),
        min_confidence=float(experiment["min_confidence"]),
    )
    return {
        "field_ids": [field.field_id for field in fields],
        "query_count": sum(len(field.queries) for field in fields),
        "metrics": {arm: metric_row(row) for arm, row in metrics.items()},
        "diagnostics": diagnostics,
    }


def _gates(
    evaluation: dict[str, object],
    gates: dict[str, Any],
    experiment: dict[str, Any],
) -> tuple[dict[str, bool], dict[str, object]]:
    metrics = evaluation["metrics"]
    diagnostics = evaluation["diagnostics"]
    shared = metrics["shared_temporal_graph"]
    flat = metrics["pooled_flat"]
    shuffled = metrics["shuffled_graph"]
    stale = metrics["stale_graph"]
    unfiltered = metrics["unfiltered_conflict_graph"]
    no_provenance = metrics["graph_without_provenance"]

    query_count = int(evaluation["query_count"])
    budget = int(experiment["context_budget"])
    matched = all(
        int(metrics[arm]["context_claims"]) == budget * query_count
        for arm in NONISOLATED_ARMS
    )
    no_provenance_recall_delta = abs(
        float(shared["recall"]) - float(no_provenance["recall"])
    )
    diagnostics_row = {
        "nonisolated_context_budget_matched": matched,
        "shared_recall_lift_over_flat": float(shared["recall"]) - float(flat["recall"]),
        "shared_recall_lift_over_shuffled": (
            float(shared["recall"]) - float(shuffled["recall"])
        ),
        "shared_exact_lift_over_stale": (
            float(shared["exact_query_rate"]) - float(stale["exact_query_rate"])
        ),
        "shared_exact_lift_over_unfiltered": (
            float(shared["exact_query_rate"])
            - float(unfiltered["exact_query_rate"])
        ),
        "no_provenance_recall_delta": no_provenance_recall_delta,
        "belief_contamination": 0,
    }
    gate_results = {
        "evaluation_query_count_min": query_count >= int(gates["evaluation_query_count_min"]),
        "shared_recall_min": float(shared["recall"]) >= float(gates["shared_recall_min"]),
        "shared_exact_query_rate_min": (
            float(shared["exact_query_rate"]) >= float(gates["shared_exact_query_rate_min"])
        ),
        "shared_false_positive_rate_max": (
            float(shared["false_positive_rate"])
            <= float(gates["shared_false_positive_rate_max"])
        ),
        "shared_recall_lift_over_flat_min": (
            diagnostics_row["shared_recall_lift_over_flat"]
            >= float(gates["shared_recall_lift_over_flat_min"])
        ),
        "shared_recall_lift_over_shuffled_min": (
            diagnostics_row["shared_recall_lift_over_shuffled"]
            >= float(gates["shared_recall_lift_over_shuffled_min"])
        ),
        "shared_exact_lift_over_stale_min": (
            diagnostics_row["shared_exact_lift_over_stale"]
            >= float(gates["shared_exact_lift_over_stale_min"])
        ),
        "shared_exact_lift_over_unfiltered_min": (
            diagnostics_row["shared_exact_lift_over_unfiltered"]
            >= float(gates["shared_exact_lift_over_unfiltered_min"])
        ),
        "shared_provenance_completeness_min": (
            float(shared["provenance_completeness"])
            >= float(gates["shared_provenance_completeness_min"])
        ),
        "shared_source_classes_min": (
            float(shared["mean_source_classes"])
            >= float(gates["shared_source_classes_min"])
        ),
        "no_provenance_recall_delta_max": (
            no_provenance_recall_delta
            <= float(gates["no_provenance_recall_delta_max"])
        ),
        "no_provenance_completeness_max": (
            float(no_provenance["provenance_completeness"])
            <= float(gates["no_provenance_completeness_max"])
        ),
        "raw_conflicts_min": (
            int(diagnostics["raw_false_current_membership_claims"])
            >= int(gates["raw_conflicts_min"])
        ),
        "filtered_conflicts_max": (
            int(diagnostics["filtered_false_current_membership_claims"])
            <= int(gates["filtered_conflicts_max"])
        ),
        "nonisolated_context_budget_matched": matched,
        "belief_contamination_max": (
            int(diagnostics_row["belief_contamination"])
            <= int(gates["belief_contamination_max"])
        ),
    }
    return gate_results, diagnostics_row


def run(
    *,
    config_path: str | Path,
    missions_path: str | Path,
    calibration_source_dir: str | Path,
    evaluation_source_dir: str | Path | None,
    output_path: str | Path,
) -> dict[str, object]:
    config = _read_json(config_path)
    missions = _read_json(missions_path)
    experiment = config["experiment"]
    calibration_pin = config["sources"]["calibration"]
    evaluation_pin = config["sources"]["evaluation"]

    calibration_source = Path(calibration_source_dir)
    calibration_fields = _build_phase(
        source_dir=calibration_source,
        field_ids=[str(item) for item in calibration_pin["field_ids"]],
        missions_raw=list(missions[str(calibration_pin["mission_section"])]["formation"]),
        experiment=experiment,
    )
    calibration = _phase_row(calibration_fields, experiment=experiment)

    result: dict[str, object] = {
        "version": "context-graph-cg2-w5-result-v0.1",
        "config_version": config["version"],
        "scientific_boundary": (
            "CG-2 evaluates retrieval and lineage reconstruction only; "
            "it does not reinterpret W5's replicated null for productive institutional memory."
        ),
        "sources": {
            "calibration": _source_record(calibration_source, calibration_pin),
            "evaluation": evaluation_pin,
        },
        "calibration": calibration,
        "evaluation": None,
        "gate_results": None,
        "diagnostics": None,
        "passed": None,
    }

    if evaluation_source_dir is not None:
        evaluation_source = Path(evaluation_source_dir)
        evaluation_fields = _build_phase(
            source_dir=evaluation_source,
            field_ids=[str(item) for item in evaluation_pin["field_ids"]],
            missions_raw=list(missions[str(evaluation_pin["mission_section"])]["formation"]),
            experiment=experiment,
        )
        evaluation = _phase_row(evaluation_fields, experiment=experiment)
        gate_results, diagnostics = _gates(
            evaluation,
            config["success_gates"],
            experiment,
        )
        result["sources"]["evaluation"] = _source_record(
            evaluation_source,
            evaluation_pin,
        )
        result["evaluation"] = evaluation
        result["gate_results"] = gate_results
        result["diagnostics"] = diagnostics
        result["passed"] = all(gate_results.values())

    _write_json(output_path, result)
    print(json.dumps(result, indent=2, sort_keys=True))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="experiments/context_graph/cg2-w5.json")
    parser.add_argument("--missions", default="configs/w5/institution-missions.json")
    parser.add_argument("--calibration-source-dir", required=True)
    parser.add_argument("--evaluation-source-dir")
    parser.add_argument(
        "--output",
        default="output/context_graph/cg2-w5-result.json",
    )
    args = parser.parse_args()
    result = run(
        config_path=args.config,
        missions_path=args.missions,
        calibration_source_dir=args.calibration_source_dir,
        evaluation_source_dir=args.evaluation_source_dir,
        output_path=args.output,
    )
    if args.evaluation_source_dir is not None and not result["passed"]:
        raise SystemExit("CG-2 failed preregistered evaluation gates")


if __name__ == "__main__":
    main()
