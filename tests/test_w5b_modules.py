import inspect

from resonance_world.w4a_joint_learning import IndividualState, JointEnvironment, JointMission
from resonance_world.w5b_modules import (
    FieldDesign,
    ModuleMission,
    _classification,
    _develop_modules,
    _replication_requirement,
    _w5b_02,
    _w5b_03,
    _w5b_04,
)


def _design() -> FieldDesign:
    skills = [
        "energy_storage",
        "supply_networks",
        "public_health",
        "water_systems",
        "urban_heat",
        "mobility",
    ]
    agents = []
    for index in range(12):
        practice = {skill: (index + offset) % 7 for offset, skill in enumerate(skills)}
        agents.append(IndividualState(f"agent-{index:02d}", practice))
    return FieldDesign("field-test", tuple(agents))


def _missions() -> list[ModuleMission]:
    return [
        ModuleMission(
            "storage-grid",
            JointMission("f1", "storage-grid", "energy_storage", "supply_networks"),
            JointMission("e1", "storage-grid", "energy_storage", "supply_networks"),
        ),
        ModuleMission(
            "clinic-water",
            JointMission("f2", "clinic-water", "public_health", "water_systems"),
            JointMission("e2", "clinic-water", "public_health", "water_systems"),
        ),
        ModuleMission(
            "heat-mobility",
            JointMission("f3", "heat-mobility", "urban_heat", "mobility"),
            JointMission("e3", "heat-mobility", "urban_heat", "mobility"),
        ),
    ]


def _campaign() -> dict[str, object]:
    return {
        "formation_depth": 3,
        "evaluation_trials_per_mission": 8,
        "communication_bandwidth_bits": 1,
        "module_pair_slots": [[0, 1], [2, 3], [4, 5]],
        "replacement_slots": [6, 7, 8],
        "library_sizes": [0, 1, 2, 3],
    }


def test_w5b_succession_keeps_old_pair_state_out_of_new_pair() -> None:
    design = _design()
    missions = _missions()
    campaign = _campaign()
    modules = _develop_modules(design, missions, campaign)
    result = _w5b_02(design, modules, missions, campaign)
    for row in result["rows"]:
        assert row["retained_state"] == ["survivor_general_teamwork"]


def test_cross_module_composition_has_no_inter_module_state() -> None:
    design = _design()
    missions = _missions()
    campaign = _campaign()
    modules = _develop_modules(design, missions, campaign)
    result = _w5b_03(design, modules, missions, campaign)
    assert result["inter_module_state"] == "absent_by_design"


def test_module_library_holds_agent_count_fixed() -> None:
    design = _design()
    missions = _missions()
    campaign = _campaign()
    modules = _develop_modules(design, missions, campaign)
    result = _w5b_04(design, modules, missions, campaign)
    assert result["fixed_agent_count"] == 6
    assert sorted(map(int, result["library_curve"])) == [0, 1, 2, 3]


def test_classification_and_replication_rules_are_preregistered() -> None:
    assert _classification(0.03, 0.02) == "positive"
    assert _classification(-0.03, 0.02) == "negative"
    assert _classification(0.01, 0.02) == "null"
    assert _replication_requirement("positive", 0.03, [0.01, 0.02, 0.03], 0.02, 2)
    assert _replication_requirement("null", 0.01, [0.03, -0.01, 0.01], 0.02, 2)


def test_joint_environment_remains_module_state_blind() -> None:
    parameters = set(inspect.signature(JointEnvironment.evaluate).parameters)
    assert not parameters & {
        "module",
        "module_id",
        "module_library",
        "module_history",
        "organization",
        "institutional_memory",
    }
