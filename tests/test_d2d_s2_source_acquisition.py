from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
D2D_S2 = ROOT / "research" / "d2d_s2"
sys.path.insert(0, str(SCRIPTS))

import d2d_s2_acquisition_core as core  # noqa: E402
import materialize_d2d_s2_source_acquisition as materializer  # noqa: E402
import run_d2d_s2_source_acquisition as runner  # noqa: E402

EXPECTED_COHORT = "d74348dc2d15e2b1c1959726faa9ae473e01a3aeed46bcdc3b1c240e918b3d9f"


def load_json(name: str):
    return json.loads((D2D_S2 / name).read_text())


def test_fresh_namespace_and_d2e_firewall() -> None:
    suite = load_json("D2D_S2_SCHEMA_SUITE.json")
    assert [row["id"] for row in suite["schemas"]] == list(core.SCHEMA_ORDER)
    assert [row["seed_base"] for row in suite["schemas"]] == [
        6_000_000,
        6_200_000,
        6_400_000,
        6_600_000,
    ]
    assert suite["freshness"]["predecessor_d2d_seed_namespace_reused"] is False
    assert suite["future_use"]["eligible_as_d2e_heldout_confirmatory_schema"] is False


def test_request_plan_is_frozen_unexecuted_and_hardened() -> None:
    plan = load_json("D2D_S2_REQUEST_PLAN.json")
    assert plan["issue"] == 208
    assert plan["provider"] == "Z.AI"
    assert plan["endpoint"] == "https://api.z.ai/api/paas/v4/chat/completions"
    assert plan["model"] == "glm-5-turbo"
    assert plan["max_attempts_per_logical_call"] == 1
    assert plan["redirect_policy"] == "reject_do_not_follow"
    assert plan["http_status_required"] == 200
    assert plan["strict_json_required"] is True
    assert plan["provider_execution_authorized"] is False
    assert plan["same_request_stream_rerun_allowed"] is False
    assert plan["registry_promotion_authorized"] is False
    assert plan["historical_substrate_enabled"] is False


def test_materialization_matches_committed_frozen_inputs() -> None:
    lock = materializer.build_cohort_lock()
    shard_map = materializer.build_shard_map()
    assert lock == load_json("d2d-s2-source-acquisition-cohort-lock.json")
    assert shard_map == load_json("D2D_S2_SHARD_MAP.json")
    assert lock["cohort_pairs_sha256"] == EXPECTED_COHORT
    assert all(value == 0 for value in lock["predecessor_seed_namespace_overlap"].values())
    assert shard_map["maximum_attempts_per_logical_call"] == 1
    assert shard_map["favorable_result_possible_with_missing_whole_shard"] is False


def test_marker_absent_on_frozen_construction_candidate() -> None:
    assert not runner.MARKER_PATH.exists()


def test_sample_size_margin_and_hierarchy() -> None:
    sample = load_json("D2D_S2_SAMPLE_SIZE.json")
    request = load_json("D2D_S2_REQUEST_PLAN.json")
    assert sample["approx_required_n"] < 88
    assert sample["minimum_analyzable_n_per_schema"] == 88
    assert sample["attempted_n_per_schema"] == 96
    assert request["gatekeeping_order"] == [
        "developed_160_minus_fresh",
        "developed_80_minus_fresh",
        "developed_40_minus_fresh",
    ]
    assert request["registered_logical_calls_if_all_pairs_complete"] == 21_120


def test_registry_and_historical_substrate_are_not_mutated() -> None:
    registry = json.loads((ROOT / "research" / "mechanisms" / "registry.json").read_text())
    node = next(
        row
        for row in registry["nodes"]
        if row.get("mechanism_id") == "d2_stochastic_capability_reproduction"
    )
    assert node["status"] == "internally_replicated"
    assert node.get("production_historical_substrate_enabled") is False
