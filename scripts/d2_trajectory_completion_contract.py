"""Frozen contract for the D2 trajectory completion-envelope qualification."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / "research" / "d2_trajectory_completion_envelope"
PLAN = DIR / "REQUEST_PLAN.json"
TOPOLOGY = DIR / "TOPOLOGY.json"
MARKER = DIR / "RUN_D2_TRAJECTORY_COMPLETION_ENVELOPE"
GUARD_PATH = ROOT / "src" / "resonance_world" / "provider_send_guard.py"

ISSUE = 234
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
ACTIONS = ("KAPPA", "MICA", "ORBIT", "VELA")
SHAPES = (
    "fresh_evaluation",
    "developed_development",
    "developed_evaluation",
    "oracle_evaluation",
)
PROFILE = {"name": "iterations2_tokens768", "max_iterations": 2, "max_tokens": 768}
TRAJECTORIES = ("schema_like_0", "schema_like_1", "schema_like_2", "schema_like_3")
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
STAGE1_ISSUE = 231
STAGE1_EVIDENCE_MERGE_SHA = "f8ac997112efb1b677691f50029415cc6274f7b2"
STAGE1_RESULT_SHA256 = "9982e3c059e864cc06027173cfc3e3c17de7276393c501b15d4a4831a722f6a5"
AUTH_ENV = "D2_TRAJECTORY_COMPLETION_ENVELOPE_AUTHORIZED"
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
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_blob_sha(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()


def load_plan() -> dict[str, Any]:
    return json.loads(PLAN.read_text())


def validate_plan(plan: dict[str, Any]) -> None:
    expected = {
        "schema": "d2-trajectory-completion-envelope-request-plan-v0.1",
        "issue": ISSUE,
        "engineering_only": True,
        "purpose": "trajectory_scale_d2_shaped_completion_on_repaired_hermes_transport",
        "predecessor_apparatus_issue": 223,
        "predecessor_apparatus_result": "FAIL",
        "transport_conformance_issue": 229,
        "transport_conformance_result": "FAIL",
        "stage1_completion_issue": STAGE1_ISSUE,
        "stage1_completion_result": "PASS",
        "stage1_evidence_merge_sha": STAGE1_EVIDENCE_MERGE_SHA,
        "stage1_result_sha256": STAGE1_RESULT_SHA256,
        "selected_profile": PROFILE,
        "guard_repair_issue": 227,
        "guard_repair_pr": 228,
        "guard_repair_merge_sha": GUARD_REPAIR_MERGE_SHA,
        "provider_send_guard_git_blob_sha": GUARD_GIT_BLOB_SHA,
        "provider": "Z.AI",
        "subscription_product": "GLM Coding Plan",
        "supported_product_environment": "Hermes Agent Python library",
        "hermes_repository": HERMES_REPOSITORY,
        "hermes_revision": HERMES_REVISION,
        "hermes_package_version": HERMES_VERSION,
        "hermes_run_agent_blob_sha": HERMES_RUN_AGENT_BLOB_SHA,
        "openai_sdk_version": OPENAI_VERSION,
        "openai_sdk_default_max_retries": OPENAI_DEFAULT_MAX_RETRIES,
        "httpx_version": HTTPX_VERSION,
        "endpoint_base_url": BASE_URL,
        "provider_id": PROVIDER,
        "provider_base_url_env_var": "GLM_BASE_URL",
        "credential_env_var": "ZAI_API_KEY",
        "api_mode": API_MODE,
        "requested_model": MODEL,
        "sampling_temperature": TEMPERATURE,
        "thinking": THINKING,
        "enabled_toolsets": [],
        "memory_context_files_enabled": False,
        "persistent_session_enabled": False,
        "fallback_provider_configured": False,
        "general_api_fallback_allowed": False,
        "trajectory_names": list(TRAJECTORIES),
        "trajectory_logical_calls_each": TRAJECTORY_CALLS_EACH,
        "trajectory_logical_calls_total": MAX_LOGICAL_CALLS,
        "trajectory_max_concurrency": MAX_TRAJECTORY_CONCURRENCY,
        "maximum_registered_logical_calls": MAX_LOGICAL_CALLS,
        "maximum_physical_sends_per_logical_call": MAX_SENDS_PER_LOGICAL,
        "maximum_physical_sends_total": MAX_SENDS_TOTAL,
        "physical_send_guard_fail_closed": True,
        "logical_context_thread_propagation_required": True,
        "independent_request_origin_header": PROBE_ORIGIN_HEADER,
        "origin_reservation_match_required": True,
        "attribution_mismatch_fail_closed": True,
        "unregistered_outbound_http_blocked": True,
        "provider_worker_tracking_required": True,
        "provider_worker_target_module": PROVIDER_WORKER_TARGET_MODULE,
        "provider_worker_target_name": PROVIDER_WORKER_TARGET_NAME,
        "pinned_hermes_worker_join_until_exit_required": True,
        "provider_worker_drain_before_guard_restore": True,
        "provider_worker_drain_timeout_seconds": PROVIDER_WORKER_DRAIN_TIMEOUT_SECONDS,
        "provider_worker_leak_fail_closed": True,
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
    }
    if plan != expected:
        differing = sorted(
            key for key in set(plan) | set(expected) if plan.get(key) != expected.get(key)
        )
        raise AssertionError(f"request-plan drift: {differing}")


def cases(seed: int) -> list[dict[str, int]]:
    return [
        {
            "case_id": seed * 100 + i,
            "f0": (seed + 3 * i) % 11 - 5,
            "f1": (2 * seed + 5 * i) % 13 - 6,
            "f2": (3 * seed + 7 * i) % 17 - 8,
            "f3": (5 * seed + 11 * i) % 19 - 9,
        }
        for i in range(8)
    ]


def feedback(seed: int) -> list[dict[str, Any]]:
    return [
        {
            "case_id": row["case_id"],
            "chosen_action": ACTIONS[(seed + i) % 4],
            "correct": bool((seed + i) % 2),
            "bounded_feedback": "engineering sentinel feedback",
        }
        for i, row in enumerate(cases(seed))
    ]


def system_prompt() -> str:
    return (
        "Return one JSON object with an actions array containing exactly 8 entries, "
        "each one of KAPPA, MICA, ORBIT, VELA. You may also include strategy as a "
        "concise private working string. Other keys are ignored. Do not use markdown."
    )


def user_prompt(shape: str, seed: int, strategy: str = "") -> str:
    if shape not in SHAPES:
        raise ValueError(shape)
    sections = [
        "Objective: engineering-only D2-shaped structured completion sentinel; "
        "responses are never scientifically scored.",
        f"Call shape: {shape}",
        "Task ecology: synthetic four-feature integer cases with no hidden scientific policy.",
    ]
    if shape == "oracle_evaluation":
        sections.append(
            "Diagnostic instruction: emit any internally consistent valid action; "
            "there is no scientific answer key."
        )
    if strategy:
        sections.append("Prior private strategy:\n" + strategy[:1200])
    if shape in {"developed_development", "developed_evaluation"}:
        sections.append(
            "Outcome-bearing local feedback (synthetic engineering sentinel):\n"
            + json.dumps(feedback(seed - 1), sort_keys=True, separators=(",", ":"))
        )
    sections.append(
        "Cases to answer now:\n"
        + json.dumps(cases(seed), sort_keys=True, separators=(",", ":"))
    )
    if shape == "developed_development":
        sections.append(
            "Return choices and, if useful, an updated private strategy. "
            "This feedback carries no scientific truth."
        )
    else:
        sections.append(
            "These are held-out-shaped engineering cases. "
            "No correctness feedback will be returned."
        )
    return "\n\n".join(sections)


def trajectory_specs(index: int) -> list[dict[str, Any]]:
    if not 0 <= index < len(TRAJECTORIES):
        raise ValueError(index)
    out: list[dict[str, Any]] = []
    base_seed = 5000 + 1000 * index
    for evaluation in range(4):
        out.append(
            {
                "phase": f"fresh/evaluation{evaluation + 1}",
                "shape": "fresh_evaluation",
                "seed": base_seed + evaluation,
                "arm": "fresh",
            }
        )
    for development_budget in (40, 80, 160):
        for batch in range(development_budget // 8):
            out.append(
                {
                    "phase": f"developed_{development_budget}/development{batch + 1}",
                    "shape": "developed_development",
                    "seed": base_seed + 10 * development_budget + batch,
                    "arm": f"developed_{development_budget}",
                }
            )
        for evaluation in range(4):
            out.append(
                {
                    "phase": f"developed_{development_budget}/evaluation{evaluation + 1}",
                    "shape": "developed_evaluation",
                    "seed": base_seed + 10 * development_budget + 100 + evaluation,
                    "arm": f"developed_{development_budget}",
                }
            )
    for evaluation in range(4):
        out.append(
            {
                "phase": f"oracle/evaluation{evaluation + 1}",
                "shape": "oracle_evaluation",
                "seed": base_seed + 3000 + evaluation,
                "arm": "oracle",
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
                "topology_sha256": hashlib.sha256(canonical(specs)).hexdigest(),
            }
        )
    return {
        "schema": "d2-trajectory-completion-envelope-topology-v0.1",
        "issue": ISSUE,
        "system_prompt_sha256": sha(system_prompt()),
        "selected_profile": PROFILE,
        "trajectories": trajectories,
        "trajectory_logical_calls_each": TRAJECTORY_CALLS_EACH,
        "trajectory_logical_calls_total": MAX_LOGICAL_CALLS,
        "trajectory_max_concurrency": MAX_TRAJECTORY_CONCURRENCY,
        "maximum_registered_logical_calls": MAX_LOGICAL_CALLS,
        "maximum_physical_sends_per_logical_call": MAX_SENDS_PER_LOGICAL,
        "maximum_physical_sends_total": MAX_SENDS_TOTAL,
        "scientific_hidden_policy_used": False,
        "scientific_scoring_performed": False,
        "production_historical_substrate_enabled": False,
    }


def bounded_error(exc: BaseException) -> dict[str, Any]:
    text = str(exc)
    status = re.search(
        r"(?:status(?:_code)?[=: ]+|HTTP\s+)(\d{3})", text, re.I
    ) or re.search(r"\b(4\d\d|5\d\d)\b", text)
    code = re.search(
        r"""["']code["']\s*:\s*["']?(\d{3,6})""", text, re.I
    ) or re.search(r"provider(?:_code)?[=: ]+(\d{3,6})", text, re.I)
    http_status = int(status.group(1)) if status else None
    provider_code = int(code.group(1)) if code else None
    return {
        "error_type": type(exc).__name__,
        "http_status": http_status,
        "provider_code": provider_code,
        "error_text_length": len(text),
        "error_text_sha256": sha(text),
        "terminal_http_429_code_1113": http_status == 429 and provider_code == 1113,
    }


def parse_response(text: str) -> str:
    def reject_constant(value: str) -> None:
        raise ValueError(f"non-standard JSON constant prohibited: {value}")

    payload = json.loads(text, parse_constant=reject_constant)
    if not isinstance(payload, dict):
        raise ValueError("response must be JSON object")
    actions = payload.get("actions")
    if (
        not isinstance(actions, list)
        or len(actions) != 8
        or any(action not in ACTIONS for action in actions)
    ):
        raise ValueError("invalid actions contract")
    strategy = payload.get("strategy")
    if strategy is None:
        return ""
    if not isinstance(strategy, str):
        raise ValueError("strategy must be string")
    return strategy[:1200]


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
        raise AssertionError(f"OpenAI SDK version drift: {openai_version}/{openai.__version__}")
    if httpx_version != HTTPX_VERSION or httpx.__version__ != HTTPX_VERSION:
        raise AssertionError(f"httpx version drift: {httpx_version}/{httpx.__version__}")
    if DEFAULT_MAX_RETRIES != OPENAI_DEFAULT_MAX_RETRIES:
        raise AssertionError(f"OpenAI SDK retry-default drift: {DEFAULT_MAX_RETRIES}")
    if not hasattr(httpx.Client, "_send_single_request"):
        raise AssertionError("httpx physical-send hook unavailable")
    if not hasattr(httpx.AsyncClient, "_send_single_request"):
        raise AssertionError("httpx async physical-send hook unavailable")
    return hermes_version, int(DEFAULT_MAX_RETRIES), httpx_version
