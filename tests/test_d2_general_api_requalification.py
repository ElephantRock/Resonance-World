from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

SCRIPTS = Path("scripts").resolve()
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

SCRIPT = Path("scripts/requalify_d2_general_api.py")
PLAN = Path("research/d2_general_api_requalification/REQUALIFICATION_REQUEST_PLAN.json")
MARKER = Path("research/d2_general_api_requalification/RUN_D2_GENERAL_API_REQUALIFICATION")

spec = importlib.util.spec_from_file_location("d2_general_requalification", SCRIPT)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_request_plan_is_fresh_engineering_only_and_unauthorized() -> None:
    plan = json.loads(PLAN.read_text())
    assert plan["issue"] == 206
    assert plan["upstream_issue"] == 202
    assert plan["upstream_pr"] == 203
    assert plan["historical_preflight_closeout_status"] == (
        "completed_response_level_pass_redirect_unverified"
    )
    assert plan["historical_redirect_history_verified"] is False
    assert plan["historical_one_physical_request_per_probe_verified"] is False
    assert plan["engineering_only"] is True
    assert plan["provider_execution_authorized"] is False
    assert plan["endpoint"] == "https://api.z.ai/api/paas/v4/chat/completions"
    assert plan["model"] == "glm-5-turbo"
    assert plan["request_count"] == 3
    assert plan["max_attempts_per_request"] == 1
    assert plan["redirect_policy"] == "reject_do_not_follow"
    assert plan["physical_attempt_accounting"] == "instrumented_https_handler"
    assert plan["historical_substrate_enabled"] is False


def test_marker_is_absent_before_explicit_authorization() -> None:
    assert not MARKER.exists()


def test_materialization_is_deterministic_and_reuses_fixed_probe_contract() -> None:
    first = module.materialized_plan()
    second = module.materialized_plan()
    assert first == second
    assert first["issue"] == 206
    assert first["request_count"] == 3
    assert first["request_ids"] == list(module.base.REQUEST_IDS)
    assert first["request_body_sha256"] == module.base.materialized_plan()[
        "request_body_sha256"
    ]
    assert first["max_attempts_per_request"] == 1
    assert first["redirect_policy"] == "reject_do_not_follow"
    assert first["physical_attempt_accounting"] == "instrumented_https_handler"
    assert len(first["hardened_transport_sha256"]) == 64
    assert len(first["requalification_wrapper_sha256"]) == 64
    assert first["provider_execution_authorized"] is False
    assert first["production_historical_substrate_enabled"] is False


def _fake_execute_with_attempts(monkeypatch, attempts: int, *, status: int = 200) -> dict:
    def fake_execute_one(key, row):
        counter = next(
            handler
            for handler in module.base.OPENER.handlers
            if isinstance(handler, module.CountingHTTPSHandler)
        )
        counter.attempts += attempts
        return {
            "diagnostic_id": row["diagnostic_id"],
            "stage": "http_success" if status == 200 else "http_error",
            "http_status": status,
            "contract_pass": status == 200,
        }

    monkeypatch.setattr(module.base, "execute_one", fake_execute_one)
    return module.execute_probe("not-a-real-key", module.base.request_matrix()[0])


def test_one_initiated_https_attempt_is_verified(monkeypatch) -> None:
    result = _fake_execute_with_attempts(monkeypatch, 1)
    assert result["physical_attempts_initiated"] == 1
    assert result["one_physical_request_verified"] is True
    assert result["redirect_following_disabled"] is True
    assert result["redirects_followed"] == 0
    assert result["redirect_history_verified"] is True
    assert result["contract_pass"] is True


def test_multiple_physical_attempts_fail_transport_contract(monkeypatch) -> None:
    result = _fake_execute_with_attempts(monkeypatch, 2)
    assert result["physical_attempts_initiated"] == 2
    assert result["one_physical_request_verified"] is False
    assert result["redirect_history_verified"] is False
    assert result["contract_pass"] is False


def test_surfaced_redirect_response_is_never_qualified(monkeypatch) -> None:
    result = _fake_execute_with_attempts(monkeypatch, 1, status=302)
    assert result["redirect_response_observed"] is True
    assert result["redirects_followed"] == 0
    assert result["one_physical_request_verified"] is True
    assert result["contract_pass"] is False


def test_aggregate_qualification_requires_physical_and_redirect_verification() -> None:
    good = {
        "http_status": 200,
        "contract_pass": True,
        "one_physical_request_verified": True,
        "redirect_history_verified": True,
        "redirects_followed": 0,
    }
    assert module.qualification_pass([dict(good) for _ in range(3)]) is True

    bad_physical = [dict(good) for _ in range(3)]
    bad_physical[1]["one_physical_request_verified"] = False
    assert module.qualification_pass(bad_physical) is False

    bad_redirect = [dict(good) for _ in range(3)]
    bad_redirect[2]["redirect_history_verified"] = False
    assert module.qualification_pass(bad_redirect) is False


def test_execute_requires_explicit_authorization(monkeypatch) -> None:
    monkeypatch.delenv(module.AUTH_ENV, raising=False)
    try:
        module.execute()
    except RuntimeError as exc:
        assert "not authorized" in str(exc)
    else:
        raise AssertionError("execute() must fail closed without explicit authorization")
