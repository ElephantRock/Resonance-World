"""Fail-closed local witness checkpoint exercises; no external deposit claims."""

from __future__ import annotations

import copy
import os
from datetime import UTC, datetime, timedelta

import pytest

from resonance_world.c3r_g1_crossed_enrollment import EnrollmentPin, _digest
from resonance_world.c3r_g1_crossed_local_evaluator import CrossedLocalEvaluator
from resonance_world.c3r_g1_crossed_plan import make_plan
from resonance_world.c3r_g1_crossed_receipt_bridge import verify_crossed_receipt_chain
from resonance_world.c3r_g1_crossed_source_deposit import deposit_source_receipts
from resonance_world.c3r_g1_crossed_witness_checkpoint import verify_witness_checkpoint
from resonance_world.c3r_g1_evaluator_receipts import ReceiptSigner

RUN_ID = "g1x-checkpoint-offline-20261023"
NOW = datetime(2026, 10, 23, 5, 0, tzinfo=UTC)


def _fixture(tmp_path):
    witness_seed = os.urandom(32)
    witness = ReceiptSigner(witness_seed, run_id=RUN_ID)
    target_seed = os.urandom(32)
    evaluator_seed = os.urandom(32)
    custody_seed = os.urandom(32)
    evaluator_key = ReceiptSigner(evaluator_seed, run_id=RUN_ID).public_key_hex
    custodian_key = ReceiptSigner(custody_seed, run_id=RUN_ID).public_key_hex
    enrollment = witness.seal({
        "schema": "c3r-g1-crossed-enrollment-v0.1",
        "plan_digest": make_plan().public_digest,
        "evaluator_public_key_hex": evaluator_key,
        "custodian_public_key_hex": custodian_key,
        "development_attempts": 16,
        "qualification_attempts": 24,
        "claimed_issued_at_utc": "2026-10-23T04:00:00Z",
        "claimed_expires_at_utc": "2026-10-24T04:00:00Z",
        "provider_sends_authorized": False,
        "external_witness_attested": False,
        "trusted_timestamp_attested": False,
        "scientific_acceptance": False,
    })
    pin = EnrollmentPin.verify(
        enrollment, pinned_witness_public_key_hex=witness.public_key_hex,
        expected_run_id=RUN_ID, expected_evaluator_public_key_hex=evaluator_key,
        expected_custodian_public_key_hex=custodian_key,
        claimed_clock_check_utc=NOW,
    )
    grader = CrossedLocalEvaluator(
        run_id=RUN_ID, private_target_seed=target_seed,
        signing_seed=evaluator_seed, pinned_custodian_public_key_hex=custodian_key,
        signed_enrollment=enrollment,
        pinned_witness_public_key_hex=witness.public_key_hex,
        claimed_clock_check_utc=NOW,
    )
    sources = tuple(grader.submit(status="accepted", choice="A")[
        "signed_source_receipt"] for _ in range(16))
    freeze = grader.seal_source()["source_chain_head_sha256"]
    deposit_dir = tmp_path / "custody"
    deposit_dir.mkdir(mode=0o700)
    deposit, _ = deposit_source_receipts(
        source_receipts=sources, expected_run_id=RUN_ID,
        evaluator_public_key_hex=evaluator_key,
        custodian_private_seed=custody_seed, destination=deposit_dir,
    )
    body = {
        "schema": "c3r-g1-crossed-witness-checkpoint-v0.1",
        "plan_digest": make_plan().public_digest,
        "enrollment_sha256": _digest(enrollment),
        "source_chain_head_sha256": freeze,
        "custodian_receipt_sha256": _digest(deposit),
        "development_attempts": 16,
        "qualification_attempts": 24,
        "claimed_checkpoint_at_utc": "2026-10-23T04:59:00Z",
        "external_witness_attested": False,
        "trusted_timestamp_attested": False,
        "external_immutable_deposit_attested": False,
        "provider_sends_authorized": False,
        "scientific_acceptance": False,
    }
    checkpoint = witness.seal(body)
    return {
        "witness": witness, "witness_seed": witness_seed, "pin": pin, "grader": grader,
        "source": sources, "enrollment": enrollment, "checkpoint": checkpoint,
        "deposit": deposit, "source_head": freeze,
    }


def _verify(f, **overrides):
    return verify_witness_checkpoint(
        overrides.get("pin", f["pin"]),
        signed_enrollment=overrides.get("enrollment", f["enrollment"]),
        signed_checkpoint=overrides.get("checkpoint", f["checkpoint"]),
        signed_custodian_deposit=overrides.get("deposit", f["deposit"]),
        source_chain_head_sha256=overrides.get("source_head", f["source_head"]),
        claimed_clock_check_utc=overrides.get("now", NOW),
    )


def test_checkpoint_releases_qualification_only_with_matched_signed_chain(tmp_path):
    f = _fixture(tmp_path)
    with pytest.raises(ValueError, match="checkpoint required"):
        f["grader"].acknowledge_custody(f["deposit"])
    with pytest.raises(ValueError, match="before signed source custody"):
        f["grader"].submit(status="accepted", choice="A")
    out = _verify(f)
    assert out.source_chain_head_sha256 == f["source_head"]
    assert out.audit()["external_deposit_observed_before_holdout"] is False
    assert out.audit()["scientific_acceptance"] is False
    f["grader"].acknowledge_custody(f["deposit"], witness_checkpoint=f["checkpoint"])
    with pytest.raises(ValueError, match="exactly once"):
        f["grader"].acknowledge_custody(f["deposit"], witness_checkpoint=f["checkpoint"])
    for i in range(24):
        response = f["grader"].submit(status="accepted" if i < 23 else "not_sent",
                                       choice="B" if i < 23 else None)
        assert set(response) == {"schema", "phase", "qualification_received"}
    terminal = f["grader"].finalize()
    assert terminal["prospective_witness_checkpoint_checked"] is True
    assert terminal["witness_checkpoint_sha256"] == _digest(f["checkpoint"])
    result = verify_crossed_receipt_chain(
        make_plan(), receipts=tuple(terminal["receipts"]), mode="terminal",
        expected_run_id=RUN_ID,
        pinned_evaluator_public_key_hex=f["grader"].evaluator_public_key_hex,
        expected_source_chain_head_sha256=f["source_head"],
    )
    assert result.audit["descriptive"]["logical_status_counts"]["not_sent"] == 1


def test_absent_pre_enrollment_rejects_checkpoint(tmp_path):
    f = _fixture(tmp_path)
    legacy = CrossedLocalEvaluator(
        run_id=RUN_ID, private_target_seed=os.urandom(32),
        signing_seed=os.urandom(32),
        pinned_custodian_public_key_hex=f["pin"].custodian_public_key_hex,
    )
    for _ in range(16):
        legacy.submit(status="accepted", choice="A")
    legacy.seal_source()
    with pytest.raises(ValueError, match="requires pre-source enrollment"):
        legacy.acknowledge_custody(f["deposit"], witness_checkpoint=f["checkpoint"])


def test_wrong_previously_pinned_enrollment_rejected(tmp_path):
    f = _fixture(tmp_path)
    corrupted = copy.deepcopy(f["enrollment"])
    corrupted["payload"]["plan_digest"] = "0" * 64
    with pytest.raises(ValueError):
        _verify(f, enrollment=corrupted)


def test_replay_wrong_sequence_and_incorrect_signature_rejected(tmp_path):
    f = _fixture(tmp_path)
    with pytest.raises(ValueError):
        _verify(f, checkpoint=f["enrollment"])
    bad = copy.deepcopy(f["checkpoint"])
    bad["payload"]["source_chain_head_sha256"] = "0" * 64
    with pytest.raises(ValueError):
        _verify(f, checkpoint=bad)
    other = ReceiptSigner(os.urandom(32), run_id=RUN_ID)
    alien = other.seal(f["checkpoint"]["payload"])
    with pytest.raises(ValueError):
        _verify(f, checkpoint=alien)


def test_custodian_swap_and_prequalification_head_mismatch_rejected(tmp_path):
    f = _fixture(tmp_path)
    bad = copy.deepcopy(f["deposit"])
    bad["payload"]["source_chain_head_sha256"] = "0" * 64
    with pytest.raises(ValueError):
        _verify(f, deposit=bad)
    with pytest.raises(ValueError):
        _verify(f, source_head="0" * 64)


def test_correctly_signed_but_wrong_reference_and_private_field_rejected(tmp_path):
    f = _fixture(tmp_path)
    extra = {**f["checkpoint"]["payload"], "private_target_map": "AABB"}
    # Recreate a valid sequence-2 signature using the identical test key.
    signer = ReceiptSigner(f["witness_seed"], run_id=RUN_ID)
    assert signer.seal(f["enrollment"]["payload"]) == f["enrollment"]
    signed_bad = signer.seal(extra)
    with pytest.raises(ValueError, match="forbidden or missing"):
        _verify(f, checkpoint=signed_bad)
    signer2 = ReceiptSigner(f["witness_seed"], run_id=RUN_ID)
    _ = signer2.seal(f["enrollment"]["payload"])
    bad_deposit_hash = signer2.seal({
        **f["checkpoint"]["payload"], "custodian_receipt_sha256": "0" * 64,
    })
    with pytest.raises(ValueError):
        _verify(f, checkpoint=bad_deposit_hash)


def test_claimed_wrong_time_rejected_not_treated_as_external_time(tmp_path):
    f = _fixture(tmp_path)
    for invalid in (NOW - timedelta(days=2), NOW + timedelta(days=2),
                    datetime(2026, 10, 23, 5, 0)):
        with pytest.raises(ValueError):
            _verify(f, now=invalid)
    assert _verify(f).audit()["trusted_timestamp_attested"] is False


def test_type_confusion_and_wrong_counts_rejected(tmp_path):
    f = _fixture(tmp_path)
    witness = f["witness"]
    for changed in ({"development_attempts": True},
                    {"qualification_attempts": 23},
                    {"external_witness_attested": True}):
        cloned = ReceiptSigner(f["witness_seed"], run_id=RUN_ID)
        cloned.seal(f["enrollment"]["payload"])
        forged = cloned.seal({**f["checkpoint"]["payload"], **changed})
        with pytest.raises(ValueError):
            _verify(f, checkpoint=forged)
    assert witness.public_key_hex == f["pin"].witness_public_key_hex
