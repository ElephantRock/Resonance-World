from __future__ import annotations

from pathlib import Path

import d2_vnext_q1_acquisition_core as core
import materialize_d2_vnext_q1_acquisition as materializer

EXPECTED_A = "21ae386da6fdba2883a331864fcaffc51f9fa8adb58aa43ee9d68519cadc3686"
EXPECTED_B = "41124075eeda43439b392997b090ed7fe11275271b4bae86bc619371f86a750e"


def test_stage_sizes_and_interleaving() -> None:
    assert core.pair_count(core.STAGE_A) == 64
    assert core.pair_count(core.STAGE_B) == 384
    for stage in core.STAGES:
        shard_map = materializer.build_shard_map(stage)
        assert shard_map["mixed_schema_shards"] is True
        assert shard_map["pairs_per_provider_shard"] == 16
        assert shard_map["pairs_per_schema_per_shard"] == 4
        for shard in shard_map["shards"]:
            assert shard["schema_counts"] == {schema: 4 for schema in core.SCHEMA_ORDER}


def test_pinned_cohort_commitments() -> None:
    a = materializer.build_cohort_lock(core.STAGE_A)
    b = materializer.build_cohort_lock(core.STAGE_B)
    assert a["cohort_pairs_sha256"] == EXPECTED_A
    assert b["cohort_pairs_sha256"] == EXPECTED_B
    assert materializer.EXPECTED_COHORT_SHA256 == {
        core.STAGE_A: EXPECTED_A,
        core.STAGE_B: EXPECTED_B,
    }


def test_stage_seed_namespaces_are_fresh_and_separate() -> None:
    materializer.validate_cross_stage_seed_separation()
    for stage in core.STAGES:
        lock = materializer.build_cohort_lock(stage)
        assert lock["cross_schema_seed_overlap"] == 0
        assert all(value == 0 for value in lock["predecessor_seed_namespace_overlap"].values())
        assert lock["all_development_evaluation_overlaps_zero"] is True


def test_resource_topology_matches_frozen_contract() -> None:
    a = materializer.build_shard_map(core.STAGE_A)
    b = materializer.build_shard_map(core.STAGE_B)
    assert a["shard_count"] == 4
    assert a["maximum_physical_provider_sends_campaign"] == 4608
    assert b["shard_count"] == 24
    assert b["maximum_physical_provider_sends_campaign"] == 27648
    for data in (a, b):
        assert data["maximum_registered_logical_calls_per_shard"] == 880
        assert data["maximum_physical_provider_sends_per_logical_call"] == 36
        assert data["maximum_physical_provider_sends_per_shard"] == 1152


def test_construction_markers_absent() -> None:
    root = Path(__file__).resolve().parents[1] / "research" / "d2_vnext_q1"
    assert not (root / "RUN_D2_VNEXT_Q1_A").exists()
    assert not (root / "RUN_D2_VNEXT_Q1_B").exists()
