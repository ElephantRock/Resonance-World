from __future__ import annotations

import json
from pathlib import Path


def test_q3d4_contract_keeps_execution_authority_absent() -> None:
    contract = json.loads(
        Path("research/d2_vnext_q3d4/D2_VNEXT_Q3D4_CONTRACT.json").read_text()
    )
    future = contract["future_execution"]
    authority = contract["authority"]

    assert future["provider_execution_authorized"] is False
    assert future["sample_plan_frozen"] is False
    assert future["fresh_namespace"] is None
    assert future["pair_count"] is None
    assert future["campaign_send_ceiling"] is None
    assert future["execution_marker_path"] is None
    assert future["provider_triggering_workflow_path"] is None
    assert future["qualification_branch"] is None
    assert all(value is False for value in authority.values())


def test_q3d3_provider_workflow_is_retired() -> None:
    workflow = Path(".github/workflows/d2-vnext-q3d3-diagnostic.yml").read_text()
    assert "(retired)" in workflow
    assert "36226997038" in workflow
    assert "provider-shards" not in workflow
    assert "ZAI_API_KEY" not in workflow
    assert "run_d2_vnext_q3d3_diagnostic.py" not in workflow
    assert "exit 1" in workflow


def test_q3d3_preexecution_is_retired() -> None:
    workflow = Path(".github/workflows/d2-vnext-q3d3-preexecution.yml").read_text()
    assert "(retired)" in workflow
    assert "36226997038" in workflow
    assert "pytest" not in workflow
    assert "materialize_d2_vnext_q3d3_diagnostic.py" not in workflow
    assert "exit 1" in workflow


def test_q3d4_has_no_execution_marker_or_provider_workflow() -> None:
    assert not Path("research/d2_vnext_q3d4/RUN_D2_VNEXT_Q3D4").exists()
    assert not Path(".github/workflows/d2-vnext-q3d4-diagnostic.yml").exists()
