from __future__ import annotations

import inspect
import json
from pathlib import Path

from resonance_world.context_graph_w3_endogenous import (
    CG4Mission,
    LiveClaim,
    _membership_candidates,
    build_endogenous_field,
    diagnostics,
    evaluate_fields,
)
from resonance_world.w4a_joint_learning import JointEnvironment

SKILLS = (
    "energy_storage",
    "mobility",
    "public_health",
    "supply_networks",
    "urban_heat",
    "water_systems",
)


def _capsules(path: Path) -> Path:
    rows = []
    for index in range(12):
        rows.append(
            {
                "agent_id": f"agent-{index:02d}",
                "field_id": "field-test",
                "practice_by_skill": {
                    skill: (index + skill_index) % 7
                    for skill_index, skill in enumerate(SKILLS)
                },
            }
        )
    target = path / "capsules.private.jsonl"
    target.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    return target


def _field(tmp_path: Path):
    return build_endogenous_field(
        capsules_path=_capsules(tmp_path),
        field_id="field-test",
        initial_roster_size=8,
        turnover_count=4,
        probes_per_skill=2,
        skills_per_agent=3,
        noise_rate=1.0,
        rumor_count=2,
    )


def test_evidence_is_emitted_online_and_contains_live_noise(tmp_path: Path) -> None:
    field = _field(tmp_path)
    classes = {claim.source_class for claim in field.claims}
    assert classes == {"live_probe", "membership", "rumor"}
    assert field.duplicate_observation_groups > 0
    assert field.conflicting_observation_groups > 0
    assert field.low_confidence_claims > 0
    diag = diagnostics([field])
    assert diag["posthoc_imported_claims"] == 0
    assert diag["historical_outcome_rows_consumed"] == 0


def test_temporal_and_confidence_filters_prevent_departed_reactivation() -> None:
    claims = (
        LiveClaim(
            field_id="f",
            subject="agent-a",
            predicate="membership_state",
            object="active",
            observed_by="registry",
            source_id="join",
            source_class="membership",
            observed_at=1,
            confidence=0.99,
        ),
        LiveClaim(
            field_id="f",
            subject="agent-a",
            predicate="membership_state",
            object="departed",
            observed_by="registry",
            source_id="leave",
            source_class="membership",
            observed_at=2,
            confidence=0.99,
        ),
        LiveClaim(
            field_id="f",
            subject="agent-a",
            predicate="membership_state",
            object="active",
            observed_by="rumor",
            source_id="rumor",
            source_class="rumor",
            observed_at=3,
            confidence=0.35,
            direct=False,
        ),
    )
    assert _membership_candidates(
        claims,
        min_confidence=0.7,
        respect_temporal_order=True,
    ) == set()
    assert _membership_candidates(
        claims,
        min_confidence=0.7,
        respect_temporal_order=False,
    ) == {"agent-a"}
    assert _membership_candidates(
        claims,
        min_confidence=0.0,
        respect_temporal_order=True,
    ) == {"agent-a"}


def test_retrieval_preserves_beliefs_and_outcome_law_boundary(tmp_path: Path) -> None:
    field = _field(tmp_path)
    before = field.belief_snapshot
    metrics = evaluate_fields(
        [field],
        [CG4Mission("mission", "urban_heat", "water_systems")],
        context_budget=48,
        min_confidence=0.7,
        evaluation_trials=8,
    )
    assert field.belief_snapshot == before
    for arm in (
        "pooled_flat",
        "endogenous_graph",
        "shuffled_graph",
        "stale_graph",
        "conflicted_graph",
    ):
        assert metrics[arm].mean_context_claims == 48.0
        assert metrics[arm].provenance_completeness == 1.0
    parameters = inspect.signature(JointEnvironment.evaluate).parameters
    assert "graph" not in parameters
    assert "evidence" not in parameters
    assert "context_graph" not in parameters
