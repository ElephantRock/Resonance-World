"""External log anchoring for tamper-evident world history.

The per-event digest chain stored inside the world file detects
inconsistent tampering, but a local actor can recompute every internal
digest. The defense is external anchoring: a compact commitment over
the whole recorded log (a sequential hash chain of the event content
digests) that the operator stores outside the world file. The verifier
in this module recomputes the chain from the log alone, so any rewrite
- however internally consistent - fails comparison with the anchored
head.
"""

from __future__ import annotations

import hashlib
from typing import Any

from .events import WorldEvent

ANCHOR_SCHEMA = "rw-log-anchor-v1"
_GENESIS_HEAD = "0" * 64


def log_chain_head(events: tuple[WorldEvent, ...] | list[WorldEvent]) -> str:
    """Return the sequential hash-chain head over the branch log."""

    head = _GENESIS_HEAD
    for event in events:
        head = hashlib.sha256((head + event.event_sha256).encode("utf-8")).hexdigest()
    return head


def build_log_anchor(
    branch_id: str,
    events: tuple[WorldEvent, ...] | list[WorldEvent],
    *,
    scenario_id: str | None = None,
    genesis_state_sha256: str | None = None,
) -> dict[str, Any]:
    """Build the anchor record an operator must custody externally.

    ``scenario_id`` and ``genesis_state_sha256`` bind the anchor to one
    world identity so a log from another branch or scenario can never be
    substituted for the anchored one.
    """

    return {
        "schema": ANCHOR_SCHEMA,
        "branch_id": branch_id,
        "scenario_id": scenario_id,
        "genesis_state_sha256": genesis_state_sha256,
        "event_count": len(events),
        "chain_head": log_chain_head(events),
    }


def verify_log_anchor(
    events: tuple[WorldEvent, ...] | list[WorldEvent],
    anchor: dict[str, Any],
    *,
    branch_id: str,
    scenario_id: str | None = None,
    genesis_state_sha256: str | None = None,
) -> bool:
    """Independently verify ``events`` against an externally held anchor.

    The expected ``branch_id`` (and, when the verifier knows them, the
    scenario identity and genesis commitment) must match the anchor, and
    the anchor's counters and chain head must match the log.
    """

    return (
        anchor.get("schema") == ANCHOR_SCHEMA
        and anchor.get("branch_id") == branch_id
        and (scenario_id is None or anchor.get("scenario_id") == scenario_id)
        and (
            genesis_state_sha256 is None
            or anchor.get("genesis_state_sha256") == genesis_state_sha256
        )
        and anchor.get("event_count") == len(events)
        and anchor.get("chain_head") == log_chain_head(events)
    )
