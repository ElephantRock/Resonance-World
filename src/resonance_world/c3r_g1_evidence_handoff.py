"""Portable G1 public-key-verifiable evidence handoff, not external custody.

Exports only an already-verified signed journal + a checksum manifest.
No witness or evaluator private keys are opened. Copying to a local folder
never satisfies third-party WORM retention, timestamp, or non-equivocation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
from dataclasses import dataclass
from pathlib import Path

from .c3r_g1_multischema import PublicCohort, V2Design
from .c3r_g1_witness_journal import audit_witness_journal
from .c3r_g1_witnessed_lock import _parse_clock

MAX_JOURNAL_BYTES = 5 * 1024 * 1024
JOURNAL_NAME = "signed-evaluator-journal.jsonl"
MANIFEST_NAME = "handoff-manifest.json"


def _canonical(data: object) -> bytes:
    return json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@dataclass(frozen=True, slots=True)
class HandoffVerification:
    verdict: str
    reason: str

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": "c3r-g1-evidence-handoff-verdict-v0.1",
            "verdict": self.verdict,
            "reason": self.reason,
            "external_custodian_receipt_verified": False,
            "trusted_timestamp_verified": False,
            "independent_grader_attested": False,
            "scientific_acceptance": False,
        }


def _read_journal(path: Path, cohort: PublicCohort) -> tuple[bytes, list[dict]]:
    if path.is_symlink() or not path.is_file():
        raise ValueError("evidence source must be a regular nonsymlink file")
    if path.stat().st_size > MAX_JOURNAL_BYTES:
        raise ValueError("evidence journal exceeds hard cap")
    data = path.read_bytes()
    if len(data) > MAX_JOURNAL_BYTES:
        raise ValueError("evidence journal grew beyond hard cap")
    lines = data.splitlines(keepends=True)
    if (len(lines) != cohort.design.logical_calls + 3
            or not lines or any(not line.endswith(b"\n") for line in lines)):
        raise ValueError("evidence journal line count or termination differs from lock")
    try:
        events = [json.loads(line) for line in lines]
    except (json.JSONDecodeError, UnicodeError) as exc:
        raise ValueError("evidence journal is not valid JSONL") from exc
    return data, events


def _audit_source(
    events: list[dict], cohort: PublicCohort, *,
    witness_public_hex: str, evaluator_public_hex: str,
    run_id: str, admission_utc: str,
) -> None:
    result = audit_witness_journal(
        events, cohort, witness_public_hex=witness_public_hex,
        evaluator_public_hex=evaluator_public_hex, run_id=run_id,
        now_utc=_parse_clock(admission_utc),
    )
    if result.verdict != "signed_structural_chain":
        raise ValueError("signed evidence journal failed prospective public-key audit")


def _safe_write(directory: Path, name: str, data: bytes) -> None:
    path = directory / name
    fd = os.open(
        path, os.O_WRONLY | os.O_EXCL | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    try:
        remainder = memoryview(data)
        while remainder:
            written = os.write(fd, remainder)
            if written <= 0:
                raise OSError("evidence handoff write incomplete")
            remainder = remainder[written:]
        os.fsync(fd)
    finally:
        os.close(fd)


def prepare_handoff(
    journal: Path, destination: Path, cohort: PublicCohort, *,
    witness_public_hex: str, evaluator_public_hex: str,
    run_id: str, admission_utc: str,
) -> dict[str, object]:
    raw, events = _read_journal(journal, cohort)
    _audit_source(
        events, cohort, witness_public_hex=witness_public_hex,
        evaluator_public_hex=evaluator_public_hex, run_id=run_id,
        admission_utc=admission_utc,
    )
    manifest: dict[str, object] = {
        "schema": "c3r-g1-evidence-handoff-v0.1",
        "state": "local_export_not_externally_deposited",
        "run_id": run_id,
        "public_cohort_digest": cohort.digest,
        "admission_time_used_for_audit": admission_utc,
        "journal_name": JOURNAL_NAME,
        "journal_sha256": _sha_bytes(raw),
        "journal_size_bytes": len(raw),
        "journal_signed_events": len(events),
        "enrollment_event_sha256": _sha_bytes(_canonical(events[0])),
        "final_event_sha256": _sha_bytes(_canonical(events[-1])),
        "witness_public_key_sha256": _sha_bytes(bytes.fromhex(witness_public_hex)),
        "evaluator_public_key_sha256": _sha_bytes(bytes.fromhex(evaluator_public_hex)),
        "external_custodian_receipt": None,
        "trusted_timestamp_verified": False,
        "scientific_acceptance": False,
    }
    if not destination.is_absolute() or destination.exists() or destination.is_symlink():
        raise ValueError("new absolute handoff destination directory is required")
    parent = destination.parent.stat()
    if (not stat.S_ISDIR(parent.st_mode)
            or parent.st_uid != os.geteuid()
            or parent.st_mode & 0o077):
        raise ValueError("handoff destination parent must be private and owner-controlled")
    destination.mkdir(mode=0o700)
    _safe_write(destination, JOURNAL_NAME, raw)
    _safe_write(destination, MANIFEST_NAME, _canonical(manifest) + b"\n")
    dir_fd = os.open(destination, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(dir_fd)
    finally:
        os.close(dir_fd)
    return manifest


def verify_handoff(
    destination: Path, cohort: PublicCohort, *,
    witness_public_hex: str, evaluator_public_hex: str,
    run_id: str, admission_utc: str,
) -> HandoffVerification:
    try:
        if destination.is_symlink() or not destination.is_dir():
            raise ValueError("handoff directory missing or symlinked")
        if {item.name for item in destination.iterdir()} != {
            JOURNAL_NAME, MANIFEST_NAME,
        }:
            raise ValueError("handoff has missing or unexpected files")
        manifest_path = destination / MANIFEST_NAME
        if (manifest_path.is_symlink() or
                manifest_path.stat().st_size > 4096):
            raise ValueError("manifest missing or too large")
        manifest = json.loads(manifest_path.read_bytes())
        if not isinstance(manifest, dict):
            raise ValueError("invalid handoff manifest")
        raw, events = _read_journal(destination / JOURNAL_NAME, cohort)
        _audit_source(
            events, cohort, witness_public_hex=witness_public_hex,
            evaluator_public_hex=evaluator_public_hex, run_id=run_id,
            admission_utc=admission_utc,
        )
        # Recompute expected exact manifest. Never trust self-declared hashes.
        expected = {
            "schema": "c3r-g1-evidence-handoff-v0.1",
            "state": "local_export_not_externally_deposited",
            "run_id": run_id,
            "public_cohort_digest": cohort.digest,
            "admission_time_used_for_audit": admission_utc,
            "journal_name": JOURNAL_NAME,
            "journal_sha256": _sha_bytes(raw),
            "journal_size_bytes": len(raw),
            "journal_signed_events": len(events),
            "enrollment_event_sha256": _sha_bytes(_canonical(events[0])),
            "final_event_sha256": _sha_bytes(_canonical(events[-1])),
            "witness_public_key_sha256": _sha_bytes(bytes.fromhex(witness_public_hex)),
            "evaluator_public_key_sha256": _sha_bytes(bytes.fromhex(evaluator_public_hex)),
            "external_custodian_receipt": None,
            "trusted_timestamp_verified": False,
            "scientific_acceptance": False,
        }
        if manifest != expected:
            raise ValueError("handoff manifest does not match verified evidence")
    except (OSError, ValueError, TypeError, KeyError, UnicodeError):
        return HandoffVerification("rejected", "invalid_or_unmatched_handoff")
    return HandoffVerification("public_key_verified_not_external_custody", "none")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Prepare or inspect public-key-verifiable C3R evidence handoff"
    )
    parser.add_argument("operation", choices=("prepare", "verify"))
    parser.add_argument("path", type=Path, help="source journal or prepared directory")
    parser.add_argument("--destination", type=Path)
    parser.add_argument("--witness-public", type=Path, required=True)
    parser.add_argument("--evaluator-public", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--admission-utc", required=True)
    parser.add_argument("--units", type=int, default=8)
    parser.add_argument("--development", type=int, default=6)
    parser.add_argument("--qualification", type=int, default=8)
    parser.add_argument("--public-seed", type=int, default=20261022)
    parser.add_argument("--model-id", default="offline-schema-fixture")
    args = parser.parse_args(argv)
    try:
        if (args.witness_public.stat().st_size > 128
                or args.evaluator_public.stat().st_size > 128):
            raise ValueError("public key files exceed cap")
        witness = args.witness_public.read_text(encoding="ascii").strip()
        evaluator = args.evaluator_public.read_text(encoding="ascii").strip()
        cohort = V2Design(
            units=args.units,
            development_per_family=args.development,
            qualification_per_family=args.qualification,
            public_seed=args.public_seed,
            model_id=args.model_id,
        ).freeze()
        if args.operation == "prepare":
            if args.destination is None:
                raise ValueError("--destination required for prepare")
            prepare_handoff(
                args.path, args.destination, cohort,
                witness_public_hex=witness, evaluator_public_hex=evaluator,
                run_id=args.run_id, admission_utc=args.admission_utc,
            )
            result = HandoffVerification(
                "prepared_locally_not_external_custody", "none"
            )
        elif args.destination is not None:
            raise ValueError("--destination is invalid for verify")
        else:
            result = verify_handoff(
                args.path, cohort, witness_public_hex=witness,
                evaluator_public_hex=evaluator, run_id=args.run_id,
                admission_utc=args.admission_utc,
            )
    except (OSError, ValueError, TypeError, KeyError, UnicodeError):
        result = HandoffVerification("rejected", "invalid_or_unmatched_handoff")
    print(json.dumps(result.to_dict(), sort_keys=True, separators=(",", ":")))
    return 2 if result.verdict == "rejected" else 0


if __name__ == "__main__":
    raise SystemExit(main())
