from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from resonance_world import d2_terminal_observability as contract
from resonance_world import d2_terminal_transport as transport
from resonance_world.provider_send_guard import ProviderSendBudget

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "qualify_d2_terminal_response_observability.py"
PROBES_PATH = ROOT / "research" / "d2_terminal_response_observability" / "PROBES.json"


def load_script():
    spec = importlib.util.spec_from_file_location("d2_terminal_observability_script", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_frozen_probe_manifest_is_balanced_and_fresh() -> None:
    probes = contract.validate_probes(json.loads(PROBES_PATH.read_text()))
    assert len(probes) == 72
    assert sum(probe["development_budget"] == 40 for probe in probes) == 24
    assert sum(probe["development_budget"] == 80 for probe in probes) == 24
    assert sum(probe["development_budget"] == 160 for probe in probes) == 24
    assert min(probe["seed"] for probe in probes) >= 900000
    assert len({probe["seed"] for probe in probes}) == 72


def test_prompt_materialization_is_realistic_and_deterministic() -> None:
    probes = contract.validate_probes(json.loads(PROBES_PATH.read_text()))
    first = contract.user_prompt(probes[0])
    assert first == contract.user_prompt(probes[0])
    assert 2000 <= len(first.encode()) <= 2200
    assert "never scientifically scored" in first
    assert "deterministic synthetic context" in first


def test_exact_structured_parser_accepts_bounded_contract() -> None:
    text = json.dumps(
        {
            "actions": ["KAPPA", "MICA", "ORBIT", "VELA"] * 2,
            "strategy": "fresh ASCII strategy",
        }
    )
    valid, strategy = contract.parse_response(text)
    assert valid is True
    assert strategy == "fresh ASCII strategy"


@pytest.mark.parametrize(
    "text",
    [
        "",
        "not-json",
        json.dumps({"actions": ["KAPPA"] * 7}),
        json.dumps({"actions": ["KAPPA"] * 8, "extra": 1}),
        json.dumps({"actions": ["KAPPA"] * 8, "strategy": "é"}),
        json.dumps({"actions": ["KAPPA"] * 8, "strategy": "x" * 513}),
    ],
)
def test_structured_parser_fails_closed(text: str) -> None:
    valid, strategy = contract.parse_response(text)
    assert valid is False
    assert strategy == ""


def test_valid_terminal_observation_requires_every_registered_condition() -> None:
    kwargs = {
        "api_calls": 2,
        "hermes_completed": False,
        "hermes_failed": False,
        "hermes_partial": False,
        "hermes_interrupted": False,
        "hermes_error_present": False,
        "final_nonempty": True,
        "parse_valid": True,
        "attribution_integrity": True,
        "unexpected_outbound_blocks": 0,
        "provider_budget_blocks": 0,
        "attribution_mismatch_blocks": 0,
    }
    assert contract.is_valid_terminal_observation(**kwargs) is True
    for key in (
        "hermes_failed",
        "hermes_partial",
        "hermes_interrupted",
        "hermes_error_present",
    ):
        changed = dict(kwargs)
        changed[key] = True
        assert contract.is_valid_terminal_observation(**changed) is False
    changed = dict(kwargs)
    changed["api_calls"] = 1
    assert contract.is_valid_terminal_observation(**changed) is False
    changed = dict(kwargs)
    changed["hermes_completed"] = True
    assert contract.is_valid_terminal_observation(**changed) is False
    changed = dict(kwargs)
    changed["parse_valid"] = False
    assert contract.is_valid_terminal_observation(**changed) is False


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


def test_terminal_two_call_transport_requires_exact_two_clean_http_200_sends() -> None:
    script = load_script()
    clean = [
        {"http_status": 200, "transport_error_type": None},
        {"http_status": 200, "transport_error_type": None},
    ]
    assert script.exact_two_clean_provider_sends(clean, 2) is True

    extra_grace_or_summary = clean + [
        {"http_status": 200, "transport_error_type": None}
    ]
    assert script.exact_two_clean_provider_sends(extra_grace_or_summary, 3) is False

    retry_or_error = [
        {"http_status": 500, "transport_error_type": None},
        {"http_status": 200, "transport_error_type": None},
    ]
    assert script.exact_two_clean_provider_sends(retry_or_error, 2) is False

    transport_error = [
        {"http_status": None, "transport_error_type": "ConnectError"},
        {"http_status": 200, "transport_error_type": None},
    ]
    assert script.exact_two_clean_provider_sends(transport_error, 2) is False


def test_handled_hermes_failure_or_terminal_transport_ambiguity_is_apparatus_failure() -> None:
    script = load_script()
    clean_terminal_negative = {
        "runtime_exception": False,
        "hermes_completed": False,
        "hermes_failed": False,
        "hermes_partial": False,
        "hermes_interrupted": False,
        "hermes_error_present": False,
        "api_calls": 2,
        "terminal_two_call_transport_unambiguous": True,
        "final_response_length": 0,
        "structured_parse_valid": False,
    }
    assert script.probe_has_apparatus_failure(clean_terminal_negative) is False
    for key in (
        "runtime_exception",
        "hermes_failed",
        "hermes_partial",
        "hermes_interrupted",
        "hermes_error_present",
    ):
        handled_failure = dict(clean_terminal_negative)
        handled_failure[key] = True
        assert script.probe_has_apparatus_failure(handled_failure) is True

    ambiguous_transport = dict(clean_terminal_negative)
    ambiguous_transport["terminal_two_call_transport_unambiguous"] = False
    assert script.probe_has_apparatus_failure(ambiguous_transport) is True

    one_call_negative = dict(clean_terminal_negative)
    one_call_negative["api_calls"] = 1
    one_call_negative["terminal_two_call_transport_unambiguous"] = False
    assert script.probe_has_apparatus_failure(one_call_negative) is False


def test_preflight_is_deterministic_and_credential_free(monkeypatch: pytest.MonkeyPatch) -> None:
    script = load_script()
    monkeypatch.setattr(script, "MARKER", ROOT / "does-not-exist-terminal-observability-marker")
    monkeypatch.delenv("ZAI_API_KEY", raising=False)
    monkeypatch.delenv(script.AUTH_ENV, raising=False)
    first = script.preflight()
    second = script.preflight()
    assert first == second
    assert first["provider_execution_performed"] is False
    assert first["probe_count"] == 72


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
