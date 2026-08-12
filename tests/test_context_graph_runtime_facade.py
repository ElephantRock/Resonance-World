"""Contract tests for the graduated World -> ContextGraph runtime facade."""

from __future__ import annotations

import inspect

import pytest

pytest.importorskip("resonance_contextgraph")

import resonance_world.context_graph_runtime as runtime


def test_runtime_facade_points_to_tested_standalone_release_candidate() -> None:
    assert runtime.STANDALONE_REPOSITORY == "ElephantRock/Resonance-ContextGraph"
    assert runtime.STANDALONE_TESTED_COMMIT == "55ce7bb435b3d4a1ff888474a5ca76ccff843150"
    assert runtime.ARCHITECTURAL_PARITY_RUN == 31638124103
    assert runtime.LEGACY_WORLD_MODULE_STATUS == "scientific-compatibility-fixture"


def test_runtime_facade_exposes_adapter_operations_not_world_truth() -> None:
    source = inspect.getsource(runtime)
    assert "practice_by_skill" not in source
    assert "JointEnvironment" not in source
    assert "_oracle_pair" not in source
    assert "context_graph_w3_endogenous" not in source

    expected = {
        "build_evidence_store",
        "checkpoint_from_live_contexts",
        "choose_stopping_point",
        "compile_live_context",
        "next_balanced_cell",
        "pair_from_live_context",
        "to_evidence_claim",
        "to_mission_spec",
        "validated_estimator",
    }
    assert expected.issubset(set(runtime.__all__))
