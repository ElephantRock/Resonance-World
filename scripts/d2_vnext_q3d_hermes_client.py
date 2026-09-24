# ruff: noqa: E501
"""Q3-D structural observability wrapper preserving the frozen Q2 behavior."""
from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import threading
from typing import Any, Callable

import d2_vnext_q2_hermes_client as q2
import d2_vnext_s2_hermes_client as s2
from resonance_world import d2_terminal_adapter as adapter

BASE_URL = q2.BASE_URL
PROVIDER = q2.PROVIDER
API_MODE = q2.API_MODE
MODEL = q2.MODEL
TEMPERATURE = q2.TEMPERATURE
MAX_TOKENS = q2.MAX_TOKENS
MAX_ITERATIONS = q2.MAX_ITERATIONS
MAX_AGENT_INVOCATIONS = q2.MAX_AGENT_INVOCATIONS
MAX_LOGICAL_CALLS_PER_SHARD = 220
MAX_PHYSICAL_SENDS_PER_LOGICAL_CALL = q2.MAX_PHYSICAL_SENDS_PER_LOGICAL_CALL
MAX_PHYSICAL_SENDS_PER_SHARD = 1152
TransportLedger = s2.TransportLedger
ProviderWorkerTracker = s2.ProviderWorkerTracker
guarded_shard_transport = s2.guarded_shard_transport
PARSE_INVALID_TRIGGER = q2.PARSE_INVALID_TRIGGER
CLEAN_EMPTY_TRIGGER = q2.CLEAN_EMPTY_TRIGGER
TERMINAL_FAILURE_MESSAGE = "D2-vNext-Q3-D logical call has no accepted exact completion"
TERMINAL_FAILURE_SHA256 = hashlib.sha256(
    f"RuntimeError:{TERMINAL_FAILURE_MESSAGE}".encode()
).hexdigest()

FORBIDDEN_RAW_KEYS = {
    "raw_response_text",
    "raw_first_response_text",
    "raw_second_response_text",
    "raw_provider_body",
    "prompt_text",
    "retry_prompt_text",
    "final_response",
    "assistant_content",
    "response_body",
    "raw_content",
}


def _sha_text(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _value_snapshot(value: Any) -> dict[str, Any]:
    if value is None:
        return {"present": False, "type": "null", "length": 0, "sha256": None}
    if isinstance(value, str):
        return {
            "present": bool(value),
            "type": "string",
            "length": len(value),
            "sha256": _sha_text(value) if value else None,
        }
    if isinstance(value, list):
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
        return {
            "present": bool(value),
            "type": "list",
            "length": len(value),
            "sha256": _sha_text(encoded) if value else None,
        }
    if isinstance(value, dict):
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
        return {
            "present": bool(value),
            "type": "object",
            "length": len(value),
            "sha256": _sha_text(encoded) if value else None,
        }
    encoded = str(value)
    return {
        "present": True,
        "type": "other",
        "length": len(encoded),
        "sha256": _sha_text(encoded),
    }


def _bounded_content_view(content: Any) -> dict[str, Any]:
    snap = _value_snapshot(content)
    return {
        "assistant_content_present": snap["present"],
        "assistant_content_type": snap["type"],
        "assistant_content_length": snap["length"],
        "assistant_content_sha256": snap["sha256"],
    }


def _transport_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "logical_send_index": int(row["logical_send_index"]),
            "total_send_index": int(row["total_send_index"]),
            "http_status": int(row["http_status"]) if row.get("http_status") is not None else None,
            "transport_error_type": (
                str(row["transport_error_type"])
                if row.get("transport_error_type") is not None
                else None
            ),
        }
        for row in rows
    ]


def provider_completion_view(
    response: Any,
    *,
    agent_invocation_index: int,
    semantic_response_index: int,
    provider_sends: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    choices = list(getattr(response, "choices", []) or [])
    first = choices[0] if choices else None
    message = getattr(first, "message", None) if first is not None else None
    content = getattr(message, "content", None) if message is not None else None
    content_view = _bounded_content_view(content)
    tool_calls = getattr(message, "tool_calls", None) if message is not None else None
    tool_count = len(tool_calls) if isinstance(tool_calls, (list, tuple)) else (1 if tool_calls else 0)
    usage = getattr(response, "usage", None)
    finish_reason = getattr(first, "finish_reason", None) if first is not None else None
    view = {
        "agent_invocation_index": agent_invocation_index,
        "semantic_response_index": semantic_response_index,
        "semantic_response_observed": True,
        "semantic_response_error_type": None,
        "effective_model_if_returned": str(getattr(response, "model", None)) if getattr(response, "model", None) is not None else None,
        "choice_count": len(choices),
        "finish_reason_present": finish_reason is not None,
        "finish_reason": str(finish_reason) if finish_reason is not None else None,
        "assistant_message_present": message is not None,
        **content_view,
        "tool_calls_present": tool_count > 0,
        "tool_calls_count": tool_count,
        "usage_prompt_tokens": int(getattr(usage, "prompt_tokens", 0)) if getattr(usage, "prompt_tokens", None) is not None else None,
        "usage_completion_tokens": int(getattr(usage, "completion_tokens", 0)) if getattr(usage, "completion_tokens", None) is not None else None,
        "usage_total_tokens": int(getattr(usage, "total_tokens", 0)) if getattr(usage, "total_tokens", None) is not None else None,
        "provider_sends": list(provider_sends or []),
    }
    assert_no_raw_content(view)
    return view


def provider_completion_error_view(
    exc: BaseException,
    *,
    agent_invocation_index: int,
    semantic_response_index: int,
    provider_sends: list[dict[str, Any]],
) -> dict[str, Any]:
    view = {
        "agent_invocation_index": agent_invocation_index,
        "semantic_response_index": semantic_response_index,
        "semantic_response_observed": False,
        "semantic_response_error_type": type(exc).__name__,
        "effective_model_if_returned": None,
        "choice_count": None,
        "finish_reason_present": False,
        "finish_reason": None,
        "assistant_message_present": False,
        "assistant_content_present": False,
        "assistant_content_type": "null",
        "assistant_content_length": 0,
        "assistant_content_sha256": None,
        "tool_calls_present": False,
        "tool_calls_count": 0,
        "usage_prompt_tokens": None,
        "usage_completion_tokens": None,
        "usage_total_tokens": None,
        "provider_sends": provider_sends,
    }
    assert_no_raw_content(view)
    return view


class SemanticRecorder:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._rows: list[dict[str, Any]] = []
        self._next_index = 1

    def reserve_index(self) -> int:
        with self._lock:
            value = self._next_index
            self._next_index += 1
            return value

    def append(self, row: dict[str, Any]) -> None:
        with self._lock:
            self._rows.append(copy.deepcopy(row))

    def rows(self) -> list[dict[str, Any]]:
        with self._lock:
            return copy.deepcopy(self._rows)


def instrument_chat_completions(
    agent: Any,
    *,
    agent_invocation_index: int,
    recorder: SemanticRecorder,
    logical_index: int | None = None,
    ledger: TransportLedger | None = None,
) -> Callable[..., Any]:
    """Observe each semantic completion and return the exact original response object."""
    original = agent.client.chat.completions.create

    def wrapped(*args: Any, **kwargs: Any) -> Any:
        semantic_index = recorder.reserve_index()
        before = len(ledger.rows(logical_index)) if ledger is not None and logical_index is not None else 0
        try:
            response = original(*args, **kwargs)
        except Exception as exc:
            rows = ledger.rows(logical_index)[before:] if ledger is not None and logical_index is not None else []
            recorder.append(provider_completion_error_view(exc, agent_invocation_index=agent_invocation_index, semantic_response_index=semantic_index, provider_sends=_transport_rows(rows)))
            raise
        rows = ledger.rows(logical_index)[before:] if ledger is not None and logical_index is not None else []
        recorder.append(provider_completion_view(response, agent_invocation_index=agent_invocation_index, semantic_response_index=semantic_index, provider_sends=_transport_rows(rows)))
        return response

    agent.client.chat.completions.create = wrapped
    return original


def bounded_termination_reason(*, runtime_exception: bool, result: dict[str, Any], api_calls: int, final_text: str) -> str:
    if runtime_exception:
        return "runtime_exception"
    if result.get("failed") is True:
        return "hermes_failed"
    if result.get("partial") is True:
        return "hermes_partial"
    if result.get("interrupted") is True:
        return "hermes_interrupted"
    if bool(result.get("error")):
        return "hermes_error_present"
    if result.get("completed") is True:
        return "hermes_completed"
    if api_calls >= MAX_ITERATIONS:
        return "iteration_budget_exhausted"
    if final_text:
        return "terminal_response_uncompleted"
    return "terminal_empty_uncompleted"


def classify_boundary(*, runtime_exception: bool, provider_semantic: list[dict[str, Any]], hermes_terminal: dict[str, Any], adapter_candidate: dict[str, Any], parse_valid: bool, effective_completed: bool) -> str:
    if runtime_exception:
        return "runtime_or_transport_failure"
    last = provider_semantic[-1] if provider_semantic else None
    if last is None or not last.get("semantic_response_observed") or not bool(last.get("assistant_content_present")):
        return "provider_content_absent"
    if not bool(hermes_terminal.get("present")):
        return "provider_content_present_hermes_terminal_absent"
    if bool(hermes_terminal.get("present")) and not bool(adapter_candidate.get("present")):
        return "hermes_terminal_present_adapter_candidate_absent"
    if bool(adapter_candidate.get("present")) and not parse_valid:
        return "adapter_candidate_nonempty_parse_invalid"
    if parse_valid and effective_completed:
        return "accepted_exact_completion"
    return "unclassified_observability_defect"


def assert_no_raw_content(value: Any) -> None:
    if isinstance(value, dict):
        overlap = FORBIDDEN_RAW_KEYS & set(value)
        if overlap:
            raise AssertionError(f"raw-content field leaked into Q3-D evidence: {sorted(overlap)}")
        for nested in value.values():
            assert_no_raw_content(nested)
    elif isinstance(value, list):
        for nested in value:
            assert_no_raw_content(nested)


def new_shard_budget() -> s2.ProviderSendBudget:
    return s2.ProviderSendBudget(allowed_url_prefix=BASE_URL, maximum_logical_calls=MAX_LOGICAL_CALLS_PER_SHARD, maximum_sends_per_logical_call=MAX_PHYSICAL_SENDS_PER_LOGICAL_CALL, maximum_sends_total=MAX_PHYSICAL_SENDS_PER_SHARD)


def _invoke(logical_index: int, user: str, budget: s2.ProviderSendBudget, ledger: TransportLedger, *, agent_invocation_index: int) -> tuple[dict[str, Any], dict[str, Any] | None]:
    before = len(ledger.rows(logical_index)); agent = None; result: dict[str, Any] = {}; final_value: Any = None; final_text = ""; runtime_exception = False; error_type = None; error_sha256 = None; recorder = SemanticRecorder()
    try:
        agent = s2._new_agent(logical_index)
        instrument_chat_completions(agent, agent_invocation_index=agent_invocation_index, recorder=recorder, logical_index=logical_index, ledger=ledger)
        result = agent.run_conversation(user_message=user)
        final_value = result.get("final_response")
        final_text = final_value if isinstance(final_value, str) else ""
    except Exception as exc:
        runtime_exception = True; error_type = type(exc).__name__; error_sha256 = _sha_text(f"{type(exc).__name__}:{str(exc)[:500]}")
    rows = ledger.rows(logical_index)[before:]
    api_calls = int(getattr(agent, "_api_call_count", 0) if agent is not None else 0)
    completed = result.get("completed"); completed_valid = isinstance(completed, bool)
    diagnostic = s2.bounded_parse_diagnostic(final_text)
    parse_valid, strategy = adapter.parse_response(final_text)
    if parse_valid != (diagnostic == "exact_valid"):
        raise AssertionError("Q3-D exact parser/diagnostic divergence")
    logical_integrity = bool(rows) and all(row.get("origin_logical_index") == logical_index and row.get("logical_index") == logical_index for row in rows)
    view = {"completed": completed if completed_valid else None, "failed": result.get("failed") is True or runtime_exception, "partial": result.get("partial") is True, "interrupted": result.get("interrupted") is True, "error": "bounded-error-present" if (bool(result.get("error")) or runtime_exception) else None, "api_calls": api_calls, "final_response": "bounded-nonempty-response-sentinel" if final_text.strip() else ""}
    decision = adapter.evaluate_terminal_completion(view, max_iterations=MAX_ITERATIONS, parse_valid=parse_valid, logical_attribution_integrity=logical_integrity, attempts=rows, physical_sends=len(rows), unexpected_outbound_blocks=budget.blocked_unexpected, provider_budget_blocks=budget.blocked_budget, attribution_mismatch_blocks=ledger.attribution_mismatches)
    compatibility = s2._compatibility_failure(runtime_exception, rows)
    payload = None
    if parse_valid:
        decoded = json.loads(final_text); payload = {"actions": list(decoded["actions"]), "strategy": decoded.get("strategy")}
    semantic = recorder.rows(); hermes_terminal = _value_snapshot(final_value); adapter_candidate = _value_snapshot(final_text)
    adapter_snapshot = {"candidate_source": "hermes_final_response_after_q2_string_normalization", "candidate_present": adapter_candidate["present"], "candidate_type": adapter_candidate["type"], "candidate_length": adapter_candidate["length"], "candidate_sha256": adapter_candidate["sha256"], "candidate_matches_hermes_terminal": hermes_terminal["type"] == adapter_candidate["type"] and hermes_terminal["length"] == adapter_candidate["length"] and hermes_terminal["sha256"] == adapter_candidate["sha256"], "adapter_reason": decision.reason, "parse_diagnostic": diagnostic, "exact_structured_parse_valid": parse_valid, "accepted_exact_completion": bool(parse_valid and decision.effective_completed)}
    boundary = classify_boundary(runtime_exception=runtime_exception, provider_semantic=semantic, hermes_terminal=hermes_terminal, adapter_candidate=adapter_candidate, parse_valid=parse_valid, effective_completed=decision.effective_completed)
    bounded = {"runtime_exception": runtime_exception, "error_type": error_type, "error_sha256": error_sha256, "hermes_completed_flag_valid": completed_valid, "hermes_completed": completed is True, "hermes_failed": result.get("failed") is True, "hermes_partial": result.get("partial") is True, "hermes_interrupted": result.get("interrupted") is True, "hermes_error_present": bool(result.get("error")), "agent_invocation_index": agent_invocation_index, "api_calls": api_calls, "loop_termination_reason": bounded_termination_reason(runtime_exception=runtime_exception, result=result, api_calls=api_calls, final_text=final_text), "final_response_length": len(final_text), "final_response_sha256": _sha_text(final_text) if final_text else None, "exact_structured_parse_valid": parse_valid, "parse_diagnostic": diagnostic, "physical_provider_sends_observed": len(rows), "attempts": rows, "logical_attribution_integrity": logical_integrity, "exact_attributed_clean_transport": s2._clean_attempts(rows), "json_mode_compatibility_failure": compatibility, "effective_completed": decision.effective_completed, "terminal_iteration_override_used": decision.terminal_iteration_override_used, "adapter_reason": decision.reason, "semantic_completions": semantic, "hermes_terminal": hermes_terminal, "adapter_snapshot": adapter_snapshot, "boundary_classification": boundary}
    assert_no_raw_content({key: value for key, value in bounded.items() if key != "attempts"})
    return bounded, payload


def _public_invocation(attempt: dict[str, Any]) -> dict[str, Any]:
    result = {"agent_invocation_index": int(attempt["agent_invocation_index"]), "api_calls": int(attempt["api_calls"]), "hermes_completed_flag_valid": bool(attempt["hermes_completed_flag_valid"]), "hermes_completed": bool(attempt["hermes_completed"]), "hermes_failed": bool(attempt["hermes_failed"]), "hermes_partial": bool(attempt["hermes_partial"]), "hermes_interrupted": bool(attempt["hermes_interrupted"]), "hermes_error_present": bool(attempt["hermes_error_present"]), "loop_termination_reason": str(attempt["loop_termination_reason"]), "terminal_iteration_override_used": bool(attempt["terminal_iteration_override_used"]), "physical_provider_sends_observed": int(attempt["physical_provider_sends_observed"]), "exact_attributed_clean_transport": bool(attempt["exact_attributed_clean_transport"]), "logical_attribution_integrity": bool(attempt["logical_attribution_integrity"]), "json_mode_compatibility_failure": bool(attempt["json_mode_compatibility_failure"]), "semantic_completions": copy.deepcopy(attempt["semantic_completions"]), "hermes_terminal": copy.deepcopy(attempt["hermes_terminal"]), "adapter_snapshot": copy.deepcopy(attempt["adapter_snapshot"]), "boundary_classification": str(attempt["boundary_classification"])}
    assert_no_raw_content(result); return result


def _observability_defects(invocations: list[dict[str, Any]]) -> list[str]:
    defects: list[str] = []
    for inv in invocations:
        semantic = inv["semantic_completions"]
        if len(semantic) != int(inv["api_calls"]):
            defects.append(f"invocation_{inv['agent_invocation_index']}_semantic_count_mismatch")
        send_total = sum(len(event.get("provider_sends", [])) for event in semantic)
        if send_total != int(inv["physical_provider_sends_observed"]):
            defects.append(f"invocation_{inv['agent_invocation_index']}_transport_association_mismatch")
        if inv["hermes_terminal"]["type"] == "string" and not inv["adapter_snapshot"]["candidate_matches_hermes_terminal"]:
            defects.append(f"invocation_{inv['agent_invocation_index']}_adapter_identity_mismatch")
    return defects


def build_observability_record(*, phase: str, logical_index: int, first: dict[str, Any], trigger: str | None, second: dict[str, Any] | None, accepted_index: int | None) -> dict[str, Any]:
    invocations = [_public_invocation(first)]
    if second is not None:
        invocations.append(_public_invocation(second))
    final_invocation = invocations[-1]
    record = {"schema": "d2-vnext-q3d-structural-observability-record-v0.2", "study_stream": "D2-vNext-Q3-D", "stage": "Q3-D", "arm": phase.split("/", 1)[0], "phase": phase, "logical_call_index": logical_index, "physical_provider_sends_observed": sum(int(inv["physical_provider_sends_observed"]) for inv in invocations), "agent_invocations": invocations, "retry_eligible_after_first": trigger is not None, "retry_trigger_class": trigger, "retry_used": second is not None, "accepted_attempt_index": accepted_index, "accepted_exact_completion": accepted_index is not None, "boundary_classification": "accepted_exact_completion" if accepted_index is not None else final_invocation["boundary_classification"], "observability_defects": _observability_defects(invocations)}
    assert_no_raw_content(record); return record


class Q3DLogicalCallFailure(RuntimeError):
    def __init__(self, evidence: dict[str, Any]) -> None:
        super().__init__(TERMINAL_FAILURE_MESSAGE); self.evidence = evidence


class Client:
    def __init__(self, key: str, budget: s2.ProviderSendBudget, ledger: TransportLedger) -> None:
        if not key.strip():
            raise RuntimeError("ZAI_API_KEY is required")
        if os.environ.get("GLM_BASE_URL", "").rstrip("/") != BASE_URL:
            raise RuntimeError("Coding Plan base URL drift")
        s2._runtime_versions()
        self.budget = budget; self.ledger = ledger; self.logical_calls_started = 0; self.logical_calls_completed = 0; self.logical_call_failures = 0; self.retry_used_count = 0; self.terminal_iteration_override_count = 0; self._counter = 0; self.observability_records: list[dict[str, Any]] = []

    def complete(self, *, phase: str, system: str, user: str, expected_actions: int, temperature: float) -> dict[str, Any]:
        del system
        if expected_actions != 8:
            raise AssertionError("D2-vNext-Q3-D exact action count drift")
        if float(temperature) != TEMPERATURE:
            raise AssertionError("D2-vNext-Q3-D temperature drift")
        logical_index = self._counter; self._counter += 1
        if logical_index >= MAX_LOGICAL_CALLS_PER_SHARD:
            raise RuntimeError("registered logical-call topology exhausted")
        self.logical_calls_started += 1
        prompt_sha256 = hashlib.sha256(s2.canonical_bytes({"system": s2.SYSTEM_PROMPT, "user": user})).hexdigest()
        second = None; second_payload = None; retry_prompt = None; trigger = None; accepted_index: int | None = None
        try:
            with self.budget.logical_call(logical_index):
                first, first_payload = _invoke(logical_index, user, self.budget, self.ledger, agent_invocation_index=1)
                trigger = q2.retry_trigger(first, self.budget, self.ledger)
                if trigger is not None:
                    retry_prompt = q2.retry_user_prompt(user, first, trigger)
                    second, second_payload = _invoke(logical_index, retry_prompt, self.budget, self.ledger, agent_invocation_index=2)
                    self.retry_used_count += 1
            if first["exact_structured_parse_valid"] and first["effective_completed"]:
                accepted_index = 1; accepted = first; payload = first_payload
            elif second is not None and second["exact_structured_parse_valid"] and second["effective_completed"]:
                accepted_index = 2; accepted = second; payload = second_payload
            else:
                obs = build_observability_record(phase=phase, logical_index=logical_index, first=first, trigger=trigger, second=second, accepted_index=None)
                self.observability_records.append(copy.deepcopy(obs)); self.logical_call_failures += 1
                evidence = {"arm": phase.split("/", 1)[0], "phase": phase, "logical_call_index": logical_index, "retry_eligible": trigger is not None, "retry_trigger_class": trigger, "retry_used": second is not None, "accepted_exact_completion": False, "q3d_observability": obs, "terminal_error_type": "RuntimeError", "terminal_error_sha256": TERMINAL_FAILURE_SHA256}
                assert_no_raw_content(evidence); raise Q3DLogicalCallFailure(evidence)
            if payload is None:
                raise AssertionError("accepted exact response payload missing")
            if first["exact_structured_parse_valid"] and second is not None:
                raise AssertionError("valid first response was retried")
            if second is not None and trigger is None:
                raise AssertionError("format-regeneration retry was not eligible")
            if accepted["terminal_iteration_override_used"]:
                self.terminal_iteration_override_count += 1
            all_attempts = self.ledger.rows(logical_index)
            if len(all_attempts) != self.budget.sends_for_logical_call(logical_index):
                raise AssertionError("provider-send ledger/accounting mismatch")
            obs = build_observability_record(phase=phase, logical_index=logical_index, first=first, trigger=trigger, second=second, accepted_index=accepted_index)
            self.observability_records.append(copy.deepcopy(obs)); self.logical_calls_completed += 1
            accepted_semantic = accepted["semantic_completions"]
            effective_model = next((row.get("effective_model_if_returned") for row in reversed(accepted_semantic) if row.get("effective_model_if_returned")), None)
            return {"actions": list(payload["actions"]), "strategy": payload.get("strategy"), "model": MODEL, "effective_model_identity_observed": effective_model is not None, "effective_model": effective_model, "temperature": TEMPERATURE, "thinking": "disabled", "request_id": f"d2-vnext-q3d-{logical_index:04d}-" + re.sub(r"[^a-zA-Z0-9_.-]+", "-", phase)[-72:], "prompt_sha256": prompt_sha256, "response_sha256": accepted["final_response_sha256"], "strategy_present": payload.get("strategy") is not None, "extra_key_count": 0, "attempts": all_attempts, "usage": {}, "total_latency_ms": None, "retry_used": second is not None, "retry_eligible_after_first": trigger is not None, "retry_trigger_class": trigger, "accepted_attempt_index": accepted_index, "agent_invocation_count": 1 + int(second is not None), "first_attempt_api_calls": int(first["api_calls"]), "first_attempt_parse_valid": first["exact_structured_parse_valid"], "first_attempt_parse_diagnostic": first["parse_diagnostic"], "first_attempt_final_response_length": first["final_response_length"], "first_attempt_final_response_sha256": first["final_response_sha256"], "second_attempt_api_calls": int(second["api_calls"]) if second is not None else None, "second_attempt_parse_valid": second["exact_structured_parse_valid"] if second is not None else None, "second_attempt_parse_diagnostic": second["parse_diagnostic"] if second is not None else None, "second_attempt_final_response_length": second["final_response_length"] if second is not None else None, "second_attempt_final_response_sha256": second["final_response_sha256"] if second is not None else None, "retry_prompt_sha256": s2.sha256_text(retry_prompt) if retry_prompt else None, "retry_raw_first_response_content_included": False, "hermes_completed": accepted["hermes_completed"], "terminal_iteration_override_used": accepted["terminal_iteration_override_used"], "adapter_reason": accepted["adapter_reason"], "json_mode_compatibility_failure": bool(first["json_mode_compatibility_failure"] or (second and second["json_mode_compatibility_failure"])), "q3d_observability": obs}
        except Q3DLogicalCallFailure:
            raise
        except Exception:
            if self.logical_calls_completed + self.logical_call_failures < self.logical_calls_started:
                self.logical_call_failures += 1
            raise
