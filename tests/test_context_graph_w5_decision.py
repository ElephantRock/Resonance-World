from __future__ import annotations

import inspect

from resonance_world.context_graph_w5_decision import (
    DecisionCase,
    DecisionClaim,
    _select_pair,
    _shuffle_skill_edges,
)
from resonance_world.w4a_joint_learning import JointEnvironment, JointMission


def _case() -> DecisionCase:
    return DecisionCase(
        decision_id="field:test:mission",
        field_id="field:test",
        decision_node="decision:test",
        field_node="field:field:test",
        mission=JointMission("m", "ctx", "lead_skill", "support_skill"),
        as_of=13,
    )


def test_temporal_filter_prevents_departed_high_skill_selection() -> None:
    case = _case()
    claims = (
        DecisionClaim(
            "field:test",
            "current-a",
            "available_in",
            case.field_node,
            "availability:a",
            "availability",
            12,
            valid_from=12,
        ),
        DecisionClaim(
            "field:test",
            "current-b",
            "available_in",
            case.field_node,
            "availability:b",
            "availability",
            12,
            valid_from=12,
        ),
        DecisionClaim(
            "field:test",
            "departed",
            "available_in",
            case.field_node,
            "availability:departed",
            "availability",
            0,
            valid_from=0,
            valid_until=12,
        ),
        DecisionClaim(
            "field:test",
            "current-a",
            "demonstrated_skill",
            "skill:lead_skill",
            "skill:a",
            "field_outcome_summary",
            1,
            strength=2,
        ),
        DecisionClaim(
            "field:test",
            "current-b",
            "demonstrated_skill",
            "skill:support_skill",
            "skill:b",
            "field_outcome_summary",
            1,
            strength=2,
        ),
        DecisionClaim(
            "field:test",
            "departed",
            "demonstrated_skill",
            "skill:lead_skill",
            "skill:departed",
            "field_outcome_summary",
            1,
            strength=20,
        ),
    )

    temporal = _select_pair(
        claims,
        case,
        min_confidence=0.7,
        respect_temporal_validity=True,
    )
    stale = _select_pair(
        claims,
        case,
        min_confidence=0.7,
        respect_temporal_validity=False,
    )

    assert temporal == ("current-a", "current-b")
    assert stale is not None
    assert "departed" in stale


def test_shuffled_control_preserves_provenance_and_changes_skill_topology() -> None:
    claims = (
        DecisionClaim(
            "field:test",
            "a",
            "demonstrated_skill",
            "skill:x",
            "source:a",
            "field_outcome_summary",
            1,
        ),
        DecisionClaim(
            "field:test",
            "b",
            "demonstrated_skill",
            "skill:y",
            "source:b",
            "field_outcome_summary",
            1,
        ),
        DecisionClaim(
            "field:test",
            "c",
            "demonstrated_skill",
            "skill:z",
            "source:c",
            "field_outcome_summary",
            1,
        ),
    )
    shuffled = _shuffle_skill_edges(claims)
    assert len(shuffled) == len(claims)
    assert {claim.source_id for claim in shuffled} == {claim.source_id for claim in claims}
    assert [claim.object for claim in shuffled] != [claim.object for claim in claims]


def test_environment_outcome_law_has_no_graph_state_inputs() -> None:
    parameters = set(inspect.signature(JointEnvironment.evaluate).parameters)
    forbidden = {
        "graph",
        "context_graph",
        "evidence",
        "provenance",
        "confidence",
        "temporal_state",
    }
    assert not parameters & forbidden
