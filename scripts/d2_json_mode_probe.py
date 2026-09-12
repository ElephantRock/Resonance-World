"""Per-probe execution and classification for #258 JSON-mode conformance."""

from __future__ import annotations

from typing import Any

import d2_json_mode_contract as contract
import d2_json_mode_transport as transport
from d2_json_mode_agent import new_agent

from resonance_world import d2_terminal_adapter as adapter
from resonance_world.provider_send_guard import ProviderSendBudget


def _view(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "completed": row["hermes_completed"] if row["hermes_completed_flag_valid"] else None,
        "failed": row["hermes_failed"],
        "partial": row["hermes_partial"],
        "interrupted": row["hermes_interrupted"],
        "error": "bounded-error-present" if row["hermes_error_present"] else None,
        "api_calls": row["api_calls"],
        "final_response": (
            "bounded-nonempty-response-sentinel"
            if row["final_response_length"]
            else ""
        ),
    }


def _decision(
    row: dict[str, Any],
    budget: ProviderSendBudget,
    ledger: transport.TransportLedger,
) -> adapter.TerminalCompletionDecision:
    return adapter.evaluate_terminal_completion(
        _view(row),
        max_iterations=contract.MAX_ITERATIONS,
        parse_valid=bool(row["structured_parse_valid"]),
        logical_attribution_integrity=bool(row["logical_attribution_integrity"]),
        attempts=row["attempts"],
        physical_sends=int(row["physical_provider_sends_observed"]),
        unexpected_outbound_blocks=budget.blocked_unexpected,
        provider_budget_blocks=budget.blocked_budget,
        attribution_mismatch_blocks=ledger.attribution_mismatches,
    )


def _compatibility_failure(row: dict[str, Any]) -> bool:
    attempts = row.get("attempts") or []
    return bool(
        row.get("runtime_exception")
        and attempts
        and all(attempt.get("transport_error_type") is None for attempt in attempts)
        and any(attempt.get("http_status") in {400, 404, 409, 415, 422} for attempt in attempts)
    )


def _failure_row(row: dict[str, Any], agent: Any | None, exc: BaseException) -> None:
    row.update(
        {
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
            "structured_parse_valid": False,
            "parse_diagnostic": "no_response_runtime_exception",
            "strategy_length": 0,
            "strategy_sha256": None,
            **contract.bounded_error(exc),
        }
    )


def run_probe(
    budget: ProviderSendBudget,
    ledger: transport.TransportLedger,
    probe: dict[str, Any],
) -> dict[str, Any]:
    logical = int(probe["logical_index"])
    prompt = contract.user_prompt(probe)
    row: dict[str, Any] = {
        **probe,
        "prompt_length": len(prompt),
        "prompt_sha256": contract.sha(prompt),
        "runtime_exception": False,
    }
    agent: Any | None = None
    try:
        with budget.logical_call(logical):
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
        valid, strategy = adapter.parse_response(final_text)
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
                "structured_parse_valid": valid,
                "parse_diagnostic": contract.parse_diagnostic(final_text),
                "strategy_length": len(strategy) if valid else 0,
                "strategy_sha256": contract.sha(strategy) if valid and strategy else None,
            }
        )
    except Exception as exc:
        _failure_row(row, agent, exc)

    attempts = ledger.rows(logical)
    sends = budget.sends_for_logical_call(logical)
    attribution = len(attempts) == sends and all(
        attempt["origin_logical_index"] == logical
        and attempt["logical_index"] == logical
        for attempt in attempts
    )
    exact_clean = attribution and bool(attempts) and all(
        attempt.get("http_status") == 200
        and attempt.get("transport_error_type") is None
        for attempt in attempts
    )
    row.update(
        {
            "physical_provider_sends_observed": sends,
            "attempts": attempts,
            "logical_attribution_integrity": attribution,
            "exact_attributed_clean_transport": exact_clean,
        }
    )
    row["json_mode_compatibility_failure"] = _compatibility_failure(row)
    decision = _decision(row, budget, ledger)
    row.update(
        {
            "effective_completed": decision.effective_completed,
            "terminal_iteration_override_used": decision.terminal_iteration_override_used,
            "adapter_reason": decision.reason,
        }
    )
    return row


def apparatus_failure(row: dict[str, Any]) -> bool:
    if row.get("json_mode_compatibility_failure"):
        return False
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
