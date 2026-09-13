"""Bounded unknown-top-level-key projection for D2 structured completion."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from resonance_world import d2_terminal_adapter as exact_adapter

RECOGNIZED_TOP_LEVEL_KEYS = frozenset({"actions", "strategy"})


@dataclass(frozen=True, slots=True)
class ProjectionParseResult:
    valid: bool
    strategy: str
    exact_parse_valid: bool
    projection_used: bool
    unknown_key_count: int
    unknown_key_fingerprints: tuple[str, ...]
    diagnostic: str


def _fingerprint(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def _decode(text: str) -> tuple[dict[str, Any] | None, str | None]:
    def reject_constant(value: str) -> None:
        raise ValueError(f"non-standard JSON constant prohibited: {value}")

    try:
        payload = json.loads(text, parse_constant=reject_constant)
    except (json.JSONDecodeError, TypeError, ValueError):
        return None, "json_decode_failure"
    if not isinstance(payload, dict):
        return None, "non_object_top_level"
    return payload, None


def _semantic_diagnostic(payload: dict[str, Any]) -> str:
    actions = payload.get("actions")
    if not isinstance(actions, list):
        return "actions_not_list"
    if len(actions) != 8:
        return "wrong_action_count"
    if any(action not in exact_adapter.ACTIONS for action in actions):
        return "invalid_action"
    strategy = payload.get("strategy", "")
    if not isinstance(strategy, str):
        return "strategy_not_string"
    if len(strategy) > exact_adapter.MAX_STRATEGY_CHARS:
        return "strategy_too_long"
    try:
        strategy.encode("ascii")
    except UnicodeEncodeError:
        return "strategy_non_ascii"
    return "structured_contract_invalid"


def parse_projected_response(text: str) -> ProjectionParseResult:
    """Ignore unknown top-level keys only; preserve all required semantic checks."""

    exact_valid, exact_strategy = exact_adapter.parse_response(text)
    if exact_valid:
        return ProjectionParseResult(
            valid=True,
            strategy=exact_strategy,
            exact_parse_valid=True,
            projection_used=False,
            unknown_key_count=0,
            unknown_key_fingerprints=(),
            diagnostic="exact_valid",
        )

    payload, decode_error = _decode(text)
    if payload is None:
        return ProjectionParseResult(
            valid=False,
            strategy="",
            exact_parse_valid=False,
            projection_used=False,
            unknown_key_count=0,
            unknown_key_fingerprints=(),
            diagnostic=str(decode_error),
        )

    unknown = sorted(set(payload) - RECOGNIZED_TOP_LEVEL_KEYS)
    projected = {key: payload[key] for key in RECOGNIZED_TOP_LEVEL_KEYS if key in payload}
    projected_text = json.dumps(projected, sort_keys=True, separators=(",", ":"))
    projected_valid, strategy = exact_adapter.parse_response(projected_text)
    fingerprints = tuple(_fingerprint(key) for key in unknown)
    if projected_valid and unknown:
        return ProjectionParseResult(
            valid=True,
            strategy=strategy,
            exact_parse_valid=False,
            projection_used=True,
            unknown_key_count=len(unknown),
            unknown_key_fingerprints=fingerprints,
            diagnostic="unknown_top_level_keys_projected",
        )
    if projected_valid:
        # Defensive: the exact parser should also have accepted when no unknown keys exist.
        return ProjectionParseResult(
            valid=False,
            strategy="",
            exact_parse_valid=False,
            projection_used=False,
            unknown_key_count=0,
            unknown_key_fingerprints=(),
            diagnostic="exact_projected_inconsistency",
        )
    return ProjectionParseResult(
        valid=False,
        strategy="",
        exact_parse_valid=False,
        projection_used=bool(unknown),
        unknown_key_count=len(unknown),
        unknown_key_fingerprints=fingerprints,
        diagnostic=_semantic_diagnostic(projected),
    )
