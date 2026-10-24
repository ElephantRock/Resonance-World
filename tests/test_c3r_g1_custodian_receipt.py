"""Detached custody receipt: local simulation only, no provider or external WORM."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

from resonance_world.c3r_g1_custodian_receipt import (
    ARCHIVE_DIR,
    RECEIPT_NAME,
    LocalCustodianFixture,
    verify_custodian_receipt,
)
from resonance_world.c3r_g1_evaluator_receipts import (
    ReceiptSigner,
    ReceiptVerifier,
    VerifiedEvaluatorSession,
)
from resonance_world.c3r_g1_evidence_handoff import (
    JOURNAL_NAME,
    MANIFEST_NAME,
    prepare_handoff,
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

RUN = "g1-custodian-sim-20261022"
CUSTODIAN_ID = "fixture-custodian-01"
STAMP = "2026-10-22T12:00:00Z"
RECEIVED = "2026-10-22T13:00:00Z"
COHORT = V2Design(
    units=1, development_per_family=1, qualification_per_family=1,
).freeze()
WITNESS_SEED = bytes.fromhex("a1" * 32)
EVAL_TARGET_SEED = bytes.fromhex("b2" * 32)
EVAL_SIGN_SEED = bytes.fromhex("c3" * 32)
CUSTODIAN_SEED = bytes.fromhex("d4" * 32)


class _Null:
    def complete(self, _request):
        return ModelChoiceCompletion("A", "offline-schema-fixture")


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


def _bundle(tmp_path: Path):
    grader = SealedEvaluator(COHORT, private_key=EVAL_TARGET_SEED)
    signer = ReceiptSigner(EVAL_SIGN_SEED, run_id=RUN)
    witness = WitnessSigner(WITNESS_SEED)
    admission = witness.sign_lock(
        run_id=RUN, cohort=COHORT,
        evaluator_public_key_hex=signer.public_key_hex,
        target_commitment=grader.ready().payload["target_commitment"],
        issued_at_utc="2026-10-22T11:00:00Z",
        expires_at_utc="2026-10-23T11:00:00Z",
    )
    verified = VerifiedEvaluatorSession(
        _Transport(grader, signer),
        ReceiptVerifier(signer.public_key_hex, expected_run_id=RUN),
    )
    source = tmp_path / "journal.jsonl"
    with WitnessJournal(
        source, witness_seed=WITNESS_SEED,
        signed_lock=admission, cohort=COHORT,
        evaluator_public_hex=signer.public_key_hex,
        run_id=RUN, now_utc=datetime(2026, 10, 22, 12, tzinfo=UTC),
    ) as journal:
        SealedPilotRunner(
            COHORT, JournaledEvaluatorSession(verified, journal)
        ).run(port_factory=lambda _unit, _arm, _stage: _Null())
    bundle = tmp_path / "handoff"
    prepare_handoff(
        source, bundle, COHORT,
        witness_public_hex=witness.public_key_hex,
        evaluator_public_hex=signer.public_key_hex,
        run_id=RUN, admission_utc=STAMP,
    )
    return bundle, witness.public_key_hex, signer.public_key_hex


def _setup(tmp_path: Path):
    bundle, witness, evaluator = _bundle(tmp_path)
    root = tmp_path / "custodian-inbox"
    root.mkdir(mode=0o700)
    fixture = LocalCustodianFixture(
        root, custodian_seed=CUSTODIAN_SEED, custodian_id=CUSTODIAN_ID,
    )
    entry = fixture.receive(
        bundle, COHORT, witness_public_hex=witness,
        evaluator_public_hex=evaluator, run_id=RUN,
        admission_utc=STAMP, claimed_received_at_utc=RECEIVED,
    )
    return bundle, witness, evaluator, fixture, entry


def _audit(entry, witness, evaluator, custodian, run_id=RUN):
    return verify_custodian_receipt(
        entry, COHORT,
        witness_public_hex=witness, evaluator_public_hex=evaluator,
        custodian_public_hex=custodian,
        expected_custodian_id=CUSTODIAN_ID,
        run_id=run_id, admission_utc=STAMP,
    )


def test_signed_archived_copy_is_verifiable_without_private_keys(tmp_path: Path):
    bundle, witness, evaluator, fixture, entry = _setup(tmp_path)
    assert bundle != entry / ARCHIVE_DIR
    assert (entry / ARCHIVE_DIR / JOURNAL_NAME).read_bytes() == (
        bundle / JOURNAL_NAME
    ).read_bytes()
    assert (entry / ARCHIVE_DIR / MANIFEST_NAME).read_bytes() == (
        bundle / MANIFEST_NAME
    ).read_bytes()
    receipt = json.loads((entry / RECEIPT_NAME).read_bytes())
    assert receipt["status"] == "local_custodian_fixture_not_external_custody"
    assert receipt["immutable_retention_verified"] is False
    assert receipt["independent_operator_verified"] is False
    assert receipt["trusted_timestamp_verified"] is False
    assert receipt["scientific_acceptance"] is False
    outcome = _audit(entry, witness, evaluator, fixture.public_hex)
    assert outcome.verdict == "signed_local_archive_consistent_unattested"
    assert outcome.to_dict()["signature_and_archive_match"] is True
    assert outcome.to_dict()["external_deposit_attested"] is False
    assert outcome.to_dict()["scientific_acceptance"] is False
    payload = (entry / RECEIPT_NAME).read_bytes()
    assert CUSTODIAN_SEED.hex().encode() not in payload
    assert EVAL_TARGET_SEED.hex().encode() not in payload
    assert WITNESS_SEED.hex().encode() not in payload


@pytest.mark.parametrize("attack", [
    "forge_status", "forge_timestamp", "forge_custodian",
    "forge_retention", "forge_signature", "forge_journal",
    "remove_manifest", "extra_artifact", "wrong_reference",
])
def test_changed_receipt_or_archived_evidence_is_rejected(
    tmp_path: Path, attack: str,
):
    _bundle, witness, evaluator, fixture, entry = _setup(tmp_path)
    receipt_path = entry / RECEIPT_NAME
    archived_journal = entry / ARCHIVE_DIR / JOURNAL_NAME
    archived_manifest = entry / ARCHIVE_DIR / MANIFEST_NAME
    receipt = json.loads(receipt_path.read_bytes())
    if attack == "forge_status":
        receipt["status"] = "externally_attested_worm"
    elif attack == "forge_timestamp":
        receipt["claimed_received_at_utc"] = "2026-10-23T13:00:00Z"
    elif attack == "forge_custodian":
        receipt["custodian_id"] = "evil-custodian-01"
    elif attack == "forge_retention":
        receipt["immutable_retention_verified"] = True
    elif attack == "forge_signature":
        receipt["signature"] = "aa" * 64
    elif attack == "wrong_reference":
        receipt["archive_reference"] = "f" * 64
    elif attack == "forge_journal":
        original = archived_journal.read_bytes()
        archived_journal.write_bytes(original.replace(
            b'"accepted":true', b'"accepted":false', 1
        ))
    elif attack == "remove_manifest":
        archived_manifest.unlink()
    else:
        (entry / "unregistered.file").write_text("bad")
    if attack.startswith("forge_") and attack != "forge_journal" or (
        attack == "wrong_reference"
    ):
        receipt_path.write_text(json.dumps(receipt, sort_keys=True))
    assert _audit(entry, witness, evaluator, fixture.public_hex).verdict == "rejected"


def test_two_custody_signers_and_wrong_run_are_not_interchangeable(tmp_path: Path):
    _, witness, evaluator, fixture, entry = _setup(tmp_path)
    other = LocalCustodianFixture(
        tmp_path / "custodian-inbox", custodian_seed=bytes.fromhex("e5" * 32),
        custodian_id=CUSTODIAN_ID,
    )
    assert _audit(entry, witness, evaluator, other.public_hex).verdict == "rejected"
    assert _audit(
        entry, witness, evaluator, fixture.public_hex,
        run_id="g1-custodian-sim-other",
    ).verdict == "rejected"
    assert verify_custodian_receipt(
        entry, COHORT, witness_public_hex=witness,
        evaluator_public_hex=evaluator, custodian_public_hex=fixture.public_hex,
        expected_custodian_id="unregistered-custodian", run_id=RUN,
        admission_utc=STAMP,
    ).verdict == "rejected"


def test_no_run_id_reuse_or_preceding_admission(tmp_path: Path):
    bundle, witness, evaluator, fixture, entry = _setup(tmp_path)
    assert entry.exists()
    with pytest.raises(FileExistsError):
        fixture.receive(
            bundle, COHORT, witness_public_hex=witness,
            evaluator_public_hex=evaluator, run_id=RUN,
            admission_utc=STAMP, claimed_received_at_utc=RECEIVED,
        )
    other_root = tmp_path / "second-inbox"
    other_root.mkdir(mode=0o700)
    other = LocalCustodianFixture(
        other_root, custodian_seed=CUSTODIAN_SEED, custodian_id=CUSTODIAN_ID,
    )
    with pytest.raises(ValueError, match="precedes"):
        other.receive(
            bundle, COHORT, witness_public_hex=witness,
            evaluator_public_hex=evaluator, run_id=RUN,
            admission_utc=STAMP,
            claimed_received_at_utc="2026-10-22T11:00:00Z",
        )


def test_reject_custodian_key_reused_as_witness(tmp_path: Path):
    bundle, witness, evaluator, _fixture, _entry = _setup(tmp_path)
    root = tmp_path / "reuse"
    root.mkdir(mode=0o700)
    reuse = LocalCustodianFixture(
        root, custodian_seed=WITNESS_SEED, custodian_id=CUSTODIAN_ID,
    )
    assert reuse.public_hex == witness
    with pytest.raises(ValueError, match="distinct"):
        reuse.receive(
            bundle, COHORT, witness_public_hex=witness,
            evaluator_public_hex=evaluator, run_id=RUN,
            admission_utc=STAMP, claimed_received_at_utc=RECEIVED,
        )


def test_custodian_receipt_cli_verifies_only_with_out_of_band_public_key(
    tmp_path: Path,
):
    _, witness, evaluator, fixture, entry = _setup(tmp_path)
    witness_path = tmp_path / "witness.pub"
    evaluator_path = tmp_path / "evaluator.pub"
    custodian_path = tmp_path / "custodian.pub"
    witness_path.write_text(witness)
    evaluator_path.write_text(evaluator)
    custodian_path.write_text(fixture.public_hex)
    argv = [
        sys.executable, "-m", "resonance_world.c3r_g1_custodian_receipt",
        str(entry), "--witness-public", str(witness_path),
        "--evaluator-public", str(evaluator_path),
        "--custodian-public", str(custodian_path),
        "--custodian-id", CUSTODIAN_ID, "--run-id", RUN,
        "--admission-utc", STAMP,
        "--units", "1", "--development", "1", "--qualification", "1",
    ]
    success = subprocess.run(
        argv, cwd=Path(__file__).resolve().parents[1],
        text=True, capture_output=True, timeout=15, check=False,
    )
    assert success.returncode == 0, success.stderr
    assert json.loads(success.stdout)["scientific_acceptance"] is False
    assert json.loads(success.stdout)["verdict"] == (
        "signed_local_archive_consistent_unattested"
    )
    custodian_path.write_text("00" * 32)
    rejected = subprocess.run(
        argv, cwd=Path(__file__).resolve().parents[1],
        text=True, capture_output=True, timeout=15, check=False,
    )
    assert rejected.returncode == 2
    assert json.loads(rejected.stdout)["scientific_acceptance"] is False


def test_parent_permissions_and_invalid_source_fail_before_archive(tmp_path: Path):
    bundle, witness, evaluator, _fixture, _entry = _setup(tmp_path)
    world = tmp_path / "insecure-root"
    world.mkdir(mode=0o777)
    world.chmod(0o777)
    with pytest.raises(ValueError, match="private"):
        LocalCustodianFixture(
            world, custodian_seed=CUSTODIAN_SEED,
            custodian_id=CUSTODIAN_ID,
        )
    safe = tmp_path / "safe"
    safe.mkdir(mode=0o700)
    fixture = LocalCustodianFixture(
        safe, custodian_seed=CUSTODIAN_SEED, custodian_id=CUSTODIAN_ID,
    )
    malformed = tmp_path / "tampered"
    malformed.mkdir(mode=0o700)
    (malformed / "something.json").write_text("{}")
    with pytest.raises(ValueError, match="source bundle"):
        fixture.receive(
            malformed, COHORT, witness_public_hex=witness,
            evaluator_public_hex=evaluator, run_id=RUN,
            admission_utc=STAMP, claimed_received_at_utc=RECEIVED,
        )
    assert list(safe.iterdir()) == []
