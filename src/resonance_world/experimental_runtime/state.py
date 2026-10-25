"""Authoritative world state with canonical serialization and hashing.

World state splits into a public projection (the only part agents may
observe) and a private evaluator compartment (hidden policies, hidden
thresholds, and evaluator answers). Both compartments are covered by the
full state hash, which is the authoritative integrity anchor for
checkpoints and replay. The public hash covers only agent-visible
content and is stable under private-state changes.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

from resonance_world.adapters import canonical_json_bytes

StateValue = int | str


def _validated(mapping: Mapping[str, StateValue] | None) -> Mapping[str, StateValue]:
    if mapping is None:
        return {}
    for key, value in mapping.items():
        if not isinstance(key, str) or not key:
            raise ValueError("state keys must be non-empty strings")
        if isinstance(value, bool) or not isinstance(value, (int, str)):
            raise ValueError("state values must be int or str")
    return mapping


def public_state_bytes(state: WorldState) -> bytes:
    """Canonical bytes of the agent-visible projection of ``state``."""

    return canonical_json_bytes(
        {
            "public": dict(state.public),
            "scenario_id": state.scenario_id,
            "tick": state.tick,
        }
    )


def full_state_bytes(state: WorldState) -> bytes:
    """Canonical bytes of the complete authoritative state."""

    return canonical_json_bytes(
        {
            "event_count": state.event_count,
            "private": dict(state.private),
            "public": dict(state.public),
            "scenario_id": state.scenario_id,
            "tick": state.tick,
        }
    )


def public_state_sha256(state: WorldState) -> str:
    """SHA-256 of the agent-visible projection."""

    return hashlib.sha256(public_state_bytes(state)).hexdigest()


def full_state_sha256(state: WorldState) -> str:
    """SHA-256 of the complete authoritative state, private state included."""

    return hashlib.sha256(full_state_bytes(state)).hexdigest()


@dataclass(frozen=True, slots=True)
class WorldState:
    """The complete authoritative world state at one event watermark.

    ``tick`` and ``event_count`` are watermarks maintained by the state
    machine; reducers must not set them directly. ``public`` is the only
    compartment agents may observe. ``private`` is evaluator-owned and is
    never exposed through agent-visible views or public event logs.
    """

    scenario_id: str
    tick: int = 0
    event_count: int = 0
    public: Mapping[str, StateValue] = field(default_factory=dict)
    private: Mapping[str, StateValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.scenario_id:
            raise ValueError("scenario_id is required")
        if isinstance(self.tick, bool) or not isinstance(self.tick, int) or self.tick < 0:
            raise ValueError("tick must be a non-negative integer")
        if (
            isinstance(self.event_count, bool)
            or not isinstance(self.event_count, int)
            or self.event_count < 0
        ):
            raise ValueError("event_count must be a non-negative integer")
        # Deep immutability: the compartments are exposed as read-only
        # mappings, so accidental mutation outside a reducer fails loudly
        # instead of silently diverging from the event log.
        object.__setattr__(self, "public", MappingProxyType(dict(_validated(self.public))))
        object.__setattr__(self, "private", MappingProxyType(dict(_validated(self.private))))
