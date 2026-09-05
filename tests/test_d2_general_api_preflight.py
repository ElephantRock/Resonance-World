from __future__ import annotations

import http.client
import importlib.util
import json
import urllib.error
import urllib.request
from pathlib import Path

SCRIPT = Path("scripts/preflight_d2_general_api.py")
PLAN = Path("research/d2_general_api_preflight/PREFLIGHT_REQUEST_PLAN.json")
MARKER = Path("research/d2_general_api_preflight/RUN_D2_GENERAL_API_PREFLIGHT")
CLOSEOUT = Path("research/d2_general_api_preflight/D2_GENERAL_API_PREFLIGHT_CLOSEOUT.json")

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


def test_nonstandard_json_constants_fail_contract() -> None:
    outer = {
        "model": "glm-5-turbo",
        "choices": [{"message": {"content": '{"status":NaN}'}}],
    }
    result = module.validate_success(json.dumps(outer), "general_minimal_json")
    assert result["outer_json_valid"] is True
    assert result["content_present"] is True
    assert result["content_json_valid"] is False
    assert result["contract_pass"] is False

    invalid_outer = (
        '{"model":"glm-5-turbo","unexpected":Infinity,'
        '"choices":[{"message":{"content":"OK"}}]}'
    )
    result = module.validate_success(invalid_outer, "general_minimal_text")
    assert result["outer_json_valid"] is False
    assert result["contract_pass"] is False


def test_redirect_handler_rejects_redirects() -> None:
    handler = module.NoRedirectHandler()
    request = urllib.request.Request("https://example.invalid")
    redirected = handler.redirect_request(
        request,
        None,
        302,
        "Found",
        {},
        "https://other.invalid",
    )
    assert redirected is None


def test_timeout_is_recorded_without_aborting(monkeypatch) -> None:
    class TimeoutOpener:
        def open(self, request, timeout):
            raise TimeoutError("bounded timeout")

    monkeypatch.setattr(module, "OPENER", TimeoutOpener())
    result = module.execute_one("not-a-real-key", module.request_matrix()[0])
    assert result["stage"] == "timeout_error"
    assert result["http_status"] is None
    assert result["network_error_type"] == "TimeoutError"
    assert result["contract_pass"] is False
    assert "not-a-real-key" not in json.dumps(result)


def test_open_protocol_failure_is_recorded_without_aborting(monkeypatch) -> None:
    class ProtocolFailureOpener:
        def __init__(self, error):
            self.error = error

        def open(self, request, timeout):
            raise self.error

    for error in (
        http.client.RemoteDisconnected("remote closed before headers"),
        http.client.BadStatusLine("malformed status"),
    ):
        monkeypatch.setattr(module, "OPENER", ProtocolFailureOpener(error))
        result = module.execute_one("not-a-real-key", module.request_matrix()[0])
        assert result["stage"] == "open_transport_error"
        assert result["http_status"] is None
        assert result["network_error_type"] == type(error).__name__
        assert result["contract_pass"] is False
        assert "not-a-real-key" not in json.dumps(result)


def test_truncated_success_body_is_recorded_without_aborting(monkeypatch) -> None:
    class TruncatedResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def settimeout(self, timeout):
            return None

        def read1(self, size):
            raise http.client.IncompleteRead(b"partial", 100)

    class TruncatedOpener:
        def open(self, request, timeout):
            return TruncatedResponse()

    monkeypatch.setattr(module, "OPENER", TruncatedOpener())
    result = module.execute_one("not-a-real-key", module.request_matrix()[0])
    assert result["stage"] == "response_body_read_error"
    assert result["http_status"] == 200
    assert result["response_read_error_type"] == "IncompleteRead"
    assert result["contract_pass"] is False
    assert "partial" not in json.dumps(result)
    assert "not-a-real-key" not in json.dumps(result)


def test_http_error_body_timeout_is_recorded_without_aborting(monkeypatch) -> None:
    class TimeoutBody:
        def settimeout(self, timeout):
            return None

        def read1(self, size):
            raise TimeoutError("bounded error-body timeout")

        def close(self):
            return None

    class HTTPErrorOpener:
        def open(self, request, timeout):
            raise urllib.error.HTTPError(
                request.full_url,
                503,
                "Service Unavailable",
                None,
                TimeoutBody(),
            )

    monkeypatch.setattr(module, "OPENER", HTTPErrorOpener())
    result = module.execute_one("not-a-real-key", module.request_matrix()[0])
    assert result["stage"] == "http_error_body_read_error"
    assert result["http_status"] == 503
    assert result["response_read_error_type"] == "TimeoutError"
    assert result["contract_pass"] is False
    assert "not-a-real-key" not in json.dumps(result)


def test_response_body_read_enforces_total_deadline(monkeypatch) -> None:
    class FakeClock:
        value = 0.0

        def __call__(self):
            return self.value

    clock = FakeClock()

    class DripResponse:
        def __init__(self):
            self.read_calls = 0
            self.timeouts = []

        def settimeout(self, timeout):
            self.timeouts.append(timeout)

        def read1(self, size):
            self.read_calls += 1
            clock.value += 0.6
            return b"x"

    response = DripResponse()
    monkeypatch.setattr(module.time, "perf_counter", clock)
    raw, error_type = module.read_response_body(response, timeout_seconds=1.0)
    assert raw is None
    assert error_type == "ReadDeadlineExceeded"
    assert response.read_calls == 2
    assert len(response.timeouts) == 2
    assert response.timeouts[0] == 1.0
    assert 0.39 < response.timeouts[1] < 0.41


def test_qualification_requires_http_200() -> None:
    assert module.qualification_pass([{"http_status": 200, "contract_pass": True}]) is True
    assert module.qualification_pass([{"http_status": 201, "contract_pass": True}]) is False
    assert module.qualification_pass([{"http_status": 200, "contract_pass": False}]) is False


def test_closeout_marks_historical_redirect_limit() -> None:
    closeout = json.loads(CLOSEOUT.read_text())
    assert closeout["status"] == "completed_response_level_pass_redirect_unverified"
    assert closeout["result"]["qualification_pass"] is True
    interpretation = closeout["interpretation"]
    assert interpretation["redirect_history_verified"] is False
    assert interpretation["one_physical_request_per_probe_verified"] is False
    assert interpretation["transport_qualified_for_future_prospective_design"] is False
    assert interpretation["fresh_engineering_requalification_required"] is True


def test_execution_marker_preserves_exact_authorization() -> None:
    assert MARKER.read_text() == (
        "candidate_sha=2d3f46ad381fbe9d5da069239f0ab3e7ef2d678f\n"
        "issue=202\n"
        "authorization=D2_general_api_preflight_execution_explicitly_authorized\n"
    )
