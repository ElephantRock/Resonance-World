"""The four G1 v9 experimental arms as offline decision policies.

Every arm implements the kernel ``ModelDecisionPort`` contract and is a
purely offline, deterministic stand-in for the model integration that
follows the protocol-freeze gate. The policies learn only from the
lawful feedback channel - the public success counter diffed between
observations, attributed to their own previous choice - and never
touch evaluator truth.

Arm A keeps its experience memory across the rule switch. Arm B exposes
``ablate()`` and is cleared by the runner exactly when the recorded
ablation transaction fires. Arm C stops updating its memory at the
contract's freeze tick (P0 snapshot semantics). Arm D is a canonical
alternation baseline that ignores feedback entirely.
"""

from __future__ import annotations

import copy
from collections.abc import Mapping
from typing import Any

from ..views import DecisionRequest

ARMS = ("adaptive", "memory-ablated", "frozen", "canonical")
_ORDERINGS = ("AB", "BA")


class AdaptivePolicy:
    """Experience-memory policy: learns which ordering is rewarded.

    Memory is the policy's own record of its choices and the outcome
    deltas it observed; it contains no evaluator state.
    """

    model_id = "g1v9-adaptive-offline-v1"

    def __init__(self, *, exploration_rounds: int = 2) -> None:
        self.exploration_rounds = exploration_rounds
        self.chosen: list[str] = []
        self.outcomes: list[bool] = []
        self._last_seen: int | None = 0
        self._successes: dict[str, int] = {"AB": 0, "BA": 0}
        self._attempts: dict[str, int] = {"AB": 0, "BA": 0}
        self.frozen_at: int | None = None
        self.calls = 0

    def decide(self, request: DecisionRequest) -> dict[str, str]:
        self.calls += 1
        total = int(request.observation.public_state.get("successes", 0))
        self._absorb_feedback(total)
        ordering = self._choose()
        self.chosen.append(ordering)
        self._attempts[ordering] += 1
        return {"ordering": ordering, "decided_at": request.tick}

    def _absorb_feedback(self, total: int) -> None:
        """Attribute the outcome delta of the previous decision to it."""

        if self._last_seen is None:
            # Resync without attribution (construction, or post-ablation).
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
        if delta == 1 and self.chosen:
            self._successes[self.chosen[-1]] += 1
            self.outcomes.append(True)
        elif delta == 0 and self.chosen:
            self.outcomes.append(False)

    def _choose(self) -> str:
        # Stagnation re-exploration: after four consecutive failures the
        # remembered best ordering is no longer paying, so probe the
        # alternative instead of locking in forever.
        if len(self.outcomes) >= 4 and not any(self.outcomes[-4:]):
            return "BA" if self._successes["AB"] >= self._successes["BA"] else "AB"
        if self._attempts["AB"] < self.exploration_rounds:
            return "AB"
        if self._attempts["BA"] < self.exploration_rounds:
            return "BA"
        if self._successes["AB"] >= self._successes["BA"]:
            return "AB"
        return "BA"

    def snapshot(self) -> dict[str, Any]:
        """Return a canonical copy of the memory (P0 policy snapshot)."""

        return copy.deepcopy(
            {
                "chosen": list(self.chosen),
                "outcomes": list(self.outcomes),
                "success_total_seen": self._last_seen,
                "successes": dict(self._successes),
                "attempts": dict(self._attempts),
            }
        )

    def restore(self, snapshot: Mapping[str, Any]) -> None:
        """Restore a previously taken snapshot."""

        self.chosen = list(snapshot["chosen"])
        self.outcomes = list(snapshot["outcomes"])
        self._last_seen = snapshot["success_total_seen"]
        self._successes = dict(snapshot["successes"])
        self._attempts = dict(snapshot["attempts"])

    def ablate(self) -> None:
        """Clear the experience memory (arm B treatment)."""

        self.chosen = []
        self.outcomes = []
        self._last_seen = None
        self._successes = {"AB": 0, "BA": 0}
        self._attempts = {"AB": 0, "BA": 0}


class MemoryAblatedPolicy(AdaptivePolicy):
    """Arm B: identical to the adaptive policy until ``ablate`` fires."""

    model_id = "g1v9-memory-ablated-offline-v1"


class FrozenPolicy(AdaptivePolicy):
    """Arm C: stops learning at ``freeze_tick`` (P0 snapshot semantics)."""

    model_id = "g1v9-frozen-offline-v1"

    def __init__(self, *, freeze_tick: int) -> None:
        super().__init__()
        self.freeze_tick = freeze_tick

    def decide(self, request: DecisionRequest) -> dict[str, str]:
        if request.tick >= self.freeze_tick and self.frozen_at is None:
            self.frozen_at = request.tick
        return super().decide(request)


class CanonicalPolicy:
    """Arm D: fixed alternation baseline; feedback is ignored."""

    model_id = "g1v9-canonical-offline-v1"

    def __init__(self) -> None:
        self.calls = 0

    def decide(self, request: DecisionRequest) -> dict[str, str]:
        self.calls += 1
        ordering = "AB" if self.calls % 2 == 1 else "BA"
        return {"ordering": ordering, "decided_at": request.tick}


def build_policy(arm_kind: str, *, contract_freeze_tick: int):
    """Return the offline policy for one arm kind."""

    if arm_kind == "adaptive":
        return AdaptivePolicy()
    if arm_kind == "memory-ablated":
        return MemoryAblatedPolicy()
    if arm_kind == "frozen":
        return FrozenPolicy(freeze_tick=contract_freeze_tick)
    if arm_kind == "canonical":
        return CanonicalPolicy()
    raise ValueError(f"unknown arm kind {arm_kind!r}")
