from __future__ import annotations

import importlib.util
import json
from pathlib import Path

SCRIPT = Path("scripts/diagnose_d2d_provider_runtime.py")
PLAN = Path("research/d2d_diag/DIAGNOSTIC_REQUEST_PLAN.json")
MARKER = Path("research/d2d_diag/RUN_D2D_PROVIDER_DIAGNOSTIC")

spec = importlib.util.spec_from_file_location("d2d_diag", SCRIPT)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_request_plan_is_engineering_only_and_unauthorized() -> None:
    plan = json.loads(PLAN.read_text())
    assert plan["issue"] == 200
    assert plan["engineering_only"] is True
    assert plan["provider_execution_authorized"] is False
    assert plan["request_count"] == 3
    assert plan["max_attempts_per_request"] == 1
    assert plan["scientific_field_trajectory_executed"] is False
    assert plan["replacement_d2d_data_allowed"] is False
    assert plan["registry_promotion_authorized"] is False
    assert plan["historical_substrate_enabled"] is False


def test_materialization_is_deterministic_and_bounded() -> None:
    first = module.materialized_plan()
    second = module.materialized_plan()
    assert first == second
    assert first["request_count"] == 3
    assert first["request_ids"] == [
        "minimal_json",
        "d2d_shape_json",
        "d2d_shape_text",
    ]
    assert len(first["request_body_sha256"]) == 3
    assert all(len(value) == 64 for value in first["request_body_sha256"].values())
    assert first["provider_execution_authorized"] is False
    assert first["production_historical_substrate_enabled"] is False


def test_request_matrix_has_no_retry_or_scientific_scoring_contract() -> None:
    rows = module.request_matrix()
    assert len(rows) == 3
    assert {row["diagnostic_id"] for row in rows} == set(module.REQUEST_IDS)
    for row in rows:
        body = module.request_body(row)
        assert body["model"] == "glm-5-turbo"
        assert body["temperature"] == 0.8
        assert body["thinking"] == {"type": "disabled"}
        assert body["stream"] is False
        assert "Authorization" not in json.dumps(body)


def test_error_summary_never_preserves_raw_message() -> None:
    raw = json.dumps({"code": 1313, "message": "sensitive provider explanation"})
    summary = module.summarize_error_body(raw)
    assert summary["provider_code"] == "1313"
    assert summary["provider_message_length"] == len("sensitive provider explanation")
    assert summary["provider_message_sha256"] == module.sha256_text(
        "sensitive provider explanation"
    )
    assert "sensitive provider explanation" not in json.dumps(summary)


def test_success_validation_distinguishes_json_shape() -> None:
    valid_outer = {
        "model": "glm-5-turbo",
        "choices": [
            {
                "message": {
                    "content": json.dumps(
                        {"actions": ["KAPPA"] * 8}, separators=(",", ":")
                    )
                }
            }
        ],
    }
    result = module.validate_success(json.dumps(valid_outer), "minimal_json")
    assert result["outer_json_valid"] is True
    assert result["content_present"] is True
    assert result["content_json_valid"] is True
    assert result["actions_shape_valid"] is True


def test_execution_marker_absent_before_separate_authorization() -> None:
    assert not MARKER.exists()
