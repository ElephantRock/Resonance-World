from __future__ import annotations

from resonance_world.w3_swarm_core import _team_probability


def test_coordination_exposure_adds_relationship_capital() -> None:
    config = {
        "destination_law": {
            "base_success_probability": 0.30,
            "practice_gain": 0.10,
            "maximum_success_probability": 0.88,
            "coordination_gain": 0.05,
            "maximum_coordination_bonus": 0.12,
            "team_overhead_penalty": 0.01,
            "team_maximum_success_probability": 0.94,
        }
    }
    mission = {"mission": "m", "requirements": {"alpha": 0.5, "beta": 0.5}}
    first = {"alpha": 9.0, "beta": 0.0}
    second = {"alpha": 0.0, "beta": 9.0}

    unrelated = _team_probability(first, second, 0.0, mission, config)
    related = _team_probability(first, second, 4.0, mission, config)

    assert related > unrelated
    assert related - unrelated >= 0.09
