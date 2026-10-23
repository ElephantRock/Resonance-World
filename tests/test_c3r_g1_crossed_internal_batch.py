"""Regression tests for bounded G1 internal batch; zero provider/network calls."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

import resonance_world.c3r_g1_crossed_internal_batch as batch


def _workspace(tmp_path: Path) -> Path:
    directory = tmp_path / "internal"
    directory.mkdir(mode=0o700)
    return directory


def test_parallel_runs_have_private_signed_snapshots_and_no_grade_in_summary(
    tmp_path: Path,
) -> None:
    path = _workspace(tmp_path)
    names = ("g1-batch-alpha", "g1-batch-beta", "g1-batch-gamma")
    result = batch.run_batch(
        workspace=path, run_ids=names, max_workers=2, max_in_flight=3,
    )
    assert result["new_run_claims"] == 3
    assert result["automatic_retries"] == 0
    assert result["worker_limit"] == 2
    assert 1 <= result["observed_high_water"] <= 3
    assert result["counts"] == {"completed_and_verified_internally": 3}
    assert result["requires_external_approval"] is False
    assert result["scientific_acceptance"] is False
    assert result["physical_provider_sends"] == 0
    public = json.dumps(result)
    assert '"correct"' not in public and '"target"' not in public
    assert '"receipts"' not in public and '"feedback"' not in public
    for name in names:
        _claim, locked_dir, terminal, _failure = batch._paths(path, name)
        assert locked_dir.is_dir()
        assert locked_dir.stat().st_mode & 0o077 == 0
        assert terminal.stat().st_mode & 0o077 == 0
        data = json.loads(terminal.read_text())
        assert len(data["terminal"]["receipts"]) == 40
        assert data["terminal"]["audit"]["scientific_acceptance"] is False
    again = batch.inspect_batch(workspace=path, run_ids=names)
    assert again["counts"]["completed_and_verified_internally"] == 3


def test_same_run_ids_are_not_reexecuted_even_when_user_requests_again(
    tmp_path: Path,
) -> None:
    path = _workspace(tmp_path)
    first = batch.run_batch(
        workspace=path, run_ids=("once-only",), max_workers=1, max_in_flight=1,
    )
    assert first["new_run_claims"] == 1
    _claim, _directory, terminal, _failed = batch._paths(path, "once-only")
    before = terminal.read_bytes()
    again = batch.run_batch(
        workspace=path, run_ids=("once-only",), max_workers=1, max_in_flight=1,
    )
    assert again["new_run_claims"] == 0
    assert again["counts"] == {"completed_and_verified_internally": 1}
    assert terminal.read_bytes() == before


def test_unresolved_claim_is_not_automatically_restarted(
    tmp_path: Path,
) -> None:
    path = _workspace(tmp_path)
    batch._claim(path, "interrupted")
    report = batch.inspect_batch(workspace=path, run_ids=("interrupted",))
    assert report["counts"] == {"unresolved_no_auto_retry": 1}
    follow_up = batch.run_batch(
        workspace=path, run_ids=("interrupted", "new-one"),
        max_workers=1, max_in_flight=1,
    )
    assert follow_up["new_run_claims"] == 1
    assert follow_up["counts"]["unresolved_no_auto_retry"] == 1
    assert follow_up["counts"]["completed_and_verified_internally"] == 1


def test_one_worker_failure_isolated_and_never_silently_retried(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = _workspace(tmp_path)
    actual = batch._execute_internal_run

    def broken_once(directory: Path, name: str) -> None:
        if name == "bad":
            raise RuntimeError("never include private exception text")
        actual(directory, name)

    monkeypatch.setattr(batch, "_execute_internal_run", broken_once)
    summary = batch.run_batch(
        workspace=path, run_ids=("bad", "healthy"),
        max_workers=2, max_in_flight=2,
    )
    assert summary["counts"] == {
        "failed_no_auto_retry": 1,
        "completed_and_verified_internally": 1,
    }
    assert "never include private exception text" not in json.dumps(summary)
    assert summary["physical_provider_sends"] == 0
    _claim, _directory, _terminal, failed = batch._paths(path, "bad")
    assert json.loads(failed.read_text())["error_type"] == "RuntimeError"
    rerun = batch.run_batch(
        workspace=path, run_ids=("bad", "healthy"),
        max_workers=1, max_in_flight=1,
    )
    assert rerun["new_run_claims"] == 0
    assert rerun["counts"]["failed_no_auto_retry"] == 1


def test_tampered_terminal_or_source_checkpoint_fails_audit(
    tmp_path: Path,
) -> None:
    path = _workspace(tmp_path)
    names = ("tampered-terminal", "deleted-source-lock")
    first = batch.run_batch(
        workspace=path, run_ids=names, max_workers=2, max_in_flight=2,
    )
    assert first["counts"]["completed_and_verified_internally"] == 2
    _claim, _directory, terminal, _failed = batch._paths(path, names[0])
    saved = json.loads(terminal.read_text())
    original = saved["terminal"]["receipts"][17]["payload"]["correct"]
    saved["terminal"]["receipts"][17]["payload"]["correct"] = not original
    terminal.write_text(json.dumps(saved))
    _claim, directory, _term, _failure = batch._paths(path, names[1])
    next(directory.glob("*.json")).unlink()
    report = batch.inspect_batch(workspace=path, run_ids=names)
    assert report["counts"] == {"integrity_failure": 2}
    assert report["scientific_acceptance"] is False


def test_hard_cap_on_in_flight_submissions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = _workspace(tmp_path)
    active = 0
    peak = 0
    lock = threading.Lock()

    def slow_worker(_directory: Path, _name: str) -> None:
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(active, peak)
        time.sleep(0.03)
        with lock:
            active -= 1
        # Deliberately no terminal record: inspect must report unresolved.

    monkeypatch.setattr(batch, "_execute_internal_run", slow_worker)
    names = tuple(f"worker-{i}" for i in range(8))
    report = batch.run_batch(
        workspace=path, run_ids=names, max_workers=2, max_in_flight=3,
    )
    assert peak == 2
    assert report["observed_high_water"] <= 3
    assert report["new_run_claims"] == 8
    assert report["counts"]["unresolved_no_auto_retry"] == 8


def test_duplicate_bad_run_ids_and_unsafe_workspace_refused_before_claim(
    tmp_path: Path,
) -> None:
    path = _workspace(tmp_path)
    for names in (("dup", "dup"), ("../escape",), ("",), tuple()):
        with pytest.raises(ValueError):
            batch.run_batch(workspace=path, run_ids=names)
    with pytest.raises(ValueError):
        batch.run_batch(workspace=path, run_ids=("bad-size",), max_workers=0)
    with pytest.raises(ValueError):
        batch.run_batch(
            workspace=path, run_ids=("over",), max_workers=2, max_in_flight=5,
        )
    assert list(path.iterdir()) == []
    path.chmod(0o755)
    with pytest.raises(ValueError):
        batch.inspect_batch(workspace=path, run_ids=("good",))
    path.chmod(0o700)
    alias = tmp_path / "alias"
    alias.symlink_to(path, target_is_directory=True)
    with pytest.raises(ValueError):
        batch.run_batch(workspace=alias, run_ids=("good",))


def test_corrupted_claim_and_cross_run_source_cannot_be_counted_complete(
    tmp_path: Path,
) -> None:
    path = _workspace(tmp_path)
    batch.run_batch(
        workspace=path, run_ids=("alpha", "beta"),
        max_workers=2, max_in_flight=2,
    )
    claim, _directory, _term, _failure = batch._paths(path, "alpha")
    claimed = json.loads(claim.read_text())
    claimed["run_id"] = "beta"
    claim.write_text(json.dumps(claimed))
    _claim, other_dir, _terminal, _fail = batch._paths(path, "beta")
    lock = next(other_dir.glob("*.json"))
    lock.unlink()
    inspected = batch.inspect_batch(workspace=path, run_ids=("alpha", "beta"))
    assert inspected["counts"] == {"integrity_failure": 2}


def test_public_only_cli_execution_then_readonly_inspection(tmp_path: Path) -> None:
    path = _workspace(tmp_path)
    cmd = [
        sys.executable, "-m", "resonance_world.c3r_g1_crossed_internal_batch",
        "--workspace", str(path), "--run-id", "cli-001",
        "--workers", "1", "--in-flight", "1",
    ]
    env = dict(os.environ)
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
    run = subprocess.run(cmd, check=True, capture_output=True, text=True, env=env)
    output = json.loads(run.stdout)
    assert output["counts"]["completed_and_verified_internally"] == 1
    inspect = subprocess.run(
        [*cmd, "--inspect"], check=True, capture_output=True, text=True, env=env,
    )
    assert json.loads(inspect.stdout)["mode"] == "inspection_only"
    assert "target_seed" not in inspect.stdout
    assert "scientific_acceptance" in inspect.stdout



def test_pause_admission_and_resume_unclaimed_only(tmp_path: Path) -> None:
    path = _workspace(tmp_path)
    ids = ("phase-1", "phase-2", "phase-3", "phase-4")
    part = batch.run_batch(
        workspace=path, run_ids=ids, max_workers=2, max_in_flight=2,
        max_new_runs=2,
    )
    assert part["new_run_claims"] == 2
    assert part["admission_limited"] is True
    assert part["counts"]["not_claimed"] == 2
    assert part["counts"]["completed_and_verified_internally"] == 2
    first_file = batch._paths(path, ids[0])[2]
    retained_terminal = first_file.read_bytes()
    follow_up = batch.run_batch(
        workspace=path, run_ids=ids, max_workers=2, max_in_flight=3,
        max_new_runs=2,
    )
    assert follow_up["new_run_claims"] == 2
    assert follow_up["counts"] == {"completed_and_verified_internally": 4}
    assert first_file.read_bytes() == retained_terminal
    all_complete = batch.run_batch(
        workspace=path, run_ids=ids, max_workers=1, max_in_flight=1,
    )
    assert all_complete["new_run_claims"] == 0
    assert all_complete["automatic_retries"] == 0


def test_admission_limit_zero_leaves_entire_batch_unstarted(tmp_path: Path) -> None:
    path = _workspace(tmp_path)
    dry = batch.run_batch(
        workspace=path, run_ids=("not-started",),
        max_workers=1, max_in_flight=1, max_new_runs=0,
    )
    assert dry["new_run_claims"] == 0
    assert dry["counts"] == {"not_claimed": 1}
    assert list(path.iterdir()) == []
    with pytest.raises(ValueError):
        batch.run_batch(
            workspace=path, run_ids=("not-started",),
            max_workers=1, max_in_flight=1, max_new_runs=True,
        )
