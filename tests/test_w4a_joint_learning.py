import inspect

from resonance_world.w4a_joint_learning import (
    CommunicationPolicy,
    IndividualState,
    JointAction,
    JointController,
    JointEnvironment,
    JointEpisode,
    JointLearningSession,
    JointMission,
    RelationshipStateStore,
)


def _agents() -> tuple[IndividualState, IndividualState]:
    return (
        IndividualState("agent-a", {"planning": 9, "verification": 1}),
        IndividualState("agent-b", {"planning": 9, "verification": 1}),
    )


def _mission() -> JointMission:
    return JointMission(
        mission_id="mission-001",
        context="novel-joint-control",
        lead_skill="planning",
        support_skill="verification",
    )


def test_environment_has_no_relationship_state_input() -> None:
    parameters = set(inspect.signature(JointEnvironment.evaluate).parameters)

    assert "relationships" not in parameters
    assert "relationship_state" not in parameters
    assert "coordination_exposure" not in parameters
    assert "pair_memory" not in parameters
    assert "teamwork_model" not in parameters


def test_identical_actions_and_individual_state_have_relationship_independent_outcome() -> None:
    first, second = _agents()
    mission = _mission()
    environment = JointEnvironment()
    actions = (JointAction(first.agent_id, "lead"), JointAction(second.agent_id, "support"))

    baseline = environment.evaluate(first, second, mission, *actions, seed=77)

    relationships = RelationshipStateStore()
    relationships.record(
        JointEpisode(
            mission_id="old",
            context=mission.context,
            agent_a=first.agent_id,
            action_a="support",
            agent_b=second.agent_id,
            action_b="lead",
            success=True,
        )
    )
    assert relationships.snapshot()

    repeated = environment.evaluate(first, second, mission, *actions, seed=77)
    assert repeated is baseline


def test_relationship_state_is_separable_from_individual_practice() -> None:
    first, second = _agents()
    original_first = dict(first.practice_by_skill)
    original_second = dict(second.practice_by_skill)
    relationships = RelationshipStateStore()
    relationships.record(
        JointEpisode(
            mission_id="formation-1",
            context="formation",
            agent_a=first.agent_id,
            action_a="lead",
            agent_b=second.agent_id,
            action_b="support",
            success=True,
        )
    )

    snapshot = relationships.snapshot()
    assert "practice_by_skill" not in str(snapshot)
    assert snapshot["partner_models"]
    assert snapshot["teamwork_models"]
    assert snapshot["pair_memories"]

    relationships.reset_partner_models(first.agent_id, second.agent_id)
    after_partner_reset = relationships.snapshot()
    assert after_partner_reset["partner_models"] == []
    assert after_partner_reset["teamwork_models"]
    assert after_partner_reset["pair_memories"]
    assert first.practice_by_skill == original_first
    assert second.practice_by_skill == original_second

    relationships.clear_pair_memory(first.agent_id, second.agent_id)
    after_pair_reset = relationships.snapshot()
    assert after_pair_reset["pair_memories"] == []
    assert after_pair_reset["teamwork_models"]
    assert first.practice_by_skill == original_first
    assert second.practice_by_skill == original_second

    relationships.reset_general_teamwork(first.agent_id)
    relationships.reset_general_teamwork(second.agent_id)
    after_full_reset = relationships.snapshot()
    assert after_full_reset["partner_models"] == []
    assert after_full_reset["teamwork_models"] == []
    assert after_full_reset["pair_memories"] == []
    assert first.practice_by_skill == original_first
    assert second.practice_by_skill == original_second


def test_shared_history_can_change_decisions_without_direct_success_bonus() -> None:
    first, second = _agents()
    mission = _mission()
    relationships = RelationshipStateStore()
    session = JointLearningSession(
        environment=JointEnvironment(),
        controller=JointController(),
        relationships=relationships,
        communication=CommunicationPolicy(bandwidth_bits=0),
    )

    first_episode = session.run_episode(first, second, mission, seed=1)
    assert first_episode.action_a == "lead"
    assert first_episode.action_b == "lead"
    assert first_episode.success is False

    second_episode = session.run_episode(first, second, mission, seed=2)
    assert {second_episode.action_a, second_episode.action_b} == {"lead", "support"}


def test_communication_bandwidth_is_explicit_and_matchable() -> None:
    experienced = CommunicationPolicy(bandwidth_bits=1)
    stranger = CommunicationPolicy(bandwidth_bits=1)

    assert experienced == stranger


def test_pair_memory_rejects_foreign_pair_episode() -> None:
    relationships = RelationshipStateStore()
    memory = relationships.pair_memory("agent-a", "agent-b")

    foreign = JointEpisode(
        mission_id="foreign",
        context="formation",
        agent_a="agent-a",
        action_a="lead",
        agent_b="agent-c",
        action_b="support",
        success=True,
    )

    try:
        memory.append(foreign)
    except ValueError as exc:
        assert "does not match" in str(exc)
    else:
        raise AssertionError("foreign pair episode was accepted")
