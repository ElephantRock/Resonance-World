"""Zero-provider witness-UID checkpoint issuer contract tests."""

from __future__ import annotations

import copy
import os
from datetime import UTC, datetime

import pytest

from resonance_world.c3r_g1_crossed_local_evaluator import CrossedLocalEvaluator
from resonance_world.c3r_g1_crossed_plan import make_plan
from resonance_world.c3r_g1_crossed_source_deposit import deposit_source_receipts
from resonance_world.c3r_g1_crossed_uid_witness import issue_checkpoint
from resonance_world.c3r_g1_crossed_witness_checkpoint import verify_witness_checkpoint
from resonance_world.c3r_g1_crossed_enrollment import EnrollmentPin
from resonance_world.c3r_g1_evaluator_receipts import ReceiptSigner

RUN = "g1x-fouruid-fixture-direct"
NOW = datetime(2026, 10, 23, 6, 0, tzinfo=UTC)


def _setup(tmp_path):
    witness_seed, evaluator_seed, custody_seed = (os.urandom(32) for _ in range(3))
    signer = ReceiptSigner(witness_seed, run_id=RUN)
    evaluator_key = ReceiptSigner(evaluator_seed, run_id=RUN).public_key_hex
    custodian_key = ReceiptSigner(custody_seed, run_id=RUN).public_key_hex
    enrollment = signer.seal({
        "schema": "c3r-g1-crossed-enrollment-v0.1",
        "plan_digest": make_plan().public_digest,
        "evaluator_public_key_hex": evaluator_key,
        "custodian_public_key_hex": custodian_key,
        "development_attempts": 16,
        "qualification_attempts": 24,
        "claimed_issued_at_utc": "2026-10-23T05:00:00Z",
        "claimed_expires_at_utc": "2026-10-24T05:00:00Z",
        "provider_sends_authorized": False,
        "external_witness_attested": False,
        "trusted_timestamp_attested": False,
        "scientific_acceptance": False,
    })
    grader = CrossedLocalEvaluator(
        run_id=RUN, private_target_seed=os.urandom(32),
        signing_seed=evaluator_seed, pinned_custodian_public_key_hex=custodian_key,
        signed_enrollment=enrollment,
        pinned_witness_public_key_hex=signer.public_key_hex,
        claimed_clock_check_utc=NOW,
    )
    sources = tuple(grader.submit(status="accepted", choice="A")[
        "signed_source_receipt"] for _ in range(16))
    source_head = grader.seal_source()["source_chain_head_sha256"]
    store = tmp_path / "custody"
    store.mkdir(mode=0o700)
    deposit, _ = deposit_source_receipts(
        source_receipts=sources, expected_run_id=RUN,
        evaluator_public_key_hex=evaluator_key,
        custodian_private_seed=custody_seed, destination=store,
    )
    return witness_seed, enrollment, evaluator_key, custodian_key, sources, deposit, source_head


def _issue(fixture, **changes):
    secret, enrollment, evaluator, custodian, sources, deposit, _head = fixture
    args = {
        "run_id": RUN, "witness_seed": secret, "enrollment": enrollment,
        "evaluator_public_hex": evaluator, "custodian_public_hex": custodian,
        "source_receipts": sources, "custodian_deposit": deposit,
        "claimed_clock_utc": NOW,
    }
    args.update(changes)
    return issue_checkpoint(**args)


def test_witness_issues_chain_second_receipt_after_full_source_and_deposit(tmp_path):
    fixture = _setup(tmp_path)
    signed = _issue(fixture)
    secret, enrollment, evaluator, custodian, _sources, deposit, head = fixture
    assert signed["sequence"] == 2
    assert signed["payload"]["source_chain_head_sha256"] == head
    assert signed["payload"]["scientific_acceptance"] is False
    pinned = EnrollmentPin.verify(
        enrollment, pinned_witness_public_key_hex=ReceiptSigner(
            secret, run_id=RUN
        ).public_key_hex,
        expected_run_id=RUN,
        expected_evaluator_public_key_hex=evaluator,
        expected_custodian_public_key_hex=custodian,
        claimed_clock_check_utc=NOW,
    )
    verdict = verify_witness_checkpoint(
        pinned, signed_enrollment=enrollment, signed_checkpoint=signed,
        signed_custodian_deposit=deposit, source_chain_head_sha256=head,
        claimed_clock_check_utc=NOW,
    )
    assert verdict.audit()["external_deposit_observed_before_holdout"] is False


def test_witness_rejects_missing_or_reordered_source_receipts(tmp_path):
    fixture = _setup(tmp_path)
    source = fixture[4]
    for invalid in (source[:-1], source[1:] + source[:1],
                    source[:10] + source[9:10] + source[11:]):
        with pytest.raises(ValueError):
            _issue(fixture, source_receipts=invalid)


def test_witness_rejects_tampered_custodian_deposit(tmp_path):
    fixture = _setup(tmp_path)
    corrupted = copy.deepcopy(fixture[5])
    corrupted["payload"]["source_chain_head_sha256"] = "0" * 64
    with pytest.raises(ValueError):
        _issue(fixture, custodian_deposit=corrupted)


def test_witness_rejects_wrong_private_seed_and_wrong_enrolled_key(tmp_path):
    fixture = _setup(tmp_path)
    with pytest.raises(ValueError):
        _issue(fixture, witness_seed=os.urandom(32))
    with pytest.raises(ValueError):
        _issue(fixture, custodian_public_hex=fixture[2])


def test_witness_rejects_out_of_window_local_clock(tmp_path):
    fixture = _setup(tmp_path)
    with pytest.raises(ValueError):
        _issue(fixture, claimed_clock_utc=datetime(2026, 10, 25, tzinfo=UTC))
