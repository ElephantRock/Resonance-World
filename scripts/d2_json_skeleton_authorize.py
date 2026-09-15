#!/usr/bin/env python3
# ruff: noqa
"""Fail-closed sole-child authorization gate for #273."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

MARKER = Path("research/d2_json_skeleton/RUN_D2_JSON_SKELETON")
AUTH = "Autonomous_Operating_Charter_Amendment_A1_standing_execution_authority"
BASE = "31b88c6e067908bdac79c7fa7a68b59412eb6db9"
BLOBS = {
    "src/resonance_world/provider_send_guard.py": "4b8896235d8048523d007400d0acfe85470f628c",
    "src/resonance_world/github_authorization_queries.py": "4fec4f0bfac06ae17a87a7c148dea6521736a97a",
    "src/resonance_world/d2_terminal_adapter.py": "ba16d2eb4b7255437c8ab224e91d5ed093897990",
    "scripts/d2_json_skeleton_spec.py": "467c327df7a82a54819b8cd089a63b98880b3b52",
    "scripts/d2_json_skeleton_prompts.py": "727b57362cdb6f1d552c15e5703a331cfa0cc1a2",
    "scripts/d2_json_skeleton_contract.py": "018057b0796aaa5cf2623b49fc4c42fdacd8690d",
    "scripts/d2_json_skeleton_transport.py": "c9ffa278394ac06944fea034e24593d1c736c0e6",
    "scripts/d2_json_skeleton_agent.py": "5b0ba2a95a6c389222fcf8bd11ba660d442ab285",
    "scripts/d2_json_skeleton_probe.py": "7d9980b60ddb0b82a26c33f5fcfe786a84481f73",
    "scripts/d2_json_skeleton_runtime.py": "5f95fff33f413bac539732fc2b4bc5b7d1e72fe9",
    "scripts/qualify_d2_json_skeleton.py": "30350b997f50ecb22d4dc28dac069fa1b5b0d2c6",
    "scripts/d2_json_skeleton_verify_result.py": "ff75e5af16ed19384c191a151e1e5e22f980c208",
    "tests/test_d2_json_skeleton.py": "cedf1e2c626ec2f13c27f62ded4b6a3b73cc9c1c",
    "research/d2_json_skeleton/REQUEST_PLAN.json": "c5e7681a2b177e4a1df2aefba7eea770bb52a225",
    "research/d2_json_skeleton/PROBES.json": "237468365dee86076999738f9a418890a0a912b6",
    ".github/workflows/d2-json-skeleton-preexecution.yml": "cba2ed4fc563b8ba5b026b2b7398d9a97277dd35",
    ".github/workflows/d2-json-skeleton-qualification.yml": "b4aa83c0fcec3e8142d2fcea4eac7e1c971d5839",
}

def run(*args: str) -> str:
    return subprocess.check_output(args, text=True).strip()

def main() -> int:
    if not MARKER.is_file():
        raise SystemExit("marker absent")
    fields = dict(line.split("=", 1) for line in MARKER.read_text().splitlines() if line)
    if set(fields) != {"candidate_sha", "issue", "authorization"} or fields["issue"] != "273" or fields["authorization"] != AUTH:
        raise SystemExit("marker invalid")
    candidate = fields["candidate_sha"]
    if run("git", "rev-parse", "HEAD^") != candidate or run("git", "diff", "--name-only", candidate, "HEAD") != str(MARKER):
        raise SystemExit("not sole-child activation")
    if subprocess.run(["git", "cat-file", "-e", f"{candidate}:{MARKER}"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0:
        raise SystemExit("candidate already marked")
    if run("git", "log", "--format=%H", "--", str(MARKER)).splitlines() != [run("git", "rev-parse", "HEAD")]:
        raise SystemExit("marker history invalid")
    repo = run("git", "config", "--get", "remote.origin.url").removesuffix(".git").split("github.com/")[-1]
    run_id = os.environ["GITHUB_RUN_ID"]
    query = [sys.executable, "-m", "resonance_world.github_authorization_queries"]
    if int(run(*query, "workflow-runs", "--repository", repo, "--workflow", "d2-json-skeleton-qualification.yml", "--exclude-run-id", run_id)) != 0:
        raise SystemExit("prior run exists")
    if int(run(*query, "reviews", "--repository", repo, "--pull-request", "274", "--candidate-sha", candidate)) < 1:
        raise SystemExit("exact-head review absent")
    if int(run(*query, "threads", "--repository", repo, "--pull-request", "274")) != 0:
        raise SystemExit("unresolved review thread")
    subprocess.check_call(["git", "merge-base", "--is-ancestor", BASE, candidate])
    for path, expected in BLOBS.items():
        if run("git", "rev-parse", f"{candidate}:{path}") != expected:
            raise SystemExit(f"blob drift: {path}")
    print(candidate)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
