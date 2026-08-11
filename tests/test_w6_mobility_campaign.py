from __future__ import annotations

import json
from pathlib import Path

import pytest

from resonance_world.w4a_joint_learning import IndividualState
from resonance_world.w6_mobility_campaign import (
    _classify,
    _expected_probability,
    _public_score,
    run_phase,
)

SKILLS = [
    "urban_heat",
    "water_systems",
    "energy_storage",
    "supply_networks",
    "public_health",
    "mobility",
]
DISCOVERY_SEEDS = [191, 313, 437, 559, 683, 809]


def _candidate(field_id: str, agent_id: str, index: int) -> dict[str, object]:
    return {
        "agent_id": agent_id,
        "field_id": field_id,
        "checkpoint_id": f"checkpoint-{field_id}",
        "seed": 0,
        "source_evidence_sha256": f"evidence-{field_id}-{index}",
        "public_features": {
            "bid_count": 10.0 + index,
            "bid_win_rate": 0.20 + 0.02 * (index % 5),
            "completed_tasks": 4.0 + index,
            "home_success_rate": 0.35 + 0.02 * (index % 6),
            "mean_bid_confidence": 0.45 + 0.01 * index,
            "request_count": 5.0,
            "skill_concentration": 0.4,
            "skill_entropy": 0.7,
            "task_domain_concentration": 0.4,
            "win_share": 0.15,
        },
        "public_mission_profile": {
            "dominant_success_skill": SKILLS[index % len(SKILLS)],
            "secondary_success_skill": SKILLS[(index + 1) % len(SKILLS)],
        },
    }


def _capsule(field_id: str, agent_id: str, index: int) -> dict[str, object]:
    return {
        "agent_id": agent_id,
        "field_id": field_id,
        "checkpoint_id": f"checkpoint-{field_id}",
        "practice_by_skill": {
            skill: 1 + ((index + skill_index) % 6)
            for skill_index, skill in enumerate(SKILLS)
        },
    }


def _write_sources(tmp_path: Path) -> tuple[Path, Path]:
    candidates: list[dict[str, object]] = []
    capsules: list[dict[str, object]] = []
    for seed in DISCOVERY_SEEDS:
        field_id = f"w4-source-seed-{seed}"
        for index in range(12):
            agent_id = f"agent-{seed}-{index:02d}"
            candidates.append(_candidate(field_id, agent_id, index))
            capsules.append(_capsule(field_id, agent_id, index))
    candidates_path = tmp_path / "candidates.jsonl"
    capsules_path = tmp_path / "capsules.jsonl"
    candidates_path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in candidates)
    )
    capsules_path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in capsules)
    )
    return candidates_path, capsules_path


def test_probability_law_reuses_practice_without_mobility_inputs() -> None:
    state = IndividualState("agent", {"water_systems": 4, "public_health": 1})
    law = {
        "base_success_probability": 0.38,
        "practice_gain": 0.14,
        "maximum_success_probability": 0.90,
    }
    value = _expected_probability(
        state,
        {"water_systems": 0.75, "public_health": 0.25},
        law,
    )
    assert 0.38 < value <= 0.90


def test_public_selector_score_does_not_require_private_practice() -> None:
    config = json.loads(Path("configs/w6/mobility-campaign.json").read_text())
    candidate = _candidate("w4-source-seed-191", "agent-191-00", 0)
    missions = config["mission_families"]["host_grid_mobility"]
    assert "practice_by_skill" not in json.dumps(candidate, sort_keys=True)
    assert _public_score(candidate, missions, config) >= 0.0


def test_discovery_phase_executes_all_w6_causal_boundaries(tmp_path: Path) -> None:
    candidates, capsules = _write_sources(tmp_path)
    result = run_phase(
        candidates,
        capsules,
        "configs/w6/mobility-campaign.json",
        "discovery",
    )

    assert result["phase"] == "discovery"
    assert len(result["routes"]) == 3
    assert result["summary"]["w6_02"]["exact_mode_parity"] is True
    for route in result["routes"]:
        assert route["w6_02"]["home_difference"] == 0.0
        assert route["w6_02"]["host_difference"] == 0.0
        movement = route["w6_01"]["mobility_event"]
        assert movement["state_before_sha256"] == movement["state_after_sha256"]
        learning = route["w6_04"]
        assert learning["learned_state_before_sha256"] != learning[
            "learned_state_after_sha256"
        ]
        assert learning["discard_state_before_sha256"] == learning[
            "discard_state_after_sha256"
        ]
        assert len(route["w6_06"]["member_ids"]) == 2
        assert route["w6_06"]["communication_bandwidth_bits"] == 1
        assert route["w6_06"]["trials"] == 128


def test_private_practice_in_public_candidate_is_rejected(tmp_path: Path) -> None:
    candidates, capsules = _write_sources(tmp_path)
    rows = [json.loads(line) for line in candidates.read_text().splitlines()]
    rows[0]["practice_by_skill"] = {"water_systems": 99}
    candidates.write_text("".join(json.dumps(row) + "\n" for row in rows))
    with pytest.raises(ValueError, match="private practice leaked"):
        run_phase(
            candidates,
            capsules,
            "configs/w6/mobility-campaign.json",
            "discovery",
        )


def test_effect_classification_uses_strict_two_point_band() -> None:
    assert _classify(0.020001, 0.02) == "positive"
    assert _classify(-0.020001, 0.02) == "negative"
    assert _classify(0.02, 0.02) == "null"
    assert _classify(-0.02, 0.02) == "null"
