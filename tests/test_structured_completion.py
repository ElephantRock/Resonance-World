from __future__ import annotations

import pytest

from resonance_world.structured_completion import evaluate_structured_completion


def _result(**overrides: object) -> dict[str, object]:
    result: dict[str, object] = {
        "final_response": '{"actions":["KAPPA","MICA","ORBIT","VELA","KAPPA","MICA","ORBIT","VELA"]}',
        "completed": True,
        "failed": False,
        "partial": False,
        "interrupted": False,
        "api_calls": 1,
    }
    result.update(overrides)
    return result


def _decide(result: dict[str, object], **overrides: object):
    kwargs: dict[str, object] = {
        "max_iterations": 2,
        "parse_valid": True,
        "logical_attribution_integrity": True,
        "unexpected_outbound_blocks": 0,
        "provider_budget_blocks": 0,
        "attribution_mismatch_blocks": 0,
        "physical_sends": 1,
        "maximum_physical_sends": 36,
    }
    kwargs.update(overrides)
    return evaluate_structured_completion(result, **kwargs)


def test_normal_hermes_completion_is_accepted_without_override() -> None:
    decision = _decide(_result())
    assert decision.accepted is True
    assert decision.hermes_completed is True
    assert decision.terminal_iteration_override_used is False


def test_valid_terminal_iteration_completion_is_accepted_with_explicit_override() -> None:
    decision = _decide(_result(completed=False, api_calls=2), physical_sends=2)
    assert decision.accepted is True
    assert decision.hermes_completed is False
    assert decision.terminal_iteration_override_used is True
    assert decision.reason == "valid_terminal_iteration_response"


def test_hermes_incomplete_before_terminal_iteration_is_rejected() -> None:
    decision = _decide(_result(completed=False, api_calls=1))
    assert decision.accepted is False
    assert decision.reason == "hermes_incomplete_before_terminal_iteration"


@pytest.mark.parametrize(
    ("result_override", "decision_override", "reason"),
    [
        ({"final_response": ""}, {}, "final_response_empty"),
        ({}, {"parse_valid": False}, "structured_parse_invalid"),
        ({"failed": True}, {}, "hermes_failed"),
        ({"partial": True}, {}, "hermes_partial"),
        ({"interrupted": True}, {}, "hermes_interrupted"),
        ({"error": "bounded"}, {}, "hermes_error"),
        ({"api_calls": 0}, {}, "api_calls_out_of_bounds"),
        ({"api_calls": 3}, {}, "api_calls_out_of_bounds"),
        ({}, {"logical_attribution_integrity": False}, "attribution_integrity_failed"),
        ({}, {"unexpected_outbound_blocks": 1}, "unexpected_outbound_blocked"),
        ({}, {"provider_budget_blocks": 1}, "provider_budget_blocked"),
        ({}, {"attribution_mismatch_blocks": 1}, "attribution_mismatch"),
        ({}, {"physical_sends": 0}, "physical_sends_out_of_bounds"),
        ({}, {"physical_sends": 37}, "physical_sends_out_of_bounds"),
    ],
)
def test_fail_closed_conditions(
    result_override: dict[str, object],
    decision_override: dict[str, object],
    reason: str,
) -> None:
    decision = _decide(_result(**result_override), **decision_override)
    assert decision.accepted is False
    assert decision.terminal_iteration_override_used is False
    assert decision.reason == reason


def test_completed_flag_must_be_boolean() -> None:
    decision = _decide(_result(completed=None))
    assert decision.accepted is False
    assert decision.reason == "completed_flag_invalid"


def test_counter_types_fail_closed() -> None:
    decision = _decide(_result(), provider_budget_blocks=True)
    assert decision.accepted is False
    assert decision.reason == "transport_counter_invalid"


def test_bounds_configuration_is_validated() -> None:
    with pytest.raises(ValueError, match="max_iterations"):
        _decide(_result(), max_iterations=0)
    with pytest.raises(ValueError, match="maximum_physical_sends"):
        _decide(_result(), maximum_physical_sends=0)
