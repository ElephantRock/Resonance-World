"""Detached, publicly verifiable custodian receipt for a G1 evidence bundle.

This is an OFFLINE local custody simulator. It copies an authenticated bundle
under a separate directory and signs its precise archived bytes. Neither a
valid signature nor a successful filesystem copy proves independent operator
control, external timestamps, WORM retention, or scientific correctness.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from .c3r_g1_evaluator_receipts import _valid_run_id
from .c3r_g1_evidence_handoff import (
    JOURNAL_NAME,
    MANIFEST_NAME,
    verify_handoff,
)
from .c3r_g1_multischema import PublicCohort, V2Design
from .c3r_g1_witnessed_lock import _parse_clock

RECEIPT_NAME = "detached-custodian-receipt.json"
ARCHIVE_DIR = "bundle"
RECEIPT_FIELDS = frozenset({
    "schema", "status", "custodian_id", "run_id",
    "public_cohort_digest", "archive_reference",
    "manifest_sha256", "journal_sha256",
    "enrollment_event_sha256", "final_event_sha256",
    "witness_public_key_sha256", "evaluator_public_key_sha256",
    "custodian_public_key_sha256", "claimed_received_at_utc",
    "immutable_retention_verified", "trusted_timestamp_verified",
    "independent_operator_verified", "scientific_acceptance",
    "signature",
})


def _canon(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _matches_hex(value: object, size: int) -> bool:
    return isinstance(value, str) and re.fullmatch(
        rf"[0-9a-f]{{{size}}}", value
    ) is not None


def _read(path: Path, max_size: int) -> bytes:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > max_size:
        raise ValueError("missing, oversized or redirected custody artifact")
    data = path.read_bytes()
    if len(data) > max_size:
        raise ValueError("custody artifact exceeded size limit")
    return data


def _write_once(path: Path, data: bytes) -> None:
    fd = os.open(
        path, os.O_WRONLY | os.O_CREAT | os.O_EXCL
        | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    try:
        pending = memoryview(data)
        while pending:
            n = os.write(fd, pending)
            if n <= 0:
                raise OSError("custodian fixture failed to write complete file")
            pending = pending[n:]
        os.fsync(fd)
    finally:
        os.close(fd)


def _sync_dir(directory: Path) -> None:
    fd = os.open(directory, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _private_dir(path: Path) -> None:
    if (not path.is_absolute() or path.is_symlink() or not path.is_dir()
            or path.stat().st_uid != os.geteuid()
            or path.stat().st_mode & 0o077):
        raise ValueError("custodian inbox must be absolute, owner-held and private")


def _archive_id(run_id: str) -> str:
    if not _valid_run_id(run_id):
        raise ValueError("invalid custodian run identifier")
    return _sha(run_id.encode("utf-8"))


@dataclass(frozen=True, slots=True)
class CustodyCheck:
    verdict: str
    category: str

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": "c3r-g1-custodian-receipt-audit-v0.1",
            "verdict": self.verdict,
            "category": self.category,
            "signature_and_archive_match": (
                self.verdict == "signed_local_archive_consistent_unattested"
            ),
            "independent_operator_attested": False,
            "external_deposit_attested": False,
            "trusted_timestamp_verified": False,
            "immutable_retention_verified": False,
            "private_grading_truth_verified": False,
            "provider_billing_verified": False,
            "scientific_acceptance": False,
        }


class LocalCustodianFixture:
    """Offline separately-keyed archive simulator. NOT external custody."""

    def __init__(self, directory: Path, *, custodian_seed: bytes,
                 custodian_id: str) -> None:
        _private_dir(directory)
        if not isinstance(custodian_seed, bytes) or len(custodian_seed) != 32:
            raise ValueError("local custodian seed must be exactly 32 bytes")
        if not isinstance(custodian_id, str) or re.fullmatch(
            r"[a-zA-Z0-9][a-zA-Z0-9_.-]{7,79}", custodian_id
        ) is None:
            raise ValueError("custodian identity must be bounded and explicit")
        self._directory = directory
        self._key = Ed25519PrivateKey.from_private_bytes(custodian_seed)
        self.custodian_id = custodian_id
        self.public_hex = self._key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        ).hex()

    def receive(
        self, bundle: Path, cohort: PublicCohort, *,
        witness_public_hex: str, evaluator_public_hex: str,
        run_id: str, admission_utc: str, claimed_received_at_utc: str,
    ) -> Path:
        if len({self.public_hex, witness_public_hex, evaluator_public_hex}) != 3:
            raise ValueError("custodian, witness and evaluator must use distinct keys")
        # Do not create even an archive directory for invalid source evidence.
        if verify_handoff(
            bundle, cohort, witness_public_hex=witness_public_hex,
            evaluator_public_hex=evaluator_public_hex, run_id=run_id,
            admission_utc=admission_utc,
        ).verdict != "public_key_verified_not_external_custody":
            raise ValueError("source bundle did not pass its public-key audit")
        issued = _parse_clock(claimed_received_at_utc)
        admitted = _parse_clock(admission_utc)
        if issued < admitted:
            raise ValueError("claimed receipt precedes caller-provided admission")
        reference = _archive_id(run_id)
        entry = self._directory / reference
        entry.mkdir(mode=0o700)  # no run-ID reuse, including a failed prior attempt
        archived = entry / ARCHIVE_DIR
        archived.mkdir(mode=0o700)
        manifest_bytes = _read(bundle / MANIFEST_NAME, 4096)
        journal_bytes = _read(bundle / JOURNAL_NAME, 5 * 1024 * 1024)
        _write_once(archived / MANIFEST_NAME, manifest_bytes)
        _write_once(archived / JOURNAL_NAME, journal_bytes)
        if verify_handoff(
            archived, cohort, witness_public_hex=witness_public_hex,
            evaluator_public_hex=evaluator_public_hex, run_id=run_id,
            admission_utc=admission_utc,
        ).verdict != "public_key_verified_not_external_custody":
            raise ValueError("archived bytes failed re-verification")
        manifest = json.loads(manifest_bytes)
        body: dict[str, object] = {
            "schema": "c3r-g1-custodian-receipt-v0.1",
            "status": "local_custodian_fixture_not_external_custody",
            "custodian_id": self.custodian_id,
            "run_id": run_id,
            "public_cohort_digest": cohort.digest,
            "archive_reference": reference,
            "manifest_sha256": _sha(manifest_bytes),
            "journal_sha256": _sha(journal_bytes),
            "enrollment_event_sha256": manifest["enrollment_event_sha256"],
            "final_event_sha256": manifest["final_event_sha256"],
            "witness_public_key_sha256": _sha(bytes.fromhex(witness_public_hex)),
            "evaluator_public_key_sha256": _sha(bytes.fromhex(evaluator_public_hex)),
            "custodian_public_key_sha256": _sha(bytes.fromhex(self.public_hex)),
            "claimed_received_at_utc": claimed_received_at_utc,
            "immutable_retention_verified": False,
            "trusted_timestamp_verified": False,
            "independent_operator_verified": False,
            "scientific_acceptance": False,
        }
        signed = {**body, "signature": self._key.sign(_canon(body)).hex()}
        _write_once(entry / RECEIPT_NAME, _canon(signed) + b"\n")
        _sync_dir(archived)
        _sync_dir(entry)
        _sync_dir(self._directory)
        return entry


def verify_custodian_receipt(
    entry: Path, cohort: PublicCohort, *,
    witness_public_hex: str, evaluator_public_hex: str,
    custodian_public_hex: str, expected_custodian_id: str,
    run_id: str, admission_utc: str,
) -> CustodyCheck:
    try:
        if len({custodian_public_hex, witness_public_hex, evaluator_public_hex}) != 3:
            raise ValueError("custodian role must use a distinct pinned key")
        if entry.is_symlink() or not entry.is_dir() or {
            path.name for path in entry.iterdir()
        } != {ARCHIVE_DIR, RECEIPT_NAME}:
            raise ValueError("custodian entry missing or modified")
        archive = entry / ARCHIVE_DIR
        if verify_handoff(
            archive, cohort, witness_public_hex=witness_public_hex,
            evaluator_public_hex=evaluator_public_hex, run_id=run_id,
            admission_utc=admission_utc,
        ).verdict != "public_key_verified_not_external_custody":
            raise ValueError("archived journal/manifest failed independent audit")
        data = json.loads(_read(entry / RECEIPT_NAME, 4096))
        if not isinstance(data, dict) or set(data) != RECEIPT_FIELDS:
            raise ValueError("receipt fields differ from strict contract")
        if not _matches_hex(custodian_public_hex, 64):
            raise ValueError("untrusted or invalid custodian public key")
        if not _matches_hex(data["signature"], 128):
            raise ValueError("receipt signature malformed")
        manifest_bytes = _read(archive / MANIFEST_NAME, 4096)
        journal_bytes = _read(archive / JOURNAL_NAME, 5 * 1024 * 1024)
        manifest = json.loads(manifest_bytes)
        received = _parse_clock(data["claimed_received_at_utc"])
        if received < _parse_clock(admission_utc):
            raise ValueError("receipt claims to precede admission")
        expected = {
            "schema": "c3r-g1-custodian-receipt-v0.1",
            "status": "local_custodian_fixture_not_external_custody",
            "custodian_id": expected_custodian_id,
            "run_id": run_id,
            "public_cohort_digest": cohort.digest,
            "archive_reference": _archive_id(run_id),
            "manifest_sha256": _sha(manifest_bytes),
            "journal_sha256": _sha(journal_bytes),
            "enrollment_event_sha256": manifest["enrollment_event_sha256"],
            "final_event_sha256": manifest["final_event_sha256"],
            "witness_public_key_sha256": _sha(bytes.fromhex(witness_public_hex)),
            "evaluator_public_key_sha256": _sha(bytes.fromhex(evaluator_public_hex)),
            "custodian_public_key_sha256": _sha(bytes.fromhex(custodian_public_hex)),
            "claimed_received_at_utc": data["claimed_received_at_utc"],
            "immutable_retention_verified": False,
            "trusted_timestamp_verified": False,
            "independent_operator_verified": False,
            "scientific_acceptance": False,
        }
        if {k: v for k, v in data.items() if k != "signature"} != expected:
            raise ValueError("receipt binds different archive or operator")
        key = Ed25519PublicKey.from_public_bytes(bytes.fromhex(custodian_public_hex))
        key.verify(bytes.fromhex(data["signature"]), _canon(expected))
    except (OSError, ValueError, TypeError, KeyError, InvalidSignature, UnicodeError):
        return CustodyCheck("rejected", "receipt_archive_or_authority_invalid")
    return CustodyCheck("signed_local_archive_consistent_unattested", "none")


def main(argv: list[str] | None = None) -> int:
    """Offline verification ONLY; never expose a private-key signing CLI."""
    parser = argparse.ArgumentParser(description="Audit detached local custodian receipt")
    parser.add_argument("entry", type=Path)
    parser.add_argument("--witness-public", type=Path, required=True)
    parser.add_argument("--evaluator-public", type=Path, required=True)
    parser.add_argument("--custodian-public", type=Path, required=True)
    parser.add_argument("--custodian-id", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--admission-utc", required=True)
    parser.add_argument("--units", type=int, default=8)
    parser.add_argument("--development", type=int, default=6)
    parser.add_argument("--qualification", type=int, default=8)
    parser.add_argument("--public-seed", type=int, default=20261022)
    parser.add_argument("--model-id", default="offline-schema-fixture")
    args = parser.parse_args(argv)
    try:
        paths = [args.witness_public, args.evaluator_public, args.custodian_public]
        if any(p.is_symlink() or p.stat().st_size > 128 for p in paths):
            raise ValueError("untrusted public key file")
        keys = [p.read_text(encoding="ascii").strip() for p in paths]
        cohort = V2Design(
            units=args.units, development_per_family=args.development,
            qualification_per_family=args.qualification,
            public_seed=args.public_seed, model_id=args.model_id,
        ).freeze()
        outcome = verify_custodian_receipt(
            args.entry, cohort, witness_public_hex=keys[0],
            evaluator_public_hex=keys[1], custodian_public_hex=keys[2],
            expected_custodian_id=args.custodian_id,
            run_id=args.run_id, admission_utc=args.admission_utc,
        )
    except (OSError, ValueError, TypeError, UnicodeError):
        outcome = CustodyCheck("rejected", "invalid_verifier_input")
    print(json.dumps(outcome.to_dict(), sort_keys=True, separators=(",", ":")))
    return 0 if outcome.verdict == "signed_local_archive_consistent_unattested" else 2


if __name__ == "__main__":
    raise SystemExit(main())
