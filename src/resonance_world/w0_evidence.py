"""Build W0 matched-run non-interference evidence from Field artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from resonance_world.non_interference import FieldRunObservation, compare_observations

_ARTIFACT_FILES = (
    "experiment.json",
    "agents.csv",
    "events.jsonl",
    "tasks.csv",
    "traces.csv",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _state_hashes(root: Path) -> dict[str, str]:
    hashes = {}
    for name in _ARTIFACT_FILES:
        path = root / name
        if not path.is_file():
            raise ValueError(f"missing Field artifact: {path}")
        hashes[name] = _sha256(path)
    return hashes


def _numeric_metrics(summary: dict[str, Any]) -> dict[str, float]:
    raw = summary.get("metrics")
    if not isinstance(raw, dict):
        raise ValueError("experiment.json metrics must be an object")
    metrics = {}
    for key, value in raw.items():
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)):
            metrics[str(key)] = float(value)
    return metrics


def build_non_interference_report(
    control_dir: str | Path,
    observed_dir: str | Path,
    observer_stats_path: str | Path,
    *,
    control_runtime_seconds: float,
    observed_runtime_seconds: float,
    seed: int,
    max_instrumentation_ratio: float = 0.05,
) -> dict[str, Any]:
    """Compare matched Field runs and return a serializable W0 evidence report."""

    control_root = Path(control_dir)
    observed_root = Path(observed_dir)
    control_summary = _load_json(control_root / "experiment.json")
    observed_summary = _load_json(observed_root / "experiment.json")
    observer_stats = _load_json(Path(observer_stats_path))

    control_run_id = str(control_summary.get("run_id") or "")
    observed_run_id = str(observed_summary.get("run_id") or "")
    if not control_run_id or control_run_id != observed_run_id:
        raise ValueError("matched runs must have the same deterministic run_id")

    query_seconds = float(observer_stats.get("query_seconds", 0.0))
    successful_snapshots = int(observer_stats.get("successful_snapshots", 0))
    observer_active = successful_snapshots > 0
    control = FieldRunObservation(
        field_id=f"w0-seed-{seed}",
        checkpoint_id=control_run_id,
        state_hashes=_state_hashes(control_root),
        emergence_metrics=_numeric_metrics(control_summary),
        total_runtime_seconds=control_runtime_seconds,
    )
    observed = FieldRunObservation(
        field_id=f"w0-seed-{seed}",
        checkpoint_id=observed_run_id,
        state_hashes=_state_hashes(observed_root),
        emergence_metrics=_numeric_metrics(observed_summary),
        total_runtime_seconds=observed_runtime_seconds,
        world_instrumentation_seconds=query_seconds,
    )
    comparison = compare_observations(
        control,
        observed,
        metric_tolerance=0.0,
        max_overhead_ratio=max_instrumentation_ratio,
    )

    wall_clock_delta_ratio = (
        observed_runtime_seconds - control_runtime_seconds
    ) / control_runtime_seconds
    passed = comparison.passed and observer_active
    return {
        "behavior_identical": comparison.behavior_identical,
        "control_runtime_seconds": control_runtime_seconds,
        "differing_hashes": list(comparison.differing_hashes),
        "hashes_identical": comparison.hashes_identical,
        "instrumentation_overhead_ratio": comparison.overhead_ratio,
        "instrumentation_overhead_within_bound": comparison.overhead_within_bound,
        "max_instrumentation_ratio": max_instrumentation_ratio,
        "metric_deltas": [list(item) for item in comparison.metric_deltas],
        "metrics_within_tolerance": comparison.metrics_within_tolerance,
        "observed_runtime_seconds": observed_runtime_seconds,
        "observer": observer_stats,
        "observer_active": observer_active,
        "passed": passed,
        "run_id": control_run_id,
        "seed": seed,
        "wall_clock_delta_ratio": wall_clock_delta_ratio,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("control_dir", type=Path)
    parser.add_argument("observed_dir", type=Path)
    parser.add_argument("observer_stats", type=Path)
    parser.add_argument("report", type=Path)
    parser.add_argument("--control-runtime", required=True, type=float)
    parser.add_argument("--observed-runtime", required=True, type=float)
    parser.add_argument("--seed", required=True, type=int)
    parser.add_argument("--max-instrumentation-ratio", type=float, default=0.05)
    args = parser.parse_args(argv)
    report = build_non_interference_report(
        args.control_dir,
        args.observed_dir,
        args.observer_stats,
        control_runtime_seconds=args.control_runtime,
        observed_runtime_seconds=args.observed_runtime,
        seed=args.seed,
        max_instrumentation_ratio=args.max_instrumentation_ratio,
    )
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
