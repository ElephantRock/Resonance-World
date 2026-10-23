"""Negative/positive evidence-handoff tests; all signatures are local toy fixtures."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from resonance_world.c3r_g1_crossed_enrollment import _digest
from resonance_world.c3r_g1_crossed_external_handoff import verify_external_handoff
from resonance_world.c3r_g1_crossed_plan import make_plan
from resonance_world.c3r_g1_evaluator_receipts import ReceiptSigner

RUN = "g1x-archive-handoff-fixture"
AT = datetime.now(UTC)


def _fixture():
    plan = make_plan()
    seeds = [os.urandom(32) for _ in range(4)]
    eva, cus, wit, arc = [ReceiptSigner(seed, run_id=RUN) for seed in seeds]
    enrollment = wit.seal({
        "schema": "c3r-g1-crossed-enrollment-v0.1",
        "plan_digest": plan.public_digest,
        "evaluator_public_key_hex": eva.public_key_hex,
        "custodian_public_key_hex": cus.public_key_hex,
        "development_attempts": 16,
        "qualification_attempts": 24,
        "claimed_issued_at_utc": (AT - timedelta(minutes=30)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "claimed_expires_at_utc": (AT + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "provider_sends_authorized": False,
        "external_witness_attested": False,
        "trusted_timestamp_attested": False,
        "scientific_acceptance": False,
    })
    receipts = []
    for i, slot in enumerate(plan.schedule):
        is_last = i == 39
        receipts.append(eva.seal({
            "schema": "c3r-g1-crossed-attempt-v0.1",
            "plan_digest": plan.public_digest,
            "slot_index": i,
            "unit_id": slot.unit_id,
            "task_id": slot.task_id,
            "stage": slot.stage,
            "arm": slot.arm,
            "status": "not_sent" if is_last else "accepted",
            "action": None if is_last else "A",
            "correct": None if is_last else i % 3 == 0,
            "output_sha256": None if is_last else hashlib.sha256(
                f"fixture-{i}".encode()
            ).hexdigest(),
        }))
    source_head = _digest(receipts[15])
    custody = cus.seal({
        "schema": "c3r-g1-crossed-source-custody-v0.1",
        "plan_digest": plan.public_digest,
        "source_chain_head_sha256": source_head,
        "evaluator_public_key_sha256": hashlib.sha256(
            bytes.fromhex(eva.public_key_hex)
        ).hexdigest(),
        "source_receipt_count": 16,
        "independent_custody_attested": False,
        "trusted_time_attested": False,
        "scientific_acceptance": False,
    })
    checkpoint = wit.seal({
        "schema": "c3r-g1-crossed-witness-checkpoint-v0.1",
        "plan_digest": plan.public_digest,
        "enrollment_sha256": _digest(enrollment),
        "source_chain_head_sha256": source_head,
        "custodian_receipt_sha256": _digest(custody),
        "development_attempts": 16,
        "qualification_attempts": 24,
        "claimed_checkpoint_at_utc": (AT - timedelta(minutes=25)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "external_witness_attested": False,
        "trusted_timestamp_attested": False,
        "external_immutable_deposit_attested": False,
        "provider_sends_authorized": False,
        "scientific_acceptance": False,
    })
    manifest = {
        "schema": "c3r-g1-crossed-source-manifest-v0.1",
        "run_id": RUN,
        "plan_digest": plan.public_digest,
        "enrollment_sha256": _digest(enrollment),
        "source_receipts_sha256": _digest(receipts[:16]),
        "source_chain_head_sha256": source_head,
        "custodian_deposit_sha256": _digest(custody),
        "witness_checkpoint_sha256": _digest(checkpoint),
    }
    archive = arc.seal({
        "schema": "c3r-g1-crossed-archive-receipt-v0.1",
        "manifest_sha256": _digest(manifest),
        "source_chain_head_sha256": source_head,
        "witness_checkpoint_sha256": _digest(checkpoint),
        "source_attempts": 16,
        "claimed_received_at_utc": (AT - timedelta(minutes=20)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "independent_archive_custody_attested": False,
        "trusted_timestamp_attested": False,
        "immutable_remote_retention_attested": False,
        "scientific_acceptance": False,
    })
    bundle = {
        "schema": "c3r-g1-crossed-handoff-v0.1",
        "enrollment": enrollment,
        "source_receipts": receipts[:16],
        "custodian_deposit": custody,
        "witness_checkpoint": checkpoint,
        "archive_receipt": archive,
    }
    keys = [s.public_key_hex for s in (eva, cus, wit, arc)]
    return bundle, receipts, keys, seeds


def _check(bundle, keys, *, mode="source", pin=None, run_id=RUN, now=AT):
    return verify_external_handoff(
        bundle, mode=mode, expected_run_id=run_id,
        pinned_evaluator_public_key_hex=keys[0],
        pinned_custodian_public_key_hex=keys[1],
        pinned_witness_public_key_hex=keys[2],
        pinned_archive_public_key_hex=keys[3],
        claimed_clock_check_utc=now,
        expected_prior_archive_receipt_sha256=pin,
    )


def test_source_manifest_and_archive_signature_verified_without_promotion():
    bundle, _records, keys, _ = _fixture()
    report = _check(bundle, keys)
    assert report.verified_logical_attempts == 16
    assert report.mode == "source"
    assert report.archive_receipt_sha256 == _digest(bundle["archive_receipt"])
    assert report.to_dict()["external_archive_key_ownership_attested"] is False
    assert report.to_dict()["scientific_acceptance"] is False


def test_terminal_reuses_externally_retained_source_archive_fingerprint():
    bundle, records, keys, _ = _fixture()
    prior_pin = _check(bundle, keys).archive_receipt_sha256
    full = {**bundle, "terminal_receipts": records}
    terminal = _check(full, keys, mode="terminal", pin=prior_pin)
    assert terminal.verified_logical_attempts == 40
    assert terminal.to_dict()["archive_receipt_reused_from_prior_source_verification"]
    assert terminal.to_dict()["source_received_before_real_holdout_attested"] is False


def test_terminal_refuses_missing_prior_pin_or_changed_one():
    bundle, records, keys, _ = _fixture()
    full = {**bundle, "terminal_receipts": records}
    for pin in (None, "0" * 64):
        with pytest.raises(ValueError):
            _check(full, keys, mode="terminal", pin=pin)


def test_terminal_refuses_source_prefix_substitution_even_with_archive_receipt():
    bundle, records, keys, _ = _fixture()
    full = {**bundle, "terminal_receipts": records}
    full["terminal_receipts"] = [copy.deepcopy(r) for r in records]
    full["terminal_receipts"][3]["payload"]["correct"] = False
    with pytest.raises(ValueError):
        _check(full, keys, mode="terminal", pin=_digest(bundle["archive_receipt"]))


def test_tampered_source_or_wrong_archive_signature_rejected():
    bundle, _records, keys, _ = _fixture()
    altered = copy.deepcopy(bundle)
    altered["source_receipts"][3]["payload"]["correct"] = not altered[
        "source_receipts"
    ][3]["payload"]["correct"]
    with pytest.raises(ValueError):
        _check(altered, keys)
    with pytest.raises(ValueError):
        _check(bundle, [*keys[:3], keys[0]])
    with pytest.raises(ValueError):
        _check(bundle, [*keys[:3], ReceiptSigner(os.urandom(32), run_id=RUN).public_key_hex])


def test_valid_archive_signature_cannot_override_manifest_binding():
    bundle, _records, keys, seeds = _fixture()
    signer = ReceiptSigner(seeds[3], run_id=RUN)
    false_receipt = signer.seal({
        **bundle["archive_receipt"]["payload"],
        "manifest_sha256": "0" * 64,
    })
    with pytest.raises(ValueError, match="does not bind"):
        _check({**bundle, "archive_receipt": false_receipt}, keys)


def test_correctly_signed_wrong_counts_flags_or_private_fields_rejected():
    bundle, _records, keys, seeds = _fixture()
    for override in (
        {"source_attempts": True}, {"source_attempts": 15},
        {"scientific_acceptance": True}, {"private_target_map": "AABB"},
        {"trusted_timestamp_attested": True},
    ):
        signer = ReceiptSigner(seeds[3], run_id=RUN)
        archive = signer.seal({**bundle["archive_receipt"]["payload"], **override})
        with pytest.raises(ValueError):
            _check({**bundle, "archive_receipt": archive}, keys)


def test_time_claim_is_not_trusted_and_inconsistent_claim_is_rejected():
    bundle, _records, keys, seeds = _fixture()
    with pytest.raises(ValueError):
        _check(bundle, keys, now=AT - timedelta(hours=1))
    with pytest.raises(ValueError):
        _check(bundle, keys, now=AT.replace(tzinfo=None))
    signer = ReceiptSigner(seeds[3], run_id=RUN)
    archive = signer.seal({
        **bundle["archive_receipt"]["payload"],
        "claimed_received_at_utc": (AT - timedelta(minutes=29)).strftime("%Y-%m-%dT%H:%M:%SZ"),
    })
    with pytest.raises(ValueError, match="chronology"):
        _check({**bundle, "archive_receipt": archive}, keys)


def test_wrong_run_role_replay_or_extra_undocumented_evidence_rejected():
    bundle, records, keys, _ = _fixture()
    with pytest.raises(ValueError):
        _check(bundle, keys, run_id="g1x-different-project")
    with pytest.raises(ValueError):
        _check(bundle, [keys[1], keys[0], *keys[2:]])
    with pytest.raises(ValueError, match="unexpected fields"):
        _check({**bundle, "private_targets": "ABAB"}, keys)
    with pytest.raises(ValueError):
        _check({**bundle, "terminal_receipts": records}, keys, mode="source")


def test_absent_archive_or_extra_terminal_omission_rejected():
    bundle, records, keys, _ = _fixture()
    no_archive = {key: value for key, value in bundle.items() if key != "archive_receipt"}
    with pytest.raises(ValueError):
        _check(no_archive, keys)
    with pytest.raises(ValueError):
        _check({**bundle, "terminal_receipts": records[:-1]}, keys,
               mode="terminal", pin=_digest(bundle["archive_receipt"]))


def test_public_key_cli_verify_source_and_terminal_without_private_key_files(tmp_path):
    bundle, records, keys, _seeds = _fixture()
    bundle_file = tmp_path / "source.json"
    bundle_file.write_text(json.dumps(bundle))
    command = [
        sys.executable, "-m", "resonance_world.c3r_g1_crossed_external_handoff",
        "--bundle", str(bundle_file), "--mode", "source", "--run-id", RUN,
        "--evaluator-public-key-hex", keys[0],
        "--custodian-public-key-hex", keys[1],
        "--witness-public-key-hex", keys[2],
        "--archive-public-key-hex", keys[3],
    ]
    env = dict(os.environ)
    root = Path(__file__).resolve().parents[1] / "src"
    env["PYTHONPATH"] = str(root)
    source = subprocess.run(command, env=env, capture_output=True, text=True, check=True)
    parsed = json.loads(source.stdout)
    assert parsed["verified_logical_attempts"] == 16
    assert parsed["scientific_acceptance"] is False
    bundle_file.write_text(json.dumps({**bundle, "terminal_receipts": records}))
    terminal = subprocess.run([
        *command,
        "--previous-archive-receipt-sha256", parsed["archive_receipt_sha256"],
    ], env=env, capture_output=True, text=True, check=False)
    # Without switching the --mode from source to terminal the CLI fails closed.
    assert terminal.returncode == 2
    command[command.index("source")] = "terminal"
    final = subprocess.run([
        *command, "--previous-archive-receipt-sha256", parsed["archive_receipt_sha256"],
    ], env=env, capture_output=True, text=True, check=True)
    assert json.loads(final.stdout)["verified_logical_attempts"] == 40
