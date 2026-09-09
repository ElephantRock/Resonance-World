"""Future-only structured completion semantics for bounded Hermes calls."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class StructuredCompletionDecision:
    """Outcome of Resonance World's future-only structured completion predicate."""

    accepted: bool
    hermes_completed: bool
    terminal_iteration_override_used: bool
    reason: str


def evaluate_structured_completion(
    result: Mapping[str, Any],
    *,
    max_iterations: int,
    parse_valid: bool,
    logical_attribution_integrity: bool,
    unexpected_outbound_blocks: int,
    provider_budget_blocks: int,
    attribution_mismatch_blocks: int,
    physical_sends: int,
    maximum_physical_sends: int,
) -> StructuredCompletionDecision:
    """Evaluate a bounded Hermes result without changing Hermes' historical semantics.

    A valid response reported as ``completed=False`` may be accepted only when it
    arrived on exactly the terminal registered iteration and every independent
    structured-output and transport guard passes.  The caller must persist whether
    this future-only terminal-iteration override was used.
    """

    if isinstance(max_iterations, bool) or not isinstance(max_iterations, int):
        raise TypeError("max_iterations must be an integer")
    if max_iterations <= 0:
        raise ValueError("max_iterations must be positive")
    if isinstance(maximum_physical_sends, bool) or not isinstance(
        maximum_physical_sends, int
    ):
        raise TypeError("maximum_physical_sends must be an integer")
    if maximum_physical_sends <= 0:
        raise ValueError("maximum_physical_sends must be positive")

    completed = result.get("completed")
    if not isinstance(completed, bool):
        return StructuredCompletionDecision(False, False, False, "completed_flag_invalid")

    final_response = result.get("final_response")
    if not isinstance(final_response, str) or not final_response.strip():
        return StructuredCompletionDecision(False, completed, False, "final_response_empty")
    if not parse_valid:
        return StructuredCompletionDecision(False, completed, False, "structured_parse_invalid")

    if result.get("failed") is True:
        return StructuredCompletionDecision(False, completed, False, "hermes_failed")
    if result.get("partial") is True:
        return StructuredCompletionDecision(False, completed, False, "hermes_partial")
    if result.get("interrupted") is True:
        return StructuredCompletionDecision(False, completed, False, "hermes_interrupted")
    if result.get("error"):
        return StructuredCompletionDecision(False, completed, False, "hermes_error")

    api_calls = result.get("api_calls")
    if isinstance(api_calls, bool) or not isinstance(api_calls, int):
        return StructuredCompletionDecision(False, completed, False, "api_calls_invalid")
    if not 1 <= api_calls <= max_iterations:
        return StructuredCompletionDecision(False, completed, False, "api_calls_out_of_bounds")

    counters = (
        unexpected_outbound_blocks,
        provider_budget_blocks,
        attribution_mismatch_blocks,
    )
    if any(isinstance(value, bool) or not isinstance(value, int) for value in counters):
        return StructuredCompletionDecision(False, completed, False, "transport_counter_invalid")
    if not logical_attribution_integrity:
        return StructuredCompletionDecision(False, completed, False, "attribution_integrity_failed")
    if unexpected_outbound_blocks != 0:
        return StructuredCompletionDecision(False, completed, False, "unexpected_outbound_blocked")
    if provider_budget_blocks != 0:
        return StructuredCompletionDecision(False, completed, False, "provider_budget_blocked")
    if attribution_mismatch_blocks != 0:
        return StructuredCompletionDecision(False, completed, False, "attribution_mismatch")
    if (
        isinstance(physical_sends, bool)
        or not isinstance(physical_sends, int)
        or not 1 <= physical_sends <= maximum_physical_sends
    ):
        return StructuredCompletionDecision(False, completed, False, "physical_sends_out_of_bounds")

    if completed:
        return StructuredCompletionDecision(True, True, False, "hermes_completed")

    if api_calls == max_iterations:
        return StructuredCompletionDecision(
            True,
            False,
            True,
            "valid_terminal_iteration_response",
        )

    return StructuredCompletionDecision(
        False,
        False,
        False,
        "hermes_incomplete_before_terminal_iteration",
    )
