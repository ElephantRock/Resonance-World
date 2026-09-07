from __future__ import annotations

import json
import sys
from pathlib import Path

import d2_vnext_s1_acquisition_core as core
import d2_vnext_s1_hermes_client as hermes
import evaluate_d2_vnext_s1_source_acquisition as evaluator
import materialize_d2_vnext_s1_source_acquisition as materializer


def test_fresh_namespace_and_frozen_cohort() -> None:
    lock = materializer.build_cohort_lock()
    assert lock["cohort_pairs_sha256"] == materializer.EXPECTED_COHORT_SHA256
    assert lock["pair_count"] == 384
    assert lock["pairs_per_schema"] == 96
    assert lock["cross_schema_seed_overlap"] == 0
    assert all(value == 0 for value in lock["predecessor_seed_namespace_overlap"].values())
    assert lock["all_development_evaluation_overlaps_zero"] is True
    assert lock["production_historical_substrate_enabled"] is False
    assert core.SCHEMA_SEED_BASES == {
        "threshold_at_4": 9_000_000,
        "parity_pair": 9_200_000,
        "interval_pair": 9_400_000,
        "pairwise_order": 9_600_000,
    }


def test_shard_topology_and_physical_caps() -> None:
    shard_map = materializer.build_shard_map()
    assert shard_map["shard_count"] == 24
    assert shard_map["pairs_per_provider_shard"] == 16
    assert shard_map["workflow_max_parallel"] == 4
    assert shard_map["logical_calls_per_complete_pair"] == 55
    assert shard_map["registered_logical_calls_if_all_pairs_complete"] == 21_120
    assert shard_map["maximum_physical_provider_sends_per_shard"] == 1_000
    assert shard_map["maximum_physical_provider_sends_campaign"] == 24_000
    assert shard_map["favorable_result_possible_with_missing_whole_shard"] is False


def test_physical_send_budget_blocks_foreign_and_over_budget_requests() -> None:
    budget = hermes.ShardPhysicalSendBudget()
    budget.begin_logical_call("registered")
    try:
        budget.reserve("https://example.com/not-allowed")
    except hermes.ScientificUnexpectedOutboundRequest:
        pass
    else:
        raise AssertionError("foreign outbound request was not blocked")
    assert budget.blocked_unexpected == 1

    for _ in range(hermes.MAX_PHYSICAL_SENDS_PER_LOGICAL_CALL):
        budget.reserve(hermes.BASE_URL + "/chat/completions")
    try:
        budget.reserve(hermes.BASE_URL + "/chat/completions")
    except hermes.ScientificPhysicalSendBudgetExceeded:
        pass
    else:
        raise AssertionError("per-logical-call physical cap was not enforced")
    assert budget.total == hermes.MAX_PHYSICAL_SENDS_PER_LOGICAL_CALL
    assert budget.blocked_budget == 1


def test_client_parses_strict_registered_response_without_network(monkeypatch) -> None:
    budget = hermes.ShardPhysicalSendBudget()
    client = hermes.Client.__new__(hermes.Client)
    client.budget = budget
    client.logical_calls_started = 0
    client.logical_calls_completed = 0
    client.logical_call_failures = 0
    client._counter = 0

    class FakeAgent:
        _api_call_count = 1

        def run_conversation(self, *, user_message: str):
            logical, index = budget.reserve(hermes.BASE_URL + "/chat/completions")
            budget.record_response(logical, index, 200)
            return {
                "completed": True,
                "failed": False,
                "error": None,
                "final_response": json.dumps(
                    {"actions": ["KAPPA", "MICA"], "strategy": "test strategy"},
                    separators=(",", ":"),
                ),
            }

    monkeypatch.setattr(client, "_new_agent", lambda system: FakeAgent())
    result = client.complete(
        phase="test/evaluation",
        system="system",
        user="user",
        expected_actions=2,
        temperature=0.8,
    )
    assert result["actions"] == ["KAPPA", "MICA"]
    assert result["strategy"] == "test strategy"
    assert result["model"] == "glm-5.3"
    assert result["effective_model_identity_observed"] is False
    assert result["thinking"] == "disabled"
    assert len(result["attempts"]) == 1
    assert result["attempts"][0]["http_status"] == 200
    assert client.logical_calls_completed == 1


def test_client_rejects_malformed_scientific_response(monkeypatch) -> None:
    budget = hermes.ShardPhysicalSendBudget()
    client = hermes.Client.__new__(hermes.Client)
    client.budget = budget
    client.logical_calls_started = 0
    client.logical_calls_completed = 0
    client.logical_call_failures = 0
    client._counter = 0

    class FakeAgent:
        _api_call_count = 1

        def run_conversation(self, *, user_message: str):
            logical, index = budget.reserve(hermes.BASE_URL + "/chat/completions")
            budget.record_response(logical, index, 200)
            return {
                "completed": True,
                "failed": False,
                "error": None,
                "final_response": "not-json",
            }

    monkeypatch.setattr(client, "_new_agent", lambda system: FakeAgent())
    try:
        client.complete(
            phase="test/failure",
            system="system",
            user="user",
            expected_actions=1,
            temperature=0.8,
        )
    except json.JSONDecodeError:
        pass
    else:
        raise AssertionError("malformed scientific response was accepted")
    assert client.logical_call_failures == 1


def test_all_failed_provider_output_is_valid_negative_a0() -> None:
    records = []
    for pair_index in range(384):
        schema_id, local = core.schema_and_local_index(pair_index)
        records.append(
            {
                "status": "failed",
                "pair_index": pair_index,
                "schema_id": schema_id,
                "schema_pair_index": local,
                "pair_public_id": f"d2-vnext-s1-{schema_id}-pair-{local:03d}",
                "failure_class": "provider_pair_failure",
            }
        )
    provider = {
        "schema": "d2-vnext-s1-source-acquisition-provider-output-v0.1",
        "study_stream": "D2-vNext-S1",
        "status": "provider_campaign_complete_unclassified",
        "classification": None,
        "attempted_pairs": 384,
        "complete_pairs": 0,
        "failed_pairs": 384,
        "requested_model": "glm-5.3",
        "effective_model_identity_observed": False,
        "effective_model": None,
        "temperature": 0.8,
        "thinking": "disabled",
        "cohort_pairs_sha256": materializer.EXPECTED_COHORT_SHA256,
        "physical_provider_sends_observed_total": 0,
        "maximum_physical_provider_sends_campaign": 24_000,
        "pair_records": records,
        "shard_inputs": [],
        "production_historical_substrate_enabled": False,
    }
    result = evaluator.evaluate(provider)
    assert result["classification"] == "D2-vNext-S1-A0"
    assert result["common_confirmed_acquisition_budget"] is None
    assert result["transport_integrity"]["passed"] is True
    assert all(value == 0 for value in result["analyzable_pairs_by_schema"].values())
    assert result["registry_promotion_authorized"] is False
    assert result["acceptance_action_authorized"] is False
    assert result["production_historical_substrate_enabled"] is False


def test_committed_materialization_matches_builder() -> None:
    root = Path(__file__).resolve().parents[1]
    lock = json.loads(
        (root / "research/d2_vnext_s1/d2-vnext-s1-source-acquisition-cohort-lock.json").read_text()
    )
    shards = json.loads(
        (root / "research/d2_vnext_s1/D2_VNEXT_S1_SHARD_MAP.json").read_text()
    )
    assert lock == materializer.build_cohort_lock()
    assert shards == materializer.build_shard_map()
