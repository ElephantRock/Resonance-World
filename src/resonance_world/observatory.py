"""Passive ContextGraph Observatory for World joint-learning episodes.

The Observatory receives only immutable ``JointMission`` and ``JointEpisode`` records
through the dependency-inverted hook in ``w4a_joint_learning``. It has no handle to
individual capability state, relationship state, controllers, environments, or evaluator
truth, and it exposes no participant-side decision API.

O0 freezes this module to an exactly nine-claim joint-episode schema. Historical context
retrieval for agents or organizations is deliberately absent.
"""

from __future__ import annotations

from dataclasses import dataclass

from resonance_contextgraph import EvidenceClaim, EvidenceStore

from .context_graph_adapter import to_evidence_claim
from .w4a_joint_learning import JointEpisode, JointMission

OBSERVER_ID = "resonance-world:joint-learning-observer"
SOURCE_CLASS = "world_observation"
EVENT_TYPE = "joint_episode"
PREDICATES = (
    "event_type",
    "context",
    "lead_skill",
    "support_skill",
    "participant_a",
    "action_a",
    "participant_b",
    "action_b",
    "outcome",
)


@dataclass(frozen=True, slots=True)
class _ObservedClaim:
    field_id: str
    subject: str
    predicate: str
    object: str
    observed_by: str
    source_id: str
    source_class: str
    observed_at: int
    confidence: float
    direct: bool


class ContextGraphObservatory:
    """Append-only observer for the frozen O0 joint-episode evidence schema."""

    def __init__(self, *, scope_id: str) -> None:
        if not scope_id:
            raise ValueError("scope_id must be non-empty")
        self._scope_id = scope_id
        self._store = EvidenceStore()
        self._episode_ordinal = 0

    @property
    def scope_id(self) -> str:
        return self._scope_id

    @property
    def observed_episode_count(self) -> int:
        return self._episode_ordinal

    @property
    def claim_count(self) -> int:
        return self._store.size

    def observe(self, mission: JointMission, episode: JointEpisode) -> None:
        """Record one completed episode after World has committed endogenous state."""
        if episode.mission_id != mission.mission_id:
            raise ValueError("episode mission_id does not match observed mission")
        if episode.context != mission.context:
            raise ValueError("episode context does not match observed mission")

        self._episode_ordinal += 1
        observed_at = self._episode_ordinal
        values = {
            "event_type": EVENT_TYPE,
            "context": episode.context,
            "lead_skill": mission.lead_skill,
            "support_skill": mission.support_skill,
            "participant_a": episode.agent_a,
            "action_a": episode.action_a,
            "participant_b": episode.agent_b,
            "action_b": episode.action_b,
            "outcome": "success" if episode.success else "failure",
        }
        for predicate in PREDICATES:
            source_id = f"{self._scope_id}:{mission.mission_id}:{predicate}"
            observed = _ObservedClaim(
                field_id=self._scope_id,
                subject=mission.mission_id,
                predicate=predicate,
                object=values[predicate],
                observed_by=OBSERVER_ID,
                source_id=source_id,
                source_class=SOURCE_CLASS,
                observed_at=observed_at,
                confidence=1.0,
                direct=True,
            )
            # Source IDs are unique by frozen schema. The explicit ordinal is still
            # mandatory at the adapter boundary; each source has exactly one delivery.
            self._store.ingest(to_evidence_claim(observed, delivery=0))

    def evidence(self) -> tuple[EvidenceClaim, ...]:
        """Return evaluator-side evidence in deterministic append order."""
        return self._store.claims(scope_id=self._scope_id)
