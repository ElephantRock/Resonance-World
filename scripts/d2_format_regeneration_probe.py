# ruff: noqa: I001,E501
"""Per-probe execution for #276 bounded format-regeneration qualification."""
from __future__ import annotations

from typing import Any

import d2_format_regeneration_contract as contract
import d2_format_regeneration_transport as transport
from d2_format_regeneration_agent import new_agent

from resonance_world import d2_terminal_adapter as adapter
from resonance_world.provider_send_guard import ProviderSendBudget


def _view(inv: dict[str, Any]) -> dict[str, Any]:
    return {
        "completed": inv["hermes_completed"] if inv["hermes_completed_flag_valid"] else None,
        "failed": inv["hermes_failed"],
        "partial": inv["hermes_partial"],
        "interrupted": inv["hermes_interrupted"],
        "error": "bounded-error-present" if inv["hermes_error_present"] else None,
        "api_calls": inv["api_calls"],
        "final_response": "bounded-nonempty-response-sentinel" if inv["final_response_length"] else "",
    }


def _decision(
    inv: dict[str, Any],
    budget: ProviderSendBudget,
    ledger: transport.TransportLedger,
) -> adapter.TerminalCompletionDecision:
    return adapter.evaluate_terminal_completion(
        _view(inv),
        max_iterations=contract.MAX_ITERATIONS,
        parse_valid=bool(inv["exact_structured_parse_valid"]),
        logical_attribution_integrity=bool(inv["logical_attribution_integrity"]),
        attempts=inv["attempts"],
        physical_sends=int(inv["physical_provider_sends_observed"]),
        unexpected_outbound_blocks=budget.blocked_unexpected,
        provider_budget_blocks=budget.blocked_budget,
        attribution_mismatch_blocks=ledger.attribution_mismatches,
    )


def _compatibility_failure(inv: dict[str, Any]) -> bool:
    attempts = inv.get("attempts") or []
    return bool(
        inv.get("runtime_exception")
        and attempts
        and all(attempt.get("transport_error_type") is None for attempt in attempts)
        and any(attempt.get("http_status") in {400, 404, 409, 415, 422} for attempt in attempts)
    )


def _failure_invocation(exc: BaseException, agent: Any | None) -> dict[str, Any]:
    return {
        "runtime_exception": True,
        "hermes_completed_flag_valid": True,
        "hermes_completed": False,
        "hermes_failed": True,
        "hermes_partial": False,
        "hermes_interrupted": False,
        "hermes_error_present": True,
        "api_calls": int(getattr(agent, "_api_call_count", 0) if agent else 0),
        "result_api_calls": None,
        "final_response_length": 0,
        "final_response_sha256": None,
        "exact_structured_parse_valid": False,
        "structured_parse_valid": False,
        "parse_diagnostic": "no_response_runtime_exception",
        "placeholder_leak": False,
        "strategy_length": 0,
        "strategy_sha256": None,
        **contract.bounded_error(exc),
    }


def _invoke(
    logical: int,
    prompt: str,
    budget: ProviderSendBudget,
    ledger: transport.TransportLedger,
) -> dict[str, Any]:
    before = len(ledger.rows(logical))
    agent: Any | None = None
    try:
        agent = new_agent(logical)
        result = agent.run_conversation(user_message=prompt)
        api_calls = int(getattr(agent, "_api_call_count", 0))
        result_calls = result.get("api_calls")
        if (
            isinstance(result_calls, bool)
            or not isinstance(result_calls, int)
            or result_calls != api_calls
            or not 1 <= api_calls <= contract.MAX_ITERATIONS
        ):
            raise AssertionError("Hermes API-call count drift")
        final = result.get("final_response")
        final_text = final if isinstance(final, str) else ""
        exact_valid, strategy = adapter.parse_response(final_text)
        diagnostic = contract.bounded_parse_diagnostic(final_text)
        leaked = contract.placeholder_leak(final_text)
        if exact_valid != (diagnostic == "exact_valid"):
            raise AssertionError("diagnostic/exact parser consistency drift")
        completed = result.get("completed")
        inv = {
            "runtime_exception": False,
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
            "exact_structured_parse_valid": exact_valid,
            "structured_parse_valid": exact_valid,
            "parse_diagnostic": diagnostic,
            "placeholder_leak": leaked,
            "strategy_length": len(strategy) if exact_valid else 0,
            "strategy_sha256": contract.sha(strategy) if exact_valid and strategy else None,
        }
    except Exception as exc:
        inv = _failure_invocation(exc, agent)

    all_rows = ledger.rows(logical)
    attempts = all_rows[before:]
    attribution = bool(attempts) and all(
        attempt["origin_logical_index"] == logical and attempt["logical_index"] == logical
        for attempt in attempts
    )
    exact_clean = attribution and all(
        attempt.get("http_status") == 200 and attempt.get("transport_error_type") is None
        for attempt in attempts
    )
    inv.update({
        "physical_provider_sends_observed": len(attempts),
        "attempts": attempts,
        "logical_attribution_integrity": attribution,
        "exact_attributed_clean_transport": exact_clean,
    })
    inv["json_mode_compatibility_failure"] = _compatibility_failure(inv)
    decision = _decision(inv, budget, ledger)
    inv.update({
        "effective_completed": decision.effective_completed,
        "terminal_iteration_override_used": decision.terminal_iteration_override_used,
        "adapter_reason": decision.reason,
    })
    return inv


def retry_eligible(
    first: dict[str, Any],
    budget: ProviderSendBudget,
    ledger: transport.TransportLedger,
) -> bool:
    return bool(
        not first["runtime_exception"]
        and first["final_response_length"] > 0
        and not first["exact_structured_parse_valid"]
        and first["exact_attributed_clean_transport"]
        and first["logical_attribution_integrity"]
        and first["hermes_completed_flag_valid"]
        and not first["hermes_failed"]
        and not first["hermes_partial"]
        and not first["hermes_interrupted"]
        and not first["hermes_error_present"]
        and not first["json_mode_compatibility_failure"]
        and budget.blocked_unexpected == 0
        and budget.blocked_budget == 0
        and ledger.attribution_mismatches == 0
    )


def run_probe(
    budget: ProviderSendBudget,
    ledger: transport.TransportLedger,
    probe: dict[str, Any],
) -> dict[str, Any]:
    logical = int(probe["logical_index"])
    primary_prompt = contract.user_prompt(probe)
    row: dict[str, Any] = {
        **probe,
        "primary_prompt_length": len(primary_prompt),
        "primary_prompt_sha256": contract.sha(primary_prompt),
        "retry_used": False,
        "retry_policy_violation": False,
        "retry_raw_first_response_content_included": False,
        "accepted_attempt_index": None,
    }
    with budget.logical_call(logical):
        first = _invoke(logical, primary_prompt, budget, ledger)
        eligible = retry_eligible(first, budget, ledger)
        second: dict[str, Any] | None = None
        retry_prompt: str | None = None
        if eligible:
            try:
                retry_prompt = contract.retry_user_prompt(probe, str(first["parse_diagnostic"]))
                second = _invoke(logical, retry_prompt, budget, ledger)
                row["retry_used"] = True
            except Exception as exc:
                row["retry_policy_violation"] = True
                row["retry_construction_error"] = contract.bounded_error(exc)

    if first["exact_structured_parse_valid"]:
        accepted = first
        row["accepted_attempt_index"] = 1
    elif second is not None and second["exact_structured_parse_valid"]:
        accepted = second
        row["accepted_attempt_index"] = 2
    else:
        accepted = second if second is not None else first

    if row["retry_used"] != eligible:
        row["retry_policy_violation"] = True
    if first["exact_structured_parse_valid"] and row["retry_used"]:
        row["retry_policy_violation"] = True
    if row["retry_used"] and second is None:
        row["retry_policy_violation"] = True

    attempts = ledger.rows(logical)
    sends = budget.sends_for_logical_call(logical)
    attribution = len(attempts) == sends and all(
        attempt["origin_logical_index"] == logical and attempt["logical_index"] == logical
        for attempt in attempts
    )
    exact_clean = attribution and bool(attempts) and all(
        attempt.get("http_status") == 200 and attempt.get("transport_error_type") is None
        for attempt in attempts
    )
    row.update({
        "first_attempt": first,
        "second_attempt": second,
        "retry_eligible_after_first": eligible,
        "retry_prompt_length": len(retry_prompt) if retry_prompt else 0,
        "retry_prompt_sha256": contract.sha(retry_prompt) if retry_prompt else None,
        "agent_invocation_count": 1 + int(second is not None),
        "final_response_length": accepted["final_response_length"],
        "final_response_sha256": accepted["final_response_sha256"],
        "exact_structured_parse_valid": accepted["exact_structured_parse_valid"],
        "structured_parse_valid": accepted["structured_parse_valid"],
        "parse_diagnostic": accepted["parse_diagnostic"],
        "placeholder_leak": accepted["placeholder_leak"],
        "effective_completed": bool(row["accepted_attempt_index"]) and accepted["effective_completed"],
        "hermes_completed": accepted["hermes_completed"],
        "terminal_iteration_override_used": bool(row["accepted_attempt_index"]) and accepted["terminal_iteration_override_used"],
        "adapter_reason": accepted["adapter_reason"],
        "json_mode_compatibility_failure": bool(first["json_mode_compatibility_failure"] or (second and second["json_mode_compatibility_failure"])),
        "physical_provider_sends_observed": sends,
        "attempts": attempts,
        "logical_attribution_integrity": attribution,
        "exact_attributed_clean_transport": exact_clean,
    })
    return row


def apparatus_failure(row: dict[str, Any]) -> bool:
    if row.get("json_mode_compatibility_failure"):
        return False
    invocations = [row.get("first_attempt"), row.get("second_attempt")]
    return bool(
        row.get("retry_policy_violation")
        or row.get("agent_invocation_count", 0) > contract.MAX_AGENT_INVOCATIONS
        or any(inv and inv.get("runtime_exception") for inv in invocations)
        or any(inv and inv.get("hermes_completed_flag_valid") is False for inv in invocations)
        or not row.get("logical_attribution_integrity")
        or not row.get("exact_attributed_clean_transport")
    )
