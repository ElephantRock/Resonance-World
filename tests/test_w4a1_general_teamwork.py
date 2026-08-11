import inspect

from resonance_world.w4a_joint_learning import (
    CommunicationPolicy,
    IndividualState,
    JointController,
    JointEnvironment,
    JointEpisode,
    JointMission,
    RelationshipStateStore,
)


def _mission() -> JointMission:
    return JointMission(
        mission_id="transfer-novel-001",
        context="role-allocation",
        lead_skill="planning",
        support_skill="verification",
    )


def test_general_teamwork_transfers_decision_state_to_new_partner() -> None:
    experienced = IndividualState("z-agent", {"planning": 9, "verification": 1})
    old_partner = IndividualState("old-agent", {"planning": 1, "verification": 9})
    stranger = IndividualState("a-agent", {"planning": 9, "verification": 1})
    mission = _mission()
    controller = JointController()
    communication = CommunicationPolicy(bandwidth_bits=0)

    fresh = RelationshipStateStore()
    fresh_action = controller.choose_action(
        experienced,
        stranger,
        mission,
        fresh,
        communication,
    )
    assert fresh_action.role == "lead"

    trained = RelationshipStateStore()
    trained.record(
        JointEpisode(
            mission_id="formation-success",
            context=mission.context,
            agent_a=experienced.agent_id,
            action_a="support",
            agent_b=old_partner.agent_id,
            action_b="lead",
            success=True,
        )
    )
    assert trained.pair_memory(experienced.agent_id, stranger.agent_id).episodes == []
    stranger_prediction = trained.partner_model(
        experienced.agent_id, stranger.agent_id
    ).predict(mission.context)
    assert stranger_prediction is None

    transferred_action = controller.choose_action(
        experienced,
        stranger,
        mission,
        trained,
        communication,
    )
    assert transferred_action.role == "support"


def test_general_teamwork_reset_is_independent() -> None:
    first = IndividualState("agent-a", {"planning": 8, "verification": 2})
    second = IndividualState("agent-b", {"planning": 2, "verification": 8})
    before_first = dict(first.practice_by_skill)
    before_second = dict(second.practice_by_skill)
    relationships = RelationshipStateStore()
    relationships.record(
        JointEpisode(
            mission_id="formation",
            context="role-allocation",
            agent_a=first.agent_id,
            action_a="lead",
            agent_b=second.agent_id,
            action_b="support",
            success=True,
        )
    )

    assert relationships.snapshot()["teamwork_models"]
    relationships.reset_general_teamwork(first.agent_id)
    snapshot = relationships.snapshot()

    assert all(
        row["owner_agent_id"] != first.agent_id for row in snapshot["teamwork_models"]
    )
    assert snapshot["partner_models"]
    assert snapshot["pair_memories"]
    assert first.practice_by_skill == before_first
    assert second.practice_by_skill == before_second


def test_environment_remains_blind_to_general_teamwork_state() -> None:
    parameters = set(inspect.signature(JointEnvironment.evaluate).parameters)

    assert "teamwork_model" not in parameters
    assert "teamwork_state" not in parameters
    assert "relationship_state" not in parameters
    assert "coordination_exposure" not in parameters


def test_general_teamwork_snapshot_contains_no_individual_practice() -> None:
    relationships = RelationshipStateStore()
    relationships.teamwork_model("agent-a").observe(
        "role-allocation", "support", "lead", True
    )

    snapshot = relationships.snapshot()
    assert snapshot["teamwork_models"]
    assert "practice_by_skill" not in str(snapshot)
