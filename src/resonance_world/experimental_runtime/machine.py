"""Reducer registry: the only path by which events change world state.

A reducer is a pure function ``(state, event, sealed_payload) -> state``.
``sealed_payload`` is the withheld content of a private event and is
``None`` for public events. Reducers must not mutate their inputs and
must not set the ``tick`` or ``event_count`` watermarks; the state
machine stamps those from the event itself, which keeps replay and
live execution on exactly the same transition path.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable
from typing import Any

from resonance_world.adapters import sha256_json

from .events import WorldEvent
from .state import WorldState

Reducer = Callable[[WorldState, WorldEvent, Any], WorldState]


class StateMachine:
    """Deterministic, kind-dispatched reducer registry."""

    def __init__(self) -> None:
        self._reducers: dict[str, Reducer] = {}

    def register(self, kind: str, reducer: Reducer) -> None:
        """Register the reducer for one event kind."""

        if not kind:
            raise ValueError("reducer kind is required")
        if kind in self._reducers:
            raise ValueError(f"reducer for kind {kind!r} is already registered")
        if not callable(reducer):
            raise TypeError("reducer must be callable")
        self._reducers[kind] = reducer

    def kinds(self) -> tuple[str, ...]:
        """Return the registered event kinds in sorted order."""

        return tuple(sorted(self._reducers))

    def fingerprint(self) -> str:
        """Return a stable identity for this reducer registry.

        The fingerprint covers the registered kinds and the module and
        qualified name of every reducer, so renaming or swapping a
        reducer implementation changes the identity even when the event
        kinds stay the same. Branches record it at creation; resume and
        replay refuse to rebuild history under a different machine.

        Note: anonymous functions all report ``<lambda>`` and therefore
        produce meaningless fingerprints; reducers must be named
        functions or classes for the fingerprint to be meaningful.
        """

        reducers = {
            kind: f"{reducer.__module__}.{reducer.__qualname__}"
            for kind, reducer in sorted(self._reducers.items())
        }
        return sha256_json({"reducers": reducers, "schema": "rw-machine-fingerprint-v1"})

    def apply(
        self,
        state: WorldState,
        event: WorldEvent,
        sealed_payload: Any = None,
    ) -> WorldState:
        """Apply ``event`` to ``state`` and stamp the watermarks.

        Private events must be applied with their sealed payload; public
        events must be applied without one. The same strictness holds on
        both live execution and offline replay, so the two paths cannot
        diverge.
        """

        reducer = self._reducers.get(event.kind)
        if reducer is None:
            raise ValueError(f"no reducer registered for event kind {event.kind!r}")
        if event.visibility == "private" and sealed_payload is None:
            raise ValueError(
                f"private event {event.seq} requires its sealed payload to be applied"
            )
        if event.visibility == "public" and sealed_payload is not None:
            raise ValueError(
                f"public event {event.seq} must not be applied with a sealed payload"
            )

        candidate = reducer(state, event, sealed_payload)
        if candidate.tick != state.tick or candidate.event_count != state.event_count:
            raise ValueError(
                f"reducer for {event.kind!r} must not set the tick or event_count watermarks"
            )
        if candidate.scenario_id != state.scenario_id:
            raise ValueError(f"reducer for {event.kind!r} changed the scenario identity")
        return dataclasses.replace(
            candidate, tick=event.tick, event_count=event.seq + 1
        )
