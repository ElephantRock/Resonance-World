"""Signed G1 evaluator receipts: public verification and replay/tamper resistance."""

from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

from resonance_world.c3r_g1_evaluator_receipts import (
    ReceiptSigner,
    ReceiptVerifier,
    VerifiedEvaluatorSession,
)
from resonance_world.c3r_g1_evaluator_transcript import audit_signed_transcript
from resonance_world.c3r_g1_model_boundary import ModelChoiceCompletion
from resonance_world.c3r_g1_multischema import V2Design
from resonance_world.c3r_g1_multischema_audit import audit_multischema
from resonance_world.c3r_g1_sealed_runner import (
    JsonLineEvaluatorSession,
    SealedPilotRunner,
)

RUN_ID = "g1-pilot-offline-20261022-tests"
SIGNER_SEED = bytes.fromhex("cd" * 32)
TARGET_SEED = bytes.fromhex("ef" * 32)
ROOT = Path(__file__).resolve().parents[1]


def _signer() -> ReceiptSigner:
    return ReceiptSigner(SIGNER_SEED, run_id=RUN_ID)


def _verifier(public_key: str | None = None) -> ReceiptVerifier:
    return ReceiptVerifier(public_key or _signer().public_key_hex, expected_run_id=RUN_ID)


def test_authentic_chained_receipts_and_pinned_public_key() -> None:
    signer = _signer()
    verifier = _verifier()
    for i in range(5):
        payload = {"phase": "qualification_sealed", "n": i}
        signed = signer.seal(payload)
        assert signed["sequence"] == i + 1
        assert signed["signature"] != ""
        assert verifier.verify_next(signed) == payload
    assert signer.public_key_hex == _signer().public_key_hex


@pytest.mark.parametrize("field", [
    "payload", "sequence", "run_id", "prior_sha256",
    "signature", "public_key_sha256", "schema",
])
def test_tamper_rejected_without_advancing_verifier(field: str) -> None:
    signer = _signer()
    original = signer.seal({"phase": "accept_development"})
    forged = copy.deepcopy(original)
    if field == "payload":
        forged[field]["phase"] = "qualification_sealed"
    elif field == "sequence":
        forged[field] = 2
    elif field == "run_id":
        forged[field] = "g1-other-run-20261022"
    elif field == "signature":
        forged[field] = "ab" * 64
    elif field == "schema":
        forged[field] = "unknown"
    else:
        forged[field] = "1" * 64
    verifier = _verifier()
    with pytest.raises(ValueError):
        verifier.verify_next(forged)
    assert verifier.verify_next(original)["phase"] == "accept_development"


def test_replay_missing_reorder_and_wrong_public_key_are_denied() -> None:
    signer = _signer()
    a = signer.seal({"phase": "ready"})
    b = signer.seal({"phase": "development"})
    c = signer.seal({"phase": "qualification"})
    v = _verifier()
    with pytest.raises(ValueError, match="sequence"):
        v.verify_next(b)
    v.verify_next(a)
    with pytest.raises(ValueError, match="sequence"):
        v.verify_next(a)
    with pytest.raises(ValueError, match="sequence"):
        v.verify_next(c)
    v.verify_next(b)
    v.verify_next(c)
    wrong = ReceiptVerifier(
        ReceiptSigner(bytes.fromhex("11" * 32), run_id=RUN_ID).public_key_hex,
        expected_run_id=RUN_ID,
    )
    with pytest.raises(ValueError, match="fingerprint"):
        wrong.verify_next(a)
    wrong_run = ReceiptVerifier(signer.public_key_hex, expected_run_id="other-run-id")
    with pytest.raises(ValueError, match="run ID"):
        wrong_run.verify_next(a)


def test_rejects_noncanonical_extra_fields_and_invalid_private_material() -> None:
    signer = _signer()
    valid = signer.seal({"phase": "ready"})
    extra = {**valid, "private_data": "not allowed"}
    with pytest.raises(ValueError, match="unexpected fields"):
        _verifier().verify_next(extra)
    with pytest.raises(ValueError, match="32 bytes"):
        ReceiptSigner(b"short", run_id=RUN_ID)
    with pytest.raises(ValueError, match="run ID"):
        ReceiptSigner(SIGNER_SEED, run_id="../../injection")
    with pytest.raises(ValueError, match="public key"):
        ReceiptVerifier("not-a-key", expected_run_id=RUN_ID)


def test_worker_signed_subprocess_fails_without_proper_signing_key(
    tmp_path: Path,
) -> None:
    target = tmp_path / "target.hex"
    signing = tmp_path / "signing.hex"
    target.write_text(TARGET_SEED.hex() + "\n")
    signing.write_text(SIGNER_SEED.hex() + "\n")
    target.chmod(0o600)
    signing.chmod(0o644)
    proc = subprocess.run(
        [
            sys.executable, "-m", "resonance_world.c3r_g1_evaluator_worker",
            "--key-file", str(target), "--signing-key-file", str(signing),
            "--run-id", RUN_ID, "--units", "2", "--development", "3",
            "--qualification", "2",
        ],
        cwd=ROOT, text=True, input="", capture_output=True, timeout=12,
        check=False,
    )
    assert proc.returncode == 2
    assert json.loads(proc.stdout)["status"] == "rejected_before_ready"
    assert TARGET_SEED.hex() not in proc.stdout
    assert SIGNER_SEED.hex() not in proc.stdout


class _ConstantPort:
    def complete(self, _request):
        return ModelChoiceCompletion("A", "offline-schema-fixture")


def test_verified_full_three_arm_pilot_over_true_signed_subprocess(
    tmp_path: Path,
) -> None:
    target = tmp_path / "target.hex"
    signing = tmp_path / "signing.hex"
    target.write_text(TARGET_SEED.hex() + "\n")
    signing.write_text(SIGNER_SEED.hex() + "\n")
    target.chmod(0o600)
    signing.chmod(0o600)
    child = subprocess.Popen(
        [
            sys.executable, "-m", "resonance_world.c3r_g1_evaluator_worker",
            "--key-file", str(target), "--signing-key-file", str(signing),
            "--run-id", RUN_ID, "--units", "2", "--development", "3",
            "--qualification", "2",
        ],
        cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, text=True, bufsize=1,
    )
    try:
        assert child.stdout is not None and child.stdin is not None
        transport = JsonLineEvaluatorSession(child.stdout, child.stdin)
        verifier = _verifier()
        session = VerifiedEvaluatorSession(transport, verifier)
        spec = V2Design(units=2, development_per_family=3,
                        qualification_per_family=2)
        cohort = spec.freeze()
        result = SealedPilotRunner(cohort, session).run(
            port_factory=lambda _uid, _arm, _stage: _ConstantPort(),
        )
        child.stdin.close()
        assert child.wait(timeout=15) == 0
        payload = result.to_dict()
        assert payload["evaluator_identity_attested"] is False
        assert payload["scientific_acceptance"] is False
        assert payload["report"]["heldout_triplets_complete"] == 8
        assert payload["report"]["qualification_actions_accepted"] == 24
        audit = audit_multischema(payload["report"], cohort)
        assert audit.verdict == "structurally_consistent_unattested"
        # 1 signed ready + 12 development + 24 qualification + 1 final.
        assert verifier._sequence == 38
        receipts = list(session.signed_receipts)
        assert len(receipts) == 38
        transcript = audit_signed_transcript(
            receipts, cohort, public_key_hex=_signer().public_key_hex,
            expected_run_id=RUN_ID,
        )
        assert transcript.status == "signed_structurally_consistent"
        assert transcript.signed_attempts == 36
        assert transcript.to_dict()["signature_chain_verified"] is True
        assert transcript.to_dict()["evaluator_independence_attested"] is False
        assert transcript.to_dict()["private_grade_correctness_verified"] is False
        assert transcript.to_dict()["scientific_acceptance"] is False
        transcript_file = tmp_path / "signed-receipts.jsonl"
        public_file = tmp_path / "pinned-public-key.hex"
        public_file.write_text(_signer().public_key_hex + "\n", encoding="ascii")
        transcript_file.write_text(
            "".join(json.dumps(x, sort_keys=True) + "\n" for x in receipts),
            encoding="utf-8",
        )
        verify = subprocess.run(
            [
                sys.executable, "-m", "resonance_world.c3r_g1_evaluator_transcript",
                str(transcript_file), "--public-key-file", str(public_file),
                "--run-id", RUN_ID, "--units", "2", "--development", "3",
                "--qualification", "2",
            ],
            cwd=ROOT, capture_output=True, text=True, timeout=15, check=False,
        )
        assert verify.returncode == 0
        assert json.loads(verify.stdout)["signature_chain_verified"] is True
        public_file.write_text("00" * 32 + "\n")
        rejected = subprocess.run(
            [
                sys.executable, "-m", "resonance_world.c3r_g1_evaluator_transcript",
                str(transcript_file), "--public-key-file", str(public_file),
                "--run-id", RUN_ID, "--units", "2", "--development", "3",
                "--qualification", "2",
            ],
            cwd=ROOT, capture_output=True, text=True, timeout=15, check=False,
        )
        assert rejected.returncode == 2
        assert json.loads(rejected.stdout)["scientific_acceptance"] is False
        truncated = audit_signed_transcript(
            receipts[:-1], cohort, public_key_hex=_signer().public_key_hex,
            expected_run_id=RUN_ID,
        )
        assert truncated.status == "rejected_incomplete_or_invalid"
        forged = copy.deepcopy(receipts)
        forged[-1]["payload"]["records"][0]["success"] = not (
            forged[-1]["payload"]["records"][0]["success"]
        )
        attacked = audit_signed_transcript(
            forged, cohort, public_key_hex=_signer().public_key_hex,
            expected_run_id=RUN_ID,
        )
        assert attacked.status == "rejected_incomplete_or_invalid"
        assert "signature_or_chain_invalid" in attacked.errors
        assert SIGNER_SEED.hex() not in json.dumps(payload)
        assert TARGET_SEED.hex() not in json.dumps(payload)
    finally:
        if child.poll() is None:
            child.kill()
            child.wait(timeout=15)


def test_unauthenticated_replies_do_not_pass_verified_adapter() -> None:
    class Unverified:
        def ready(self):
            return {"schema": "c3r-g1-evaluator-v0.1", "phase": "accept_development"}

        def submit(self, _request):
            raise AssertionError("must not reach")

        def finalize(self):
            raise AssertionError("must not reach")

    client = VerifiedEvaluatorSession(Unverified(), _verifier())
    with pytest.raises(ValueError, match="signed evaluator receipt"):
        client.ready()



def test_validly_resigned_but_missing_final_attempt_fails_transcript_contract() -> None:
    from resonance_world.c3r_g1_sealed_evaluator import SealedEvaluator

    cohort = V2Design(
        units=1, development_per_family=1, qualification_per_family=1,
    ).freeze()
    grader = SealedEvaluator(cohort, private_key=TARGET_SEED)
    payloads = [grader.ready().payload]
    for unit in cohort.units:
        for family in unit.families:
            for task in family.development:
                payloads.append(grader.submit({
                    "op": "submit", "unit_id": unit.unit_id, "arm": "learned",
                    "stage": "development", "task_id": task.task_id,
                    "status": "accepted", "choice": "A",
                }).payload)
    for unit in cohort.units:
        for family in unit.families:
            for task in family.qualification:
                for arm in ("learned", "fresh", "placebo"):
                    payloads.append(grader.submit({
                        "op": "submit", "unit_id": unit.unit_id, "arm": arm,
                        "stage": "qualification", "task_id": task.task_id,
                        "status": "accepted", "choice": "A",
                    }).payload)
    final = grader.finalize({"op": "finalize"}).payload
    final["records"].pop()
    import hashlib

    final["records_sha256"] = hashlib.sha256(json.dumps(
        final["records"], sort_keys=True, separators=(",", ":")
    ).encode()).hexdigest()
    payloads.append(final)
    signer = _signer()
    signed = [signer.seal(p) for p in payloads]
    audited = audit_signed_transcript(
        signed, cohort, public_key_hex=signer.public_key_hex,
        expected_run_id=RUN_ID,
    )
    assert audited.status == "rejected_incomplete_or_invalid"
    assert "final_record_denominator_mismatch" in audited.errors
