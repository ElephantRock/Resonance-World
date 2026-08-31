from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUEST = ROOT / "research" / "d2b" / "REQUEST_PLAN_DRAFT.json"
REGISTRY = ROOT / "research" / "mechanisms" / "registry.json"
MARKER = ROOT / "research" / "d2b" / "RUN_D2B_REPLICATION"


def test_d2b_scaffold_contract() -> None:
    request = json.loads(REQUEST.read_text())
    assert request["status"] == "prospective_zero_provider_scaffold_not_execution_candidate"
    assert request["preregistration_issue"] == 186
    assert request["provider"] == "Z.AI"
    assert request["model"] == "glm-5-turbo"
    assert request["temperature"] == 0.8
    assert request["thinking"] == "disabled"
    assert request["pair_count_attempted"] == 360
    assert request["minimum_analyzable_pairs"] == 330
    assert request["p0_threshold"] == 0.1
    assert request["p1_threshold"] == 0.1
    assert request["p2_fidelity_fraction"] == 0.9
    assert request["alpha_one_sided"] == 0.05
    assert request["gatekeeping"] == ["P0", "P1", "P2"]
    assert request["provider_shards"] == 18
    assert request["pairs_per_shard"] == 20
    assert request["provider_local_concurrency_per_shard"] == 1
    assert request["workflow_matrix_max_parallel"] == 4
    assert request["provider_shard_timeout_minutes"] == 240
    assert request["logical_calls_per_complete_pair"] == 31
    assert request["logical_calls_if_all_pairs_complete"] == 11160
    assert request["max_attempts_per_logical_call"] == 8
    assert request["minimum_request_start_interval_seconds"] == 0.35
    assert request["pair_replacement_allowed"] is False
    assert request["imputation_allowed"] is False
    assert request["outcome_adaptive_n_allowed"] is False
    assert request["threshold_retuning_allowed"] is False
    assert request["same_request_stream_rerun_allowed"] is False
    assert request["automatic_registry_promotion"] is False
    assert request["production_historical_substrate_enabled"] is False
    assert request["cohort_lock_sha256"] is None
    assert request["scientific_candidate_sha"] is None
    assert request["authorization_marker_present"] is False
    assert not MARKER.exists()


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
    c1 = namespace(1_200_000)
    c2 = namespace(2_200_000)
    assert d2b.isdisjoint(c1)
    assert d2b.isdisjoint(c2)


def test_registry_prerequisite_is_discovery_supported() -> None:
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
