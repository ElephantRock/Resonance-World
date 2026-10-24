"""C3R G1 witnessed journal: enrollment-first, signed append and audit."""

from __future__ import annotations

import copy
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
from resonance_world.c3r_g1_model_boundary import ModelChoiceCompletion
from resonance_world.c3r_g1_multischema import V2Design
from resonance_world.c3r_g1_sealed_evaluator import SealedEvaluator
from resonance_world.c3r_g1_sealed_runner import SealedPilotRunner
from resonance_world.c3r_g1_witness_journal import (
    JournaledEvaluatorSession,
    WitnessJournal,
    audit_witness_journal,
)
from resonance_world.c3r_g1_witnessed_lock import WitnessSigner

RUN = "g1-journal-fixture-20261022"
EVAL_TARGET = bytes.fromhex("19" * 32)
EVAL_SIGN = bytes.fromhex("29" * 32)
WITNESS_SIGN = bytes.fromhex("39" * 32)
NOW = datetime(2026, 10, 22, 12, 0, tzinfo=UTC)


class _ConstantPort:
    def complete(self, _request):
        return ModelChoiceCompletion("A", "offline-schema-fixture")


class _SignedTransport:
    def __init__(self, evaluator, signer):
        self.evaluator = evaluator
        self.signer = signer

    def ready(self):
        return self.signer.seal(self.evaluator.ready().payload)

    def submit(self, request):
        return self.signer.seal(self.evaluator.submit(request).payload)

    def finalize(self):
        return self.signer.seal(self.evaluator.finalize({"op": "finalize"}).payload)


def _components():
    design = V2Design(units=1, development_per_family=1, qualification_per_family=1)
    cohort = design.freeze()
    evaluator = SealedEvaluator(cohort, private_key=EVAL_TARGET)
    signer = ReceiptSigner(EVAL_SIGN, run_id=RUN)
    witness = WitnessSigner(WITNESS_SIGN)
    admitted = witness.sign_lock(
        run_id=RUN, cohort=cohort,
        evaluator_public_key_hex=signer.public_key_hex,
        target_commitment=evaluator.ready().payload["target_commitment"],
        issued_at_utc="2026-10-22T11:00:00Z",
        expires_at_utc="2026-10-23T11:00:00Z",
    )
    return cohort, evaluator, signer, witness, admitted


def _execute(path: Path):
    cohort, evaluator, signer, witness, admitted = _components()
    signed = VerifiedEvaluatorSession(
        _SignedTransport(evaluator, signer),
        ReceiptVerifier(signer.public_key_hex, expected_run_id=RUN),
    )
    with WitnessJournal(
        path, witness_seed=WITNESS_SIGN, signed_lock=admitted,
        cohort=cohort, evaluator_public_hex=signer.public_key_hex,
        run_id=RUN, now_utc=NOW,
    ) as journal:
        wrapped = JournaledEvaluatorSession(signed, journal)
        result = SealedPilotRunner(cohort, wrapped).run(
            port_factory=lambda _uid, _arm, _stage: _ConstantPort()
        )
        assert result.to_dict()["scientific_acceptance"] is False
        assert journal.event_count == cohort.design.logical_calls + 3
    events = [json.loads(line) for line in path.read_text().splitlines()]
    return cohort, signer, witness, admitted, events


def _audit(events, cohort, signer, witness):
    return audit_witness_journal(
        events, cohort,
        witness_public_hex=witness.public_key_hex,
        evaluator_public_hex=signer.public_key_hex,
        run_id=RUN, now_utc=NOW,
    )


def test_signed_complete_journal_lock_precedes_all_trials(tmp_path: Path) -> None:
    cohort, signer, witness, admission, events = _execute(tmp_path / "journal.jsonl")
    assert len(events) == 11
    assert events[0]["kind"] == "enrollment"
    assert events[0]["payload"] == admission
    assert events[1]["payload"]["payload"]["phase"] == "accept_development"
    assert events[-1]["payload"]["payload"]["schema"] == (
        "c3r-g1-evaluator-final-v0.1"
    )
    result = _audit(events, cohort, signer, witness)
    assert result.verdict == "signed_structural_chain"
    assert result.event_count == 11
    assert result.to_dict()["trusted_timestamp_attested"] is False
    assert result.to_dict()["scientific_acceptance"] is False
    assert events[-1]["payload"]["payload"]["scientific_acceptance"] is False
    assert EVAL_TARGET.hex() not in json.dumps(events)
    assert WITNESS_SIGN.hex() not in json.dumps(events)


@pytest.mark.parametrize("change", [
    "remove_first", "remove_middle", "swap", "change_grade",
    "append_duplicate", "change_target", "change_chain", "change_run",
])
def test_tamper_or_missing_event_is_rejected(tmp_path: Path, change: str) -> None:
    cohort, signer, witness, _, original = _execute(tmp_path / "journal.jsonl")
    events = copy.deepcopy(original)
    if change == "remove_first":
        events.pop(0)
    elif change == "remove_middle":
        events.pop(3)
    elif change == "swap":
        events[2], events[3] = events[3], events[2]
    elif change == "change_grade":
        item = events[-1]["payload"]["payload"]["records"][0]
        item["success"] = not item["success"]
    elif change == "append_duplicate":
        events.append(copy.deepcopy(events[-1]))
    elif change == "change_target":
        events[0]["payload"]["target_commitment"] = "0" * 64
    elif change == "change_chain":
        events[4]["prior_sha256"] = "1" * 64
    elif change == "change_run":
        events[2]["run_id"] = "wrong-run-fixture-20261022"
    assert _audit(events, cohort, signer, witness).verdict == "rejected"


def test_exclusive_creation_and_owner_only_private_directory(tmp_path: Path) -> None:
    cohort, _evaluator, signer, _witness, admitted = _components()
    path = tmp_path / "once.jsonl"
    tmp_path.chmod(0o700)
    with WitnessJournal(
        path, witness_seed=WITNESS_SIGN, signed_lock=admitted,
        cohort=cohort, evaluator_public_hex=signer.public_key_hex,
        run_id=RUN, now_utc=NOW,
    ) as journal:
        assert journal.event_count == 1
        assert path.stat().st_mode & 0o777 == 0o600
        with pytest.raises(FileExistsError):
            WitnessJournal(
                path, witness_seed=WITNESS_SIGN, signed_lock=admitted,
                cohort=cohort, evaluator_public_hex=signer.public_key_hex,
                run_id=RUN, now_utc=NOW,
            )
    with pytest.raises(ValueError, match="closed"):
        journal.observe({})
    shared = tmp_path / "insecure"
    shared.mkdir(mode=0o777)
    shared.chmod(0o777)
    with pytest.raises(ValueError, match="private"):
        WitnessJournal(
            shared / "no.jsonl", witness_seed=WITNESS_SIGN,
            signed_lock=admitted, cohort=cohort,
            evaluator_public_hex=signer.public_key_hex,
            run_id=RUN, now_utc=NOW,
        )


def test_invalid_enrollment_refused_before_any_journal_created(
    tmp_path: Path,
) -> None:
    cohort, _evaluator, signer, _, admitted = _components()
    changed = dict(admitted, target_commitment="f" * 64)
    file = tmp_path / "no.jsonl"
    with pytest.raises(ValueError):
        WitnessJournal(
            file, witness_seed=WITNESS_SIGN,
            signed_lock=changed, cohort=cohort,
            evaluator_public_hex=signer.public_key_hex,
            run_id=RUN, now_utc=NOW,
        )
    assert not file.exists()
    with pytest.raises(ValueError, match="expired"):
        WitnessJournal(
            file, witness_seed=WITNESS_SIGN,
            signed_lock=admitted, cohort=cohort,
            evaluator_public_hex=signer.public_key_hex,
            run_id=RUN, now_utc=datetime(2026, 11, 1, tzinfo=UTC),
        )
    assert not file.exists()


def test_early_final_or_any_leaked_qualification_grade_fails_closed(
    tmp_path: Path,
) -> None:
    cohort, evaluator, signer, _witness, admitted = _components()
    file = tmp_path / "part.jsonl"
    with WitnessJournal(
        file, witness_seed=WITNESS_SIGN, signed_lock=admitted,
        cohort=cohort, evaluator_public_hex=signer.public_key_hex,
        run_id=RUN, now_utc=NOW,
    ) as journal:
        signed = signer.seal(evaluator.ready().payload)
        journal.observe(signed)
        bad = signer.seal({
            "schema": "c3r-g1-evaluator-v0.1",
            "phase": "qualification_sealed",
            "task_id": "holdout-000-arithmetic-00",
            "qualification_received": 1,
            "grade": True,
        })
        with pytest.raises(ValueError, match="development"):
            journal.observe(bad)
        assert journal.event_count == 2
    assert len(file.read_text().splitlines()) == 2


def test_offline_auditor_rejects_wrong_pinned_witness_key(
    tmp_path: Path,
) -> None:
    cohort, signer, witness, _, events = _execute(tmp_path / "journal.jsonl")
    wrong = WitnessSigner(bytes.fromhex("99" * 32))
    assert audit_witness_journal(
        events, cohort, witness_public_hex=wrong.public_key_hex,
        evaluator_public_hex=signer.public_key_hex,
        run_id=RUN, now_utc=NOW,
    ).verdict == "rejected"
    assert _audit(events, cohort, signer, witness).verdict == "signed_structural_chain"



def test_read_only_cli_checks_full_journal_with_only_pinned_public_keys(
    tmp_path: Path,
) -> None:
    cohort, signer, witness, _, events = _execute(tmp_path / "journal.jsonl")
    witness_public = tmp_path / "witness-public.hex"
    evaluator_public = tmp_path / "evaluator-public.hex"
    witness_public.write_text(witness.public_key_hex + "\n", encoding="ascii")
    evaluator_public.write_text(signer.public_key_hex + "\n", encoding="ascii")
    args = [
        sys.executable, "-m", "resonance_world.c3r_g1_witness_journal",
        str(tmp_path / "journal.jsonl"),
        "--witness-public", str(witness_public),
        "--evaluator-public", str(evaluator_public),
        "--run-id", RUN,
        "--admission-utc", "2026-10-22T12:00:00Z",
        "--units", "1", "--development", "1", "--qualification", "1",
    ]
    success = subprocess.run(
        args, text=True, capture_output=True, timeout=15,
        cwd=Path(__file__).resolve().parents[1], check=False,
    )
    assert success.returncode == 0
    assert json.loads(success.stdout)["verdict"] == "signed_structural_chain"
    assert json.loads(success.stdout)["scientific_acceptance"] is False
    assert json.loads(success.stdout)["trusted_timestamp_attested"] is False
    assert len(events) == cohort.design.logical_calls + 3

    expired_args = args.copy()
    expired_args[11] = "2026-11-15T12:00:00Z"
    expired = subprocess.run(
        expired_args,
        text=True, capture_output=True, timeout=15,
        cwd=Path(__file__).resolve().parents[1], check=False,
    )
    assert expired.returncode == 2
    assert json.loads(expired.stdout)["scientific_acceptance"] is False

    witness_public.write_text("11" * 32, encoding="ascii")
    forged = subprocess.run(
        args, text=True, capture_output=True, timeout=15,
        cwd=Path(__file__).resolve().parents[1], check=False,
    )
    assert forged.returncode == 2
    assert json.loads(forged.stdout)["verdict"] == "rejected"
