from __future__ import annotations

import json

import pytest

from resonance_world.w6_mobility import PortableAgentState
from resonance_world.w8_campaign import W8Population, _generate_offers
from resonance_world.w9_allocation import (
    _source_reduction_fraction,
    criticality_aware_allocation,
    run_w9_01,
)


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
        "service_trials": 32,
        "organization_budget": 220,
        "offer_count": 8,
        "bid_base": 30,
        "bid_span": 60,
        "source_reserve_cap_comparator": 2,
        "source_loss_budget_pp": 2.0,
        "effect_band_pp": 2.0,
        "required_source_loss_reduction_fraction": 0.50,
        "conservative_z": 1.645,
        "estimator_residual_se_pp": 0.70,
        "selector": selector,
        "public_estimator": {"selector": dict(selector)},
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
            {"mission_id": f"home-{skill}", "skill": skill} for skill in SKILLS
        ],
    }


def _population(*, practice_shift: int = 0) -> W8Population:
    candidates: list[dict[str, object]] = []
    states: dict[str, PortableAgentState] = {}
    by_field: dict[str, list[PortableAgentState]] = {}
    for field_index in range(2):
        field_id = f"field-{field_index}"
        for index in range(6):
            agent_id = f"agent-{field_index}-{index}"
            dominant = SKILLS[index]
            secondary = SKILLS[(index + 1) % len(SKILLS)]
            candidate = {
                "agent_id": agent_id,
                "checkpoint_id": f"checkpoint-{field_index}",
                "field_id": field_id,
                "public_features": {
                    "bid_count": 12.0,
                    "bid_win_rate": 0.4 + index * 0.02,
                    "completed_tasks": float(3 + index),
                    "home_success_rate": 0.50 + index * 0.03,
                    "mean_bid_confidence": 0.45 + index * 0.02,
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
                "seed": field_index,
                "source_evidence_sha256": f"evidence-{field_index}-{index}",
            }
            candidates.append(candidate)
            practice = {skill: 0 for skill in SKILLS}
            practice[dominant] = 3 + practice_shift + index
            practice[secondary] = 2 + practice_shift
            state = PortableAgentState(
                agent_id=agent_id,
                home_field_id=field_id,
                practice_by_skill=tuple(sorted(practice.items())),
                evidence_refs=(f"evidence:{agent_id}",),
            )
            states[agent_id] = state
            by_field.setdefault(field_id, []).append(state)
    return W8Population(
        candidates=tuple(candidates),
        portable_by_id=states,
        portable_by_field={key: tuple(value) for key, value in by_field.items()},
        source_fields=tuple(),
    )


def _acceptance() -> dict[str, object]:
    return {
        "classification": "calibrated_source_cost_estimator",
        "authorizes_w9_01_principal_claim": True,
    }


def test_criticality_allocation_never_exceeds_conservative_field_budget() -> None:
    population = _population()
    config = _config()
    window = "w9-01:test"
    offers = _generate_offers(population, config, window_id=window)

    allocation = criticality_aware_allocation(
        population,
        offers,
        config,
        window_id=window,
    )

    assert allocation.conservative_budget_pp_by_field
    assert all(
        value <= float(config["source_loss_budget_pp"]) + 1e-12
        for value in allocation.conservative_budget_pp_by_field.values()
    )
    assert any(row["decision"] == "awarded" for row in allocation.decisions)
    assert "practice_by_skill" not in json.dumps(allocation.decisions, sort_keys=True)


def test_criticality_allocation_is_invariant_to_private_practice() -> None:
    config = _config()
    first = _population(practice_shift=0)
    second = _population(practice_shift=20)
    window = "w9-01:test"
    offers_first = _generate_offers(first, config, window_id=window)
    offers_second = _generate_offers(second, config, window_id=window)

    a = criticality_aware_allocation(first, offers_first, config, window_id=window)
    b = criticality_aware_allocation(second, offers_second, config, window_id=window)

    assert [row["decision"] for row in a.decisions] == [
        row["decision"] for row in b.decisions
    ]
    assert {
        contract.agent_id
        for contract in a.market.settle("other-window")
    } == set()
    assert a.predicted_loss_pp_by_field == b.predicted_loss_pp_by_field
    assert a.conservative_budget_pp_by_field == b.conservative_budget_pp_by_field
    assert [
        state.agent_id
        for org in ("org-alpha", "org-beta", "org-gamma")
        for state in a.market.contracted_agents(org, window)
    ] == [
        state.agent_id
        for org in ("org-alpha", "org-beta", "org-gamma")
        for state in b.market.contracted_agents(org, window)
    ]


def test_selector_drift_is_rejected() -> None:
    population = _population()
    config = _config()
    config["public_estimator"]["selector"]["home_success_rate"] = 0.31
    offers = _generate_offers(population, config, window_id="w9-01:test")

    with pytest.raises(ValueError, match="selectors must remain identical"):
        criticality_aware_allocation(
            population,
            offers,
            config,
            window_id="w9-01:test",
        )


def test_run_w9_01_requires_accepted_calibration() -> None:
    population = _population()
    config = _config()

    with pytest.raises(ValueError, match="requires accepted calibrated"):
        run_w9_01(
            population,
            config,
            {
                "classification": "biased_but_rank_informative",
                "authorizes_w9_01_principal_claim": False,
            },
            phase="discovery",
        )


def test_run_w9_01_reports_all_registered_comparators_and_gates() -> None:
    result = run_w9_01(_population(), _config(), _acceptance(), phase="discovery")

    assert result["calibration_classification"] == "calibrated_source_cost_estimator"
    assert set(result["gates"]) == {
        "organization_noninferiority",
        "source_loss_at_most_2pp",
        "source_loss_reduction_at_least_50pct",
    }
    assert result["unrestricted"]["contract_count"] >= 0
    assert result["cap_2"]["contract_count"] >= 0
    assert result["criticality_aware"]["contract_count"] >= 0
    assert result["criticality_aware"]["mean_conservative_budget_used_pp"] <= 2.0
    assert result["classification"] in {
        "criticality_allocation_effective",
        "criticality_allocation_ineffective",
    }


def test_source_reduction_fraction_has_defined_zero_baseline_behavior() -> None:
    assert _source_reduction_fraction(4.0, 1.0) == pytest.approx(0.75)
    assert _source_reduction_fraction(0.0, 0.0) == pytest.approx(1.0)
    assert _source_reduction_fraction(0.0, 1.0) == float("-inf")
