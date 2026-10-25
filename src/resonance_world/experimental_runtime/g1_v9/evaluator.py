"""The G1 v9 evaluator: sole owner and sealer of the hidden task truth.

The hidden rule of the world - which ordering each task context rewards in
each rule epoch - is derived here from evaluator-held seed material and
enters the world exclusively as sealed private events. No ordering value
exists as a module constant or in any importable public interface: the only
way to read the hidden truth is to hold the store commitment key and open
the sealed ledger.

The switch schedule is counterbalanced by construction: at the rule switch
exactly half of the contexts flip and half keep their ordering, with the
flip set chosen by the evaluator seed. Contexts that do not flip measure
any "switch-prior" memorization bias in a policy.
"""

from __future__ import annotations

import hashlib
import hmac
from typing import Any

ORDERINGS = ("AB", "BA")
_SEED_LABEL = b"g1v9-evaluator-seed-v1"


def derive_evaluator_seed(seed_material: bytes) -> bytes:
    """Derive the internal evaluator seed from operator-held material."""

    if not isinstance(seed_material, bytes) or len(seed_material) < 16:
        raise ValueError("evaluator seed material must be at least 16 bytes")
    return hmac.new(seed_material, _SEED_LABEL, hashlib.sha256).digest()


def context_schedule(seed: bytes, ticks: int, context_count: int, cadence: int) -> list[str]:
    """Return the public context presented at each prescribed decision.

    Contexts rotate deterministically, seeded by the evaluator, so every
    context appears equally often and no decision order leaks the hidden
    truth.
    """

    count = ticks // cadence
    schedule = []
    for index in range(count):
        digest = hmac.new(
            seed, f"context:{index}".encode(), hashlib.sha256
        ).digest()
        schedule.append(f"ctx-{digest[0] % context_count}")
    return schedule


def derive_epoch_table(
    seed: bytes, epoch: int, context_count: int, previous: dict[str, str] | None = None
) -> dict[str, str]:
    """Derive the hidden ordering table for one rule epoch.

    Epoch 0 assigns each context an ordering derived from the seed. Later
    epochs flip exactly half of the contexts (counterbalanced) and keep
    the other half unchanged, relative to ``previous``.
    """

    if context_count < 2 or context_count % 2 != 0:
        raise ValueError("context_count must be even and at least 2")
    if epoch == 0:
        table: dict[str, str] = {}
        for context in range(context_count):
            digest = hmac.new(
                seed, f"table:0:{context}".encode(), hashlib.sha256
            ).digest()
            table[f"ctx-{context}"] = ORDERINGS[digest[0] % 2]
        return table
    if previous is None or len(previous) != context_count:
        raise ValueError("epoch > 0 requires the previous hidden table")

    # Balanced switch: a seeded, deterministic ordering of contexts decides
    # which exact half flips; the other half keeps its ordering (no-change
    # controls for switch-prior memorization bias).
    ranked = sorted(
        range(context_count),
        key=lambda context: hmac.new(
            seed, f"flip:{epoch}:{context}".encode(), hashlib.sha256
        ).digest(),
    )
    flip_set = set(ranked[: context_count // 2])
    table = {}
    for context in range(context_count):
        name = f"ctx-{context}"
        if context in flip_set:
            table[name] = (
                ORDERINGS[1] if previous[name] == ORDERINGS[0] else ORDERINGS[0]
            )
        else:
            table[name] = previous[name]
    flips = sum(1 for name in table if table[name] != previous[name])
    if flips != context_count // 2:
        raise ValueError("counterbalancing invariant violated at the switch")
    return table


def sealed_payload(epoch: int, table: dict[str, str]) -> dict[str, Any]:
    """Return the sealed payload for a rule epoch (evaluator-owned truth)."""

    return {"epoch": epoch, "table": dict(table)}
