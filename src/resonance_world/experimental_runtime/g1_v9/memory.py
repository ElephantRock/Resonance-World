"""Memory custody contract for G1 v9: the MemorySnapshot attestation chain.

Agent experience memory is policy-owned but world-attested. Every save,
ablation, or restore of the memory records:

- a public ``memory_snapshot`` event carrying the memory identity, the tick,
  the kind of transaction, and a keyed commitment over the canonical memory;
- a sealed private ``memory_state`` event whose sealed payload is the
  canonical memory content itself, so custody survives resume through the
  world's own sealed ledger.

The attestation invariant is: for every memory event, the keyed commitment
in the public event equals the commitment of the co-recorded sealed payload.
Ablation consistency after resume is therefore checkable from the world
alone, without trusting the policy object.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ..events import WorldEvent
from ..kernel import WorldKernel
from ..store import KernelStore

MEMORY_SNAPSHOT_KIND = "memory_snapshot"
MEMORY_STATE_KIND = "memory_state"


def canonical_memory(memory: Mapping[str, Any]) -> dict[str, Any]:
    """Return the canonical, serializable form of one policy memory."""

    return _plain(memory)


def _plain(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    return value


def _commit_memory(kernel: WorldKernel, memory: Mapping[str, Any]) -> str:
    if kernel.store is None:
        raise ValueError("memory custody requires a persistence store")
    return kernel.store.commit_payload(canonical_memory(memory))


def record_memory_event(
    kernel: WorldKernel,
    *,
    tick: int,
    kind: str,
    memory: Mapping[str, Any],
    memory_id: str,
) -> WorldEvent:
    """Record one memory transaction: public attestation + sealed state.

    ``kind`` is one of ``save``, ``ablated``, or ``restore``. The public
    event commits to the memory content without revealing it; the sealed
    event carries the content so custody survives resume.
    """

    if kind not in ("save", "ablated", "restore"):
        raise ValueError(f"unknown memory transaction kind {kind!r}")
    canonical = canonical_memory(memory)
    commitment = _commit_memory(kernel, canonical)
    kernel.emit(
        MEMORY_STATE_KIND,
        dict(canonical),
        source="external",
        visibility="private",
    )
    return kernel.emit(
        MEMORY_SNAPSHOT_KIND,
        {
            "memory_id": memory_id,
            "tick": tick,
            "kind": kind,
            "memory_commitment": commitment,
            "custody": "sealed-world-ledger",
        },
    )


def verify_memory_attestation(
    store: KernelStore, branch_id: str, event_seq: int
) -> bool:
    """Verify one attestation against its co-recorded sealed payload.

    Any integrity failure along the chain (missing event, tampered sealed
    payload, digest mismatch) yields ``False`` rather than raising, so the
    verifier is usable by external auditors.
    """

    try:
        events = store.iter_events(branch_id)
        attestation = next(
            (
                event
                for event in events
                if event.kind == MEMORY_SNAPSHOT_KIND and event.seq == event_seq
            ),
            None,
        )
        if attestation is None or attestation.payload is None:
            return False
        sealed_seq = attestation.seq - 1
        if sealed_seq < 0:
            return False
        sealed_event = next(
            (event for event in events if event.seq == sealed_seq), None
        )
        if sealed_event is None or sealed_event.kind != MEMORY_STATE_KIND:
            return False
        payload = store.sealed_payload(branch_id, sealed_seq)
    except ValueError:
        return False
    return store.commit_payload(payload) == attestation.payload["memory_commitment"]


def latest_memory_state(store: KernelStore, branch_id: str) -> dict[str, Any] | None:
    """Return the most recent sealed memory content for ``branch_id``."""

    rows = [
        event
        for event in store.iter_events(branch_id)
        if event.kind == MEMORY_STATE_KIND
    ]
    if not rows:
        return None
    return store.sealed_payload(branch_id, rows[-1].seq)
