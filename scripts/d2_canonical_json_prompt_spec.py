# ruff: noqa
"""Frozen constants and validation for #270 canonical-JSON prompt conformance."""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import re
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / "research" / "d2_canonical_json_prompt"
PLAN = DIR / "REQUEST_PLAN.json"
PROBES = DIR / "PROBES.json"
MARKER = DIR / "RUN_D2_CANONICAL_JSON_PROMPT"
GUARD_PATH = ROOT / "src" / "resonance_world" / "provider_send_guard.py"
ADAPTER_PATH = ROOT / "src" / "resonance_world" / "d2_terminal_adapter.py"

ISSUE = 270
PR_NUMBER = 271
NAMESPACE = "rw.d2-canonical-json-prompt.v1"
BASE_URL = "https://api.z.ai/api/coding/paas/v4"
PROVIDER = "zai"
API_MODE = "chat_completions"
MODEL = "glm-5.3"
HERMES_REVISION = "036cbdfa0a3158454a0a2a7a7388cf70353326b4"
HERMES_VERSION = "0.8.0"
HERMES_RUN_AGENT_BLOB_SHA = "4c0d3be4b0c2d364c550fa663d34f6545c9e6d20"
OPENAI_VERSION = "2.21.0"
HTTPX_VERSION = "0.28.1"
OPENAI_DEFAULT_MAX_RETRIES = 2
MAX_ITERATIONS = 2
MAX_TOKENS = 768
TEMPERATURE = 0.8
THINKING = {"type": "disabled"}
RESPONSE_FORMAT = {"type": "json_object"}
MAX_CONCURRENCY = 4
MAX_LOGICAL_CALLS = 72
MAX_SENDS_PER_LOGICAL = 36
MAX_SENDS_TOTAL = 180
PROBE_ORIGIN_HEADER = "X-Resonance-World-Logical-Index"
PROVIDER_WORKER_TARGET_MODULE = "run_agent"
PROVIDER_WORKER_TARGET_NAME = "_call"
PROVIDER_WORKER_DRAIN_TIMEOUT_SECONDS = 60.0
AUTH_ENV = "D2_CANONICAL_JSON_PROMPT_AUTHORIZED"
AUTH_STRING = "Autonomous_Operating_Charter_Amendment_A1_standing_execution_authority"

GUARD_GIT_BLOB_SHA = "4b8896235d8048523d007400d0acfe85470f628c"
ADAPTER_GIT_BLOB_SHA = "ba16d2eb4b7255437c8ab224e91d5ed093897990"
PLAN_GIT_BLOB_SHA = "66b23953edb7620a8c1c67bbaf78960d54ffb283"
PROBES_GIT_BLOB_SHA = "fcf7e3bee404c3247498cd95cd4095d13c993032"
SYSTEM_PROMPT_SHA256 = "fb35b51c6a6243543cb628a66607ca77f06fbdcc504c923d3c3b2c342eeab7f7"

FORBIDDEN = (
    "OPENROUTER_API_KEY", "OPENAI_API_KEY", "OPENAI_BASE_URL",
    "ANTHROPIC_API_KEY", "ANTHROPIC_TOKEN", "NOUS_API_KEY", "GLM_API_KEY",
    "Z_AI_API_KEY", "KIMI_API_KEY", "MINIMAX_API_KEY", "DEEPSEEK_API_KEY",
    "DASHSCOPE_API_KEY", "XAI_API_KEY",
)

def sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()

def git_blob_sha(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()

def load_probes() -> list[dict[str, Any]]:
    payload = json.loads(PROBES.read_text())
    expected = {
        "schema": "d2-canonical-json-prompt-probes-v0.1",
        "issue": ISSUE,
        "namespace": NAMESPACE,
        "seed_start": 4300000,
        "shape_order": ["fresh_evaluation", "developed_development", "developed_evaluation", "oracle_evaluation"],
        "probes_per_shape": 18,
        "developed_budget_order": [40, 80, 160],
        "probes_per_developed_budget": 6,
    }
    if payload != expected:
        raise AssertionError("probe manifest drift")
    rows: list[dict[str, Any]] = []
    logical = 0
    for shape in payload["shape_order"]:
        for local in range(18):
            budget = payload["developed_budget_order"][local // 6] if shape.startswith("developed_") else None
            rows.append({
                "logical_index": logical,
                "probe_id": f"canonical_{shape}_{local:02d}",
                "call_shape": shape,
                "development_budget": budget,
                "seed": payload["seed_start"] + logical,
            })
            logical += 1
    return rows

def validate_frozen_contract() -> list[dict[str, Any]]:
    for path, expected in (
        (PLAN, PLAN_GIT_BLOB_SHA),
        (PROBES, PROBES_GIT_BLOB_SHA),
        (GUARD_PATH, GUARD_GIT_BLOB_SHA),
        (ADAPTER_PATH, ADAPTER_GIT_BLOB_SHA),
    ):
        if git_blob_sha(path) != expected:
            raise AssertionError(f"blob drift: {path.name}")
    plan = json.loads(PLAN.read_text())
    required = {
        "schema": "d2-canonical-json-prompt-request-plan-v0.1",
        "issue": ISSUE,
        "fresh_namespace": NAMESPACE,
        "predecessor_projection_issue": 263,
        "predecessor_projection_outcome_unchanged": "FAIL_STRUCTURED_CONTRACT",
        "predecessor_json_mode_issue": 258,
        "predecessor_json_mode_outcome_unchanged": "FAIL_STRUCTURED_CONTRACT",
        "qualified_terminal_adapter_issue": 251,
        "qualified_terminal_adapter_outcome_unchanged": "PASS",
        "endpoint_base_url": BASE_URL,
        "provider_id": PROVIDER,
        "api_mode": API_MODE,
        "requested_model": MODEL,
        "hermes_revision": HERMES_REVISION,
        "hermes_package_version": HERMES_VERSION,
        "hermes_run_agent_blob_sha": HERMES_RUN_AGENT_BLOB_SHA,
        "openai_sdk_version": OPENAI_VERSION,
        "httpx_version": HTTPX_VERSION,
        "max_iterations": MAX_ITERATIONS,
        "max_tokens": MAX_TOKENS,
        "sampling_temperature": TEMPERATURE,
        "thinking": THINKING,
        "request_intervention": {"response_format": RESPONSE_FORMAT},
        "prompt_intervention": "canonical_json_exemplar_and_explicit_array_positional_constraints",
        "system_prompt_sha256": SYSTEM_PROMPT_SHA256,
        "parser_intervention": "none_unchanged_exact_eight_action_contract",
        "recognized_top_level_keys": ["actions", "strategy"],
        "probe_count": MAX_LOGICAL_CALLS,
        "maximum_concurrency": MAX_CONCURRENCY,
        "maximum_physical_sends_per_logical_call": MAX_SENDS_PER_LOGICAL,
        "maximum_physical_sends_total": MAX_SENDS_TOTAL,
    }
    for key, value in required.items():
        if plan.get(key) != value:
            raise AssertionError(f"plan drift: {key}")
    for key in (
        "logical_context_thread_propagation_required",
        "independent_logical_origin_attribution_required",
        "provider_worker_drain_before_hook_restore_required",
        "canonical_exemplar_shape_only",
        "canonical_exemplar_copy_prohibited",
        "actions_array_required",
        "actions_positionally_correspond_to_cases",
    ):
        if plan.get(key) is not True:
            raise AssertionError(f"plan drift: {key}")
    forbidden_false = (
        "unknown_top_level_projection_allowed", "embedded_json_extraction_allowed",
        "markdown_fence_stripping_allowed", "json_syntax_repair_allowed",
        "required_field_coercion_allowed", "object_to_array_conversion_allowed",
        "action_vocabulary_expansion_allowed", "action_count_change_allowed",
        "strategy_bound_change_allowed", "hermes_completed_mutation_allowed",
        "provider_derived_strategy_propagation_allowed", "raw_final_response_content_persisted",
        "raw_provider_response_body_persisted", "raw_provider_error_body_or_message_persisted",
        "scientific_scoring_performed", "acceptance_action_authorized",
        "historical_substrate_enabled", "workflow_rerun_allowed",
        "same_request_stream_rerun_allowed", "replacement_or_rescue_allowed",
    )
    if any(plan.get(key) is not False for key in forbidden_false):
        raise AssertionError("plan authority drift")
    rows = load_probes()
    shapes = Counter(row["call_shape"] for row in rows)
    developed = Counter(
        (row["call_shape"], row["development_budget"])
        for row in rows if row["call_shape"].startswith("developed_")
    )
    if shapes != Counter({shape: 18 for shape in ("fresh_evaluation", "developed_development", "developed_evaluation", "oracle_evaluation")}):
        raise AssertionError("shape balance drift")
    if developed != Counter({(shape, budget): 6 for shape in ("developed_development", "developed_evaluation") for budget in (40, 80, 160)}):
        raise AssertionError("budget balance drift")
    if len({row["probe_id"] for row in rows}) != 72 or len({row["seed"] for row in rows}) != 72 or min(row["seed"] for row in rows) < 4_300_000:
        raise AssertionError("fresh identity drift")
    return rows

def bounded_error(exc: BaseException) -> dict[str, Any]:
    text = str(exc)
    status = re.search(r"(?:status(?:_code)?[=: ]+|HTTP\s+)(\d{3})", text, re.I)
    code = re.search(r"[\"']code[\"']\s*:\s*[\"']?(\d{3,6})", text, re.I)
    return {
        "error_type": type(exc).__name__,
        "http_status": int(status.group(1)) if status else None,
        "provider_code": int(code.group(1)) if code else None,
        "error_text_length": len(text),
        "error_text_sha256": sha(text),
    }

def assert_execution_environment() -> None:
    if os.getenv(AUTH_ENV) != "1" or not os.getenv("ZAI_API_KEY", "").strip():
        raise RuntimeError("provider execution not authorized")
    if os.getenv("GLM_BASE_URL", "").strip().rstrip("/") != BASE_URL:
        raise RuntimeError("base URL drift")
    if any(os.getenv(key) for key in FORBIDDEN):
        raise RuntimeError("unexpected provider credential exposed")

def validate_runtime_versions() -> tuple[str, int, str]:
    import httpx
    from openai._constants import DEFAULT_MAX_RETRIES
    hermes = importlib.metadata.version("hermes-agent")
    openai_version = importlib.metadata.version("openai")
    httpx_version = importlib.metadata.version("httpx")
    if (hermes, openai_version, httpx_version, httpx.__version__, DEFAULT_MAX_RETRIES) != (
        HERMES_VERSION, OPENAI_VERSION, HTTPX_VERSION, HTTPX_VERSION, OPENAI_DEFAULT_MAX_RETRIES
    ):
        raise AssertionError("runtime version drift")
    return hermes, DEFAULT_MAX_RETRIES, httpx_version
