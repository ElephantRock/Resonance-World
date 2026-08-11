# ruff: noqa: E501
from __future__ import annotations

import json
from pathlib import Path

import pytest

from resonance_world.w6_mobility import PortableAgentState
from resonance_world.w7_competition import TalentMarket, TalentOffer
from resonance_world.w8_campaign import (
    W8Population,
    _hungarian_max,
    _new_market,
    _source_loss_from_ids,
    _structured_expected,
    capped_rival_allocation,
    matched_source_loss_frontier,
    run_w8_03,
    run_w8_04,
    summarize_allocation,
    synthesize,
)
from resonance_world.w8_execution import replacement_activation_costs


def _state(agent_id: str, field_id: str, **practice: int) -> PortableAgentState:
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
        home_field_id=field_id,
        practice_by_skill=tuple(skills.items()),
        evidence_refs=(f"evidence:{agent_id}",),
    )


def _config() -> dict[str, object]:
    return {
        "effect_band": 0.02,
        "stock_growth_band": 0.02,
        "source_loss_match_tolerance": 0.002,
        "service_trials": 64,
        "organization_budget": 220,
        "offer_count": 8,
        "bid_base": 30,
        "bid_span": 60,
        "source_reserve": {"primary_cap": 1, "sensitivity_caps": [2]},
        "circulation": {
            "horizon_windows": 6,
            "primary_external_windows": 4,
            "primary_home_windows": 2,
            "sensitivity_external_windows": 3,
            "sensitivity_home_windows": 3,
            "roster_offsets": [0, 2, 4],
            "learning_per_executed_role": 1,
        },
        "dividend": {
            "primary_basis_points": 5000,
            "sensitivity_basis_points": [0, 10000],
            "development_credit_per_cycle": 12,
        },
        "replacement_classification": {
            "recovery_source_loss_max": 0.02,
            "contingency_cosine_distance": 0.10,
            "replication_cosine_similarity": 0.95,
            "replication_dominant_match_share": 0.80,
        },
        "coalition": {
            "message_bandwidth_bits": 1,
            "required_positive_missions": 1,
            "nondecomposable_cross_base": 0.30,
            "nondecomposable_cross_gain": 0.12,
            "nondecomposable_cross_max": 0.92,
        },
        "integrated_charter": {
            "reserve_cap": 1,
            "external_windows": 4,
            "home_windows": 2,
            "dividend_basis_points": 5000,
            "message_bandwidth_bits": 1,
        },
        "long_horizon": {
            "cycles": 2,
            "neutral_base_budget": 220,
            "compounding_reward_per_successful_trial": 1,
            "compounding_max_budget": 500,
            "stress_schedule": {
                "demand_shift_cycles": [],
                "demand_shift_skill_rotation": 1,
                "source_shortage_cycles": [],
                "source_shortage_field_stride": 1,
                "withholding_cycles": [],
                "withholding_side": "support",
            },
        },
        "selector": {
            "home_success_rate": 0.30,
            "bid_win_rate": 0.20,
            "mean_bid_confidence": 0.10,
            "experience": 0.10,
            "dominant_host_fit": 0.20,
            "secondary_host_fit": 0.10,
            "experience_scale": 12.0,
        },
        "organization_environment": {
            "base_success_probability": 0.35,
            "practice_gain": 0.16,
            "maximum_role_success": 0.94,
        },
        "source_service_law": {
            "base_success_probability": 0.38,
            "practice_gain": 0.14,
            "maximum_success_probability": 0.90,
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
            {"mission_id": "home-energy", "skill": "energy_storage"},
            {"mission_id": "home-water", "skill": "water_systems"},
            {"mission_id": "home-supply", "skill": "supply_networks"},
        ],
        "benchmark_missions": [
            {"mission_id": "bench-energy", "skill": "energy_storage"},
            {"mission_id": "bench-water", "skill": "water_systems"},
        ],
        "coalition_missions": [
            {
                "coalition_id": "swap",
                "structure": "decomposable",
                "lead_organization_id": "org-alpha",
                "support_organization_id": "org-beta",
                "mission": {
                    "mission_id": "swap-mission",
                    "context": "swap-mission",
                    "lead_skill": "energy_storage",
                    "support_skill": "public_health",
                },
            }
        ],
    }


def _population() -> W8Population:
    states = [
        _state("a1", "field-a", energy_storage=8),
        _state("a2", "field-a", mobility=5),
        _state("b1", "field-b", water_systems=8),
        _state("b2", "field-b", public_health=5),
        _state("c1", "field-c", supply_networks=8),
        _state("c2", "field-c", urban_heat=5),
    ]
    return W8Population(
        candidates=(),
        portable_by_id={state.agent_id: state for state in states},
        portable_by_field={
            field_id: tuple(state for state in states if state.home_field_id == field_id)
            for field_id in ("field-a", "field-b", "field-c")
        },
        source_fields=(),
    )


def _offer(org: str, agent: str, bid: int = 50) -> TalentOffer:
    return TalentOffer(
        offer_id=f"offer:w:{org}:{agent}",
        organization_id=org,
        agent_id=agent,
        window_id="w",
        bid=bid,
        evidence_refs=(f"public:{agent}",),
    )


def test_source_reserve_never_exceeds_cap() -> None:
    population = _population()
    config = _config()
    offers = (
        _offer("org-alpha", "a1", 80),
        _offer("org-beta", "a2", 70),
        _offer("org-gamma", "b1", 60),
    )
    market = capped_rival_allocation(
        population, offers, config, window_id="w", cap=1
    )
    fields = [
        population.portable_by_id[row["agent_id"]].home_field_id
        for row in market.snapshot()["contracts"]
    ]
    assert fields.count("field-a") == 1
    assert max(fields.count(field_id) for field_id in set(fields)) <= 1


def test_source_loss_matched_frontier_respects_loss_budget() -> None:
    population = _population()
    config = _config()
    offers = (
        _offer("org-alpha", "a1", 40),
        _offer("org-alpha", "b1", 40),
        _offer("org-beta", "a2", 40),
        _offer("org-beta", "b2", 40),
        _offer("org-gamma", "c1", 40),
        _offer("org-gamma", "c2", 40),
    )
    capped_market = capped_rival_allocation(
        population, offers, config, window_id="w", cap=1
    )
    capped = summarize_allocation(
        population,
        capped_market,
        config,
        window_id="w",
        seed_salt="test",
    )
    frontier, _ = matched_source_loss_frontier(
        population,
        offers,
        capped,
        config,
        window_id="w",
    )
    assert frontier is not None
    removed = {
        row["agent_id"] for row in frontier.snapshot()["contracts"]
    }
    loss, _ = _source_loss_from_ids(population, removed, config)
    assert loss <= capped.mean_source_loss + float(config["source_loss_match_tolerance"]) + 1e-12


def test_hungarian_stock_never_reuses_one_agent() -> None:
    scores = [
        [0.9, 0.8, 0.1],
        [0.95, 0.2, 0.7],
    ]
    assignment = _hungarian_max(scores)
    assert len(assignment) == 2
    assert len({agent for _, agent in assignment}) == 2
    total = sum(scores[mission][agent] for mission, agent in assignment)
    assert total == pytest.approx(1.75)


def test_coordinated_contract_can_swap_roles_without_success_bonus() -> None:
    config = _config()
    states = [
        _state("alpha", "field-a", public_health=10),
        _state("beta", "field-b", energy_storage=10),
    ]
    population = W8Population(
        candidates=(),
        portable_by_id={state.agent_id: state for state in states},
        portable_by_field={
            "field-a": (states[0],),
            "field-b": (states[1],),
        },
        source_fields=(),
    )
    market = _new_market(population, config)
    market.submit_offer(_offer("org-alpha", "alpha"))
    market.submit_offer(_offer("org-beta", "beta"))
    market.settle("w")

    result = run_w8_04(market, config, phase="test", window_id="w")
    mission = result["mission_results"][0]
    assert mission["coordination_bit"] == 1
    assert mission["coordinated_coalition_success"] > mission["simple_coalition_success"]


def test_nondecomposable_structure_adds_cross_skill_requirement_not_contract_metadata() -> None:
    config = _config()
    lead = _state("lead", "field-a", energy_storage=8).to_individual()
    support = _state("support", "field-b", public_health=8).to_individual()
    mission = run_w8_04.__globals__["JointMission"](
        "m", "m", "energy_storage", "public_health"
    )
    decomposable = _structured_expected(
        lead, support, mission, config, structure="decomposable"
    )
    joint = _structured_expected(
        lead, support, mission, config, structure="nondecomposable"
    )
    assert joint < decomposable


def test_replacement_classifier_distinguishes_contingent_regeneration() -> None:
    population = _population()
    config = _config()
    market = _new_market(population, config)
    replacement_state = _state(
        "successor", "field-a", energy_storage=8, mobility=5
    )
    replacement = {
        "status": "completed",
        "basis_points": {
            "5000": {
                "developed_fields": 1,
                "mean_extracted_vs_vacancy_cosine_distance": 0.25,
                "mean_successor_vs_source_target_cosine": 0.80,
                "dominant_match_share": 1.0,
                "fields": [
                    {
                        "field_id": "field-a",
                        "status": "native_successor_developed",
                        "funded_cycles": 4,
                        "dividend_amount": 48,
                        "extracted_successor_state": replacement_state.as_dict(),
                    }
                ],
            }
        },
    }
    result = run_w8_03(
        population, market, replacement, config, window_id="w"
    )
    assert result["classification"] == "ecological_regeneration"
    assert result["recovery_gate"] is True


def test_replacement_activation_requires_full_native_development_cost() -> None:
    config = _config()
    replacement = {
        "basis_points": {
            "5000": {
                "fields": [
                    {
                        "field_id": "field-a",
                        "status": "native_successor_developed",
                        "funded_cycles": 5,
                    }
                ]
            }
        }
    }
    assert replacement_activation_costs(replacement, config) == {"field-a": 60}


def _phase_payload(long_label: str = "generative_circulation") -> dict[str, object]:
    return {
        "w8_01_source_reserve": {"primary_gate": True},
        "w8_02_circulation": {"gate": True},
        "w8_03_replacement": {"classification": "ecological_regeneration"},
        "w8_04_coalitions": {"gate": True},
        "w8_05_integrated_charter": {"gate": True},
        "w8_06_long_horizon": {
            "neutral": {
                "long_run_label": long_label,
                "compute_normalized_world_stock_growth": 0.05,
            }
        },
    }


def test_synthesis_requires_all_sustainability_gates(tmp_path: Path) -> None:
    discovery = tmp_path / "discovery.json"
    replication = tmp_path / "replication.json"
    output = tmp_path / "synthesis.json"
    discovery.write_text(json.dumps(_phase_payload()), encoding="utf-8")
    replication.write_text(json.dumps(_phase_payload()), encoding="utf-8")

    result = synthesize(
        discovery_path=discovery,
        replication_path=replication,
        output_path=output,
    )
    assert result["status"] == "replicated_generative_circulation"

    failed = _phase_payload()
    failed["w8_04_coalitions"]["gate"] = False
    replication.write_text(json.dumps(failed), encoding="utf-8")
    result = synthesize(
        discovery_path=discovery,
        replication_path=replication,
        output_path=output,
    )
    assert result["replicated_sustainable_circulation"] is False
    assert result["status"] == "w8_discovery_not_replicated"
