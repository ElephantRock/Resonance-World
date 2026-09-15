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
    "scripts/d2_canonical_json_prompt_spec.py": "68015fccafbeb0f09dd57100409298fc4ffdb5fb",
    "scripts/d2_canonical_json_prompt_prompts.py": "89405950bab72e42dfc2b58715fa92f7adbcb547",
    "scripts/d2_canonical_json_prompt_contract.py": "9fbc96e9c84567646dcba09e4df61b9cea806467",
    "scripts/d2_canonical_json_prompt_transport.py": "c68ee95ddc4a9abcf8f041a582ad3744f9ec092f",
    "scripts/d2_canonical_json_prompt_agent.py": "5fd49cbae14e92efd85fe001752524f7bc420930",
    "scripts/d2_canonical_json_prompt_probe.py": "dd8f35367a2b724592ba5da95246edeb85ab0324",
    "scripts/d2_canonical_json_prompt_runtime.py": "d1181e181e69b9af71b65ceb2e64d04577c060d1",
    "scripts/qualify_d2_canonical_json_prompt.py": "53e6fcb8f2c1c7fd74338f69c5a67c5ea5e953f6",
    "scripts/d2_canonical_json_prompt_verify_result.py": "1f0c74bdb6855f0c199a8799d22d7c26196974aa",
    "tests/test_d2_canonical_json_prompt.py": "2b42bb6a51108e2c64bf0038c0e695ca2800dd94",
    "research/d2_canonical_json_prompt/REQUEST_PLAN.json": "66b23953edb7620a8c1c67bbaf78960d54ffb283",
    "research/d2_canonical_json_prompt/PROBES.json": "fcf7e3bee404c3247498cd95cd4095d13c993032",
    ".github/workflows/d2-canonical-json-prompt-preexecution.yml": "ef9a5e4be2180c6200afca7faead66d37434c407",
    ".github/workflows/d2-canonical-json-prompt-qualification.yml": "1aaf284b69608b109b1bb9e787b854586c80fe84",
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
