from __future__ import annotations

import importlib.util
import json
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "qualify_d2_trajectory_terminal_adapter.py"
SPEC = importlib.util.spec_from_file_location("qualify_d2_trajectory_terminal_adapter", SCRIPT)
assert SPEC and SPEC.loader
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)
contract = mod.contract
transport = mod.transport
adapter = mod.adapter


def _budget() -> mod.ProviderSendBudget:
    return mod.ProviderSendBudget(
        allowed_url_prefix=contract.BASE_URL,
        maximum_logical_calls=220,
        maximum_sends_per_logical_call=36,
        maximum_sends_total=400,
    )


def test_request_plan_exact_and_execution_disabled() -> None:
    plan = contract.load_plan()
    contract.validate_plan(plan)
    assert plan["issue"] == 255
    assert plan["fresh_namespace"] == "rw.d2-trajectory-terminal-adapter.v1"
    assert plan["qualified_adapter_issue"] == 251
    assert plan["qualified_adapter_result_unchanged"] == "PASS"
    assert plan["predecessor_trajectory_result_unchanged"] == "FAIL"
    assert plan["trajectory_logical_calls_total"] == 220
    assert plan["maximum_physical_sends_total"] == 400
    assert plan["pass_requires_terminal_override_exercised"] is True
    assert plan["provider_execution_authorized"] is False
    assert plan["same_request_stream_rerun_allowed"] is False


def test_topology_is_fresh_balanced_and_committed() -> None:
    topology = contract.materialize_topology()
    assert json.loads(contract.TOPOLOGY.read_text()) == topology
    assert len(topology["trajectories"]) == 4
    seen: set[int] = set()
    for index in range(4):
        specs = contract.trajectory_specs(index)
        assert len(specs) == 55
        assert sum(x["shape"] == "fresh_evaluation" for x in specs) == 4
        assert sum(x["shape"] == "developed_development" for x in specs) == 35
        assert sum(x["shape"] == "developed_evaluation" for x in specs) == 12
        assert sum(x["shape"] == "oracle_evaluation" for x in specs) == 4
        seeds = {int(x["seed"]) for x in specs}
        assert min(seeds) >= 3_000_000
        assert not seeds.intersection(range(2_000_000, 2_000_072))
        assert seen.isdisjoint(seeds)
        seen.update(seeds)
    assert len(seen) == 220


def test_preflight_deterministic_and_credential_free(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("ZAI_API_KEY", raising=False)
    monkeypatch.delenv(contract.AUTH_ENV, raising=False)
    monkeypatch.setattr(contract, "MARKER", tmp_path / "absent")
    first = mod.preflight()
    second = mod.preflight()
    assert first == second
    assert first["provider_execution_performed"] is False
    assert first["qualified_adapter_evidence"] == {
        "effective_completed": 72,
        "native_completed": 71,
        "terminal_overrides": 1,
        "physical_sends": 73,
    }


def test_preflight_fails_closed_on_marker(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    marker = tmp_path / "marker"
    marker.write_text("candidate_sha=" + "0" * 40 + "\n")
    monkeypatch.setattr(contract, "MARKER", marker)
    with pytest.raises(AssertionError, match="marker must be absent"):
        mod.preflight()


def _row(*, completed: bool, api_calls: int, sends: int) -> dict[str, object]:
    return {
        "hermes_completed_flag_valid": True,
        "hermes_completed": completed,
        "hermes_failed": False,
        "hermes_partial": False,
        "hermes_interrupted": False,
        "hermes_error_present": False,
        "api_calls": api_calls,
        "final_response_length": 10,
        "structured_parse_valid": True,
        "logical_attribution_integrity": True,
        "physical_provider_sends_observed": sends,
        "attempts": [
            {"http_status": 200, "transport_error_type": None} for _ in range(sends)
        ],
    }


def test_exact_adapter_accepts_native_and_terminal_override() -> None:
    native = adapter.evaluate_terminal_completion(
        mod._result_view(_row(completed=True, api_calls=1, sends=1)),
        max_iterations=2,
        parse_valid=True,
        logical_attribution_integrity=True,
        attempts=_row(completed=True, api_calls=1, sends=1)["attempts"],
        physical_sends=1,
        unexpected_outbound_blocks=0,
        provider_budget_blocks=0,
        attribution_mismatch_blocks=0,
    )
    assert native.effective_completed is True
    assert native.terminal_iteration_override_used is False
    terminal_row = _row(completed=False, api_calls=2, sends=2)
    terminal = adapter.evaluate_terminal_completion(
        mod._result_view(terminal_row),
        max_iterations=2,
        parse_valid=True,
        logical_attribution_integrity=True,
        attempts=terminal_row["attempts"],
        physical_sends=2,
        unexpected_outbound_blocks=0,
        provider_budget_blocks=0,
        attribution_mismatch_blocks=0,
    )
    assert terminal.effective_completed is True
    assert terminal.terminal_iteration_override_used is True


def test_adapter_rejects_bad_parse_and_nonterminal_incomplete() -> None:
    row = _row(completed=False, api_calls=1, sends=1)
    decision = adapter.evaluate_terminal_completion(
        mod._result_view(row),
        max_iterations=2,
        parse_valid=True,
        logical_attribution_integrity=True,
        attempts=row["attempts"],
        physical_sends=1,
        unexpected_outbound_blocks=0,
        provider_budget_blocks=0,
        attribution_mismatch_blocks=0,
    )
    assert decision.effective_completed is False
    bad = adapter.evaluate_terminal_completion(
        mod._result_view(_row(completed=False, api_calls=2, sends=2)),
        max_iterations=2,
        parse_valid=False,
        logical_attribution_integrity=True,
        attempts=_row(completed=False, api_calls=2, sends=2)["attempts"],
        physical_sends=2,
        unexpected_outbound_blocks=0,
        provider_budget_blocks=0,
        attribution_mismatch_blocks=0,
    )
    assert bad.effective_completed is False


def test_clean_hermes_failure_is_semantic_not_apparatus() -> None:
    clean = {"runtime_exception": False, "hermes_completed_flag_valid": True, "adapter_reason": "hermes_failed"}
    assert mod.row_has_apparatus_failure(clean) is False
    assert mod.row_has_apparatus_failure(dict(clean, runtime_exception=True)) is True
    assert mod.row_has_apparatus_failure(dict(clean, adapter_reason="transport_not_exact_clean")) is True


def test_independent_origin_blocks_cross_attribution() -> None:
    budget = _budget()
    ledger = transport.TransportLedger()
    request = SimpleNamespace(headers={contract.PROBE_ORIGIN_HEADER: "118"})
    with budget.logical_call(117):
        with pytest.raises(transport.LogicalAttributionMismatch):
            transport.verified_origin_logical_index(request, budget, ledger)
    assert ledger.attribution_mismatches == 1
    assert budget.total_sends == 0


def test_only_development_strategy_propagates(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[tuple[str, str]] = []

    def fake_run_call(budget: object, ledger: object, logical: int, call_id: str, shape: str, seed: int, arm_budget: int | None, strategy: str):
        del budget, ledger, call_id, seed, arm_budget
        seen.append((shape, strategy))
        return {
            "effective_completed": True,
            "terminal_iteration_override_used": False,
            "hermes_completed": True,
        }, f"developed_development:{logical}"

    monkeypatch.setattr(mod, "run_call", fake_run_call)
    result = mod.run_trajectory(_budget(), transport.TransportLedger(), 0)
    assert result["complete_55_of_55"] is True
    assert len(seen) == 55
    for shape, strategy in seen:
        if shape in {"fresh_evaluation", "oracle_evaluation"}:
            assert strategy == ""
        elif shape == "developed_evaluation":
            assert strategy.startswith("developed_development:")


def test_execution_requires_authorization(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(contract.AUTH_ENV, raising=False)
    monkeypatch.delenv("ZAI_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="not authorized"):
        mod.execute()


def test_worker_drain_waits_for_exit() -> None:
    stop = threading.Event()

    def _call() -> None:
        stop.wait()

    _call.__module__ = "run_agent"
    _call.__name__ = "_call"
    thread = threading.Thread(target=_call, daemon=True)
    tracker = transport.ProviderWorkerTracker()
    tracker.observe_before_start(thread)
    thread.start()

    def release() -> None:
        time.sleep(0.02)
        stop.set()

    releaser = threading.Thread(target=release)
    releaser.start()
    assert tracker.drain(timeout_seconds=1.0) == 0
    releaser.join(timeout=1.0)


def test_bounded_error_does_not_persist_raw_text() -> None:
    result = contract.bounded_error(RuntimeError("HTTP 429 provider_code=1113 secret body"))
    assert result["http_status"] == 429
    assert result["provider_code"] == 1113
    assert "secret body" not in json.dumps(result)
