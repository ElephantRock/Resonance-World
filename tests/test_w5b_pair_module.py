import inspect

from resonance_world.w4a_joint_learning import (
    CommunicationPolicy,
    IndividualState,
    JointController,
    JointEnvironment,
    JointLearningSession,
    JointMission,
    RelationshipStateStore,
)
from resonance_world.w5b_pair_module import (
    capture_pair,
    instantiate_intact,
    instantiate_with_reset,
    replace_member,
)


def _developed_module():
    first = IndividualState("a", {"lead": 5, "support": 1})
    second = IndividualState("b", {"lead": 1, "support": 5})
    relationships = RelationshipStateStore()
    session = JointLearningSession(
        JointEnvironment(),
        JointController(),
        relationships,
        CommunicationPolicy(1),
    )
    mission = JointMission("m", "context", "lead", "support")
    for index in range(6):
        session.run_episode(first, second, mission, seed=100 + index)
    module = capture_pair(
        "module-1",
        first,
        second,
        relationships,
        source_field_ids=("field-a", "field-a"),
        formation_evidence=("evidence://formation",),
        capability_profile={"lead-support": 0.75},
        provenance=("field://checkpoint",),
    )
    return module


def test_pair_module_is_deterministic_and_content_addressable() -> None:
    first = _developed_module()
    second = _developed_module()
    assert first.canonical_bytes() == second.canonical_bytes()
    assert first.content_sha256() == second.content_sha256()
    assert len(first.content_sha256()) == 64


def test_intact_instantiation_restores_relationship_state() -> None:
    module = _developed_module()
    instance = instantiate_intact(module)
    assert instance.member_ids == ("a", "b")
    assert instance.first.practice_by_skill == {"lead": 5, "support": 1}
    assert instance.second.practice_by_skill == {"lead": 1, "support": 5}
    assert instance.relationships.partner_models
    assert instance.relationships.teamwork_models
    assert instance.relationships.pair_memories


def test_reset_holds_individual_state_fixed_and_removes_relationship_state() -> None:
    module = _developed_module()
    intact = instantiate_intact(module)
    reset = instantiate_with_reset(module)
    assert intact.first.practice_by_skill == reset.first.practice_by_skill
    assert intact.second.practice_by_skill == reset.second.practice_by_skill
    assert reset.relationships.partner_models == {}
    assert reset.relationships.teamwork_models == {}
    assert reset.relationships.pair_memories == {}


def test_member_replacement_never_relabels_old_pair_state() -> None:
    module = _developed_module()
    replacement = IndividualState("c", {"lead": 3, "support": 3})
    instance = replace_member(module, "b", replacement)
    assert instance.member_ids == ("a", "c")
    assert instance.relationships.partner_models == {}
    assert instance.relationships.pair_memories == {}
    assert set(instance.relationships.teamwork_models) <= {"a"}
    assert instance.retained_state == ("survivor_general_teamwork",)


def test_module_state_cannot_enter_environment_outcome_law() -> None:
    parameters = set(inspect.signature(JointEnvironment.evaluate).parameters)
    assert not parameters & {
        "module",
        "module_id",
        "module_history",
        "pair_module",
        "relationship_state",
        "pair_memory",
    }
