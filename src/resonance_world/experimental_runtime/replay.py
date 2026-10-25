"""Offline deterministic replay from the persisted event log.

Replay rebuilds a branch by applying its recorded events through the
same reducer registry used during live execution. It consumes recorded
agent decisions as external inputs; no model port exists on this path,
so replay cannot invoke a model. Every stored event digest and every
checkpoint digest is re-verified, which turns replay into a full
integrity audit of the persisted world.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .events import WorldEvent
from .machine import StateMachine
from .state import WorldState, public_state_sha256
from .store import KernelStore


def _sealed_for(event: WorldEvent, sealed: dict[int, Any], store: KernelStore) -> Any:
    """Return the sealed payload for a private event, commitment-verified.

    The event record is the root of trust: its ``payload_sha256`` holds
    the store's keyed commitment to content the public log does not
    reveal. A sealed payload is only admissible when it matches that
    commitment, so consistent tampering with the sealed table alone
    cannot slip through replay.
    """

    if event.visibility != "private":
        return None
    payload = sealed.get(event.seq)
    if payload is None or store.commit_payload(payload) != event.payload_sha256:
        raise ValueError(
            f"sealed payload for event {event.seq} fails its committed digest on event record"
        )
    return payload


@dataclass(frozen=True, slots=True)
class CheckpointVerification:
    """One checkpoint compared against the replayed state at its watermark."""

    name: str
    event_count: int
    expected_state_sha256: str
    actual_state_sha256: str

    @property
    def matched(self) -> bool:
        return self.expected_state_sha256 == self.actual_state_sha256


@dataclass(frozen=True, slots=True)
class ReplayResult:
    """The complete outcome of one offline replay."""

    branch_id: str
    event_count: int
    final_state_sha256: str
    final_public_state_sha256: str
    checkpoint_verifications: tuple[CheckpointVerification, ...]
    recorded_agent_decisions: int

    @property
    def all_checkpoints_matched(self) -> bool:
        return all(item.matched for item in self.checkpoint_verifications)


def _replay(
    store: KernelStore,
    branch_id: str,
    machine: StateMachine,
) -> tuple[WorldState, int, int]:
    """Apply the whole log from genesis.

    Returns ``(state, applied_event_count, recorded_agent_decisions)``.
    """

    state = store.genesis_state(branch_id)
    events = store.iter_events(branch_id)
    sealed = store.sealed_payloads(branch_id)
    decisions = 0
    for event in events:
        # Replay must hand reducers the same frozen representation live
        # execution uses: identical payload types, identical behaviour.
        frozen = event.frozen()
        state = machine.apply(state, frozen, _sealed_for(event, sealed, store))
        if frozen.source == "agent":
            decisions += 1
    return state, len(events), decisions


def replay_state(store: KernelStore, branch_id: str, machine: StateMachine) -> WorldState:
    """Rebuild the branch head state from the persisted event log."""

    state, _, _ = _replay(store, branch_id, machine)
    return state


def replay_branch(store: KernelStore, branch_id: str, machine: StateMachine) -> ReplayResult:
    """Replay ``branch_id`` and verify every checkpoint digest along the way."""

    if store.machine_fingerprint(branch_id) != machine.fingerprint():
        raise ValueError(
            f"state machine does not match the fingerprint recorded for {branch_id!r}; "
            "refusing to rebuild history under different world rules"
        )
    checkpoints = store.checkpoints_by_event_count(branch_id)
    by_watermark = {cp.event_count: cp for cp in checkpoints.values()}
    state = store.genesis_state(branch_id)
    events = store.iter_events(branch_id)
    sealed = store.sealed_payloads(branch_id)

    verifications: list[CheckpointVerification] = []
    decisions = 0
    for event in events:
        # Same frozen representation as live execution: see _replay.
        frozen = event.frozen()
        payload = _sealed_for(event, sealed, store)
        state = machine.apply(state, frozen, payload)
        if frozen.source == "agent":
            decisions += 1
        checkpoint = by_watermark.get(state.event_count)
        if checkpoint is not None:
            verifications.append(
                CheckpointVerification(
                    name=checkpoint.name,
                    event_count=checkpoint.event_count,
                    expected_state_sha256=checkpoint.state_sha256,
                    actual_state_sha256=store.commit_state(state),
                )
            )

    if len(verifications) != len(by_watermark):
        missing = sorted(set(by_watermark) - {item.event_count for item in verifications})
        raise ValueError(
            f"checkpoints {missing} on branch {branch_id!r} were never reached during replay"
        )

    return ReplayResult(
        branch_id=branch_id,
        event_count=len(events),
        final_state_sha256=store.commit_state(state),
        final_public_state_sha256=public_state_sha256(state),
        checkpoint_verifications=tuple(
            sorted(verifications, key=lambda item: item.event_count)
        ),
        recorded_agent_decisions=decisions,
    )
