import inspect

from resonance_world.w4a_joint_learning import IndividualState
from resonance_world.w5_institution import (
    InstitutionEnvironment,
    _classification,
    _field_design,
)
from resonance_world.w5a_organization import OrganizationState


def _capsule(index: int) -> dict[str, object]:
    return {
        "agent_id": f"agent-{index:02d}",
        "field_id": "field",
        "practice_by_skill": {
            "energy_storage": index,
            "supply_networks": 12 - index,
        },
    }


def test_w5_design_has_exact_turnover_controls() -> None:
    design = _field_design("field", [_capsule(index) for index in range(12)], 4)
    assert len(design.initial_members) == 4
    assert len(design.replacement_pool) == 8
    assert len(design.replacement_roster(0)) == 4
    assert len(design.replacement_roster(4)) == 4
    assert not {
        item.agent_id for item in design.initial_members
    } & {item.agent_id for item in design.replacement_roster(4)}


def test_memory_reset_holds_identity_and_replacement_roster_fixed() -> None:
    members = [
        IndividualState("a", {"x": 1}),
        IndividualState("b", {"x": 2}),
    ]
    organization = OrganizationState("org-fixed", {item.agent_id: item for item in members})
    before = set(organization.members)
    organization.reset_memory()
    assert organization.organization_id == "org-fixed"
    assert set(organization.members) == before


def test_w5_environment_is_institutional_state_blind() -> None:
    parameters = set(inspect.signature(InstitutionEnvironment.evaluate).parameters)
    assert not parameters & {
        "organization",
        "organization_id",
        "organization_memory",
        "institutional_memory",
        "organization_age",
    }


def test_w5_classification_is_preregistered() -> None:
    assert _classification(0.03, 0.02) == "institutional_memory"
    assert _classification(-0.03, 0.02) == "institutional_harm"
    assert _classification(0.01, 0.02) == "no_institutional_memory"
