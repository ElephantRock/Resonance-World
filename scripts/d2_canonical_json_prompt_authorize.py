#!/usr/bin/env python3
# ruff: noqa
"""Fail-closed sole-child authorization gate for #270."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

MARKER = Path("research/d2_canonical_json_prompt/RUN_D2_CANONICAL_JSON_PROMPT")
AUTH = "Autonomous_Operating_Charter_Amendment_A1_standing_execution_authority"
BASE = "43e600a11b9cbe44a0c3752a0ddb087872b63a93"
BLOBS = {
    "src/resonance_world/provider_send_guard.py": "4b8896235d8048523d007400d0acfe85470f628c",
    "src/resonance_world/github_authorization_queries.py": "4fec4f0bfac06ae17a87a7c148dea6521736a97a",
    "src/resonance_world/d2_terminal_adapter.py": "ba16d2eb4b7255437c8ab224e91d5ed093897990",
    "scripts/d2_canonical_json_prompt_spec.py": "711a5a35f9ac5abaa67034b1f6eaf3c94a41cd0f",
    "scripts/d2_canonical_json_prompt_prompts.py": "0b01645183323a46bbfda41b069e7764fe00f50c",
    "scripts/d2_canonical_json_prompt_contract.py": "9fbc96e9c84567646dcba09e4df61b9cea806467",
    "scripts/d2_canonical_json_prompt_transport.py": "5c5033cd72f8881afe313302068266738a2b16f1",
    "scripts/d2_canonical_json_prompt_agent.py": "d2506b60415bf6ba64ab30d3edbbb762088744e1",
    "scripts/d2_canonical_json_prompt_probe.py": "975ad3179bb5022e2fe3a10cd90a8f21b5e066b9",
    "scripts/d2_canonical_json_prompt_runtime.py": "98eb0289d0256fefba5f0f783e63c7a49d51bf16",
    "scripts/qualify_d2_canonical_json_prompt.py": "9bc13a18cab340fd86b5346b425ff289cbca0e56",
    "scripts/d2_canonical_json_prompt_verify_result.py": "8b0afe55981478e3ecd614165488b7c1405b20d1",
    "tests/test_d2_canonical_json_prompt.py": "5056f7b74b19a7d3231705d9ab3650cbca7820e5",
    "research/d2_canonical_json_prompt/REQUEST_PLAN.json": "77973b907ac919af534f725ab4696854e6bf1ec8",
    "research/d2_canonical_json_prompt/PROBES.json": "80ed965fdc6dea168294ca9dfd0a689bb29465a6",
    ".github/workflows/d2-canonical-json-prompt-preexecution.yml": "157df52d5d78a73a4688c6e77552c1b17b7a1abe",
    ".github/workflows/d2-canonical-json-prompt-qualification.yml": "0d37853893b6f1075ebce474684391d4eb6a4707",
}

def run(*args: str) -> str:
    return subprocess.check_output(args, text=True).strip()

def main() -> int:
    if not MARKER.is_file():
        raise SystemExit("marker absent")
    fields = dict(line.split("=", 1) for line in MARKER.read_text().splitlines() if line)
    if set(fields) != {"candidate_sha", "issue", "authorization"} or fields["issue"] != "270" or fields["authorization"] != AUTH:
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
    if int(run(*query, "workflow-runs", "--repository", repo, "--workflow", "d2-canonical-json-prompt-qualification.yml", "--exclude-run-id", run_id)) != 0:
        raise SystemExit("prior run exists")
    if int(run(*query, "reviews", "--repository", repo, "--pull-request", "271", "--candidate-sha", candidate)) < 1:
        raise SystemExit("exact-head review absent")
    if int(run(*query, "threads", "--repository", repo, "--pull-request", "271")) != 0:
        raise SystemExit("unresolved review thread")
    subprocess.check_call(["git", "merge-base", "--is-ancestor", BASE, candidate])
    for path, expected in BLOBS.items():
        if run("git", "rev-parse", f"{candidate}:{path}") != expected:
            raise SystemExit(f"blob drift: {path}")
    print(candidate)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
