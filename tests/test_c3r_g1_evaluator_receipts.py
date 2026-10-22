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
