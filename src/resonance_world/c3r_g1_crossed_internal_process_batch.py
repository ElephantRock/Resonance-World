"""Hard-deadline POSIX subprocess supervisor for internal-only G1 offline fixtures.

Each unique run is claimed once on disk before process admission, with a
bounded number of *running* child processes. Timed-out/crashed children are
killed and never automatically retried. No model/provider calls are made.
This is engineering construction, not scientifically accepted G1 evidence.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from resonance_world.c3r_g1_crossed_internal_batch import (
    _claim,
    _execute_internal_run,
    _paths,
    _read_private,
    _validate,
    _write_once,
    inspect_batch,
)
from resonance_world.c3r_g1_crossed_plan import make_plan

MAX_PROCESSES = 8


def _check_claim(workspace: Path, run_id: str) -> None:
    """Child may execute only the precise already-persisted local claim."""
    _validate(workspace, (run_id,))
    claim, _directory, terminal, failed = _paths(workspace, run_id)
    expected = {
        "schema": "c3r-g1-crossed-batch-claim-v0.1",
        "run_id": run_id,
        "plan_digest": make_plan().public_digest,
        "state": "claimed_no_automatic_retry",
        "physical_provider_sends": 0,
        "scientific_acceptance": False,
    }
    if _read_private(claim) != expected:
        raise ValueError("child run claim integrity mismatch")
    if terminal.exists() or terminal.is_symlink() or failed.exists() or failed.is_symlink():
        raise ValueError("child may not replay a terminal or failed run")



def _start_worker_once(workspace: Path, run_id: str) -> None:
    """Independent O_EXCL child admission prevents duplicate manual worker launch."""
    _check_claim(workspace, run_id)
    claim, _directory, _terminal, _failed = _paths(workspace, run_id)
    start_marker = claim.with_name(claim.name.replace(".claim.json", ".started.json"))
    _write_once(start_marker, {
        "schema": "c3r-g1-crossed-process-worker-start-v0.1",
        "run_id": run_id,
        "state": "child_started_once_never_replay",
        "scientific_acceptance": False,
    })


def _spawn(workspace: Path, run_id: str) -> subprocess.Popen[bytes]:
    """Keep potentially sensitive parent env vars out of the child process."""
    env = {
        "PATH": os.environ.get("PATH", ""),
        "LANG": os.environ.get("LANG", "C"),
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    if "PYTHONPATH" in os.environ:
        env["PYTHONPATH"] = os.environ["PYTHONPATH"]
    return subprocess.Popen(
        [
            sys.executable, "-m",
            "resonance_world.c3r_g1_crossed_internal_process_batch",
            "--workspace", str(workspace), "--worker-run-id", run_id,
        ],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=env,
        start_new_session=True,
        close_fds=True,
    )


def _terminate_group(proc: subprocess.Popen[bytes]) -> None:
    """SIGKILL is a hard POSIX deadline, including same-session descendants."""
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)


def _record_failure(workspace: Path, run_id: str, reason: str) -> None:
    _claim_path, _directory, _terminal, failure = _paths(workspace, run_id)
    try:
        _write_once(failure, {
            "schema": "c3r-g1-crossed-batch-failure-v0.1",
            "run_id": run_id,
            "state": "failed_no_auto_retry",
            "error_type": reason,
        })
    except (OSError, ValueError):
        # Leave an unresolved claim rather than reconstruct or replay attempts.
        pass


def run_process_batch(
    *, workspace: Path, run_ids: tuple[str, ...],
    max_processes: int = 2, deadline_seconds: float = 30.0,
    max_new_runs: int | None = None,
) -> dict[str, object]:
    """Bound child processes; kill a stalled run; admit unrelated work.

    No automatic retry or mid-attempt resume is performed. All child calls
    execute synthetic fixture actions, not actual model/provider requests.
    """
    _validate(workspace, run_ids)
    if os.name != "posix" or not hasattr(os, "killpg"):
        raise ValueError("hard process-group deadlines require POSIX")
    if (type(max_processes) is not int or not 1 <= max_processes <= MAX_PROCESSES
            or isinstance(deadline_seconds, bool)
            or not isinstance(deadline_seconds, (int, float))
            or not math.isfinite(deadline_seconds)
            or not 0.05 <= deadline_seconds <= 600):
        raise ValueError("process limit 1..8 and deadline 0.05..600s required")
    if (max_new_runs is not None and (
        type(max_new_runs) is not int
        or not 0 <= max_new_runs <= len(run_ids)
    )):
        raise ValueError("new-run admission budget is invalid")
    active: dict[str, tuple[subprocess.Popen[bytes], float]] = {}
    names = iter(run_ids)
    exhausted = False
    admitted = 0
    max_active = 0
    deadlines_hit = 0
    try:
        while active or not exhausted:
            while not exhausted and len(active) < max_processes:
                if max_new_runs is not None and admitted >= max_new_runs:
                    exhausted = True
                    break
                try:
                    name = next(names)
                except StopIteration:
                    exhausted = True
                    break
                try:
                    _claim(workspace, name)
                except FileExistsError:
                    continue  # Already submitted once; never replay.
                admitted += 1
                try:
                    child = _spawn(workspace, name)
                except OSError:
                    _record_failure(workspace, name, "SpawnError")
                    continue
                active[name] = (child, time.monotonic() + deadline_seconds)
                max_active = max(max_active, len(active))
            if not active:
                continue
            progressed = False
            for name, (child, deadline) in tuple(active.items()):
                code = child.poll()
                if code is not None:
                    child.wait()
                    if code != 0:
                        _record_failure(workspace, name, "WorkerNonzeroExit")
                    del active[name]
                    progressed = True
                elif time.monotonic() >= deadline:
                    _terminate_group(child)
                    _record_failure(workspace, name, "DeadlineExceeded")
                    deadlines_hit += 1
                    del active[name]
                    progressed = True
            if active and not progressed:
                next_deadline = min(end for _child, end in active.values())
                time.sleep(max(0.0, min(0.025, next_deadline - time.monotonic())))
    except BaseException:
        for name, (child, _deadline) in tuple(active.items()):
            _terminate_group(child)
            _record_failure(workspace, name, "ControllerInterrupted")
        raise
    report = inspect_batch(workspace=workspace, run_ids=run_ids)
    report.update({
        "schema": "c3r-g1-crossed-process-batch-report-v0.1",
        "mode": "bounded_posix_processes_offline",
        "process_limit": max_processes,
        "per_process_deadline_seconds": float(deadline_seconds),
        "max_observed_active_processes": max_active,
        "new_run_claims": admitted,
        "admission_limited": max_new_runs is not None,
        "hard_deadlines_reached": deadlines_hit,
        "automatic_retries": 0,
        "scientific_acceptance": False,
    })
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Hard deadline internal G1 offline runs")
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--run-id", action="append")
    parser.add_argument("--worker-run-id", help="one-shot claimed child invocation")
    parser.add_argument("--processes", type=int, default=2)
    parser.add_argument("--deadline-seconds", type=float, default=30)
    parser.add_argument("--max-new-runs", type=int)
    parser.add_argument("--inspect", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.worker_run_id is not None:
            if args.run_id or args.inspect:
                raise ValueError("one-shot worker cannot accept batch operations")
            _start_worker_once(args.workspace, args.worker_run_id)
            _execute_internal_run(args.workspace, args.worker_run_id)
            return 0
        if not args.run_id:
            raise ValueError("bounded batch requires at least one run ID")
        if args.inspect:
            report = inspect_batch(
                workspace=args.workspace, run_ids=tuple(args.run_id),
            )
        else:
            report = run_process_batch(
                workspace=args.workspace, run_ids=tuple(args.run_id),
                max_processes=args.processes,
                deadline_seconds=args.deadline_seconds,
                max_new_runs=args.max_new_runs,
            )
        print(json.dumps(report, sort_keys=True))
        return 0 if report["counts"].get("completed_and_verified_internally", 0) == len(
            args.run_id
        ) else 2
    except (OSError, ValueError, TypeError, KeyError, UnicodeError):
        if args.worker_run_id is None:
            print(json.dumps({
                "schema": "c3r-g1-crossed-process-batch-report-v0.1",
                "status": "rejected_offline_without_provider_sends",
                "scientific_acceptance": False,
            }, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
