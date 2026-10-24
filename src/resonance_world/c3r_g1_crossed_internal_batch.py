"""Bounded, internal-only crossed G1 fixture batch execution and inspection.

All actions are synthetic A/B fixtures; never connect to a model provider.
A run ID is claimed *before* worker submission. Interrupted, failed or
colliding runs are NOT automatically restarted, resent or counted as valid.
Terminal signed receipts are available only in owner-private closed files.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from pathlib import Path

from resonance_world.c3r_g1_crossed_internal_lock import verify_internal_source_lock
from resonance_world.c3r_g1_crossed_local_evaluator import CrossedLocalEvaluator
from resonance_world.c3r_g1_crossed_plan import make_plan
from resonance_world.c3r_g1_crossed_receipt_bridge import verify_crossed_receipt_chain

_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{7,63}\Z")
_MAX_FINAL = 512 * 1024
_MAX_JOBS = 64


def _validate(workspace: Path, run_ids: tuple[str, ...]) -> None:
    if (not workspace.is_absolute() or workspace.is_symlink()
            or not workspace.is_dir()
            or workspace.stat().st_uid != os.geteuid()
            or workspace.stat().st_mode & 0o077):
        raise ValueError("batch workspace must be an owned private absolute directory")
    if (not isinstance(run_ids, tuple) or not 1 <= len(run_ids) <= _MAX_JOBS
            or any(not isinstance(x, str) or _NAME.fullmatch(x) is None
                   for x in run_ids)
            or len(set(run_ids)) != len(run_ids)):
        raise ValueError("batch run IDs must be unique, bounded and path-safe")


def _paths(workspace: Path, run_id: str) -> tuple[Path, Path, Path, Path]:
    stem = hashlib.sha256(run_id.encode("ascii")).hexdigest()
    return (
        workspace / (stem + ".claim.json"),
        workspace / stem,
        workspace / (stem + ".terminal.json"),
        workspace / (stem + ".failed.json"),
    )


def _write_once(path: Path, record: dict[str, object]) -> None:
    data = json.dumps(record, sort_keys=True, separators=(",", ":")).encode() + b"\n"
    if len(data) > _MAX_FINAL:
        raise ValueError("local batch record exceeds size budget")
    fd = os.open(
        path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    with os.fdopen(fd, "wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    directory_fd = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


def _read_private(path: Path) -> dict[str, object]:
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
                or info.st_mode & 0o077 or info.st_size > _MAX_FINAL):
            raise ValueError("untrusted local batch record")
        raw = os.read(fd, _MAX_FINAL + 1)
    finally:
        os.close(fd)
    if len(raw) > _MAX_FINAL:
        raise ValueError("oversized local batch record")
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError("batch record must be an object")
    return value


def _claim(workspace: Path, run_id: str) -> None:
    claim, _directory, _terminal, _failed = _paths(workspace, run_id)
    _write_once(claim, {
        "schema": "c3r-g1-crossed-batch-claim-v0.1",
        "run_id": run_id,
        "plan_digest": make_plan().public_digest,
        "state": "claimed_no_automatic_retry",
        "physical_provider_sends": 0,
        "scientific_acceptance": False,
    })


def _execute_internal_run(workspace: Path, run_id: str) -> None:
    """Worker writes *private* signed closed evidence; returns no grade."""
    _claim_path, directory, terminal_path, _failed = _paths(workspace, run_id)
    directory.mkdir(mode=0o700, exist_ok=False)
    engine = CrossedLocalEvaluator(
        run_id=run_id, signing_seed=os.urandom(32),
        private_target_seed=os.urandom(32),
        internal_checkpoint_dir=directory,
    )
    for _ in range(16):
        engine.submit(status="accepted", choice="A")
    frozen = engine.seal_source()
    if frozen["phase"] != "internal_source_frozen_qualification_allowed":
        raise ValueError("internal automatic source freeze did not complete")
    for i in range(24):
        status = "not_sent" if i == 23 else "accepted"
        reply = engine.submit(
            status=status, choice=None if status == "not_sent" else "B",
        )
        if (reply.get("phase") != "qualification_sealed"
                or set(reply) != {"schema", "phase", "qualification_received"}):
            raise ValueError("holdout grade was released before closure")
    terminal = engine.finalize()
    if (terminal["actual_provider_sends"] != 0
            or terminal["scientific_acceptance"] is not False):
        raise ValueError("synthetic fixture asserted live or scientific evidence")
    _write_once(terminal_path, {
        "schema": "c3r-g1-crossed-private-batch-terminal-v0.1",
        "run_id": run_id,
        "evaluator_public_key_hex": engine.evaluator_public_key_hex,
        "terminal": terminal,
    })


def _verify_closed(workspace: Path, run_id: str) -> dict[str, object]:
    _claim_path, directory, terminal_path, _failed = _paths(workspace, run_id)
    saved = _read_private(terminal_path)
    if (set(saved) != {"schema", "run_id", "evaluator_public_key_hex", "terminal"}
            or saved["schema"] != "c3r-g1-crossed-private-batch-terminal-v0.1"
            or saved["run_id"] != run_id):
        raise ValueError("private terminal schema/run ID mismatched")
    outcome = saved["terminal"]
    if (not isinstance(outcome, dict)
            or outcome.get("scientific_acceptance") is not False
            or outcome.get("actual_provider_sends") != 0
            or outcome.get("source_gate_mode") != "internal_durable_checkpoint"
            or outcome.get("requires_external_approval") is not False):
        raise ValueError("completed fixture does not declare internal-only mode")
    receipts = outcome["receipts"]
    if not isinstance(receipts, list):
        raise ValueError("terminal receipts must be a list")
    checked = verify_crossed_receipt_chain(
        make_plan(), receipts=tuple(receipts), mode="terminal",
        expected_run_id=run_id,
        pinned_evaluator_public_key_hex=saved["evaluator_public_key_hex"],
        expected_source_chain_head_sha256=outcome["source_chain_head_sha256"],
    )
    verify_internal_source_lock(
        directory=directory, run_id=run_id,
        evaluator_public_key_hex=saved["evaluator_public_key_hex"],
        source_receipts=tuple(receipts[:16]),
        expected_lock_sha256=outcome["internal_source_lock_sha256"],
    )
    if checked.audit != outcome["audit"]:
        raise ValueError("saved terminal audit differs from verified receipt chain")
    return {
        "run_id": run_id,
        "state": "completed_and_verified_internally",
        "logical_attempts": 40,
        "physical_provider_sends": 0,
        "source_lock_sha256": outcome["internal_source_lock_sha256"],
        "scientific_acceptance": False,
    }


def inspect_batch(*, workspace: Path, run_ids: tuple[str, ...]) -> dict[str, object]:
    """Never retries or resumes scientific attempts; reports uncertain outcomes."""
    _validate(workspace, run_ids)
    entries: list[dict[str, object]] = []
    for run_id in run_ids:
        claim_path, _directory, terminal_path, failed_path = _paths(workspace, run_id)
        if not claim_path.exists():
            state = "not_claimed"
            entry = {"run_id": run_id, "state": state}
        else:
            try:
                claimed = _read_private(claim_path)
                if claimed != {
                    "schema": "c3r-g1-crossed-batch-claim-v0.1",
                    "run_id": run_id, "plan_digest": make_plan().public_digest,
                    "state": "claimed_no_automatic_retry",
                    "physical_provider_sends": 0, "scientific_acceptance": False,
                }:
                    raise ValueError("claim payload mutated")
                if terminal_path.exists():
                    entry = _verify_closed(workspace, run_id)
                elif failed_path.exists():
                    failed = _read_private(failed_path)
                    if (set(failed) != {"schema", "run_id", "state", "error_type"}
                            or failed["schema"] != "c3r-g1-crossed-batch-failure-v0.1"
                            or failed["run_id"] != run_id
                            or failed["state"] != "failed_no_auto_retry"
                            or not isinstance(failed["error_type"], str)):
                        raise ValueError("failure journal is malformed")
                    entry = {"run_id": run_id, "state": "failed_no_auto_retry"}
                else:
                    entry = {"run_id": run_id, "state": "unresolved_no_auto_retry"}
            except (OSError, ValueError, KeyError, TypeError, UnicodeError):
                entry = {"run_id": run_id, "state": "integrity_failure"}
        entries.append(entry)
    counts: dict[str, int] = {}
    for entry in entries:
        key = str(entry["state"])
        counts[key] = counts.get(key, 0) + 1
    return {
        "schema": "c3r-g1-crossed-internal-batch-report-v0.1",
        "mode": "inspection_only",
        "runs": entries,
        "counts": counts,
        "source_gate": "internal_local_checkpoint",
        "requires_external_approval": False,
        "physical_provider_sends": 0,
        "scientific_acceptance": False,
    }


def run_batch(
    *, workspace: Path, run_ids: tuple[str, ...],
    max_workers: int = 2, max_in_flight: int = 4,
    max_new_runs: int | None = None,
) -> dict[str, object]:
    """Bound submissions, isolate failures, and never resubmit a claimed run.

    Only synthetic fixtures execute here. This is not provider orchestration.
    """
    _validate(workspace, run_ids)
    if (type(max_workers) is not int or type(max_in_flight) is not int
            or not 1 <= max_workers <= 8
            or not max_workers <= max_in_flight <= 2 * max_workers):
        raise ValueError("worker count 1..8 and in-flight cap workers..2*workers required")
    if (max_new_runs is not None
            and (type(max_new_runs) is not int
                 or not 0 <= max_new_runs <= len(run_ids))):
        raise ValueError("new run admission limit must fit requested batch")
    pending: dict[Future[None], str] = {}
    submitted = 0
    high_water = 0
    ids = iter(run_ids)
    exhausted = False
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        while pending or not exhausted:
            while not exhausted and len(pending) < max_in_flight:
                if max_new_runs is not None and submitted >= max_new_runs:
                    exhausted = True
                    break
                try:
                    run_id = next(ids)
                except StopIteration:
                    exhausted = True
                    break
                try:
                    _claim(workspace, run_id)
                except FileExistsError:
                    # Previously claimed is NOT a new scientific attempt.
                    continue
                pending[executor.submit(_execute_internal_run, workspace, run_id)] = run_id
                submitted += 1
                high_water = max(high_water, len(pending))
            if not pending:
                continue
            done, _remaining = wait(tuple(pending), return_when=FIRST_COMPLETED)
            for future in done:
                run_id = pending.pop(future)
                try:
                    future.result()
                except Exception as exc:
                    _claim_path, _directory, _terminal, failed = _paths(workspace, run_id)
                    try:
                        _write_once(failed, {
                            "schema": "c3r-g1-crossed-batch-failure-v0.1",
                            "run_id": run_id,
                            "state": "failed_no_auto_retry",
                            "error_type": type(exc).__name__,
                        })
                    except (OSError, ValueError):
                        # An unresolved claim must never be silently reconstructed.
                        pass
    output = inspect_batch(workspace=workspace, run_ids=run_ids)
    output.update({
        "mode": "bounded_offline_execution",
        "worker_limit": max_workers,
        "in_flight_limit": max_in_flight,
        "observed_high_water": high_water,
        "new_run_claims": submitted,
        "admission_limited": max_new_runs is not None,
        "automatic_retries": 0,
    })
    return output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Internal-only G1 bounded offline batch")
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--run-id", action="append", required=True)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--in-flight", type=int, default=4)
    parser.add_argument("--max-new-runs", type=int)
    parser.add_argument("--inspect", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.inspect:
            result = inspect_batch(workspace=args.workspace, run_ids=tuple(args.run_id))
        else:
            result = run_batch(
                workspace=args.workspace, run_ids=tuple(args.run_id),
                max_workers=args.workers, max_in_flight=args.in_flight,
                max_new_runs=args.max_new_runs,
            )
        print(json.dumps(result, sort_keys=True))
        return 0 if result["counts"].get("completed_and_verified_internally", 0) == len(
            args.run_id
        ) else 2
    except (OSError, ValueError, TypeError):
        print(json.dumps({
            "schema": "c3r-g1-crossed-internal-batch-report-v0.1",
            "status": "rejected_without_provider_sends",
            "scientific_acceptance": False,
        }, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
