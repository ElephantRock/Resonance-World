#!/usr/bin/env python3
"""Qualify a future-only terminal structured-completion adapter."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from resonance_world import d2_terminal_adapter as adapter
from resonance_world import d2_terminal_transport as transport
from resonance_world.provider_send_guard import ProviderSendBudget

ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / "research" / "d2_terminal_adapter"
PLAN = DIR / "REQUEST_PLAN.json"
PROBES = DIR / "PROBES.json"
MARKER = DIR / "RUN_D2_TERMINAL_ADAPTER_QUALIFICATION"
GUARD_PATH = ROOT / "src" / "resonance_world" / "provider_send_guard.py"
EVIDENCE_243 = (
    ROOT / "research" / "evidence" / "d2_terminal_response_observability" / "RESULT.json"
)

ISSUE = 246
AUTH_ENV = "D2_TERMINAL_ADAPTER_AUTHORIZED"
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
OPENAI_DEFAULT_MAX_RETRIES = 2
MAX_ITERATIONS = 2
MAX_TOKENS = 768
TEMPERATURE = 0.8
THINKING = {"type": "disabled"}
MAX_CONCURRENCY = 4
MAX_SENDS_PER_LOGICAL = 36
MAX_SENDS_TOTAL = 180
GUARD_GIT_BLOB_SHA = "4b8896235d8048523d007400d0acfe85470f628c"
PLAN_GIT_BLOB_SHA = "05f3e9ab10e8d8f1ac833d6cf033a5fd0a32a4cb"
PROBES_GIT_BLOB_SHA = "81ad8a9df6cc7862286ea2e42d100770a6abbaee"
EVIDENCE_243_MERGE_SHA = "83257f740262726e906fb203c4657163bf36079f"
EVIDENCE_243_SHA256 = "cde58890d2d6bd1027381ffa559b385f11883c15e08860a823a1a5017495a9d6"

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
    header = f"blob {len(data)}\0".encode()
    return hashlib.sha1(header + data).hexdigest()


def load_probes() -> list[dict[str, Any]]:
    return adapter.validate_probes(json.loads(PROBES.read_text()))


def validate_frozen_files() -> list[dict[str, Any]]:
    if git_blob_sha(PLAN) != PLAN_GIT_BLOB_SHA:
        raise AssertionError("request plan blob drift")
    if git_blob_sha(PROBES) != PROBES_GIT_BLOB_SHA:
        raise AssertionError("probe manifest blob drift")
    if git_blob_sha(GUARD_PATH) != GUARD_GIT_BLOB_SHA:
        raise AssertionError("provider-send guard blob drift")
    if file_sha(EVIDENCE_243) != EVIDENCE_243_SHA256:
        raise AssertionError("#243 preserved result drift")

    plan = json.loads(PLAN.read_text())
    if (
        plan.get("schema") != "d2-terminal-adapter-request-plan-v0.1"
        or plan.get("issue") != ISSUE
        or plan.get("probe_count") != adapter.PROBE_COUNT
        or plan.get("max_iterations") != MAX_ITERATIONS
        or plan.get("max_tokens") != MAX_TOKENS
        or plan.get("sampling_temperature") != TEMPERATURE
        or plan.get("maximum_physical_sends_total") != MAX_SENDS_TOTAL
        or plan.get("terminal_override_exact_physical_sends") != 2
        or plan.get("preserved_evidence_expected_terminal_overrides") != 8
        or plan.get("pass_requires_all_effective_completed") is not True
        or plan.get("pass_requires_terminal_override_exercised") is not True
        or plan.get("workflow_rerun_allowed") is not False
        or plan.get("same_request_stream_rerun_allowed") is not False
        or plan.get("hermes_completed_mutation_allowed") is not False
    ):
        raise AssertionError("request plan semantic drift")
    return load_probes()


def _bounded_result_view(row: dict[str, Any]) -> dict[str, Any]:
    """Reconstruct only fields consumed by the pure adapter from bounded metadata."""

    return {
        "completed": (
            bool(row["hermes_completed"])
            if row.get("hermes_completed_flag_valid", True)
            else None
        ),
        "failed": bool(row["hermes_failed"]),
        "partial": bool(row["hermes_partial"]),
        "interrupted": bool(row["hermes_interrupted"]),
        "error": "bounded-error-present" if row["hermes_error_present"] else None,
        "api_calls": int(row["api_calls"]),
        "final_response": (
            "bounded-nonempty-response-sentinel"
            if int(row["final_response_length"]) > 0
            else ""
        ),
    }


def classify_row(
    row: dict[str, Any],
    *,
    unexpected_outbound_blocks: int,
    provider_budget_blocks: int,
    attribution_mismatch_blocks: int,
) -> adapter.TerminalCompletionDecision:
    return adapter.evaluate_terminal_completion(
        _bounded_result_view(row),
        max_iterations=MAX_ITERATIONS,
        parse_valid=bool(row["structured_parse_valid"]),
        logical_attribution_integrity=bool(row["logical_attribution_integrity"]),
        attempts=row["attempts"],
        physical_sends=int(row["physical_provider_sends_observed"]),
        unexpected_outbound_blocks=unexpected_outbound_blocks,
        provider_budget_blocks=provider_budget_blocks,
        attribution_mismatch_blocks=attribution_mismatch_blocks,
    )


def preserved_evidence_regression() -> dict[str, int]:
    """Reproduce the #243 bounded metadata with the new pure adapter."""

    evidence = json.loads(EVIDENCE_243.read_text())
    if evidence.get("diagnostic_outcome") != "VALID_TERMINAL_RESPONSE_OBSERVED":
        raise AssertionError("#243 outcome drift")
    rows = evidence.get("probes")
    if not isinstance(rows, list) or len(rows) != adapter.PROBE_COUNT:
        raise AssertionError("#243 probe count drift")

    decisions = [
        classify_row(
            row,
            unexpected_outbound_blocks=int(
                evidence["unexpected_outbound_http_requests_blocked"]
            ),
            provider_budget_blocks=int(evidence["provider_attempts_blocked_by_cap"]),
            attribution_mismatch_blocks=int(
                evidence["logical_attribution_mismatch_blocks"]
            ),
        )
        for row in rows
    ]
    effective = sum(decision.effective_completed for decision in decisions)
    native = sum(
        decision.effective_completed and decision.hermes_completed
        for decision in decisions
    )
    overrides = sum(decision.terminal_iteration_override_used for decision in decisions)
    if (effective, native, overrides) != (72, 64, 8):
        raise AssertionError("#243 preserved-evidence adapter regression failed")
    return {
        "effective_completed": effective,
        "native_completed": native,
        "terminal_overrides": overrides,
    }


def preflight() -> dict[str, Any]:
    probes = validate_frozen_files()
    if MARKER.exists():
        raise AssertionError("execution marker must be absent from frozen candidate")
    prompt_lengths = [len(adapter.user_prompt(probe).encode()) for probe in probes]
    if not all(2100 <= length <= 2200 for length in prompt_lengths):
        raise AssertionError("fresh prompt envelope drift")
    regression = preserved_evidence_regression()
    return {
        "schema": "d2-terminal-adapter-preflight-v0.1",
        "issue": ISSUE,
        "engineering_only": True,
        "provider_execution_performed": False,
        "execution_marker_absent": True,
        "request_plan_git_blob_sha": git_blob_sha(PLAN),
        "probes_git_blob_sha": git_blob_sha(PROBES),
        "provider_send_guard_git_blob_sha": git_blob_sha(GUARD_PATH),
        "causal_predecessor_result_sha256": file_sha(EVIDENCE_243),
        "preserved_evidence_regression": regression,
        "probe_count": len(probes),
        "minimum_prompt_bytes": min(prompt_lengths),
        "maximum_prompt_bytes": max(prompt_lengths),
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
        raise RuntimeError("GLM_BASE_URL must equal frozen Coding Plan base URL")
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
    if (
        importlib.metadata.version("httpx") != HTTPX_VERSION
        or httpx.__version__ != HTTPX_VERSION
    ):
        raise AssertionError("httpx version drift")
    if int(DEFAULT_MAX_RETRIES) != OPENAI_DEFAULT_MAX_RETRIES:
        raise AssertionError("OpenAI retry default drift")
    if not hasattr(httpx.Client, "_send_single_request"):
        raise AssertionError("httpx physical-send hook unavailable")
    if not hasattr(httpx.AsyncClient, "_send_single_request"):
        raise AssertionError("httpx async physical-send hook unavailable")


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


def new_agent(logical_index: int) -> Any:
    from run_agent import AIAgent

    agent = AIAgent(
        provider=PROVIDER,
        api_mode=API_MODE,
        model=MODEL,
        max_iterations=MAX_ITERATIONS,
        enabled_toolsets=[],
        quiet_mode=True,
        save_trajectories=False,
        ephemeral_system_prompt=adapter.system_prompt(),
        max_tokens=MAX_TOKENS,
        request_overrides={
            "temperature": TEMPERATURE,
            "extra_body": {"thinking": THINKING},
            "extra_headers": {transport.ORIGIN_HEADER: str(logical_index)},
        },
        skip_context_files=True,
        skip_memory=True,
        persist_session=False,
        fallback_model=None,
    )
    if int(getattr(agent.client, "max_retries", -1)) != OPENAI_DEFAULT_MAX_RETRIES:
        raise AssertionError("OpenAI client retry drift")
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
    if str(headers.get(transport.ORIGIN_HEADER, "")) != str(logical_index):
        raise AssertionError("request-origin header drift")
    return agent


def run_probe(
    budget: ProviderSendBudget,
    probe: dict[str, Any],
) -> dict[str, Any]:
    logical = int(probe["logical_index"])
    prompt = adapter.user_prompt(probe)
    row: dict[str, Any] = {
        "logical_index": logical,
        "probe_id": probe["probe_id"],
        "development_budget": probe["development_budget"],
        "seed": probe["seed"],
        "prompt_bytes": len(prompt.encode()),
        "prompt_sha256": sha(prompt),
        "runtime_exception": False,
    }
    agent: Any | None = None
    try:
        with budget.logical_call(logical):
            agent = new_agent(logical)
            result = agent.run_conversation(user_message=prompt)

        agent_api_calls = int(getattr(agent, "_api_call_count", 0))
        result_api_calls = result.get("api_calls")
        if isinstance(result_api_calls, bool) or not isinstance(result_api_calls, int):
            raise AssertionError("Hermes result api_calls field missing or invalid")
        if result_api_calls != agent_api_calls:
            raise AssertionError("Hermes result/agent API-call count mismatch")
        if not 1 <= agent_api_calls <= MAX_ITERATIONS:
            raise AssertionError("Hermes API-call count outside frozen envelope")

        final = result.get("final_response")
        final_text = final if isinstance(final, str) else ""
        parse_valid, strategy = adapter.parse_response(final_text)
        completed_value = result.get("completed")
        row.update(
            {
                "hermes_completed_flag_valid": isinstance(completed_value, bool),
                "hermes_completed": completed_value is True,
                "hermes_failed": result.get("failed") is True,
                "hermes_partial": result.get("partial") is True,
                "hermes_interrupted": result.get("interrupted") is True,
                "hermes_error_present": bool(result.get("error")),
                "api_calls": agent_api_calls,
                "result_api_calls": result_api_calls,
                "final_response_length": len(final_text),
                "final_response_sha256": sha(final_text) if final_text else None,
                "structured_parse_valid": parse_valid,
                "strategy_length": len(strategy) if parse_valid else 0,
                "strategy_sha256": sha(strategy) if parse_valid and strategy else None,
            }
        )
    except Exception as exc:
        row.update(
            {
                "runtime_exception": True,
                "hermes_completed": False,
                "hermes_failed": True,
                "hermes_partial": False,
                "hermes_interrupted": False,
                "hermes_error_present": True,
                "api_calls": int(
                    getattr(agent, "_api_call_count", 0) if agent is not None else 0
                ),
                "result_api_calls": None,
                "final_response_length": 0,
                "final_response_sha256": None,
                "structured_parse_valid": False,
                "strategy_length": 0,
                "strategy_sha256": None,
                **bounded_error(exc),
            }
        )
    return row


def probe_has_apparatus_failure(row: dict[str, Any]) -> bool:
    """Separate apparatus failures from clean adapter qualification failures."""

    return bool(
        row.get("runtime_exception")
        or row.get("hermes_completed_flag_valid") is False
        or row.get("hermes_failed")
        or row.get("hermes_partial")
        or row.get("hermes_interrupted")
        or row.get("hermes_error_present")
        or row.get("adapter_reason") == "transport_not_exact_clean"
    )


def execute() -> dict[str, Any]:
    assert_execution_environment()
    probes = validate_frozen_files()
    auth = parse_marker()
    validate_runtime_versions()
    regression = preserved_evidence_regression()

    budget = ProviderSendBudget(
        allowed_url_prefix=BASE_URL,
        maximum_logical_calls=adapter.PROBE_COUNT,
        maximum_sends_per_logical_call=MAX_SENDS_PER_LOGICAL,
        maximum_sends_total=MAX_SENDS_TOTAL,
    )
    ledger = transport.TransportLedger()
    workers = transport.ProviderWorkerTracker()

    with budget.propagate_to_child_threads():
        with transport.transport_guard(budget, ledger, workers):
            with ThreadPoolExecutor(max_workers=MAX_CONCURRENCY) as pool:
                rows = list(pool.map(lambda probe: run_probe(budget, probe), probes))

    global_transport_clean = (
        budget.blocked_unexpected == 0
        and budget.blocked_budget == 0
        and ledger.attribution_mismatches == 0
        and workers.alive_after_drain == 0
        and workers.transport_hooks_restored is True
        and 1 <= budget.total_sends <= MAX_SENDS_TOTAL
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
        row.update(
            {
                "physical_provider_sends_observed": sends,
                "attempts": attempts,
                "logical_attribution_integrity": attribution_ok,
            }
        )
        decision = classify_row(
            row,
            unexpected_outbound_blocks=budget.blocked_unexpected,
            provider_budget_blocks=budget.blocked_budget,
            attribution_mismatch_blocks=ledger.attribution_mismatches,
        )
        row.update(
            {
                "effective_completed": decision.effective_completed,
                "terminal_iteration_override_used": (
                    decision.terminal_iteration_override_used
                ),
                "adapter_reason": decision.reason,
            }
        )

    apparatus_failure = (
        len(rows) != adapter.PROBE_COUNT
        or any(probe_has_apparatus_failure(row) for row in rows)
        or not global_transport_clean
    )
    effective_count = sum(bool(row["effective_completed"]) for row in rows)
    native_count = sum(
        bool(row["effective_completed"]) and bool(row["hermes_completed"])
        for row in rows
    )
    override_count = sum(bool(row["terminal_iteration_override_used"]) for row in rows)

    if apparatus_failure:
        qualification_outcome = "APPARATUS_FAILURE"
    elif effective_count != adapter.PROBE_COUNT:
        qualification_outcome = "FAIL"
    elif override_count == 0:
        qualification_outcome = "ADAPTER_PATH_NOT_EXERCISED"
    else:
        qualification_outcome = "PASS"

    return {
        "schema": "d2-terminal-adapter-qualification-result-v0.1",
        "issue": ISSUE,
        "engineering_only": True,
        "purpose": "qualify_terminal_structured_completion_adapter_under_realistic_d2_envelope",
        "candidate_sha": auth["candidate_sha"],
        "authorization_basis": (
            "Autonomous Operating Charter Amendment A1 — standing execution authority"
        ),
        "causal_predecessor_issue": 243,
        "causal_predecessor_outcome_unchanged": "VALID_TERMINAL_RESPONSE_OBSERVED",
        "causal_predecessor_evidence_merge_sha": EVIDENCE_243_MERGE_SHA,
        "causal_predecessor_result_sha256": EVIDENCE_243_SHA256,
        "predecessor_trajectory_issue": 234,
        "predecessor_trajectory_result_unchanged": "FAIL",
        "predecessor_terminal_semantics_issue": 237,
        "predecessor_terminal_semantics_result_unchanged": "FAIL",
        "preserved_evidence_regression": regression,
        "guard_repair_pr": 228,
        "provider_send_guard_git_blob_sha": git_blob_sha(GUARD_PATH),
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
        "openai_sdk_default_max_retries": OPENAI_DEFAULT_MAX_RETRIES,
        "httpx_version": HTTPX_VERSION,
        "max_iterations": MAX_ITERATIONS,
        "max_tokens": MAX_TOKENS,
        "sampling_temperature": TEMPERATURE,
        "thinking": THINKING,
        "probe_count_registered": adapter.PROBE_COUNT,
        "probe_count_attempted": len(rows),
        "maximum_concurrency": MAX_CONCURRENCY,
        "maximum_physical_sends_per_logical_call": MAX_SENDS_PER_LOGICAL,
        "maximum_physical_sends_total": MAX_SENDS_TOTAL,
        "physical_provider_sends_observed_total": budget.total_sends,
        "unexpected_outbound_http_requests_blocked": budget.blocked_unexpected,
        "provider_attempts_blocked_by_cap": budget.blocked_budget,
        "logical_attribution_mismatch_blocks": ledger.attribution_mismatches,
        "provider_worker_threads_observed": workers.observed,
        "provider_worker_threads_alive_after_drain": workers.alive_after_drain,
        "transport_hooks_restored_after_worker_drain": workers.transport_hooks_restored,
        "probes": rows,
        "effective_completed_count": effective_count,
        "native_hermes_completed_count": native_count,
        "terminal_iteration_override_count": override_count,
        "terminal_iteration_override_exercised": override_count > 0,
        "apparatus_failure": apparatus_failure,
        "qualification_outcome": qualification_outcome,
        "qualification_pass": qualification_outcome == "PASS",
        "hermes_completed_mutated": False,
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
        "raw_final_response_content_persisted": False,
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
