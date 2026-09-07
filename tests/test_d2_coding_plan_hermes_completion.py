from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "qualify_d2_coding_plan_hermes_completion.py"
SPEC = importlib.util.spec_from_file_location("d2_coding_plan_hermes_completion", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


def test_frozen_completion_request_plan_contract() -> None:
    plan = mod.load_plan()
    mod.validate_plan(plan)
    assert plan["issue"] == 219
    assert plan["predecessor_issue"] == 213
    assert plan["predecessor_pr"] == 218
    assert plan["predecessor_merge_sha"] == "105b5386e5f1027a18e2f68361a186bd8c93de9b"
    assert plan["endpoint_base_url"] == "https://api.z.ai/api/coding/paas/v4"
    assert plan["requested_model"] == "glm-5.3"
    assert plan["max_agent_iterations_per_probe"] == 2
    assert plan["max_tokens_per_model_call"] == 512
    assert plan["max_model_calls_per_probe"] == 2
    assert plan["provider_execution_authorized"] is False
    assert plan["scientific_campaign_authorized"] is False
    assert plan["historical_substrate_enabled"] is False


def test_registered_completion_provider_attempt_bound() -> None:
    assert mod.LOGICAL_PROBES == 3
    assert mod.MAX_AGENT_ITERATIONS == 2
    assert mod.MAX_TOKENS == 512
    assert mod.MAX_MODEL_CALLS_PER_PROBE == 2
    assert mod.MAX_HTTP_ATTEMPTS_PER_MODEL_CALL == 18
    assert mod.MAX_HTTP_ATTEMPTS_PER_PROBE == 36
    assert mod.MAX_PROVIDER_HTTP_ATTEMPTS == 108


def test_physical_attempt_budget_blocks_thirty_seventh_send() -> None:
    budget = mod._PhysicalAttemptBudget(probe_count=3, max_per_probe=36, max_total=108)
    budget.begin_probe(0)
    for _ in range(36):
        budget.reserve(mod.BASE_URL + "/chat/completions")
    assert budget.counts[0] == 36
    assert budget.total == 36
    with pytest.raises(mod.ProviderAttemptBudgetExceeded):
        budget.reserve(mod.BASE_URL + "/chat/completions")
    assert budget.counts[0] == 36
    assert budget.total == 36
    assert budget.blocked_budget_counts[0] == 1


def test_physical_attempt_budget_blocks_unregistered_outbound() -> None:
    budget = mod._PhysicalAttemptBudget(probe_count=3, max_per_probe=36, max_total=108)
    budget.begin_probe(1)
    with pytest.raises(mod.UnexpectedOutboundRequest):
        budget.reserve("https://api.z.ai/api/paas/v4/chat/completions")
    assert budget.counts[1] == 0
    assert budget.total == 0
    assert budget.blocked_unexpected_counts[1] == 1


def test_httpx_guard_wraps_and_restores_physical_send_boundary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeClient:
        def _send_single_request(self, request: object) -> str:
            return "sync-ok"

    class FakeAsyncClient:
        async def _send_single_request(self, request: object) -> str:
            return "async-ok"

    fake_httpx = SimpleNamespace(Client=FakeClient, AsyncClient=FakeAsyncClient)
    monkeypatch.setitem(sys.modules, "httpx", fake_httpx)
    budget = mod._PhysicalAttemptBudget(probe_count=3, max_per_probe=36, max_total=108)
    budget.begin_probe(0)
    request = SimpleNamespace(url=mod.BASE_URL + "/chat/completions")

    original_sync = FakeClient._send_single_request
    original_async = FakeAsyncClient._send_single_request
    with mod._enforce_physical_http_attempt_cap(budget):
        assert FakeClient()._send_single_request(request) == "sync-ok"
        assert budget.counts[0] == 1
        assert FakeClient._send_single_request is not original_sync
        assert FakeAsyncClient._send_single_request is not original_async

    assert FakeClient._send_single_request is original_sync
    assert FakeAsyncClient._send_single_request is original_async
    assert FakeClient()._send_single_request(request) == "sync-ok"
    assert budget.counts[0] == 1


def test_completion_sentinel_prompt_is_non_scientific_and_deterministic() -> None:
    prompt = mod.PROMPT_PATH.read_text()
    assert "RW_CODING_PLAN_COMPLETION_OK" in prompt
    assert "engineering connectivity probe" in prompt
    assert "not a scientific task" in prompt
    assert "Do not call tools" in prompt


def test_construction_candidate_has_no_completion_execution_marker() -> None:
    if mod.MARKER_PATH.exists():
        marker = mod.MARKER_PATH.read_text()
        assert "issue=219" in marker
        assert (
            "authorization=D2_vNext_Hermes_Coding_Plan_completion_execution_explicitly_authorized"
            in marker
        )
    else:
        assert not mod.MARKER_PATH.exists()


def test_preflight_is_zero_provider_when_marker_absent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if mod.MARKER_PATH.exists():
        pytest.skip("authorized/post-execution lifecycle")
    monkeypatch.delenv("ZAI_API_KEY", raising=False)
    monkeypatch.delenv("D2_CODING_PLAN_HERMES_COMPLETION_AUTHORIZED", raising=False)
    result = mod.preflight()
    assert result["provider_execution_performed"] is False
    assert result["execution_marker_absent"] is True
    assert result["max_agent_iterations_per_probe"] == 2
    assert result["max_tokens_per_model_call"] == 512
    assert result["provider_http_attempt_count_maximum"] == 108
    assert result["physical_http_attempt_cap_enforced"] is True


def test_rows_qualify_accepts_one_or_two_model_calls() -> None:
    def row(api_calls: int) -> dict[str, object]:
        return {
            "status": "success",
            "completed": True,
            "final_response_nonempty": True,
            "agent_api_calls_observed": api_calls,
            "terminal_http_429_code_1113": False,
            "provider_attempts_blocked_by_cap": 0,
            "unexpected_outbound_http_requests_blocked": 0,
            "provider_http_attempts_observed": api_calls,
        }

    assert mod._rows_qualify([row(1), row(2), row(1)]) is True


def test_rows_qualify_rejects_third_model_call() -> None:
    rows = [
        {
            "status": "success",
            "completed": True,
            "final_response_nonempty": True,
            "agent_api_calls_observed": 1,
            "terminal_http_429_code_1113": False,
            "provider_attempts_blocked_by_cap": 0,
            "unexpected_outbound_http_requests_blocked": 0,
            "provider_http_attempts_observed": 1,
        }
        for _ in range(3)
    ]
    rows[1]["agent_api_calls_observed"] = 3
    assert mod._rows_qualify(rows) is False


def test_bounded_error_never_persists_raw_text() -> None:
    exc = RuntimeError(
        'Error code: 429 - {"error":{"code":"1113","message":"secret detail"}}'
    )
    row = mod._bounded_error(exc)
    assert row["http_status"] == 429
    assert row["provider_code"] == 1113
    assert row["terminal_http_429_code_1113"] is True
    assert "secret detail" not in repr(row)


def test_execute_requires_explicit_completion_process_authorization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("D2_CODING_PLAN_HERMES_COMPLETION_AUTHORIZED", raising=False)
    monkeypatch.delenv("ZAI_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="completion provider execution is not authorized"):
        mod.execute()
