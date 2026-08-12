from __future__ import annotations

import json

from resonance_world.w6_mobility import PortableAgentState
from resonance_world.w8_campaign import W8Population
from resonance_world.w9_coalition import FACTORS, _conditions, run_w9_04


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
        "discovery_seeds": [3611, 3731, 3851, 3971, 4091],
        "replication_seeds": [4211, 4331, 4451, 4571, 4691],
        "service_trials": 16,
        "organization_budget": 220,
        "offer_count": 8,
        "bid_base": 30,
        "bid_span": 60,
        "factor_main_effect_gate_pp": 2.0,
        "factor_required_positive_missions": 4,
        "factor_required_positive_fields": 5,
        "interaction_gate_pp": 1.0,
        "interaction_required_positive_missions": 4,
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
        "coalition": {
            "message_bandwidth_bits": 1,
            "nondecomposable_cross_base": 0.30,
            "nondecomposable_cross_gain": 0.12,
            "nondecomposable_cross_max": 0.92,
        },
        "organizations": [
            {"organization_id": "org-alpha", "lead_skill": "energy_storage", "support_skill": "mobility"},
            {"organization_id": "org-beta", "lead_skill": "water_systems", "support_skill": "public_health"},
            {"organization_id": "org-gamma", "lead_skill": "supply_networks", "support_skill": "urban_heat"},
        ],
        "coalition_missions": [
            {
                "coalition_id": "decomp-alpha-beta",
                "structure": "decomposable",
                "lead_organization_id": "org-alpha",
                "support_organization_id": "org-beta",
                "mission": {"mission_id": "d-ab", "context": "d-ab", "lead_skill": "energy_storage", "support_skill": "public_health"},
            },
            {
                "coalition_id": "decomp-beta-gamma",
                "structure": "decomposable",
                "lead_organization_id": "org-beta",
                "support_organization_id": "org-gamma",
                "mission": {"mission_id": "d-bg", "context": "d-bg", "lead_skill": "water_systems", "support_skill": "urban_heat"},
            },
            {
                "coalition_id": "decomp-gamma-alpha",
                "structure": "decomposable",
                "lead_organization_id": "org-gamma",
                "support_organization_id": "org-alpha",
                "mission": {"mission_id": "d-ga", "context": "d-ga", "lead_skill": "supply_networks", "support_skill": "mobility"},
            },
            {
                "coalition_id": "joint-alpha-beta",
                "structure": "nondecomposable",
                "lead_organization_id": "org-alpha",
                "support_organization_id": "org-beta",
                "mission": {"mission_id": "j-ab", "context": "j-ab", "lead_skill": "mobility", "support_skill": "water_systems"},
            },
            {
                "coalition_id": "joint-beta-gamma",
                "structure": "nondecomposable",
                "lead_organization_id": "org-beta",
                "support_organization_id": "org-gamma",
                "mission": {"mission_id": "j-bg", "context": "j-bg", "lead_skill": "public_health", "support_skill": "supply_networks"},
            },
            {
                "coalition_id": "joint-gamma-alpha",
                "structure": "nondecomposable",
                "lead_organization_id": "org-gamma",
                "support_organization_id": "org-alpha",
                "mission": {"mission_id": "j-ga", "context": "j-ga", "lead_skill": "urban_heat", "support_skill": "energy_storage"},
            },
        ],
    }


def _population() -> W8Population:
    candidates = []
    states = {}
    by_field = {}
    seeds = [3611, 3731, 3851, 3971, 4091]
    for field_index, seed in enumerate(seeds):
        field_id = f"w4-source-seed-{seed}"
        for index in range(12):
            agent_id = f"agent-{seed}-{index:02d}"
            dominant = SKILLS[(index + field_index) % 6]
            secondary = SKILLS[(index + field_index + 1) % 6]
            candidates.append(
                {
                    "agent_id": agent_id,
                    "checkpoint_id": f"checkpoint-{seed}",
                    "field_id": field_id,
                    "public_features": {
                        "bid_count": 12.0,
                        "bid_win_rate": 0.30 + 0.01 * index,
                        "completed_tasks": float(3 + index),
                        "home_success_rate": 0.45 + 0.02 * index,
                        "mean_bid_confidence": 0.40 + 0.01 * index,
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
                    "seed": seed,
                    "source_evidence_sha256": f"evidence-{seed}-{index}",
                }
            )
            practice = {skill: 1 for skill in SKILLS}
            practice[dominant] = 5 + index
            practice[secondary] = 3 + field_index
            state = PortableAgentState(
                agent_id=agent_id,
                home_field_id=field_id,
                practice_by_skill=tuple(sorted(practice.items())),
                evidence_refs=(f"private:{agent_id}",),
            )
            states[agent_id] = state
            by_field.setdefault(field_id, []).append(state)
    return W8Population(
        candidates=tuple(candidates),
        portable_by_id=states,
        portable_by_field={field: tuple(rows) for field, rows in by_field.items()},
        source_fields=tuple(),
    )


def test_factorial_has_all_sixteen_unique_conditions() -> None:
    conditions = _conditions()
    assert len(conditions) == 16
    assert len({tuple(bits[factor] for factor in FACTORS) for bits in conditions}) == 16


def test_w9_04_runs_pooled_and_five_local_diagnostics() -> None:
    result = run_w9_04(_population(), _config(), phase="discovery")

    assert len(result["pooled_factorial"]["condition_results"]) == 16
    assert len(result["diagnostic_field_pair_results"]) == 5
    assert set(result["factor_results"]) == set(FACTORS)
    assert len(result["interaction_results"]) == 6
    assert result["K"]
    for factor in FACTORS:
        row = result["factor_results"][factor]
        assert len(row["mission_effects_pp"]) == 6
        assert len(row["field_effects_pp"]) == 5
        assert row["selected_for_K"] == (factor in result["K"])
    assert "practice_by_skill" not in json.dumps(result, sort_keys=True)


def test_diversity_factor_is_expressible_in_two_field_diagnostics() -> None:
    result = run_w9_04(_population(), _config(), phase="discovery")
    for diagnostic in result["diagnostic_field_pair_results"].values():
        assert len(diagnostic["field_ids"]) == 2
        assert diagnostic["main_effects"]["V"]["main_effect_pp"] == diagnostic["main_effects"]["V"]["main_effect_pp"]
