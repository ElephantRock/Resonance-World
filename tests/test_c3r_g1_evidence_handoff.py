"""Public-key evidence handoff: no secrets or externally attested claims."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

from resonance_world.c3r_g1_evaluator_receipts import (
    ReceiptSigner,
    ReceiptVerifier,
    VerifiedEvaluatorSession,
)
from resonance_world.c3r_g1_evidence_handoff import (
    JOURNAL_NAME,
    MANIFEST_NAME,
    prepare_handoff,
    verify_handoff,
)
from resonance_world.c3r_g1_model_boundary import ModelChoiceCompletion
from resonance_world.c3r_g1_multischema import V2Design
from resonance_world.c3r_g1_sealed_evaluator import SealedEvaluator
from resonance_world.c3r_g1_sealed_runner import SealedPilotRunner
from resonance_world.c3r_g1_witness_journal import (
    JournaledEvaluatorSession,
    WitnessJournal,
)
from resonance_world.c3r_g1_witnessed_lock import WitnessSigner

RUN = "g1-public-handoff-fixture"
STAMP = "2026-10-22T12:00:00Z"
NOW = datetime(2026, 10, 22, 12, tzinfo=UTC)
WITNESS_SEED = bytes.fromhex("ab" * 32)
EVALUATOR_SIGNING_SEED = bytes.fromhex("bc" * 32)
EVALUATOR_TARGET_SEED = bytes.fromhex("cd" * 32)


class _Transport:
    def __init__(self, grader, signer):
        self.grader = grader
        self.signer = signer

    def ready(self):
        return self.signer.seal(self.grader.ready().payload)

    def submit(self, request):
        return self.signer.seal(self.grader.submit(request).payload)

    def finalize(self):
        return self.signer.seal(self.grader.finalize({"op": "finalize"}).payload)


class _Constant:
    def complete(self, _request):
        return ModelChoiceCompletion("A", "offline-schema-fixture")


def _source(tmp_path: Path):
    cohort = V2Design(
        units=1, development_per_family=1, qualification_per_family=1
    ).freeze()
    grader = SealedEvaluator(cohort, private_key=EVALUATOR_TARGET_SEED)
    signer = ReceiptSigner(EVALUATOR_SIGNING_SEED, run_id=RUN)
    witness = WitnessSigner(WITNESS_SEED)
    admission = witness.sign_lock(
        run_id=RUN, cohort=cohort,
        evaluator_public_key_hex=signer.public_key_hex,
        target_commitment=grader.ready().payload["target_commitment"],
        issued_at_utc="2026-10-22T11:00:00Z",
        expires_at_utc="2026-10-23T11:00:00Z",
    )
    session = VerifiedEvaluatorSession(
        _Transport(grader, signer),
        ReceiptVerifier(signer.public_key_hex, expected_run_id=RUN),
    )
    journal = tmp_path / "journal-source.jsonl"
    with WitnessJournal(
        journal, witness_seed=WITNESS_SEED, signed_lock=admission,
        cohort=cohort, evaluator_public_hex=signer.public_key_hex,
        run_id=RUN, now_utc=NOW,
    ) as writer:
        SealedPilotRunner(
            cohort, JournaledEvaluatorSession(session, writer)
        ).run(port_factory=lambda _u, _a, _stage: _Constant())
    return journal, cohort, signer.public_key_hex, witness.public_key_hex


def _verify(dest, cohort, evaluator, witness):
    return verify_handoff(
        dest, cohort, witness_public_hex=witness,
        evaluator_public_hex=evaluator, run_id=RUN, admission_utc=STAMP,
    )


def test_verified_journal_exports_exactly_two_credential_free_files(
    tmp_path: Path,
) -> None:
    source, cohort, evaluator, witness = _source(tmp_path)
    dest = tmp_path / "bundle"
    result = prepare_handoff(
        source, dest, cohort, witness_public_hex=witness,
        evaluator_public_hex=evaluator, run_id=RUN, admission_utc=STAMP,
    )
    assert {p.name for p in dest.iterdir()} == {JOURNAL_NAME, MANIFEST_NAME}
    assert (dest / JOURNAL_NAME).read_bytes() == source.read_bytes()
    assert result["journal_signed_events"] == cohort.design.logical_calls + 3 == 11
    assert result["state"] == "local_export_not_externally_deposited"
    assert result["scientific_acceptance"] is False
    assert result["external_custodian_receipt"] is None
    assert (dest / MANIFEST_NAME).stat().st_mode & 0o777 == 0o600
    verdict = _verify(dest, cohort, evaluator, witness).to_dict()
    assert verdict["verdict"] == "public_key_verified_not_external_custody"
    assert verdict["external_custodian_receipt_verified"] is False
    assert verdict["scientific_acceptance"] is False
    serialized = json.dumps(result)
    assert WITNESS_SEED.hex() not in serialized
    assert EVALUATOR_TARGET_SEED.hex() not in serialized
    assert EVALUATOR_SIGNING_SEED.hex() not in serialized


def test_modified_manifest_journal_or_extra_file_rejected(tmp_path: Path) -> None:
    source, cohort, evaluator, witness = _source(tmp_path)
    dest = tmp_path / "bundle"
    prepare_handoff(
        source, dest, cohort, witness_public_hex=witness,
        evaluator_public_hex=evaluator, run_id=RUN, admission_utc=STAMP,
    )
    manifest_path = dest / MANIFEST_NAME
    manifest = json.loads(manifest_path.read_bytes())
    manifest["external_custodian_receipt"] = "pretend-ack"
    manifest_path.write_text(json.dumps(manifest))
    assert _verify(dest, cohort, evaluator, witness).verdict == "rejected"
    manifest["external_custodian_receipt"] = None
    manifest_path.write_text(json.dumps(manifest))
    assert _verify(dest, cohort, evaluator, witness).verdict == (
        "public_key_verified_not_external_custody"
    )
    journal = dest / JOURNAL_NAME
    original = journal.read_bytes()
    journal.write_bytes(original.replace(b'"accepted":true', b'"accepted":false', 1))
    assert _verify(dest, cohort, evaluator, witness).verdict == "rejected"
    journal.write_bytes(original)
    (dest / "unexpected-private.json").write_text("{}")
    assert _verify(dest, cohort, evaluator, witness).verdict == "rejected"


def test_reject_duplicate_destination_symlink_and_wrong_public_key(
    tmp_path: Path,
) -> None:
    source, cohort, evaluator, witness = _source(tmp_path)
    dest = tmp_path / "bundle"
    kwargs = {
        "witness_public_hex": witness, "evaluator_public_hex": evaluator,
        "run_id": RUN, "admission_utc": STAMP,
    }
    prepare_handoff(source, dest, cohort, **kwargs)
    with pytest.raises(ValueError, match="destination"):
        prepare_handoff(source, dest, cohort, **kwargs)
    wrong = WitnessSigner(bytes.fromhex("88" * 32)).public_key_hex
    assert verify_handoff(
        dest, cohort, witness_public_hex=wrong,
        evaluator_public_hex=evaluator, run_id=RUN, admission_utc=STAMP,
    ).verdict == "rejected"
    alias = tmp_path / "link"
    alias.symlink_to(source)
    with pytest.raises(ValueError, match="nonsymlink"):
        prepare_handoff(alias, tmp_path / "another", cohort, **kwargs)


def test_read_only_bundle_cli_accepts_valid_and_rejects_wrong_key(
    tmp_path: Path,
) -> None:
    source, cohort, evaluator, witness = _source(tmp_path)
    public_a = tmp_path / "witness.pub"
    public_b = tmp_path / "grader.pub"
    public_a.write_text(witness + "\n")
    public_b.write_text(evaluator + "\n")
    dest = tmp_path / "bundle"
    common = [
        "--witness-public", str(public_a),
        "--evaluator-public", str(public_b),
        "--run-id", RUN, "--admission-utc", STAMP,
        "--units", "1", "--development", "1", "--qualification", "1",
    ]
    root = Path(__file__).resolve().parents[1]
    command = [sys.executable, "-m", "resonance_world.c3r_g1_evidence_handoff"]
    prepare = subprocess.run(
        [*command, "prepare", str(source), "--destination", str(dest), *common],
        cwd=root, capture_output=True, text=True, check=False, timeout=15,
    )
    assert prepare.returncode == 0
    assert json.loads(prepare.stdout)["scientific_acceptance"] is False
    verify = subprocess.run(
        [*command, "verify", str(dest), *common],
        cwd=root, capture_output=True, text=True, check=False, timeout=15,
    )
    assert verify.returncode == 0
    assert json.loads(verify.stdout)["verdict"] == (
        "public_key_verified_not_external_custody"
    )
    public_a.write_text("00" * 32 + "\n")
    rejected = subprocess.run(
        [*command, "verify", str(dest), *common],
        cwd=root, capture_output=True, text=True, check=False, timeout=15,
    )
    assert rejected.returncode == 2
    assert json.loads(rejected.stdout)["scientific_acceptance"] is False
    assert cohort.design.logical_calls == 8
