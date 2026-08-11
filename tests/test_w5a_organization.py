import inspect

from resonance_world.w4a_joint_learning import (
    IndividualState,
    JointMission,
    RelationshipStateStore,
)
from resonance_world.w5a_organization import (
    OrganizationController,
    OrganizationEnvironment,
    OrganizationEpisode,
    OrganizationState,
)


def _agent(agent_id: str, lead: int, support: int) -> IndividualState:
    return IndividualState(agent_id, {"lead-skill": lead, "support-skill": support})


def _mission() -> JointMission:
    return JointMission("mission", "context", "lead-skill", "support-skill")


def test_full_roster_replacement_preserves_identity_and_memory() -> None:
    original = [_agent("a", 5, 1), _agent("b", 1, 5)]
    organization = OrganizationState("org-1", {item.agent_id: item for item in original})
    organization.memory.observe(
        OrganizationEpisode("m", "context", "specialist", "a", "b", True)
    )
    before = organization.memory.snapshot()
    organization.replace_members([_agent("c", 4, 2), _agent("d", 2, 4)])
    assert organization.organization_id == "org-1"
    assert set(organization.members) == {"c", "d"}
    assert organization.memory.snapshot() == before


def test_organization_reset_does_not_change_individual_or_pair_state() -> None:
    first = _agent("a", 5, 1)
    second = _agent("b", 1, 5)
    organization = OrganizationState("org-1", {"a": first, "b": second})
    organization.memory.observe(
        OrganizationEpisode("m", "context", "specialist", "a", "b", True)
    )
    relationships = RelationshipStateStore()
    pair_before = relationships.snapshot()
    practice_before = {
        key: dict(value.practice_by_skill) for key, value in organization.members.items()
    }
    organization.reset_memory()
    assert organization.memory.snapshot()["episode_count"] == 0
    assert relationships.snapshot() == pair_before
    assert {
        key: dict(value.practice_by_skill) for key, value in organization.members.items()
    } == practice_before


def test_retained_procedure_changes_routing_on_new_roster() -> None:
    roster = [
        _agent("special-lead", 9, 0),
        _agent("special-support", 0, 9),
        _agent("general-1", 7, 7),
        _agent("general-2", 6, 6),
    ]
    controller = OrganizationController()
    mission = _mission()
    organization = OrganizationState("org-routing-3", {item.agent_id: item for item in roster})

    for index in range(3):
        organization.memory.observe(
            OrganizationEpisode(
                f"history-{index}",
                mission.context,
                "balanced",
                "retired-a",
                "retired-b",
                True,
            )
        )
    decision = controller.select(organization, mission)
    assert decision.strategy == "balanced"
    assert {decision.lead.agent_id, decision.support.agent_id} == {
        "general-1",
        "general-2",
    }

    organization.reset_memory()
    reset = controller.select(organization, mission)
    assert reset.strategy == "specialist"
    assert {reset.lead.agent_id, reset.support.agent_id} == {
        "special-lead",
        "special-support",
    }


def test_environment_is_organization_memory_blind() -> None:
    parameters = set(inspect.signature(OrganizationEnvironment.evaluate).parameters)
    assert not parameters & {
        "organization",
        "organization_id",
        "organization_memory",
        "institutional_memory",
        "organization_age",
    }
