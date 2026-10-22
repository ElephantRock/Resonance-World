"""CLI-level negative checks for the offline C3R run reconciler."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
AUDIT_SCRIPT = REPO_ROOT / "scripts" / "audit_c3r_g1_smoke.py"


def test_missing_artifact_does_not_claim_provider_execution(tmp_path: Path) -> None:
    process = subprocess.run(
        [
            sys.executable,
            str(AUDIT_SCRIPT),
            str(tmp_path / "not-found.json"),
            "--model",
            "glm-5.3",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert process.returncode != 0
    assert "does not exist" in process.stderr
    assert "provider_execution_verified" not in process.stdout


def test_empty_and_fabricated_artifact_fail_closed(tmp_path: Path) -> None:
    artifact = tmp_path / "simulated.json"
    artifact.write_text(json.dumps({"schema": "unexpected", "status": "success"}))
    process = subprocess.run(
        [
            sys.executable,
            str(AUDIT_SCRIPT),
            str(artifact),
            "--model",
            "glm-5.3",
            "--route",
            "coding",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert process.returncode == 2
    summary = json.loads(process.stdout)
    assert summary["status"] == "rejected_inconsistent_artifact"
    assert summary["provider_execution_verified"] is False
    assert summary["independently_attested"] is False
    assert summary["scientific_acceptance"] is False


def test_dry_run_json_never_passes_live_audit(tmp_path: Path) -> None:
    preflight = subprocess.run(
        [sys.executable, "scripts/run_c3r_g1_live_smoke.py"],
        cwd=REPO_ROOT, capture_output=True, text=True, check=True,
    )
    artifact = tmp_path / "preflight.json"
    artifact.write_text(preflight.stdout)
    audit = subprocess.run(
        [
            sys.executable, str(AUDIT_SCRIPT), str(artifact),
            "--model", "glm-5.3",
        ],
        cwd=REPO_ROOT, capture_output=True, text=True, check=False,
    )
    assert audit.returncode == 2
    verdict = json.loads(audit.stdout)
    assert "unexpected_schema" in verdict["issues"]
    assert "missing_send_ledger" in verdict["issues"]


def test_oversize_artifact_is_rejected_without_parsing(tmp_path: Path) -> None:
    artifact = tmp_path / "large.json"
    artifact.write_bytes(b"A" * (512 * 1024 + 1))
    process = subprocess.run(
        [sys.executable, str(AUDIT_SCRIPT), str(artifact), "--model", "glm-5.3"],
        cwd=REPO_ROOT, capture_output=True, text=True, check=False,
    )
    assert process.returncode != 0
    assert "size cap" in process.stderr
