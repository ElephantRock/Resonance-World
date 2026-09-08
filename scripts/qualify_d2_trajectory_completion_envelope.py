#!/usr/bin/env python3
"""Trajectory-scale D2-shaped completion qualification on repaired Hermes transport."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import d2_trajectory_completion_contract as contract  # noqa: E402
import d2_trajectory_completion_transport as transport  # noqa: E402
from resonance_world.provider_send_guard import ProviderSendBudget  # noqa: E402


def preflight() -> dict[str, Any]:
    contract.validate_plan(contract.load_plan())
    if contract.MARKER.exists():
        raise AssertionError("execution marker must be absent from frozen candidate")
    topology = contract.materialize_topology()
    if json.loads(contract.TOPOLOGY.read_text()) != topology:
        raise AssertionError("committed topology drift")
    if contract.git_blob_sha(contract.GUARD_PATH) != contract.GUARD_GIT_BLOB_SHA:
        raise AssertionError("provider-send guard blob drift")
    return {
        "schema": "d2-trajectory-completion-envelope-preflight-v0.1",
        "issue": contract.ISSUE,
        "engineering_only": True,
        "provider_execution_performed": False,
        "execution_marker_absent": True,
        "request_plan_sha256": contract.file_sha(contract.PLAN),
        "topology_sha256": contract.file_sha(contract.TOPOLOGY),
        "provider_send_guard_git_blob_sha": contract.git_blob_sha(contract.GUARD_PATH),
        "stage1_result_sha256": contract.STAGE1_RESULT_SHA256,
        "topology": topology,
        "scientific_scoring_performed": False,
        "historical_substrate_enabled": False,
    }


def new_agent(logical_index: int) -> Any:
    from run_agent import AIAgent

    agent = AIAgent(
        provider=contract.PROVIDER,
        api_mode=contract.API_MODE,
        model=contract.MODEL,
        max_iterations=int(contract.PROFILE["max_iterations"]),
        enabled_toolsets=[],
        quiet_mode=True,
        save_trajectories=False,
        ephemeral_system_prompt=contract.system_prompt(),
        max_tokens=int(contract.PROFILE["max_tokens"]),
        request_overrides={
            "temperature": contract.TEMPERATURE,
            "extra_body": {"thinking": contract.THINKING},
            "extra_headers": {contract.PROBE_ORIGIN_HEADER: str(logical_index)},
        },
        skip_context_files=True,
        skip_memory=True,
        persist_session=False,
        fallback_model=None,
    )
    client_retries = int(getattr(agent.client, "max_retries", -1))
    if client_retries != contract.OPENAI_DEFAULT_MAX_RETRIES:
        raise AssertionError(f"OpenAI retry drift: {client_retries}")
    if agent.tools != [] or agent.valid_tool_names or agent._fallback_chain:
        raise AssertionError("Hermes tool/fallback drift")
    if (
        agent.model != contract.MODEL
        or agent.provider != contract.PROVIDER
        or agent.api_mode != contract.API_MODE
    ):
        raise AssertionError("Hermes route drift")
    if (
        str(agent.client.base_url).rstrip("/") != contract.BASE_URL
        or str(agent.base_url).rstrip("/") != contract.BASE_URL
    ):
        raise AssertionError("Hermes base URL drift")
    kwargs = agent._build_api_kwargs([{"role": "user", "content": "preflight"}])
    if float(kwargs.get("temperature", -1)) != contract.TEMPERATURE:
        raise AssertionError("sampling temperature drift")
    if kwargs.get("extra_body") != {"thinking": contract.THINKING}:
        raise AssertionError("thinking drift")
    headers = kwargs.get("extra_headers") or {}
    if str(headers.get(contract.PROBE_ORIGIN_HEADER, "")) != str(logical_index):
        raise AssertionError("independent request-origin header drift")
    return agent


def run_call(
    budget: ProviderSendBudget,
    ledger: transport.TransportLedger,
    logical: int,
    call_id: str,
    shape: str,
    seed: int,
    strategy: str,
) -> tuple[dict[str, Any], str]:
    prompt = contract.user_prompt(shape, seed, strategy)
    before_unexpected = budget.blocked_unexpected
    before_budget = budget.blocked_budget
    before_mismatch = ledger.attribution_mismatches
    row: dict[str, Any] = {
        "logical_index": logical,
        "call_id": call_id,
        "call_shape": shape,
        "max_iterations": contract.PROFILE["max_iterations"],
        "max_tokens": contract.PROFILE["max_tokens"],
        "prompt_bytes": len(prompt.encode()),
        "prompt_sha256": contract.sha(prompt),
    }
    agent: Any | None = None
    next_strategy = strategy
    try:
        with budget.logical_call(logical):
            agent = new_agent(logical)
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
        if not 1 <= api_calls <= int(contract.PROFILE["max_iterations"]):
            raise RuntimeError(f"Hermes semantic API-call count drift: {api_calls}")
        next_strategy = contract.parse_response(final)
        attempts = ledger.rows(logical)
        send_count = budget.sends_for_logical_call(logical)
        if not 1 <= send_count <= contract.MAX_SENDS_PER_LOGICAL:
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
                "final_response_sha256": contract.sha(final),
                "strategy_present": bool(next_strategy),
                "strategy_length": len(next_strategy),
                "strategy_sha256": contract.sha(next_strategy) if next_strategy else None,
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
                **contract.bounded_error(exc),
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


def call_pass(row: dict[str, Any]) -> bool:
    return (
        row.get("status") == "success"
        and 1
        <= int(row.get("agent_api_calls_observed", 0))
        <= int(contract.PROFILE["max_iterations"])
        and row.get("logical_attribution_integrity") is True
        and int(row.get("unexpected_outbound_blocks", 0)) == 0
        and int(row.get("provider_budget_blocks", 0)) == 0
        and int(row.get("attribution_mismatch_blocks", 0)) == 0
        and row.get("terminal_http_429_code_1113") is False
    )


def run_trajectory(
    budget: ProviderSendBudget,
    ledger: transport.TransportLedger,
    trajectory_index: int,
) -> dict[str, Any]:
    start = trajectory_index * contract.TRAJECTORY_CALLS_EACH
    strategies: dict[str, str] = {}
    rows: list[dict[str, Any]] = []
    for offset, spec in enumerate(contract.trajectory_specs(trajectory_index)):
        arm = str(spec["arm"])
        prior_strategy = strategies.get(arm, "")
        row, next_strategy = run_call(
            budget,
            ledger,
            start + offset,
            f"{contract.TRAJECTORIES[trajectory_index]}/{spec['phase']}",
            str(spec["shape"]),
            int(spec["seed"]),
            prior_strategy,
        )
        rows.append(row)
        if not call_pass(row):
            break
        strategies[arm] = next_strategy or prior_strategy
    complete = len(rows) == contract.TRAJECTORY_CALLS_EACH and all(
        call_pass(row) for row in rows
    )
    return {
        "trajectory": contract.TRAJECTORIES[trajectory_index],
        "registered_logical_calls": contract.TRAJECTORY_CALLS_EACH,
        "logical_index_start": start,
        "attempted_logical_calls": len(rows),
        "completed_logical_calls": sum(call_pass(row) for row in rows),
        "complete_55_of_55": complete,
        "calls": rows,
    }


def marker() -> dict[str, str]:
    if not contract.MARKER.exists():
        raise RuntimeError("authorization marker absent")
    fields = dict(
        line.split("=", 1) for line in contract.MARKER.read_text().splitlines() if line
    )
    if (
        set(fields) != {"candidate_sha", "issue", "authorization"}
        or fields["issue"] != str(contract.ISSUE)
        or fields["authorization"] != contract.AUTH_STRING
    ):
        raise RuntimeError("authorization marker invalid")
    if not re.fullmatch(r"[0-9a-f]{40}", fields["candidate_sha"]):
        raise RuntimeError("candidate SHA invalid")
    return fields


def execute() -> dict[str, Any]:
    if os.getenv(contract.AUTH_ENV) != "1" or not os.getenv("ZAI_API_KEY", "").strip():
        raise RuntimeError("provider execution not authorized/credentialed")
    contract.assert_execution_environment()
    contract.validate_plan(contract.load_plan())
    auth = marker()
    if contract.git_blob_sha(contract.GUARD_PATH) != contract.GUARD_GIT_BLOB_SHA:
        raise AssertionError("provider-send guard blob drift")
    hermes_version, sdk_retries, httpx_version = contract.validate_runtime_versions()
    budget = ProviderSendBudget(
        allowed_url_prefix=contract.BASE_URL,
        maximum_logical_calls=contract.MAX_LOGICAL_CALLS,
        maximum_sends_per_logical_call=contract.MAX_SENDS_PER_LOGICAL,
        maximum_sends_total=contract.MAX_SENDS_TOTAL,
    )
    ledger = transport.TransportLedger()
    workers = transport.ProviderWorkerTracker()
    trajectories: list[dict[str, Any]] = []
    with budget.propagate_to_child_threads():
        with transport.transport_guard(budget, ledger, workers):
            with ThreadPoolExecutor(max_workers=contract.MAX_TRAJECTORY_CONCURRENCY) as pool:
                trajectories = list(
                    pool.map(
                        lambda index: run_trajectory(budget, ledger, index),
                        range(len(contract.TRAJECTORIES)),
                    )
                )

    attempted = sum(int(entry["attempted_logical_calls"]) for entry in trajectories)
    completed = sum(int(entry["completed_logical_calls"]) for entry in trajectories)
    qualified = (
        len(trajectories) == len(contract.TRAJECTORIES)
        and all(entry["complete_55_of_55"] is True for entry in trajectories)
        and attempted == contract.MAX_LOGICAL_CALLS
        and completed == contract.MAX_LOGICAL_CALLS
        and budget.blocked_unexpected == 0
        and budget.blocked_budget == 0
        and ledger.attribution_mismatches == 0
        and budget.total_sends <= contract.MAX_SENDS_TOTAL
        and workers.alive_after_drain == 0
        and workers.transport_hooks_restored is True
    )
    return {
        "schema": "d2-trajectory-completion-envelope-result-v0.1",
        "issue": contract.ISSUE,
        "engineering_only": True,
        "purpose": "trajectory_scale_d2_shaped_completion_on_repaired_hermes_transport",
        "candidate_sha": auth["candidate_sha"],
        "authorization_basis": (
            "Autonomous Operating Charter Amendment A1 — standing execution authority"
        ),
        "predecessor_apparatus_issue": 223,
        "predecessor_apparatus_result_unchanged": "FAIL",
        "transport_conformance_issue": 229,
        "transport_conformance_result_unchanged": "FAIL",
        "stage1_completion_issue": contract.STAGE1_ISSUE,
        "stage1_completion_result_unchanged": "PASS",
        "stage1_evidence_merge_sha": contract.STAGE1_EVIDENCE_MERGE_SHA,
        "stage1_result_sha256": contract.STAGE1_RESULT_SHA256,
        "selected_profile": contract.PROFILE,
        "predecessor_stream_rerun_or_replacement_performed": False,
        "guard_repair_pr": 228,
        "guard_repair_merge_sha": contract.GUARD_REPAIR_MERGE_SHA,
        "provider_send_guard_git_blob_sha": contract.git_blob_sha(contract.GUARD_PATH),
        "provider": "Z.AI",
        "subscription_product": "GLM Coding Plan",
        "supported_product_environment": "Hermes Agent Python library",
        "hermes_repository": contract.HERMES_REPOSITORY,
        "hermes_revision": contract.HERMES_REVISION,
        "hermes_package_version": hermes_version,
        "hermes_run_agent_blob_sha": contract.HERMES_RUN_AGENT_BLOB_SHA,
        "openai_sdk_version": contract.OPENAI_VERSION,
        "openai_sdk_default_max_retries": sdk_retries,
        "httpx_version": httpx_version,
        "endpoint_base_url": contract.BASE_URL,
        "provider_id": contract.PROVIDER,
        "api_mode": contract.API_MODE,
        "requested_model": contract.MODEL,
        "effective_model_identity_observed": False,
        "sampling_temperature": contract.TEMPERATURE,
        "thinking": contract.THINKING,
        "trajectories": trajectories,
        "trajectory_logical_calls_each": contract.TRAJECTORY_CALLS_EACH,
        "trajectory_logical_calls_registered": contract.MAX_LOGICAL_CALLS,
        "logical_calls_attempted": attempted,
        "logical_calls_completed": completed,
        "trajectory_max_concurrency": contract.MAX_TRAJECTORY_CONCURRENCY,
        "maximum_physical_sends_per_logical_call": contract.MAX_SENDS_PER_LOGICAL,
        "maximum_physical_sends_total": contract.MAX_SENDS_TOTAL,
        "physical_provider_sends_observed_total": budget.total_sends,
        "unexpected_outbound_http_requests_blocked": budget.blocked_unexpected,
        "provider_attempts_blocked_by_cap": budget.blocked_budget,
        "logical_attribution_mismatch_blocks": ledger.attribution_mismatches,
        "logical_context_thread_propagation_used": True,
        "independent_request_origin_header": contract.PROBE_ORIGIN_HEADER,
        "provider_worker_threads_observed": workers.observed,
        "provider_worker_threads_alive_after_drain": workers.alive_after_drain,
        "provider_worker_drain_timeout_seconds": contract.PROVIDER_WORKER_DRAIN_TIMEOUT_SECONDS,
        "transport_hooks_restored_after_worker_drain": workers.transport_hooks_restored,
        "qualification_pass": qualified,
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
