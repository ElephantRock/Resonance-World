import pytest

from resonance_world import w9_long_horizon as long_horizon


def test_zero_development_compute_is_undefined_not_infinite():
    result = long_horizon._efficiency_fields(
        initial_world_stock=10.0,
        final_world_stock=11.0,
        initial_source_stock=10.0,
        final_source_stock=10.5,
        embodied_compute=100.0,
        source_development_compute=0.0,
        mission_execution_compute=50.0,
        organization_coordination_compute=10.0,
        world_regulatory_estimation_compute=5.0,
        successful_mission_evaluations=40.0,
    )
    assert result["developmental_efficiency"] is None
    assert result["service_efficiency"] == pytest.approx(0.8)
    assert result["compute"]["final_total_measured_compute_including_cycle0_embodied"] == 165.0
    assert result["total_efficiency_cycle0"] == pytest.approx(0.1)
    assert result["total_efficiency_final"] == pytest.approx(11.0 / 165.0)
    assert result["compute_normalized_world_stock_growth"] == pytest.approx(
        (11.0 / 165.0) / 0.1 - 1.0
    )


def test_developmental_efficiency_gate_is_conservative_for_undefined_values():
    assert long_horizon._developmental_efficiency_gate(None, 0.1, 0.2) is False
    assert long_horizon._developmental_efficiency_gate(0.2, None, 0.2) is False
    assert long_horizon._developmental_efficiency_gate(0.12, 0.1, 0.2) is True
    assert long_horizon._developmental_efficiency_gate(-0.08, -0.1, 0.2) is True
    assert long_horizon._developmental_efficiency_gate(-0.081, -0.1, 0.2) is False


def test_long_horizon_overlay_does_not_mutate_market_config():
    market = {"organizations": [{"organization_id": "o"}], "service_trials": 512}
    overlay = {
        "version": "v",
        "cycles": 24,
        "neutral_base_budget": 220,
        "compounding_reward_per_successful_trial": 1,
        "compounding_max_budget": 500,
        "stress_schedule": {"demand_shift_cycles": []},
        "compute_accounting": {},
    }
    merged = long_horizon._merged_config(market, overlay)
    assert "long_horizon" not in market
    assert merged["service_trials"] == 512
    assert merged["long_horizon"]["cycles"] == 24
    assert "version" not in merged["long_horizon"]
    assert "compute_accounting" not in merged["long_horizon"]


def test_selected_w9_w7_and_no_portfolio_are_explicit_aliases(monkeypatch):
    selected = {
        "mean_source_loss_pp": 1.0,
        "mean_organization_success_pct": 80.0,
        "compute_normalized_world_stock_growth": 0.01,
        "source_accessible_capability_growth": 0.5,
        "developmental_efficiency": None,
    }
    w8 = {"developmental_efficiency": 0.02}
    monkeypatch.setattr(
        long_horizon,
        "run_unrestricted_long_horizon",
        lambda *args, **kwargs: selected,
    )
    monkeypatch.setattr(
        long_horizon,
        "summarize_w8_neutral",
        lambda *args, **kwargs: w8,
    )
    result = long_horizon.run_w9_06(
        object(),
        {"source_loss_bound_pp": 2.0, "effect_band_pp": 2.0},
        {
            "cycles": 24,
            "neutral_base_budget": 220,
            "compounding_reward_per_successful_trial": 1,
            "compounding_max_budget": 500,
            "stress_schedule": {},
            "required_compute_normalized_growth_fraction": 0.02,
            "developmental_efficiency_improvement_fraction": 0.20,
            "compute_accounting": {"zero_source_development_efficiency": None},
        },
        {},
        phase="discovery",
    )
    assert result["arms"]["selected_W9"] == result["arms"]["W7_unrestricted"]
    assert result["arms"]["selected_W9"] == result["arms"]["W9_without_portfolio_development"]
    assert result["alias_map"] == {
        "W7_unrestricted": "selected_W9",
        "W9_without_portfolio_development": "selected_W9",
    }
    assert result["gates"]["developmental_efficiency_at_least_20pct_better_than_W8"] is False
    assert result["classification"] == "sustainable_but_non_generative_allocation"
