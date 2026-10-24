"""Offline signed crossed G1 witness enrollment and source custody checks."""

from __future__ import annotations

import copy
import hashlib
import json
import os
from datetime import UTC, datetime, timedelta

import pytest

from resonance_world.c3r_g1_crossed_enrollment import EnrollmentPin
from resonance_world.c3r_g1_crossed_plan import make_plan
from resonance_world.c3r_g1_crossed_receipt_bridge import verify_crossed_receipt_chain
from resonance_world.c3r_g1_crossed_source_deposit import deposit_source_receipts
from resonance_world.c3r_g1_evaluator_receipts import ReceiptSigner

RUN = "g1x-prospective-enrollment-fixture"
ISSUED = datetime(2026, 10, 22, 10, 0, tzinfo=UTC)


def _fixture():
    witness = ReceiptSigner(os.urandom(32), run_id=RUN)
    evaluator = ReceiptSigner(os.urandom(32), run_id=RUN)
    custodian = ReceiptSigner(os.urandom(32), run_id=RUN)
    body = {
        "schema": "c3r-g1-crossed-enrollment-v0.1",
        "plan_digest": make_plan().public_digest,
        "evaluator_public_key_hex": evaluator.public_key_hex,
        "custodian_public_key_hex": custodian.public_key_hex,
        "development_attempts": 16,
        "qualification_attempts": 24,
        "claimed_issued_at_utc": "2026-10-22T10:00:00Z",
        "claimed_expires_at_utc": "2026-10-23T10:00:00Z",
        "provider_sends_authorized": False,
        "external_witness_attested": False,
        "trusted_timestamp_attested": False,
        "scientific_acceptance": False,
    }
    return witness, evaluator, custodian, witness.seal(body)


def _check(w, e, c, envelope, **overrides):
    return EnrollmentPin.verify(
        envelope, pinned_witness_public_key_hex=overrides.get(
            "witness", w.public_key_hex),
        expected_run_id=overrides.get("run_id", RUN),
        expected_evaluator_public_key_hex=overrides.get("evaluator", e.public_key_hex),
        expected_custodian_public_key_hex=overrides.get("custodian", c.public_key_hex),
        claimed_clock_check_utc=overrides.get("now", ISSUED + timedelta(minutes=1)),
    )


def test_enrollment_pins_frozen_plan_and_three_distinct_role_keys() -> None:
    w, e, c, receipt = _fixture()
    pin = _check(w, e, c, receipt)
    assert len(pin.signed_enrollment_sha256) == 64
    assert pin.public_plan_digest == make_plan().public_digest
    assert pin.run_id == RUN


def test_wrong_witness_identity_cross_run_replay_and_key_alias_rejected() -> None:
    w, e, c, receipt = _fixture()
    with pytest.raises(ValueError):
        _check(w, e, c, receipt, witness=e.public_key_hex)
    with pytest.raises(ValueError):
        _check(w, e, c, receipt, run_id="different-run-20261022")
    with pytest.raises(ValueError, match="distinct"):
        _check(w, e, c, receipt, custodian=e.public_key_hex)


def test_tamper_and_signed_wrong_plan_denominator_rejected() -> None:
    w, e, c, receipt = _fixture()
    changed = copy.deepcopy(receipt)
    changed["payload"]["plan_digest"] = "0" * 64
    with pytest.raises(ValueError):
        _check(w, e, c, changed)
    signer = ReceiptSigner(os.urandom(32), run_id=RUN)
    signed_wrong = signer.seal({**receipt["payload"], "qualification_attempts": 23})
    with pytest.raises(ValueError, match="wrong frozen run"):
        _check(signer, e, c, signed_wrong)
    with pytest.raises(ValueError):
        _check(w, e, c, receipt, custodian=w.public_key_hex)


def test_claimed_enrollment_clock_not_equivalent_to_trusted_time() -> None:
    w, e, c, receipt = _fixture()
    for now in (ISSUED - timedelta(seconds=1), ISSUED + timedelta(days=30),
                datetime(2026, 10, 22, 12, 0)):
        with pytest.raises(ValueError):
            _check(w, e, c, receipt, now=now)
    expected = hashlib.sha256(
        json.dumps(receipt, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    assert _check(w, e, c, receipt).signed_enrollment_sha256 == expected


def test_signed_private_target_leak_field_rejected() -> None:
    w, e, c, receipt = _fixture()
    signer = ReceiptSigner(os.urandom(32), run_id=RUN)
    forbidden = signer.seal({**receipt["payload"], "private_target_map": "AABB"})
    with pytest.raises(ValueError, match="payload schema mismatch"):
        _check(signer, e, c, forbidden)


def test_pinned_enrollment_custody_handoff_and_terminal(tmp_path) -> None:
    _witness, evaluator, _unused, old = _fixture()
    custody_seed = os.urandom(32)
    custody = ReceiptSigner(custody_seed, run_id=RUN)
    other_witness = ReceiptSigner(os.urandom(32), run_id=RUN)
    enrol = other_witness.seal({
        **old["payload"], "custodian_public_key_hex": custody.public_key_hex,
    })
    # WitnessSigner is a local fixture, not third-party enrollment.
    pin = _check(other_witness, evaluator, custody, enrol)
    plan = make_plan()
    receipts = []
    for index, slot in enumerate(plan.schedule):
        accepted = index < 39
        receipts.append(evaluator.seal({
            "schema": "c3r-g1-crossed-attempt-v0.1",
            "plan_digest": plan.public_digest,
            "slot_index": index,
            "unit_id": slot.unit_id,
            "task_id": slot.task_id,
            "stage": slot.stage,
            "arm": slot.arm,
            "status": "accepted" if accepted else "not_sent",
            "action": "A" if accepted else None,
            "correct": False if accepted else None,
            "output_sha256": hashlib.sha256(b"A").hexdigest()
            if accepted else None,
        }))
    source = verify_crossed_receipt_chain(
        plan, receipts=tuple(receipts[:16]), mode="development",
        expected_run_id=RUN,
        pinned_evaluator_public_key_hex=evaluator.public_key_hex,
    )
    private_store = tmp_path / "store"
    private_store.mkdir(mode=0o700)
    deposit, _ = deposit_source_receipts(
        source_receipts=tuple(receipts[:16]), expected_run_id=RUN,
        evaluator_public_key_hex=evaluator.public_key_hex,
        custodian_private_seed=custody_seed, destination=private_store,
    )
    audit = pin.verify_deposit(
        deposit=deposit, source_head_sha256=source.source_chain_head_sha256,
    )
    assert audit["source_deposit_signed_by_registered_custodian"] is True
    assert audit["independent_witness_custody_attested"] is False
    with pytest.raises(ValueError):
        pin.verify_deposit(deposit=deposit, source_head_sha256="0" * 64)
    terminal = pin.verify_terminal(
        receipts=tuple(receipts),
        expected_source_head_sha256=source.source_chain_head_sha256,
    )
    assert terminal["verified_logical_attempts"] == 40
    assert terminal["external_prequalification_deposit_time_attested"] is False
    assert terminal["scientific_acceptance"] is False
    with pytest.raises(ValueError):
        pin.verify_terminal(
            receipts=tuple(receipts), expected_source_head_sha256="0" * 64,
        )
