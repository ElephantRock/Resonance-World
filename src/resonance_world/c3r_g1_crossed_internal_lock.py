"""Internal-first durable G1 source checkpoint; no additional approval service.

The evaluator verifies its own 16 signed source receipts, records their
digest using exclusive creation and fsync, then may enter qualification.
This prevents accidental replay/mutation on the local filesystem but does
NOT resist a privileged administrator or prove independent audit/timing.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from pathlib import Path

from resonance_world.c3r_g1_crossed_enrollment import _digest
from resonance_world.c3r_g1_crossed_plan import make_plan
from resonance_world.c3r_g1_crossed_receipt_bridge import verify_crossed_receipt_chain

_SCHEMA = "c3r-g1-crossed-internal-source-lock-v0.1"
_FIELDS = frozenset({
    "schema", "run_id", "plan_digest", "evaluator_public_key_hex",
    "source_chain_head_sha256", "source_receipts_sha256", "source_attempts",
    "independent_custody_attested", "trusted_timestamp_attested",
    "provider_sends_authorized", "scientific_acceptance",
})
_HEX = re.compile(r"[0-9a-f]{64}\Z")
_MAX_LOCK_BYTES = 2048


def _lock_path(directory: Path, run_id: str) -> Path:
    if not isinstance(run_id, str) or not run_id or len(run_id) > 256:
        raise ValueError("nonempty bounded internal run identifier required")
    if not directory.is_absolute() or directory.is_symlink():
        raise ValueError("internal source lock directory must be absolute and not symlinked")
    info = directory.stat()
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid()
            or info.st_mode & 0o077):
        raise ValueError("internal source lock directory must be private and owned")
    return directory / (hashlib.sha256(run_id.encode("utf-8")).hexdigest() + ".json")


def _expected(
    *, run_id: str, evaluator_public_key_hex: str,
    source_receipts: tuple[dict[str, object], ...],
) -> dict[str, object]:
    if (not isinstance(evaluator_public_key_hex, str)
            or _HEX.fullmatch(evaluator_public_key_hex) is None):
        raise ValueError("invalid internally pinned evaluator key")
    verified = verify_crossed_receipt_chain(
        make_plan(), receipts=source_receipts, mode="development",
        expected_run_id=run_id,
        pinned_evaluator_public_key_hex=evaluator_public_key_hex,
    )
    return {
        "schema": _SCHEMA,
        "run_id": run_id,
        "plan_digest": make_plan().public_digest,
        "evaluator_public_key_hex": evaluator_public_key_hex,
        "source_chain_head_sha256": verified.source_chain_head_sha256,
        "source_receipts_sha256": _digest(source_receipts),
        "source_attempts": 16,
        "independent_custody_attested": False,
        "trusted_timestamp_attested": False,
        "provider_sends_authorized": False,
        "scientific_acceptance": False,
    }


def write_internal_source_lock(
    *, directory: Path, run_id: str, evaluator_public_key_hex: str,
    source_receipts: tuple[dict[str, object], ...],
) -> tuple[dict[str, object], str]:
    """Exclusive durable local commit. Any existing lock fails closed.

    A crash during the write leaves the run unusable rather than allowing
    overwrite; rerun with a new run ID after investigating the failure.
    """
    path = _lock_path(directory, run_id)
    record = _expected(
        run_id=run_id, evaluator_public_key_hex=evaluator_public_key_hex,
        source_receipts=source_receipts,
    )
    data = json.dumps(record, sort_keys=True, separators=(",", ":")).encode() + b"\n"
    if len(data) > _MAX_LOCK_BYTES:
        raise ValueError("internal source checkpoint exceeds size limit")
    fd = os.open(
        path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
    finally:
        # fdopen owns/ closes fd even when its write/fsync raises.
        pass
    dfd = os.open(directory, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(dfd)
    finally:
        os.close(dfd)
    return record, _digest(record)


def verify_internal_source_lock(
    *, directory: Path, run_id: str, evaluator_public_key_hex: str,
    source_receipts: tuple[dict[str, object], ...],
    expected_lock_sha256: str,
) -> dict[str, object]:
    """Reconcile signed source and pre-existing local lock before/after holdout."""
    path = _lock_path(directory, run_id)
    if not isinstance(expected_lock_sha256, str) or _HEX.fullmatch(
        expected_lock_sha256
    ) is None:
        raise ValueError("internal source lock SHA256 pin missing")
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
                or info.st_mode & 0o077 or info.st_size > _MAX_LOCK_BYTES):
            raise ValueError("internal source checkpoint file is unsafe")
        with os.fdopen(fd, "rb") as stream:
            raw = stream.read(_MAX_LOCK_BYTES + 1)
    finally:
        pass
    if len(raw) > _MAX_LOCK_BYTES:
        raise ValueError("oversized internal source checkpoint")
    record = json.loads(raw)
    expected = _expected(
        run_id=run_id, evaluator_public_key_hex=evaluator_public_key_hex,
        source_receipts=source_receipts,
    )
    if (not isinstance(record, dict) or set(record) != _FIELDS
            or record != expected or _digest(record) != expected_lock_sha256):
        raise ValueError("internal source lock diverges from frozen signed evidence")
    return {
        "schema": "c3r-g1-crossed-internal-lock-audit-v0.1",
        "source_signature_chain_verified": True,
        "exclusive_local_source_lock_verified": True,
        "source_lock_sha256": expected_lock_sha256,
        "requires_external_approval": False,
        "independent_custody_attested": False,
        "trusted_timestamp_attested": False,
        "provider_sends": 0,
        "live_ready": False,
        "scientific_acceptance": False,
    }
