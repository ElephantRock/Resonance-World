from __future__ import annotations

import json
from pathlib import Path

from resonance_world.w0_evidence import build_non_interference_report


def _write_artifacts(
    root: Path,
    *,
    event_text: str = "event\n",
    mean_specialization: float = 0.51,
) -> None:
    root.mkdir(parents=True)
    summary = {
        "run_id": "run-001",
        "name": "fixture",
        "ablation": "full",
        "seed": 101,
        "config_hash": "config",
        "code_sha": "code",
        "cycles": 40,
        "agents": 20,
        "metrics": {
            "event_count": 800,
            "mean_specialization": mean_specialization,
        },
    }
    (root / "experiment.json").write_text(
        json.dumps(summary, sort_keys=True) + "\n", encoding="utf-8"
    )
    (root / "agents.csv").write_text("agent_id\na1\n", encoding="utf-8")
    (root / "events.jsonl").write_text(event_text, encoding="utf-8")
    (root / "tasks.csv").write_text("task_id\nt1\n", encoding="utf-8")
    (root / "traces.csv").write_text("trace_id\nr1\n", encoding="utf-8")


def _observer_stats(path: Path, query_seconds: float = 0.02) -> None:
    path.write_text(
        json.dumps(
            {
                "attempts": 4,
                "elapsed_seconds": 1.0,
                "interval_seconds": 0.1,
                "last_counts": {"decision_events": 800},
                "query_seconds": query_seconds,
                "successful_snapshots": 3,
            }
        ),
        encoding="utf-8",
    )


def test_identical_matched_runs_pass(tmp_path: Path) -> None:
    source = tmp_path / "source"
    control = tmp_path / "control"
    observed = tmp_path / "observed"
    stats = tmp_path / "observer.json"
    _write_artifacts(source)
    _write_artifacts(control)
    _write_artifacts(observed)
    _observer_stats(stats)

    report = build_non_interference_report(
        control,
        observed,
        stats,
        control_runtime_seconds=1.0,
        observed_runtime_seconds=1.1,
        seed=101,
        source_dir=source,
    )

    assert report["passed"] is True
    assert report["hashes_identical"] is True
    assert report["source_summary_matches"] is True
    assert report["instrumentation_overhead_ratio"] < 0.05


def test_behavioral_drift_fails(tmp_path: Path) -> None:
    control = tmp_path / "control"
    observed = tmp_path / "observed"
    stats = tmp_path / "observer.json"
    _write_artifacts(control)
    _write_artifacts(observed, event_text="different\n")
    _observer_stats(stats)

    report = build_non_interference_report(
        control,
        observed,
        stats,
        control_runtime_seconds=1.0,
        observed_runtime_seconds=1.0,
        seed=202,
    )

    assert report["passed"] is False
    assert report["differing_hashes"] == ["events.jsonl"]


def test_identity_control_must_preserve_source_metrics(tmp_path: Path) -> None:
    source = tmp_path / "source"
    control = tmp_path / "control"
    observed = tmp_path / "observed"
    stats = tmp_path / "observer.json"
    _write_artifacts(source, mean_specialization=0.52)
    _write_artifacts(control, mean_specialization=0.51)
    _write_artifacts(observed, mean_specialization=0.51)
    _observer_stats(stats)

    report = build_non_interference_report(
        control,
        observed,
        stats,
        control_runtime_seconds=1.0,
        observed_runtime_seconds=1.0,
        seed=303,
        source_dir=source,
    )

    assert report["hashes_identical"] is True
    assert report["source_summary_matches"] is False
    assert report["passed"] is False
