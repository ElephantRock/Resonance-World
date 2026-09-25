from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_q3d2_construction_remains_credential_free() -> None:
    contract = json.loads(
        (ROOT / "research/d2_vnext_q3d2/D2_VNEXT_Q3D2_CONTRACT.json").read_text()
    )
    future = contract["future_execution"]
    authority = contract["authority"]

    assert future["provider_execution_authorized"] is False
    assert future["execution_marker_path"] is None
    assert future["provider_triggering_workflow_path"] is None
    assert future["sample_plan_frozen"] is False
    assert future["campaign_send_ceiling"] is None
    assert all(value is False for value in authority.values())

    assert not (ROOT / "research/d2_vnext_q3d2/RUN_D2_VNEXT_Q3D2").exists()
    assert not (ROOT / ".github/workflows/d2-vnext-q3d2-diagnostic.yml").exists()


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
