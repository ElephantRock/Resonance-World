"""Frozen contract for #258 D2 JSON-mode structured-completion conformance."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import re
from collections import Counter
from pathlib import Path
from typing import Any

from resonance_world import d2_terminal_adapter as adapter

ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / "research" / "d2_json_mode_conformance"
PLAN = DIR / "REQUEST_PLAN.json"
PROBES = DIR / "PROBES.json"
MARKER = DIR / "RUN_D2_JSON_MODE_CONFORMANCE"
GUARD_PATH = ROOT / "src" / "resonance_world" / "provider_send_guard.py"
ADAPTER_PATH = ROOT / "src" / "resonance_world" / "d2_terminal_adapter.py"

ISSUE = 258
PR_NUMBER = 261
NAMESPACE = "rw.d2-json-mode-conformance.v1"
BASE_URL = "https://api.z.ai/api/coding/paas/v4"
PROVIDER = "zai"
API_MODE = "chat_completions"
MODEL = "glm-5.3"
HERMES_REPOSITORY = "hermes-agent-org/hermes"
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
AUTH_ENV = "D2_JSON_MODE_CONFORMANCE_AUTHORIZED"
AUTH_STRING = "Autonomous_Operating_Charter_Amendment_A1_standing_execution_authority"

GUARD_GIT_BLOB_SHA = "4b8896235d8048523d007400d0acfe85470f628c"
ADAPTER_GIT_BLOB_SHA = "ba16d2eb4b7255437c8ab224e91d5ed093897990"
PLAN_GIT_BLOB_SHA = "5055611c44b722a907549364ae661f12d53f1f13"
PROBES_GIT_BLOB_SHA = "2833691dd11cbcb46ce97ec682c6ce69a167fce7"

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


def sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_blob_sha(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()


def load_plan() -> dict[str, Any]:
    return json.loads(PLAN.read_text())


def load_probes() -> list[dict[str, Any]]:
    payload = json.loads(PROBES.read_text())
    if payload.get("schema") != "d2-json-mode-conformance-probes-v0.1":
        raise AssertionError("probe schema drift")
    if payload.get("issue") != ISSUE or payload.get("namespace") != NAMESPACE:
        raise AssertionError("probe authority drift")
    rows = payload.get("probes")
    if not isinstance(rows, list) or len(rows) != MAX_LOGICAL_CALLS:
        raise AssertionError("probe count drift")
    return rows


def validate_frozen_contract() -> list[dict[str, Any]]:
    if git_blob_sha(PLAN) != PLAN_GIT_BLOB_SHA:
        raise AssertionError("request plan blob drift")
    if git_blob_sha(PROBES) != PROBES_GIT_BLOB_SHA:
        raise AssertionError("probe manifest blob drift")
    if git_blob_sha(GUARD_PATH) != GUARD_GIT_BLOB_SHA:
        raise AssertionError("provider-send guard blob drift")
    if git_blob_sha(ADAPTER_PATH) != ADAPTER_GIT_BLOB_SHA:
        raise AssertionError("terminal adapter/parser blob drift")

    plan = load_plan()
    exact = {
        "schema": "d2-json-mode-conformance-request-plan-v0.1",
        "issue": ISSUE,
        "fresh_namespace": NAMESPACE,
        "predecessor_issue": 255,
        "predecessor_outcome_unchanged": "FAIL",
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
        "terminal_adapter_git_blob_sha": ADAPTER_GIT_BLOB_SHA,
        "provider_send_guard_git_blob_sha": GUARD_GIT_BLOB_SHA,
        "probe_count": MAX_LOGICAL_CALLS,
        "maximum_concurrency": MAX_CONCURRENCY,
        "maximum_physical_sends_per_logical_call": MAX_SENDS_PER_LOGICAL,
        "maximum_physical_sends_total": MAX_SENDS_TOTAL,
    }
    for key, value in exact.items():
        if plan.get(key) != value:
            raise AssertionError(f"request plan semantic drift: {key}")
    for key in (
        "logical_context_thread_propagation_required",
        "independent_logical_origin_attribution_required",
        "provider_worker_drain_before_hook_restore_required",
    ):
        if plan.get(key) is not True:
            raise AssertionError(f"request plan semantic drift: {key}")
    for key in (
        "parser_semantics_may_change",
        "hermes_completed_mutation_allowed",
        "provider_derived_strategy_propagation_allowed",
        "raw_final_response_content_persisted",
        "raw_provider_response_body_persisted",
        "raw_provider_error_body_or_message_persisted",
        "scientific_scoring_performed",
        "acceptance_action_authorized",
        "historical_substrate_enabled",
        "workflow_rerun_allowed",
        "same_request_stream_rerun_allowed",
        "replacement_or_rescue_allowed",
    ):
        if plan.get(key) is not False:
            raise AssertionError(f"request plan semantic drift: {key}")

    rows = load_probes()
    shapes = Counter()
    developed = Counter()
    seen_ids: set[str] = set()
    seen_seeds: set[int] = set()
    for index, row in enumerate(rows):
        if set(row) != {
            "logical_index", "probe_id", "call_shape", "development_budget", "seed"
        }:
            raise AssertionError("probe row keys drift")
        if row["logical_index"] != index:
            raise AssertionError("probe logical index drift")
        probe_id = row["probe_id"]
        seed = row["seed"]
        shape = row["call_shape"]
        budget = row["development_budget"]
        if not isinstance(probe_id, str) or not probe_id.startswith("jsonmode_"):
            raise AssertionError("probe id drift")
        if probe_id in seen_ids or seed in seen_seeds:
            raise AssertionError("probe identity reuse")
        if isinstance(seed, bool) or not isinstance(seed, int) or seed < 4_000_000:
            raise AssertionError("probe seed namespace drift")
        if shape not in {
            "fresh_evaluation", "developed_development",
            "developed_evaluation", "oracle_evaluation"
        }:
            raise AssertionError("probe shape drift")
        if shape.startswith("developed_"):
            if budget not in {40, 80, 160}:
                raise AssertionError("developed budget drift")
            developed[(shape, budget)] += 1
        elif budget is not None:
            raise AssertionError("non-developed budget must be null")
        seen_ids.add(probe_id)
        seen_seeds.add(seed)
        shapes[shape] += 1
    if shapes != Counter({
        "fresh_evaluation": 18,
        "developed_development": 18,
        "developed_evaluation": 18,
        "oracle_evaluation": 18,
    }):
        raise AssertionError("probe shape balance drift")
    expected_developed = Counter({
        ("developed_development", 40): 6,
        ("developed_development", 80): 6,
        ("developed_development", 160): 6,
        ("developed_evaluation", 40): 6,
        ("developed_evaluation", 80): 6,
        ("developed_evaluation", 160): 6,
    })
    if developed != expected_developed:
        raise AssertionError("developed budget balance drift")
    return rows


def cases(seed: int) -> list[dict[str, int]]:
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
    rows = cases(seed - 2)
    return [
        {
            "case_id": row["case_id"],
            "chosen_action": adapter.ACTIONS[
                (seed + 2 * budget + 3 * index) % len(adapter.ACTIONS)
            ],
            "correct": bool((seed + budget + 2 * index) % 2),
            "bounded_feedback": "json-mode conformance engineering sentinel only",
        }
        for index, row in enumerate(rows)
    ]


def synthetic_strategy(seed: int, budget: int) -> str:
    return "; ".join(
        (
            f"jsonmode-b{budget}-s{seed}",
            f"anchor-{adapter.ACTIONS[(seed + 1) % 4].lower()}",
            f"phase-{seed % 3}",
            f"span-{(seed % 19) + 9}",
            "exact-eight-action-json",
            "no-provider-derived-strategy-propagation",
        )
    )


def system_prompt() -> str:
    return adapter.system_prompt()


def user_prompt(probe: dict[str, Any]) -> str:
    shape = str(probe["call_shape"])
    seed = int(probe["seed"])
    budget = probe["development_budget"]
    sections = [
        "Objective: fresh engineering-only D2-shaped JSON-mode conformance sentinel; "
        "the response is never scientifically scored.",
        f"Fresh namespace: {NAMESPACE}",
        f"Probe: {probe['probe_id']}",
        f"Call shape: {shape}",
        f"Fresh seed: {seed}",
        "Task ecology: synthetic four-feature integer cases with no hidden scientific "
        "policy or answer key.",
    ]
    if shape.startswith("developed_"):
        if budget not in {40, 80, 160}:
            raise AssertionError("developed probe missing budget")
        sections.extend(
            (
                f"Development budget shape: {budget}",
                "Deterministic bounded strategy context (synthetic; never provider-derived):\n"
                + synthetic_strategy(seed, int(budget)),
                "Outcome-bearing local feedback (synthetic engineering sentinel only):\n"
                + json.dumps(
                    feedback(seed, int(budget)),
                    sort_keys=True,
                    separators=(",", ":"),
                ),
            )
        )
    sections.append(
        "Cases to answer now:\n"
        + json.dumps(cases(seed), sort_keys=True, separators=(",", ":"))
    )
    if shape == "developed_development":
        sections.append(
            "Return choices and, if useful, an updated bounded private strategy. "
            "No strategy from this response will propagate to another probe. Return JSON only."
        )
    else:
        sections.append(
            "Return choices under the exact structured contract. Return JSON only."
        )
    return "\n\n".join(sections)


def parse_diagnostic(text: str) -> str:
    """Classify parse failure without changing exact parser acceptance."""
    valid, _ = adapter.parse_response(text)
    if valid:
        return "valid"
    def reject_constant(value: str) -> None:
        raise ValueError(value)
    try:
        payload = json.loads(text, parse_constant=reject_constant)
    except (json.JSONDecodeError, TypeError, ValueError):
        return "json_decode_failure"
    if not isinstance(payload, dict):
        return "non_object_top_level"
    if not set(payload).issubset({"actions", "strategy"}):
        return "extra_keys"
    actions = payload.get("actions")
    if not isinstance(actions, list):
        return "actions_not_list"
    if len(actions) != 8:
        return "wrong_action_count"
    if any(action not in adapter.ACTIONS for action in actions):
        return "invalid_action"
    strategy = payload.get("strategy", "")
    if not isinstance(strategy, str):
        return "strategy_not_string"
    if len(strategy) > adapter.MAX_STRATEGY_CHARS:
        return "strategy_too_long"
    try:
        strategy.encode("ascii")
    except UnicodeEncodeError:
        return "strategy_non_ascii"
    return "structured_contract_invalid"


def bounded_error(exc: BaseException) -> dict[str, Any]:
    text = str(exc)
    status = re.search(r"(?:status(?:_code)?[=: ]+|HTTP\s+)(\d{3})", text, re.I)
    code = re.search(r"""["']code["']\s*:\s*["']?(\d{3,6})""", text, re.I)
    return {
        "error_type": type(exc).__name__,
        "http_status": int(status.group(1)) if status else None,
        "provider_code": int(code.group(1)) if code else None,
        "error_text_length": len(text),
        "error_text_sha256": sha(text),
    }


def assert_execution_environment() -> None:
    if os.getenv(AUTH_ENV) != "1":
        raise RuntimeError("provider execution not authorized")
    if not os.getenv("ZAI_API_KEY", "").strip():
        raise RuntimeError("ZAI_API_KEY is required")
    if os.getenv("GLM_BASE_URL", "").strip().rstrip("/") != BASE_URL:
        raise RuntimeError("GLM_BASE_URL must equal frozen Coding Plan base URL")
    for name in _FORBIDDEN_PROVIDER_CREDENTIAL_ENV_VARS:
        if os.getenv(name):
            raise RuntimeError(f"unexpected provider credential exposed: {name}")


def validate_runtime_versions() -> tuple[str, int, str]:
    import httpx
    import openai
    from openai._constants import DEFAULT_MAX_RETRIES
    hermes = importlib.metadata.version("hermes-agent")
    sdk = importlib.metadata.version("openai")
    hx = importlib.metadata.version("httpx")
    if hermes != HERMES_VERSION:
        raise AssertionError("Hermes version drift")
    if sdk != OPENAI_VERSION or openai.__version__ != OPENAI_VERSION:
        raise AssertionError("OpenAI SDK version drift")
    if hx != HTTPX_VERSION or httpx.__version__ != HTTPX_VERSION:
        raise AssertionError("httpx version drift")
    if int(DEFAULT_MAX_RETRIES) != OPENAI_DEFAULT_MAX_RETRIES:
        raise AssertionError("OpenAI retry default drift")
    if not hasattr(httpx.Client, "_send_single_request"):
        raise AssertionError("httpx physical-send hook unavailable")
    if not hasattr(httpx.AsyncClient, "_send_single_request"):
        raise AssertionError("httpx async physical-send hook unavailable")
    return hermes, int(DEFAULT_MAX_RETRIES), hx
