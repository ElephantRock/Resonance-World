"""Future-only terminal structured-completion adapter for bounded D2-shaped calls."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

ACTIONS = ("KAPPA", "MICA", "ORBIT", "VELA")
ALLOWED_BUDGETS = (40, 80, 160)
PROBE_COUNT = 72
MAX_STRATEGY_CHARS = 512


@dataclass(frozen=True, slots=True)
class TerminalCompletionDecision:
    """Preserve native Hermes completion and derive a separate effective decision."""

    effective_completed: bool
    hermes_completed: bool
    terminal_iteration_override_used: bool
    reason: str


def validate_probes(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Validate the prospectively frozen fresh-probe manifest."""

    if payload.get("schema") != "d2-terminal-adapter-probes-v0.1":
        raise AssertionError("probe schema drift")
    if payload.get("issue") != 246:
        raise AssertionError("probe issue drift")
    if payload.get("seed_namespace") != "rw.d2-terminal-adapter.v1":
        raise AssertionError("probe seed namespace drift")
    probes = payload.get("probes")
    if not isinstance(probes, list) or len(probes) != PROBE_COUNT:
        raise AssertionError("probe count drift")

    budgets: Counter[int] = Counter()
    seen_ids: set[str] = set()
    seen_seeds: set[int] = set()
    for index, probe in enumerate(probes):
        if not isinstance(probe, dict):
            raise AssertionError("probe row type drift")
        if set(probe) != {"development_budget", "logical_index", "probe_id", "seed"}:
            raise AssertionError("probe row keys drift")
        budget = probe["development_budget"]
        seed = probe["seed"]
        probe_id = probe["probe_id"]
        if probe["logical_index"] != index:
            raise AssertionError("probe logical index drift")
        if budget not in ALLOWED_BUDGETS:
            raise AssertionError("probe budget drift")
        if isinstance(seed, bool) or not isinstance(seed, int) or seed < 1_000_000:
            raise AssertionError("probe seed drift")
        if not isinstance(probe_id, str) or not probe_id.startswith(f"adapter_b{budget}_"):
            raise AssertionError("probe id drift")
        if probe_id in seen_ids or seed in seen_seeds:
            raise AssertionError("probe identity reuse")
        seen_ids.add(probe_id)
        seen_seeds.add(seed)
        budgets[budget] += 1

    if budgets != Counter({40: 24, 80: 24, 160: 24}):
        raise AssertionError("probe budget balance drift")
    return probes


def cases(seed: int) -> list[dict[str, int]]:
    """Materialize eight deterministic synthetic engineering cases."""

    return [
        {
            "case_id": seed * 100 + i,
            "f0": (seed + 5 * i) % 13 - 6,
            "f1": (2 * seed + 7 * i) % 17 - 8,
            "f2": (3 * seed + 11 * i) % 19 - 9,
            "f3": (7 * seed + 13 * i) % 23 - 11,
        }
        for i in range(8)
    ]


def feedback(seed: int, budget: int) -> list[dict[str, Any]]:
    """Create fresh synthetic feedback with no hidden scientific truth."""

    rows = cases(seed - 2)
    return [
        {
            "case_id": row["case_id"],
            "chosen_action": ACTIONS[(seed + 2 * budget + 3 * i) % len(ACTIONS)],
            "correct": bool((seed + budget + 2 * i) % 2),
            "bounded_feedback": "future-adapter engineering sentinel only",
        }
        for i, row in enumerate(rows)
    ]


def synthetic_prior_strategy(seed: int, budget: int) -> str:
    """Produce deterministic fresh strategy-like context, never provider-derived."""

    parts = [
        f"adapter-b{budget}-s{seed}",
        f"anchor-{ACTIONS[(seed + 1) % 4].lower()}",
        f"phase-{seed % 3}",
        f"span-{(seed % 19) + 9}",
        "prefer-exact-eight-action-json",
        "treat-feedback-as-nonscientific-adapter-context",
    ]
    return "; ".join(parts)


def system_prompt() -> str:
    """Return the exact bounded structured-output contract."""

    return (
        "Engineering completion-adapter qualification only. Return exactly one JSON "
        "object with an actions array containing exactly 8 entries, each one of "
        "KAPPA, MICA, ORBIT, VELA. You may also include strategy as an ASCII string "
        f"of at most {MAX_STRATEGY_CHARS} characters. Do not include other keys, "
        "markdown, tools, browsing, external information, or scientific claims."
    )


def user_prompt(probe: dict[str, Any]) -> str:
    """Materialize one fresh realistic D2-shaped development prompt."""

    seed = int(probe["seed"])
    budget = int(probe["development_budget"])
    sections = [
        "Objective: fresh engineering-only D2-shaped developed-development completion "
        "adapter sentinel; the response is never scientifically scored.",
        f"Fresh adapter probe: {probe['probe_id']}",
        f"Development budget shape: {budget}",
        "Task ecology: synthetic four-feature integer cases with no hidden scientific "
        "policy or answer key.",
        "Prior private strategy (deterministic synthetic context, not provider-derived):\n"
        + synthetic_prior_strategy(seed, budget),
        "Outcome-bearing local feedback (synthetic engineering sentinel only):\n"
        + json.dumps(feedback(seed, budget), sort_keys=True, separators=(",", ":")),
        "Cases to answer now:\n"
        + json.dumps(cases(seed), sort_keys=True, separators=(",", ":")),
        "Return choices and, if useful, an updated bounded private strategy. The feedback "
        "carries no scientific truth. Return JSON only.",
    ]
    return "\n\n".join(sections)


def parse_response(text: str) -> tuple[bool, str]:
    """Parse the exact eight-action contract and return bounded strategy text."""

    def reject_constant(value: str) -> None:
        raise ValueError(f"non-standard JSON constant prohibited: {value}")

    try:
        payload = json.loads(text, parse_constant=reject_constant)
    except (json.JSONDecodeError, TypeError, ValueError):
        return False, ""
    if not isinstance(payload, dict) or not set(payload).issubset({"actions", "strategy"}):
        return False, ""
    actions = payload.get("actions")
    if (
        not isinstance(actions, list)
        or len(actions) != 8
        or any(action not in ACTIONS for action in actions)
    ):
        return False, ""
    strategy = payload.get("strategy", "")
    if not isinstance(strategy, str) or len(strategy) > MAX_STRATEGY_CHARS:
        return False, ""
    try:
        strategy.encode("ascii")
    except UnicodeEncodeError:
        return False, ""
    return True, strategy


def _clean_attempts(
    attempts: Sequence[Mapping[str, Any]],
    *,
    api_calls: int,
    physical_sends: int,
) -> bool:
    """Require one clean HTTP-200 physical send for each Hermes API/model call."""

    if physical_sends != api_calls or len(attempts) != api_calls:
        return False
    return all(
        attempt.get("http_status") == 200
        and attempt.get("transport_error_type") is None
        for attempt in attempts
    )


def evaluate_terminal_completion(
    result: Mapping[str, Any],
    *,
    max_iterations: int,
    parse_valid: bool,
    logical_attribution_integrity: bool,
    attempts: Sequence[Mapping[str, Any]],
    physical_sends: int,
    unexpected_outbound_blocks: int,
    provider_budget_blocks: int,
    attribution_mismatch_blocks: int,
) -> TerminalCompletionDecision:
    """Derive effective completion without mutating Hermes' native completion semantics."""

    completed = result.get("completed")
    if not isinstance(completed, bool):
        return TerminalCompletionDecision(False, False, False, "completed_flag_invalid")
    if max_iterations != 2:
        return TerminalCompletionDecision(False, completed, False, "max_iterations_not_two")

    final_response = result.get("final_response")
    if not isinstance(final_response, str) or not final_response.strip():
        return TerminalCompletionDecision(False, completed, False, "final_response_empty")
    if not parse_valid:
        return TerminalCompletionDecision(False, completed, False, "structured_parse_invalid")
    if result.get("failed") is True:
        return TerminalCompletionDecision(False, completed, False, "hermes_failed")
    if result.get("partial") is True:
        return TerminalCompletionDecision(False, completed, False, "hermes_partial")
    if result.get("interrupted") is True:
        return TerminalCompletionDecision(False, completed, False, "hermes_interrupted")
    if result.get("error"):
        return TerminalCompletionDecision(False, completed, False, "hermes_error")

    api_calls = result.get("api_calls")
    if isinstance(api_calls, bool) or not isinstance(api_calls, int):
        return TerminalCompletionDecision(False, completed, False, "api_calls_invalid")
    if not 1 <= api_calls <= max_iterations:
        return TerminalCompletionDecision(False, completed, False, "api_calls_out_of_bounds")

    counters = (
        unexpected_outbound_blocks,
        provider_budget_blocks,
        attribution_mismatch_blocks,
    )
    if any(isinstance(value, bool) or not isinstance(value, int) for value in counters):
        return TerminalCompletionDecision(False, completed, False, "transport_counter_invalid")
    if not logical_attribution_integrity:
        return TerminalCompletionDecision(False, completed, False, "attribution_integrity_failed")
    if unexpected_outbound_blocks != 0:
        return TerminalCompletionDecision(False, completed, False, "unexpected_outbound_blocked")
    if provider_budget_blocks != 0:
        return TerminalCompletionDecision(False, completed, False, "provider_budget_blocked")
    if attribution_mismatch_blocks != 0:
        return TerminalCompletionDecision(False, completed, False, "attribution_mismatch")
    if isinstance(physical_sends, bool) or not isinstance(physical_sends, int):
        return TerminalCompletionDecision(False, completed, False, "physical_sends_invalid")
    if not _clean_attempts(attempts, api_calls=api_calls, physical_sends=physical_sends):
        return TerminalCompletionDecision(False, completed, False, "transport_not_exact_clean")

    if completed:
        if api_calls >= max_iterations:
            return TerminalCompletionDecision(False, True, False, "native_completion_count_inconsistent")
        return TerminalCompletionDecision(True, True, False, "hermes_completed")

    if api_calls == max_iterations:
        return TerminalCompletionDecision(
            True,
            False,
            True,
            "valid_terminal_iteration_response",
        )

    return TerminalCompletionDecision(
        False,
        False,
        False,
        "hermes_incomplete_before_terminal_iteration",
    )
