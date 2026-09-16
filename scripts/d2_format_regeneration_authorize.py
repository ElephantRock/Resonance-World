#!/usr/bin/env python3
# ruff: noqa
"""Fail-closed sole-child authorization gate for #276."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

MARKER = Path("research/d2_format_regeneration/RUN_D2_FORMAT_REGENERATION")
AUTH = "Autonomous_Operating_Charter_Amendment_A1_standing_execution_authority"
ISSUE = "276"
CONSTRUCTION_PR = "277"
BASE = "2e29af4bc38bc5a72df407bb87b6a472d29f20e3"
CRITICAL_BLOBS = {
    "src/resonance_world/provider_send_guard.py": "4b8896235d8048523d007400d0acfe85470f628c",
    "src/resonance_world/github_authorization_queries.py": "4fec4f0bfac06ae17a87a7c148dea6521736a97a",
    "src/resonance_world/d2_terminal_adapter.py": "ba16d2eb4b7255437c8ab224e91d5ed093897990",
    "research/d2_format_regeneration/REQUEST_PLAN.json": "c170288e4f0a250187f35890977f2bc4732f8ca1",
    "research/d2_format_regeneration/PROBES.json": "0c2f4aca3d5aecdd7428374aa5ec60804a2b1d4f",
}


def run(*args: str) -> str:
    return subprocess.check_output(args, text=True).strip()


def main() -> int:
    if not MARKER.is_file():
        raise SystemExit("marker absent")
    fields = dict(line.split("=", 1) for line in MARKER.read_text().splitlines() if line)
    if set(fields) != {"candidate_sha", "issue", "authorization"} or fields["issue"] != ISSUE or fields["authorization"] != AUTH:
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
    if int(run(*query, "workflow-runs", "--repository", repo, "--workflow", "d2-format-regeneration-qualification.yml", "--exclude-run-id", run_id)) != 0:
        raise SystemExit("prior run exists")
    if int(run(*query, "reviews", "--repository", repo, "--pull-request", CONSTRUCTION_PR, "--candidate-sha", candidate)) < 1:
        raise SystemExit("exact-head review absent")
    if int(run(*query, "threads", "--repository", repo, "--pull-request", CONSTRUCTION_PR)) != 0:
        raise SystemExit("unresolved review thread")
    subprocess.check_call(["git", "merge-base", "--is-ancestor", BASE, candidate])
    for path, expected in CRITICAL_BLOBS.items():
        if run("git", "rev-parse", f"{candidate}:{path}") != expected:
            raise SystemExit(f"critical blob drift: {path}")
    print(candidate)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
