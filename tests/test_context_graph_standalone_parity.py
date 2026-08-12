"""Parity gates for the standalone Resonance ContextGraph extraction."""

from __future__ import annotations

import inspect
from collections import defaultdict

import pytest

pytest.importorskip("resonance_contextgraph")

from experiments.context_graph.run_cg4m_measurement_sufficiency import (
    EstimatorSpec as WorldEstimatorSpec,
)
from experiments.context_graph.run_cg4m_measurement_sufficiency import (
    _canonical_event_bundles,
    _coverage_graph_context,
)
from experiments.context_graph.run_cg6_adaptive_acquisition import (
    choose_cell,
    pair_from_context,
)
from experiments.context_graph.run_cg10_balanced_stopping import choose_stop
from resonance_world.context_graph_adapter import (
    choose_stopping_point,
    compile_live_context,
    next_balanced_cell,
    pair_from_live_context,
)
from resonance_world.context_graph_w3_endogenous import (
    CG4Mission,
    EndogenousField,
    LiveClaim,
    _membership_candidates,
)


def _membership(field_id: str, agent_id: str, *, active: bool = True, time: int = 0) -> LiveClaim:
    state = "active" if active else "departed"
    return LiveClaim(
        field_id=field_id,
        subject=agent_id,
        predicate="membership_state",
        object=state,
        observed_by="registry",
        source_id=f"membership:{field_id}:{time}:{agent_id}:{state}",
        source_class="membership",
        observed_at=time,
        confidence=0.99,
        direct=True,
    )


def _probe_bundle(
    field_id: str,
    event_id: str,
    agent_id: str,
    skill: str,
    success: bool,
    *,
    observer: str,
    time: int,
    confidence: float,
) -> list[LiveClaim]:
    outcome = "success" if success else "failure"
    return [
        LiveClaim(
            field_id=field_id,
            subject=event_id,
            predicate=predicate,
            object=value,
            observed_by=observer,
            source_id=f"{event_id}:{observer}:{predicate}",
            source_class="live_probe",
            observed_at=time,
            confidence=confidence,
            direct=True,
        )
        for predicate, value in (
            ("participant", agent_id),
            ("skill", skill),
            ("outcome", outcome),
        )
    ]


def _fixture() -> tuple[EndogenousField, CG4Mission]:
    field_id = "parity-field"
    agents = ["agent-a", "agent-b", "agent-c", "agent-d"]
    skills = ["lead-skill", "support-skill"]
    claims: list[LiveClaim] = [_membership(field_id, agent) for agent in agents]

    # More relevant complete events than fit the 48-claim context budget, with
    # duplicate observers and deterministic conflicts on a subset. Participant
    # reports have higher confidence and therefore remain the canonical event.
    time = 1
    for agent_index, agent in enumerate(agents):
        for skill_index, skill in enumerate(skills):
            for event_index in range(5):
                event_id = f"probe:{field_id}:{agent}:{skill}:{event_index}"
                success = (agent_index + skill_index + event_index) % 3 != 0
                claims.extend(
                    _probe_bundle(
                        field_id,
                        event_id,
                        agent,
                        skill,
                        success,
                        observer=agent,
                        time=time,
                        confidence=0.95,
                    )
                )
                scout = agents[(agent_index + 1) % len(agents)]
                scout_success = not success if event_index == 1 else success
                claims.extend(
                    _probe_bundle(
                        field_id,
                        event_id,
                        agent,
                        skill,
                        scout_success,
                        observer=scout,
                        time=time,
                        confidence=0.45 if event_index == 1 else 0.85,
                    )
                )
                time += 1

    # A stale/departed member must not survive the temporal membership projection.
    claims.append(_membership(field_id, "agent-z", time=0))
    claims.append(_membership(field_id, "agent-z", active=False, time=time + 1))

    field = EndogenousField(
        field_id=field_id,
        states={},
        claims=tuple(claims),
        belief_snapshot={},
        current_members=frozenset(agents),
        departed_members=frozenset({"agent-z"}),
        coordinator_id="agent-a",
        as_of=time + 2,
        emitted_claims=len(claims),
        duplicate_observation_groups=0,
        conflicting_observation_groups=0,
        low_confidence_claims=0,
    )
    mission = CG4Mission(
        mission_id="parity-mission",
        lead_skill="lead-skill",
        support_skill="support-skill",
    )
    return field, mission


def _world_spec() -> WorldEstimatorSpec:
    return WorldEstimatorSpec(
        name="wilson80_min3",
        kind="wilson_lower",
        min_support=3,
        fallback_score=0.35,
        z=1.2815515655446004,
    )


def test_standalone_compiler_matches_frozen_world_coverage_semantics() -> None:
    field, mission = _fixture()
    spec = _world_spec()
    world_context = _coverage_graph_context(
        field,
        mission,
        budget=48,
        estimator=spec,
        min_confidence=0.7,
    )
    world_pair, _world_evidence = pair_from_context(world_context, mission, spec, 0.7)
    world_candidates = _membership_candidates(
        world_context,
        min_confidence=0.7,
        respect_temporal_order=True,
    )
    world_event_ids = {
        bundle[0]
        for bundle in _canonical_event_bundles(world_context, min_confidence=0.7)
    }

    standalone_pair, standalone = pair_from_live_context(
        claims=field.claims,
        field_id=field.field_id,
        as_of=field.as_of,
        mission=mission,
        claim_budget=48,
        min_confidence=0.7,
    )
    standalone_event_ids = {event.event_id for event in standalone.events}

    assert standalone.candidates == frozenset(world_candidates)
    assert standalone.claim_cost == len(world_context) == 46
    assert standalone_event_ids == world_event_ids
    assert standalone_pair == world_pair
    assert standalone.provenance_complete
    assert "agent-z" not in standalone.candidates


def test_standalone_reconciliation_matches_world_event_identity_and_canonical_report() -> None:
    field, mission = _fixture()
    standalone = compile_live_context(
        claims=field.claims,
        field_id=field.field_id,
        as_of=field.as_of,
        mission=mission,
        claim_budget=48,
        min_confidence=0.7,
    )
    world_context = _coverage_graph_context(
        field,
        mission,
        budget=48,
        estimator=_world_spec(),
        min_confidence=0.7,
    )
    world = {
        event_id: (agent_id, skill, confidence)
        for event_id, _observer, agent_id, skill, confidence, _time, _claims
        in _canonical_event_bundles(world_context, min_confidence=0.7)
    }
    standalone_rows = {
        event.event_id: (event.participant, event.skill, event.confidence)
        for event in standalone.events
    }
    assert standalone_rows == world
    assert all(event.observer_count >= 1 for event in standalone.events)


def test_balanced_round_robin_next_cell_matches_world_policy() -> None:
    field, mission = _fixture()
    spec = _world_spec()
    available_cells = {
        (agent, skill): object()
        for agent in sorted(field.current_members)
        for skill in mission.required_skills
    }
    # Reconstruct the observable independent-event counts exactly as the frozen
    # World policy sees them after event reconciliation.
    counts: dict[tuple[str, str], int] = defaultdict(int)
    for bundle in _canonical_event_bundles(field.claims, min_confidence=0.7):
        _event, _observer, agent_id, skill, *_rest = bundle
        if (agent_id, skill) in available_cells:
            counts[(agent_id, skill)] += 1
    counts[("agent-c", "lead-skill")] -= 1

    # Remove one final event bundle from the World claims for the deliberately
    # under-measured cell so both policies see the same observable counts.
    removed_event = "probe:parity-field:agent-c:lead-skill:4"
    claims = [claim for claim in field.claims if claim.subject != removed_event]
    world_choice = choose_cell(
        policy="uniform_round_robin",
        field=field,
        claims=claims,
        available=available_cells,  # type: ignore[arg-type]
        mission_rows=[mission],
        spec=spec,
        min_confidence=0.7,
        weights={
            "selected_role_bonus": 0.0,
            "plausible_challenger_bonus": 0.0,
            "support_deficit_bonus": 0.0,
            "ambiguity_margin": 0.0,
        },
    )
    standalone_choice = next_balanced_cell(
        field_id=field.field_id,
        available=available_cells,
        reconciled_event_counts=counts,
    )
    assert standalone_choice == world_choice == ("agent-c", "lead-skill")


def test_pair_stability_stopper_matches_frozen_world_rule() -> None:
    history = [
        {"budget": 48, "pair_vector": ("a::b", "c::d")},
        {"budget": 60, "pair_vector": ("a::c", "c::d")},
        {"budget": 72, "pair_vector": ("a::b", "c::d")},
        {"budget": 96, "pair_vector": ("a::b", "c::d")},
        {"budget": 120, "pair_vector": ("a::b", "c::d")},
        {"budget": 144, "pair_vector": ("a::b", "c::d")},
        {"budget": 168, "pair_vector": ("a::b", "c::d")},
    ]
    world_budget, world_reason = choose_stop(
        [
            {
                **row,
                "minimum_selected_role_event_support": 0,
                "minimum_selected_role_score_margin": 0.0,
            }
            for row in history
        ],
        {
            "stable_checkpoint_count": 2,
            "minimum_selected_role_event_support": 0,
            "minimum_selected_role_score_margin": 0.0,
        },
        minimum_budget=60,
    )
    standalone = choose_stopping_point(
        (row["budget"], row["pair_vector"]) for row in history
    )
    assert standalone.stop
    assert standalone.budget == world_budget == 96
    assert standalone.reason == "pair_stability"
    assert world_reason == "criterion"


def test_world_adapter_cannot_cross_hidden_state_or_outcome_law_boundary() -> None:
    import resonance_world.context_graph_adapter as adapter

    source = inspect.getsource(adapter)
    assert ".states" not in source
    assert "practice_by_skill" not in source
    assert "JointEnvironment" not in source
    assert "_oracle_pair" not in source
