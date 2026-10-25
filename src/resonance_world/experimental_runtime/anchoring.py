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


def build_log_anchor(branch_id: str, events: tuple[WorldEvent, ...] | list[WorldEvent]) -> dict[str, Any]:
    """Build the anchor record an operator must custody externally."""

    return {
        "schema": ANCHOR_SCHEMA,
        "branch_id": branch_id,
        "event_count": len(events),
        "chain_head": log_chain_head(events),
    }


def verify_log_anchor(
    events: tuple[WorldEvent, ...] | list[WorldEvent],
    anchor: dict[str, Any],
) -> bool:
    """Independently verify ``events`` against an externally held anchor."""

    return (
        anchor.get("schema") == ANCHOR_SCHEMA
        and anchor.get("chain_head") == log_chain_head(events)
    )
