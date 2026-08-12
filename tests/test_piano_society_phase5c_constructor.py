from resonance_world.w4a_joint_learning import IndividualState
from resonance_world.w5_institution import FieldDesign

from experiments.piano_society.phase5c_constructor import (
    _candidate,
    _choose_distinct_fields,
)


ELIGIBILITY = {
    "require_distinct_ordered_policy_assignments": True,
    "min_role_specific_specialist_advantage": 0.02,
    "min_cross_coverage_balanced_advantage": 0.02,
    "min_neutral_forecast_margin": 0.0005,
    "min_formation_hypothesis_identifiability": 0.005,
}


def _state(agent_id: str, lead: int, support: int) -> IndividualState:
    return IndividualState(
        agent_id,
        {
            "lead-skill": lead,
            "support-skill": support,
            "other-a": 0,
            "other-b": 0,
            "other-c": 0,
            "other-d": 0,
        },
    )


def _geometry_design() -> FieldDesign:
    # Initial and replacement rosters both contain role specialists plus two
    # generalists. Specialist routing selects the role specialists; balanced
    # routing selects the two generalists, creating a genuine policy boundary.
    initial = (
        _state("i-lead", 9, 0),
        _state("i-support", 0, 9),
        _state("i-general-1", 4, 4),
        _state("i-general-2", 4, 4),
    )
    replacement = (
        _state("r-lead", 9, 0),
        _state("r-support", 0, 9),
        _state("r-general-1", 4, 4),
        _state("r-general-2", 4, 4),
        _state("unused-1", 1, 1),
        _state("unused-2", 1, 1),
        _state("unused-3", 1, 1),
        _state("unused-4", 1, 1),
    )
    return FieldDesign("synthetic-field", initial, replacement)


def test_constructor_requires_real_policy_geometry_and_opposes_neutral_preference() -> None:
    candidate = _candidate(
        _geometry_design(),
        lead_skill="lead-skill",
        support_skill="support-skill",
        eligibility=ELIGIBILITY,
    )
    assert candidate is not None
    assert candidate["replacement_policy_assignments"]["specialist"] == {
        "lead_agent_id": "r-lead",
        "support_agent_id": "r-support",
    }
    balanced = candidate["replacement_policy_assignments"]["balanced"]
    assert {balanced["lead_agent_id"], balanced["support_agent_id"]} == {
        "r-general-1",
        "r-general-2",
    }
    assert candidate["role_specific_specialist_advantage"] >= 0.02
    assert candidate["cross_coverage_balanced_advantage"] >= 0.02
    assert candidate["neutral_preferred_policy"] == "specialist"
    assert candidate["target_hypothesis"] == "cross_coverage"
    assert candidate["target_policy"] == "balanced"
    assert candidate["hidden_regime"] == "balanced"


def test_constructor_rejects_policy_equivalence() -> None:
    all_generalists = tuple(
        _state(f"i-{index}", 4, 4) for index in range(4)
    )
    replacement = tuple(
        _state(f"r-{index}", 4, 4) for index in range(8)
    )
    design = FieldDesign("equivalent-field", all_generalists, replacement)
    assert (
        _candidate(
            design,
            lead_skill="lead-skill",
            support_skill="support-skill",
            eligibility=ELIGIBILITY,
        )
        is None
    )


def _option(field_id: str, target: str, score: float):
    return {
        "field_id": field_id,
        "target_hypothesis": target,
        "lead_skill": f"lead-{field_id}-{target}",
        "support_skill": f"support-{field_id}-{target}",
        "constructor_score": score,
        "decision_leverage": score,
        "formation_hypothesis_identifiability": score,
        "neutral_forecast_margin": score,
    }


def test_balanced_field_selection_is_distinct_and_deterministic() -> None:
    options = {
        "field-a": {
            "role_specific": [_option("field-a", "role_specific", 0.9)],
            "cross_coverage": [_option("field-a", "cross_coverage", 0.1)],
        },
        "field-b": {
            "role_specific": [_option("field-b", "role_specific", 0.8)],
            "cross_coverage": [_option("field-b", "cross_coverage", 0.7)],
        },
        "field-c": {
            "role_specific": [_option("field-c", "role_specific", 0.2)],
            "cross_coverage": [_option("field-c", "cross_coverage", 0.95)],
        },
        "field-d": {
            "role_specific": [_option("field-d", "role_specific", 0.1)],
            "cross_coverage": [_option("field-d", "cross_coverage", 0.85)],
        },
    }
    selected = _choose_distinct_fields(options, role_count=2, cross_count=2)
    assert len(selected) == 4
    assert len({row["field_id"] for row in selected}) == 4
    assert sum(row["target_hypothesis"] == "role_specific" for row in selected) == 2
    assert sum(row["target_hypothesis"] == "cross_coverage" for row in selected) == 2
    assert [(row["field_id"], row["target_hypothesis"]) for row in selected] == [
        ("field-a", "role_specific"),
        ("field-b", "role_specific"),
        ("field-c", "cross_coverage"),
        ("field-d", "cross_coverage"),
    ]
