"""Pure contract helpers for D2 terminal-response observability."""

from __future__ import annotations

import json
from collections import Counter
from typing import Any

ACTIONS = ("KAPPA", "MICA", "ORBIT", "VELA")
ALLOWED_BUDGETS = (40, 80, 160)
PROBE_COUNT = 72
MAX_STRATEGY_CHARS = 512


def validate_probes(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Validate the prospectively frozen fresh-probe manifest."""

    if payload.get("schema") != "d2-terminal-response-observability-probes-v0.1":
        raise AssertionError("probe schema drift")
    if payload.get("issue") != 243:
        raise AssertionError("probe issue drift")
    if payload.get("seed_namespace") != "rw.d2-terminal-observability.v1":
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
        if isinstance(seed, bool) or not isinstance(seed, int) or seed < 900000:
            raise AssertionError("probe seed drift")
        if not isinstance(probe_id, str) or not probe_id.startswith(f"obs_b{budget}_"):
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
            "f0": (seed + 3 * i) % 11 - 5,
            "f1": (2 * seed + 5 * i) % 13 - 6,
            "f2": (3 * seed + 7 * i) % 17 - 8,
            "f3": (5 * seed + 11 * i) % 19 - 9,
        }
        for i in range(8)
    ]


def feedback(seed: int, budget: int) -> list[dict[str, Any]]:
    """Create synthetic feedback with no hidden scientific truth."""

    rows = cases(seed - 1)
    return [
        {
            "case_id": row["case_id"],
            "chosen_action": ACTIONS[(seed + budget + i) % len(ACTIONS)],
            "correct": bool((seed + budget + i) % 2),
            "bounded_feedback": "engineering sentinel feedback only",
        }
        for i, row in enumerate(rows)
    ]


def synthetic_prior_strategy(seed: int, budget: int) -> str:
    """Produce a deterministic fresh strategy-like context, never provider-derived."""

    parts = [
        f"b{budget}-s{seed}",
        f"rotate-{ACTIONS[seed % 4].lower()}",
        f"parity-{seed % 2}",
        f"span-{(seed % 17) + 8}",
        "prefer-consistent-eight-action-json",
        "treat-feedback-as-synthetic-engineering-context",
    ]
    return "; ".join(parts)


def system_prompt() -> str:
    """Return the exact bounded structured-output contract."""

    return (
        "Engineering transport diagnostic only. Return exactly one JSON object with "
        "an actions array containing exactly 8 entries, each one of KAPPA, MICA, "
        "ORBIT, VELA. You may also include strategy as an ASCII string of at most "
        f"{MAX_STRATEGY_CHARS} characters. Do not include other keys, markdown, tools, "
        "browsing, external information, or scientific claims."
    )


def user_prompt(probe: dict[str, Any]) -> str:
    """Materialize one fresh realistic D2-shaped development prompt."""

    seed = int(probe["seed"])
    budget = int(probe["development_budget"])
    sections = [
        "Objective: fresh engineering-only D2-shaped developed-development completion "
        "sentinel; the response is never scientifically scored.",
        f"Fresh probe: {probe['probe_id']}",
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


def is_valid_terminal_observation(
    *,
    api_calls: int,
    hermes_completed: bool,
    hermes_failed: bool,
    hermes_partial: bool,
    hermes_interrupted: bool,
    hermes_error_present: bool,
    final_nonempty: bool,
    parse_valid: bool,
    attribution_integrity: bool,
    unexpected_outbound_blocks: int,
    provider_budget_blocks: int,
    attribution_mismatch_blocks: int,
) -> bool:
    """Apply the prospectively frozen observational predicate."""

    return (
        api_calls == 2
        and hermes_completed is False
        and hermes_failed is False
        and hermes_partial is False
        and hermes_interrupted is False
        and hermes_error_present is False
        and final_nonempty
        and parse_valid
        and attribution_integrity
        and unexpected_outbound_blocks == 0
        and provider_budget_blocks == 0
        and attribution_mismatch_blocks == 0
    )
