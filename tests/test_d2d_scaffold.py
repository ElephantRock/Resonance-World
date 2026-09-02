from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
D2D = ROOT / "research" / "d2d"


def load_json(name: str):
    return json.loads((D2D / name).read_text())


def test_request_plan_authority_and_fixed_substrate() -> None:
    plan = load_json("D2D_REQUEST_PLAN.json")
    assert plan["provider"] == "Z.AI"
    assert plan["model"] == "glm-5-turbo"
    assert plan["temperature"] == 0.8
    assert plan["thinking"] == "disabled"
    assert plan["destination_reproduction_tested"] is False
    assert plan["capability_artifact_exported"] is False
    assert plan["provider_execution_authorized"] is False
    assert plan["registry_promotion_authorized"] is False
    assert plan["historical_substrate_enabled"] is False
    assert plan["same_request_stream_rerun_allowed"] is False


def test_registered_exposure_hierarchy_and_sample_size() -> None:
    plan = load_json("D2D_REQUEST_PLAN.json")
    sample = load_json("D2D_SAMPLE_SIZE.json")
    assert plan["gatekeeping_order"] == [
        "developed_160_minus_fresh",
        "developed_80_minus_fresh",
        "developed_40_minus_fresh",
    ]
    assert plan["primary_materiality_margin"] == 0.1
    assert plan["alpha_one_sided"] == 0.05
    assert plan["attempted_pairs_per_schema"] == 96
    assert plan["minimum_analyzable_pairs_per_schema"] == 88
    assert sample["minimum_analyzable_n_per_schema"] == 88
    assert sample["attempted_n_per_schema"] == 96
    assert sample["approx_required_n"] < 88


def test_calibration_schema_firewall() -> None:
    suite = load_json("D2D_SCHEMA_SUITE.json")
    ids = [row["id"] for row in suite["schemas"]]
    assert ids == [
        "threshold_at_4",
        "parity_pair",
        "interval_pair",
        "pairwise_order",
    ]
    assert len({row["seed_base"] for row in suite["schemas"]}) == 4
    assert suite["future_use"]["eligible_as_d2e_heldout_confirmatory_schema"] is False
    assert suite["freshness"]["cross_schema_seed_overlap_allowed"] is False
    assert suite["freshness"]["development_evaluation_feature_overlap_allowed"] is False


def test_no_provider_run_marker_exists() -> None:
    assert not (D2D / "RUN_D2D_SOURCE_ACQUISITION").exists()


def test_d2_registry_state_is_not_promoted_by_d2d() -> None:
    registry = json.loads((ROOT / "research" / "mechanisms" / "registry.json").read_text())
    node = next(
        row
        for row in registry["nodes"]
        if row.get("mechanism_id") == "d2_stochastic_capability_reproduction"
    )
    assert node["status"] == "internally_replicated"
    assert node.get("production_historical_substrate_enabled") is False
