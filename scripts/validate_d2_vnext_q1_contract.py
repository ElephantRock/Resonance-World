#!/usr/bin/env python3
# ruff: noqa: E501
"""Credential-free structural validation for the D2-vNext-Q1 contract.

This validator performs no provider/model calls and must remain safe to run in ordinary CI.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESEARCH = ROOT / "research" / "d2_vnext_q1"
CONTRACT = RESEARCH / "D2_VNEXT_Q1_CONTRACT.json"
OBSERVABILITY = RESEARCH / "D2_VNEXT_Q1_FAILURE_OBSERVABILITY_SCHEMA.json"
SAMPLE_SIZE = RESEARCH / "D2_VNEXT_Q1_SAMPLE_SIZE.json"
REQUEST_PLAN = RESEARCH / "D2_VNEXT_Q1_REQUEST_PLAN.json"
SCHEMA_SUITE = RESEARCH / "D2_VNEXT_Q1_SCHEMA_SUITE.json"
A_LOCK = RESEARCH / "D2_VNEXT_Q1_A_COHORT_LOCK.json"
B_LOCK = RESEARCH / "D2_VNEXT_Q1_B_COHORT_LOCK.json"
A_MAP = RESEARCH / "D2_VNEXT_Q1_A_SHARD_MAP.json"
B_MAP = RESEARCH / "D2_VNEXT_Q1_B_SHARD_MAP.json"
EXPECTED_A_COHORT = "21ae386da6fdba2883a331864fcaffc51f9fa8adb58aa43ee9d68519cadc3686"
EXPECTED_B_COHORT = "41124075eeda43439b392997b090ed7fe11275271b4bae86bc619371f86a750e"
EXECUTION_MARKERS = (
    RESEARCH / "RUN_D2_VNEXT_Q1_A",
    RESEARCH / "RUN_D2_VNEXT_Q1_B",
)


def load(path: Path) -> dict:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise AssertionError(f"expected object: {path}")
    return value


def main() -> None:
    contract = load(CONTRACT)
    obs = load(OBSERVABILITY)
    sample = load(SAMPLE_SIZE)
    request = load(REQUEST_PLAN)
    suite = load(SCHEMA_SUITE)
    a_lock = load(A_LOCK)
    b_lock = load(B_LOCK)
    a_map = load(A_MAP)
    b_map = load(B_MAP)

    assert contract["schema"] == "d2-vnext-q1-acquisition-qualification-contract-v0.1"
    assert contract["issue"] == 290
    assert contract["study_stream"] == "D2-vNext-Q1"
    assert contract["status"] == "construction_only_provider_execution_not_authorized"
    assert contract["governance"]["provider_execution_authorized"] is False
    assert contract["governance"]["historical_substrate_enabled"] is False

    product = contract["supported_product"]
    assert product["requested_model"] == "glm-5.3"
    assert product["temperature"] == 0.8
    assert product["thinking"] == "disabled"
    assert product["response_format"] == {"type": "json_object"}
    assert product["format_regeneration_retries_max"] == 1
    assert product["raw_first_response_content_in_retry_prompt"] is False
    assert product["raw_response_content_persisted_in_failure_record"] is False

    assert request["schema"] == "d2-vnext-q1-acquisition-qualification-request-plan-v0.1"
    assert request["issue"] == 290
    assert request["requested_model"] == product["requested_model"]
    assert request["sampling_temperature"] == product["temperature"]
    assert request["provider_execution_authorized"] is False
    assert request["qualification_campaign_authorized"] is False
    assert request["scientific_effect_gates_authorized"] is False
    assert request["same_request_stream_rerun_allowed"] is False
    assert request["max_physical_provider_sends_per_logical_call"] == 36
    assert request["max_physical_provider_sends_per_shard"] == 1152

    assert suite["schema"] == "d2-vnext-q1-acquisition-qualification-schema-suite-v0.1"
    assert suite["fresh_namespace"] == "rw.d2-vnext-q1-acquisition-qualification.v1"
    assert [row["id"] for row in suite["schemas"]] == contract["schemas"]
    assert suite["stages"]["Q1-A"]["pairs_per_schema"] == 16
    assert suite["stages"]["Q1-B"]["pairs_per_schema"] == 96
    assert suite["future_use"]["eligible_as_scientific_effect_evidence"] is False

    shards = contract["sharding"]
    assert shards["mixed_schema_shards"] is True
    assert shards["pairs_per_shard"] == 16
    assert shards["pairs_per_schema_per_shard"] == 4
    assert 4 * shards["pairs_per_schema_per_shard"] == shards["pairs_per_shard"]
    assert shards["predecessor_seed_overlap_allowed"] is False

    topology = contract["transport_topology"]
    assert topology["maximum_registered_logical_calls_per_shard"] == 880
    assert topology["maximum_physical_sends_per_logical_call"] == 36
    assert topology["maximum_physical_sends_per_shard"] == 1152
    assert topology["cross_shard_budget_borrowing_allowed"] is False

    a = contract["q1_a"]
    assert a["attempted_pairs_per_schema"] == 16
    assert a["attempted_pairs_total"] == 64
    assert a["shard_count"] == 4
    assert a["maximum_physical_sends_campaign"] == a["shard_count"] * 1152 == 4608
    assert a["continuation_gate"]["minimum_complete_analyzable_pairs_per_schema"] == 12
    assert a["primary_q1_b_estimator_includes_q1_a"] is False
    assert a["provider_execution_authorized"] is False

    b = contract["q1_b"]
    assert b["attempted_pairs_per_schema"] == 96
    assert b["attempted_pairs_total"] == 384
    assert b["shard_count"] == 24
    assert b["maximum_physical_sends_campaign"] == b["shard_count"] * 1152 == 27648
    assert b["independent_from_q1_a"] is True
    assert b["provider_execution_authorized"] is False

    assert a_lock["cohort_pairs_sha256"] == EXPECTED_A_COHORT
    assert b_lock["cohort_pairs_sha256"] == EXPECTED_B_COHORT
    assert a_lock["pair_count"] == 64 and a_lock["pairs_per_schema"] == 16
    assert b_lock["pair_count"] == 384 and b_lock["pairs_per_schema"] == 96
    for lock in (a_lock, b_lock):
        assert lock["cross_schema_seed_overlap"] == 0
        assert all(value == 0 for value in lock["predecessor_seed_namespace_overlap"].values())
        assert lock["production_historical_substrate_enabled"] is False
    assert a_map["shard_count"] == 4 and a_map["maximum_physical_provider_sends_campaign"] == 4608
    assert b_map["shard_count"] == 24 and b_map["maximum_physical_provider_sends_campaign"] == 27648
    for shard_map in (a_map, b_map):
        assert shard_map["mixed_schema_shards"] is True
        assert shard_map["pairs_per_provider_shard"] == 16
        assert shard_map["pairs_per_schema_per_shard"] == 4
        assert shard_map["maximum_registered_logical_calls_per_shard"] == 880
        assert shard_map["maximum_physical_provider_sends_per_shard"] == 1152
        for row in shard_map["shards"]:
            assert row["schema_counts"] == {
                "threshold_at_4": 4,
                "parity_pair": 4,
                "interval_pair": 4,
                "pairwise_order": 4,
            }

    stats = contract["qualification_statistics"]
    assert stats["future_minimum_analyzable_pairs_per_schema"] == 88
    assert stats["future_joint_all_schema_clearance_target"] == 0.95
    assert stats["per_schema_clearance_target"] == 0.9875
    assert stats["per_schema_lower_bound_alpha"] == 0.0125
    assert stats["per_schema_lower_bound_confidence"] == 0.9875
    assert stats["s2_data_pooled"] is False
    assert stats["scientific_effect_gates_computed"] is False

    resource = contract["future_resource_feasibility"]
    assert resource["maximum_sum_attempted_pairs_across_schemas"] == 640
    assert resource["maximum_future_mixed_schema_shards"] == 40
    assert resource["maximum_physical_sends_per_future_shard"] == 1152
    assert resource["maximum_future_topology_physical_sends"] == 40 * 1152 == 46080
    assert resource["existing_campaign_boundary_physical_sends"] == 48000
    assert resource["reserved_headroom_physical_sends"] == 48000 - 46080 == 1920

    assert sample["stage_a"]["attempted_pairs_total"] == a["attempted_pairs_total"]
    assert sample["stage_a"]["maximum_physical_sends_campaign"] == a["maximum_physical_sends_campaign"]
    assert sample["stage_b"]["attempted_pairs_total"] == b["attempted_pairs_total"]
    assert sample["stage_b"]["maximum_physical_sends_campaign"] == b["maximum_physical_sends_campaign"]

    assert obs["raw_response_content_allowed"] is False
    forbidden = set(obs["forbidden_fields_or_payloads"])
    assert "raw_response_text" in forbidden
    assert "raw_first_response_text" in forbidden
    invariants = obs["instrumentation_invariants"]
    assert invariants["may_change_retry_count"] is False
    assert invariants["may_change_retry_eligibility"] is False
    assert invariants["may_change_prompt_content"] is False
    assert invariants["may_change_terminal_acceptance"] is False
    assert invariants["may_change_scientific_output"] is False

    for marker in EXECUTION_MARKERS:
        if marker.exists():
            raise AssertionError(f"Q1 execution marker must be absent during construction: {marker}")

    print("D2-vNext-Q1 contract validation PASS (credential-free; provider execution not authorized)")


if __name__ == "__main__":
    main()
