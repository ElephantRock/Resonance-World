import pytest

from resonance_world import w9_long_horizon_execution as execution


def test_w8_coalition_trials_are_counted_in_mission_compute():
    arm = {
        "compute": {
            "mission_execution_compute": 98304.0,
            "incremental_total_measured_compute": 100875.0,
            "final_total_measured_compute_including_cycle0_embodied": 101235.0,
        },
        "successful_mission_evaluations": 62616.0,
        "final_world_stock": 10.0,
        "total_efficiency_cycle0": 0.02,
        "service_efficiency": 0.0,
        "total_efficiency_final": 0.0,
        "compute_normalized_world_stock_growth": 0.0,
    }
    config = {"long_horizon": {"cycles": 24}, "service_trials": 512}

    corrected = execution._correct_w8_coalition_mission_compute(arm, config)

    assert arm["compute"]["mission_execution_compute"] == 98304.0
    assert corrected["compute"]["coalition_mission_execution_compute"] == 36864.0
    assert corrected["compute"]["mission_execution_compute"] == 135168.0
    assert corrected["compute"]["incremental_total_measured_compute"] == 137739.0
    assert corrected["compute"]["final_total_measured_compute_including_cycle0_embodied"] == 138099.0
    assert corrected["service_efficiency"] == pytest.approx(62616.0 / 135168.0)
    assert corrected["total_efficiency_final"] == pytest.approx(10.0 / 138099.0)
    assert corrected["compute_normalized_world_stock_growth"] == pytest.approx(
        (10.0 / 138099.0) / 0.02 - 1.0
    )


def test_execution_wrapper_versions_and_records_correction(monkeypatch):
    raw = {
        "version": "w9-06-long-horizon-result-v0.1",
        "arms": {
            "W8_neutral_full_regulatory_charter": {
                "compute": {
                    "mission_execution_compute": 10.0,
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
        },
    }
    monkeypatch.setattr(execution.base, "run_w9_06", lambda *args, **kwargs: raw)
    monkeypatch.setattr(
        execution.base,
        "_merged_config",
        lambda *args, **kwargs: {
            "long_horizon": {"cycles": 2},
            "service_trials": 4,
        },
    )

    result = execution.run_w9_06_execution(
        object(),
        {},
        {},
        {},
        phase="discovery",
    )

    assert result["version"] == "w9-06-long-horizon-result-v0.2"
    assert result["accounting_corrections"]["w8_coalition_mission_execution"] == {
        "trial_blocks_per_cycle": 3,
        "cycles": 2,
        "trials_per_block": 4,
        "mission_execution_compute_added": 24.0,
    }
    corrected = result["arms"]["W8_neutral_full_regulatory_charter"]
    assert corrected["compute"]["coalition_mission_execution_compute"] == 24.0
    assert corrected["compute"]["mission_execution_compute"] == 34.0
