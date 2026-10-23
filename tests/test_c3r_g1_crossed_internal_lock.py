"""Fast internal-only G1 source lock tests; no external approvers/provider sends."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from resonance_world.c3r_g1_crossed_internal_lock import (
    verify_internal_source_lock,
    write_internal_source_lock,
)
from resonance_world.c3r_g1_crossed_local_evaluator import CrossedLocalEvaluator

RUN = "g1-internal-first-offline-20261023"


def _engine(directory: Path, *, run_id: str = RUN) -> CrossedLocalEvaluator:
    return CrossedLocalEvaluator(
        run_id=run_id,
        private_target_seed=os.urandom(32),
        signing_seed=os.urandom(32),
        internal_checkpoint_dir=directory,
    )


def _source(engine: CrossedLocalEvaluator) -> tuple[dict[str, object], ...]:
    receipts = []
    for _ in range(16):
        response = engine.submit(status="accepted", choice="A")
        assert response["phase"] == "development_feedback"
        receipts.append(response["signed_source_receipt"])
    return tuple(receipts)


def _directory(tmp_path: Path) -> Path:
    path = tmp_path / "internal-lock"
    path.mkdir(mode=0o700)
    return path


def test_internal_auto_unlock_without_witness_or_custodian(tmp_path: Path) -> None:
    directory = _directory(tmp_path)
    engine = _engine(directory)
    _source(engine)
    frozen = engine.seal_source()
    assert frozen["phase"] == "internal_source_frozen_qualification_allowed"
    assert frozen["source_receipt_count"] == 16
    assert len(frozen["internal_source_lock_sha256"]) == 64
    for i in range(24):
        response = engine.submit(
            status="accepted" if i < 23 else "not_sent",
            choice="B" if i < 23 else None,
        )
        assert response["phase"] == "qualification_sealed"
        assert set(response) == {"schema", "phase", "qualification_received"}
    result = engine.finalize()
    assert result["source_gate_mode"] == "internal_durable_checkpoint"
    assert result["internal_source_lock_sha256"] == frozen["internal_source_lock_sha256"]
    assert result["requires_external_approval"] is False
    assert result["actual_provider_sends"] == 0
    assert result["audit"]["descriptive"]["logical_status_counts"]["not_sent"] == 1
    assert result["scientific_acceptance"] is False


def test_source_lock_rejects_early_qualification_and_unfinished_source(tmp_path: Path) -> None:
    engine = _engine(_directory(tmp_path))
    with pytest.raises(ValueError, match="before source lock"):
        engine.submit(status="accepted", choice="A")
    for _ in range(15):
        engine.submit(status="accepted", choice="A")
    with pytest.raises(ValueError, match="exactly sixteen"):
        engine.seal_source()


def test_duplicate_run_id_exclusive_file_fails_closed(tmp_path: Path) -> None:
    directory = _directory(tmp_path)
    first = _engine(directory)
    _source(first)
    first.seal_source()
    second = _engine(directory)
    _source(second)
    with pytest.raises(FileExistsError):
        second.seal_source()
    with pytest.raises(ValueError, match="before source lock"):
        second.submit(status="accepted", choice="A")


def test_tampered_local_checkpoint_blocks_holdout(tmp_path: Path) -> None:
    directory = _directory(tmp_path)
    engine = _engine(directory)
    _source(engine)
    engine.seal_source()
    lock_path = next(directory.iterdir())
    record = json.loads(lock_path.read_text())
    record["source_chain_head_sha256"] = "0" * 64
    lock_path.write_text(json.dumps(record))
    with pytest.raises(ValueError, match="diverges"):
        engine.submit(status="accepted", choice="A")


def test_missing_local_checkpoint_blocks_holdout(tmp_path: Path) -> None:
    directory = _directory(tmp_path)
    engine = _engine(directory)
    _source(engine)
    engine.seal_source()
    next(directory.iterdir()).unlink()
    with pytest.raises(FileNotFoundError):
        engine.submit(status="accepted", choice="A")


def test_mutation_after_first_holdout_blocks_finalization(tmp_path: Path) -> None:
    directory = _directory(tmp_path)
    engine = _engine(directory)
    _source(engine)
    engine.seal_source()
    for _ in range(24):
        engine.submit(status="accepted", choice="B")
    lock = next(directory.iterdir())
    lock.unlink()
    with pytest.raises(FileNotFoundError):
        engine.finalize()


def test_internal_mode_rejects_unnecessary_approver_and_witness(tmp_path: Path) -> None:
    directory = _directory(tmp_path)
    with pytest.raises(ValueError, match="cannot depend on a custodian"):
        CrossedLocalEvaluator(
            run_id=RUN, private_target_seed=os.urandom(32),
            signing_seed=os.urandom(32),
            internal_checkpoint_dir=directory,
            pinned_custodian_public_key_hex="a" * 64,
        )
    with pytest.raises(ValueError, match="cannot depend on a witness"):
        CrossedLocalEvaluator(
            run_id=RUN, private_target_seed=os.urandom(32),
            signing_seed=os.urandom(32),
            internal_checkpoint_dir=directory,
            pinned_witness_public_key_hex="b" * 64,
        )
    engine = _engine(directory)
    with pytest.raises(ValueError, match="no custodian approval"):
        engine.acknowledge_custody({})


def test_storage_permissions_and_symlink_directory_rejected(tmp_path: Path) -> None:
    directory = _directory(tmp_path)
    directory.chmod(0o755)
    engine = _engine(directory)
    _source(engine)
    with pytest.raises(ValueError, match="private and owned"):
        engine.seal_source()
    directory.chmod(0o700)
    link = tmp_path / "alias"
    link.symlink_to(directory, target_is_directory=True)
    second = _engine(link)
    _source(second)
    with pytest.raises(ValueError, match="not symlinked"):
        second.seal_source()


def test_offline_lock_verifier_rejects_wrong_key_and_source(tmp_path: Path) -> None:
    directory = _directory(tmp_path)
    engine = _engine(directory)
    receipts = _source(engine)
    frozen = engine.seal_source()
    result = verify_internal_source_lock(
        directory=directory, run_id=RUN,
        evaluator_public_key_hex=engine.evaluator_public_key_hex,
        source_receipts=receipts,
        expected_lock_sha256=frozen["internal_source_lock_sha256"],
    )
    assert result["requires_external_approval"] is False
    assert result["scientific_acceptance"] is False
    with pytest.raises(ValueError):
        verify_internal_source_lock(
            directory=directory, run_id=RUN,
            evaluator_public_key_hex="0" * 64,
            source_receipts=receipts,
            expected_lock_sha256=frozen["internal_source_lock_sha256"],
        )
    with pytest.raises(ValueError):
        write_internal_source_lock(
            directory=directory, run_id=RUN,
            evaluator_public_key_hex=engine.evaluator_public_key_hex,
            source_receipts=receipts[:-1],
        )


def test_internal_subprocess_cli_full_40_attempts_no_other_service(tmp_path: Path) -> None:
    directory = _directory(tmp_path)
    keys = []
    for name in ("target.hex", "signer.hex"):
        key = tmp_path / name
        key.write_text(os.urandom(32).hex() + "\n")
        key.chmod(0o600)
        keys.append(key)
    env = dict(os.environ)
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
    command = [
        sys.executable, "-m", "resonance_world.c3r_g1_crossed_local_evaluator",
        "--run-id", RUN, "--target-seed-file", str(keys[0]),
        "--signing-seed-file", str(keys[1]),
        "--internal-checkpoint-dir", str(directory),
    ]
    with subprocess.Popen(
        command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, text=True, bufsize=1, env=env,
    ) as proc:
        assert proc.stdin is not None and proc.stdout is not None
        first = json.loads(proc.stdout.readline())
        assert first["actual_provider_sends"] == 0

        def ask(command: dict[str, object]) -> dict[str, object]:
            proc.stdin.write(json.dumps(command) + "\n")
            proc.stdin.flush()
            return json.loads(proc.stdout.readline())

        for _ in range(16):
            assert ask({"op": "submit", "status": "accepted", "choice": "A"})[
                "phase"
            ] == "development_feedback"
        assert ask({"op": "seal_source"})[
            "phase"
        ] == "internal_source_frozen_qualification_allowed"
        for _ in range(24):
            response = ask({"op": "submit", "status": "accepted", "choice": "B"})
            assert response["phase"] == "qualification_sealed"
        terminal = ask({"op": "finalize"})
        assert terminal["source_gate_mode"] == "internal_durable_checkpoint"
        assert len(terminal["receipts"]) == 40
        assert terminal["scientific_acceptance"] is False
        assert proc.wait(timeout=10) == 0
