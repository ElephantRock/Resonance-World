from __future__ import annotations

import json
from pathlib import Path

from resonance_world.w6_mobility import PortableAgentState
from resonance_world.w8_campaign import W8Population, _generate_offers
from resonance_world.w9_portfolio import (
    _public_frontier,
    functional_redundancy_allocation,
)
from resonance_world.w9_portfolio_development import build_portfolio_plan


SKILLS = (
    "urban_heat",
    "water_systems",
    "energy_storage",
    "supply_networks",
    "public_health",
    "mobility",
)


def _config() -> dict[str, object]:
    selector = {
        "home_success_rate": 0.30,
        "bid_win_rate": 0.20,
        "mean_bid_confidence": 0.10,
        "experience": 0.10,
        "dominant_host_fit": 0.20,
        "secondary_host_fit": 0.10,
        "experience_scale": 12.0,
    }
    return {
        "discovery_seeds": [3611],
        "replication_seeds": [4211],
        "agents_per_field": 12,
        "portfolio_target_strata": 3,
        "service_trials": 48,
        "organization_budget": 220,
        "offer_count": 8,
        "bid_base": 30,
        "bid_span": 60,
        "source_incremental_bound_pp": 2.0,
        "source_cumulative_bound_pp": 2.0,
        "stratum_cumulative_bound_pp": 3.0,
        "effect_band_pp": 2.0,
        "diagnostic_probability_threshold": 0.64,
        "diagnostic_redundancy_ratio_threshold": 1.2,
        "selector": selector,
        "public_estimator": {"selector": dict(selector)},
        "source_service_law": {
            "base_success_probability": 0.38,
            "practice_gain": 0.14,
            "maximum_success_probability": 0.90,
        },
        "organization_environment": {
            "base_success_probability": 0.35,
            "practice_gain": 0.16,
            "maximum_role_success": 0.94,
        },
        "organizations": [
            {
                "organization_id": "org-alpha",
                "lead_skill": "energy_storage",
                "support_skill": "mobility",
            },
            {
                "organization_id": "org-beta",
                "lead_skill": "water_systems",
                "support_skill": "public_health",
            },
            {
                "organization_id": "org-gamma",
                "lead_skill": "supply_networks",
                "support_skill": "urban_heat",
            },
        ],
        "home_service_missions": [
            {"mission_id": f"home-{skill}", "skill": skill} for skill in SKILLS
        ],
    }


def _candidate(index: int, *, field_id: str = "w4-source-seed-3611") -> dict[str, object]:
    dominant = SKILLS[index % len(SKILLS)]
    secondary = SKILLS[(index + 1) % len(SKILLS)]
    return {
        "agent_id": f"agent-{index:02d}",
        "checkpoint_id": "checkpoint",
        "field_id": field_id,
        "public_features": {
            "bid_count": 12.0,
            "bid_win_rate": 0.30 + index * 0.02,
            "completed_tasks": float(2 + index),
            "home_success_rate": 0.42 + index * 0.035,
            "mean_bid_confidence": 0.38 + index * 0.02,
            "request_count": 6.0,
            "skill_concentration": 0.5,
            "skill_entropy": 0.8,
            "task_domain_concentration": 0.5,
            "win_share": 0.1,
        },
        "public_mission_profile": {
            "dominant_success_skill": dominant,
            "secondary_success_skill": secondary,
        },
        "seed": 3611,
        "source_evidence_sha256": f"evidence-{index:02d}",
    }


def _population() -> W8Population:
    candidates = tuple(_candidate(index) for index in range(12))
    states = {}
    for index, candidate in enumerate(candidates):
        practice = {skill: 1 for skill in SKILLS}
        practice[SKILLS[index % len(SKILLS)]] = 4 + index
        states[str(candidate["agent_id"])] = PortableAgentState(
            agent_id=str(candidate["agent_id"]),
            home_field_id=str(candidate["field_id"]),
            practice_by_skill=tuple(sorted(practice.items())),
            evidence_refs=(f"private:{index}",),
        )
    return W8Population(
        candidates=candidates,
        portable_by_id=states,
        portable_by_field={"w4-source-seed-3611": tuple(states.values())},
        source_fields=tuple(),
    )


def _write_public_source(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    candidates = [_candidate(index) for index in range(12)]
    (path / "candidates.jsonl").write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in candidates),
        encoding="utf-8",
    )
    (path / "source-fields.json").write_text(
        json.dumps(
            [
                {
                    "field_id": "w4-source-seed-3611",
                    "seed": 3611,
                    "checkpoint_id": "checkpoint",
                    "run_id": "run",
                    "environment": {"agents": 12},
                    "source_evidence_sha256": "field-evidence",
                }
            ]
        ),
        encoding="utf-8",
    )


def test_portfolio_plan_uses_public_redundancy_gaps_only(tmp_path: Path) -> None:
    source = tmp_path / "source"
    _write_public_source(source)

    plan = build_portfolio_plan(source, _config(), phase="discovery")

    assert plan["field_count"] == 1
    assert plan["agent_count"] == 12
    assert len(plan["fields"][0]["selected_strata"]) == 3
    assert len(set(plan["fields"][0]["selected_strata"])) == 3
    assert "practice_by_skill" not in json.dumps(plan, sort_keys=True)
    ranked = sorted(
        plan["fields"][0]["strata"],
        key=lambda row: (-row["redundancy_gap_pp"], row["skill"]),
    )
    assert plan["fields"][0]["selected_strata"] == [row["skill"] for row in ranked[:3]]


def test_public_frontier_is_monotone_under_removal() -> None:
    population = _population()
    config = _config()
    candidates = population.candidates

    full = _public_frontier(candidates, config, unavailable_agent_ids=frozenset())
    reduced = _public_frontier(
        candidates,
        config,
        unavailable_agent_ids=frozenset({"agent-11"}),
    )

    assert reduced.weighted_value <= full.weighted_value + 1e-12
    assert all(reduced.by_skill[skill] <= full.by_skill[skill] + 1e-12 for skill in SKILLS)


def test_functional_allocator_uses_public_state_and_respects_all_bounds() -> None:
    population = _population()
    config = _config()
    window = "w9-03:test"
    offers = _generate_offers(population, config, window_id=window)

    result = functional_redundancy_allocation(
        population,
        offers,
        config,
        window_id=window,
    )

    for row in result.decisions:
        if row["decision"] != "awarded":
            continue
        assert row["incremental_predicted_loss_pp"] <= 2.0 + 1e-12
        assert row["cumulative_predicted_loss_pp"] <= 2.0 + 1e-12
        assert row["max_stratum_predicted_loss_pp"] <= 3.0 + 1e-12
    assert "practice_by_skill" not in json.dumps(result.decisions, sort_keys=True)


def test_functional_allocator_is_invariant_to_private_practice() -> None:
    first = _population()
    second = _population()
    second_states = {
        agent_id: PortableAgentState(
            agent_id=state.agent_id,
            home_field_id=state.home_field_id,
            practice_by_skill=tuple(
                (skill, value + 50) for skill, value in state.practice_by_skill
            ),
            evidence_refs=state.evidence_refs,
        )
        for agent_id, state in second.portable_by_id.items()
    }
    second = W8Population(
        candidates=second.candidates,
        portable_by_id=second_states,
        portable_by_field={
            "w4-source-seed-3611": tuple(second_states.values())
        },
        source_fields=tuple(),
    )
    config = _config()
    window = "w9-03:test"

    offers_a = _generate_offers(first, config, window_id=window)
    offers_b = _generate_offers(second, config, window_id=window)
    a = functional_redundancy_allocation(first, offers_a, config, window_id=window)
    b = functional_redundancy_allocation(second, offers_b, config, window_id=window)

    assert [row["decision"] for row in a.decisions] == [
        row["decision"] for row in b.decisions
    ]
    assert [row.get("agent_id") for row in a.decisions] == [
        row.get("agent_id") for row in b.decisions
    ]


def test_stratum_bound_can_reject_candidate_even_when_mean_bound_is_loose() -> None:
    population = _population()
    config = _config()
    config["source_incremental_bound_pp"] = 100.0
    config["source_cumulative_bound_pp"] = 100.0
    config["stratum_cumulative_bound_pp"] = 0.0
    window = "w9-03:test"
    offers = _generate_offers(population, config, window_id=window)

    result = functional_redundancy_allocation(
        population,
        offers,
        config,
        window_id=window,
    )

    assert any(row["decision"] == "rejected_functional_coverage" for row in result.decisions)
