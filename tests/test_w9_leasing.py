from __future__ import annotations

import json

import pytest

from resonance_world.w6_mobility import PortableAgentState
from resonance_world.w8_campaign import W8Population, _generate_offers, _unrestricted_allocation
from resonance_world.w9_leasing import run_w9_02, simulate_w9_02_arm


SKILLS = (
    "urban_heat",
    "water_systems",
    "energy_storage",
    "supply_networks",
    "public_health",
    "mobility",
)


def _config() -> dict[str, object]:
    return {
        "service_trials": 48,
        "organization_budget": 220,
        "offer_count": 8,
        "bid_base": 30,
        "bid_span": 60,
        "horizon_windows": 8,
        "source_slots_per_window": 6,
        "learning_per_executed_role": 1,
        "lease_recovery_windows": 1,
        "effect_band_pp": 2.0,
        "source_loss_bound_pp": 2.0,
        "lease_organization_slots": {
            "org-alpha": 0,
            "org-beta": 2,
            "org-gamma": 4,
        },
        "w8_4_2": {
            "external_windows": 4,
            "home_windows": 2,
            "roster_offsets": [0, 2, 4],
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
            {"mission_id": f"home-{skill}", "skill": skill} for skill in SKILLS
        ],
    }


def _population() -> W8Population:
    candidates: list[dict[str, object]] = []
    states: dict[str, PortableAgentState] = {}
    by_field: dict[str, list[PortableAgentState]] = {}
    for field_index in range(2):
        field_id = f"field-{field_index}"
        for index in range(6):
            agent_id = f"agent-{field_index}-{index}"
            dominant = SKILLS[index]
            secondary = SKILLS[(index + 1) % len(SKILLS)]
            candidates.append(
                {
                    "agent_id": agent_id,
                    "checkpoint_id": f"checkpoint-{field_index}",
                    "field_id": field_id,
                    "public_features": {
                        "bid_count": 12.0,
                        "bid_win_rate": 0.35 + 0.02 * index,
                        "completed_tasks": float(4 + index),
                        "home_success_rate": 0.50 + 0.025 * index,
                        "mean_bid_confidence": 0.42 + 0.02 * index,
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
            )
            practice = {skill: 1 for skill in SKILLS}
            practice[dominant] = 6 + index
            practice[secondary] = 4 + index
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
        portable_by_field={field: tuple(rows) for field, rows in by_field.items()},
        source_fields=tuple(),
    )


def _market(population: W8Population, config: dict[str, object]):
    window_id = "w9-02:test"
    offers = _generate_offers(population, config, window_id=window_id)
    return window_id, _unrestricted_allocation(
        population, offers, config, window_id=window_id
    )


def test_zero_recovery_leasing_preserves_org_roster_but_reduces_source_unavailability() -> None:
    population = _population()
    config = _config()
    window_id, market = _market(population, config)

    permanent = simulate_w9_02_arm(
        population,
        market,
        config,
        phase="discovery",
        window_id=window_id,
        mode="permanent",
    )
    lease = simulate_w9_02_arm(
        population,
        market,
        config,
        phase="discovery",
        window_id=window_id,
        mode="lease-zero-recovery",
    )

    assert lease["mean_organization_success_pct"] == pytest.approx(
        permanent["mean_organization_success_pct"]
    )
    assert lease["source_unavailable_agent_slots"] < permanent[
        "source_unavailable_agent_slots"
    ]
    assert lease["useful_external_service_per_source_unavailable_window"] > permanent[
        "useful_external_service_per_source_unavailable_window"
    ]
    assert lease["lease_conflict_rate"] == pytest.approx(0.0)


def test_one_window_recovery_adds_source_idle_slots_without_reducing_org_access() -> None:
    population = _population()
    config = _config()
    window_id, market = _market(population, config)

    zero = simulate_w9_02_arm(
        population,
        market,
        config,
        phase="discovery",
        window_id=window_id,
        mode="lease-zero-recovery",
    )
    recovery = simulate_w9_02_arm(
        population,
        market,
        config,
        phase="discovery",
        window_id=window_id,
        mode="lease-one-window-recovery",
    )

    assert recovery["mean_organization_success_pct"] == pytest.approx(
        zero["mean_organization_success_pct"]
    )
    assert recovery["recovery_idle_source_agent_slots"] > 0
    assert recovery["source_unavailable_agent_slots"] > zero[
        "source_unavailable_agent_slots"
    ]


def test_w8_four_two_comparator_has_whole_window_source_absence() -> None:
    population = _population()
    config = _config()
    window_id, market = _market(population, config)

    circulation = simulate_w9_02_arm(
        population,
        market,
        config,
        phase="discovery",
        window_id=window_id,
        mode="4:2",
    )

    assert circulation["source_unavailable_agent_slots"] % 6 == 0
    assert circulation["external_agent_window_exposures"] > 0
    assert circulation["learning_events"] > 0


def test_run_w9_02_reports_registered_classification_and_no_private_state() -> None:
    result = run_w9_02(_population(), _config(), phase="discovery")

    assert set(result["arms"]) == {
        "permanent",
        "4:2",
        "lease-zero-recovery",
        "lease-one-window-recovery",
    }
    assert result["classification"] in {
        "robust_sustainable_leasing",
        "leasing_switching_fragile",
        "leasing_not_sustainable",
    }
    assert result["robust_gate"] == (
        result["zero_recovery_gate"] and result["recovery_gate"]
    )
    assert "practice_by_skill" not in json.dumps(result, sort_keys=True)
