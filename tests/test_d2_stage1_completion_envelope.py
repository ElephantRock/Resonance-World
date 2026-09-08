from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "qualify_d2_stage1_completion_envelope.py"
SPEC = importlib.util.spec_from_file_location("qualify_d2_stage1_completion_envelope", SCRIPT_PATH)
assert SPEC and SPEC.loader
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


def test_request_plan_is_exact_and_provider_execution_is_disabled() -> None:
    plan = mod.load_plan()
    mod.validate_plan(plan)
    assert plan["issue"] == 231
    assert plan["profile_logical_calls"] == 12
    assert plan["trajectory_stage_registered"] is False
    assert plan["maximum_physical_sends_per_logical_call"] == 54
    assert plan["maximum_physical_sends_total"] == 120
    assert plan["provider_execution_authorized"] is False
    assert plan["same_request_stream_rerun_allowed"] is False
    assert plan["independent_request_origin_header"] == mod.PROBE_ORIGIN_HEADER


def test_topology_materialization_matches_committed_file() -> None:
    assert json.loads(mod.TOPOLOGY.read_text()) == mod.materialize_topology()
    topology = mod.materialize_topology()
    assert topology["profile_logical_calls"] == 12
    assert topology["trajectory_stage_registered"] is False
    assert len(topology["profile_call_shapes"]) == 4


def test_preflight_is_deterministic_and_credential_free(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("ZAI_API_KEY", raising=False)
    monkeypatch.delenv(mod.AUTH_ENV, raising=False)
    monkeypatch.setattr(mod, "MARKER", tmp_path / "absent-marker")
    first = mod.preflight()
    second = mod.preflight()
    assert first == second
    assert first["provider_execution_performed"] is False
    assert first["execution_marker_absent"] is True
    assert first["provider_send_guard_git_blob_sha"] == mod.GUARD_GIT_BLOB_SHA


def test_preflight_fails_closed_on_marker_presence(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    marker = tmp_path / "marker"
    marker.write_text("candidate_sha=" + "0" * 40 + "\n")
    monkeypatch.setattr(mod, "MARKER", marker)
    with pytest.raises(AssertionError, match="marker must be absent"):
        mod.preflight()


def test_parse_response_accepts_exact_actions_and_bounded_strategy() -> None:
    text = json.dumps(
        {
            "actions": ["KAPPA", "MICA", "ORBIT", "VELA"] * 2,
            "strategy": "S" * 1500,
        }
    )
    assert mod.parse_response(text) == "S" * 1200


@pytest.mark.parametrize(
    "payload",
    [
        [],
        {"actions": ["KAPPA"] * 7},
        {"actions": ["KAPPA"] * 7 + ["BAD"]},
        {"actions": ["KAPPA"] * 8, "strategy": 3},
    ],
)
def test_parse_response_rejects_invalid_contract(payload: object) -> None:
    with pytest.raises(ValueError):
        mod.parse_response(json.dumps(payload))


def test_execution_requires_process_authorization(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(mod.AUTH_ENV, raising=False)
    monkeypatch.delenv("ZAI_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="not authorized"):
        mod.execute()


def _budget() -> mod.ProviderSendBudget:
    return mod.ProviderSendBudget(
        allowed_url_prefix=mod.BASE_URL,
        maximum_logical_calls=mod.MAX_LOGICAL_CALLS,
        maximum_sends_per_logical_call=mod.MAX_SENDS_PER_LOGICAL,
        maximum_sends_total=mod.MAX_SENDS_TOTAL,
    )


def test_independent_origin_matches_registered_logical_context() -> None:
    budget = _budget()
    ledger = mod.TransportLedger()
    request = SimpleNamespace(headers={mod.PROBE_ORIGIN_HEADER: "7"})
    with budget.logical_call(7):
        assert mod._verified_origin_logical_index(request, budget, ledger) == 7
    assert ledger.attribution_mismatches == 0


def test_cross_attribution_is_blocked_before_send_reservation() -> None:
    budget = _budget()
    ledger = mod.TransportLedger()
    request = SimpleNamespace(headers={mod.PROBE_ORIGIN_HEADER: "8"})
    with budget.logical_call(7):
        with pytest.raises(mod.LogicalAttributionMismatch, match="does not match"):
            mod._verified_origin_logical_index(request, budget, ledger)
    assert ledger.attribution_mismatches == 1
    assert budget.total_sends == 0


def test_missing_independent_origin_is_blocked() -> None:
    budget = _budget()
    ledger = mod.TransportLedger()
    request = SimpleNamespace(headers={})
    with budget.logical_call(0):
        with pytest.raises(mod.LogicalAttributionMismatch):
            mod._verified_origin_logical_index(request, budget, ledger)
    assert ledger.attribution_mismatches == 1
    assert budget.total_sends == 0


def test_ledger_preserves_independent_origin_and_reservation_separately() -> None:
    budget = _budget()
    ledger = mod.TransportLedger()
    with budget.logical_call(3):
        reservation = budget.reserve(mod.BASE_URL + "/chat/completions")
    row_index = ledger.begin(reservation, 3)
    assert row_index == 0
    row = ledger.rows(3)[0]
    assert row["origin_logical_index"] == 3
    assert row["logical_index"] == 3


def test_profile_pass_requires_four_clean_successes() -> None:
    profile = dict(mod.PROFILES[0])
    clean = {
        "status": "success",
        "agent_api_calls_observed": 1,
        "logical_attribution_integrity": True,
        "unexpected_outbound_blocks": 0,
        "provider_budget_blocks": 0,
        "attribution_mismatch_blocks": 0,
        "terminal_http_429_code_1113": False,
    }
    assert mod.profile_pass(profile, [dict(clean) for _ in range(4)])
    bad = [dict(clean) for _ in range(4)]
    bad[2]["attribution_mismatch_blocks"] = 1
    assert not mod.profile_pass(profile, bad)


def test_bounded_error_does_not_persist_raw_error_text() -> None:
    result = mod.bounded_error(RuntimeError("HTTP 429 provider_code=1113 secret body text"))
    assert result["http_status"] == 429
    assert result["provider_code"] == 1113
    assert result["terminal_http_429_code_1113"] is True
    assert "secret body text" not in json.dumps(result)
