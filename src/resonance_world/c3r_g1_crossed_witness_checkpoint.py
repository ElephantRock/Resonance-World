"""Local, chained witness checkpoint before the crossed G1 holdout (offline only).

This verifies cryptographic consistency, *not* pre-holdout external publication,
independent witness custody, trusted chronology, or model-provider execution.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta

from resonance_world.c3r_g1_crossed_enrollment import EnrollmentPin, _digest, _utc
from resonance_world.c3r_g1_evaluator_receipts import ReceiptVerifier

_FIELDS = frozenset({
    "schema", "plan_digest", "enrollment_sha256", "source_chain_head_sha256",
    "custodian_receipt_sha256", "development_attempts", "qualification_attempts",
    "claimed_checkpoint_at_utc", "external_witness_attested",
    "trusted_timestamp_attested", "external_immutable_deposit_attested",
    "provider_sends_authorized", "scientific_acceptance",
})


@dataclass(frozen=True, slots=True)
class WitnessCheckpoint:
    """Bound receipt fingerprint only: never a live authorization or attestation."""

    witness_checkpoint_sha256: str
    source_chain_head_sha256: str
    custodian_receipt_sha256: str
    enrollment_sha256: str

    def audit(self) -> dict[str, object]:
        return {
            "schema": "c3r-g1-crossed-witness-checkpoint-audit-v0.1",
            "enrollment_and_checkpoint_signature_chain_verified": True,
            "frozen_plan_and_custody_receipt_bound": True,
            "witness_checkpoint_sha256": self.witness_checkpoint_sha256,
            "external_witness_operator_attested": False,
            "external_deposit_observed_before_holdout": False,
            "trusted_timestamp_attested": False,
            "immutable_off_host_custody_attested": False,
            "provider_sends_verified": False,
            "physical_sends_by_verifier": 0,
            "live_ready": False,
            "scientific_acceptance": False,
            "verdict": "local_chained_witness_claim_valid_unattested",
        }


def verify_witness_checkpoint(
    pin: EnrollmentPin, *,
    signed_enrollment: dict[str, object],
    signed_checkpoint: dict[str, object],
    signed_custodian_deposit: dict[str, object],
    source_chain_head_sha256: str,
    claimed_clock_check_utc: datetime,
) -> WitnessCheckpoint:
    """Require sequence-2 witness signature, enrollment and deposited source.

    The pinned verifier receives the *original* enrollment and checks both
    envelopes in sequence. The source head is obtained from verified source
    receipts. The checkpoint's date is a claim, not third-party time proof.
    """
    if (not isinstance(signed_enrollment, dict)
            or not isinstance(signed_checkpoint, dict)
            or not isinstance(signed_custodian_deposit, dict)):
        raise ValueError("witness checkpoint requires signed envelope objects")
    try:
        if sum(len(json.dumps(x)) for x in (
            signed_enrollment, signed_checkpoint, signed_custodian_deposit,
        )) > 16_384:
            raise ValueError("witness checkpoint bundle too large")
    except (TypeError, OverflowError) as exc:
        raise ValueError("witness checkpoint bundle is not JSON serializable") from exc
    if (_digest(signed_enrollment) != pin.signed_enrollment_sha256
            or pin.public_plan_digest == ""
            or pin.witness_public_key_hex in (
                pin.custodian_public_key_hex, pin.evaluator_public_key_hex,
            )):
        raise ValueError("witness enrollment does not match prospective pin")
    if (not isinstance(claimed_clock_check_utc, datetime)
            or claimed_clock_check_utc.tzinfo is None
            or claimed_clock_check_utc.utcoffset() != timedelta()):
        raise ValueError("witness clock check requires UTC datetime")
    # Re-verify enrollment signature and exact sequence lineage, not just a hash.
    verifier = ReceiptVerifier(
        pin.witness_public_key_hex, expected_run_id=pin.run_id,
    )
    first = verifier.verify_next(signed_enrollment)
    if first.get("plan_digest") != pin.public_plan_digest:
        raise ValueError("witness enrollment plan mismatch")
    second = verifier.verify_next(signed_checkpoint)
    if set(second) != _FIELDS:
        raise ValueError("witness checkpoint has forbidden or missing fields")
    pin.verify_deposit(
        deposit=signed_custodian_deposit,
        source_head_sha256=source_chain_head_sha256,
    )
    expected = {
        "schema": "c3r-g1-crossed-witness-checkpoint-v0.1",
        "plan_digest": pin.public_plan_digest,
        "enrollment_sha256": pin.signed_enrollment_sha256,
        "source_chain_head_sha256": source_chain_head_sha256,
        "custodian_receipt_sha256": _digest(signed_custodian_deposit),
        "development_attempts": 16,
        "qualification_attempts": 24,
        "external_witness_attested": False,
        "trusted_timestamp_attested": False,
        "external_immutable_deposit_attested": False,
        "provider_sends_authorized": False,
        "scientific_acceptance": False,
    }
    if any(second.get(name) != value or type(second.get(name)) is not type(value)
           for name, value in expected.items()):
        raise ValueError("witness checkpoint does not bind enrollment and deposit")
    claimed = _utc(second["claimed_checkpoint_at_utc"])
    enrolled_at = _utc(first["claimed_issued_at_utc"])
    expires_at = _utc(first["claimed_expires_at_utc"])
    if not enrolled_at <= claimed <= claimed_clock_check_utc <= expires_at:
        raise ValueError("witness checkpoint claimed chronology invalid")
    return WitnessCheckpoint(
        witness_checkpoint_sha256=_digest(signed_checkpoint),
        source_chain_head_sha256=source_chain_head_sha256,
        custodian_receipt_sha256=_digest(signed_custodian_deposit),
        enrollment_sha256=pin.signed_enrollment_sha256,
    )
