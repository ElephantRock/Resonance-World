from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import d2_vnext_q1_hermes_client as q1
import pytest


class FakeLedger:
    def __init__(self) -> None:
        self.data: dict[int, list[dict[str, Any]]] = {}
        self.attribution_mismatches = 0

    def rows(self, logical_index: int) -> list[dict[str, Any]]:
        return list(self.data.get(logical_index, []))

    def append_clean(self, logical_index: int) -> None:
        rows = self.data.setdefault(logical_index, [])
        rows.append(
            {
                "origin_logical_index": logical_index,
                "logical_index": logical_index,
                "logical_send_index": len(rows) + 1,
                "total_send_index": sum(len(value) for value in self.data.values()) + 1,
                "http_status": 200,
                "transport_error_type": None,
            }
        )


class FakeBudget:
    def __init__(self, ledger: FakeLedger) -> None:
        self.ledger = ledger
        self.blocked_unexpected = 0
        self.blocked_budget = 0

    @contextmanager
    def logical_call(self, logical_index: int) -> Iterator[None]:
        yield

    def sends_for_logical_call(self, logical_index: int) -> int:
        return len(self.ledger.rows(logical_index))


def bounded_attempt(
    *,
    parse_valid: bool,
    effective_completed: bool,
    diagnostic: str,
    runtime_exception: bool = False,
    adapter_reason: str = "fixture",
    transport_clean: bool = True,
) -> dict[str, Any]:
    return {
        "runtime_exception": runtime_exception,
        "error_type": "RuntimeError" if runtime_exception else None,
        "error_sha256": "e" * 64 if runtime_exception else None,
        "hermes_completed_flag_valid": True,
        "hermes_completed": effective_completed,
        "hermes_failed": runtime_exception,
        "hermes_partial": False,
        "hermes_interrupted": False,
        "hermes_error_present": runtime_exception,
        "api_calls": 1,
        "final_response_length": 8 if not runtime_exception else 0,
        "final_response_sha256": "f" * 64 if not runtime_exception else None,
        "exact_structured_parse_valid": parse_valid,
        "parse_diagnostic": diagnostic,
        "placeholder_leak": False,
        "strategy_length": 0,
        "strategy_sha256": None,
        "physical_provider_sends_observed": 1,
        "attempts": [],
        "logical_attribution_integrity": transport_clean,
        "exact_attributed_clean_transport": transport_clean,
        "json_mode_compatibility_failure": False,
        "effective_completed": effective_completed,
        "terminal_iteration_override_used": False,
        "adapter_reason": adapter_reason,
    }


def make_client() -> tuple[q1.Client, FakeLedger, FakeBudget]:
    ledger = FakeLedger()
    budget = FakeBudget(ledger)
    client = q1.Client.__new__(q1.Client)
    client.budget = budget
    client.ledger = ledger
    client.logical_calls_started = 0
    client.logical_calls_completed = 0
    client.logical_call_failures = 0
    client.retry_used_count = 0
    client.terminal_iteration_override_count = 0
    client._counter = 0
    return client, ledger, budget


def install_sequence(
    monkeypatch: pytest.MonkeyPatch,
    ledger: FakeLedger,
    sequence: list[tuple[dict[str, Any], dict[str, Any] | None]],
) -> None:
    values = iter(sequence)

    def fake_invoke(logical_index: int, user: str, budget: Any, target_ledger: Any):
        del user, budget, target_ledger
        ledger.append_clean(logical_index)
        return next(values)

    monkeypatch.setattr(q1.s2, "_invoke", fake_invoke)


def call(client: q1.Client) -> dict[str, Any]:
    return client.complete(
        phase="fresh/evaluation1",
        system="ignored",
        user="fixture user prompt",
        expected_actions=8,
        temperature=0.8,
    )


def test_clean_first_attempt_exact_completion(monkeypatch: pytest.MonkeyPatch) -> None:
    client, ledger, _ = make_client()
    first = bounded_attempt(
        parse_valid=True,
        effective_completed=True,
        diagnostic="exact_valid",
    )
    payload = {"actions": ["KAPPA"] * 8, "strategy": None}
    install_sequence(monkeypatch, ledger, [(first, payload)])
    result = call(client)
    assert result["accepted_attempt_index"] == 1
    assert result["retry_used"] is False
    assert client.logical_calls_completed == 1


def test_retry_eligible_parse_failure_then_success(monkeypatch: pytest.MonkeyPatch) -> None:
    client, ledger, _ = make_client()
    first = bounded_attempt(
        parse_valid=False,
        effective_completed=False,
        diagnostic="json_decode_failure",
    )
    second = bounded_attempt(
        parse_valid=True,
        effective_completed=True,
        diagnostic="exact_valid",
    )
    payload = {"actions": ["MICA"] * 8, "strategy": "fixture"}
    install_sequence(monkeypatch, ledger, [(first, None), (second, payload)])
    result = call(client)
    assert result["accepted_attempt_index"] == 2
    assert result["retry_used"] is True
    assert result["retry_raw_first_response_content_included"] is False
    assert client.retry_used_count == 1


def test_retry_failure_preserves_bounded_second_attempt(monkeypatch: pytest.MonkeyPatch) -> None:
    client, ledger, _ = make_client()
    first = bounded_attempt(
        parse_valid=False,
        effective_completed=False,
        diagnostic="json_decode_failure",
    )
    second = bounded_attempt(
        parse_valid=False,
        effective_completed=False,
        diagnostic="wrong_action_count",
    )
    install_sequence(monkeypatch, ledger, [(first, None), (second, None)])
    with pytest.raises(q1.Q1LogicalCallFailure) as caught:
        call(client)
    evidence = caught.value.evidence
    assert evidence["retry_used"] is True
    assert evidence["second_attempt"]["parse_diagnostic"] == "wrong_action_count"
    q1.assert_failure_evidence_has_no_raw_content(evidence)


def test_terminal_adapter_rejection_is_located_without_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, ledger, _ = make_client()
    first = bounded_attempt(
        parse_valid=True,
        effective_completed=False,
        diagnostic="exact_valid",
        adapter_reason="terminal_completion_rejected_fixture",
    )
    payload = {"actions": ["ORBIT"] * 8, "strategy": None}
    install_sequence(monkeypatch, ledger, [(first, payload)])
    with pytest.raises(q1.Q1LogicalCallFailure) as caught:
        call(client)
    evidence = caught.value.evidence
    assert evidence["retry_eligible"] is False
    assert evidence["first_attempt"]["exact_structured_parse_valid"] is True
    assert evidence["first_attempt"]["adapter_reason"] == "terminal_completion_rejected_fixture"


def test_runtime_exception_is_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    client, ledger, _ = make_client()
    first = bounded_attempt(
        parse_valid=False,
        effective_completed=False,
        diagnostic="json_decode_failure",
        runtime_exception=True,
    )
    install_sequence(monkeypatch, ledger, [(first, None)])
    with pytest.raises(q1.Q1LogicalCallFailure) as caught:
        call(client)
    assert caught.value.evidence["first_attempt"]["runtime_exception"] is True
    q1.assert_failure_evidence_has_no_raw_content(caught.value.evidence)


def test_budget_or_attribution_defect_prevents_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    client, ledger, budget = make_client()
    budget.blocked_budget = 1
    ledger.attribution_mismatches = 1
    first = bounded_attempt(
        parse_valid=False,
        effective_completed=False,
        diagnostic="json_decode_failure",
        transport_clean=False,
    )
    install_sequence(monkeypatch, ledger, [(first, None)])
    with pytest.raises(q1.Q1LogicalCallFailure) as caught:
        call(client)
    evidence = caught.value.evidence
    assert evidence["retry_eligible"] is False
    assert evidence["retry_used"] is False
    assert evidence["first_attempt"]["logical_attribution_integrity"] is False
