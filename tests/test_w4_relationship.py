from resonance_world.w4_relationship import (
    _classification,
    _field_design,
    _pair_specific_reset,
    _train,
)
from resonance_world.w4a_joint_learning import CommunicationPolicy, JointMission


def _rows(field_id: str = "w4-source-seed-1") -> list[dict[str, object]]:
    skills = [
        "urban_heat",
        "water_systems",
        "energy_storage",
        "supply_networks",
        "public_health",
        "mobility",
    ]
    return [
        {
            "agent_id": f"agent-{index:02d}",
            "field_id": field_id,
            "practice_by_skill": {
                skill: (index + skill_index) % 7
                for skill_index, skill in enumerate(skills)
            },
        }
        for index in range(12)
    ]


def test_c1_and_c2_use_identical_experienced_agents_but_different_pairs() -> None:
    design = _field_design("w4-source-seed-1", _rows())

    original_agents = {
        agent.agent_id for pair in design.original_pairs for agent in pair
    }
    rotated_agents = {
        agent.agent_id for pair in design.rotated_pairs for agent in pair
    }
    original_pairs = {
        frozenset((first.agent_id, second.agent_id))
        for first, second in design.original_pairs
    }
    rotated_pairs = {
        frozenset((first.agent_id, second.agent_id))
        for first, second in design.rotated_pairs
    }

    assert original_agents == rotated_agents
    assert original_pairs.isdisjoint(rotated_pairs)
    assert len(original_agents) == 6


def test_treatment_assignment_is_fixed_without_outcomes() -> None:
    first = _field_design("w4-source-seed-1", _rows())
    second = _field_design("w4-source-seed-1", list(reversed(_rows())))

    assert [agent.agent_id for agent in first.treated_agents] == [
        agent.agent_id for agent in second.treated_agents
    ]
    assert [agent.agent_id for agent in first.control_agents] == [
        agent.agent_id for agent in second.control_agents
    ]


def test_pair_specific_reset_preserves_general_teamwork_state() -> None:
    design = _field_design("w4-source-seed-1", _rows())
    mission = JointMission(
        "formation",
        "allocation-a",
        "urban_heat",
        "water_systems",
    )
    trained = _train(
        design,
        [mission],
        2,
        CommunicationPolicy(bandwidth_bits=1),
    )
    reset = _pair_specific_reset(trained, design.original_pairs)
    snapshot = reset.snapshot()

    assert snapshot["teamwork_models"]
    for first, second in design.original_pairs:
        assert reset.partner_model(first.agent_id, second.agent_id).predict(mission.context) is None
        assert reset.pair_memory(first.agent_id, second.agent_id).episodes == []


def test_w4_classification_map_distinguishes_both_effects() -> None:
    threshold = 0.02

    assert _classification(0.03, 0.00, threshold) == "partner_specific"
    assert _classification(0.00, 0.03, threshold) == "general_teamwork"
    assert _classification(0.03, 0.03, threshold) == "both"
    assert _classification(0.01, 0.01, threshold) == "neither"
