#!/usr/bin/env python3
"""Bounded Hermes/Coding Plan completion-envelope qualification."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

# Direct-script execution requires the sibling predecessor module on sys.path.
import qualify_d2_coding_plan_hermes as base  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RESEARCH_DIR = ROOT / "research" / "d2_coding_plan_hermes_completion"
PLAN_PATH = RESEARCH_DIR / "CODING_PLAN_HERMES_COMPLETION_REQUEST_PLAN.json"
PROMPT_PATH = RESEARCH_DIR / "HERMES_COMPLETION_SENTINEL_PROMPT.txt"
MARKER_PATH = RESEARCH_DIR / "RUN_D2_CODING_PLAN_HERMES_COMPLETION_QUALIFICATION"

ISSUE = 219
PREDECESSOR_ISSUE = 213
PREDECESSOR_PR = 218
PREDECESSOR_MERGE_SHA = "105b5386e5f1027a18e2f68361a186bd8c93de9b"

HERMES_REPOSITORY = base.HERMES_REPOSITORY
HERMES_REVISION = base.HERMES_REVISION
HERMES_VERSION = base.HERMES_VERSION
HERMES_RUN_AGENT_BLOB_SHA = base.HERMES_RUN_AGENT_BLOB_SHA
OPENAI_VERSION = base.OPENAI_VERSION
HTTPX_VERSION = base.HTTPX_VERSION
OPENAI_DEFAULT_MAX_RETRIES = base.OPENAI_DEFAULT_MAX_RETRIES
HERMES_APPLICATION_MAX_ATTEMPTS_PER_RETRY_CYCLE = (
    base.HERMES_APPLICATION_MAX_ATTEMPTS_PER_RETRY_CYCLE
)
HERMES_PRIMARY_TRANSPORT_RECOVERY_ADDITIONAL_CYCLES_MAXIMUM = (
    base.HERMES_PRIMARY_TRANSPORT_RECOVERY_ADDITIONAL_CYCLES_MAXIMUM
)
BASE_URL = base.BASE_URL
PROVIDER = base.PROVIDER
API_MODE = base.API_MODE
MODEL = base.MODEL

LOGICAL_PROBES = 3
MAX_AGENT_ITERATIONS = 2
MAX_TOKENS = 512
MAX_MODEL_CALLS_PER_PROBE = 2
MAX_HTTP_ATTEMPTS_PER_MODEL_CALL = base.MAX_HTTP_ATTEMPTS_PER_PROBE
MAX_HTTP_ATTEMPTS_PER_PROBE = (
    MAX_MODEL_CALLS_PER_PROBE * MAX_HTTP_ATTEMPTS_PER_MODEL_CALL
)
MAX_PROVIDER_HTTP_ATTEMPTS = LOGICAL_PROBES * MAX_HTTP_ATTEMPTS_PER_PROBE

ProviderAttemptBudgetExceeded = base.ProviderAttemptBudgetExceeded
UnexpectedOutboundRequest = base.UnexpectedOutboundRequest
_PhysicalAttemptBudget = base._PhysicalAttemptBudget
_enforce_physical_http_attempt_cap = base._enforce_physical_http_attempt_cap
_bounded_error = base._bounded_error
sha256_bytes = base.sha256_bytes
file_sha256 = base.file_sha256


def load_plan() -> dict[str, Any]:
    return json.loads(PLAN_PATH.read_text())


def validate_plan(plan: dict[str, Any]) -> None:
    expected = {
        "schema": "d2-vnext-hermes-coding-plan-completion-request-plan-v0.1",
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
        "max_agent_iterations_per_probe": MAX_AGENT_ITERATIONS,
        "max_tokens_per_model_call": MAX_TOKENS,
        "max_model_calls_per_probe": MAX_MODEL_CALLS_PER_PROBE,
        "max_provider_http_attempts_per_model_call": MAX_HTTP_ATTEMPTS_PER_MODEL_CALL,
        "max_provider_http_attempts_per_probe": MAX_HTTP_ATTEMPTS_PER_PROBE,
        "provider_http_attempt_count_maximum": MAX_PROVIDER_HTTP_ATTEMPTS,
        "physical_http_attempt_cap_enforced": True,
        "unregistered_outbound_http_blocked": True,
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
        "qualification_requires_all_logical_probes_successful": True,
        "qualification_requires_completed_result": True,
        "qualification_requires_nonempty_final_response": True,
        "qualification_allows_agent_api_calls_minimum": 1,
        "qualification_allows_agent_api_calls_maximum": 2,
        "qualification_requires_no_terminal_http_429_code_1113": True,
        "same_request_stream_rerun_allowed": False,
        "predecessor_issue": PREDECESSOR_ISSUE,
        "predecessor_pr": PREDECESSOR_PR,
        "predecessor_merge_sha": PREDECESSOR_MERGE_SHA,
        "historical_d2d_s2_replacement": False,
    }
    for key, value in expected.items():
        if plan.get(key) != value:
            raise AssertionError(
                f"completion request-plan drift for {key}: {plan.get(key)!r} != {value!r}"
            )
    if MAX_HTTP_ATTEMPTS_PER_MODEL_CALL != 18:
        raise AssertionError("per-model-call physical-attempt bound drift")
    if MAX_HTTP_ATTEMPTS_PER_PROBE != 36:
        raise AssertionError("per-probe physical-attempt bound drift")
    if MAX_PROVIDER_HTTP_ATTEMPTS != 108:
        raise AssertionError("campaign physical-attempt bound drift")


def preflight() -> dict[str, Any]:
    plan = load_plan()
    validate_plan(plan)
    prompt = PROMPT_PATH.read_text()
    if "RW_CODING_PLAN_COMPLETION_OK" not in prompt:
        raise AssertionError("completion sentinel prompt drift")
    if MARKER_PATH.exists():
        raise AssertionError(
            "execution marker must be absent from frozen completion construction candidate"
        )
    return {
        "schema": "d2-vnext-hermes-coding-plan-completion-preflight-v0.1",
        "issue": ISSUE,
        "provider_execution_performed": False,
        "execution_marker_absent": True,
        "request_plan_sha256": file_sha256(PLAN_PATH),
        "prompt_sha256": file_sha256(PROMPT_PATH),
        "requested_model": MODEL,
        "endpoint_base_url": BASE_URL,
        "logical_probe_count": LOGICAL_PROBES,
        "max_agent_iterations_per_probe": MAX_AGENT_ITERATIONS,
        "max_tokens_per_model_call": MAX_TOKENS,
        "provider_http_attempt_count_maximum": MAX_PROVIDER_HTTP_ATTEMPTS,
        "physical_http_attempt_cap_enforced": True,
        "historical_substrate_enabled": False,
    }


def _assert_execution_environment() -> None:
    base._assert_execution_environment()


def _validate_runtime_versions() -> tuple[str, int, str]:
    return base._validate_runtime_versions()


def _rows_qualify(rows: list[dict[str, Any]]) -> bool:
    return len(rows) == LOGICAL_PROBES and all(
        row.get("status") == "success"
        and row.get("completed") is True
        and row.get("final_response_nonempty") is True
        and 1 <= int(row.get("agent_api_calls_observed", 0)) <= MAX_MODEL_CALLS_PER_PROBE
        and row.get("terminal_http_429_code_1113") is False
        and row.get("provider_attempts_blocked_by_cap") == 0
        and row.get("unexpected_outbound_http_requests_blocked") == 0
        and 1 <= int(row.get("provider_http_attempts_observed", 0))
        <= MAX_HTTP_ATTEMPTS_PER_PROBE
        for row in rows
    )


def execute() -> dict[str, Any]:
    if os.getenv("D2_CODING_PLAN_HERMES_COMPLETION_AUTHORIZED") != "1":
        raise RuntimeError("completion provider execution is not authorized in this process")
    key = os.getenv("ZAI_API_KEY", "").strip()
    if not key:
        raise RuntimeError("ZAI_API_KEY is empty")
    _assert_execution_environment()

    plan = load_plan()
    validate_plan(plan)
    if not MARKER_PATH.exists():
        raise AssertionError("authorized completion execution requires marker")

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
                    "Return the requested short plain-text acknowledgement."
                ),
                max_tokens=MAX_TOKENS,
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
                "max_tokens_per_model_call": MAX_TOKENS,
                "openai_sdk_max_retries": client_retries,
                "provider_http_attempts_maximum": MAX_HTTP_ATTEMPTS_PER_PROBE,
            }
            try:
                result = agent.run_conversation(user_message=prompt)
                final_response = str(result.get("final_response") or "")
                terminal_error = str(result.get("error") or "")
                completed = result.get("completed") is True
                result_failed = result.get("failed") is True or bool(terminal_error)
                api_calls = int(getattr(agent, "_api_call_count", 0))
                if (
                    result_failed
                    or not completed
                    or not final_response.strip()
                    or not 1 <= api_calls <= MAX_MODEL_CALLS_PER_PROBE
                ):
                    bounded = _bounded_error(
                        RuntimeError(
                            terminal_error
                            or "Hermes returned non-completed completion-envelope result"
                        )
                    )
                    row.update(
                        {
                            "status": "failure",
                            "completed": completed,
                            "final_response_nonempty": bool(final_response.strip()),
                            "agent_api_calls_observed": api_calls,
                            **bounded,
                        }
                    )
                else:
                    row.update(
                        {
                            "status": "success",
                            "completed": True,
                            "final_response_nonempty": True,
                            "final_response_length": len(final_response),
                            "final_response_sha256": sha256_bytes(final_response.encode()),
                            "agent_api_calls_observed": api_calls,
                            "terminal_http_429_code_1113": False,
                        }
                    )
            except Exception as exc:
                row.update(
                    {
                        "status": "failure",
                        "completed": False,
                        "final_response_nonempty": False,
                        "agent_api_calls_observed": int(
                            getattr(agent, "_api_call_count", 0)
                        ),
                        **_bounded_error(exc),
                    }
                )
            row.update(
                {
                    "provider_http_attempts_observed": budget.counts[probe_index],
                    "provider_attempts_blocked_by_cap": budget.blocked_budget_counts[
                        probe_index
                    ],
                    "unexpected_outbound_http_requests_blocked": (
                        budget.blocked_unexpected_counts[probe_index]
                    ),
                }
            )
            rows.append(row)

    qualified = _rows_qualify(rows)
    return {
        "schema": "d2-vnext-hermes-coding-plan-completion-qualification-result-v0.1",
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
        "max_agent_iterations_per_probe": MAX_AGENT_ITERATIONS,
        "max_tokens_per_model_call": MAX_TOKENS,
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
        "predecessor_issue": PREDECESSOR_ISSUE,
        "predecessor_pr": PREDECESSOR_PR,
        "predecessor_merge_sha": PREDECESSOR_MERGE_SHA,
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
