#!/usr/bin/env python3
"""Qualify the fresh v2 terminal structured-completion adapter stream."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CORE_PATH = ROOT / "scripts" / "qualify_d2_terminal_adapter_core.py"
DIR = ROOT / "research" / "d2_terminal_adapter_v2"
PLAN = DIR / "REQUEST_PLAN.json"
MARKER = DIR / "RUN_D2_TERMINAL_ADAPTER_V2_QUALIFICATION"
GUARD_PATH = ROOT / "src" / "resonance_world" / "provider_send_guard.py"
EVIDENCE_243 = ROOT / "research" / "evidence" / "d2_terminal_response_observability" / "RESULT.json"

ISSUE = 251
AUTH_ENV = "D2_TERMINAL_ADAPTER_V2_AUTHORIZED"
PLAN_GIT_BLOB_SHA = "8d932cf1b844127c3c655ab56638d73c876a08d3"
GUARD_GIT_BLOB_SHA = "4b8896235d8048523d007400d0acfe85470f628c"
EVIDENCE_243_SHA256 = "cde58890d2d6bd1027381ffa559b385f11883c15e08860a823a1a5017495a9d6"
SEED_NAMESPACE = "rw.d2-terminal-adapter.v2"
SEED_START = 2_000_000
PROBE_ID_PREFIX = "adapter_v2"
PROBE_COUNT = 72


def _git_blob_sha(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_core() -> Any:
    spec = importlib.util.spec_from_file_location("d2_terminal_adapter_core", CORE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load terminal-adapter qualification core")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


core = _load_core()


def generate_probes() -> list[dict[str, Any]]:
    probes: list[dict[str, Any]] = []
    for logical_index in range(PROBE_COUNT):
        budget = 40 if logical_index < 24 else 80 if logical_index < 48 else 160
        probes.append(
            {
                "development_budget": budget,
                "logical_index": logical_index,
                "probe_id": f"{PROBE_ID_PREFIX}_b{budget}_{logical_index:02d}",
                "seed": SEED_START + logical_index,
            }
        )
    return probes


def validate_frozen_files() -> list[dict[str, Any]]:
    if _git_blob_sha(PLAN) != PLAN_GIT_BLOB_SHA:
        raise AssertionError("request plan blob drift")
    if _git_blob_sha(GUARD_PATH) != GUARD_GIT_BLOB_SHA:
        raise AssertionError("provider-send guard blob drift")
    if _file_sha256(EVIDENCE_243) != EVIDENCE_243_SHA256:
        raise AssertionError("#243 preserved result drift")

    plan = json.loads(PLAN.read_text())
    expected = {
        "schema": "d2-terminal-adapter-request-plan-v0.2",
        "issue": ISSUE,
        "probe_count": PROBE_COUNT,
        "fresh_seed_namespace": SEED_NAMESPACE,
        "fresh_seed_start": SEED_START,
        "probe_id_prefix": PROBE_ID_PREFIX,
        "max_iterations": 2,
        "max_tokens": 768,
        "sampling_temperature": 0.8,
        "maximum_concurrency": 4,
        "maximum_physical_sends_total": 180,
        "terminal_override_exact_physical_sends": 2,
        "preserved_evidence_expected_terminal_overrides": 8,
        "authorization_gate_repair_merge_sha": "09d6c5c6ac7884213b492da62a1c236f08f1d62c",
        "consumed_predecessor_issue": 246,
        "consumed_predecessor_outcome": "INTEGRITY_APPARATUS_FAILURE_PRE_PROVIDER",
    }
    for key, value in expected.items():
        if plan.get(key) != value:
            raise AssertionError(f"request plan semantic drift: {key}")
    for key in (
        "pass_requires_all_effective_completed",
        "pass_requires_terminal_override_exercised",
    ):
        if plan.get(key) is not True:
            raise AssertionError(f"request plan semantic drift: {key}")
    for key in (
        "hermes_completed_mutation_allowed",
        "workflow_rerun_allowed",
        "same_request_stream_rerun_allowed",
        "predecessor_stream_rerun_or_replacement_allowed",
        "scientific_scoring_performed",
        "acceptance_action_authorized",
        "historical_substrate_enabled",
    ):
        if plan.get(key) is not False:
            raise AssertionError(f"request plan semantic drift: {key}")

    probes = generate_probes()
    if len(probes) != PROBE_COUNT:
        raise AssertionError("probe count drift")
    if Counter(int(row["development_budget"]) for row in probes) != Counter({40: 24, 80: 24, 160: 24}):
        raise AssertionError("probe budget balance drift")
    if len({row["probe_id"] for row in probes}) != PROBE_COUNT:
        raise AssertionError("probe id reuse")
    if len({row["seed"] for row in probes}) != PROBE_COUNT:
        raise AssertionError("probe seed reuse")
    if any(int(row["seed"]) < SEED_START for row in probes):
        raise AssertionError("probe seed namespace drift")
    if any(not str(row["probe_id"]).startswith(PROBE_ID_PREFIX + "_") for row in probes):
        raise AssertionError("probe id namespace drift")
    return probes


def _patch_core() -> None:
    core.ISSUE = ISSUE
    core.DIR = DIR
    core.PLAN = PLAN
    core.MARKER = MARKER
    core.GUARD_PATH = GUARD_PATH
    core.EVIDENCE_243 = EVIDENCE_243
    core.AUTH_ENV = AUTH_ENV
    core.PLAN_GIT_BLOB_SHA = PLAN_GIT_BLOB_SHA
    core.GUARD_GIT_BLOB_SHA = GUARD_GIT_BLOB_SHA
    core.EVIDENCE_243_SHA256 = EVIDENCE_243_SHA256
    core.validate_frozen_files = validate_frozen_files
    core.load_probes = generate_probes


def preflight() -> dict[str, Any]:
    _patch_core()
    probes = validate_frozen_files()
    if MARKER.exists():
        raise AssertionError("execution marker must be absent from frozen candidate")
    prompt_lengths = [len(core.adapter.user_prompt(probe).encode()) for probe in probes]
    if not all(2100 <= length <= 2250 for length in prompt_lengths):
        raise AssertionError("fresh prompt envelope drift")
    regression = core.preserved_evidence_regression()
    return {
        "schema": "d2-terminal-adapter-v2-preflight-v0.1",
        "issue": ISSUE,
        "engineering_only": True,
        "provider_execution_performed": False,
        "execution_marker_absent": True,
        "request_plan_git_blob_sha": _git_blob_sha(PLAN),
        "provider_send_guard_git_blob_sha": _git_blob_sha(GUARD_PATH),
        "causal_predecessor_result_sha256": _file_sha256(EVIDENCE_243),
        "authorization_gate_repair_merge_sha": "09d6c5c6ac7884213b492da62a1c236f08f1d62c",
        "consumed_predecessor_issue": 246,
        "consumed_predecessor_outcome": "INTEGRITY_APPARATUS_FAILURE_PRE_PROVIDER",
        "fresh_seed_namespace": SEED_NAMESPACE,
        "fresh_seed_start": SEED_START,
        "probe_count": len(probes),
        "minimum_prompt_bytes": min(prompt_lengths),
        "maximum_prompt_bytes": max(prompt_lengths),
        "preserved_evidence_regression": regression,
        "scientific_scoring_performed": False,
        "historical_substrate_enabled": False,
    }


def execute() -> dict[str, Any]:
    _patch_core()
    result = core.execute()
    result.update(
        {
            "schema": "d2-terminal-adapter-v2-qualification-result-v0.1",
            "issue": ISSUE,
            "purpose": "requalify_terminal_structured_completion_adapter_after_authorization_gate_repair",
            "fresh_seed_namespace": SEED_NAMESPACE,
            "fresh_seed_start": SEED_START,
            "consumed_predecessor_issue": 246,
            "consumed_predecessor_outcome_unchanged": "INTEGRITY_APPARATUS_FAILURE_PRE_PROVIDER",
            "consumed_predecessor_provider_traffic": False,
            "authorization_gate_repair_issue": 249,
            "authorization_gate_repair_pr": 250,
            "authorization_gate_repair_merge_sha": "09d6c5c6ac7884213b492da62a1c236f08f1d62c",
        }
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--preflight", action="store_true")
    mode.add_argument("--execute", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    result = preflight() if args.preflight else execute()
    rendered = json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered)
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
