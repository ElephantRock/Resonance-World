"""Exact reproduction helper for the preregistered H2 turnover experiment."""
# ruff: noqa: E501
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path


def _run(root: Path, work: Path, candidate: str) -> dict[str, bytes]:
    corpus = work / "corpus"
    subprocess.run([sys.executable, "scripts/materialize_h2_fixtures.py", "--output-root", str(corpus)], cwd=root, check=True)
    lock = work / "lock.json"
    subprocess.run([sys.executable, "scripts/verify_h2_lock.py", "--materialization", str(corpus / "materialization-manifest.json"), "--corpus-root", str(corpus), "--output", str(lock)], cwd=root, check=True)
    public = work / "evidence.json"
    shutil.copyfile(corpus / "plane_e/evidence.json", public)
    shutil.rmtree(corpus)
    research = work / "research"
    subprocess.run([sys.executable, "scripts/run_h2_turnover.py", "--plane-e", str(public), "--output-dir", str(research)], cwd=root, check=True)
    researcher = research / "h2-researcher-output.json"
    pre_key = hashlib.sha256(researcher.read_bytes()).hexdigest()
    public.unlink()
    evaluator = work / "evaluator"
    subprocess.run([sys.executable, "scripts/materialize_h2_fixtures.py", "--output-root", str(evaluator)], cwd=root, check=True)
    evaluator_lock = work / "evaluator-lock.json"
    subprocess.run([sys.executable, "scripts/verify_h2_lock.py", "--materialization", str(evaluator / "materialization-manifest.json"), "--corpus-root", str(evaluator), "--output", str(evaluator_lock)], cwd=root, check=True)
    assert lock.read_bytes() == evaluator_lock.read_bytes()
    acceptance = work / "acceptance"
    subprocess.run([sys.executable, "scripts/accept_h2_turnover.py", "--lock-verification", str(lock), "--corpus-root", str(evaluator), "--researcher-output", str(research), "--pre-key-sha256", pre_key, "--candidate-head", candidate, "--output-dir", str(acceptance)], cwd=root, check=True)
    assert hashlib.sha256(researcher.read_bytes()).hexdigest() == pre_key
    result_path = acceptance / "h2-result.json"
    result = json.loads(result_path.read_text())
    assert result["classification"] == "historical_substrate_turnover_persistence_pass"
    return {
        "lock": lock.read_bytes(),
        "researcher": researcher.read_bytes(),
        "result": result_path.read_bytes(),
        "manifest": (acceptance / "h2-manifest.json").read_bytes(),
    }


def reproduce_h2_exact_head(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    candidate = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    first = _run(root, tmp_path / "primary", candidate)
    second = _run(root, tmp_path / "independent", candidate)
    assert first == second
    print("H2_RESULT=" + first["result"].decode().strip())
    print("H2_MANIFEST=" + first["manifest"].decode().strip())
