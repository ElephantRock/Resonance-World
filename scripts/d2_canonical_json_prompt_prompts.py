"""Deterministic fresh D2-shaped prompts for #270 canonical-JSON prompt qualification."""
from __future__ import annotations

import json
from typing import Any

from resonance_world import d2_terminal_adapter as adapter

from d2_canonical_json_prompt_spec import NAMESPACE, SYSTEM_PROMPT_SHA256, sha

SYSTEM_PROMPT = (
    'Engineering structured-completion qualification only. Return exactly one JSON object and no surrounding text. '
    'The object MUST contain "actions" as a JSON square-bracket array of exactly 8 strings. '
    'Each array position corresponds to the matching presented case in order. '
    'Never return actions as an object, map, string, keyed per-case record, or scalar. '
    'Each action value must be exactly KAPPA, MICA, ORBIT, or VELA. '
    'Optional "strategy" may be an ASCII string of at most 512 characters. '
    'No other top-level keys are permitted. '
    'Shape example only (not an answer key; do not copy these choices): '
    '{"actions":["KAPPA","MICA","ORBIT","VELA","KAPPA","MICA","ORBIT","VELA"]}. '
    'Choose actions for the actual presented cases. Return JSON only.'
)

def cases(seed: int) -> list[dict[str, int]]:
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
    return [
        {
            "case_id": row["case_id"],
            "chosen_action": adapter.ACTIONS[(seed + 2 * budget + 3 * i) % 4],
            "correct": bool((seed + budget + 2 * i) % 2),
            "bounded_feedback": "structured-completion engineering sentinel only",
        }
        for i, row in enumerate(cases(seed - 2))
    ]

def synthetic_strategy(seed: int, budget: int) -> str:
    return (
        f"canonical-b{budget}-s{seed}; anchor-{adapter.ACTIONS[(seed + 1) % 4].lower()}; "
        f"phase-{seed % 3}; span-{(seed % 19) + 9}; exact-eight-action-json; "
        "no-provider-derived-strategy-propagation"
    )

def system_prompt() -> str:
    if sha(SYSTEM_PROMPT) != SYSTEM_PROMPT_SHA256:
        raise AssertionError("system prompt drift")
    return SYSTEM_PROMPT

def user_prompt(probe: dict[str, Any]) -> str:
    shape = str(probe["call_shape"])
    seed = int(probe["seed"])
    budget = probe["development_budget"]
    sections = [
        (
            "Objective: engineering-only D2 structured-completion sentinel; never scientifically scored.\n"
            f"Fresh namespace: {NAMESPACE}\nProbe: {probe['probe_id']}\n"
            f"Call shape: {shape}\nFresh seed: {seed}"
        ),
        "Task ecology: synthetic integer cases; no hidden scientific policy or answer key.",
    ]
    if shape.startswith("developed_"):
        sections.extend([
            f"Development budget shape: {budget}",
            "Deterministic synthetic strategy context (never provider-derived):\n"
            + synthetic_strategy(seed, int(budget)),
            "Synthetic engineering feedback:\n"
            + json.dumps(feedback(seed, int(budget)), sort_keys=True, separators=(",", ":")),
        ])
    sections.extend([
        "Cases to answer now:\n"
        + json.dumps(cases(seed), sort_keys=True, separators=(",", ":")),
        (
            "Return choices"
            + (" and, if useful, bounded private strategy" if shape == "developed_development" else "")
            + ". No response strategy propagates. Return JSON only."
        ),
    ])
    return "\n\n".join(sections)

def bounded_parse_diagnostic(text: str) -> str:
    """Observe rejection shape without changing exact-parser acceptance."""
    def reject_constant(value: str) -> None:
        raise ValueError(value)
    try:
        payload = json.loads(text, parse_constant=reject_constant)
    except (json.JSONDecodeError, TypeError, ValueError):
        return "json_decode_failure"
    if not isinstance(payload, dict):
        return "top_level_not_object"
    if not set(payload).issubset({"actions", "strategy"}):
        return "extra_keys"
    if "actions" not in payload:
        return "actions_missing"
    actions = payload["actions"]
    if not isinstance(actions, list):
        return "actions_not_list"
    if len(actions) != 8:
        return "wrong_action_count"
    if any(action not in adapter.ACTIONS for action in actions):
        return "invalid_action"
    strategy = payload.get("strategy", "")
    if not isinstance(strategy, str):
        return "strategy_not_string"
    if len(strategy) > adapter.MAX_STRATEGY_CHARS:
        return "strategy_too_long"
    try:
        strategy.encode("ascii")
    except UnicodeEncodeError:
        return "strategy_non_ascii"
    return "exact_valid"
