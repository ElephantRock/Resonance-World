"""Zero-provider staged issuer and custodian tests (never scientific attestation)."""

from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from resonance_world.c3r_g1_crossed_local_evaluator import CrossedLocalEvaluator
from resonance_world.c3r_g1_crossed_plan import make_plan
from resonance_world.c3r_g1_crossed_receipt_bridge import verify_crossed_receipt_chain
from resonance_world.c3r_g1_crossed_source_deposit import (
    deposit_source_receipts,
    verify_source_deposit,
)
from resonance_world.c3r_g1_evaluator_receipts import ReceiptSigner

RUN = "g1x-staged-local-only-20261022"


def _local_keys():
    private_custody = os.urandom(32)
    public_custody = ReceiptSigner(private_custody, run_id=RUN).public_key_hex
    evaluator = CrossedLocalEvaluator(
        run_id=RUN, private_target_seed=os.urandom(32),
        signing_seed=os.urandom(32),
        pinned_custodian_public_key_hex=public_custody,
    )
    return evaluator, private_custody, public_custody


def _source(evaluator):
    source_receipts = []
    for _ in range(16):
        response = evaluator.submit(status="accepted", choice="A")
        assert response["phase"] == "development_feedback"
        assert type(response["feedback"]) is bool
        source_receipts.append(response["signed_source_receipt"])
    freeze = evaluator.seal_source()
    assert freeze["source_receipt_count"] == 16
    return tuple(source_receipts), freeze["source_chain_head_sha256"]


def _issue_ack(evaluator, custody_seed, sources, destination):
    destination.mkdir(mode=0o700)
    return deposit_source_receipts(
        source_receipts=sources, expected_run_id=RUN,
        evaluator_public_key_hex=evaluator.evaluator_public_key_hex,
        custodian_private_seed=custody_seed,
        destination=destination,
    )


def test_signed_source_custody_gate_and_late_holdout_release(tmp_path) -> None:
    evaluator, custodian_seed, public = _local_keys()
    source, source_head = _source(evaluator)
    with pytest.raises(ValueError, match="before signed source custody"):
        evaluator.submit(status="accepted", choice="A")
    with pytest.raises(ValueError, match="before full 40-slot closure"):
        evaluator.finalize()
    acknowledgement, path = _issue_ack(evaluator, custodian_seed, source, tmp_path / "deposit")
    audit = verify_source_deposit(
        deposit=json.loads(path.read_text()), source_head=source_head,
        expected_run_id=RUN,
        evaluator_public_key_hex=evaluator.evaluator_public_key_hex,
        pinned_custodian_public_key_hex=public,
    )
    assert audit["custodian_operator_independence_attested"] is False
    assert path.stat().st_mode & 0o077 == 0
    assert evaluator.acknowledge_custody(acknowledgement)["scientific_acceptance"] is False
    for i in range(24):
        response = evaluator.submit(status="accepted", choice="B")
        assert response["phase"] == "qualification_sealed"
        assert response["qualification_received"] == i + 1
        assert "correct" not in json.dumps(response)
        assert "grade" not in json.dumps(response)
    terminal = evaluator.finalize()
    assert len(terminal["receipts"]) == 40
    assert terminal["source_chain_head_sha256"] == source_head
    assert terminal["audit"]["descriptive"]["prescribed_logical_attempts"] == 40
    assert terminal["scientific_acceptance"] is False
    assert terminal["actual_provider_sends"] == 0
    assert verify_crossed_receipt_chain(
        make_plan(), receipts=tuple(terminal["receipts"]), mode="terminal",
        expected_run_id=RUN,
        pinned_evaluator_public_key_hex=evaluator.evaluator_public_key_hex,
        expected_source_chain_head_sha256=source_head,
    ).audit["scientific_acceptance"] is False


def test_source_deposit_rejects_missing_receipt_and_double_write(tmp_path) -> None:
    evaluator, custody_seed, public = _local_keys()
    source, _ = _source(evaluator)
    with pytest.raises(ValueError):
        _issue_ack(evaluator, custody_seed, source[:-1], tmp_path / "missing")
    ack, path = _issue_ack(evaluator, custody_seed, source, tmp_path / "record")
    with pytest.raises(FileExistsError):
        _issue_ack(evaluator, custody_seed, source, tmp_path / "record")
    with pytest.raises(ValueError):
        verify_source_deposit(
            deposit=ack, source_head="0" * 64, expected_run_id=RUN,
            evaluator_public_key_hex=evaluator.evaluator_public_key_hex,
            pinned_custodian_public_key_hex=public,
        )
    assert path.stat().st_size > 0


def test_wrong_key_tamper_and_duplicate_ack_cannot_unlock(tmp_path) -> None:
    evaluator, custody_seed, _public = _local_keys()
    source, _ = _source(evaluator)
    ack, _path = _issue_ack(evaluator, custody_seed, source, tmp_path / "record")
    replaced = copy.deepcopy(ack)
    replaced["payload"]["source_receipt_count"] = 15
    with pytest.raises(ValueError):
        evaluator.acknowledge_custody(replaced)
    evaluator.acknowledge_custody(ack)
    with pytest.raises(ValueError, match="exactly once"):
        evaluator.acknowledge_custody(ack)


def test_incomplete_source_cannot_seal() -> None:
    evaluator, _seed, _pub = _local_keys()
    with pytest.raises(ValueError, match="exactly sixteen"):
        evaluator.seal_source()
    for _ in range(15):
        evaluator.submit(status="accepted", choice="A")
    with pytest.raises(ValueError):
        evaluator.seal_source()
    evaluator.submit(status="not_sent", choice=None)
    with pytest.raises(ValueError, match="sixteen accepted"):
        evaluator.seal_source()


def test_public_ready_and_source_not_exposing_private_target_map() -> None:
    evaluator, _seed, _pub = _local_keys()
    ready = evaluator.ready()
    assert ready["actual_provider_sends"] == 0
    assert "target_mapping" not in json.dumps(ready)
    source, head = _source(evaluator)
    assert len(head) == 64
    assert len(source) == 16
    assert all("target" not in json.dumps(receipt) for receipt in source)


def _private_file(path: Path) -> None:
    path.write_text(os.urandom(32).hex())
    path.chmod(0o600)


def test_distinct_python_processes_exchange_source_deposit(tmp_path) -> None:
    seed_target = tmp_path / "target.key"
    seed_sign = tmp_path / "evaluator.key"
    seed_custody = tmp_path / "custodian.key"
    for p in (seed_target, seed_sign, seed_custody):
        _private_file(p)
    custodian_public = ReceiptSigner(
        bytes.fromhex(seed_custody.read_text()), run_id=RUN
    ).public_key_hex
    custodian_public_file = tmp_path / "custodian.pub"
    custodian_public_file.write_text(custodian_public)
    env = dict(os.environ)
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
    command = [
        sys.executable, "-m", "resonance_world.c3r_g1_crossed_local_evaluator",
        "--target-seed-file", str(seed_target), "--signing-seed-file", str(seed_sign),
        "--custodian-public-key-file", str(custodian_public_file), "--run-id", RUN,
    ]
    with subprocess.Popen(
        command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, text=True, bufsize=1, env=env,
    ) as proc:
        assert proc.stdin is not None and proc.stdout is not None
        ready = json.loads(proc.stdout.readline())
        evaluator_public = ready["evaluator_public_key_hex"]
        assert proc.pid != os.getpid()
        assert ready["scientific_acceptance"] is False

        def send(message):
            proc.stdin.write(json.dumps(message, separators=(",", ":")) + "\n")
            proc.stdin.flush()
            return json.loads(proc.stdout.readline())

        sources = [send({"op": "submit", "status": "accepted", "choice": "A"})[
            "signed_source_receipt"] for _ in range(16)]
        stage = send({"op": "seal_source"})
        assert stage["phase"] == "await_source_custody"
        source_file = tmp_path / "sources.json"
        source_file.write_text(json.dumps(sources))
        evaluator_pub_file = tmp_path / "evaluator.pub"
        evaluator_pub_file.write_text(evaluator_public)
        deposit_dir = tmp_path / "custody"
        deposit_dir.mkdir(mode=0o700)
        command = [
            sys.executable, "-m", "resonance_world.c3r_g1_crossed_source_deposit",
            "--source-receipts-file", str(source_file),
            "--evaluator-public-key-file", str(evaluator_pub_file),
            "--custodian-private-seed-file", str(seed_custody),
            "--destination", str(deposit_dir), "--run-id", RUN,
        ]
        result = subprocess.run(command, check=True, capture_output=True, text=True, env=env)
        deposited = json.loads(result.stdout)
        assert deposited["status"] == "local_source_deposit_written_not_independent_custody"
        ack = json.loads(Path(deposited["receipt_path"]).read_text())
        assert send({"op": "acknowledge_custody", "deposit": ack})[
            "phase"] == "qualification_allowed_by_local_signed_custody_claim"
        for _ in range(23):
            response = send({"op": "submit", "status": "accepted", "choice": "A"})
            assert response["phase"] == "qualification_sealed"
            assert "correct" not in response
        response = send({"op": "submit", "status": "provider_error", "choice": None})
        assert response["phase"] == "qualification_sealed"
        terminal = send({"op": "finalize"})
        assert len(terminal["receipts"]) == 40
        assert terminal["audit"]["descriptive"]["logical_status_counts"]["provider_error"] == 1
        assert terminal["audit"]["scientific_acceptance"] is False
        assert proc.wait(timeout=5) == 0
