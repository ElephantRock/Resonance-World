#!/usr/bin/env python3
"""Credential-free preflight and explicitly authorized Hermes/Coding Plan qualification."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import re
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RESEARCH_DIR = ROOT / "research" / "d2_coding_plan_hermes"
PLAN_PATH = RESEARCH_DIR / "CODING_PLAN_HERMES_REQUEST_PLAN.json"
PROMPT_PATH = RESEARCH_DIR / "HERMES_SENTINEL_PROMPT.txt"
MARKER_PATH = RESEARCH_DIR / "RUN_D2_CODING_PLAN_HERMES_QUALIFICATION"

ISSUE = 213
HERMES_REPOSITORY = "hermes-agent-org/hermes"
HERMES_REVISION = "036cbdfa0a3158454a0a2a7a7388cf70353326b4"
HERMES_VERSION = "0.8.0"
HERMES_RUN_AGENT_BLOB_SHA = "4c0d3be4b0c2d364c550fa663d34f6545c9e6d20"
OPENAI_VERSION = "2.21.0"
HTTPX_VERSION = "0.28.1"
OPENAI_DEFAULT_MAX_RETRIES = 2
HERMES_APPLICATION_MAX_ATTEMPTS_PER_RETRY_CYCLE = 3
HERMES_PRIMARY_TRANSPORT_RECOVERY_ADDITIONAL_CYCLES_MAXIMUM = 1
BASE_URL = "https://api.z.ai/api/coding/paas/v4"
PROVIDER = "zai"
API_MODE = "chat_completions"
MODEL = "glm-5.3"
LOGICAL_PROBES = 3
MAX_AGENT_ITERATIONS = 1

# The pinned Hermes loop has three application attempts and, for direct-provider
# transport errors, at most one additional recovery cycle. Each OpenAI SDK call
# may itself make the initial request plus two SDK retries. A process-wide httpx
# guard independently enforces this upper bound before any physical send.
MAX_HTTP_ATTEMPTS_PER_PROBE = (
    HERMES_APPLICATION_MAX_ATTEMPTS_PER_RETRY_CYCLE
    * (1 + HERMES_PRIMARY_TRANSPORT_RECOVERY_ADDITIONAL_CYCLES_MAXIMUM)
    * (1 + OPENAI_DEFAULT_MAX_RETRIES)
)
MAX_PROVIDER_HTTP_ATTEMPTS = LOGICAL_PROBES * MAX_HTTP_ATTEMPTS_PER_PROBE

_ALLOWED_PROVIDER_URL_PREFIX = BASE_URL.rstrip("/") + "/"
_FORBIDDEN_PROVIDER_CREDENTIAL_ENV_VARS = (
    "OPENROUTER_API_KEY",
    "OPENAI_API_KEY",
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


class ProviderAttemptBudgetExceeded(RuntimeError):
    """Raised before a physical provider send would exceed the frozen budget."""


class UnexpectedOutboundRequest(RuntimeError):
    """Raised before an unregistered HTTP request is physically sent."""


class _PhysicalAttemptBudget:
    """Process-wide physical-send guard for the explicitly authorized probe window."""

    def __init__(self, *, probe_count: int, max_per_probe: int, max_total: int) -> None:
        self.probe_count = probe_count
        self.max_per_probe = max_per_probe
        self.max_total = max_total
        self.current_probe: int | None = None
        self.counts = [0 for _ in range(probe_count)]
        self.blocked_budget_counts = [0 for _ in range(probe_count)]
        self.blocked_unexpected_counts = [0 for _ in range(probe_count)]
        self.total = 0

    def begin_probe(self, probe_index: int) -> None:
        if not 0 <= probe_index < self.probe_count:
            raise AssertionError(f"invalid probe index: {probe_index}")
        self.current_probe = probe_index

    def reserve(self, url: str) -> None:
        if self.current_probe is None:
            raise UnexpectedOutboundRequest(
                "outbound HTTP request blocked outside registered probe"
            )
        probe_index = self.current_probe
        if not str(url).startswith(_ALLOWED_PROVIDER_URL_PREFIX):
            self.blocked_unexpected_counts[probe_index] += 1
            raise UnexpectedOutboundRequest("unregistered outbound HTTP request blocked")
        if self.counts[probe_index] >= self.max_per_probe or self.total >= self.max_total:
            self.blocked_budget_counts[probe_index] += 1
            raise ProviderAttemptBudgetExceeded("physical provider-attempt budget exhausted")
        self.counts[probe_index] += 1
        self.total += 1


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def file_sha256(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def load_plan() -> dict[str, Any]:
    return json.loads(PLAN_PATH.read_text())


def validate_plan(plan: dict[str, Any]) -> None:
    expected = {
        "schema": "d2-vnext-hermes-coding-plan-request-plan-v0.2",
        "issue": ISSUE,
        "engineering_only": True,
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
        "hermes_application_max_attempts_per_retry_cycle": (
            HERMES_APPLICATION_MAX_ATTEMPTS_PER_RETRY_CYCLE
        ),
        "hermes_primary_transport_recovery_additional_cycles_maximum": (
            HERMES_PRIMARY_TRANSPORT_RECOVERY_ADDITIONAL_CYCLES_MAXIMUM
        ),
        "endpoint_base_url": BASE_URL,
        "provider_id": PROVIDER,
        "provider_base_url_env_var": "GLM_BASE_URL",
        "credential_env_var": "ZAI_API_KEY",
        "provider_router_required": True,
        "explicit_openai_client_bypass_allowed": False,
        "api_mode": API_MODE,
        "requested_model": MODEL,
        "logical_probe_count": LOGICAL_PROBES,
        "max_provider_http_attempts_per_probe": MAX_HTTP_ATTEMPTS_PER_PROBE,
        "provider_http_attempt_count_maximum": MAX_PROVIDER_HTTP_ATTEMPTS,
        "physical_http_attempt_cap_enforced": True,
        "unregistered_outbound_http_blocked": True,
        "max_agent_iterations_per_probe": MAX_AGENT_ITERATIONS,
        "enabled_toolsets": [],
        "fallback_provider_configured": False,
        "general_api_fallback_allowed": False,
        "replacement_probe_allowed": False,
        "workflow_rerun_allowed": False,
        "deterministic_non_scientific_prompt": True,
        "scientific_field_trajectory_executed": False,
        "scientific_scoring_performed": False,
        "scientific_campaign_authorized": False,
        "provider_execution_authorized": False,
        "registry_promotion_authorized": False,
        "acceptance_action_authorized": False,
        "historical_substrate_enabled": False,
        "raw_credentials_persisted": False,
        "raw_provider_error_body_persisted": False,
        "raw_provider_error_message_persisted": False,
        "same_request_stream_rerun_allowed": False,
        "historical_d2d_s2_replacement": False,
    }
    for key, value in expected.items():
        if plan.get(key) != value:
            raise AssertionError(f"request-plan drift for {key}: {plan.get(key)!r} != {value!r}")
    if MAX_HTTP_ATTEMPTS_PER_PROBE != 18:
        raise AssertionError("per-probe provider-attempt bound drift")
    if LOGICAL_PROBES * MAX_HTTP_ATTEMPTS_PER_PROBE != MAX_PROVIDER_HTTP_ATTEMPTS:
        raise AssertionError("provider-attempt bound arithmetic drift")


def preflight() -> dict[str, Any]:
    plan = load_plan()
    validate_plan(plan)
    prompt = PROMPT_PATH.read_text()
    if "RW_CODING_PLAN_OK" not in prompt:
        raise AssertionError("sentinel prompt drift")
    if MARKER_PATH.exists():
        raise AssertionError("execution marker must be absent from frozen construction candidate")
    return {
        "schema": "d2-vnext-hermes-coding-plan-preflight-v0.2",
        "issue": ISSUE,
        "provider_execution_performed": False,
        "execution_marker_absent": True,
        "request_plan_sha256": file_sha256(PLAN_PATH),
        "prompt_sha256": file_sha256(PROMPT_PATH),
        "requested_model": MODEL,
        "endpoint_base_url": BASE_URL,
        "logical_probe_count": LOGICAL_PROBES,
        "provider_http_attempt_count_maximum": MAX_PROVIDER_HTTP_ATTEMPTS,
        "physical_http_attempt_cap_enforced": True,
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
    status = int(status_match.group(1)) if status_match else None
    provider_code = int(code_match.group(1)) if code_match else None
    return {
        "error_type": type(exc).__name__,
        "http_status": status,
        "provider_code": provider_code,
        "error_text_length": len(text),
        "error_text_sha256": sha256_bytes(text.encode()),
        "terminal_http_429_code_1113": status == 429 and provider_code == 1113,
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


@contextmanager
def _enforce_physical_http_attempt_cap(
    budget: _PhysicalAttemptBudget,
) -> Iterator[None]:
    """Cap every physical httpx send and fail closed on unregistered outbound HTTP."""
    import httpx

    original_sync = httpx.Client._send_single_request
    original_async = httpx.AsyncClient._send_single_request

    def capped_sync(client: Any, request: Any) -> Any:
        budget.reserve(str(request.url))
        return original_sync(client, request)

    async def capped_async(client: Any, request: Any) -> Any:
        budget.reserve(str(request.url))
        return await original_async(client, request)

    httpx.Client._send_single_request = capped_sync
    httpx.AsyncClient._send_single_request = capped_async
    try:
        yield
    finally:
        httpx.Client._send_single_request = original_sync
        httpx.AsyncClient._send_single_request = original_async


def execute() -> dict[str, Any]:
    if os.getenv("D2_CODING_PLAN_HERMES_AUTHORIZED") != "1":
        raise RuntimeError("provider execution is not authorized in this process")
    key = os.getenv("ZAI_API_KEY", "").strip()
    if not key:
        raise RuntimeError("ZAI_API_KEY is empty")
    _assert_execution_environment()

    plan = load_plan()
    validate_plan(plan)
    if not MARKER_PATH.exists():
        raise AssertionError("authorized execution requires marker")

    hermes_version, sdk_retries, httpx_version = _validate_runtime_versions()
    prompt = PROMPT_PATH.read_text().strip()
    rows: list[dict[str, Any]] = []
    budget = _PhysicalAttemptBudget(
        probe_count=LOGICAL_PROBES,
        max_per_probe=MAX_HTTP_ATTEMPTS_PER_PROBE,
        max_total=MAX_PROVIDER_HTTP_ATTEMPTS,
    )

    with _enforce_physical_http_attempt_cap(budget):
        from run_agent import AIAgent

        for probe_index in range(LOGICAL_PROBES):
            budget.begin_probe(probe_index)
            agent = AIAgent(
                provider=PROVIDER,
                api_mode=API_MODE,
                model=MODEL,
                max_iterations=MAX_AGENT_ITERATIONS,
                enabled_toolsets=[],
                quiet_mode=True,
                save_trajectories=False,
                ephemeral_system_prompt=(
                    "You are participating only in a bounded engineering connectivity probe. "
                    "Do not use tools or external actions. "
                    "Return a short plain-text acknowledgement."
                ),
                max_tokens=64,
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

            row: dict[str, Any] = {
                "probe_index": probe_index,
                "requested_model": MODEL,
                "effective_model_identity_observed": False,
                "effective_model": None,
                "tools_exposed": 0,
                "max_agent_iterations": MAX_AGENT_ITERATIONS,
                "openai_sdk_max_retries": client_retries,
                "provider_http_attempts_maximum": MAX_HTTP_ATTEMPTS_PER_PROBE,
            }
            try:
                result = agent.run_conversation(user_message=prompt)
                final_response = str(result.get("final_response") or "")
                terminal_error = str(result.get("error") or "")
                result_failed = result.get("failed") is True or bool(terminal_error)
                if result_failed or not final_response.strip():
                    bounded = _bounded_error(
                        RuntimeError(terminal_error or "Hermes returned non-completed result")
                    )
                    row.update(
                        {
                            "status": "failure",
                            "final_response_nonempty": False,
                            "agent_api_calls_observed": int(
                                getattr(agent, "_api_call_count", 0)
                            ),
                            **bounded,
                        }
                    )
                else:
                    row.update(
                        {
                            "status": "success",
                            "final_response_nonempty": True,
                            "final_response_length": len(final_response),
                            "final_response_sha256": sha256_bytes(final_response.encode()),
                            "agent_api_calls_observed": int(
                                getattr(agent, "_api_call_count", 0)
                            ),
                            "terminal_http_429_code_1113": False,
                        }
                    )
            except Exception as exc:
                row.update(
                    {
                        "status": "failure",
                        "final_response_nonempty": False,
                        "agent_api_calls_observed": int(getattr(agent, "_api_call_count", 0)),
                        **_bounded_error(exc),
                    }
                )
            row.update(
                {
                    "provider_http_attempts_observed": budget.counts[probe_index],
                    "provider_attempts_blocked_by_cap": budget.blocked_budget_counts[probe_index],
                    "unexpected_outbound_http_requests_blocked": (
                        budget.blocked_unexpected_counts[probe_index]
                    ),
                }
            )
            rows.append(row)

    qualified = all(
        row.get("status") == "success"
        and row.get("final_response_nonempty") is True
        and row.get("agent_api_calls_observed") == 1
        and row.get("terminal_http_429_code_1113") is False
        and row.get("provider_attempts_blocked_by_cap") == 0
        and row.get("unexpected_outbound_http_requests_blocked") == 0
        and 1 <= int(row.get("provider_http_attempts_observed", 0))
        <= MAX_HTTP_ATTEMPTS_PER_PROBE
        for row in rows
    )
    return {
        "schema": "d2-vnext-hermes-coding-plan-qualification-result-v0.2",
        "issue": ISSUE,
        "engineering_only": True,
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
        "provider_base_url_env_var": "GLM_BASE_URL",
        "credential_env_var": "ZAI_API_KEY",
        "provider_routed_via_hermes": True,
        "api_mode": API_MODE,
        "requested_model": MODEL,
        "effective_model_identity_observed": False,
        "effective_model_identity_claim": "unobserved_at_supported_product_boundary",
        "logical_probe_count": LOGICAL_PROBES,
        "provider_http_attempt_count_maximum": MAX_PROVIDER_HTTP_ATTEMPTS,
        "provider_http_attempts_observed_total": budget.total,
        "physical_http_attempt_cap_enforced": True,
        "unregistered_outbound_http_blocked": True,
        "probes": rows,
        "qualification_pass": qualified,
        "scientific_field_trajectory_executed": False,
        "scientific_scoring_performed": False,
        "scientific_campaign_authorized": False,
        "registry_promotion_authorized": False,
        "acceptance_action_authorized": False,
        "production_historical_substrate_enabled": False,
        "raw_credentials_persisted": False,
        "raw_provider_error_body_persisted": False,
        "raw_provider_error_message_persisted": False,
        "same_request_stream_rerun_allowed": False,
        "historical_d2d_s2_replacement": False,
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
