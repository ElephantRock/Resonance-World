from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "qualify_terminal_iteration_completion.py"
SPEC = importlib.util.spec_from_file_location("qualify_terminal_iteration_completion", SCRIPT)
assert SPEC and SPEC.loader
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


def test_preflight_is_deterministic_and_provider_free(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("ZAI_API_KEY", raising=False)
    monkeypatch.delenv(mod.AUTH_ENV, raising=False)
    monkeypatch.setattr(mod, "MARKER", tmp_path / "absent-marker")
    first = mod.preflight()
    second = mod.preflight()
    assert first == second
    assert first["provider_execution_performed"] is False
    assert first["execution_marker_absent"] is True
    assert first["issue"] == 237


def test_preflight_rejects_marker_presence(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    marker = tmp_path / "marker"
    marker.write_text("candidate_sha=" + "0" * 40 + "\n")
    monkeypatch.setattr(mod, "MARKER", marker)
    with pytest.raises(AssertionError, match="marker must be absent"):
        mod.preflight()


def test_frozen_probe_contract_is_exact() -> None:
    probes = mod.load_probes()
    assert len(probes) == 4
    assert [probe["probe_id"] for probe in probes] == [
        "terminal_semantics_0",
        "terminal_semantics_1",
        "terminal_semantics_2",
        "terminal_semantics_3",
    ]
    assert all(len(probe["actions"]) == 8 for probe in probes)
    assert all(len(probe["strategy"]) == 128 for probe in probes)


def test_probe_parser_requires_exact_registered_object() -> None:
    probe = mod.load_probes()[0]
    exact = mod.json.dumps(
        {"actions": probe["actions"], "strategy": probe["strategy"]},
        separators=(",", ":"),
    )
    assert mod.parse_probe_response(exact, probe) is True
    assert mod.parse_probe_response('{"actions":[],"strategy":""}', probe) is False
    assert mod.parse_probe_response(exact + " trailing", probe) is False


def test_origin_mismatch_is_blocked_before_send_reservation() -> None:
    budget = mod.ProviderSendBudget(
        allowed_url_prefix=mod.BASE_URL,
        maximum_logical_calls=mod.MAX_LOGICAL,
        maximum_sends_per_logical_call=mod.MAX_SENDS_PER_LOGICAL,
        maximum_sends_total=mod.MAX_SENDS_TOTAL,
    )
    ledger = mod.TransportLedger()
    request = SimpleNamespace(headers={mod.ORIGIN_HEADER: "2"})
    with budget.logical_call(1):
        with pytest.raises(mod.LogicalAttributionMismatch):
            mod.verified_origin(request, budget, ledger)
    assert ledger.mismatches == 1
    assert budget.total_sends == 0


def test_execution_requires_authorization_before_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(mod.AUTH_ENV, raising=False)
    monkeypatch.delenv("ZAI_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="not authorized"):
        mod.execute()
