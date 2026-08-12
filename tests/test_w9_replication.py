import pytest

from resonance_world import w9_replication as replication


def _stages():
    seeds = list(replication.EXPECTED_SEEDS)
    calibration = {
        "phase": "replication",
        "seeds": seeds,
        "calibration": {
            "label": "calibrated_source_cost_estimator",
            "mae_pp": 0.4,
            "signed_bias_pp": 0.1,
            "spearman_rho": 0.7,
            "high_cost_safe_rate": 0.95,
        },
    }
    allocation = {
        "phase": "replication",
        "classification": "criticality_allocation_effective",
        "gate": True,
        "gates": {"example": True},
    }
    leasing = {
        "phase": "replication",
        "classification": "robust_sustainable_leasing",
        "zero_recovery_gate": True,
        "recovery_gate": True,
        "robust_gate": True,
    }
    portfolio = {
        "phase": "replication",
        "classification": "portfolio_redundancy_effective",
        "eligible_for_w9_05_P": True,
    }
    coalition = {
        "phase": "replication",
        "K": ["D"],
    }
    integrated = {
        "phase": "replication",
        "classification": "integrated_static_gate_failed",
        "integrated_static_gate": False,
        "gates": {"example": False},
        "upstream_eligibility": {"C": False, "L": False, "P": False, "K": []},
        "selected_mechanisms": [],
        "structural_status": "no_upstream_eligible_w9_mechanisms",
    }
    long_horizon = {
        "version": "w9-06-long-horizon-result-v0.6",
        "phase": "replication",
        "classification": "long_horizon_gate_failed",
        "long_horizon_gate": False,
        "gates": {"example": False},
        "selected_mechanisms": [],
    }
    return {
        "calibration": calibration,
        "allocation": allocation,
        "leasing": leasing,
        "portfolio": portfolio,
        "coalition": coalition,
        "integrated": integrated,
        "long_horizon": long_horizon,
    }


def test_replication_cannot_rescue_failed_discovery_constituents():
    result = replication.synthesize_replication(**_stages())

    assert result["nested_outcomes"] == {
        "replicated_calibrated_criticality_pricing": True,
        "replicated_tradeoff_reduction": False,
        "replicated_sustainable_capability_leasing": False,
        "replicated_regenerative_allocation": False,
    }
    assert result["replication_stage_results"]["W9-01"]["gate"] is True
    assert result["replication_stage_results"]["W9-02"]["robust_gate"] is True
    assert result["replication_stage_results"]["W9-04"]["K_replication_diagnostic"] == ["D"]
    assert result["replication_stage_results"]["W9-04"]["discovery_frozen_K"] == ["none"]
    assert result["selected_mechanisms"] == []
    assert len(result["scientific_payload_sha256"]) == 64


def test_replication_rejects_regime_reselection():
    stages = _stages()
    stages["integrated"]["selected_mechanisms"] = ["C"]
    with pytest.raises(ValueError, match="changed the discovery-frozen regime"):
        replication.synthesize_replication(**stages)


def test_replication_requires_accepted_w9_06_accounting_version():
    stages = _stages()
    stages["long_horizon"]["version"] = "w9-06-long-horizon-result-v0.5"
    with pytest.raises(ValueError, match="accepted v0.6"):
        replication.synthesize_replication(**stages)


def test_replication_rejects_wrong_seed_vector_when_reported():
    stages = _stages()
    stages["calibration"]["seeds"] = [1, 2, 3, 4, 5]
    with pytest.raises(ValueError, match="seed mismatch"):
        replication.synthesize_replication(**stages)
