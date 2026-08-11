from __future__ import annotations

from resonance_world.w6_mobility import PortableAgentState
from resonance_world.w8_campaign import _source_frontier as reference_source_frontier
from resonance_world.w8_fastpath import exact_source_frontier


def _state(agent_id: str, **practice: int) -> PortableAgentState:
    skills = {
        "urban_heat": 0,
        "water_systems": 0,
        "energy_storage": 0,
        "supply_networks": 0,
        "public_health": 0,
        "mobility": 0,
    }
    skills.update(practice)
    return PortableAgentState(
        agent_id=agent_id,
        home_field_id="field-a",
        practice_by_skill=tuple(skills.items()),
        evidence_refs=(f"evidence:{agent_id}",),
    )


def _config(trials: int) -> dict[str, object]:
    return {
        "service_trials": trials,
        "source_service_law": {
            "base_success_probability": 0.38,
            "practice_gain": 0.14,
            "maximum_success_probability": 0.90,
        },
        "home_service_missions": [
            {"mission_id": "heat", "skill": "urban_heat"},
            {"mission_id": "water", "skill": "water_systems"},
            {"mission_id": "energy", "skill": "energy_storage"},
            {"mission_id": "supply", "skill": "supply_networks"},
            {"mission_id": "health", "skill": "public_health"},
            {"mission_id": "mobility", "skill": "mobility"},
        ],
    }


def test_exact_source_frontier_matches_trial_loop_for_non_multiple_trial_counts() -> None:
    states = [
        _state("a", urban_heat=9, energy_storage=4, mobility=1),
        _state("b", water_systems=6, supply_networks=7, public_health=2),
        _state("c", mobility=8, public_health=5),
    ]
    for trials in (1, 5, 6, 7, 127, 128, 511, 512, 513):
        config = _config(trials)
        assert exact_source_frontier(states, config) == reference_source_frontier(
            states, config
        )


def test_exact_source_frontier_matches_empty_population() -> None:
    config = _config(512)
    assert exact_source_frontier([], config) == reference_source_frontier([], config)
