from __future__ import annotations

import json
from pathlib import Path

import pytest

import d2_vnext_q3d3_diagnostic_core as core
import materialize_d2_vnext_q3d3_diagnostic as materializer
import run_d2_vnext_q3d3_diagnostic as runner

ROOT = Path(__file__).resolve().parents[1]


def test_fresh_q3d3_namespace_and_seed_envelope() -> None:
    assert core.NAMESPACE == "rw.d2-vnext-q3d3-http-sdk-boundary-diagnostic.v1"
    assert core.STAGE == "Q3-D3"
    assert core.PAIR_COUNT == 8
    assert [core.pair_seed_for(i) for i in range(core.PAIR_COUNT)] == [
        17_000_000 + 100 * i for i in range(8)
    ]
    lock = materializer.build_cohort_lock()
    assert lock["cohort_pairs_sha256"] == (
        "648884eaaf39dda5f37ee03a75ba030308e631ba8b51e536255418efa48af661"
    )
    assert all(value == 0 for value in lock["predecessor_seed_namespace_overlap"].values())


def test_frozen_q3d3_envelope_is_exact() -> None:
    shard_map = materializer.build_shard_map()
    assert shard_map["shard_count"] == 2
    assert shard_map["pairs_per_provider_shard"] == 4
    assert shard_map["provider_local_concurrency_per_shard"] == 1
    assert shard_map["workflow_max_parallel"] == 2
    assert shard_map["maximum_registered_logical_calls_per_shard"] == 220
    assert shard_map["maximum_physical_provider_sends_per_logical_call"] == 36
    assert shard_map["maximum_physical_provider_sends_per_shard"] == 1152
    assert shard_map["maximum_physical_provider_sends_campaign"] == 2304
    assert shard_map["budget_borrowing_allowed"] is False
    assert shard_map["adaptive_n_allowed"] is False
    assert shard_map["failed_pair_replacement_allowed"] is False
    assert shard_map["same_stream_rerun_allowed"] is False
    assert [row["pair_indices"] for row in shard_map["shards"]] == [[0, 1, 2, 3], [4, 5, 6, 7]]


def test_committed_materialization_matches_builders() -> None:
    assert json.loads(
        (ROOT / "research/d2_vnext_q3d3/D2_VNEXT_Q3D3_COHORT_LOCK.json").read_text()
    ) == materializer.build_cohort_lock()
    assert json.loads(
        (ROOT / "research/d2_vnext_q3d3/D2_VNEXT_Q3D3_SHARD_MAP.json").read_text()
    ) == materializer.build_shard_map()


def test_contract_is_marker_absent_and_unauthorized() -> None:
    contract = json.loads(
        (ROOT / "research/d2_vnext_q3d3/D2_VNEXT_Q3D3_CONTRACT.json").read_text()
    )
    future = contract["future_execution"]
    assert future["provider_execution_authorized"] is False
    assert future["sample_plan_frozen"] is True
    assert future["campaign_send_ceiling"] == 2304
    assert future["execution_marker_path"] == "research/d2_vnext_q3d3/RUN_D2_VNEXT_Q3D3"
    assert future["qualification_branch"] == "qualification/d2-vnext-q3d3-http-sdk-boundary"
    assert all(value is False for value in contract["authority"].values())
    assert not (ROOT / "research/d2_vnext_q3d3/RUN_D2_VNEXT_Q3D3").exists()


def test_future_workflow_is_exact_marker_gated() -> None:
    workflow = (ROOT / ".github/workflows/d2-vnext-q3d3-diagnostic.yml").read_text()
    assert 'branches: ["qualification/d2-vnext-q3d3-http-sdk-boundary"]' in workflow
    assert 'paths: ["research/d2_vnext_q3d3/RUN_D2_VNEXT_Q3D3"]' in workflow
    assert "github.run_attempt == 1" in workflow
    assert "github.run_attempt != 1" in workflow
    assert 'test "$(git rev-parse HEAD^)" = "$candidate"' in workflow
    assert 'test "$(git diff --name-only "$candidate" HEAD)" = "$marker"' in workflow
    assert "authorization marker must be absent from candidate" in workflow
    assert "matrix: {shard: [0, 1]}" in workflow
    assert "max-parallel: 2" in workflow
    assert "D2_VNEXT_Q3D3_EXECUTION_AUTHORIZED" in workflow


def test_authority_gate_fails_without_env_or_marker(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(runner.AUTH_ENV, raising=False)
    with pytest.raises(RuntimeError, match="not authorized"):
        runner.assert_authorized()
