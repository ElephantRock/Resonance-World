from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from resonance_world import d2_terminal_adapter as adapter
from resonance_world import d2_terminal_transport as transport
from resonance_world.provider_send_guard import ProviderSendBudget

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "qualify_d2_terminal_adapter.py"
PROBES_PATH = ROOT / "research" / "d2_terminal_adapter" / "PROBES.json"
EVIDENCE_243 = (
    ROOT / "research" / "evidence" / "d2_terminal_response_observability" / "RESULT.json"
)


def load_script():
    spec = importlib.util.spec_from_file_location("d2_terminal_adapter_script", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def clean_attempt(logical: int, send_index: int) -> dict[str, object]:
    return {
        "origin_logical_index": logical,
        "logical_index": logical,
        "logical_send_index": send_index,
        "total_send_index": send_index,
        "http_status": 200,
        "transport_error_type": None,
    }


def result(*, completed: bool, api_calls: int) -> dict[str, object]:
    return {
        "completed": completed,
        "failed": False,
        "partial": False,
        "interrupted": False,
        "error": None,
        "api_calls": api_calls,
        "final_response": (
            '{"actions":["KAPPA","MICA","ORBIT","VELA",'
            '"KAPPA","MICA","ORBIT","VELA"]}'
        ),
    }


def evaluate(
    payload: dict[str, object],
    *,
    attempts: list[dict[str, object]],
    sends: int,
    parse_valid: bool = True,
):
    return adapter.evaluate_terminal_completion(
        payload,
        max_iterations=2,
        parse_valid=parse_valid,
        logical_attribution_integrity=True,
        attempts=attempts,
        physical_sends=sends,
        unexpected_outbound_blocks=0,
        provider_budget_blocks=0,
        attribution_mismatch_blocks=0,
    )


def test_native_completion_is_preserved_without_override() -> None:
    decision = evaluate(
        result(completed=True, api_calls=1),
        attempts=[clean_attempt(0, 1)],
        sends=1,
    )
    assert decision.effective_completed is True
    assert decision.hermes_completed is True
    assert decision.terminal_iteration_override_used is False
    assert decision.reason == "hermes_completed"


def test_terminal_second_call_is_effective_only_via_explicit_override() -> None:
    decision = evaluate(
        result(completed=False, api_calls=2),
        attempts=[clean_attempt(0, 1), clean_attempt(0, 2)],
        sends=2,
    )
    assert decision.effective_completed is True
    assert decision.hermes_completed is False
    assert decision.terminal_iteration_override_used is True
    assert decision.reason == "valid_terminal_iteration_response"


def test_terminal_override_rejects_retry_or_grace_send() -> None:
    attempts = [clean_attempt(0, 1), clean_attempt(0, 2), clean_attempt(0, 3)]
    decision = evaluate(result(completed=False, api_calls=2), attempts=attempts, sends=3)
    assert decision.effective_completed is False
    assert decision.terminal_iteration_override_used is False
    assert decision.reason == "transport_not_exact_clean"


def test_terminal_override_rejects_non_200_or_transport_error() -> None:
    non_200 = [clean_attempt(0, 1), clean_attempt(0, 2)]
    non_200[0]["http_status"] = 500
    assert (
        evaluate(result(completed=False, api_calls=2), attempts=non_200, sends=2).reason
        == "transport_not_exact_clean"
    )

    transport_error = [clean_attempt(0, 1), clean_attempt(0, 2)]
    transport_error[1]["transport_error_type"] = "ConnectError"
    assert (
        evaluate(
            result(completed=False, api_calls=2),
            attempts=transport_error,
            sends=2,
        ).reason
        == "transport_not_exact_clean"
    )


def test_adapter_fails_closed_on_parse_failure_and_hermes_failure() -> None:
    attempts = [clean_attempt(0, 1), clean_attempt(0, 2)]
    assert (
        evaluate(
            result(completed=False, api_calls=2),
            attempts=attempts,
            sends=2,
            parse_valid=False,
        ).reason
        == "structured_parse_invalid"
    )
    failed = result(completed=False, api_calls=2)
    failed["failed"] = True
    assert evaluate(failed, attempts=attempts, sends=2).reason == "hermes_failed"


def test_fresh_probe_manifest_balanced_and_disjoint_from_243() -> None:
    probes = adapter.validate_probes(json.loads(PROBES_PATH.read_text()))
    assert len(probes) == 72
    assert sum(probe["development_budget"] == 40 for probe in probes) == 24
    assert sum(probe["development_budget"] == 80 for probe in probes) == 24
    assert sum(probe["development_budget"] == 160 for probe in probes) == 24

    prior = json.loads(EVIDENCE_243.read_text())["probes"]
    assert {probe["seed"] for probe in probes}.isdisjoint(
        {row["seed"] for row in prior}
    )
    assert {probe["probe_id"] for probe in probes}.isdisjoint(
        {row["probe_id"] for row in prior}
    )


def test_fresh_prompt_is_realistic_and_deterministic() -> None:
    probes = adapter.validate_probes(json.loads(PROBES_PATH.read_text()))
    first = adapter.user_prompt(probes[0])
    assert first == adapter.user_prompt(probes[0])
    assert 2100 <= len(first.encode()) <= 2200
    assert "never scientifically scored" in first
    assert "nonscientific-adapter-context" in first


def test_strict_parser_accepts_only_bounded_contract() -> None:
    valid = json.dumps(
        {
            "actions": ["KAPPA", "MICA", "ORBIT", "VELA"] * 2,
            "strategy": "fresh ASCII strategy",
        }
    )
    assert adapter.parse_response(valid) == (True, "fresh ASCII strategy")
    assert adapter.parse_response("") == (False, "")
    assert adapter.parse_response("not-json") == (False, "")
    assert adapter.parse_response(json.dumps({"actions": ["KAPPA"] * 7})) == (
        False,
        "",
    )


def test_transport_origin_must_match_registered_context() -> None:
    budget = ProviderSendBudget(
        allowed_url_prefix="https://api.z.ai/api/coding/paas/v4",
        maximum_logical_calls=72,
        maximum_sends_per_logical_call=36,
        maximum_sends_total=180,
    )
    ledger = transport.TransportLedger()
    request = SimpleNamespace(headers={transport.ORIGIN_HEADER: "3"})
    with budget.logical_call(3):
        assert transport.verified_origin_logical_index(request, budget, ledger) == 3
    with budget.logical_call(4):
        with pytest.raises(transport.LogicalAttributionMismatch):
            transport.verified_origin_logical_index(request, budget, ledger)
    assert ledger.attribution_mismatches == 1


def test_preserved_243_evidence_regresses_to_64_native_and_8_override() -> None:
    script = load_script()
    assert script.preserved_evidence_regression() == {
        "effective_completed": 72,
        "native_completed": 64,
        "terminal_overrides": 8,
    }


def test_handled_failure_and_transport_ambiguity_are_apparatus_failures() -> None:
    script = load_script()
    clean = {
        "runtime_exception": False,
        "hermes_completed_flag_valid": True,
        "hermes_failed": False,
        "hermes_partial": False,
        "hermes_interrupted": False,
        "hermes_error_present": False,
        "adapter_reason": "hermes_completed",
    }
    assert script.probe_has_apparatus_failure(clean) is False
    for key in (
        "runtime_exception",
        "hermes_failed",
        "hermes_partial",
        "hermes_interrupted",
        "hermes_error_present",
    ):
        failed = dict(clean)
        failed[key] = True
        assert script.probe_has_apparatus_failure(failed) is True
    invalid_completed = dict(clean)
    invalid_completed["hermes_completed_flag_valid"] = False
    assert script.probe_has_apparatus_failure(invalid_completed) is True

    ambiguous = dict(clean)
    ambiguous["adapter_reason"] = "transport_not_exact_clean"
    assert script.probe_has_apparatus_failure(ambiguous) is True


def test_preflight_is_deterministic_and_credential_free(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    script = load_script()
    monkeypatch.setattr(script, "MARKER", ROOT / "does-not-exist-terminal-adapter-marker")
    monkeypatch.delenv("ZAI_API_KEY", raising=False)
    monkeypatch.delenv(script.AUTH_ENV, raising=False)
    first = script.preflight()
    second = script.preflight()
    assert first == second
    assert first["provider_execution_performed"] is False
    assert first["preserved_evidence_regression"]["terminal_overrides"] == 8


def test_preflight_fails_if_marker_exists(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    script = load_script()
    marker = tmp_path / "marker"
    marker.write_text("present\n")
    monkeypatch.setattr(script, "MARKER", marker)
    with pytest.raises(AssertionError, match="marker"):
        script.preflight()


def test_execution_rejects_without_authorization(monkeypatch: pytest.MonkeyPatch) -> None:
    script = load_script()
    monkeypatch.delenv(script.AUTH_ENV, raising=False)
    monkeypatch.delenv("ZAI_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="authorized"):
        script.execute()
