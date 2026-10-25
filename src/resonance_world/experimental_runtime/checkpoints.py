"""Checkpoint records for the experimental world kernel.

A checkpoint is a content-addressed snapshot of the complete
authoritative state taken at a specific event watermark. Integrity is
verified on both save and load: the stored digest must equal the digest
of the stored canonical state bytes, and the public digest must equal
the digest of the stored state's public projection.
"""

from __future__ import annotations

from dataclasses import dataclass

from .state import WorldState, full_state_sha256, public_state_sha256


@dataclass(frozen=True, slots=True)
class Checkpoint:
    """A named, hash-anchored snapshot of one branch of the world."""

    branch_id: str
    name: str
    tick: int
    event_count: int
    state_sha256: str
    public_state_sha256: str
    state: WorldState

    @classmethod
    def build(
        cls,
        *,
        branch_id: str,
        name: str,
        state: WorldState,
        state_digest: str | None = None,
    ) -> Checkpoint:
        """Build a self-consistent checkpoint for ``state``.

        ``state_digest`` should be the store's keyed state commitment so
        the persisted snapshot cannot be brute-forced from its digest.
        When omitted (in-memory use only) a bare digest is computed.
        """

        if not branch_id:
            raise ValueError("branch_id is required")
        if not name:
            raise ValueError("checkpoint name is required")
        return cls(
            branch_id=branch_id,
            name=name,
            tick=state.tick,
            event_count=state.event_count,
            state_sha256=state_digest if state_digest is not None else full_state_sha256(state),
            public_state_sha256=public_state_sha256(state),
            state=state,
        )
