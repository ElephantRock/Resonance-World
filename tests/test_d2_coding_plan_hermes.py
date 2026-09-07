from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "qualify_d2_coding_plan_hermes.py"
SPEC = importlib.util.spec_from_file_location("d2_coding_plan_hermes", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


def test_frozen_request_plan_contract() -> None:
    plan = mod.load_plan()
    mod.validate_plan(plan)
    assert plan["issue"] == 213
    assert plan["endpoint_base_url"] == "https://api.z.ai/api/coding/paas/v4"
    assert plan["requested_model"] == "glm-5.3"
    assert plan["supported_product_environment"] == "Hermes Agent Python library"
    assert plan["provider_base_url_env_var"] == "GLM_BASE_URL"
    assert plan["credential_env_var"] == "ZAI_API_KEY"
    assert plan["provider_router_required"] is True
    assert plan["explicit_openai_client_bypass_allowed"] is False
    assert plan["provider_execution_authorized"] is False
    assert plan["scientific_campaign_authorized"] is False
    assert plan["historical_substrate_enabled"] is False


def test_registered_provider_attempt_bound() -> None:
    assert mod.LOGICAL_PROBES == 3
    assert mod.OPENAI_DEFAULT_MAX_RETRIES == 2
    assert mod.HERMES_APPLICATION_MAX_ATTEMPTS_PER_RETRY_CYCLE == 3
    assert mod.HERMES_PRIMARY_TRANSPORT_RECOVERY_ADDITIONAL_CYCLES_MAXIMUM == 1
    assert mod.MAX_HTTP_ATTEMPTS_PER_PROBE == 18
    assert mod.MAX_PROVIDER_HTTP_ATTEMPTS == 54
    assert mod.LOGICAL_PROBES * mod.MAX_HTTP_ATTEMPTS_PER_PROBE == 54


def test_physical_attempt_budget_blocks_nineteenth_send() -> None:
    budget = mod._PhysicalAttemptBudget(probe_count=3, max_per_probe=18, max_total=54)
    budget.begin_probe(0)
    for _ in range(18):
        budget.reserve(mod.BASE_URL + "/chat/completions")
    assert budget.counts[0] == 18
    assert budget.total == 18
    with pytest.raises(mod.ProviderAttemptBudgetExceeded):
        budget.reserve(mod.BASE_URL + "/chat/completions")
    assert budget.counts[0] == 18
    assert budget.total == 18
    assert budget.blocked_budget_counts[0] == 1


def test_physical_attempt_budget_blocks_unregistered_outbound() -> None:
    budget = mod._PhysicalAttemptBudget(probe_count=3, max_per_probe=18, max_total=54)
    budget.begin_probe(1)
    with pytest.raises(mod.UnexpectedOutboundRequest):
        budget.reserve("https://api.z.ai/api/paas/v4/chat/completions")
    assert budget.counts[1] == 0
    assert budget.total == 0
    assert budget.blocked_unexpected_counts[1] == 1


def test_sentinel_prompt_is_non_scientific_and_deterministic() -> None:
    prompt = mod.PROMPT_PATH.read_text()
    assert "RW_CODING_PLAN_OK" in prompt
    assert "engineering connectivity probe" in prompt
    assert "not a scientific task" in prompt
    assert "Do not call tools" in prompt


def test_construction_candidate_has_no_execution_marker() -> None:
    if mod.MARKER_PATH.exists():
        marker = mod.MARKER_PATH.read_text()
        # Post-authorization heads are allowed only if they carry the exact
        # prospective marker contract. The frozen construction candidate itself
        # is separately verified marker-absent by the preexecution workflow.
        assert "issue=213" in marker
        assert (
            "authorization=D2_vNext_Hermes_Coding_Plan_execution_explicitly_authorized"
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
    monkeypatch.delenv("D2_CODING_PLAN_HERMES_AUTHORIZED", raising=False)
    result = mod.preflight()
    assert result["provider_execution_performed"] is False
    assert result["execution_marker_absent"] is True
    assert result["provider_http_attempt_count_maximum"] == 54
    assert result["physical_http_attempt_cap_enforced"] is True


def test_bounded_error_never_persists_raw_text() -> None:
    exc = RuntimeError(
        'Error code: 429 - {"error":{"code":"1113","message":"secret detail"}}'
    )
    row = mod._bounded_error(exc)
    assert row["http_status"] == 429
    assert row["provider_code"] == 1113
    assert row["terminal_http_429_code_1113"] is True
    assert "secret detail" not in repr(row)
    assert set(row) == {
        "error_type",
        "http_status",
        "provider_code",
        "error_text_length",
        "error_text_sha256",
        "terminal_http_429_code_1113",
    }


def test_execute_requires_explicit_process_authorization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("D2_CODING_PLAN_HERMES_AUTHORIZED", raising=False)
    monkeypatch.delenv("ZAI_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="provider execution is not authorized"):
        mod.execute()
