"""Candidate source-chain custody for crossed G1; offline only.

Signatures, local storage and O_EXCL do not attest independent operators,
trusted time or genuine external write-once retention.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
from pathlib import Path

from resonance_world.c3r_g1_crossed_plan import make_plan
from resonance_world.c3r_g1_crossed_receipt_bridge import verify_crossed_receipt_chain
from resonance_world.c3r_g1_evaluator_receipts import ReceiptSigner, ReceiptVerifier

_SCHEMA = "c3r-g1-crossed-source-custody-v0.1"
_FIELDS = frozenset({
    "schema", "plan_digest", "source_chain_head_sha256", "evaluator_public_key_sha256",
    "source_receipt_count", "independent_custody_attested", "trusted_time_attested",
    "scientific_acceptance",
})
_HEX = re.compile(r"[0-9a-f]{64}\Z")


def read_private_seed(path: Path) -> bytes:
    """Reject non-regular, oversized and group/world-accessible key files."""
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077 or info.st_size > 65:
            raise ValueError("private signing seed file has unsafe permissions or size")
        data = os.read(fd, 66).strip()
    finally:
        os.close(fd)
    if re.fullmatch(rb"[0-9a-fA-F]{64}", data) is None:
        raise ValueError("private signing seed must be 32 bytes encoded as hex")
    return bytes.fromhex(data.decode("ascii"))


def _valid_storage(path: Path) -> None:
    if (not path.is_absolute() or path.is_symlink() or not path.is_dir()
            or path.stat().st_uid != os.geteuid()
            or path.stat().st_mode & 0o077):
        raise ValueError("custodian deposit directory must be absolute, private and owned")


def verify_source_deposit(
    *, deposit: dict[str, object], source_head: str,
    expected_run_id: str, evaluator_public_key_hex: str,
    pinned_custodian_public_key_hex: str,
) -> dict[str, object]:
    """Check signed custody claim against independent supplied pin and source head."""
    if (not isinstance(source_head, str) or _HEX.fullmatch(source_head) is None
            or not isinstance(evaluator_public_key_hex, str)
            or _HEX.fullmatch(evaluator_public_key_hex) is None
            or not isinstance(pinned_custodian_public_key_hex, str)
            or _HEX.fullmatch(pinned_custodian_public_key_hex) is None
            or evaluator_public_key_hex == pinned_custodian_public_key_hex):
        raise ValueError("invalid or reused evaluator/custodian pins")
    payload = ReceiptVerifier(
        pinned_custodian_public_key_hex, expected_run_id=expected_run_id,
    ).verify_next(deposit)
    if not isinstance(payload, dict) or set(payload) != _FIELDS:
        raise ValueError("custodian signed payload fields invalid")
    expected = {
        "schema": _SCHEMA,
        "plan_digest": make_plan().public_digest,
        "source_chain_head_sha256": source_head,
        "evaluator_public_key_sha256": hashlib.sha256(
            bytes.fromhex(evaluator_public_key_hex)
        ).hexdigest(),
        "source_receipt_count": 16,
        "independent_custody_attested": False,
        "trusted_time_attested": False,
        "scientific_acceptance": False,
    }
    if payload != expected:
        raise ValueError("source custody receipt does not match sealed source")
    return {
        "schema": "c3r-g1-crossed-source-custody-audit-v0.1",
        "source_head_signed_by_pinned_candidate_custodian": True,
        "custodian_operator_independence_attested": False,
        "trusted_time_attested": False,
        "immutable_external_custody_attested": False,
        "physical_sends": 0,
        "scientific_acceptance": False,
    }


def deposit_source_receipts(
    *, source_receipts: tuple[dict[str, object], ...],
    expected_run_id: str, evaluator_public_key_hex: str,
    custodian_private_seed: bytes, destination: Path,
) -> tuple[dict[str, object], Path]:
    """Check sixteen signed source attempts, create one write-once local deposit."""
    _valid_storage(destination)
    checked = verify_crossed_receipt_chain(
        make_plan(), receipts=source_receipts, mode="development",
        expected_run_id=expected_run_id,
        pinned_evaluator_public_key_hex=evaluator_public_key_hex,
    )
    signer = ReceiptSigner(custodian_private_seed, run_id=expected_run_id)
    if signer.public_key_hex == evaluator_public_key_hex:
        raise ValueError("custodian key must differ from evaluator signer key")
    body = {
        "schema": _SCHEMA,
        "plan_digest": make_plan().public_digest,
        "source_chain_head_sha256": checked.source_chain_head_sha256,
        "evaluator_public_key_sha256": hashlib.sha256(
            bytes.fromhex(evaluator_public_key_hex)
        ).hexdigest(),
        "source_receipt_count": 16,
        "independent_custody_attested": False,
        "trusted_time_attested": False,
        "scientific_acceptance": False,
    }
    signed = signer.seal(body)
    verify_source_deposit(
        deposit=signed, source_head=checked.source_chain_head_sha256,
        expected_run_id=expected_run_id,
        evaluator_public_key_hex=evaluator_public_key_hex,
        pinned_custodian_public_key_hex=signer.public_key_hex,
    )
    name = hashlib.sha256(expected_run_id.encode("utf-8")).hexdigest() + ".json"
    location = destination / name
    raw = json.dumps(signed, sort_keys=True, separators=(",", ":")).encode() + b"\n"
    fd = os.open(
        location, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    try:
        remaining = memoryview(raw)
        while remaining:
            size = os.write(fd, remaining)
            if size <= 0:
                raise OSError("custodian deposit write was incomplete")
            remaining = remaining[size:]
        os.fsync(fd)
    finally:
        os.close(fd)
    dfd = os.open(destination, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(dfd)
    finally:
        os.close(dfd)
    return signed, location


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Offline crossed G1 candidate custodian")
    parser.add_argument("--source-receipts-file", type=Path, required=True)
    parser.add_argument("--evaluator-public-key-file", type=Path, required=True)
    parser.add_argument("--custodian-private-seed-file", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args(argv)
    try:
        if (args.source_receipts_file.is_symlink()
                or args.source_receipts_file.stat().st_size > 256 * 1024):
            raise ValueError("source receipt file is redirected or oversized")
        source = json.loads(args.source_receipts_file.read_text(encoding="utf-8"))
        if not isinstance(source, list):
            raise ValueError("source receipts must be an array")
        pub = args.evaluator_public_key_file.read_text(encoding="ascii").strip()
        signed, target = deposit_source_receipts(
            source_receipts=tuple(source), expected_run_id=args.run_id,
            evaluator_public_key_hex=pub,
            custodian_private_seed=read_private_seed(args.custodian_private_seed_file),
            destination=args.destination,
        )
        print(json.dumps({
            "status": "local_source_deposit_written_not_independent_custody",
            "receipt_path": str(target),
            "source_chain_head_sha256": signed["payload"]["source_chain_head_sha256"],
            "scientific_acceptance": False,
        }, sort_keys=True))
        return 0
    except (OSError, ValueError, TypeError, KeyError, UnicodeError):
        print(json.dumps({
            "status": "local_source_deposit_rejected", "scientific_acceptance": False,
        }, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
