# ruff: noqa: I001,E501
"""Deterministic fresh D2-shaped prompts for #276 format-regeneration qualification."""
from __future__ import annotations

import json
from typing import Any

from resonance_world import d2_terminal_adapter as adapter

from d2_format_regeneration_spec import NAMESPACE, SYSTEM_PROMPT_SHA256, sha

SYSTEM_PROMPT = 'Engineering structured-completion qualification only. Return exactly one JSON object and no surrounding text. The object MUST contain "actions" as a JSON square-bracket array of exactly 8 strings. Each array position corresponds to the matching presented case in order. Never return actions as an object, map, string, keyed per-case record, or scalar. Each action value must be exactly KAPPA, MICA, ORBIT, or VELA. Optional "strategy" may be an ASCII string of at most 512 characters. No other top-level keys are permitted. Use this non-answer positional JSON skeleton only as syntax/position guidance: {"actions":["<ACTION_1>","<ACTION_2>","<ACTION_3>","<ACTION_4>","<ACTION_5>","<ACTION_6>","<ACTION_7>","<ACTION_8>"]}. Replace every <ACTION_n> placeholder with one allowed action for the corresponding actual case; never emit placeholder text. Before emitting, silently verify: valid JSON object; only actions and optional strategy; actions is an array of exactly 8 allowed strings; no placeholder remains; no surrounding prose, Markdown, or fences. Return JSON only.'


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
        f"regeneration-b{budget}-s{seed}; anchor-{adapter.ACTIONS[(seed + 1) % 4].lower()}; "
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


def retry_user_prompt(probe: dict[str, Any], diagnostic: str) -> str:
    if diagnostic not in {
        "json_decode_failure", "top_level_not_object", "extra_keys", "actions_missing",
        "actions_not_list", "wrong_action_count", "invalid_action", "strategy_not_string",
        "strategy_too_long", "strategy_non_ascii",
    }:
        raise ValueError("retry diagnostic not eligible")
    return (
        user_prompt(probe)
        + "\n\nFormat-regeneration attempt: the prior attempt was rejected by the unchanged exact parser "
        + f"with bounded diagnostic class {diagnostic}. Raw prior response content is not provided and must not be inferred, reconstructed, or repaired. "
        + "Generate a new answer independently for the original cases. Re-check the required non-answer positional JSON skeleton contract silently before emitting. Return JSON only."
    )


def placeholder_leak(text: str) -> bool:
    return "<ACTION_" in text


def bounded_parse_diagnostic(text: str) -> str:
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
