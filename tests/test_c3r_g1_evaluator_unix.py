"""Linux Unix socket G1 evaluator: pinned UID transport and signed full run."""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

from resonance_world.c3r_g1_evaluator_receipts import (
    ReceiptSigner,
    ReceiptVerifier,
    VerifiedEvaluatorSession,
)
from resonance_world.c3r_g1_evaluator_transcript import audit_signed_transcript
from resonance_world.c3r_g1_evaluator_unix import (
    UnixEvaluatorClient,
    _check_socket_directory,
)
from resonance_world.c3r_g1_model_boundary import ModelChoiceCompletion
from resonance_world.c3r_g1_multischema import V2Design
from resonance_world.c3r_g1_sealed_runner import SealedPilotRunner

pytestmark = pytest.mark.skipif(
    not hasattr(socket, "SO_PEERCRED"), reason="Linux SO_PEERCRED required"
)
REPO_ROOT = Path(__file__).resolve().parents[1]
RUN_ID = "g1-unix-fixture-run-20261022"


class _NullPort:
    def complete(self, _request):
        return ModelChoiceCompletion("A", "offline-schema-fixture")


def _key(path: Path, value: bytes) -> None:
    path.write_text(value.hex() + "\n")
    path.chmod(0o600)


def test_real_unix_socket_signed_evaluator_full_three_arm_run(
    tmp_path: Path,
) -> None:
    socket_dir = tmp_path / "socket"
    socket_dir.mkdir(mode=0o750)
    socket_path = socket_dir / "evaluator.sock"
    target_file = tmp_path / "target.hex"
    signing_file = tmp_path / "signing.hex"
    _key(target_file, bytes.fromhex("55" * 32))
    _key(signing_file, bytes.fromhex("66" * 32))
    public_key = ReceiptSigner(
        bytes.fromhex("66" * 32), run_id=RUN_ID
    ).public_key_hex
    argv = [
        sys.executable, "-m", "resonance_world.c3r_g1_evaluator_unix",
        "--socket-path", str(socket_path),
        "--allowed-peer-uid", str(os.geteuid()),
        "--key-file", str(target_file),
        "--signing-key-file", str(signing_file),
        "--run-id", RUN_ID,
        "--units", "1", "--development", "1", "--qualification", "1",
    ]
    server = subprocess.Popen(
        argv, cwd=REPO_ROOT, stderr=subprocess.PIPE, stdout=subprocess.PIPE,
        text=True,
    )
    try:
        for _ in range(120):
            if socket_path.exists():
                break
            if server.poll() is not None:
                break
            time.sleep(0.025)
        assert socket_path.exists(), "server failed to create socket"
        assert socket_path.stat().st_mode & 0o777 == 0o660
        spec = V2Design(units=1, development_per_family=1,
                        qualification_per_family=1)
        cohort = spec.freeze()
        with UnixEvaluatorClient(socket_path) as client:
            session = VerifiedEvaluatorSession(
                client, ReceiptVerifier(public_key, expected_run_id=RUN_ID)
            )
            report = SealedPilotRunner(cohort, session).run(
                port_factory=lambda _unit, _arm, _stage: _NullPort(),
            )
            transcript = audit_signed_transcript(
                list(session.signed_receipts), cohort,
                public_key_hex=public_key, expected_run_id=RUN_ID,
            )
            assert transcript.status == "signed_structurally_consistent"
            assert transcript.signed_attempts == spec.logical_calls == 8
            assert report.report.to_dict()["qualification_action_yield"] == 1.0
            assert report.report.to_dict()["mean_unit_itt_learned_minus_fresh"] == 0.0
            assert report.to_dict()["scientific_acceptance"] is False
        assert server.wait(timeout=12) == 0
        assert not socket_path.exists()
        assert signing_file.read_text().strip() not in json.dumps(report.to_dict())
    finally:
        if server.poll() is None:
            server.kill()
            server.wait(timeout=12)


def test_socket_directory_must_not_be_writable_by_agent_group(
    tmp_path: Path,
) -> None:
    directory = tmp_path / "shared"
    directory.mkdir(mode=0o770)
    directory.chmod(0o770)
    with pytest.raises(ValueError, match="group/world writable"):
        _check_socket_directory(directory / "grader.sock")
    directory.chmod(0o750)
    _check_socket_directory(directory / "grader.sock")
    file = directory / "grader.sock"
    file.write_text("wrong socket", encoding="utf-8")
    with pytest.raises(ValueError, match="existing Unix socket"):
        _check_socket_directory(file)


def test_unix_client_rejects_invalid_bounded_deadline(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="bounded"):
        UnixEvaluatorClient(tmp_path / "missing", timeout_seconds=100)
