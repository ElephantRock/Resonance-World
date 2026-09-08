#!/usr/bin/env python3
"""Stage-1 D2-shaped completion-envelope qualification on repaired Hermes transport."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import re
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from resonance_world.provider_send_guard import ProviderSendBudget, SendReservation

ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / "research" / "d2_stage1_completion_envelope"
PLAN = DIR / "REQUEST_PLAN.json"
TOPOLOGY = DIR / "TOPOLOGY.json"
MARKER = DIR / "RUN_D2_STAGE1_COMPLETION_ENVELOPE"

ISSUE = 231
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
PROFILES = (
    {"name": "iterations2_tokens768", "max_iterations": 2, "max_tokens": 768},
    {"name": "iterations2_tokens1024", "max_iterations": 2, "max_tokens": 1024},
    {"name": "iterations3_tokens1024", "max_iterations": 3, "max_tokens": 1024},
)
PROFILE_CALLS = 12
MAX_LOGICAL_CALLS = 12
MAX_SENDS_PER_LOGICAL = 54
MAX_SENDS_TOTAL = 120
PROBE_ORIGIN_HEADER = "X-Resonance-World-Logical-Index"
GUARD_REPAIR_MERGE_SHA = "47383f2b18c993965c89350609a4c9691897bdde"
GUARD_GIT_BLOB_SHA = "4b8896235d8048523d007400d0acfe85470f628c"
GUARD_PATH = ROOT / "src" / "resonance_world" / "provider_send_guard.py"
AUTH_ENV = "D2_STAGE1_COMPLETION_ENVELOPE_AUTHORIZED"
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


class LogicalAttributionMismatch(RuntimeError):
    """Raised before transmission when request origin disagrees with logical context."""


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
        "schema": "d2-stage1-completion-envelope-request-plan-v0.1",
        "issue": ISSUE,
        "engineering_only": True,
        "purpose": "d2_shaped_stage1_completion_envelope_on_repaired_hermes_transport",
        "predecessor_apparatus_issue": 223,
        "predecessor_apparatus_result": "FAIL",
        "transport_conformance_issue": 229,
        "transport_conformance_result": "FAIL",
        "transport_attribution_subcriterion_observed": "4_of_4_intact",
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
        "profiles": list(PROFILES),
        "profile_call_shapes": list(SHAPES),
        "profile_logical_calls": PROFILE_CALLS,
        "all_profiles_execute": True,
        "selected_profile_rule": "first_passing_profile_in_registered_order",
        "trajectory_stage_registered": False,
        "maximum_registered_logical_calls": MAX_LOGICAL_CALLS,
        "maximum_physical_sends_per_logical_call": MAX_SENDS_PER_LOGICAL,
        "maximum_physical_sends_total": MAX_SENDS_TOTAL,
        "physical_send_guard_fail_closed": True,
        "logical_context_thread_propagation_required": True,
        "independent_request_origin_header": PROBE_ORIGIN_HEADER,
        "origin_reservation_match_required": True,
        "attribution_mismatch_fail_closed": True,
        "unregistered_outbound_http_blocked": True,
        "scientific_hidden_policy_used": False,
        "scientific_scoring_performed": False,
        "source_acquisition_evidence_generated": False,
        "scientific_campaign_authorized": False,
        "provider_execution_authorized": False,
        "workflow_rerun_allowed": False,
        "same_request_stream_rerun_allowed": False,
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


def materialize_topology() -> dict[str, Any]:
    shapes = []
    for i, shape in enumerate(SHAPES):
        text = user_prompt(shape, 100 + i, "S" * 320)
        shapes.append(
            {
                "shape": shape,
                "seed": 100 + i,
                "prior_strategy_length": 320,
                "prompt_bytes": len(text.encode()),
                "prompt_sha256": sha(text),
            }
        )
    return {
        "schema": "d2-stage1-completion-envelope-topology-v0.1",
        "issue": ISSUE,
        "system_prompt_sha256": sha(system_prompt()),
        "profile_call_shapes": shapes,
        "profiles": list(PROFILES),
        "profile_logical_calls": PROFILE_CALLS,
        "maximum_registered_logical_calls": MAX_LOGICAL_CALLS,
        "maximum_physical_sends_per_logical_call": MAX_SENDS_PER_LOGICAL,
        "maximum_physical_sends_total": MAX_SENDS_TOTAL,
        "trajectory_stage_registered": False,
        "scientific_hidden_policy_used": False,
        "scientific_scoring_performed": False,
        "production_historical_substrate_enabled": False,
    }


def preflight() -> dict[str, Any]:
    validate_plan(load_plan())
    if MARKER.exists():
        raise AssertionError("execution marker must be absent from frozen candidate")
    topology = materialize_topology()
    if json.loads(TOPOLOGY.read_text()) != topology:
        raise AssertionError("committed topology drift")
    if git_blob_sha(GUARD_PATH) != GUARD_GIT_BLOB_SHA:
        raise AssertionError("provider-send guard blob drift")
    return {
        "schema": "d2-stage1-completion-envelope-preflight-v0.1",
        "issue": ISSUE,
        "engineering_only": True,
        "provider_execution_performed": False,
        "execution_marker_absent": True,
        "request_plan_sha256": file_sha(PLAN),
        "topology_sha256": file_sha(TOPOLOGY),
        "provider_send_guard_git_blob_sha": git_blob_sha(GUARD_PATH),
        "topology": topology,
        "scientific_scoring_performed": False,
        "historical_substrate_enabled": False,
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


def _assert_execution_environment() -> None:
    if os.getenv("GLM_BASE_URL", "").strip().rstrip("/") != BASE_URL:
        raise RuntimeError("GLM_BASE_URL must equal the frozen Coding Plan base URL")
    for name in _FORBIDDEN_PROVIDER_CREDENTIAL_ENV_VARS:
        if os.getenv(name):
            raise RuntimeError(f"unexpected provider credential exposed: {name}")


def _validate_runtime_versions() -> tuple[str, int, str]:
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


class TransportLedger:
    """Bounded transport metadata preserving independent origin and reservation identity."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._rows = {index: [] for index in range(MAX_LOGICAL_CALLS)}
        self._attribution_mismatches = 0

    def record_attribution_mismatch(self) -> None:
        with self._lock:
            self._attribution_mismatches += 1

    @property
    def attribution_mismatches(self) -> int:
        with self._lock:
            return self._attribution_mismatches

    def begin(self, reservation: SendReservation, origin_logical_index: int) -> int:
        if origin_logical_index != reservation.logical_index:
            self.record_attribution_mismatch()
            raise LogicalAttributionMismatch(
                "request origin disagrees with provider-send reservation"
            )
        row = {
            "origin_logical_index": origin_logical_index,
            "logical_index": reservation.logical_index,
            "logical_send_index": reservation.logical_send_index,
            "total_send_index": reservation.total_send_index,
            "http_status": None,
            "transport_error_type": None,
        }
        with self._lock:
            rows = self._rows[reservation.logical_index]
            rows.append(row)
            return len(rows) - 1

    def response(self, reservation: SendReservation, row_index: int, status: int) -> None:
        with self._lock:
            self._rows[reservation.logical_index][row_index]["http_status"] = int(status)

    def error(self, reservation: SendReservation, row_index: int, exc: BaseException) -> None:
        with self._lock:
            self._rows[reservation.logical_index][row_index]["transport_error_type"] = (
                type(exc).__name__
            )

    def rows(self, logical_index: int) -> list[dict[str, Any]]:
        with self._lock:
            return [dict(row) for row in self._rows[logical_index]]


def _verified_origin_logical_index(
    request: Any,
    budget: ProviderSendBudget,
    ledger: TransportLedger,
) -> int:
    raw = request.headers.get(PROBE_ORIGIN_HEADER)
    try:
        origin = int(raw) if raw is not None else -1
    except (TypeError, ValueError):
        origin = -1
    registered = budget.current_logical_index()
    if not 0 <= origin < MAX_LOGICAL_CALLS or registered is None or origin != registered:
        ledger.record_attribution_mismatch()
        raise LogicalAttributionMismatch(
            "independent request origin does not match registered logical context"
        )
    return origin


@contextmanager
def transport_guard(
    budget: ProviderSendBudget,
    ledger: TransportLedger,
) -> Iterator[None]:
    import httpx

    original_sync = httpx.Client._send_single_request
    original_async = httpx.AsyncClient._send_single_request

    def capped_sync(client: Any, request: Any) -> Any:
        origin = _verified_origin_logical_index(request, budget, ledger)
        reservation = budget.reserve(str(request.url))
        row_index = ledger.begin(reservation, origin)
        try:
            response = original_sync(client, request)
        except Exception as exc:
            ledger.error(reservation, row_index, exc)
            raise
        ledger.response(reservation, row_index, response.status_code)
        return response

    async def capped_async(client: Any, request: Any) -> Any:
        origin = _verified_origin_logical_index(request, budget, ledger)
        reservation = budget.reserve(str(request.url))
        row_index = ledger.begin(reservation, origin)
        try:
            response = await original_async(client, request)
        except Exception as exc:
            ledger.error(reservation, row_index, exc)
            raise
        ledger.response(reservation, row_index, response.status_code)
        return response

    httpx.Client._send_single_request = capped_sync
    httpx.AsyncClient._send_single_request = capped_async
    try:
        yield
    finally:
        httpx.Client._send_single_request = original_sync
        httpx.AsyncClient._send_single_request = original_async


def new_agent(iterations: int, tokens: int, logical_index: int) -> Any:
    from run_agent import AIAgent

    agent = AIAgent(
        provider=PROVIDER,
        api_mode=API_MODE,
        model=MODEL,
        max_iterations=iterations,
        enabled_toolsets=[],
        quiet_mode=True,
        save_trajectories=False,
        ephemeral_system_prompt=system_prompt(),
        max_tokens=tokens,
        request_overrides={
            "temperature": TEMPERATURE,
            "extra_body": {"thinking": THINKING},
            "extra_headers": {PROBE_ORIGIN_HEADER: str(logical_index)},
        },
        skip_context_files=True,
        skip_memory=True,
        persist_session=False,
        fallback_model=None,
    )
    client_retries = int(getattr(agent.client, "max_retries", -1))
    if client_retries != OPENAI_DEFAULT_MAX_RETRIES:
        raise AssertionError(f"OpenAI retry drift: {client_retries}")
    if agent.tools != [] or agent.valid_tool_names or agent._fallback_chain:
        raise AssertionError("Hermes tool/fallback drift")
    if agent.model != MODEL or agent.provider != PROVIDER or agent.api_mode != API_MODE:
        raise AssertionError("Hermes route drift")
    if (
        str(agent.client.base_url).rstrip("/") != BASE_URL
        or str(agent.base_url).rstrip("/") != BASE_URL
    ):
        raise AssertionError("Hermes base URL drift")
    kwargs = agent._build_api_kwargs([{"role": "user", "content": "preflight"}])
    if float(kwargs.get("temperature", -1)) != TEMPERATURE:
        raise AssertionError("sampling temperature drift")
    if kwargs.get("extra_body") != {"thinking": THINKING}:
        raise AssertionError("thinking drift")
    headers = kwargs.get("extra_headers") or {}
    if str(headers.get(PROBE_ORIGIN_HEADER, "")) != str(logical_index):
        raise AssertionError("independent request-origin header drift")
    return agent


def run_call(
    budget: ProviderSendBudget,
    ledger: TransportLedger,
    logical: int,
    call_id: str,
    profile: dict[str, Any],
    shape: str,
    seed: int,
    strategy: str,
) -> tuple[dict[str, Any], str]:
    prompt = user_prompt(shape, seed, strategy)
    before_unexpected = budget.blocked_unexpected
    before_budget = budget.blocked_budget
    before_mismatch = ledger.attribution_mismatches
    row: dict[str, Any] = {
        "logical_index": logical,
        "call_id": call_id,
        "call_shape": shape,
        "max_iterations": profile["max_iterations"],
        "max_tokens": profile["max_tokens"],
        "prompt_bytes": len(prompt.encode()),
        "prompt_sha256": sha(prompt),
    }
    agent: Any | None = None
    next_strategy = strategy
    try:
        with budget.logical_call(logical):
            agent = new_agent(
                int(profile["max_iterations"]),
                int(profile["max_tokens"]),
                logical,
            )
            result = agent.run_conversation(user_message=prompt)
        api_calls = int(getattr(agent, "_api_call_count", 0))
        final = str(result.get("final_response") or "")
        if (
            result.get("failed") is True
            or result.get("completed") is not True
            or bool(result.get("error"))
            or not final.strip()
        ):
            raise RuntimeError(
                str(
                    result.get("error")
                    or "Hermes returned non-completed engineering logical call"
                )
            )
        if not 1 <= api_calls <= int(profile["max_iterations"]):
            raise RuntimeError(f"Hermes semantic API-call count drift: {api_calls}")
        next_strategy = parse_response(final)
        attempts = ledger.rows(logical)
        send_count = budget.sends_for_logical_call(logical)
        if not 1 <= send_count <= int(profile["max_iterations"]) * 18:
            raise AssertionError("physical-send count outside profile bound")
        if len(attempts) != send_count:
            raise AssertionError("transport ledger/send-accounting drift")
        finish = result.get("finish_reason")
        stop = result.get("stop_reason")
        if not isinstance(finish, (str, int, float, bool, type(None))):
            finish = None
        if not isinstance(stop, (str, int, float, bool, type(None))):
            stop = None
        row.update(
            {
                "status": "success",
                "completed": True,
                "agent_api_calls_observed": api_calls,
                "final_response_length": len(final),
                "final_response_sha256": sha(final),
                "strategy_present": bool(next_strategy),
                "strategy_length": len(next_strategy),
                "strategy_sha256": sha(next_strategy) if next_strategy else None,
                "finish_reason": finish,
                "stop_reason": stop,
                "provider_http_attempts_observed": send_count,
                "attempts": attempts,
                "terminal_http_429_code_1113": False,
            }
        )
    except Exception as exc:
        attempts = ledger.rows(logical)
        row.update(
            {
                "status": "failure",
                "completed": False,
                "agent_api_calls_observed": int(
                    getattr(agent, "_api_call_count", 0) if agent is not None else 0
                ),
                "provider_http_attempts_observed": budget.sends_for_logical_call(logical),
                "attempts": attempts,
                **bounded_error(exc),
            }
        )
    row.update(
        {
            "unexpected_outbound_blocks": budget.blocked_unexpected - before_unexpected,
            "provider_budget_blocks": budget.blocked_budget - before_budget,
            "attribution_mismatch_blocks": ledger.attribution_mismatches - before_mismatch,
            "logical_attribution_integrity": all(
                attempt["origin_logical_index"] == logical
                and attempt["logical_index"] == logical
                for attempt in row["attempts"]
            ),
        }
    )
    return row, next_strategy


def profile_pass(profile: dict[str, Any], rows: list[dict[str, Any]]) -> bool:
    return len(rows) == 4 and all(
        row.get("status") == "success"
        and 1
        <= int(row.get("agent_api_calls_observed", 0))
        <= int(profile["max_iterations"])
        and row.get("logical_attribution_integrity") is True
        and int(row.get("unexpected_outbound_blocks", 0)) == 0
        and int(row.get("provider_budget_blocks", 0)) == 0
        and int(row.get("attribution_mismatch_blocks", 0)) == 0
        and row.get("terminal_http_429_code_1113") is False
        for row in rows
    )


def marker() -> dict[str, str]:
    if not MARKER.exists():
        raise RuntimeError("authorization marker absent")
    fields = dict(
        line.split("=", 1) for line in MARKER.read_text().splitlines() if line
    )
    if (
        set(fields) != {"candidate_sha", "issue", "authorization"}
        or fields["issue"] != str(ISSUE)
        or fields["authorization"] != AUTH_STRING
    ):
        raise RuntimeError("authorization marker invalid")
    if not re.fullmatch(r"[0-9a-f]{40}", fields["candidate_sha"]):
        raise RuntimeError("candidate SHA invalid")
    return fields


def execute() -> dict[str, Any]:
    if os.getenv(AUTH_ENV) != "1" or not os.getenv("ZAI_API_KEY", "").strip():
        raise RuntimeError("provider execution not authorized/credentialed")
    _assert_execution_environment()
    validate_plan(load_plan())
    auth = marker()
    if git_blob_sha(GUARD_PATH) != GUARD_GIT_BLOB_SHA:
        raise AssertionError("provider-send guard blob drift")
    hermes_version, sdk_retries, httpx_version = _validate_runtime_versions()
    budget = ProviderSendBudget(
        allowed_url_prefix=BASE_URL,
        maximum_logical_calls=MAX_LOGICAL_CALLS,
        maximum_sends_per_logical_call=MAX_SENDS_PER_LOGICAL,
        maximum_sends_total=MAX_SENDS_TOTAL,
    )
    ledger = TransportLedger()
    profiles: list[dict[str, Any]] = []
    logical = 0
    with budget.propagate_to_child_threads():
        with transport_guard(budget, ledger):
            for profile in PROFILES:
                rows = []
                for i, shape in enumerate(SHAPES):
                    row, _ = run_call(
                        budget,
                        ledger,
                        logical,
                        f"profile/{profile['name']}/{shape}",
                        profile,
                        shape,
                        100 + i,
                        "S" * 320,
                    )
                    rows.append(row)
                    logical += 1
                profiles.append(
                    {
                        "profile": profile,
                        "calls": rows,
                        "pass": profile_pass(profile, rows),
                    }
                )

    selected = next((entry["profile"] for entry in profiles if entry["pass"]), None)
    qualified = (
        selected is not None
        and logical == PROFILE_CALLS
        and budget.blocked_unexpected == 0
        and budget.blocked_budget == 0
        and ledger.attribution_mismatches == 0
        and budget.total_sends <= MAX_SENDS_TOTAL
    )
    return {
        "schema": "d2-stage1-completion-envelope-result-v0.1",
        "issue": ISSUE,
        "engineering_only": True,
        "purpose": "d2_shaped_stage1_completion_envelope_on_repaired_hermes_transport",
        "candidate_sha": auth["candidate_sha"],
        "authorization_basis": (
            "Autonomous Operating Charter Amendment A1 — standing execution authority"
        ),
        "predecessor_apparatus_issue": 223,
        "predecessor_apparatus_result_unchanged": "FAIL",
        "transport_conformance_issue": 229,
        "transport_conformance_result_unchanged": "FAIL",
        "predecessor_stream_rerun_or_replacement_performed": False,
        "guard_repair_pr": 228,
        "guard_repair_merge_sha": GUARD_REPAIR_MERGE_SHA,
        "provider_send_guard_git_blob_sha": git_blob_sha(GUARD_PATH),
        "provider": "Z.AI",
        "subscription_product": "GLM Coding Plan",
        "supported_product_environment": "Hermes Agent Python library",
        "hermes_repository": HERMES_REPOSITORY,
        "hermes_revision": HERMES_REVISION,
        "hermes_package_version": hermes_version,
        "hermes_run_agent_blob_sha": HERMES_RUN_AGENT_BLOB_SHA,
        "openai_sdk_version": OPENAI_VERSION,
        "openai_sdk_default_max_retries": sdk_retries,
        "httpx_version": httpx_version,
        "endpoint_base_url": BASE_URL,
        "provider_id": PROVIDER,
        "api_mode": API_MODE,
        "requested_model": MODEL,
        "effective_model_identity_observed": False,
        "sampling_temperature": TEMPERATURE,
        "thinking": THINKING,
        "profiles": profiles,
        "selected_profile": selected,
        "profile_logical_calls_registered": PROFILE_CALLS,
        "logical_calls_attempted": logical,
        "trajectory_stage_registered": False,
        "trajectory_stage_executed": False,
        "maximum_physical_sends_per_logical_call": MAX_SENDS_PER_LOGICAL,
        "maximum_physical_sends_total": MAX_SENDS_TOTAL,
        "physical_provider_sends_observed_total": budget.total_sends,
        "unexpected_outbound_http_requests_blocked": budget.blocked_unexpected,
        "provider_attempts_blocked_by_cap": budget.blocked_budget,
        "logical_attribution_mismatch_blocks": ledger.attribution_mismatches,
        "logical_context_thread_propagation_used": True,
        "independent_request_origin_header": PROBE_ORIGIN_HEADER,
        "qualification_pass": qualified,
        "d2_scientific_trajectory_executed": False,
        "scientific_hidden_policy_used": False,
        "scientific_scoring_performed": False,
        "source_acquisition_evidence_generated": False,
        "scientific_campaign_executed": False,
        "registry_promotion_authorized": False,
        "acceptance_action_authorized": False,
        "production_historical_substrate_enabled": False,
        "raw_credentials_persisted": False,
        "raw_provider_response_body_persisted": False,
        "raw_provider_error_body_persisted": False,
        "raw_provider_error_message_persisted": False,
        "same_request_stream_rerun_allowed": False,
    }


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
