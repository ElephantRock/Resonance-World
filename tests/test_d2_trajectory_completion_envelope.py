from __future__ import annotations

import importlib.util
import json
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "qualify_d2_trajectory_completion_envelope.py"
SPEC = importlib.util.spec_from_file_location(
    "qualify_d2_trajectory_completion_envelope", SCRIPT_PATH
)
assert SPEC and SPEC.loader
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)
contract = mod.contract
transport = mod.transport


def test_request_plan_is_exact_and_provider_execution_is_disabled() -> None:
    plan = contract.load_plan()
    contract.validate_plan(plan)
    assert plan["issue"] == 234
    assert plan["selected_profile"] == contract.PROFILE
    assert plan["trajectory_logical_calls_each"] == 55
    assert plan["trajectory_logical_calls_total"] == 220
    assert plan["trajectory_max_concurrency"] == 4
    assert plan["maximum_physical_sends_per_logical_call"] == 36
    assert plan["maximum_physical_sends_total"] == 400
    assert plan["provider_worker_tracking_required"] is True
    assert plan["provider_worker_target_module"] == "run_agent"
    assert plan["provider_worker_target_name"] == "_call"
    assert plan["pinned_hermes_worker_join_until_exit_required"] is True
    assert plan["provider_worker_drain_before_guard_restore"] is True
    assert plan["provider_worker_leak_fail_closed"] is True
    assert plan["provider_execution_authorized"] is False
    assert plan["same_request_stream_rerun_allowed"] is False
    assert plan["replacement_logical_call_allowed"] is False


def test_topology_materialization_matches_committed_file() -> None:
    topology = contract.materialize_topology()
    assert json.loads(contract.TOPOLOGY.read_text()) == topology
    assert topology["trajectory_logical_calls_each"] == 55
    assert topology["trajectory_logical_calls_total"] == 220
    assert len(topology["trajectories"]) == 4
    ranges = [
        (row["logical_index_start"], row["logical_index_stop_exclusive"])
        for row in topology["trajectories"]
    ]
    assert ranges == [(0, 55), (55, 110), (110, 165), (165, 220)]


def test_each_trajectory_spec_is_exactly_55_and_total_is_220() -> None:
    all_indices = []
    for index in range(4):
        specs = contract.trajectory_specs(index)
        assert len(specs) == 55
        start = index * 55
        all_indices.extend(range(start, start + len(specs)))
        assert sum(x["shape"] == "fresh_evaluation" for x in specs) == 4
        assert sum(x["shape"] == "oracle_evaluation" for x in specs) == 4
        assert sum(x["shape"] == "developed_development" for x in specs) == 35
        assert sum(x["shape"] == "developed_evaluation" for x in specs) == 12
    assert all_indices == list(range(220))


def test_preflight_is_deterministic_and_credential_free(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("ZAI_API_KEY", raising=False)
    monkeypatch.delenv(contract.AUTH_ENV, raising=False)
    monkeypatch.setattr(contract, "MARKER", tmp_path / "absent-marker")
    first = mod.preflight()
    second = mod.preflight()
    assert first == second
    assert first["provider_execution_performed"] is False
    assert first["execution_marker_absent"] is True
    assert first["provider_send_guard_git_blob_sha"] == contract.GUARD_GIT_BLOB_SHA


def test_preflight_fails_closed_on_marker_presence(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    marker = tmp_path / "marker"
    marker.write_text("candidate_sha=" + "0" * 40 + "\n")
    monkeypatch.setattr(contract, "MARKER", marker)
    with pytest.raises(AssertionError, match="marker must be absent"):
        mod.preflight()


def test_parse_response_accepts_exact_actions_and_bounded_strategy() -> None:
    text = json.dumps(
        {
            "actions": ["KAPPA", "MICA", "ORBIT", "VELA"] * 2,
            "strategy": "S" * 1500,
        }
    )
    assert contract.parse_response(text) == "S" * 1200


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
        contract.parse_response(json.dumps(payload))


def test_execution_requires_process_authorization(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(contract.AUTH_ENV, raising=False)
    monkeypatch.delenv("ZAI_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="not authorized"):
        mod.execute()


def _budget() -> mod.ProviderSendBudget:
    return mod.ProviderSendBudget(
        allowed_url_prefix=contract.BASE_URL,
        maximum_logical_calls=contract.MAX_LOGICAL_CALLS,
        maximum_sends_per_logical_call=contract.MAX_SENDS_PER_LOGICAL,
        maximum_sends_total=contract.MAX_SENDS_TOTAL,
    )


def test_independent_origin_matches_registered_logical_context() -> None:
    budget = _budget()
    ledger = transport.TransportLedger()
    request = SimpleNamespace(headers={contract.PROBE_ORIGIN_HEADER: "117"})
    with budget.logical_call(117):
        assert transport.verified_origin_logical_index(request, budget, ledger) == 117
    assert ledger.attribution_mismatches == 0


def test_cross_attribution_is_blocked_before_send_reservation() -> None:
    budget = _budget()
    ledger = transport.TransportLedger()
    request = SimpleNamespace(headers={contract.PROBE_ORIGIN_HEADER: "118"})
    with budget.logical_call(117):
        with pytest.raises(transport.LogicalAttributionMismatch, match="does not match"):
            transport.verified_origin_logical_index(request, budget, ledger)
    assert ledger.attribution_mismatches == 1
    assert budget.total_sends == 0


def test_missing_independent_origin_is_blocked() -> None:
    budget = _budget()
    ledger = transport.TransportLedger()
    request = SimpleNamespace(headers={})
    with budget.logical_call(0):
        with pytest.raises(transport.LogicalAttributionMismatch):
            transport.verified_origin_logical_index(request, budget, ledger)
    assert ledger.attribution_mismatches == 1
    assert budget.total_sends == 0


def test_ledger_preserves_independent_origin_and_reservation_separately() -> None:
    budget = _budget()
    ledger = transport.TransportLedger()
    with budget.logical_call(42):
        reservation = budget.reserve(contract.BASE_URL + "/chat/completions")
    row_index = ledger.begin(reservation, 42)
    assert row_index == 0
    row = ledger.rows(42)[0]
    assert row["origin_logical_index"] == 42
    assert row["logical_index"] == 42


def test_call_pass_requires_clean_bounded_success() -> None:
    clean = {
        "status": "success",
        "agent_api_calls_observed": 1,
        "logical_attribution_integrity": True,
        "unexpected_outbound_blocks": 0,
        "provider_budget_blocks": 0,
        "attribution_mismatch_blocks": 0,
        "terminal_http_429_code_1113": False,
    }
    assert mod.call_pass(clean)
    bad = dict(clean, provider_budget_blocks=1)
    assert not mod.call_pass(bad)
    bad = dict(clean, agent_api_calls_observed=3)
    assert not mod.call_pass(bad)


def test_only_development_strategy_is_propagated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[tuple[str, str]] = []

    def fake_run_call(
        budget: object,
        ledger: object,
        logical: int,
        call_id: str,
        shape: str,
        seed: int,
        strategy: str,
    ) -> tuple[dict[str, object], str]:
        del budget, ledger, call_id, seed
        seen.append((shape, strategy))
        row: dict[str, object] = {
            "status": "success",
            "agent_api_calls_observed": 1,
            "logical_attribution_integrity": True,
            "unexpected_outbound_blocks": 0,
            "provider_budget_blocks": 0,
            "attribution_mismatch_blocks": 0,
            "terminal_http_429_code_1113": False,
        }
        return row, f"{shape}:{logical}"

    monkeypatch.setattr(mod, "run_call", fake_run_call)
    result = mod.run_trajectory(_budget(), transport.TransportLedger(), 0)
    assert result["complete_55_of_55"] is True
    assert len(seen) == 55
    for shape, strategy in seen:
        if shape in {"fresh_evaluation", "oracle_evaluation"}:
            assert strategy == ""
        elif shape == "developed_evaluation":
            assert strategy.startswith("developed_development:")
            assert not strategy.startswith("developed_evaluation:")


def _make_run_agent_call_target(stop_event: threading.Event):
    def _call() -> None:
        stop_event.wait()

    _call.__module__ = "run_agent"
    _call.__name__ = "_call"
    return _call


def test_provider_worker_tracker_recognizes_pinned_hermes_call_worker() -> None:
    stop = threading.Event()
    thread = threading.Thread(target=_make_run_agent_call_target(stop), daemon=True)
    tracker = transport.ProviderWorkerTracker()
    assert tracker.is_provider_worker(thread) is True
    tracker.observe_before_start(thread)
    assert tracker.observed == 1


def test_provider_worker_tracker_drain_waits_for_worker_exit() -> None:
    stop = threading.Event()
    thread = threading.Thread(target=_make_run_agent_call_target(stop), daemon=True)
    tracker = transport.ProviderWorkerTracker()
    tracker.observe_before_start(thread)
    thread.start()

    def release() -> None:
        time.sleep(0.03)
        stop.set()

    releaser = threading.Thread(target=release)
    releaser.start()
    assert tracker.drain(timeout_seconds=1.0) == 0
    releaser.join(timeout=1.0)
    assert tracker.alive_after_drain == 0


def test_provider_worker_tracker_fails_closed_on_leaked_worker() -> None:
    stop = threading.Event()
    thread = threading.Thread(target=_make_run_agent_call_target(stop), daemon=True)
    tracker = transport.ProviderWorkerTracker()
    tracker.observe_before_start(thread)
    thread.start()
    try:
        assert tracker.drain(timeout_seconds=0.02) == 1
        assert tracker.alive_after_drain == 1
        assert tracker.transport_hooks_restored is False
    finally:
        stop.set()
        thread.join(timeout=1.0)


def test_bounded_error_does_not_persist_raw_error_text() -> None:
    result = contract.bounded_error(RuntimeError("HTTP 429 provider_code=1113 secret body text"))
    assert result["http_status"] == 429
    assert result["provider_code"] == 1113
    assert result["terminal_http_429_code_1113"] is True
    assert "secret body text" not in json.dumps(result)


def test_transport_guard_restores_hooks_only_after_clean_worker_drain() -> None:
    import httpx

    budget = _budget()
    ledger = transport.TransportLedger()
    workers = transport.ProviderWorkerTracker()
    sync_before = httpx.Client._send_single_request
    async_before = httpx.AsyncClient._send_single_request
    with transport.transport_guard(budget, ledger, workers):
        assert httpx.Client._send_single_request is not sync_before
        assert httpx.AsyncClient._send_single_request is not async_before
    assert httpx.Client._send_single_request is sync_before
    assert httpx.AsyncClient._send_single_request is async_before
    assert workers.transport_hooks_restored is True


def test_transport_guard_keeps_send_hooks_on_worker_leak(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import httpx

    budget = _budget()
    ledger = transport.TransportLedger()
    workers = transport.ProviderWorkerTracker()
    sync_before = httpx.Client._send_single_request
    async_before = httpx.AsyncClient._send_single_request
    monkeypatch.setattr(workers, "drain", lambda: 1)
    try:
        with transport.transport_guard(budget, ledger, workers):
            pass
        assert httpx.Client._send_single_request is not sync_before
        assert httpx.AsyncClient._send_single_request is not async_before
        assert workers.transport_hooks_restored is False
    finally:
        httpx.Client._send_single_request = sync_before
        httpx.AsyncClient._send_single_request = async_before
