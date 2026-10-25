"""The four G1 v9 experimental arms as offline, context-aware policies.

Every arm implements the kernel ``ModelDecisionPort`` contract and is a
purely offline, deterministic stand-in for the model integration that
follows the protocol-freeze gate. Policies learn only from the lawful
feedback channel - the public success counter diffed between
observations, attributed to their own previous (context, ordering)
choice - and never touch evaluator truth.

Arm A keeps its per-context experience memory across the rule switch.
Arm B exposes ``ablate()`` and is cleared exactly when the recorded
ablation transaction fires. Arm C restores its memory from the sealed
snapshot at the freeze fork and stops learning. Arm D is a canonical
per-context alternation baseline that ignores feedback.
"""

from __future__ import annotations

import copy
from collections.abc import Mapping
from typing import Any

from ..views import DecisionRequest

ARMS = ("adaptive", "memory-ablated", "frozen", "canonical")
_ORDERINGS = ("AB", "BA")


class ContextMemoryPolicy:
    """Per-context experience memory with bounded stagnation re-probing."""

    model_id = "g1v9-adaptive-offline-v1"

    def __init__(self, *, exploration_rounds: int = 2, stagnation_window: int = 4) -> None:
        self.exploration_rounds = exploration_rounds
        self.stagnation_window = stagnation_window
        self.calls = 0
        self.chosen: list[tuple[str, str]] = []
        self.outcomes: list[bool] = []
        self._last_seen: int | None = 0
        self._successes: dict[str, dict[str, int]] = {}
        self._attempts: dict[str, dict[str, int]] = {}
        self._context_tail: dict[str, list[bool]] = {}
        self.frozen_at: int | None = None

    def decide(self, request: DecisionRequest) -> dict[str, str]:
        self.calls += 1
        context = str(request.observation.public_state["current_context"])
        total = int(request.observation.public_state.get("successes", 0))
        self._absorb_feedback(total)
        ordering = self._choose(context)
        self.chosen.append((context, ordering))
        self._attempts[context][ordering] += 1
        return {"ordering": ordering, "context": context, "decided_at": request.tick}

    def _context_of(self, context: str, field: str):
        """Return the per-context table for one field, seeding on first use."""

        store = getattr(self, field)
        if context not in store:
            store[context] = [] if field == "_context_tail" else {"AB": 0, "BA": 0}
        return store[context]

    def _absorb_feedback(self, total: int) -> None:
        if self._last_seen is None:
            self._last_seen = total
            return
        delta = total - self._last_seen
        self._last_seen = total
        if self.frozen_at is not None:
            return
        if delta not in (0, 1):
            raise ValueError(
                "feedback channel inconsistent with the one-decision cadence"
            )
        if self.chosen:
            context, ordering = self.chosen[-1]
            outcome = delta == 1
            self.outcomes.append(outcome)
            self._context_of(context, "_context_tail").append(outcome)
            if outcome:
                self._context_of(context, "_successes")[ordering] += 1

    def _choose(self, context: str) -> str:
        tail = self._context_of(context, "_context_tail")
        attempts = self._context_of(context, "_attempts")
        successes = self._context_of(context, "_successes")
        if len(tail) >= self.stagnation_window and not any(
            tail[-self.stagnation_window :]
        ):
            return "BA" if successes["AB"] >= successes["BA"] else "AB"
        if attempts["AB"] < self.exploration_rounds:
            return "AB"
        if attempts["BA"] < self.exploration_rounds:
            return "BA"
        return "AB" if successes["AB"] >= successes["BA"] else "BA"

    def snapshot(self) -> dict[str, Any]:
        """Return a canonical copy of the memory (P0 policy snapshot)."""

        return copy.deepcopy(
            {
                "chosen": [list(item) for item in self.chosen],
                "outcomes": list(self.outcomes),
                "last_seen": self._last_seen,
                "successes": copy.deepcopy(self._successes),
                "attempts": copy.deepcopy(self._attempts),
                "context_tail": copy.deepcopy(self._context_tail),
                "frozen_at": self.frozen_at,
            }
        )

    def restore(self, snapshot: Mapping[str, Any]) -> None:
        """Restore a previously taken (or sealed) memory."""

        self.chosen = [tuple(item) for item in snapshot["chosen"]]
        self.outcomes = list(snapshot["outcomes"])
        self._last_seen = snapshot["last_seen"]
        self._successes = {
            context: dict(counts)
            for context, counts in snapshot["successes"].items()
        }
        self._attempts = {
            context: dict(counts) for context, counts in snapshot["attempts"].items()
        }
        self._context_tail = {
            context: list(tail) for context, tail in snapshot["context_tail"].items()
        }
        self.frozen_at = snapshot["frozen_at"]

    def ablate(self) -> None:
        """Clear the experience memory (arm B treatment)."""

        self.chosen = []
        self.outcomes = []
        self._last_seen = None
        self._successes = {}
        self._attempts = {}
        self._context_tail = {}


class MemoryAblatedPolicy(ContextMemoryPolicy):
    """Arm B: identical to the adaptive policy until ``ablate`` fires."""

    model_id = "g1v9-memory-ablated-offline-v1"


class FrozenPolicy(ContextMemoryPolicy):
    """Arm C: restores the sealed snapshot and never learns afterwards."""

    model_id = "g1v9-frozen-offline-v1"

    def __init__(self, snapshot: Mapping[str, Any]) -> None:
        super().__init__()
        self.restore(snapshot)
        # Freeze is explicit and unconditional at construction: feedback
        # seen later resyncs the success counter but never updates this
        # arm's outcome history, learned successes, or choices' learning
        # statistics. The arm keeps acting from the restored memory.
        self.frozen_at = 0


class CanonicalPolicy:
    """Arm D: per-context alternation baseline; feedback is ignored."""

    model_id = "g1v9-canonical-offline-v1"

    def __init__(self) -> None:
        self.calls = 0
        self.chosen: list[tuple[str, str]] = []

    def decide(self, request: DecisionRequest) -> dict[str, str]:
        self.calls += 1
        context = str(request.observation.public_state["current_context"])
        previous = [ordering for seen, ordering in self.chosen if seen == context]
        ordering = "AB" if not previous or previous[-1] == "BA" else "BA"
        self.chosen.append((context, ordering))
        return {"ordering": ordering, "context": context, "decided_at": request.tick}


def build_policy(arm_kind: str, *, contract, sealed_memory: Mapping[str, Any] | None = None):
    """Return the offline policy for one arm kind.

    The frozen arm is constructed from the sealed memory snapshot taken at
    the freeze fork; all other arms start from live (or cleared) memory.
    """

    if arm_kind == "adaptive":
        return ContextMemoryPolicy()
    if arm_kind == "memory-ablated":
        return MemoryAblatedPolicy()
    if arm_kind == "frozen":
        if sealed_memory is None:
            raise ValueError("the frozen arm requires its sealed memory snapshot")
        return FrozenPolicy(sealed_memory)
    if arm_kind == "canonical":
        return CanonicalPolicy()
    raise ValueError(f"unknown arm kind {arm_kind!r}")
