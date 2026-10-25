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
import hashlib
import inspect
from collections.abc import Callable, Mapping
from typing import Any

from resonance_world.adapters import sha256_json

from .events import WorldEvent
from .state import WorldState

Reducer = Callable[[WorldState, WorldEvent, Any], WorldState]


def _code_identity(code: Any) -> dict[str, Any]:
    """Return a canonical identity of one code object, constants included.

    ``co_code`` alone is not sufficient: two functions whose bytecode is
    identical can differ in ``co_consts`` (for example ``+ 1`` versus
    ``+ 2``). The identity therefore covers the bytecode, every constant
    (recursing into nested code objects), and the name tables.
    """

    constants: list[dict[str, Any]] = []
    for const in code.co_consts:
        nested_code = getattr(const, "co_code", None)
        if nested_code is not None:
            constants.append({"kind": "code", "identity": _code_identity(const)})
            continue
        try:
            digest: str | None = hashlib.sha256(repr(const).encode("utf-8")).hexdigest()
        except Exception:
            digest = None
        constants.append({"kind": type(const).__name__, "repr_sha256": digest})
    return {
        "code_sha256": hashlib.sha256(code.co_code).hexdigest(),
        "constants": constants,
        "names": list(code.co_names),
        "varnames": list(code.co_varnames),
    }


def _reducer_identity(fn: Reducer) -> dict[str, Any]:
    """Return the executable-content identity of one reducer.

    The identity binds the module and qualified name to the full code
    identity (bytecode, constants, names) and, when source is available,
    to the source text. Two reducers with the same name but different
    bodies - or bodies differing only in an execution constant - have
    different identities.
    """

    code = getattr(fn, "__code__", None)
    code_identity = _code_identity(code) if code is not None else None
    if code_identity is None:
        code_identity = {"repr_sha256": hashlib.sha256(repr(fn).encode("utf-8")).hexdigest()}
    try:
        source_sha256: str | None = hashlib.sha256(
            inspect.getsource(fn).encode("utf-8")
        ).hexdigest()
    except (OSError, TypeError):
        source_sha256 = None
    return {
        "module": getattr(fn, "__module__", None),
        "qualname": getattr(fn, "__qualname__", repr(fn)),
        "code": code_identity,
        "source_sha256": source_sha256,
    }


class StateMachine:
    """Deterministic, kind-dispatched reducer registry."""

    def __init__(
        self,
        *,
        rules_version: str = "unversioned",
        external_dependencies: Mapping[str, str] | None = None,
    ) -> None:
        """Create the registry with optional rule provenance.

        ``rules_version`` and ``external_dependencies`` participate in
        the machine fingerprint, so a branch recorded under a pinned
        rules version cannot be replayed under a different one.
        """

        if not rules_version:
            raise ValueError("rules_version must be a non-empty string")
        dependencies = dict(external_dependencies or {})
        for name, version in dependencies.items():
            if not isinstance(name, str) or not name:
                raise ValueError("external dependency names must be non-empty strings")
            if not isinstance(version, str) or not version:
                raise ValueError("external dependency versions must be non-empty strings")
        self._reducers: dict[str, Reducer] = {}
        self._rules_version = rules_version
        self._external_dependencies = tuple(sorted(dependencies.items()))

    @property
    def rules_version(self) -> str:
        return self._rules_version

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
        """Return a content-bound identity for this reducer registry.

        The fingerprint covers the registered kinds and, for every
        reducer, its module, qualified name, full code identity
        (bytecode, constants including nested code objects, names), and
        source text when available, plus the pinned ``rules_version``
        and declared external dependencies. Editing a reducer body,
        changing an execution constant, or changing the rules version
        changes the identity. Branches record it at creation; resume and
        replay refuse to rebuild history under a different machine.
        """

        reducers = {
            kind: _reducer_identity(reducer)
            for kind, reducer in sorted(self._reducers.items())
        }
        return sha256_json(
            {
                "external_dependencies": [
                    {"name": name, "version": version}
                    for name, version in self._external_dependencies
                ],
                "reducers": reducers,
                "rules_version": self._rules_version,
                "schema": "rw-machine-fingerprint-v3",
            }
        )

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
