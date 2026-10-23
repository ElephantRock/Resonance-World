"""Hard deadline process batch tests; provider sends and external auditors: none."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

import resonance_world.c3r_g1_crossed_internal_process_batch as process_batch
from resonance_world.c3r_g1_crossed_internal_batch import _paths


def _workspace(tmp_path: Path) -> Path:
    path = tmp_path / "only-internal"
    path.mkdir(mode=0o700)
    return path


def test_parallel_processes_complete_and_reinspect_public_results(
    tmp_path: Path,
) -> None:
    workspace = _workspace(tmp_path)
    ids = ("proc-batch-0001", "proc-batch-0002", "proc-batch-0003")
    report = process_batch.run_process_batch(
        workspace=workspace, run_ids=ids, max_processes=2,
        deadline_seconds=20,
    )
    assert report["mode"] == "bounded_posix_processes_offline"
    assert report["counts"] == {"completed_and_verified_internally": 3}
    assert report["new_run_claims"] == 3
    assert report["max_observed_active_processes"] <= 2
    assert report["hard_deadlines_reached"] == 0
    assert report["automatic_retries"] == 0
    assert report["physical_provider_sends"] == 0
    assert report["scientific_acceptance"] is False
    assert report["requires_external_approval"] is False
    public = json.dumps(report)
    assert '"feedback"' not in public
    assert '"correct"' not in public
    assert '"receipts"' not in public
    for run_id in ids:
        claim, folder, terminal, failed = _paths(workspace, run_id)
        assert claim.exists() and folder.is_dir() and terminal.exists()
        assert not failed.exists()
        assert terminal.stat().st_mode & 0o077 == 0
        assert len(json.loads(terminal.read_text())["terminal"]["receipts"]) == 40
    inspected = process_batch.inspect_batch(workspace=workspace, run_ids=ids)
    assert inspected["counts"] == {"completed_and_verified_internally": 3}


def test_claimed_run_is_never_launched_twice(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = _workspace(tmp_path)
    ids = ("proc-single-0001",)
    first = process_batch.run_process_batch(
        workspace=path, run_ids=ids, max_processes=1,
    )
    assert first["new_run_claims"] == 1

    def forbidden_spawn(_workspace: Path, _run_id: str):
        raise AssertionError("a claimed experiment may not be replayed")

    monkeypatch.setattr(process_batch, "_spawn", forbidden_spawn)
    repeat = process_batch.run_process_batch(
        workspace=path, run_ids=ids, max_processes=1,
    )
    assert repeat["new_run_claims"] == 0
    assert repeat["counts"] == {"completed_and_verified_internally": 1}


def test_deadline_kills_hung_process_but_unrelated_run_completes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = _workspace(tmp_path)
    real_spawn = process_batch._spawn
    sleepers = []

    def controlled_spawn(workspace: Path, run_id: str):
        if run_id == "proc-hung-0001":
            child = subprocess.Popen(
                [sys.executable, "-c", "import time;time.sleep(60)"],
                start_new_session=True, stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            sleepers.append(child)
            return child
        return real_spawn(workspace, run_id)

    monkeypatch.setattr(process_batch, "_spawn", controlled_spawn)
    result = process_batch.run_process_batch(
        workspace=path,
        run_ids=("proc-hung-0001", "proc-healthy-0001"),
        max_processes=2,
        deadline_seconds=4,
    )
    assert result["hard_deadlines_reached"] == 1
    assert result["counts"] == {
        "failed_no_auto_retry": 1,
        "completed_and_verified_internally": 1,
    }
    assert all(p.poll() is not None for p in sleepers)
    _claim, _dir, terminal, failed = _paths(path, "proc-hung-0001")
    assert not terminal.exists()
    assert json.loads(failed.read_text())["error_type"] == "DeadlineExceeded"
    replay = process_batch.run_process_batch(
        workspace=path, run_ids=("proc-hung-0001",),
        max_processes=1, deadline_seconds=1,
    )
    assert replay["new_run_claims"] == 0
    assert replay["counts"] == {"failed_no_auto_retry": 1}


def test_nonzero_child_does_not_block_other_runs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = _workspace(tmp_path)
    real_spawn = process_batch._spawn

    def controlled_spawn(workspace: Path, run_id: str):
        if run_id == "proc-failure-0001":
            return subprocess.Popen(
                [sys.executable, "-c", "raise SystemExit(9)"],
                start_new_session=True, stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        return real_spawn(workspace, run_id)

    monkeypatch.setattr(process_batch, "_spawn", controlled_spawn)
    result = process_batch.run_process_batch(
        workspace=path,
        run_ids=("proc-failure-0001", "proc-ok-0001"),
        max_processes=2,
    )
    assert result["counts"] == {
        "failed_no_auto_retry": 1,
        "completed_and_verified_internally": 1,
    }
    assert json.loads(_paths(path, "proc-failure-0001")[3].read_text())[
        "error_type"
    ] == "WorkerNonzeroExit"


def test_admission_pause_continues_only_not_claimed_run_ids(
    tmp_path: Path,
) -> None:
    path = _workspace(tmp_path)
    ids = ("proc-phase-0001", "proc-phase-0002", "proc-phase-0003")
    part = process_batch.run_process_batch(
        workspace=path, run_ids=ids,
        max_processes=2, max_new_runs=1,
    )
    assert part["new_run_claims"] == 1
    assert part["counts"]["not_claimed"] == 2
    second = process_batch.run_process_batch(
        workspace=path, run_ids=ids,
        max_processes=2, max_new_runs=2,
    )
    assert second["new_run_claims"] == 2
    assert second["counts"] == {"completed_and_verified_internally": 3}
    third = process_batch.run_process_batch(
        workspace=path, run_ids=ids,
        max_processes=2,
    )
    assert third["new_run_claims"] == 0


def test_interrupted_claim_remains_unresolved_without_reexecution(
    tmp_path: Path,
) -> None:
    path = _workspace(tmp_path)
    process_batch._claim(path, "proc-interrupted-0001")
    result = process_batch.run_process_batch(
        workspace=path, run_ids=("proc-interrupted-0001", "proc-other-0001"),
        max_processes=1,
    )
    assert result["new_run_claims"] == 1
    assert result["counts"]["unresolved_no_auto_retry"] == 1
    assert result["counts"]["completed_and_verified_internally"] == 1


def test_invalid_deadline_workers_and_directory_fail_before_claim(
    tmp_path: Path,
) -> None:
    path = _workspace(tmp_path)
    ids = ("proc-invalid-0001",)
    for kwargs in (
        {"max_processes": 0}, {"max_processes": 9},
        {"deadline_seconds": 0}, {"deadline_seconds": float("nan")},
        {"deadline_seconds": True}, {"deadline_seconds": 601},
        {"max_new_runs": True}, {"max_new_runs": 2},
    ):
        with pytest.raises(ValueError):
            process_batch.run_process_batch(workspace=path, run_ids=ids, **kwargs)
    assert list(path.iterdir()) == []
    path.chmod(0o755)
    with pytest.raises(ValueError):
        process_batch.run_process_batch(workspace=path, run_ids=ids)


def test_child_requires_preexisting_correct_claim_and_no_terminal(
    tmp_path: Path,
) -> None:
    path = _workspace(tmp_path)
    with pytest.raises(FileNotFoundError):
        process_batch._check_claim(path, "proc-not-claimed-0001")
    process_batch._claim(path, "proc-claimed-0001")
    process_batch._check_claim(path, "proc-claimed-0001")
    claim = _paths(path, "proc-claimed-0001")[0]
    obj = json.loads(claim.read_text())
    obj["plan_digest"] = "0" * 64
    claim.write_text(json.dumps(obj))
    with pytest.raises(ValueError, match="claim integrity"):
        process_batch._check_claim(path, "proc-claimed-0001")


def test_cli_process_batch_and_readonly_inspection(tmp_path: Path) -> None:
    path = _workspace(tmp_path)
    env = dict(os.environ)
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
    command = [
        sys.executable, "-m",
        "resonance_world.c3r_g1_crossed_internal_process_batch",
        "--workspace", str(path),
        "--run-id", "proc-cli-0001", "--processes", "1",
        "--deadline-seconds", "30",
    ]
    result = subprocess.run(
        command, env=env, capture_output=True, text=True, check=True, timeout=30,
    )
    parsed = json.loads(result.stdout)
    assert parsed["counts"] == {"completed_and_verified_internally": 1}
    inspected = subprocess.run(
        [*command, "--inspect"],
        env=env, capture_output=True, text=True, check=True, timeout=30,
    )
    assert json.loads(inspected.stdout)["mode"] == "inspection_only"
    assert '"correct"' not in inspected.stdout
    assert '"receipts"' not in inspected.stdout
    assert "scientific_acceptance" in inspected.stdout



def test_manual_or_duplicate_child_admission_is_exclusive(tmp_path: Path) -> None:
    path = _workspace(tmp_path)
    process_batch._claim(path, "proc-child-once-0001")
    process_batch._start_worker_once(path, "proc-child-once-0001")
    with pytest.raises(FileExistsError):
        process_batch._start_worker_once(path, "proc-child-once-0001")
    start_marker = next(path.glob("*.started.json"))
    assert start_marker.stat().st_mode & 0o077 == 0
    assert json.loads(start_marker.read_text())["run_id"] == "proc-child-once-0001"
    assert process_batch.inspect_batch(
        workspace=path, run_ids=("proc-child-once-0001",),
    )["counts"] == {"unresolved_no_auto_retry": 1}
