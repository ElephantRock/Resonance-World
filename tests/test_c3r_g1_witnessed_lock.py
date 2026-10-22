"""Witnessed G1 admission: prospective key/cohort/target freeze before trial."""

from __future__ import annotations

import copy
from datetime import UTC, datetime

import pytest

from resonance_world.c3r_g1_evaluator_receipts import (
    ReceiptSigner,
    ReceiptVerifier,
    VerifiedEvaluatorSession,
)
from resonance_world.c3r_g1_model_boundary import ModelChoiceCompletion
from resonance_world.c3r_g1_multischema import V2Design
from resonance_world.c3r_g1_sealed_evaluator import SealedEvaluator
from resonance_world.c3r_g1_sealed_runner import SealedPilotRunner
from resonance_world.c3r_g1_witnessed_lock import (
    WitnessSigner,
    WitnessVerifier,
    WitnessedEvaluatorSession,
)

RUN = "g1-precommitted-20261022"
NOW = datetime(2026, 10, 22, 9, 0, 0, tzinfo=UTC)
TARGET_KEY = bytes.fromhex("21" * 32)
EVALUATOR_SIGNING = bytes.fromhex("32" * 32)
WITNESS_SIGNING = bytes.fromhex("43" * 32)


class _OfflineConstant:
    def complete(self, _request):
        return ModelChoiceCompletion(output="A", model_id="offline-schema-fixture")


class _FakeSignedTransport:
    def __init__(self, grader, signer):
        self.grader = grader
        self.signer = signer
        self.attempt_count = 0

    def ready(self):
        return self.signer.seal(self.grader.ready().payload)

    def submit(self, req):
        self.attempt_count += 1
        return self.signer.seal(self.grader.submit(req).payload)

    def finalize(self):
        return self.signer.seal(self.grader.finalize({"op": "finalize"}).payload)


def _setup():
    cohort = V2Design(
        units=1, development_per_family=1, qualification_per_family=1,
    ).freeze()
    grader = SealedEvaluator(cohort, private_key=TARGET_KEY)
    signing = ReceiptSigner(EVALUATOR_SIGNING, run_id=RUN)
    witness = WitnessSigner(WITNESS_SIGNING)
    signed = witness.sign_lock(
        run_id=RUN, cohort=cohort,
        evaluator_public_key_hex=signing.public_key_hex,
        target_commitment=grader.ready().payload["target_commitment"],
        issued_at_utc="2026-10-22T08:00:00Z",
        expires_at_utc="2026-10-23T08:00:00Z",
    )
    return cohort, grader, signing, witness, signed


def _verify(cohort, witness, signing, signed):
    return WitnessVerifier(witness.public_key_hex).verify(
        signed, cohort, expected_run_id=RUN,
        expected_evaluator_public_key_hex=signing.public_key_hex, now_utc=NOW,
    )


def test_full_witness_gated_signed_source_and_sealed_qualification() -> None:
    cohort, grader, signing, witness, signed = _setup()
    immutable = _verify(cohort, witness, signing, signed)
    assert immutable.target_commitment == grader.ready().payload["target_commitment"]
    assert immutable.public_cohort_digest == cohort.digest
    transport = _FakeSignedTransport(grader, signing)
    signed_session = VerifiedEvaluatorSession(
        transport, ReceiptVerifier(signing.public_key_hex, expected_run_id=RUN)
    )
    session = WitnessedEvaluatorSession(signed_session, immutable)
    report = SealedPilotRunner(cohort, session).run(
        port_factory=lambda _u, _a, _s: _OfflineConstant()
    )
    assert transport.attempt_count == cohort.design.logical_calls == 8
    assert len(signed_session.signed_receipts) == 10
    assert report.report.to_dict()["heldout_triplets_complete"] == 2
    assert report.report.to_dict()["mean_unit_itt_learned_minus_fresh"] == 0
    assert report.to_dict()["scientific_acceptance"] is False
    assert report.to_dict()["evaluator_identity_attested"] is False


@pytest.mark.parametrize(("field", "value"), [
    ("run_id", "wrong-run-fixture"),
    ("public_cohort_digest", "0" * 64),
    ("evaluator_public_key_hex", "0" * 64),
    ("target_commitment", "1" * 64),
    ("issued_at_utc", "2026-10-24T08:00:00Z"),
    ("expires_at_utc", "2026-10-20T08:00:00Z"),
    ("witness_signature", "a" * 128),
])
def test_lock_substitution_or_incoherent_times_are_rejected(field, value) -> None:
    cohort, _grader, signing, witness, signed = _setup()
    changed = copy.deepcopy(signed)
    changed[field] = value
    with pytest.raises(ValueError):
        _verify(cohort, witness, signing, changed)


def test_different_out_of_band_witness_key_or_expired_enrollment_rejected() -> None:
    cohort, _grader, signing, _witness, signed = _setup()
    stranger = WitnessVerifier(WitnessSigner(bytes.fromhex("54" * 32)).public_key_hex)
    with pytest.raises(ValueError, match="signature"):
        stranger.verify(
            signed, cohort, expected_run_id=RUN,
            expected_evaluator_public_key_hex=signing.public_key_hex,
            now_utc=NOW,
        )
    with pytest.raises(ValueError, match="expired"):
        WitnessVerifier(WitnessSigner(WITNESS_SIGNING).public_key_hex).verify(
            signed, cohort, expected_run_id=RUN,
            expected_evaluator_public_key_hex=signing.public_key_hex,
            now_utc=datetime(2026, 10, 25, tzinfo=UTC),
        )


def test_wrong_startup_commitment_denied_before_source_submission() -> None:
    cohort, grader, signing, witness, signed = _setup()
    witnessed = _verify(cohort, witness, signing, signed)
    wrong_grader = SealedEvaluator(cohort, private_key=bytes.fromhex("91" * 32))
    transport = _FakeSignedTransport(wrong_grader, signing)
    verified = VerifiedEvaluatorSession(
        transport, ReceiptVerifier(signing.public_key_hex, expected_run_id=RUN)
    )
    session = WitnessedEvaluatorSession(verified, witnessed)
    with pytest.raises(ValueError, match="preregistered witness lock"):
        SealedPilotRunner(cohort, session).run(
            port_factory=lambda _u, _a, _s: _OfflineConstant(),
        )
    assert transport.attempt_count == 0
    assert grader.ready().payload["target_commitment"] != (
        wrong_grader.ready().payload["target_commitment"]
    )


def test_witness_lock_rejects_malformed_and_unbounded_enrollment() -> None:
    cohort, grader, signing, witness, _signed = _setup()
    with pytest.raises(ValueError, match="within 30 days"):
        witness.sign_lock(
            run_id=RUN, cohort=cohort,
            evaluator_public_key_hex=signing.public_key_hex,
            target_commitment=grader.ready().payload["target_commitment"],
            issued_at_utc="2026-10-22T08:00:00Z",
            expires_at_utc="2027-01-01T08:00:00Z",
        )
    with pytest.raises(ValueError, match="witness time"):
        witness.sign_lock(
            run_id=RUN, cohort=cohort,
            evaluator_public_key_hex=signing.public_key_hex,
            target_commitment=grader.ready().payload["target_commitment"],
            issued_at_utc="not a date",
            expires_at_utc="2026-10-23T08:00:00Z",
        )
    with pytest.raises(ValueError, match="32 bytes"):
        WitnessSigner(b"x")
    with pytest.raises(ValueError, match="pinned public key"):
        WitnessVerifier("INVALID")
