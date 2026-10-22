"""Crossed G1 adapter for the existing Ed25519 chained evaluator receipts.

Reuses the established ReceiptVerifier wire protocol. This module does not
possess a signer key, target assignment, provider transport or scientific
authorization. Independent evaluator control and key custody are external.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Literal

from resonance_world.c3r_g1_crossed_outcomes import AttemptOutcome, audit_outcomes
from resonance_world.c3r_g1_crossed_plan import CrossedPlan, make_plan
from resonance_world.c3r_g1_crossed_preflight import SourceObservation
from resonance_world.c3r_g1_evaluator_receipts import ReceiptVerifier

Mode = Literal["development", "terminal"]
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_EMPTY_SHA = hashlib.sha256(b"").hexdigest()
_PAYLOAD_FIELDS = frozenset({
    "schema", "plan_digest", "slot_index", "unit_id", "task_id",
    "stage", "arm", "status", "action", "correct", "output_sha256",
})


@dataclass(frozen=True, slots=True)
class CrossedVerifiedBatch:
    """Signed claims, not a real-world independent evaluator attestation."""

    sources: tuple[SourceObservation, ...] | None
    outcomes: tuple[AttemptOutcome, ...] | None
    source_chain_head_sha256: str
    audit: dict[str, object]


def _digest(value: object) -> str:
    """Same sorted compact JSON lineage as c3r_g1_evaluator_receipts."""
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")).hexdigest()


def _validated_attempt(
    payload: dict[str, object], *, index: int,
    expected: tuple[str, str, str, str], plan_digest: str,
) -> AttemptOutcome:
    if set(payload) != _PAYLOAD_FIELDS:
        raise ValueError("crossed attempt payload fields differ from frozen schema")
    if (payload["schema"] != "c3r-g1-crossed-attempt-v0.1"
            or payload["plan_digest"] != plan_digest
            or type(payload["slot_index"]) is not int
            or payload["slot_index"] != index):
        raise ValueError("crossed receipt schema, plan or ordinal mismatch")
    if tuple(payload[name] for name in ("unit_id", "task_id", "stage", "arm")) != expected:
        raise ValueError("crossed receipt does not match prescribed attempt")
    status = payload["status"]
    action = payload["action"]
    correct = payload["correct"]
    sha = payload["output_sha256"]
    if status not in ("accepted", "invalid_format", "provider_error", "not_sent"):
        raise ValueError("invalid crossed receipt status")
    if status == "accepted":
        if (action not in ("A", "B") or type(correct) is not bool
                or not isinstance(sha, str)
                or _SHA256.fullmatch(sha) is None
                or sha in (_EMPTY_SHA, "0" * 64)):
            raise ValueError("accepted signed attempt requires nonempty output hash and score")
    elif (action is not None or correct is not None
          or (sha is not None and (status != "invalid_format"
                                  or not isinstance(sha, str)
                                  or _SHA256.fullmatch(sha) is None))):
        raise ValueError("unresolved signed attempt asserts action, score or invalid hash")
    return AttemptOutcome(expected[0], expected[1], expected[2], expected[3],
                          status, action, correct)


def verify_crossed_receipt_chain(
    plan: CrossedPlan,
    *,
    receipts: tuple[dict[str, object], ...],
    mode: Mode,
    expected_run_id: str,
    pinned_evaluator_public_key_hex: str,
    expected_source_chain_head_sha256: str | None = None,
) -> CrossedVerifiedBatch:
    """Verify exactly 16 source or 40 terminal existing-protocol receipts.

    The terminal audit requires an externally retained source chain-head pin
    obtained before qualifications. This does not establish actual external
    custody or trusted timing; the responsible operator must attest those.
    """
    plan.audit()
    if plan.public_digest != make_plan().public_digest:
        raise ValueError("public crossed cohort was modified")
    if mode not in ("development", "terminal"):
        raise ValueError("invalid crossed receipt mode")
    if (mode == "terminal" and (
            not isinstance(expected_source_chain_head_sha256, str)
            or _SHA256.fullmatch(expected_source_chain_head_sha256) is None
    )):
        raise ValueError("terminal audit requires prior externally saved source chain head")
    if mode == "development" and expected_source_chain_head_sha256 is not None:
        raise ValueError("source chain head must originate from source verification")
    expected_length = 16 if mode == "development" else 40
    if not isinstance(receipts, tuple) or len(receipts) != expected_length:
        raise ValueError("missing or extra prescribed chained evaluator receipts")
    verifier = ReceiptVerifier(
        pinned_evaluator_public_key_hex, expected_run_id=expected_run_id,
    )
    outcomes: list[AttemptOutcome] = []
    source_head = ""
    for i, receipt in enumerate(receipts):
        if not isinstance(receipt, dict):
            raise ValueError("receipt envelope must be a JSON object")
        try:
            if len(json.dumps(receipt)) > 8192:
                raise ValueError("oversized evaluator receipt")
        except (TypeError, OverflowError) as exc:
            raise ValueError("evaluator receipt is not JSON serializable") from exc
        signed_payload = verifier.verify_next(receipt)
        slot = plan.schedule[i]
        expected = (slot.unit_id, slot.task_id, slot.stage, slot.arm)
        outcomes.append(_validated_attempt(
            signed_payload, index=i, expected=expected, plan_digest=plan.public_digest,
        ))
        if i == 15:
            source_head = _digest(receipt)
            if (mode == "terminal"
                    and source_head != expected_source_chain_head_sha256):
                raise ValueError("terminal run diverged from prior source chain head")

    audit: dict[str, object] = {
        "schema": "c3r-g1-crossed-receipt-bridge-audit-v0.1",
        "mode": mode,
        "public_plan_digest": plan.public_digest,
        "receipt_chain_length_verified": len(outcomes),
        "receipts_verified_with_pinned_key": True,
        "source_chain_head_verified_against_external_pin": mode == "terminal",
        "source_chain_head_external_custody_attested": False,
        "evaluator_key_independence_attested": False,
        "private_grade_correctness_verified": False,
        "provider_sends_verified": False,
        "physical_sends_performed_by_this_verifier": 0,
        "session_isolation_verified": False,
        "holdout_temporal_closure_attested": False,
        "provider_token_parity_verified": False,
        "live_ready": False,
        "scientific_acceptance": False,
        "verdict": "signed_structural_claims_only_unattested",
    }
    if mode == "development":
        if any(r.status != "accepted" for r in outcomes):
            raise ValueError("development requires sixteen accepted signed grades")
        sources = tuple(SourceObservation(
            r.unit_id, r.task_id, r.action,
            "correct" if r.correct else "incorrect",
        ) for r in outcomes)
        return CrossedVerifiedBatch(sources, None, source_head, audit)

    descriptive = audit_outcomes(plan, outcomes=tuple(outcomes))
    audit["descriptive"] = descriptive
    return CrossedVerifiedBatch(None, tuple(outcomes), source_head, audit)
