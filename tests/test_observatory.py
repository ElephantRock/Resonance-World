from __future__ import annotations

import inspect

import pytest

pytest.importorskip("resonance_contextgraph")

from resonance_world.context_graph_runtime import HISTORICAL_SUBSTRATE_ENABLED
from resonance_world.observatory import (
    EVENT_TYPE,
    OBSERVER_ID,
    PREDICATES,
    SOURCE_CLASS,
    ContextGraphObservatory,
)
from resonance_world.w4a_joint_learning import (
    CommunicationPolicy,
    IndividualState,
    JointController,
    JointEnvironment,
    JointEpisode,
    JointLearningSession,
    JointMission,
    RelationshipStateStore,
)


def _mission() -> JointMission:
    return JointMission(
        mission_id="o0:test:mission",
        context="o0-context-alpha",
        lead_skill="planning",
        support_skill="verification",
    )


def _episode(*, success: bool = True) -> JointEpisode:
    return JointEpisode(
        mission_id="o0:test:mission",
        context="o0-context-alpha",
        agent_a="agent-a",
        action_a="lead",
        agent_b="agent-c",
        action_b="support",
        success=success,
    )


def test_observatory_emits_exact_frozen_nine_claim_schema() -> None:
    observer = ContextGraphObservatory(scope_id="o0:communication-0:7001")
    observer.observe(_mission(), _episode())
    claims = observer.evidence()

    assert observer.observed_episode_count == 1
    assert observer.claim_count == 9
    assert len(claims) == 9
    assert tuple(claim.predicate for claim in claims) == PREDICATES
    assert len({claim.claim_id for claim in claims}) == 9
    assert len({claim.source_id for claim in claims}) == 9
    assert {claim.subject for claim in claims} == {"o0:test:mission"}
    assert {claim.scope_id for claim in claims} == {"o0:communication-0:7001"}
    assert {claim.observed_by for claim in claims} == {OBSERVER_ID}
    assert {claim.source_class for claim in claims} == {SOURCE_CLASS}
    assert {claim.observed_at for claim in claims} == {1}
    assert {claim.confidence for claim in claims} == {1.0}
    assert {claim.direct for claim in claims} == {True}
    assert next(claim.object for claim in claims if claim.predicate == "event_type") == EVENT_TYPE
    assert next(claim.object for claim in claims if claim.predicate == "outcome") == "success"


def test_observatory_uses_monotonic_episode_ordinals() -> None:
    observer = ContextGraphObservatory(scope_id="o0:communication-0:7001")
    first = _episode(success=False)
    second_mission = JointMission(
        mission_id="o0:test:mission:2",
        context="o0-context-beta",
        lead_skill="planning",
        support_skill="verification",
    )
    second = JointEpisode(
        mission_id=second_mission.mission_id,
        context=second_mission.context,
        agent_a="agent-b",
        action_a="lead",
        agent_b="agent-d",
        action_b="support",
        success=True,
    )

    observer.observe(_mission(), first)
    observer.observe(second_mission, second)
    claims = observer.evidence()

    assert len(claims) == 18
    assert [claim.observed_at for claim in claims[:9]] == [1] * 9
    assert [claim.observed_at for claim in claims[9:]] == [2] * 9


def test_observatory_rejects_mismatched_mission_records() -> None:
    observer = ContextGraphObservatory(scope_id="o0:test")
    bad_mission = JointMission("different", "o0-context-alpha", "planning", "verification")

    with pytest.raises(ValueError, match="mission_id"):
        observer.observe(bad_mission, _episode())


def test_joint_learning_calls_observer_after_relationship_record() -> None:
    relationships = RelationshipStateStore()
    mission = _mission()
    first = IndividualState("agent-a", {"planning": 9, "verification": 1})
    second = IndividualState("agent-c", {"planning": 1, "verification": 9})
    seen: list[bool] = []

    class OrderingObserver:
        def observe(self, observed_mission: JointMission, episode: JointEpisode) -> None:
            assert observed_mission == mission
            memory = relationships.pair_memory(episode.agent_a, episode.agent_b)
            seen.append(bool(memory.episodes and memory.episodes[-1] == episode))

    session = JointLearningSession(
        environment=JointEnvironment(),
        controller=JointController(),
        relationships=relationships,
        communication=CommunicationPolicy(),
        observer=OrderingObserver(),
    )
    session.run_episode(first, second, mission, seed=7001)

    assert seen == [True]


def test_observer_disabled_path_matches_explicit_none() -> None:
    first = IndividualState("agent-a", {"planning": 9, "verification": 1})
    second = IndividualState("agent-b", {"planning": 9, "verification": 1})
    mission = _mission()

    default_relationships = RelationshipStateStore()
    default_session = JointLearningSession(
        JointEnvironment(),
        JointController(),
        default_relationships,
        CommunicationPolicy(),
    )
    explicit_relationships = RelationshipStateStore()
    explicit_session = JointLearningSession(
        JointEnvironment(),
        JointController(),
        explicit_relationships,
        CommunicationPolicy(),
        observer=None,
    )

    assert (
        default_session.run_episode(first, second, mission, seed=7001)
        == explicit_session.run_episode(first, second, mission, seed=7001)
    )
    assert default_relationships.snapshot() == explicit_relationships.snapshot()


def test_observer_contract_has_no_participant_state_handle() -> None:
    init_params = set(inspect.signature(ContextGraphObservatory.__init__).parameters)
    observe_params = set(inspect.signature(ContextGraphObservatory.observe).parameters)

    assert init_params == {"self", "scope_id"}
    assert observe_params == {"self", "mission", "episode"}
    assert HISTORICAL_SUBSTRATE_ENABLED is False
