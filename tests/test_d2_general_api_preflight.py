from __future__ import annotations

import importlib.util
import json
from pathlib import Path

SCRIPT = Path("scripts/preflight_d2_general_api.py")
PLAN = Path("research/d2_general_api_preflight/PREFLIGHT_REQUEST_PLAN.json")
MARKER = Path("research/d2_general_api_preflight/RUN_D2_GENERAL_API_PREFLIGHT")

spec = importlib.util.spec_from_file_location("d2_general_preflight", SCRIPT)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_request_plan_is_engineering_only_and_unauthorized() -> None:
    plan = json.loads(PLAN.read_text())
    assert plan["issue"] == 202
    assert plan["engineering_only"] is True
    assert plan["provider_execution_authorized"] is False
    assert plan["endpoint"] == "https://api.z.ai/api/paas/v4/chat/completions"
    assert "/coding/" not in plan["endpoint"]
    assert plan["model"] == "glm-5-turbo"
    assert plan["request_count"] == 3
    assert plan["max_attempts_per_request"] == 1
    assert plan["scientific_field_trajectory_executed"] is False
    assert plan["scientific_scoring_performed"] is False
    assert plan["registry_promotion_authorized"] is False
    assert plan["historical_substrate_enabled"] is False


def test_materialization_is_deterministic_and_bounded() -> None:
    first = module.materialized_plan()
    second = module.materialized_plan()
    assert first == second
    assert first["request_count"] == 3
    assert first["request_ids"] == list(module.REQUEST_IDS)
    assert len(first["request_body_sha256"]) == 3
    assert all(len(value) == 64 for value in first["request_body_sha256"].values())
    assert first["max_attempts_per_request"] == 1
    assert first["provider_execution_authorized"] is False
    assert first["production_historical_substrate_enabled"] is False


def test_request_matrix_uses_exact_general_api_contract() -> None:
    rows = module.request_matrix()
    assert len(rows) == 3
    assert {row["diagnostic_id"] for row in rows} == set(module.REQUEST_IDS)
    for row in rows:
        body = row["body"]
        assert body["model"] == "glm-5-turbo"
        assert body["temperature"] == 0.8
        assert body["thinking"] == {"type": "disabled"}
        assert body["stream"] is False
        assert body["max_tokens"] == 256
    assert "response_format" not in rows[0]["body"]
    assert rows[1]["body"]["response_format"] == {"type": "json_object"}
    assert rows[2]["body"]["response_format"] == {"type": "json_object"}


def test_d2_shape_probe_is_non_scientific_and_eight_case() -> None:
    rows = {row["diagnostic_id"]: row for row in module.request_matrix()}
    user = rows["general_d2_shape_json"]["body"]["messages"][1]["content"]
    assert "engineering transport-shape probe" in user
    assert "not a task-solving benchmark" in user
    assert len(module.d2_shape_cases()) == 8


def test_error_summary_never_preserves_raw_message() -> None:
    raw = json.dumps({"error": {"code": 1313, "message": "sensitive provider explanation"}})
    summary = module.summarize_error_body(raw)
    assert summary["provider_code"] == "1313"
    assert summary["provider_message_length"] == len("sensitive provider explanation")
    assert summary["provider_message_sha256"] == module.sha256_text(
        "sensitive provider explanation"
    )
    assert "sensitive provider explanation" not in json.dumps(summary)


def test_success_validation_exact_model_and_shape() -> None:
    outer = {
        "model": "glm-5-turbo",
        "choices": [
            {
                "message": {
                    "content": json.dumps(
                        {"actions": ["KAPPA"] * 8},
                        separators=(",", ":"),
                    )
                }
            }
        ],
    }
    result = module.validate_success(json.dumps(outer), "general_d2_shape_json")
    assert result["outer_json_valid"] is True
    assert result["model_exact_match"] is True
    assert result["content_present"] is True
    assert result["content_json_valid"] is True
    assert result["actions_shape_valid"] is True
    assert result["contract_pass"] is True


def test_model_drift_fails_contract() -> None:
    outer = {
        "model": "glm-5.3-flash",
        "choices": [{"message": {"content": json.dumps({"status": "ok"})}}],
    }
    result = module.validate_success(json.dumps(outer), "general_minimal_json")
    assert result["model_exact_match"] is False
    assert result["content_json_valid"] is True
    assert result["contract_pass"] is False


def test_execution_marker_absent_before_separate_authorization() -> None:
    assert not MARKER.exists()
