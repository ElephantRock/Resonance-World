from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_q3d2_frozen_envelope_remains_unauthorized() -> None:
    contract = json.loads(
        (ROOT / "research/d2_vnext_q3d2/D2_VNEXT_Q3D2_CONTRACT.json").read_text()
    )
    future = contract["future_execution"]
    authority = contract["authority"]
    sample = contract["diagnostic_sample_plan"]

    assert future["provider_execution_authorized"] is False
    assert future["execution_marker_path"] == "research/d2_vnext_q3d2/RUN_D2_VNEXT_Q3D2"
    assert future["provider_triggering_workflow_path"] == ".github/workflows/d2-vnext-q3d2-diagnostic.yml"
    assert future["qualification_branch"] == "qualification/d2-vnext-q3d2-request-scoped-boundary"
    assert future["sample_plan_frozen"] is True
    assert future["campaign_send_ceiling"] == 2304
    assert future["marker_absent_candidate_required"] is True
    assert sample["pair_count"] == 8
    assert sample["shard_count"] == 2
    assert sample["scientific_effect_sample"] is False
    assert all(value is False for value in authority.values())

    assert not (ROOT / "research/d2_vnext_q3d2/RUN_D2_VNEXT_Q3D2").exists()
    assert (ROOT / ".github/workflows/d2-vnext-q3d2-diagnostic.yml").exists()


def test_future_workflow_is_exact_marker_gated() -> None:
    workflow = (ROOT / ".github/workflows/d2-vnext-q3d2-diagnostic.yml").read_text()
    assert 'paths: ["research/d2_vnext_q3d2/RUN_D2_VNEXT_Q3D2"]' in workflow
    assert 'branches: ["qualification/d2-vnext-q3d2-request-scoped-boundary"]' in workflow
    assert "github.run_attempt == 1" in workflow
    assert "github.run_attempt != 1" in workflow
    assert 'test "$(git rev-parse HEAD^)" = "$candidate"' in workflow
    assert 'test "$(git diff --name-only "$candidate" HEAD)" = "$marker"' in workflow
    assert "authorization marker must be absent from candidate" in workflow
    assert "maximum_physical_sends_campaign=//p' \"$marker\")\" = 2304" in workflow
    assert "matrix: {shard: [0, 1]}" in workflow
    assert "max-parallel: 2" in workflow


def test_q3d_closeout_is_consumed_and_non_authoritative() -> None:
    closeout = json.loads(
        (ROOT / "research/d2_vnext_q3d/D2_VNEXT_Q3_D_EXECUTION_CLOSEOUT.json").read_text()
    )
    assert closeout["status"] == "consumed_no_rerun"
    assert closeout["classification"] == "Q3-D-OBSERVABILITY-FAIL"
    assert closeout["run_attempt"] == 1
    assert closeout["semantic_completion_records"] == 0
    assert closeout["agent_invocations"] == 515
    assert closeout["boundary_labels_authoritative"] is False
    assert closeout["authority"]["q3d_rerun_authorized"] is False
