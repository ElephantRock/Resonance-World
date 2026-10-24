"""Pre-source witness enrollment verification for crossed G1 (offline only).

Reuses existing Ed25519 ReceiptVerifier. Local signatures or clocks do not
attest independently governed witness keys, external custody or trusted time.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from resonance_world.c3r_g1_crossed_plan import make_plan
from resonance_world.c3r_g1_crossed_receipt_bridge import verify_crossed_receipt_chain
from resonance_world.c3r_g1_crossed_source_deposit import verify_source_deposit
from resonance_world.c3r_g1_evaluator_receipts import ReceiptVerifier

_FIELDS = frozenset({
    "schema", "plan_digest", "evaluator_public_key_hex",
    "custodian_public_key_hex", "development_attempts", "qualification_attempts",
    "claimed_issued_at_utc", "claimed_expires_at_utc",
    "provider_sends_authorized", "external_witness_attested",
    "trusted_timestamp_attested", "scientific_acceptance",
})
_KEY = re.compile(r"[0-9a-f]{64}\Z")
_TIME = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\Z")


def _utc(value: object) -> datetime:
    if not isinstance(value, str) or _TIME.fullmatch(value) is None:
        raise ValueError("enrollment time must be UTC seconds format")
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    except ValueError as exc:
        raise ValueError("invalid claimed enrollment clock") from exc


def _digest(value: object) -> str:
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class EnrollmentPin:
    """Read-only admission record; never promotes local witness to independent."""

    public_plan_digest: str
    run_id: str
    evaluator_public_key_hex: str
    custodian_public_key_hex: str
    witness_public_key_hex: str
    signed_enrollment_sha256: str

    @classmethod
    def verify(
        cls, enrollment: dict[str, object], *,
        pinned_witness_public_key_hex: str,
        expected_run_id: str,
        expected_evaluator_public_key_hex: str,
        expected_custodian_public_key_hex: str,
        claimed_clock_check_utc: datetime,
    ) -> EnrollmentPin:
        """Require a separately supplied witness key and frozen run/role pins."""
        keys = (
            pinned_witness_public_key_hex, expected_evaluator_public_key_hex,
            expected_custodian_public_key_hex,
        )
        if (any(not isinstance(k, str) or _KEY.fullmatch(k) is None for k in keys)
                or len(set(keys)) != 3):
            raise ValueError("witness, evaluator and custodian pins must be distinct")
        if (not isinstance(claimed_clock_check_utc, datetime)
                or claimed_clock_check_utc.tzinfo is None
                or claimed_clock_check_utc.utcoffset() != timedelta()):
            raise ValueError("operator clock check must be timezone-aware UTC")
        if not isinstance(enrollment, dict) or len(json.dumps(enrollment)) > 4096:
            raise ValueError("witness enrollment missing or oversized")
        payload = ReceiptVerifier(
            pinned_witness_public_key_hex, expected_run_id=expected_run_id,
        ).verify_next(enrollment)
        if not isinstance(payload, dict) or set(payload) != _FIELDS:
            raise ValueError("witness enrollment payload schema mismatch")
        if (payload["schema"] != "c3r-g1-crossed-enrollment-v0.1"
                or payload["plan_digest"] != make_plan().public_digest
                or payload["evaluator_public_key_hex"] != expected_evaluator_public_key_hex
                or payload["custodian_public_key_hex"] != expected_custodian_public_key_hex
                or type(payload["development_attempts"]) is not int
                or payload["development_attempts"] != 16
                or type(payload["qualification_attempts"]) is not int
                or payload["qualification_attempts"] != 24
                or payload["provider_sends_authorized"] is not False
                or payload["external_witness_attested"] is not False
                or payload["trusted_timestamp_attested"] is not False
                or payload["scientific_acceptance"] is not False):
            raise ValueError("witness enrollment has wrong frozen run and role contract")
        begin = _utc(payload["claimed_issued_at_utc"])
        finish = _utc(payload["claimed_expires_at_utc"])
        if (not begin <= claimed_clock_check_utc <= finish
                or not begin < finish <= begin + timedelta(days=30)):
            raise ValueError("claimed witness enrollment validity rejected")
        return cls(
            make_plan().public_digest, expected_run_id,
            expected_evaluator_public_key_hex,
            expected_custodian_public_key_hex,
            pinned_witness_public_key_hex, _digest(enrollment),
        )

    def verify_deposit(
        self, *, deposit: dict[str, object], source_head_sha256: str,
    ) -> dict[str, object]:
        """Compare source head with signed candidate custodian receipt."""
        audit = verify_source_deposit(
            deposit=deposit, source_head=source_head_sha256,
            expected_run_id=self.run_id,
            evaluator_public_key_hex=self.evaluator_public_key_hex,
            pinned_custodian_public_key_hex=self.custodian_public_key_hex,
        )
        return {
            "schema": "c3r-g1-crossed-enrollment-deposit-audit-v0.1",
            "source_deposit_signed_by_registered_custodian": (
                audit["source_head_signed_by_pinned_candidate_custodian"]
            ),
            "enrollment_signature_and_role_pins_valid": True,
            "witness_enrollment_sha256": self.signed_enrollment_sha256,
            "independent_witness_custody_attested": False,
            "trusted_timestamp_attested": False,
            "external_immutable_deposit_verified": False,
            "provider_execution_verified": False,
            "physical_sends": 0,
            "live_ready": False,
            "scientific_acceptance": False,
        }

    def verify_terminal(
        self, *, receipts: tuple[dict[str, object], ...],
        expected_source_head_sha256: str,
    ) -> dict[str, object]:
        """Verify frozen transcript; does not prove external custody occurred."""
        checked = verify_crossed_receipt_chain(
            make_plan(), receipts=receipts, mode="terminal",
            expected_run_id=self.run_id,
            pinned_evaluator_public_key_hex=self.evaluator_public_key_hex,
            expected_source_chain_head_sha256=expected_source_head_sha256,
        )
        return {
            "schema": "c3r-g1-crossed-enrollment-terminal-audit-v0.1",
            "witness_enrollment_sha256": self.signed_enrollment_sha256,
            "verified_logical_attempts": len(checked.outcomes or ()),
            "source_chain_digest_locked": (
                checked.source_chain_head_sha256 == expected_source_head_sha256
            ),
            "external_prequalification_deposit_time_attested": False,
            "source_head_third_party_deposit_attested": False,
            "provider_sends_verified": False,
            "scientific_acceptance": False,
        }
