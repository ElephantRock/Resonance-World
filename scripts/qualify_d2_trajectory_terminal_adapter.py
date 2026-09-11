#!/usr/bin/env python3
"""Qualify trajectory-scale D2 completion with the #251 terminal adapter."""

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
from resonance_world import d2_terminal_adapter as adapter  # noqa: E402
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
    if contract.git_blob_sha(contract.ADAPTER_PATH) != contract.ADAPTER_GIT_BLOB_SHA:
        raise AssertionError("qualified adapter blob drift")
    evidence = contract.validate_preserved_adapter_evidence()
    return {
        "schema": "d2-trajectory-terminal-adapter-preflight-v0.1",
        "issue": contract.ISSUE,
        "provider_execution_performed": False,
        "execution_marker_absent": True,
        "request_plan_sha256": contract.file_sha(contract.PLAN),
        "topology_sha256": contract.file_sha(contract.TOPOLOGY),
        "provider_send_guard_git_blob_sha": contract.git_blob_sha(contract.GUARD_PATH),
        "terminal_adapter_git_blob_sha": contract.git_blob_sha(contract.ADAPTER_PATH),
        "qualified_adapter_result_sha256": contract.file_sha(contract.EVIDENCE_251),
        "qualified_adapter_evidence": evidence,
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
    if int(getattr(agent.client, "max_retries", -1)) != contract.OPENAI_DEFAULT_MAX_RETRIES:
        raise AssertionError("OpenAI retry drift")
    if agent.tools != [] or agent.valid_tool_names or agent._fallback_chain:
        raise AssertionError("Hermes tool/fallback drift")
    if (agent.model, agent.provider, agent.api_mode) != (
        contract.MODEL,
        contract.PROVIDER,
        contract.API_MODE,
    ):
        raise AssertionError("Hermes route drift")
    if str(agent.client.base_url).rstrip("/") != contract.BASE_URL:
        raise AssertionError("Hermes client base URL drift")
    kwargs = agent._build_api_kwargs([{"role": "user", "content": "preflight"}])
    if float(kwargs.get("temperature", -1)) != contract.TEMPERATURE:
        raise AssertionError("sampling temperature drift")
    if kwargs.get("extra_body") != {"thinking": contract.THINKING}:
        raise AssertionError("thinking drift")
    if str((kwargs.get("extra_headers") or {}).get(contract.PROBE_ORIGIN_HEADER, "")) != str(logical_index):
        raise AssertionError("request-origin header drift")
    return agent


def _result_view(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "completed": row["hermes_completed"] if row.get("hermes_completed_flag_valid") else None,
        "failed": row["hermes_failed"],
        "partial": row["hermes_partial"],
        "interrupted": row["hermes_interrupted"],
        "error": "bounded-error-present" if row["hermes_error_present"] else None,
        "api_calls": row["api_calls"],
        "final_response": "bounded-nonempty-response-sentinel" if row["final_response_length"] else "",
    }


def classify_row(row: dict[str, Any], budget: ProviderSendBudget, ledger: transport.TransportLedger) -> adapter.TerminalCompletionDecision:
    return adapter.evaluate_terminal_completion(
        _result_view(row),
        max_iterations=int(contract.PROFILE["max_iterations"]),
        parse_valid=bool(row["structured_parse_valid"]),
        logical_attribution_integrity=bool(row["logical_attribution_integrity"]),
        attempts=row["attempts"],
        physical_sends=int(row["physical_provider_sends_observed"]),
        unexpected_outbound_blocks=budget.blocked_unexpected,
        provider_budget_blocks=budget.blocked_budget,
        attribution_mismatch_blocks=ledger.attribution_mismatches,
    )


def run_call(
    budget: ProviderSendBudget,
    ledger: transport.TransportLedger,
    logical: int,
    call_id: str,
    shape: str,
    seed: int,
    arm_budget: int | None,
    strategy: str,
) -> tuple[dict[str, Any], str]:
    prompt = contract.user_prompt(shape, seed, arm_budget, strategy)
    row: dict[str, Any] = {
        "logical_index": logical,
        "call_id": call_id,
        "call_shape": shape,
        "seed": seed,
        "arm_budget": arm_budget,
        "prompt_bytes": len(prompt.encode()),
        "prompt_sha256": contract.sha(prompt),
        "runtime_exception": False,
    }
    agent: Any | None = None
    strategy_out = ""
    try:
        with budget.logical_call(logical):
            agent = new_agent(logical)
            result = agent.run_conversation(user_message=prompt)
        api_calls = int(getattr(agent, "_api_call_count", 0))
        result_calls = result.get("api_calls")
        if isinstance(result_calls, bool) or not isinstance(result_calls, int):
            raise AssertionError("Hermes result api_calls invalid")
        if result_calls != api_calls or not 1 <= api_calls <= 2:
            raise AssertionError("Hermes API-call count drift")
        final = result.get("final_response")
        final_text = final if isinstance(final, str) else ""
        parse_valid, strategy_out = adapter.parse_response(final_text)
        completed = result.get("completed")
        row.update(
            {
                "hermes_completed_flag_valid": isinstance(completed, bool),
                "hermes_completed": completed is True,
                "hermes_failed": result.get("failed") is True,
                "hermes_partial": result.get("partial") is True,
                "hermes_interrupted": result.get("interrupted") is True,
                "hermes_error_present": bool(result.get("error")),
                "api_calls": api_calls,
                "result_api_calls": result_calls,
                "final_response_length": len(final_text),
                "final_response_sha256": contract.sha(final_text) if final_text else None,
                "structured_parse_valid": parse_valid,
                "strategy_length": len(strategy_out) if parse_valid else 0,
                "strategy_sha256": contract.sha(strategy_out) if parse_valid and strategy_out else None,
            }
        )
    except Exception as exc:
        row.update(
            {
                "runtime_exception": True,
                "hermes_completed_flag_valid": True,
                "hermes_completed": False,
                "hermes_failed": True,
                "hermes_partial": False,
                "hermes_interrupted": False,
                "hermes_error_present": True,
                "api_calls": int(getattr(agent, "_api_call_count", 0) if agent is not None else 0),
                "result_api_calls": None,
                "final_response_length": 0,
                "final_response_sha256": None,
                "structured_parse_valid": False,
                "strategy_length": 0,
                "strategy_sha256": None,
                **contract.bounded_error(exc),
            }
        )
    attempts = ledger.rows(logical)
    sends = budget.sends_for_logical_call(logical)
    row.update(
        {
            "physical_provider_sends_observed": sends,
            "attempts": attempts,
            "logical_attribution_integrity": len(attempts) == sends
            and all(
                attempt["origin_logical_index"] == logical
                and attempt["logical_index"] == logical
                for attempt in attempts
            ),
        }
    )
    decision = classify_row(row, budget, ledger)
    row.update(
        {
            "effective_completed": decision.effective_completed,
            "terminal_iteration_override_used": decision.terminal_iteration_override_used,
            "adapter_reason": decision.reason,
        }
    )
    if shape == "developed_development" and decision.effective_completed and strategy_out:
        return row, strategy_out
    return row, strategy


def row_has_apparatus_failure(row: dict[str, Any]) -> bool:
    return bool(
        row.get("runtime_exception")
        or row.get("hermes_completed_flag_valid") is False
        or row.get("adapter_reason")
        in {
            "attribution_integrity_failed",
            "unexpected_outbound_blocked",
            "provider_budget_blocked",
            "attribution_mismatch",
            "transport_not_exact_clean",
            "transport_counter_invalid",
            "physical_sends_invalid",
        }
    )


def run_trajectory(budget: ProviderSendBudget, ledger: transport.TransportLedger, trajectory_index: int) -> dict[str, Any]:
    start = trajectory_index * contract.TRAJECTORY_CALLS_EACH
    strategies: dict[str, str] = {}
    rows: list[dict[str, Any]] = []
    for offset, spec in enumerate(contract.trajectory_specs(trajectory_index)):
        arm = str(spec["arm"])
        row, next_strategy = run_call(
            budget,
            ledger,
            start + offset,
            f"{contract.TRAJECTORIES[trajectory_index]}/{spec['phase']}",
            str(spec["shape"]),
            int(spec["seed"]),
            int(spec["arm_budget"]) if spec["arm_budget"] is not None else None,
            strategies.get(arm, ""),
        )
        rows.append(row)
        if not row["effective_completed"]:
            break
        if spec["shape"] == "developed_development":
            strategies[arm] = next_strategy
    complete = len(rows) == 55 and all(row["effective_completed"] for row in rows)
    return {
        "trajectory": contract.TRAJECTORIES[trajectory_index],
        "registered_logical_calls": 55,
        "logical_index_start": start,
        "attempted_logical_calls": len(rows),
        "effective_completed_logical_calls": sum(bool(row["effective_completed"]) for row in rows),
        "complete_55_of_55": complete,
        "calls": rows,
    }


def marker() -> dict[str, str]:
    if not contract.MARKER.exists():
        raise RuntimeError("authorization marker absent")
    fields = dict(line.split("=", 1) for line in contract.MARKER.read_text().splitlines() if line)
    if set(fields) != {"candidate_sha", "issue", "authorization"}:
        raise RuntimeError("authorization marker invalid")
    if fields["issue"] != str(contract.ISSUE) or fields["authorization"] != contract.AUTH_STRING:
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
    if contract.git_blob_sha(contract.ADAPTER_PATH) != contract.ADAPTER_GIT_BLOB_SHA:
        raise AssertionError("qualified adapter blob drift")
    preserved = contract.validate_preserved_adapter_evidence()
    hermes_version, sdk_retries, httpx_version = contract.validate_runtime_versions()
    budget = ProviderSendBudget(
        allowed_url_prefix=contract.BASE_URL,
        maximum_logical_calls=220,
        maximum_sends_per_logical_call=36,
        maximum_sends_total=400,
    )
    ledger = transport.TransportLedger()
    workers = transport.ProviderWorkerTracker()
    with budget.propagate_to_child_threads():
        with transport.transport_guard(budget, ledger, workers):
            with ThreadPoolExecutor(max_workers=4) as pool:
                trajectories = list(pool.map(lambda i: run_trajectory(budget, ledger, i), range(4)))
    all_calls = [call for trajectory in trajectories for call in trajectory["calls"]]
    attempted = sum(int(t["attempted_logical_calls"]) for t in trajectories)
    effective = sum(int(t["effective_completed_logical_calls"]) for t in trajectories)
    overrides = sum(bool(row["terminal_iteration_override_used"]) for row in all_calls)
    native = sum(bool(row["effective_completed"]) and bool(row["hermes_completed"]) for row in all_calls)
    global_clean = (
        budget.blocked_unexpected == 0
        and budget.blocked_budget == 0
        and ledger.attribution_mismatches == 0
        and workers.alive_after_drain == 0
        and workers.transport_hooks_restored is True
        and 1 <= budget.total_sends <= 400
    )
    apparatus_failure = any(row_has_apparatus_failure(row) for row in all_calls) or not global_clean
    all_effective = attempted == 220 and effective == 220 and all(t["complete_55_of_55"] for t in trajectories)
    if apparatus_failure:
        outcome = "APPARATUS_FAILURE"
    elif not all_effective:
        outcome = "FAIL"
    elif overrides == 0:
        outcome = "ADAPTER_PATH_NOT_EXERCISED"
    else:
        outcome = "PASS"
    return {
        "schema": "d2-trajectory-terminal-adapter-result-v0.1",
        "issue": 255,
        "engineering_only": True,
        "fresh_namespace": contract.NAMESPACE,
        "candidate_sha": auth["candidate_sha"],
        "authorization_basis": "Autonomous Operating Charter Amendment A1 — standing execution authority",
        "predecessor_trajectory_issue": 234,
        "predecessor_trajectory_result_unchanged": "FAIL",
        "terminal_observability_issue": 243,
        "terminal_observability_result_unchanged": "VALID_TERMINAL_RESPONSE_OBSERVED",
        "qualified_adapter_issue": 251,
        "qualified_adapter_result_unchanged": "PASS",
        "qualified_adapter_evidence_merge_sha": contract.EVIDENCE_251_MERGE_SHA,
        "qualified_adapter_result_sha256": contract.EVIDENCE_251_SHA256,
        "qualified_adapter_preserved_metrics": preserved,
        "terminal_adapter_git_blob_sha": contract.git_blob_sha(contract.ADAPTER_PATH),
        "hermes_completed_mutated": False,
        "predecessor_stream_rerun_or_replacement_performed": False,
        "provider": "Z.AI",
        "subscription_product": "GLM Coding Plan",
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
        "selected_profile": contract.PROFILE,
        "sampling_temperature": contract.TEMPERATURE,
        "thinking": contract.THINKING,
        "trajectories": trajectories,
        "trajectory_logical_calls_each": 55,
        "trajectory_logical_calls_registered": 220,
        "logical_calls_attempted": attempted,
        "effective_completed_count": effective,
        "native_hermes_completed_count": native,
        "terminal_iteration_override_count": overrides,
        "terminal_iteration_override_exercised": overrides > 0,
        "trajectory_max_concurrency": 4,
        "maximum_physical_sends_per_logical_call": 36,
        "maximum_physical_sends_total": 400,
        "physical_provider_sends_observed_total": budget.total_sends,
        "unexpected_outbound_http_requests_blocked": budget.blocked_unexpected,
        "provider_attempts_blocked_by_cap": budget.blocked_budget,
        "logical_attribution_mismatch_blocks": ledger.attribution_mismatches,
        "provider_worker_threads_observed": workers.observed,
        "provider_worker_threads_alive_after_drain": workers.alive_after_drain,
        "transport_hooks_restored_after_worker_drain": workers.transport_hooks_restored,
        "apparatus_failure": apparatus_failure,
        "qualification_outcome": outcome,
        "qualification_pass": outcome == "PASS",
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
