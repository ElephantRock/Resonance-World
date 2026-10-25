"""The deterministic world kernel: ticks, causal events, decisions, forks.

The kernel owns one authoritative :class:`WorldState` per branch and an
append-only branch-local event log. All state changes flow through
registered reducers; every change is an event. Model-generated decisions
enter the world only as recorded external-input events, so offline replay
re-executes exactly the recorded history and never invokes a model port.

World time advances only through explicit ``advance`` calls; no code path
in this package sleeps or reads the wall clock for state purposes.
"""

from __future__ import annotations

import copy
import dataclasses
from collections.abc import Mapping
from typing import Any

from resonance_world.adapters import sha256_json

from .anchoring import build_log_anchor
from .checkpoints import Checkpoint
from .events import EVENT_VISIBILITIES, WorldEvent
from .machine import StateMachine
from .replay import replay_state
from .scheduler import EventScheduler
from .state import WorldState, full_state_bytes, full_state_sha256, public_state_sha256
from .store import BranchRecord, KernelStore
from .views import DecisionRequest, ModelDecisionPort, Observation
from .world_time import WorldClock

_TICK_KIND = "tick"
_DECISION_VALUE_TYPES = (int, str)


class WorldKernel:
    """One isolated, deterministic branch of an experimental world."""

    def __init__(
        self,
        *,
        scenario_id: str,
        machine: StateMachine,
        state: WorldState,
        store: KernelStore | None = None,
        branch_id: str = "main",
    ) -> None:
        if not scenario_id:
            raise ValueError("scenario_id is required")
        if state.scenario_id != scenario_id:
            raise ValueError("state does not belong to this scenario")
        self._scenario_id = scenario_id
        self._machine = machine
        self._state = state
        self._store = store
        self._branch_id = branch_id
        self._clock = WorldClock(state.tick)
        self._events: list[WorldEvent] = []
        self._sealed: dict[int, Any] = {}
        self._scheduler = EventScheduler()
        self._answered_requests: set[str] = set()
        self._last_observation_seq = -1

    # -- construction -----------------------------------------------------

    @classmethod
    def create(
        cls,
        scenario_id: str,
        machine: StateMachine,
        *,
        store: KernelStore | None = None,
        branch_id: str = "main",
        initial_public: Mapping[str, int | str] | None = None,
        initial_private: Mapping[str, int | str] | None = None,
    ) -> WorldKernel:
        """Create a fresh genesis branch, registering it when persisted."""

        state = WorldState(
            scenario_id=scenario_id,
            tick=0,
            event_count=0,
            public=dict(initial_public or {}),
            private=dict(initial_private or {}),
        )
        if store is not None:
            store.register_branch(
                BranchRecord(
                    branch_id=branch_id,
                    genesis_state_sha256=store.commit_state(state),
                ),
                genesis_state=state,
            )
            store.set_machine_fingerprint(branch_id, machine.fingerprint())
        return cls(
            scenario_id=scenario_id,
            machine=machine,
            state=state,
            store=store,
            branch_id=branch_id,
        )

    @classmethod
    def resume(
        cls,
        *,
        store: KernelStore,
        branch_id: str,
        machine: StateMachine,
        checkpoint_name: str | None = None,
    ) -> WorldKernel:
        """Resume a persisted branch from a checkpoint or from its full log.

        Resuming is only allowed from the branch head. Historical forks are
        made with :meth:`fork`, which is the supported isolation mechanism;
        silently continuing a superseded timeline from a stale checkpoint
        would break append-only causality.
        """

        if checkpoint_name is not None:
            checkpoint = store.load_checkpoint(branch_id, checkpoint_name)
            if checkpoint.event_count != store.event_count(branch_id):
                raise ValueError(
                    f"checkpoint {checkpoint_name!r} is not at the head of {branch_id!r}; "
                    "fork from it instead"
                )
            rebuilt = replay_state(store, branch_id, machine)
            if full_state_bytes(rebuilt) != full_state_bytes(checkpoint.state):
                raise ValueError(
                    f"checkpoint {checkpoint_name!r} does not match the state rebuilt "
                    "from the branch log"
                )
            state = checkpoint.state
        else:
            state = replay_state(store, branch_id, machine)
        if store.machine_fingerprint(branch_id) != machine.fingerprint():
            raise ValueError(
                f"state machine does not match the fingerprint recorded for {branch_id!r}"
            )
        kernel = cls(
            scenario_id=state.scenario_id,
            machine=machine,
            state=state,
            store=store,
            branch_id=branch_id,
        )
        kernel._events = list(store.iter_events(branch_id))
        kernel._sealed = store.sealed_payloads(branch_id)
        kernel._answered_requests = _answered_request_ids(kernel._events)
        _require_machine_covers(machine, kernel._events)
        return kernel

    # -- introspection ----------------------------------------------------

    @property
    def scenario_id(self) -> str:
        return self._scenario_id

    @property
    def branch_id(self) -> str:
        return self._branch_id

    @property
    def tick(self) -> int:
        return self._state.tick

    @property
    def clock(self) -> WorldClock:
        return self._clock

    @property
    def state(self) -> WorldState:
        return self._state

    @property
    def event_count(self) -> int:
        return len(self._events)

    def state_hash(self) -> str:
        """Return the authoritative full-state commitment.

        With a persistence store this is a keyed commitment, so a
        published digest cannot be brute-forced to recover low-entropy
        private state; without one it is a bare digest over local state.
        """

        if self._store is not None:
            return self._store.commit_state(self._state)
        return full_state_sha256(self._state)

    def public_state_hash(self) -> str:
        """Return the agent-visible projection hash."""

        return public_state_sha256(self._state)

    def events(self) -> tuple[WorldEvent, ...]:
        """Return the full log with private payloads redacted."""

        return tuple(
            event.redacted() if event.visibility == "private" else event
            for event in self._events
        )

    def public_events(self, *, since_seq: int = -1) -> tuple[WorldEvent, ...]:
        """Return public events with ``seq > since_seq``."""

        return tuple(
            event
            for event in self._events
            if event.visibility == "public" and event.seq > since_seq
        )

    # -- event recording --------------------------------------------------

    def emit(
        self,
        kind: str,
        payload: Mapping[str, Any] | None = None,
        *,
        source: str = "kernel",
        visibility: str = "public",
        depends_on: tuple[int, ...] = (),
    ) -> WorldEvent:
        """Record one event at the current tick and apply it immediately."""

        if visibility not in EVENT_VISIBILITIES:
            raise ValueError(f"visibility must be one of {sorted(EVENT_VISIBILITIES)}")
        if visibility == "private":
            if payload is None:
                raise ValueError("private events require a payload to seal")
            return self._record(
                kind=kind,
                tick=self._state.tick,
                source=source,
                visibility=visibility,
                payload=payload,
                depends_on=depends_on,
            )
        return self._record(
            kind=kind,
            tick=self._state.tick,
            source=source,
            visibility=visibility,
            payload=payload,
            depends_on=depends_on,
        )

    def schedule(
        self,
        kind: str,
        payload: Mapping[str, Any] | None = None,
        *,
        source: str = "kernel",
        visibility: str = "public",
        priority: int = 0,
        depends_on: tuple[int, ...] = (),
    ) -> None:
        """Queue one event for dispatch at the current tick on ``advance``."""

        self._scheduler.submit(
            kind,
            payload=payload,
            source=source,
            visibility=visibility,
            priority=priority,
            depends_on=depends_on,
        )

    def advance(self, ticks: int = 1) -> WorldState:
        """Dispatch queued events, then move world time forward.

        Each unit advances the world by one tick: queued events are
        dispatched at the current tick in deterministic order, then a tick
        boundary event moves the world to ``tick + 1``. No sleeping occurs;
        world time is causal bookkeeping, not elapsed wall time.
        """

        if isinstance(ticks, bool) or not isinstance(ticks, int):
            raise TypeError("ticks must be an integer")
        if ticks <= 0:
            raise ValueError("ticks must be positive")
        for _ in range(ticks):
            for item in self._scheduler.drain():
                self._record(
                    kind=item.kind,
                    tick=self._state.tick,
                    source=item.source,
                    visibility=item.visibility,
                    payload=item.payload,
                    payload_sha256=item.payload_sha256,
                    depends_on=item.depends_on,
                )
            boundary = self._state.tick + 1
            self._record(
                kind=_TICK_KIND,
                tick=boundary,
                source="kernel",
                visibility="public",
                payload={"to_tick": boundary},
                depends_on=(self._events[-1].seq,) if self._events else (),
            )
            self._clock = WorldClock(boundary)
        return self._state

    def _payload_commitment(self, payload: Mapping[str, Any]) -> str:
        """Return the commitment for a sealed payload.

        Store-backed kernels use a keyed HMAC commitment so the public
        log cannot be brute-forced for low-entropy secrets. In-memory
        kernels have no custody boundary and use a bare digest.
        """

        if self._store is not None:
            return self._store.commit_payload(payload)
        return sha256_json(payload)

    def _record(
        self,
        *,
        kind: str,
        tick: int,
        source: str,
        visibility: str,
        payload: Mapping[str, Any] | None,
        depends_on: tuple[int, ...],
        payload_sha256: str | None = None,
    ) -> WorldEvent:
        if tick < self._state.tick:
            raise ValueError("event tick cannot move backwards")
        if tick > self._state.tick + 1:
            raise ValueError("event tick jumps more than one tick ahead")
        if tick == self._state.tick + 1 and kind != _TICK_KIND:
            raise ValueError("only the tick boundary event may advance world time")

        seq = len(self._events)
        deps = tuple(depends_on)
        for dependency in deps:
            if dependency < 0 or dependency >= seq:
                raise ValueError("causal dependency does not exist in the branch log")
            dependency_event = self._events[dependency]
            if dependency_event.tick > tick:
                raise ValueError("causal dependency lies in the future")

        # Detach the payload from caller-owned structures: recorded history
        # must never alias mutable input.
        payload = copy.deepcopy(payload)

        sealed_payload: Any = None
        if visibility == "private":
            if payload is None:
                raise ValueError("private events require a payload to seal")
            sealed_payload = payload
            event = WorldEvent.create(
                seq=seq,
                tick=tick,
                kind=kind,
                source=source,
                visibility=visibility,
                payload=None,
                payload_sha256=self._payload_commitment(payload),
                depends_on=deps,
            )
        else:
            event = WorldEvent.create(
                seq=seq,
                tick=tick,
                kind=kind,
                source=source,
                visibility=visibility,
                payload=payload,
                payload_sha256=payload_sha256,
                depends_on=deps,
            )

        # Transition is prepared first: reducer failure must leave the
        # kernel untouched. Persistence comes second: storage failure must
        # also leave the kernel untouched, so the live state can never run
        # ahead of the durable log.
        candidate = self._machine.apply(self._state, event, sealed_payload)
        if self._store is not None:
            self._store.append_event(self._branch_id, event, sealed_payload=sealed_payload)
        # Commit point: nothing above mutates kernel state; nothing below fails.
        self._state = candidate
        self._events.append(event)
        if sealed_payload is not None:
            self._sealed[seq] = sealed_payload
        return event

    # -- model decision boundary -------------------------------------------

    def observe(self) -> Observation:
        """Build the agent-visible observation of the current world state."""

        new_events = tuple(
            event
            for event in self._events[self._last_observation_seq + 1 :]
            if event.visibility == "public"
        )
        return Observation(
            scenario_id=self._scenario_id,
            branch_id=self._branch_id,
            tick=self._state.tick,
            public_state=dict(self._state.public),
            public_state_sha256=public_state_sha256(self._state),
            new_events=new_events,
        )

    def request_decision(self) -> DecisionRequest:
        """Record an observation event and open exactly one decision slot."""

        observation = self.observe()
        event = self.emit(
            "observation",
            {
                "tick": observation.tick,
                "public_state_sha256": observation.public_state_sha256,
            },
        )
        self._last_observation_seq = event.seq
        request_id = sha256_json(
            {
                "branch_id": self._branch_id,
                "observation_seq": event.seq,
                "tick": observation.tick,
            }
        )
        if request_id in self._answered_requests:
            raise ValueError("decision request already answered")
        return DecisionRequest(
            request_id=request_id,
            branch_id=self._branch_id,
            tick=observation.tick,
            observation_seq=event.seq,
            observation=observation,
        )

    def record_decision(
        self,
        request: DecisionRequest,
        decision: Mapping[str, Any],
        *,
        model_id: str,
    ) -> WorldEvent:
        """Record one model-generated decision as an external-input event.

        The decision content is frozen into the append-only log here.
        Replay reads this event instead of calling any model, so recorded
        history is sufficient to reproduce the world offline.
        """

        if request.branch_id != self._branch_id:
            raise ValueError("decision request belongs to a different branch")
        if request.request_id in self._answered_requests:
            raise ValueError("decision request already answered")
        if request.tick != self._state.tick:
            raise ValueError("decision request is stale: the world has advanced past it")
        if request.observation_seq != self._last_observation_seq:
            raise ValueError(
                "decision request does not match the latest recorded observation"
            )
        if not model_id:
            raise ValueError("model_id provenance is required")
        decision_payload = _validated_decision(decision)
        event = self._record(
            kind="agent_decision",
            tick=self._state.tick,
            source="agent",
            visibility="public",
            payload={
                "decision": decision_payload,
                "model_id": model_id,
                "request_id": request.request_id,
            },
            depends_on=(request.observation_seq,),
        )
        self._answered_requests.add(request.request_id)
        return event

    def decide_via(self, port: ModelDecisionPort) -> WorldEvent:
        """Request a decision from ``port`` and record it as external input."""

        request = self.request_decision()
        decision = port.decide(request)
        return self.record_decision(request, decision, model_id=port.model_id)

    # -- checkpoints and forks ---------------------------------------------

    def checkpoint(self, name: str) -> Checkpoint:
        """Persist a verified snapshot of the current branch head."""

        if self._store is None:
            raise ValueError("checkpointing requires a persistence store")
        if self._scheduler.pending():
            raise ValueError(
                "cannot checkpoint with pending scheduled events; advance first"
            )
        checkpoint = Checkpoint.build(
            branch_id=self._branch_id,
            name=name,
            state=self._state,
            state_digest=self._store.commit_state(self._state),
        )
        self._store.save_checkpoint(checkpoint)
        return checkpoint

    def log_anchor(self) -> dict[str, Any]:
        """Build the external anchor for the current log head.

        The returned record must be custodied outside this world file
        (governance record, issue comment, or signed note); it is what
        makes a fully recomputed internal log detectable.
        """

        return build_log_anchor(self._branch_id, self._events)

    def fork(self, child_branch_id: str) -> WorldKernel:
        """Fork the current head into a new isolated branch."""

        if self._store is None:
            raise ValueError("forking requires a persistence store")
        if self._scheduler.pending():
            raise ValueError("cannot fork with pending scheduled events; advance first")
        child_state = dataclasses.replace(self._state, event_count=0)
        self._store.register_branch(
            BranchRecord(
                branch_id=child_branch_id,
                genesis_state_sha256=self._store.commit_state(child_state),
                parent_branch_id=self._branch_id,
                fork_tick=self._state.tick,
                fork_event_count=self._state.event_count,
                parent_state_sha256=self._store.commit_state(self._state),
            ),
            genesis_state=child_state,
        )
        self._store.set_machine_fingerprint(child_branch_id, self._machine.fingerprint())
        child = WorldKernel(
            scenario_id=self._scenario_id,
            machine=self._machine,
            state=child_state,
            store=self._store,
            branch_id=child_branch_id,
        )
        child._clock = WorldClock(child_state.tick)
        child.emit(
            "branch_fork",
            {
                "parent_branch_id": self._branch_id,
                "parent_tick": self._state.tick,
                "parent_event_count": self._state.event_count,
            },
        )
        return child


def _validated_decision(decision: Mapping[str, Any]) -> dict[str, int | str]:
    validated: dict[str, int | str] = {}
    for key, value in decision.items():
        if not isinstance(key, str) or not key:
            raise ValueError("decision keys must be non-empty strings")
        if isinstance(value, bool) or not isinstance(value, _DECISION_VALUE_TYPES):
            raise ValueError("decision values must be int or str")
        validated[key] = value
    if not validated:
        raise ValueError("decision must not be empty")
    return validated


def _answered_request_ids(events: list[WorldEvent]) -> set[str]:
    """Rebuild the answered-decision set from the recorded log."""

    answered: set[str] = set()
    for event in events:
        if event.kind != "agent_decision" or event.payload is None:
            continue
        request_id = event.payload.get("request_id")
        if isinstance(request_id, str):
            answered.add(request_id)
    return answered


def _require_machine_covers(machine: StateMachine, events: list[WorldEvent]) -> None:
    covered = set(machine.kinds())
    for event in events:
        if event.kind not in covered:
            raise ValueError(
                f"state machine does not reduce recorded event kind {event.kind!r}"
            )
