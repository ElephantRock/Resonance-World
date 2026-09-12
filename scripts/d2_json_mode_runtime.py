"""One-shot execution aggregation for #258 JSON-mode conformance."""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import d2_json_mode_contract as contract
import d2_json_mode_transport as transport
from d2_json_mode_agent import new_agent, preflight, request_overrides
from d2_json_mode_probe import apparatus_failure, run_probe
from resonance_world.provider_send_guard import ProviderSendBudget

__all__ = ["execute", "new_agent", "preflight", "request_overrides", "run_probe"]


def parse_marker() -> dict[str, str]:
    if not contract.MARKER.exists():
        raise RuntimeError("authorization marker absent")
    fields = dict(
        line.split("=", 1)
        for line in contract.MARKER.read_text().splitlines()
        if line.strip()
    )
    if set(fields) != {"candidate_sha", "issue", "authorization"}:
        raise RuntimeError("authorization marker invalid")
    if fields["issue"] != str(contract.ISSUE) or fields["authorization"] != contract.AUTH_STRING:
        raise RuntimeError("authorization marker invalid")
    if not re.fullmatch(r"[0-9a-f]{40}", fields["candidate_sha"]):
        raise RuntimeError("candidate SHA invalid")
    return fields


def execute() -> dict[str, Any]:
    contract.assert_execution_environment()
    probes = contract.validate_frozen_contract()
    auth = parse_marker()
    hermes, retries, httpx_version = contract.validate_runtime_versions()
    budget = ProviderSendBudget(
        allowed_url_prefix=contract.BASE_URL,
        maximum_logical_calls=contract.MAX_LOGICAL_CALLS,
        maximum_sends_per_logical_call=contract.MAX_SENDS_PER_LOGICAL,
        maximum_sends_total=contract.MAX_SENDS_TOTAL,
    )
    ledger = transport.TransportLedger()
    workers = transport.ProviderWorkerTracker()
    with budget.propagate_to_child_threads():
        with transport.transport_guard(budget, ledger, workers):
            with ThreadPoolExecutor(max_workers=contract.MAX_CONCURRENCY) as pool:
                rows = list(pool.map(lambda probe: run_probe(budget, ledger, probe), probes))

    attempted = len(rows)
    effective = sum(bool(row["effective_completed"]) for row in rows)
    native = sum(
        bool(row["effective_completed"]) and bool(row["hermes_completed"]) for row in rows
    )
    overrides = sum(bool(row["terminal_iteration_override_used"]) for row in rows)
    structured_invalid = sum(
        bool(row["final_response_length"]) and not bool(row["structured_parse_valid"])
        for row in rows
    )
    compatibility = sum(bool(row["json_mode_compatibility_failure"]) for row in rows)
    global_clean = (
        budget.blocked_unexpected == 0
        and budget.blocked_budget == 0
        and ledger.attribution_mismatches == 0
        and workers.alive_after_drain == 0
        and workers.transport_hooks_restored is True
        and 1 <= budget.total_sends <= contract.MAX_SENDS_TOTAL
    )
    apparatus = any(apparatus_failure(row) for row in rows) or not global_clean
    pass_rule = (
        attempted == effective == contract.MAX_LOGICAL_CALLS
        and all(row["final_response_length"] > 0 for row in rows)
        and all(row["structured_parse_valid"] for row in rows)
        and all(row["exact_attributed_clean_transport"] for row in rows)
        and compatibility == 0
        and not apparatus
    )
    if apparatus:
        outcome = "APPARATUS_FAILURE"
    elif compatibility:
        outcome = "FAIL_JSON_MODE_COMPATIBILITY"
    elif structured_invalid:
        outcome = "FAIL_STRUCTURED_CONTRACT"
    elif pass_rule:
        outcome = "PASS"
    else:
        outcome = "FAIL_COMPLETION"

    return {
        "schema": "d2-json-mode-conformance-result-v0.1",
        "issue": contract.ISSUE,
        "engineering_only": True,
        "candidate_sha": auth["candidate_sha"],
        "fresh_namespace": contract.NAMESPACE,
        "predecessor_issue": 255,
        "predecessor_outcome_unchanged": "FAIL",
        "qualified_terminal_adapter_issue": 251,
        "qualified_terminal_adapter_outcome_unchanged": "PASS",
        "provider": "Z.AI",
        "subscription_product": "GLM Coding Plan",
        "endpoint_base_url": contract.BASE_URL,
        "provider_id": contract.PROVIDER,
        "api_mode": contract.API_MODE,
        "requested_model": contract.MODEL,
        "request_intervention": {"response_format": {"type": "json_object"}},
        "hermes_revision": contract.HERMES_REVISION,
        "hermes_package_version": hermes,
        "hermes_run_agent_blob_sha": contract.HERMES_RUN_AGENT_BLOB_SHA,
        "openai_sdk_version": contract.OPENAI_VERSION,
        "openai_sdk_default_max_retries": retries,
        "httpx_version": httpx_version,
        "max_iterations": contract.MAX_ITERATIONS,
        "max_tokens": contract.MAX_TOKENS,
        "sampling_temperature": contract.TEMPERATURE,
        "thinking": contract.THINKING,
        "terminal_adapter_git_blob_sha": contract.git_blob_sha(contract.ADAPTER_PATH),
        "provider_send_guard_git_blob_sha": contract.git_blob_sha(contract.GUARD_PATH),
        "registered_probe_count": contract.MAX_LOGICAL_CALLS,
        "attempted_probe_count": attempted,
        "effective_completed_count": effective,
        "native_hermes_completed_count": native,
        "terminal_iteration_override_count": overrides,
        "structured_parse_invalid_count": structured_invalid,
        "json_mode_compatibility_failure_count": compatibility,
        "physical_provider_sends_observed_total": budget.total_sends,
        "unexpected_outbound_http_requests_blocked": budget.blocked_unexpected,
        "provider_attempts_blocked_by_cap": budget.blocked_budget,
        "logical_attribution_mismatch_blocks": ledger.attribution_mismatches,
        "provider_worker_threads_observed": workers.observed,
        "provider_worker_threads_alive_after_drain": workers.alive_after_drain,
        "transport_hooks_restored_after_worker_drain": workers.transport_hooks_restored,
        "qualification_outcome": outcome,
        "qualification_pass": outcome == "PASS",
        "apparatus_failure": apparatus,
        "probes": rows,
        "provider_derived_strategy_propagation_performed": False,
        "hermes_completed_mutated": False,
        "scientific_scoring_performed": False,
        "acceptance_action_authorized": False,
        "production_historical_substrate_enabled": False,
        "raw_credentials_persisted": False,
      "raw_provider_response_body_persisted": False,
        "raw_provider_error_body_or_message_persisted": False,
        "raw_final_response_content_persisted": False,
        "same_request_stream_rerun_allowed": False,
    }
