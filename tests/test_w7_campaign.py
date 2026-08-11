from __future__ import annotations

import inspect
import json
from pathlib import Path

import pytest

from resonance_world.w4a_joint_learning import JointEnvironment
from resonance_world.w7_campaign import (
    _classify,
    _generate_offers,
    _load_population,
    _offer_digest,
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
DISCOVERY_SEEDS = [1663, 1789, 1913]


def _candidate(field_id: str, agent_id: str, index: int) -> dict[str, object]:
    return {
        "agent_id": agent_id,
        "checkpoint_id": f"checkpoint-{field_id}",
        "field_id": field_id,
        "public_features": {
            "bid_count": 10.0 + index,
            "bid_win_rate": 0.18 + 0.025 * (index % 6),
            "completed_tasks": 3.0 + index,
            "home_success_rate": 0.34 + 0.025 * (index % 7),
            "mean_bid_confidence": 0.42 + 0.015 * index,
            "request_count": 5.0,
            "skill_concentration": 0.4,
            "skill_entropy": 0.7,
            "task_domain_concentration": 0.4,
            "win_share": 0.15,
        },
        "public_mission_profile": {
            "dominant_success_skill": SKILLS[index % len(SKILLS)],
            "secondary_success_skill": SKILLS[(index + 2) % len(SKILLS)],
        },
        "source_evidence_sha256": f"evidence-{field_id}-{index}",
    }


def _capsule(field_id: str, agent_id: str, index: int) -> dict[str, object]:
    return {
        "agent_id": agent_id,
        "checkpoint_id": f"checkpoint-{field_id}",
        "field_id": field_id,
        "practice_by_skill": {
            skill: 1 + ((index + skill_index) % 7)
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
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in candidates),
        encoding="utf-8",
    )
    capsules_path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in capsules),
        encoding="utf-8",
    )
    return candidates_path, capsules_path


def _config() -> dict[str, object]:
    return json.loads(Path("configs/w7/competition-campaign.json").read_text())


def test_public_score_uses_no_private_practice() -> None:
    config = _config()
    candidate = _candidate("w4-source-seed-1663", "agent-1663-00", 0)
    requirements = config["organizations"][0]["overlap_bidding_requirements"]
    assert "practice_by_skill" not in json.dumps(candidate, sort_keys=True)
    assert 0.0 <= _public_score(candidate, requirements, config) <= 1.0

    candidate["practice_by_skill"] = {"energy_storage": 999}
    with pytest.raises(ValueError, match="private practice leaked"):
        _public_score(candidate, requirements, config)


def test_offer_generation_is_public_deterministic_and_budget_bounded(tmp_path: Path) -> None:
    candidates, capsules = _write_sources(tmp_path)
    config = _config()
    population = _load_population(candidates, capsules, config, "discovery")
    first = _generate_offers(
        population,
        config,
        window_id="window-test",
        requirement_key="overlap_bidding_requirements",
    )
    second = _generate_offers(
        population,
        config,
        window_id="window-test",
        requirement_key="overlap_bidding_requirements",
    )

    assert _offer_digest(first) == _offer_digest(second)
    assert set(first) == {"org-alpha", "org-beta", "org-gamma"}
    assert all(len(offers) == 8 for offers in first.values())
    assert all(30 <= offer.bid <= 90 for offers in first.values() for offer in offers)
    assert all(
        "practice_by_skill" not in json.dumps(offer.as_dict(), sort_keys=True)
        for offers in first.values()
        for offer in offers
    )


def test_discovery_phase_executes_all_w7_outputs(tmp_path: Path) -> None:
    candidates, capsules = _write_sources(tmp_path)
    result = run_phase(
        candidates,
        capsules,
        "configs/w7/competition-campaign.json",
        "discovery",
    )

    assert result["phase"] == "discovery"
    assert result["field_count"] == 3
    assert result["population_count"] == 36
    assert len(result["w7_01"]["organization_results"]) == 3
    assert len(result["w7_04"]["field_results"]) == 3
    assert len(result["w7_05"]["coalition_results"]) == 3
    assert len(result["w7_06"]["mission_results"]) == 3
    assert all(
        row["withholding_side"] == "support"
        for row in result["w7_06"]["mission_results"]
    )
    assert result["w7_01"]["classification"] in {"positive", "null", "negative"}
    assert result["w7_04"]["classification"] in {"positive", "null", "negative"}
    assert result["w7_05"]["classification"] in {"positive", "null", "negative"}


def test_public_candidate_practice_leak_is_rejected(tmp_path: Path) -> None:
    candidates, capsules = _write_sources(tmp_path)
    rows = [json.loads(line) for line in candidates.read_text().splitlines()]
    rows[0]["practice_by_skill"] = {"water_systems": 99}
    candidates.write_text(
        "".join(json.dumps(row) + "\n" for row in rows),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="private practice leaked"):
        run_phase(
            candidates,
            capsules,
            "configs/w7/competition-campaign.json",
            "discovery",
        )


def test_strict_effect_band_is_frozen_at_two_points() -> None:
    assert _classify(0.020001, 0.02) == "positive"
    assert _classify(-0.020001, 0.02) == "negative"
    assert _classify(0.02, 0.02) == "null"
    assert _classify(-0.02, 0.02) == "null"


def test_joint_outcome_law_has_no_market_inputs() -> None:
    parameters = set(inspect.signature(JointEnvironment.evaluate).parameters)
    forbidden = {
        "bid",
        "budget",
        "coalition",
        "competition",
        "contract",
        "market",
        "price",
        "rival",
    }
    assert not parameters & forbidden
