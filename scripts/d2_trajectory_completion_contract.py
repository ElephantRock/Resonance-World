"""Frozen contract for trajectory-scale D2 terminal-adapter qualification."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import re
from pathlib import Path
from typing import Any

from resonance_world import d2_terminal_adapter as adapter

ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / "research" / "d2_trajectory_terminal_adapter"
PLAN = DIR / "REQUEST_PLAN.json"
TOPOLOGY = DIR / "TOPOLOGY.json"
MARKER = DIR / "RUN_D2_TRAJECTORY_TERMINAL_ADAPTER"
GUARD_PATH = ROOT / "src" / "resonance_world" / "provider_send_guard.py"
ADAPTER_PATH = ROOT / "src" / "resonance_world" / "d2_terminal_adapter.py"
EVIDENCE_251 = (
    ROOT
    / "research"
    / "evidence"
    / "d2_terminal_adapter_v2_qualification"
    / "RESULT.json"
)

ISSUE = 255
NAMESPACE = "rw.d2-trajectory-terminal-adapter.v1"
HERMES_REPOSITORY = "hermes-agent-org/hermes"
HERMES_REVISION = "036cbdfa0a3158454a0a2a7a7388cf70353326b4"
HERMES_VERSION = "0.8.0"
HERMES_RUN_AGENT_BLOB_SHA = "4c0d3be4b0c2d364c550fa663d34f6545c9e6d20"
OPENAI_VERSION = "2.21.0"
HTTPX_VERSION = "0.28.1"
OPENAI_DEFAULT_MAX_RETRIES = 2
BASE_URL = "https://api.z.ai/api/coding/paas/v4"
PROVIDER = "zai"
API_MODE = "chat_completions"
MODEL = "glm-5.3"
TEMPERATURE = 0.8
THINKING = {"type": "disabled"}
PROFILE = {"name": "iterations2_tokens768", "max_iterations": 2, "max_tokens": 768}
TRAJECTORIES = tuple(f"terminal_adapter_trajectory_{index}" for index in range(4))
TRAJECTORY_CALLS_EACH = 55
MAX_LOGICAL_CALLS = 220
MAX_TRAJECTORY_CONCURRENCY = 4
MAX_SENDS_PER_LOGICAL = 36
MAX_SENDS_TOTAL = 400
PROBE_ORIGIN_HEADER = "X-Resonance-World-Logical-Index"
PROVIDER_WORKER_DRAIN_TIMEOUT_SECONDS = 60.0
PROVIDER_WORKER_TARGET_MODULE = "run_agent"
PROVIDER_WORKER_TARGET_NAME = "_call"
GUARD_REPAIR_MERGE_SHA = "47383f2b18c993965c89350609a4c9691897bdde"
GUARD_GIT_BLOB_SHA = "4b8896235d8048523d007400d0acfe85470f628c"
ADAPTER_GIT_BLOB_SHA = "ba16d2eb4b7255437c8ab224e91d5ed093897990"
EVIDENCE_251_MERGE_SHA = "01e7abc79eb84326c1705073e92d145f703854c8"
EVIDENCE_251_SHA256 = "f0c9ba663642bfec83b04287b71991ec3da275e9c231a3666acf88c3ce5b956e"
AUTH_ENV = "D2_TRAJECTORY_TERMINAL_ADAPTER_AUTHORIZED"
AUTH_STRING = "Autonomous_Operating_Charter_Amendment_A1_standing_execution_authority"

_FORBIDDEN_PROVIDER_CREDENTIAL_ENV_VARS = (
    "OPENROUTER_API_KEY",
    "OPENAI_API_KEY",
    "OPENAI_BASE_URL",
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_TOKEN",
    "NOUS_API_KEY",
    "GLM_API_KEY",
    "Z_AI_API_KEY",
    "KIMI_API_KEY",
    "MINIMAX_API_KEY",
    "DEEPSEEK_API_KEY",
    "DASHSCOPE_API_KEY",
    "XAI_API_KEY",
)


def canonical(value: Any) -> bytes:
    """Return canonical JSON bytes with one trailing newline."""

    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_blob_sha(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()


def expected_plan() -> dict[str, Any]:
    """Return the exact prospectively frozen request-plan contract."""

    return {
        "schema": "d2-trajectory-terminal-adapter-request-plan-v0.1",
        "issue": ISSUE,
        "engineering_only": True,
        "purpose": "trajectory_scale_d2_completion_with_qualified_terminal_adapter",
        "fresh_namespace": NAMESPACE,
        "predecessor_trajectory_issue": 234,
        "predecessor_trajectory_result_unchanged": "FAIL",
        "terminal_observability_issue": 243,
        "terminal_observability_result_unchanged": "VALID_TERMINAL_RESPONSE_OBSERVED",
        "qualified_adapter_issue": 251,
        "qualified_adapter_result_unchanged": "PASS",
        "qualified_adapter_evidence_merge_sha": EVIDENCE_251_MERGE_SHA,
        "qualified_adapter_result_sha256": EVIDENCE_251_SHA256,
        "terminal_adapter_git_blob_sha": ADAPTER_GIT_BLOB_SHA,
        "guard_repair_merge_sha": GUARD_REPAIR_MERGE_SHA,
        "provider_send_guard_git_blob_sha": GUARD_GIT_BLOB_SHA,
        "provider": "Z.AI",
        "subscription_product": "GLM Coding Plan",
        "endpoint_base_url": BASE_URL,
        "provider_id": PROVIDER,
        "api_mode": API_MODE,
        "requested_model": MODEL,
        "hermes_repository": HERMES_REPOSITORY,
        "hermes_revision": HERMES_REVISION,
        "hermes_package_version": HERMES_VERSION,
        "hermes_run_agent_blob_sha": HERMES_RUN_AGENT_BLOB_SHA,
        "openai_sdk_version": OPENAI_VERSION,
        "openai_sdk_default_max_retries": OPENAI_DEFAULT_MAX_RETRIES,
        "httpx_version": HTTPX_VERSION,
        "selected_profile": PROFILE,
        "sampling_temperature": TEMPERATURE,
        "thinking": THINKING,
        "enabled_toolsets": [],
        "memory_context_files_enabled": False,
        "persistent_session_enabled": False,
        "fallback_provider_configured": False,
        "trajectory_names": list(TRAJECTORIES),
        "trajectory_logical_calls_each": TRAJECTORY_CALLS_EACH,
        "trajectory_logical_calls_total": MAX_LOGICAL_CALLS,
        "trajectory_max_concurrency": MAX_TRAJECTORY_CONCURRENCY,
        "maximum_physical_sends_per_logical_call": MAX_SENDS_PER_LOGICAL,
        "maximum_physical_sends_total": MAX_SENDS_TOTAL,
        "independent_request_origin_header": PROBE_ORIGIN_HEADER,
        "logical_context_thread_propagation_required": True,
        "provider_worker_tracking_required": True,
        "provider_worker_drain_before_guard_restore": True,
        "provider_worker_leak_fail_closed": True,
        "pass_requires_all_effective_completed": True,
        "pass_requires_terminal_override_exercised": True,
        "hermes_completed_mutation_allowed": False,
        "scientific_hidden_policy_used": False,
        "scientific_scoring_performed": False,
        "source_acquisition_evidence_generated": False,
        "scientific_campaign_authorized": False,
        "provider_execution_authorized": False,
        "workflow_rerun_allowed": False,
        "same_request_stream_rerun_allowed": False,
        "replacement_logical_call_allowed": False,
        "predecessor_stream_rerun_or_replacement_allowed": False,
        "registry_promotion_authorized": False,
        "acceptance_action_authorized": False,
        "historical_substrate_enabled": False,
        "raw_credentials_persisted": False,
        "raw_provider_response_body_persisted": False,
        "raw_provider_error_body_persisted": False,
        "raw_provider_error_message_persisted": False,
        "raw_final_response_content_persisted": False,
    }


def load_plan() -> dict[str, Any]:
    return json.loads(PLAN.read_text())


def validate_plan(plan: dict[str, Any]) -> None:
    expected = expected_plan()
    if plan != expected:
        differing = sorted(
            key for key in set(plan) | set(expected) if plan.get(key) != expected.get(key)
        )
        raise AssertionError(f"request-plan drift: {differing}")


def cases(seed: int) -> list[dict[str, int]]:
    """Materialize eight deterministic synthetic engineering cases."""

    return [
        {
            "case_id": seed * 100 + index,
            "f0": (seed + 5 * index) % 13 - 6,
            "f1": (2 * seed + 7 * index) % 17 - 8,
            "f2": (3 * seed + 11 * index) % 19 - 9,
            "f3": (7 * seed + 13 * index) % 23 - 11,
        }
        for index in range(8)
    ]


def feedback(seed: int, budget: int) -> list[dict[str, Any]]:
    """Create fresh synthetic feedback with no hidden scientific truth."""

    rows = cases(seed - 2)
    return [
        {
            "case_id": row["case_id"],
            "chosen_action": adapter.ACTIONS[
                (seed + 2 * budget + 3 * index) % len(adapter.ACTIONS)
            ],
            "correct": bool((seed + budget + 2 * index) % 2),
            "bounded_feedback": "trajectory terminal-adapter engineering sentinel only",
        }
        for index, row in enumerate(rows)
    ]


def system_prompt() -> str:
    """Reuse the exact qualified terminal-adapter structured response contract."""

    return adapter.system_prompt()


def user_prompt(shape: str, seed: int, arm_budget: int | None, strategy: str) -> str:
    """Materialize one fresh non-scientific D2-shaped trajectory prompt."""

    valid_shapes = {
        "fresh_evaluation",
        "developed_development",
        "developed_evaluation",
        "oracle_evaluation",
    }
    if shape not in valid_shapes:
        raise ValueError(shape)
    sections = [
        "Objective: trajectory-scale engineering-only D2-shaped completion sentinel; "
        "the response is never scientifically scored.",
        f"Fresh namespace: {NAMESPACE}",
        f"Call shape: {shape}",
        f"Fresh seed: {seed}",
        "Task ecology: synthetic four-feature integer cases with no hidden scientific "
        "policy or answer key.",
    ]
    if arm_budget is not None:
        sections.append(f"Development budget shape: {arm_budget}")
    if strategy:
        sections.append("Prior bounded private strategy:\n" + strategy)
    if shape in {"developed_development", "developed_evaluation"}:
        if arm_budget is None:
            raise AssertionError("developed call requires arm budget")
        sections.append(
            "Outcome-bearing local feedback (synthetic engineering sentinel only):\n"
            + json.dumps(
                feedback(seed, arm_budget), sort_keys=True, separators=(",", ":")
            )
        )
    sections.append(
        "Cases to answer now:\n"
        + json.dumps(cases(seed), sort_keys=True, separators=(",", ":"))
    )
    if shape == "developed_development":
        sections.append(
            "Return choices and, if useful, an updated bounded private strategy. "
            "The feedback carries no scientific truth. Return JSON only."
        )
    else:
        sections.append(
            "Return choices under the exact structured contract. No correctness feedback "
            "will be returned. Return JSON only."
        )
    return "\n\n".join(sections)


def trajectory_specs(index: int) -> list[dict[str, Any]]:
    """Return one fresh 55-call trajectory specification."""

    if not 0 <= index < len(TRAJECTORIES):
        raise ValueError(index)
    out: list[dict[str, Any]] = []
    base_seed = 3_000_000 + 10_000 * index
    for evaluation in range(4):
        out.append(
            {
                "phase": f"fresh/evaluation{evaluation + 1}",
                "shape": "fresh_evaluation",
                "seed": base_seed + evaluation,
                "arm": "fresh",
                "arm_budget": None,
            }
        )
    for development_budget in (40, 80, 160):
        for batch in range(development_budget // 8):
            out.append(
                {
                    "phase": f"developed_{development_budget}/development{batch + 1}",
                    "shape": "developed_development",
                    "seed": base_seed + 1_000 + 10 * development_budget + batch,
                    "arm": f"developed_{development_budget}",
                    "arm_budget": development_budget,
                }
            )
        for evaluation in range(4):
            out.append(
                {
                    "phase": f"developed_{development_budget}/evaluation{evaluation + 1}",
                    "shape": "developed_evaluation",
                    "seed": base_seed + 2_000 + 10 * development_budget + evaluation,
                    "arm": f"developed_{development_budget}",
                    "arm_budget": development_budget,
                }
            )
    for evaluation in range(4):
        out.append(
            {
                "phase": f"oracle/evaluation{evaluation + 1}",
                "shape": "oracle_evaluation",
                "seed": base_seed + 5_000 + evaluation,
                "arm": "oracle",
                "arm_budget": None,
            }
        )
    if len(out) != TRAJECTORY_CALLS_EACH:
        raise AssertionError("trajectory topology drift")
    return out


def materialize_topology() -> dict[str, Any]:
    trajectories = []
    for index, name in enumerate(TRAJECTORIES):
        specs = trajectory_specs(index)
        trajectories.append(
            {
                "trajectory": name,
                "logical_calls": TRAJECTORY_CALLS_EACH,
                "logical_index_start": index * TRAJECTORY_CALLS_EACH,
                "logical_index_stop_exclusive": (index + 1) * TRAJECTORY_CALLS_EACH,
                "specs_sha256": hashlib.sha256(canonical(specs)).hexdigest(),
                "seed_min": min(int(spec["seed"]) for spec in specs),
                "seed_max": max(int(spec["seed"]) for spec in specs),
            }
        )
    return {
        "schema": "d2-trajectory-terminal-adapter-topology-v0.1",
        "issue": ISSUE,
        "fresh_namespace": NAMESPACE,
        "system_prompt_sha256": sha(system_prompt()),
        "selected_profile": PROFILE,
        "trajectories": trajectories,
        "trajectory_logical_calls_each": TRAJECTORY_CALLS_EACH,
        "trajectory_logical_calls_total": MAX_LOGICAL_CALLS,
        "trajectory_max_concurrency": MAX_TRAJECTORY_CONCURRENCY,
        "maximum_physical_sends_per_logical_call": MAX_SENDS_PER_LOGICAL,
        "maximum_physical_sends_total": MAX_SENDS_TOTAL,
        "scientific_hidden_policy_used": False,
        "scientific_scoring_performed": False,
        "production_historical_substrate_enabled": False,
    }


def validate_preserved_adapter_evidence() -> dict[str, int]:
    """Verify the authoritative #251 PASS evidence without provider traffic."""

    if file_sha(EVIDENCE_251) != EVIDENCE_251_SHA256:
        raise AssertionError("#251 preserved result drift")
    evidence = json.loads(EVIDENCE_251.read_text())
    if evidence.get("issue") != 251 or evidence.get("qualification_outcome") != "PASS":
        raise AssertionError("#251 qualification authority drift")
    expected = {
        "effective_completed": 72,
        "native_completed": 71,
        "terminal_overrides": 1,
        "physical_sends": 73,
    }
    actual = {
        "effective_completed": int(evidence.get("effective_completed_count", -1)),
        "native_completed": int(evidence.get("native_hermes_completed_count", -1)),
        "terminal_overrides": int(evidence.get("terminal_iteration_override_count", -1)),
        "physical_sends": int(evidence.get("physical_provider_sends_observed_total", -1)),
    }
    if actual != expected:
        raise AssertionError("#251 qualification metrics drift")
    if evidence.get("apparatus_failure") is not False:
        raise AssertionError("#251 apparatus state drift")
    return actual


def bounded_error(exc: BaseException) -> dict[str, Any]:
    text = str(exc)
    status = re.search(r"(?:status(?:_code)?[=: ]+|HTTP\s+)(\d{3})", text, re.I)
    code = re.search(
        r"""["']code["']\s*:\s*["']?(\d{3,6})""", text, re.I
    ) or re.search(r"provider(?:_code)?[=: ]+(\d{3,6})", text, re.I)
    return {
        "error_type": type(exc).__name__,
        "http_status": int(status.group(1)) if status else None,
        "provider_code": int(code.group(1)) if code else None,
        "error_text_length": len(text),
        "error_text_sha256": sha(text),
    }


def assert_execution_environment() -> None:
    if os.getenv("GLM_BASE_URL", "").strip().rstrip("/") != BASE_URL:
        raise RuntimeError("GLM_BASE_URL must equal the frozen Coding Plan base URL")
    for name in _FORBIDDEN_PROVIDER_CREDENTIAL_ENV_VARS:
        if os.getenv(name):
            raise RuntimeError(f"unexpected provider credential exposed: {name}")


def validate_runtime_versions() -> tuple[str, int, str]:
    import httpx
    import openai
    from openai._constants import DEFAULT_MAX_RETRIES

    hermes_version = importlib.metadata.version("hermes-agent")
    openai_version = importlib.metadata.version("openai")
    httpx_version = importlib.metadata.version("httpx")
    if hermes_version != HERMES_VERSION:
        raise AssertionError(f"Hermes version drift: {hermes_version}")
    if openai_version != OPENAI_VERSION or openai.__version__ != OPENAI_VERSION:
        raise AssertionError("OpenAI SDK version drift")
    if httpx_version != HTTPX_VERSION or httpx.__version__ != HTTPX_VERSION:
        raise AssertionError("httpx version drift")
    if int(DEFAULT_MAX_RETRIES) != OPENAI_DEFAULT_MAX_RETRIES:
        raise AssertionError("OpenAI SDK retry-default drift")
    if not hasattr(httpx.Client, "_send_single_request"):
        raise AssertionError("httpx physical-send hook unavailable")
    if not hasattr(httpx.AsyncClient, "_send_single_request"):
        raise AssertionError("httpx async physical-send hook unavailable")
    return hermes_version, int(DEFAULT_MAX_RETRIES), httpx_version
