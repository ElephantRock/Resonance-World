#!/usr/bin/env python3
"""Qualify future-only terminal-iteration structured completion semantics."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from resonance_world.provider_send_guard import ProviderSendBudget, SendReservation
from resonance_world.structured_completion import evaluate_structured_completion

ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / "research" / "terminal_iteration_completion"
PLAN = DIR / "REQUEST_PLAN.json"
PROBES = DIR / "PROBES.json"
MARKER = DIR / "RUN_TERMINAL_ITERATION_COMPLETION"
GUARD_PATH = ROOT / "src" / "resonance_world" / "provider_send_guard.py"
COMPLETION_PATH = ROOT / "src" / "resonance_world" / "structured_completion.py"
PREDECESSOR_RESULT = ROOT / "research" / "evidence" / "d2_trajectory_completion_envelope" / "RESULT.json"

ISSUE = 237
AUTH_ENV = "TERMINAL_ITERATION_COMPLETION_AUTHORIZED"
AUTH_STRING = "Autonomous_Operating_Charter_Amendment_A1_standing_execution_authority"
BASE_URL = "https://api.z.ai/api/coding/paas/v4"
PROVIDER = "zai"
API_MODE = "chat_completions"
MODEL = "glm-5.3"
HERMES_REVISION = "036cbdfa0a3158454a0a2a7a7388cf70353326b4"
HERMES_VERSION = "0.8.0"
HERMES_RUN_AGENT_BLOB_SHA = "4c0d3be4b0c2d364c550fa663d34f6545c9e6d20"
OPENAI_VERSION = "2.21.0"
HTTPX_VERSION = "0.28.1"
GUARD_BLOB_SHA = "4b8896235d8048523d007400d0acfe85470f628c"
COMPLETION_BLOB_SHA = "c318705e60b907b969d2b3757f688dd7c984de72"
PLAN_SHA256 = "4113c42aa681d81a44b92041e8cbeb23ac4855b300c51f75579f380272ea52c9"
PROBES_SHA256 = "1d2132d3dfca9f703b28eb2290e046b36886bc64b101d0b08659505d2ee1422a"
PREDECESSOR_RESULT_SHA256 = "b0ca9a93cdc2c9568847f94c4524764cfddc66e90c8d02c3ef54889ee2044b9a"
PREDECESSOR_EVIDENCE_MERGE_SHA = "0e9553905abf1077550521d4ff7dc8f35b6076f5"
ORIGIN_HEADER = "X-Resonance-World-Logical-Index"
MAX_LOGICAL = 4
MAX_ITERATIONS = 2
MAX_TOKENS = 64
MAX_CONCURRENCY = 4
MAX_SENDS_PER_LOGICAL = 36
MAX_SENDS_TOTAL = 72
TEMPERATURE = 0.0
THINKING = {"type": "disabled"}
ACTIONS = {"KAPPA", "MICA", "ORBIT", "VELA"}

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
    if payload.get("schema") != "terminal-iteration-structured-completion-probes-v0.1":
        raise AssertionError("probe schema drift")
    if payload.get("issue") != ISSUE:
        raise AssertionError("probe issue drift")
    probes = payload.get("probes")
    if not isinstance(probes, list) or len(probes) != MAX_LOGICAL:
        raise AssertionError("probe count drift")
    expected_ids = [f"terminal_semantics_{index}" for index in range(MAX_LOGICAL)]
    if [probe.get("probe_id") for probe in probes] != expected_ids:
        raise AssertionError("probe identity drift")
    for probe in probes:
        actions = probe.get("actions")
        strategy = probe.get("strategy")
        if (
            not isinstance(actions, list)
            or len(actions) != 8
            or any(action not in ACTIONS for action in actions)
        ):
            raise AssertionError("probe actions drift")
        if not isinstance(strategy, str) or not re.fullmatch(r"[0-9a-f]{128}", strategy):
            raise AssertionError("probe strategy drift")
    return probes


def validate_frozen_files() -> dict[str, Any]:
    if file_sha(PLAN) != PLAN_SHA256:
        raise AssertionError("request plan SHA drift")
    if file_sha(PROBES) != PROBES_SHA256:
        raise AssertionError("probe file SHA drift")
    if git_blob_sha(GUARD_PATH) != GUARD_BLOB_SHA:
        raise AssertionError("provider-send guard blob drift")
    if git_blob_sha(COMPLETION_PATH) != COMPLETION_BLOB_SHA:
        raise AssertionError("structured-completion blob drift")
    if file_sha(PREDECESSOR_RESULT) != PREDECESSOR_RESULT_SHA256:
        raise AssertionError("preserved predecessor result drift")

    plan = load_plan()
    expected = {
        "schema": "terminal-iteration-structured-completion-request-plan-v0.1",
        "issue": ISSUE,
        "engineering_only": True,
        "purpose": "future_only_terminal_iteration_structured_completion_semantics",
        "predecessor_trajectory_issue": 234,
        "predecessor_trajectory_result": "FAIL",
        "predecessor_evidence_merge_sha": PREDECESSOR_EVIDENCE_MERGE_SHA,
        "predecessor_result_sha256": PREDECESSOR_RESULT_SHA256,
        "guard_repair_pr": 228,
        "guard_repair_merge_sha": "47383f2b18c993965c89350609a4c9691897bdde",
        "provider_send_guard_git_blob_sha": GUARD_BLOB_SHA,
        "structured_completion_git_blob_sha": COMPLETION_BLOB_SHA,
        "probes_sha256": PROBES_SHA256,
        "provider": "Z.AI",
        "subscription_product": "GLM Coding Plan",
        "supported_product_environment": "Hermes Agent Python library",
        "endpoint_base_url": BASE_URL,
        "provider_id": PROVIDER,
        "provider_base_url_env_var": "GLM_BASE_URL",
        "credential_env_var": "ZAI_API_KEY",
        "api_mode": API_MODE,
        "requested_model": MODEL,
        "hermes_repository": "hermes-agent-org/hermes",
        "hermes_revision": HERMES_REVISION,
        "hermes_package_version": HERMES_VERSION,
        "hermes_run_agent_blob_sha": HERMES_RUN_AGENT_BLOB_SHA,
        "openai_sdk_version": OPENAI_VERSION,
        "httpx_version": HTTPX_VERSION,
        "maximum_logical_calls": MAX_LOGICAL,
        "max_iterations": MAX_ITERATIONS,
        "max_tokens": MAX_TOKENS,
        "sampling_temperature": TEMPERATURE,
        "thinking": THINKING,
        "maximum_concurrency": MAX_CONCURRENCY,
        "maximum_physical_sends_per_logical_call": MAX_SENDS_PER_LOGICAL,
        "maximum_physical_sends_total": MAX_SENDS_TOTAL,
        "independent_request_origin_header": ORIGIN_HEADER,
        "probe_ids": [f"terminal_semantics_{index}" for index in range(MAX_LOGICAL)],
        "fresh_probe_contract": "exact_actions_and_exact_128_hex_strategy",
        "terminal_iteration_override_required_for_pass": True,
        "at_least_one_two_call_probe_required_for_pass": True,
        "all_four_probes_required_for_pass": True,
        "enabled_toolsets": [],
        "memory_context_files_enabled": False,
        "persistent_session_enabled": False,
        "fallback_provider_configured": False,
        "general_api_fallback_allowed": False,
        "provider_execution_authorized": False,
        "workflow_rerun_allowed": False,
        "same_request_stream_rerun_allowed": False,
        "predecessor_stream_rerun_or_replacement_allowed": False,
        "scientific_scoring_performed": False,
        "source_acquisition_evidence_generated": False,
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
    probes = load_probes()
    return {"plan": plan, "probes": probes}


def preflight() -> dict[str, Any]:
    frozen = validate_frozen_files()
    if MARKER.exists():
        raise AssertionError("execution marker must be absent from frozen candidate")
    return {
        "schema": "terminal-iteration-structured-completion-preflight-v0.1",
        "issue": ISSUE,
        "engineering_only": True,
        "provider_execution_performed": False,
        "execution_marker_absent": True,
        "request_plan_sha256": file_sha(PLAN),
        "probes_sha256": file_sha(PROBES),
        "provider_send_guard_git_blob_sha": git_blob_sha(GUARD_PATH),
        "structured_completion_git_blob_sha": git_blob_sha(COMPLETION_PATH),
        "predecessor_result_sha256": file_sha(PREDECESSOR_RESULT),
        "probe_ids": [probe["probe_id"] for probe in frozen["probes"]],
        "scientific_scoring_performed": False,
        "historical_substrate_enabled": False,
    }


def parse_marker() -> dict[str, str]:
    if not MARKER.exists():
        raise RuntimeError("authorization marker absent")
    fields = dict(
        line.split("=", 1) for line in MARKER.read_text().splitlines() if line.strip()
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


def assert_execution_environment() -> None:
    if os.getenv(AUTH_ENV) != "1":
        raise RuntimeError("provider execution not authorized")
    if not os.getenv("ZAI_API_KEY", "").strip():
        raise RuntimeError("ZAI_API_KEY is required")
    if os.getenv("GLM_BASE_URL", "").strip().rstrip("/") != BASE_URL:
        raise RuntimeError("GLM_BASE_URL must equal the frozen Coding Plan base URL")
    for name in _FORBIDDEN_PROVIDER_CREDENTIAL_ENV_VARS:
        if os.getenv(name):
            raise RuntimeError(f"unexpected provider credential exposed: {name}")


def validate_runtime_versions() -> None:
    import httpx
    import openai
    from openai._constants import DEFAULT_MAX_RETRIES

    if importlib.metadata.version("hermes-agent") != HERMES_VERSION:
        raise AssertionError("Hermes version drift")
    if importlib.metadata.version("openai") != OPENAI_VERSION:
        raise AssertionError("OpenAI SDK version drift")
    if openai.__version__ != OPENAI_VERSION:
        raise AssertionError("OpenAI SDK runtime version drift")
    if importlib.metadata.version("httpx") != HTTPX_VERSION or httpx.__version__ != HTTPX_VERSION:
        raise AssertionError("httpx version drift")
    if int(DEFAULT_MAX_RETRIES) != 2:
        raise AssertionError("OpenAI retry default drift")
    if not hasattr(httpx.Client, "_send_single_request"):
        raise AssertionError("httpx physical-send hook unavailable")
    if not hasattr(httpx.AsyncClient, "_send_single_request"):
        raise AssertionError("httpx async physical-send hook unavailable")


class TransportLedger:
    """Thread-safe bounded physical-send metadata keyed by logical probe."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._rows: dict[int, list[dict[str, Any]]] = {
            index: [] for index in range(MAX_LOGICAL)
        }
        self._mismatches = 0

    @property
    def mismatches(self) -> int:
        with self._lock:
            return self._mismatches

    def mismatch(self) -> None:
        with self._lock:
            self._mismatches += 1

    def begin(self, reservation: SendReservation, origin: int) -> int:
        if reservation.logical_index != origin:
            self.mismatch()
            raise LogicalAttributionMismatch("reservation disagrees with request origin")
        row = {
            "origin_logical_index": origin,
            "logical_index": reservation.logical_index,
            "logical_send_index": reservation.logical_send_index,
            "total_send_index": reservation.total_send_index,
            "http_status": None,
            "transport_error_type": None,
        }
        with self._lock:
            rows = self._rows[origin]
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


def verified_origin(request: Any, budget: ProviderSendBudget, ledger: TransportLedger) -> int:
    raw = request.headers.get(ORIGIN_HEADER)
    try:
        origin = int(raw) if raw is not None else -1
    except (TypeError, ValueError):
        origin = -1
    registered = budget.current_logical_index()
    if not 0 <= origin < MAX_LOGICAL or registered is None or origin != registered:
        ledger.mismatch()
        raise LogicalAttributionMismatch(
            "independent request origin does not match registered logical context"
        )
    return origin


@contextmanager
def transport_guard(budget: ProviderSendBudget, ledger: TransportLedger):
    import httpx

    original_sync = httpx.Client._send_single_request
    original_async = httpx.AsyncClient._send_single_request

    def capped_sync(client: Any, request: Any) -> Any:
        origin = verified_origin(request, budget, ledger)
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
        origin = verified_origin(request, budget, ledger)
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


def system_prompt(probe: dict[str, Any]) -> str:
    exact = json.dumps(
        {"actions": probe["actions"], "strategy": probe["strategy"]},
        separators=(",", ":"),
    )
    return (
        "Engineering transport diagnostic only. Return exactly the JSON object below "
        "and nothing else. Do not use markdown, tools, browsing, or external information. "
        "Copy every character of the actions and strategy fields exactly. "
        f"Required object: {exact}"
    )


def user_prompt(probe: dict[str, Any]) -> str:
    return (
        f"Probe {probe['probe_id']}. Emit the exact registered JSON object from the "
        "system instruction. This is a non-scientific structured-completion sentinel."
    )


def parse_probe_response(text: str, probe: dict[str, Any]) -> bool:
    try:
        payload = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return False
    return payload == {"actions": probe["actions"], "strategy": probe["strategy"]}


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


def new_agent(logical_index: int, probe: dict[str, Any]) -> Any:
    from run_agent import AIAgent

    agent = AIAgent(
        provider=PROVIDER,
        api_mode=API_MODE,
        model=MODEL,
        max_iterations=MAX_ITERATIONS,
        enabled_toolsets=[],
        quiet_mode=True,
        save_trajectories=False,
        ephemeral_system_prompt=system_prompt(probe),
        max_tokens=MAX_TOKENS,
        request_overrides={
            "temperature": TEMPERATURE,
            "extra_body": {"thinking": THINKING},
            "extra_headers": {ORIGIN_HEADER: str(logical_index)},
        },
        skip_context_files=True,
        skip_memory=True,
        persist_session=False,
        fallback_model=None,
    )
    if agent.tools != [] or agent.valid_tool_names or agent._fallback_chain:
        raise AssertionError("Hermes tool/fallback drift")
    if (
        agent.model != MODEL
        or agent.provider != PROVIDER
        or agent.api_mode != API_MODE
        or int(agent.max_iterations) != MAX_ITERATIONS
        or int(agent.max_tokens) != MAX_TOKENS
    ):
        raise AssertionError("Hermes route/profile drift")
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
    if str(headers.get(ORIGIN_HEADER, "")) != str(logical_index):
        raise AssertionError("request-origin header drift")
    return agent


def run_probe(
    budget: ProviderSendBudget,
    ledger: TransportLedger,
    logical_index: int,
    probe: dict[str, Any],
) -> dict[str, Any]:
    prompt = user_prompt(probe)
    row: dict[str, Any] = {
        "logical_index": logical_index,
        "probe_id": probe["probe_id"],
        "prompt_bytes": len(prompt.encode()),
        "prompt_sha256": sha(prompt),
    }
    agent: Any | None = None
    try:
        with budget.logical_call(logical_index):
            agent = new_agent(logical_index, probe)
            result = agent.run_conversation(user_message=prompt)
        final = result.get("final_response")
        final_text = final if isinstance(final, str) else ""
        row.update(
            {
                "hermes_completed": result.get("completed"),
                "hermes_failed": result.get("failed") is True,
                "hermes_partial": result.get("partial") is True,
                "hermes_interrupted": result.get("interrupted") is True,
                "hermes_error_present": bool(result.get("error")),
                "api_calls": result.get("api_calls"),
                "final_response_length": len(final_text),
                "final_response_sha256": sha(final_text) if final_text else None,
                "structured_parse_valid": parse_probe_response(final_text, probe),
                "_hermes_result": {
                    "final_response": final_text,
                    "completed": result.get("completed"),
                    "failed": result.get("failed"),
                    "partial": result.get("partial"),
                    "interrupted": result.get("interrupted"),
                    "error": result.get("error"),
                    "api_calls": result.get("api_calls"),
                },
            }
        )
    except Exception as exc:
        row.update(
            {
                "hermes_completed": False,
                "hermes_failed": True,
                "hermes_partial": False,
                "hermes_interrupted": False,
                "hermes_error_present": True,
                "api_calls": int(
                    getattr(agent, "_api_call_count", 0) if agent is not None else 0
                ),
                "final_response_length": 0,
                "final_response_sha256": None,
                "structured_parse_valid": False,
                "_hermes_result": {
                    "final_response": "",
                    "completed": False,
                    "failed": True,
                    "partial": False,
                    "interrupted": False,
                    "error": type(exc).__name__,
                    "api_calls": int(
                        getattr(agent, "_api_call_count", 0) if agent is not None else 0
                    ),
                },
                **bounded_error(exc),
            }
        )
    return row


def execute() -> dict[str, Any]:
    assert_execution_environment()
    frozen = validate_frozen_files()
    auth = parse_marker()
    validate_runtime_versions()

    budget = ProviderSendBudget(
        allowed_url_prefix=BASE_URL,
        maximum_logical_calls=MAX_LOGICAL,
        maximum_sends_per_logical_call=MAX_SENDS_PER_LOGICAL,
        maximum_sends_total=MAX_SENDS_TOTAL,
    )
    ledger = TransportLedger()

    with budget.propagate_to_child_threads():
        with transport_guard(budget, ledger):
            with ThreadPoolExecutor(max_workers=MAX_CONCURRENCY) as pool:
                rows = list(
                    pool.map(
                        lambda item: run_probe(budget, ledger, item[0], item[1]),
                        enumerate(frozen["probes"]),
                    )
                )

    for row in rows:
        logical = int(row["logical_index"])
        attempts = ledger.rows(logical)
        sends = budget.sends_for_logical_call(logical)
        attribution_ok = (
            len(attempts) == sends
            and all(
                attempt["origin_logical_index"] == logical
                and attempt["logical_index"] == logical
                for attempt in attempts
            )
        )
        decision = evaluate_structured_completion(
            row.pop("_hermes_result"),
            max_iterations=MAX_ITERATIONS,
            parse_valid=bool(row["structured_parse_valid"]),
            logical_attribution_integrity=attribution_ok,
            unexpected_outbound_blocks=budget.blocked_unexpected,
            provider_budget_blocks=budget.blocked_budget,
            attribution_mismatch_blocks=ledger.mismatches,
            physical_sends=sends,
            maximum_physical_sends=MAX_SENDS_PER_LOGICAL,
        )
        row.update(
            {
                "physical_provider_sends_observed": sends,
                "attempts": attempts,
                "logical_attribution_integrity": attribution_ok,
                "adapter_accepted": decision.accepted,
                "terminal_iteration_override_used": decision.terminal_iteration_override_used,
                "adapter_reason": decision.reason,
            }
        )

    all_four = len(rows) == MAX_LOGICAL and all(row["adapter_accepted"] for row in rows)
    two_call = any(row.get("api_calls") == MAX_ITERATIONS for row in rows)
    override = any(
        row["adapter_accepted"] and row["terminal_iteration_override_used"] for row in rows
    )
    qualified = (
        all_four
        and two_call
        and override
        and budget.blocked_unexpected == 0
        and budget.blocked_budget == 0
        and ledger.mismatches == 0
        and 1 <= budget.total_sends <= MAX_SENDS_TOTAL
    )

    return {
        "schema": "terminal-iteration-structured-completion-result-v0.1",
        "issue": ISSUE,
        "engineering_only": True,
        "purpose": "future_only_terminal_iteration_structured_completion_semantics",
        "candidate_sha": auth["candidate_sha"],
        "authorization_basis": (
            "Autonomous Operating Charter Amendment A1 — standing execution authority"
        ),
        "predecessor_trajectory_issue": 234,
        "predecessor_trajectory_result_unchanged": "FAIL",
        "predecessor_result_sha256": PREDECESSOR_RESULT_SHA256,
        "predecessor_evidence_merge_sha": PREDECESSOR_EVIDENCE_MERGE_SHA,
        "predecessor_stream_rerun_or_replacement_performed": False,
        "provider": "Z.AI",
        "subscription_product": "GLM Coding Plan",
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
        "maximum_logical_calls": MAX_LOGICAL,
        "maximum_concurrency": MAX_CONCURRENCY,
        "maximum_physical_sends_per_logical_call": MAX_SENDS_PER_LOGICAL,
        "maximum_physical_sends_total": MAX_SENDS_TOTAL,
        "physical_provider_sends_observed_total": budget.total_sends,
        "unexpected_outbound_http_requests_blocked": budget.blocked_unexpected,
        "provider_attempts_blocked_by_cap": budget.blocked_budget,
        "logical_attribution_mismatch_blocks": ledger.mismatches,
        "probes": rows,
        "all_four_probes_adapter_accepted": all_four,
        "at_least_one_two_call_probe_observed": two_call,
        "at_least_one_terminal_iteration_override_observed": override,
        "qualification_pass": qualified,
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
