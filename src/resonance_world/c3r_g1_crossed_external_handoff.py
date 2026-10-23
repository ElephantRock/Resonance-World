"""Read-only source/terminal handoff auditor for externally pinned archive keys.

This module *never* signs or transmits evidence and never reads secrets.
A valid archive signature does not establish who owns the signing key, when
its receipt was genuinely issued, what was durably stored, or G1 acceptance.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal

from resonance_world.c3r_g1_crossed_enrollment import EnrollmentPin, _digest, _utc
from resonance_world.c3r_g1_crossed_plan import make_plan
from resonance_world.c3r_g1_crossed_receipt_bridge import verify_crossed_receipt_chain
from resonance_world.c3r_g1_crossed_witness_checkpoint import verify_witness_checkpoint
from resonance_world.c3r_g1_evaluator_receipts import ReceiptVerifier

Mode = Literal["source", "terminal"]
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_SOURCE_KEYS = frozenset({
    "schema", "enrollment", "source_receipts", "custodian_deposit",
    "witness_checkpoint", "archive_receipt",
})
_ARCHIVE_KEYS = frozenset({
    "schema", "manifest_sha256", "source_chain_head_sha256",
    "witness_checkpoint_sha256", "source_attempts", "claimed_received_at_utc",
    "independent_archive_custody_attested", "trusted_timestamp_attested",
    "immutable_remote_retention_attested", "scientific_acceptance",
})
_MAX_BUNDLE_BYTES = 512 * 1024


@dataclass(frozen=True, slots=True)
class CrossedExternalHandoffAudit:
    """Cryptographic checks only; no externally witnessed timing or custody."""

    archive_receipt_sha256: str
    manifest_sha256: str
    source_chain_head_sha256: str
    witness_checkpoint_sha256: str
    verified_logical_attempts: int
    mode: Mode

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": "c3r-g1-crossed-external-handoff-audit-v0.1",
            "mode": self.mode,
            "archive_receipt_sha256": self.archive_receipt_sha256,
            "source_manifest_sha256": self.manifest_sha256,
            "source_chain_head_sha256": self.source_chain_head_sha256,
            "witness_checkpoint_sha256": self.witness_checkpoint_sha256,
            "verified_logical_attempts": self.verified_logical_attempts,
            "source_manifest_signature_and_lineage_checked": True,
            "archive_signature_verified_against_supplied_pin": True,
            "archive_receipt_reused_from_prior_source_verification": (
                self.mode == "terminal"
            ),
            "external_archive_key_ownership_attested": False,
            "trusted_timestamp_attested": False,
            "remote_content_retention_verified": False,
            "source_received_before_real_holdout_attested": False,
            "provider_execution_verified": False,
            "private_grade_correctness_independently_attested": False,
            "live_ready": False,
            "scientific_acceptance": False,
            "verdict": "signed_offline_handoff_structural_only",
        }


def _parse_bundle(bundle: object, mode: Mode) -> dict[str, object]:
    if mode not in ("source", "terminal"):
        raise ValueError("unknown handoff stage")
    if not isinstance(bundle, dict):
        raise ValueError("handoff must be a JSON object")
    expected = _SOURCE_KEYS | ({"terminal_receipts"} if mode == "terminal" else set())
    if set(bundle) != expected or bundle["schema"] != "c3r-g1-crossed-handoff-v0.1":
        raise ValueError("handoff stage schema has missing or unexpected fields")
    try:
        if len(json.dumps(bundle, sort_keys=True)) > _MAX_BUNDLE_BYTES:
            raise ValueError("evidence bundle exceeds offline handoff limit")
    except (TypeError, OverflowError) as exc:
        raise ValueError("handoff contains non-JSON data") from exc
    if (not isinstance(bundle["source_receipts"], list)
            or not all(isinstance(v, dict) for v in bundle["source_receipts"])):
        raise ValueError("signed source receipts must be an array of objects")
    if mode == "terminal" and (
        not isinstance(bundle["terminal_receipts"], list)
        or not all(isinstance(v, dict) for v in bundle["terminal_receipts"])
    ):
        raise ValueError("terminal receipts must be an array of objects")
    return bundle


def verify_external_handoff(
    bundle: object,
    *,
    mode: Mode,
    expected_run_id: str,
    pinned_evaluator_public_key_hex: str,
    pinned_custodian_public_key_hex: str,
    pinned_witness_public_key_hex: str,
    pinned_archive_public_key_hex: str,
    claimed_clock_check_utc: datetime,
    expected_prior_archive_receipt_sha256: str | None = None,
) -> CrossedExternalHandoffAudit:
    """Validate a handoff source snapshot and optionally its final transcript.

    The source audit returns a digest that the operator MUST deposit with an
    independent archive before any holdout. Terminal audit requires that
    digest as an external, out-of-band pin. This module cannot establish that
    any operator complied with that requirement.
    """
    data = _parse_bundle(bundle, mode)
    public_keys = (
        pinned_evaluator_public_key_hex, pinned_custodian_public_key_hex,
        pinned_witness_public_key_hex, pinned_archive_public_key_hex,
    )
    if (any(not isinstance(k, str) or _SHA.fullmatch(k) is None for k in public_keys)
            or len(set(public_keys)) != 4):
        raise ValueError("four separately pinned public keys must be distinct")
    if (not isinstance(claimed_clock_check_utc, datetime)
            or claimed_clock_check_utc.tzinfo is None
            or claimed_clock_check_utc.utcoffset() != timedelta()):
        raise ValueError("claimed clock check must use timezone-aware UTC")
    if (mode == "terminal" and (
        not isinstance(expected_prior_archive_receipt_sha256, str)
        or _SHA.fullmatch(expected_prior_archive_receipt_sha256) is None
    )):
        raise ValueError("terminal verification requires previously retained archive pin")
    if mode == "source" and expected_prior_archive_receipt_sha256 is not None:
        raise ValueError("source stage must generate rather than consume archive pin")

    pin = EnrollmentPin.verify(
        data["enrollment"],
        pinned_witness_public_key_hex=pinned_witness_public_key_hex,
        expected_run_id=expected_run_id,
        expected_evaluator_public_key_hex=pinned_evaluator_public_key_hex,
        expected_custodian_public_key_hex=pinned_custodian_public_key_hex,
        claimed_clock_check_utc=claimed_clock_check_utc,
    )
    sources = tuple(data["source_receipts"])
    verified = verify_crossed_receipt_chain(
        make_plan(), receipts=sources, mode="development",
        expected_run_id=expected_run_id,
        pinned_evaluator_public_key_hex=pinned_evaluator_public_key_hex,
    )
    checkpoint = verify_witness_checkpoint(
        pin, signed_enrollment=data["enrollment"],
        signed_checkpoint=data["witness_checkpoint"],
        signed_custodian_deposit=data["custodian_deposit"],
        source_chain_head_sha256=verified.source_chain_head_sha256,
        claimed_clock_check_utc=claimed_clock_check_utc,
    )
    source_manifest = {
        "schema": "c3r-g1-crossed-source-manifest-v0.1",
        "run_id": expected_run_id,
        "plan_digest": pin.public_plan_digest,
        "enrollment_sha256": pin.signed_enrollment_sha256,
        "source_receipts_sha256": _digest(data["source_receipts"]),
        "source_chain_head_sha256": verified.source_chain_head_sha256,
        "custodian_deposit_sha256": checkpoint.custodian_receipt_sha256,
        "witness_checkpoint_sha256": checkpoint.witness_checkpoint_sha256,
    }
    manifest_sha = _digest(source_manifest)
    archive_payload = ReceiptVerifier(
        pinned_archive_public_key_hex, expected_run_id=expected_run_id,
    ).verify_next(data["archive_receipt"])
    if set(archive_payload) != _ARCHIVE_KEYS:
        raise ValueError("archive receipt has missing or unexpected fields")
    expected = {
        "schema": "c3r-g1-crossed-archive-receipt-v0.1",
        "manifest_sha256": manifest_sha,
        "source_chain_head_sha256": verified.source_chain_head_sha256,
        "witness_checkpoint_sha256": checkpoint.witness_checkpoint_sha256,
        "source_attempts": 16,
        "independent_archive_custody_attested": False,
        "trusted_timestamp_attested": False,
        "immutable_remote_retention_attested": False,
        "scientific_acceptance": False,
    }
    if any(archive_payload.get(k) != v or type(archive_payload.get(k)) is not type(v)
           for k, v in expected.items()):
        raise ValueError("archive signature does not bind the sealed source manifest")
    claimed_received = _utc(archive_payload["claimed_received_at_utc"])
    claimed_checkpoint = _utc(data["witness_checkpoint"]["payload"][
        "claimed_checkpoint_at_utc"
    ])
    claimed_expiry = _utc(data["enrollment"]["payload"]["claimed_expires_at_utc"])
    if not claimed_checkpoint <= claimed_received <= claimed_clock_check_utc <= claimed_expiry:
        raise ValueError("claimed archive receipt chronology contradicts enrollment")
    archive_sha = _digest(data["archive_receipt"])
    if mode == "terminal":
        if archive_sha != expected_prior_archive_receipt_sha256:
            raise ValueError("archive snapshot changed since independently pinned source")
        terminal = tuple(data["terminal_receipts"])
        if terminal[:16] != sources:
            raise ValueError("terminal source prefix differs from archived source snapshot")
        checked = verify_crossed_receipt_chain(
            make_plan(), receipts=terminal, mode="terminal",
            expected_run_id=expected_run_id,
            pinned_evaluator_public_key_hex=pinned_evaluator_public_key_hex,
            expected_source_chain_head_sha256=verified.source_chain_head_sha256,
        )
        logical = len(checked.outcomes or ())
    else:
        logical = len(verified.sources or ())
    return CrossedExternalHandoffAudit(
        archive_receipt_sha256=archive_sha,
        manifest_sha256=manifest_sha,
        source_chain_head_sha256=verified.source_chain_head_sha256,
        witness_checkpoint_sha256=checkpoint.witness_checkpoint_sha256,
        verified_logical_attempts=logical,
        mode=mode,
    )


def main(argv: list[str] | None = None) -> int:
    """Offline verifier CLI accepts public pins; it cannot issue any receipt."""
    parser = argparse.ArgumentParser(description="Read-only crossed G1 evidence handoff")
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--mode", choices=("source", "terminal"), required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--evaluator-public-key-hex", required=True)
    parser.add_argument("--custodian-public-key-hex", required=True)
    parser.add_argument("--witness-public-key-hex", required=True)
    parser.add_argument("--archive-public-key-hex", required=True)
    parser.add_argument("--previous-archive-receipt-sha256")
    args = parser.parse_args(argv)
    try:
        if args.bundle.is_symlink() or args.bundle.stat().st_size > _MAX_BUNDLE_BYTES:
            raise ValueError("oversized or redirected evidence file")
        payload = json.loads(args.bundle.read_text(encoding="utf-8"))
        report = verify_external_handoff(
            payload, mode=args.mode, expected_run_id=args.run_id,
            pinned_evaluator_public_key_hex=args.evaluator_public_key_hex,
            pinned_custodian_public_key_hex=args.custodian_public_key_hex,
            pinned_witness_public_key_hex=args.witness_public_key_hex,
            pinned_archive_public_key_hex=args.archive_public_key_hex,
            claimed_clock_check_utc=datetime.now(UTC),
            expected_prior_archive_receipt_sha256=args.previous_archive_receipt_sha256,
        )
        print(json.dumps(report.to_dict(), sort_keys=True))
        return 0
    except (OSError, ValueError, TypeError, KeyError, UnicodeError, OverflowError):
        print(json.dumps({
            "schema": "c3r-g1-crossed-external-handoff-audit-v0.1",
            "verdict": "rejected_unverified_evidence",
            "scientific_acceptance": False,
        }, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
