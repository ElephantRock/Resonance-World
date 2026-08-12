from types import SimpleNamespace

import pytest

from resonance_world import w9_long_horizon_execution as execution


def test_selected_source_and_benchmark_diagnostics_are_counted_and_recomputed():
    arm = {
        "compute": {
            "mission_execution_compute": 100.0,
            "incremental_total_measured_compute": 200.0,
            "final_total_measured_compute_including_cycle0_embodied": 300.0,
        },
        "successful_mission_evaluations": 50.0,
        "final_world_stock": 30.0,
        "total_efficiency_cycle0": 0.2,
        "service_efficiency": 0.5,
        "total_efficiency_final": 0.1,
        "compute_normalized_world_stock_growth": -0.5,
        "stock_series": [
            {"external_agent_count": 1},
            {"external_agent_count": 2},
        ],
    }
    config = {
        "long_horizon": {"cycles": 2},
        "service_trials": 4,
        "benchmark_missions": [{"skill": "a"}, {"skill": "b"}],
    }

    corrected = execution._correct_selected_compute(arm, config, field_count=2)

    assert arm["compute"]["mission_execution_compute"] == 100.0
    assert corrected["compute"]["source_diagnostic_mission_execution_compute"] == 32.0
    assert corrected["compute"]["benchmark_stock_mission_execution_compute"] == 12.0
    assert corrected["compute"]["mission_execution_compute"] == 144.0
    assert corrected["compute"]["incremental_total_measured_compute"] == 244.0
    assert corrected["compute"]["final_total_measured_compute_including_cycle0_embodied"] == 344.0
    assert corrected["service_efficiency"] == pytest.approx(50.0 / 144.0)
    assert corrected["total_efficiency_final"] == pytest.approx(30.0 / 344.0)


def test_w8_all_reviewed_compute_operations_are_counted():
    arm = {
        "compute": {
            "mission_execution_compute": 10.0,
            "organization_coordination_compute": 3.0,
            "world_regulatory_estimation_compute": 5.0,
            "incremental_total_measured_compute": 20.0,
            "final_total_measured_compute_including_cycle0_embodied": 30.0,
        },
        "successful_mission_evaluations": 5.0,
        "final_world_stock": 3.0,
        "total_efficiency_cycle0": 0.2,
        "service_efficiency": 0.5,
        "total_efficiency_final": 0.1,
        "compute_normalized_world_stock_growth": -0.5,
    }
    config = {
        "long_horizon": {
            "cycles": 2,
            "stress_schedule": {"withholding_cycles": [0, 1, 4]},
        },
        "service_trials": 4,
        "benchmark_missions": [{"skill": "a"}, {"skill": "b"}],
        "integrated_charter": {"reserve_cap": 0},
    }

    corrected = execution._correct_w8_compute(
        arm,
        config,
        field_count=2,
        organization_count=3,
    )

    assert corrected["compute"]["coalition_mission_execution_compute"] == 24.0
    assert corrected["compute"]["source_diagnostic_mission_execution_compute"] == 24.0
    assert corrected["compute"]["benchmark_stock_mission_execution_compute"] == 10.0
    assert corrected["compute"]["standalone_comparator_pair_selection_compute"] == 4.0
    assert corrected["compute"]["withholding_substitution_coordination_compute"] == 2.0
    assert corrected["compute"]["neutral_budget_update_regulatory_compute"] == 6.0
    assert corrected["compute"]["successor_activation_check_regulatory_compute"] == 4.0
    assert corrected["compute"]["mission_execution_compute"] == 68.0
    assert corrected["compute"]["organization_coordination_compute"] == 9.0
    assert corrected["compute"]["world_regulatory_estimation_compute"] == 15.0
    assert corrected["compute"]["incremental_total_measured_compute"] == 94.0
    assert corrected["compute"]["final_total_measured_compute_including_cycle0_embodied"] == 104.0
    assert corrected["service_efficiency"] == pytest.approx(5.0 / 68.0)
    assert corrected["total_efficiency_final"] == pytest.approx(3.0 / 104.0)


def test_w8_benchmark_accounting_fails_closed_if_org_stock_can_reach_width():
    config = {
        "long_horizon": {"cycles": 2},
        "benchmark_missions": [{"skill": "a"}, {"skill": "b"}],
        "integrated_charter": {"reserve_cap": 1},
    }
    with pytest.raises(ValueError, match="exact organization-accessible counts"):
        execution._w8_benchmark_stock_slots(config, field_count=2)


def test_execution_wrapper_refreshes_selected_growth_gate(monkeypatch):
    selected = {
        "compute": {
            "mission_execution_compute": 1.0,
            "incremental_total_measured_compute": 1.0,
            "final_total_measured_compute_including_cycle0_embodied": 2.0,
        },
        "successful_mission_evaluations": 1.0,
        "final_world_stock": 2.0,
        "total_efficiency_cycle0": 1.0,
        "service_efficiency": 1.0,
        "total_efficiency_final": 1.0,
        "compute_normalized_world_stock_growth": 0.5,
        "stock_series": [{"external_agent_count": 0}],
    }
    w8 = {
        "compute": {
            "mission_execution_compute": 1.0,
            "organization_coordination_compute": 1.0,
            "world_regulatory_estimation_compute": 1.0,
            "incremental_total_measured_compute": 3.0,
            "final_total_measured_compute_including_cycle0_embodied": 4.0,
        },
        "successful_mission_evaluations": 1.0,
        "final_world_stock": 2.0,
        "total_efficiency_cycle0": 1.0,
        "service_efficiency": 1.0,
        "total_efficiency_final": 0.5,
        "compute_normalized_world_stock_growth": -0.5,
    }
    raw = {
        "version": "w9-06-long-horizon-result-v0.1",
        "classification": "regenerative_allocation",
        "long_horizon_gate": True,
        "gates": {
            "source_loss_at_most_2pp": True,
            "organization_within_minus_2pp_of_W7": True,
            "compute_normalized_world_stock_growth_gt_2pct": True,
            "positive_source_accessible_capability_growth": True,
            "developmental_efficiency_at_least_20pct_better_than_W8": True,
        },
        "arms": {
            "selected_W9": selected,
            "W7_unrestricted": selected,
            "W9_without_portfolio_development": selected,
            "W8_neutral_full_regulatory_charter": w8,
        },
    }
    monkeypatch.setattr(execution.base, "run_w9_06", lambda *args, **kwargs: raw)
    monkeypatch.setattr(
        execution.base,
        "_merged_config",
        lambda *args, **kwargs: {
            "long_horizon": {
                "cycles": 1,
                "stress_schedule": {"withholding_cycles": [0]},
            },
            "service_trials": 1,
            "benchmark_missions": [{"skill": "a"}],
            "integrated_charter": {"reserve_cap": 0},
            "organizations": [{"organization_id": "o"}],
        },
    )
    population = SimpleNamespace(portable_by_field={"field": []})

    result = execution.run_w9_06_execution(
        population,
        {},
        {"required_compute_normalized_growth_fraction": 0.02},
        {},
        phase="discovery",
    )

    assert result["version"] == "w9-06-long-horizon-result-v0.6"
    assert result["arms"]["selected_W9"] == result["arms"]["W7_unrestricted"]
    assert result["arms"]["selected_W9"] == result["arms"]["W9_without_portfolio_development"]
    assert result["gates"]["compute_normalized_world_stock_growth_gt_2pct"] is False
    assert result["long_horizon_gate"] is False
    assert result["classification"] == "sustainable_but_non_generative_allocation"
    assert result["accounting_corrections"]["selected_source_frontier_diagnostics"]["mission_execution_compute_added"] == 2.0
    assert result["accounting_corrections"]["selected_benchmark_stock_assays"]["mission_execution_compute_added"] == 3.0
    assert result["accounting_corrections"]["w8_benchmark_stock_assays"]["mission_execution_compute_added"] == 3.0
    assert result["accounting_corrections"]["w8_neutral_budget_updates"]["world_regulatory_estimation_compute_added"] == 1.0
    assert result["accounting_corrections"]["w8_successor_activation_checks"]["world_regulatory_estimation_compute_added"] == 1.0
    assert result["accounting_corrections"]["w8_withholding_substitution"]["organization_coordination_compute_added"] == 1.0
