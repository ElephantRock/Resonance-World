#!/usr/bin/env python3
"""Bounded live conformance for provider-send attribution across Hermes worker threads."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import re
import threading
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from resonance_world.provider_send_guard import ProviderSendBudget, SendReservation

ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / "research" / "provider_guard_hermes_live"
PLAN = DIR / "REQUEST_PLAN.json"
PROMPT = DIR / "PROMPT.txt"
MARKER = DIR / "RUN_PROVIDER_GUARD_HERMES_LIVE_CONFORMANCE"
GUARD_PATH = ROOT / "src" / "resonance_world" / "provider_send_guard.py"

ISSUE = 229
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
TEMPERATURE = 0.0
THINKING = {"type": "disabled"}
LOGICAL_PROBES = 4
MAX_CONCURRENCY = 4
MAX_AGENT_ITERATIONS = 1
MAX_TOKENS = 64
MAX_SENDS_PER_LOGICAL = 18
MAX_SENDS_TOTAL = 72
PROBE_ORIGIN_HEADER = "X-Resonance-World-Probe-Index"
GUARD_REPAIR_MERGE_SHA = "47383f2b18c993965c89350609a4c9691897bdde"
GUARD_GIT_BLOB_SHA = "4b8896235d8048523d007400d0acfe85470f628c"
AUTH_ENV = "PROVIDER_GUARD_HERMES_LIVE_AUTHORIZED"

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
    """Raised before transmission when independent probe origin disagrees with context."""


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def file_sha256(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def git_blob_sha(path: Path) -> str:
    data = path.read_bytes()
    header = f"blob {len(data)}\0".encode()
    return hashlib.sha1(header + data).hexdigest()


def load_plan() -> dict[str, Any]:
    return json.loads(PLAN.read_text())


def validate_plan(plan: dict[str, Any]) -> None:
    expected = {
        "schema": "provider-guard-hermes-live-conformance-request-plan-v0.1",
        "issue": ISSUE,
        "engineering_only": True,
        "purpose": "live_transport_conformance_of_thread_propagating_provider_send_guard",
        "predecessor_apparatus_issue": 223,
        "predecessor_apparatus_pr": 224,
        "predecessor_apparatus_result": "FAIL",
        "guard_repair_issue": 227,
        "guard_repair_pr": 228,
        "guard_repair_merge_sha": GUARD_REPAIR_MERGE_SHA,
        "provider_send_guard_path": "src/resonance_world/provider_send_guard.py",
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
        "logical_probe_count": LOGICAL_PROBES,
        "logical_probe_max_concurrency": MAX_CONCURRENCY,
        "max_agent_iterations_per_probe": MAX_AGENT_ITERATIONS,
        "max_tokens_per_probe": MAX_TOKENS,
        "maximum_physical_sends_per_logical_probe": MAX_SENDS_PER_LOGICAL,
        "maximum_physical_sends_total": MAX_SENDS_TOTAL,
        "physical_send_guard_fail_closed": True,
        "logical_context_thread_propagation_required": True,
        "independent_probe_origin_header": PROBE_ORIGIN_HEADER,
        "origin_reservation_match_required": True,
        "attribution_mismatch_fail_closed": True,
        "unregistered_outbound_http_blocked": True,
        "enabled_toolsets": [],
        "memory_context_files_enabled": False,
        "persistent_session_enabled": False,
        "fallback_provider_configured": False,
        "general_api_fallback_allowed": False,
        "deterministic_non_scientific_prompt": True,
        "d2_scientific_call_shapes_executed": False,
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


def preflight() -> dict[str, Any]:
    validate_plan(load_plan())
    if MARKER.exists():
        raise AssertionError("execution marker must be absent from frozen candidate")
    prompt = PROMPT.read_text()
    if "RW_PROVIDER_GUARD_OK" not in prompt:
        raise AssertionError("sentinel prompt drift")
    if git_blob_sha(GUARD_PATH) != GUARD_GIT_BLOB_SHA:
        raise AssertionError("provider-send guard blob drift")
    return {
        "schema": "provider-guard-hermes-live-conformance-preflight-v0.1",
        "issue": ISSUE,
        "engineering_only": True,
        "provider_execution_performed": False,
        "execution_marker_absent": True,
        "request_plan_sha256": file_sha256(PLAN),
        "prompt_sha256": file_sha256(PROMPT),
        "provider_send_guard_git_blob_sha": git_blob_sha(GUARD_PATH),
        "logical_probe_count": LOGICAL_PROBES,
        "logical_probe_max_concurrency": MAX_CONCURRENCY,
        "independent_probe_origin_header": PROBE_ORIGIN_HEADER,
        "maximum_physical_sends_total": MAX_SENDS_TOTAL,
        "scientific_scoring_performed": False,
        "historical_substrate_enabled": False,
    }


def _bounded_error(exc: BaseException) -> dict[str, Any]:
    text = str(exc)
    status_match = re.search(r"(?:status(?:_code)?[=: ]+|HTTP\s+)(\d{3})", text, re.I)
    if status_match is None:
        status_match = re.search(r"\b(4\d\d|5\d\d)\b", text)
    code_match = re.search(r"""["']code["']\s*:\s*["']?(\d{3,6})""", text, re.I)
    if code_match is None:
        code_match = re.search(r"provider(?:_code)?[=: ]+(\d{3,6})", text, re.I)
    return {
        "error_type": type(exc).__name__,
        "http_status": int(status_match.group(1)) if status_match else None,
        "provider_code": int(code_match.group(1)) if code_match else None,
        "error_text_length": len(text),
        "error_text_sha256": sha256_bytes(text.encode()),
    }


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
    """Bounded transport metadata keyed by registered logical-call identity."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._rows = {index: [] for index in range(LOGICAL_PROBES)}
        self._attribution_mismatches = 0

    def record_attribution_mismatch(self) -> None:
        with self._lock:
            self._attribution_mismatches += 1

    @property
    def attribution_mismatches(self) -> int:
        with self._lock:
            return self._attribution_mismatches

    def begin(self, reservation: SendReservation, origin_probe_index: int) -> int:
        if origin_probe_index != reservation.logical_index:
            self.record_attribution_mismatch()
            raise LogicalAttributionMismatch("probe origin disagrees with send reservation")
        row = {
            "origin_probe_index": origin_probe_index,
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


def _verified_origin_probe_index(
    request: Any,
    budget: ProviderSendBudget,
    ledger: TransportLedger,
) -> int:
    raw = request.headers.get(PROBE_ORIGIN_HEADER)
    try:
        origin_probe_index = int(raw) if raw is not None else -1
    except (TypeError, ValueError):
        origin_probe_index = -1
    logical_index = budget.current_logical_index()
    if (
        not 0 <= origin_probe_index < LOGICAL_PROBES
        or logical_index is None
        or origin_probe_index != logical_index
    ):
        ledger.record_attribution_mismatch()
        raise LogicalAttributionMismatch(
            "independent probe origin does not match registered logical context"
        )
    return origin_probe_index


@contextmanager
def _enforce_physical_http_attempt_cap(
    budget: ProviderSendBudget,
    ledger: TransportLedger,
) -> Iterator[None]:
    import httpx

    original_sync = httpx.Client._send_single_request
    original_async = httpx.AsyncClient._send_single_request

    def capped_sync(client: Any, request: Any) -> Any:
        origin_probe_index = _verified_origin_probe_index(request, budget, ledger)
        reservation = budget.reserve(str(request.url))
        row_index = ledger.begin(reservation, origin_probe_index)
        try:
            response = original_sync(client, request)
        except Exception as exc:
            ledger.error(reservation, row_index, exc)
            raise
        ledger.response(reservation, row_index, response.status_code)
        return response

    async def capped_async(client: Any, request: Any) -> Any:
        origin_probe_index = _verified_origin_probe_index(request, budget, ledger)
        reservation = budget.reserve(str(request.url))
        row_index = ledger.begin(reservation, origin_probe_index)
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


def _new_agent(probe_index: int) -> Any:
    from run_agent import AIAgent

    agent = AIAgent(
        provider=PROVIDER,
        api_mode=API_MODE,
        model=MODEL,
        max_iterations=MAX_AGENT_ITERATIONS,
        enabled_toolsets=[],
        quiet_mode=True,
        save_trajectories=False,
        ephemeral_system_prompt=(
            "You are participating only in a bounded engineering transport probe. "
            "Do not use tools or external actions. Return a short acknowledgement."
        ),
        max_tokens=MAX_TOKENS,
        request_overrides={
            "temperature": TEMPERATURE,
            "extra_body": {"thinking": THINKING},
            "extra_headers": {PROBE_ORIGIN_HEADER: str(probe_index)},
        },
        skip_context_files=True,
        skip_memory=True,
        persist_session=False,
        fallback_model=None,
    )
    client_retries = int(getattr(agent.client, "max_retries", -1))
    if client_retries != OPENAI_DEFAULT_MAX_RETRIES:
        raise AssertionError(f"runtime client retry drift: {client_retries}")
    if agent.tools != [] or agent.valid_tool_names:
        raise AssertionError("Hermes tool-disable contract drift")
    if agent._fallback_chain:
        raise AssertionError("provider fallback unexpectedly configured")
    if agent.model != MODEL or agent.provider != PROVIDER or agent.api_mode != API_MODE:
        raise AssertionError("Hermes provider/model/api-mode drift")
    if str(agent.client.base_url).rstrip("/") != BASE_URL:
        raise AssertionError(f"Hermes base-url drift: {agent.client.base_url}")
    if str(agent.base_url).rstrip("/") != BASE_URL:
        raise AssertionError(f"Hermes routed base-url drift: {agent.base_url}")
    return agent


def execute() -> dict[str, Any]:
    if os.getenv(AUTH_ENV) != "1":
        raise RuntimeError("provider execution is not authorized in this process")
    if not os.getenv("ZAI_API_KEY", "").strip():
        raise RuntimeError("ZAI_API_KEY is empty")
    _assert_execution_environment()
    validate_plan(load_plan())
    if not MARKER.exists():
        raise AssertionError("authorized execution requires marker")
    if git_blob_sha(GUARD_PATH) != GUARD_GIT_BLOB_SHA:
        raise AssertionError("provider-send guard blob drift")

    hermes_version, sdk_retries, httpx_version = _validate_runtime_versions()
    prompt = PROMPT.read_text().strip()
    budget = ProviderSendBudget(
        allowed_url_prefix=BASE_URL,
        maximum_logical_calls=LOGICAL_PROBES,
        maximum_sends_per_logical_call=MAX_SENDS_PER_LOGICAL,
        maximum_sends_total=MAX_SENDS_TOTAL,
    )
    ledger = TransportLedger()

    def run_probe(probe_index: int) -> dict[str, Any]:
        row: dict[str, Any] = {
            "probe_index": probe_index,
            "requested_model": MODEL,
            "max_agent_iterations": MAX_AGENT_ITERATIONS,
            "max_tokens": MAX_TOKENS,
            "provider_http_attempts_maximum": MAX_SENDS_PER_LOGICAL,
        }
        agent: Any | None = None
        try:
            with budget.logical_call(probe_index):
                agent = _new_agent(probe_index)
                result = agent.run_conversation(user_message=prompt)
            final_response = str(result.get("final_response") or "")
            terminal_error = str(result.get("error") or "")
            failed = result.get("failed") is True or bool(terminal_error)
            api_calls = int(getattr(agent, "_api_call_count", 0))
            if failed or not final_response.strip():
                row.update(
                    {
                        "status": "failure",
                        "final_response_nonempty": False,
                        "agent_api_calls_observed": api_calls,
                        **_bounded_error(
                            RuntimeError(terminal_error or "Hermes returned non-completed result")
                        ),
                    }
                )
            else:
                row.update(
                    {
                        "status": "success",
                        "final_response_nonempty": True,
                        "final_response_length": len(final_response),
                        "final_response_sha256": sha256_bytes(final_response.encode()),
                        "sentinel_token_observed": "RW_PROVIDER_GUARD_OK" in final_response,
                        "agent_api_calls_observed": api_calls,
                    }
                )
        except Exception as exc:
            row.update(
                {
                    "status": "failure",
                    "final_response_nonempty": False,
                    "agent_api_calls_observed": int(
                        getattr(agent, "_api_call_count", 0) if agent is not None else 0
                    ),
                    **_bounded_error(exc),
                }
            )
        attempts = ledger.rows(probe_index)
        row.update(
            {
                "provider_http_attempts_observed": budget.sends_for_logical_call(probe_index),
                "transport_attempts": attempts,
                "logical_attribution_integrity": all(
                    attempt["origin_probe_index"] == probe_index
                    and attempt["logical_index"] == probe_index
                    for attempt in attempts
                ),
            }
        )
        return row

    with budget.propagate_to_child_threads():
        with _enforce_physical_http_attempt_cap(budget, ledger):
            with ThreadPoolExecutor(max_workers=MAX_CONCURRENCY) as pool:
                rows = list(pool.map(run_probe, range(LOGICAL_PROBES)))

    qualified = (
        budget.blocked_unexpected == 0
        and budget.blocked_budget == 0
        and ledger.attribution_mismatches == 0
        and budget.total_sends <= MAX_SENDS_TOTAL
        and all(
            row.get("status") == "success"
            and row.get("final_response_nonempty") is True
            and row.get("agent_api_calls_observed") == 1
            and row.get("logical_attribution_integrity") is True
            and 1 <= int(row.get("provider_http_attempts_observed", 0)) <= MAX_SENDS_PER_LOGICAL
            for row in rows
        )
    )

    return {
        "schema": "provider-guard-hermes-live-conformance-result-v0.1",
        "issue": ISSUE,
        "engineering_only": True,
        "purpose": "live_transport_conformance_of_thread_propagating_provider_send_guard",
        "predecessor_apparatus_issue": 223,
        "predecessor_apparatus_result_unchanged": "FAIL",
        "predecessor_stream_rerun_or_replacement_performed": False,
        "guard_repair_issue": 227,
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
        "logical_probe_count": LOGICAL_PROBES,
        "logical_probe_max_concurrency": MAX_CONCURRENCY,
        "independent_probe_origin_header": PROBE_ORIGIN_HEADER,
        "maximum_physical_sends_per_logical_probe": MAX_SENDS_PER_LOGICAL,
        "maximum_physical_sends_total": MAX_SENDS_TOTAL,
        "physical_provider_sends_observed_total": budget.total_sends,
        "unexpected_outbound_http_requests_blocked": budget.blocked_unexpected,
        "provider_attempts_blocked_by_cap": budget.blocked_budget,
        "logical_attribution_mismatch_blocks": ledger.attribution_mismatches,
        "logical_context_thread_propagation_used": True,
        "probes": rows,
        "qualification_pass": qualified,
        "d2_scientific_call_shapes_executed": False,
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
