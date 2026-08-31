from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUEST = ROOT / "research" / "d2b" / "D2B_REPLICATION_REQUEST_PLAN.json"
COHORT = ROOT / "research" / "d2b" / "d2b-replication-cohort-lock.json"
SHARDS = ROOT / "research" / "d2b" / "D2B_SHARD_MAP.json"
SAMPLE = ROOT / "research" / "d2b" / "D2B_REPLICATION_SAMPLE_SIZE.json"
REGISTRY = ROOT / "research" / "mechanisms" / "registry.json"
ACCEPTANCE = ROOT / "research" / "acceptance" / "d2" / "PROMOTION_EVENTS.json"
MARKER = ROOT / "research" / "d2b" / "RUN_D2B_REPLICATION"


def test_d2b_frozen_request_contract() -> None:
    request = json.loads(REQUEST.read_text())
    cohort = json.loads(COHORT.read_text())
    shards = json.loads(SHARDS.read_text())
    sample = json.loads(SAMPLE.read_text())

    assert request["schema"] == "d2b-replication-request-plan-v0.1"
    assert request["preregistration_issue"] == 186
    assert request["provider"] == "Z.AI"
    assert request["model"] == "glm-5-turbo"
    assert request["temperature"] == 0.8
    assert request["thinking"] == "disabled"
    assert request["pair_count_attempted"] == 360
    assert request["minimum_analyzable_pairs"] == 330
    assert request["provider_shard_count"] == 18
    assert request["pairs_per_provider_shard"] == 20
    assert request["provider_local_concurrency_per_shard"] == 1
    assert request["provider_matrix_max_parallel"] == 4
    assert request["provider_shard_timeout_minutes"] == 240
    assert request["logical_calls_per_complete_pair"] == {
        "description_only": 9,
        "fresh": 4,
        "reproduced": 9,
        "source_developed": 9,
        "total": 31,
    }
    assert request["logical_calls_campaign_before_retries"] == 11160
    assert request["max_attempts_per_logical_call"] == 8
    assert request["minimum_request_interval_seconds"] == 0.35
    assert request["pair_replacement"] is False
    assert request["shard_job_rerun_allowed"] is False
    assert request["confirmatory_same_request_stream_rerun_allowed"] is False
    assert request["historical_substrate_enabled"] is False
    assert request["cohort_pairs_sha256"] == cohort["cohort_pairs_sha256"]
    assert cohort["cohort_pairs_sha256"] == (
        "b4d8f39b9730de6869b6b3c3f9ceb4d16c76214b8eee9437c2bca62e85286b23"
    )
    assert cohort["production_historical_substrate_enabled"] is False
    assert shards["pair_count_attempted"] == 360
    assert shards["shard_count"] == 18
    assert shards["production_historical_substrate_enabled"] is False
    assert sample["attempted_pairs"] == 360
    assert sample["minimum_analyzable_pairs"] == 330
    assert sample["P2"]["required_n"] == 328


def test_d2b_reserved_seed_namespace_is_disjoint() -> None:
    request = json.loads(REQUEST.read_text())
    base = request["seed_series"]["base"]
    step = request["seed_series"]["step"]
    offsets = {
        request["seed_series"]["source_offset"],
        request["seed_series"]["destination_offset"],
        request["seed_series"]["evaluation_offset"],
    }
    assert base == 3_200_000
    assert step == 100
    assert offsets == {1, 2, 3}

    def namespace(seed_base: int) -> set[int]:
        return {
            seed_base + pair_index * step + offset
            for pair_index in range(360)
            for offset in offsets
        }

    d2b = namespace(3_200_000)
    assert d2b.isdisjoint(namespace(1_200_000))
    assert d2b.isdisjoint(namespace(2_200_000))


def test_registry_and_acceptance_prerequisite_are_preserved() -> None:
    registry = json.loads(REGISTRY.read_text())
    matches = [
        node
        for node in registry["nodes"]
        if node.get("mechanism_id") == "d2_stochastic_capability_reproduction"
    ]
    assert len(matches) == 1
    node = matches[0]
    assert node["status"] == "discovery_supported"
    assert node["production_historical_substrate_enabled"] is False
    assert "D2-C2" in node["evidence"]

    acceptance = json.loads(ACCEPTANCE.read_text())
    assert acceptance["registry_node"] == "d2_stochastic_capability_reproduction"
    assert acceptance["decision"] == "ACCEPT discovery_supported"
    assert acceptance["production_historical_substrate_enabled"] is False


def test_authorization_marker_if_present_is_well_formed() -> None:
    if not MARKER.exists():
        return
    fields = {}
    for line in MARKER.read_text().splitlines():
        key, value = line.split("=", 1)
        fields[key] = value
    assert fields["issue"] == "186"
    assert len(fields["candidate_sha"]) == 40
