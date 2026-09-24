from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

import d2_vnext_q3d_diagnostic_core as core
import d2_vnext_q3d_hermes_client as client
import evaluate_d2_vnext_q3d_diagnostic as evaluator
import materialize_d2_vnext_q3d_diagnostic as materializer
import run_d2_vnext_q3d_diagnostic as runner

ROOT = Path(__file__).resolve().parents[1]


def test_fresh_pairwise_cohort_and_resource_envelope() -> None:
    lock = materializer.build_cohort_lock()
    shard_map = materializer.build_shard_map()
    assert lock["cohort_pairs_sha256"] == materializer.EXPECTED_COHORT_SHA256
    assert lock["schema_order"] == ["pairwise_order"]
    assert lock["pair_count"] == 16
    assert all(value == 0 for value in lock["predecessor_seed_namespace_overlap"].values())
    assert core.pair_seed_for(0) == 15_000_000
    assert core.pair_seed_for(15) == 15_001_500
    assert shard_map["shard_count"] == 4
    assert [row["pair_indices"] for row in shard_map["shards"]] == [list(range(0, 4)), list(range(4, 8)), list(range(8, 12)), list(range(12, 16))]
    assert shard_map["maximum_physical_provider_sends_per_logical_call"] == 36
    assert shard_map["maximum_physical_provider_sends_per_shard"] == 1152
    assert shard_map["maximum_physical_provider_sends_campaign"] == 4608
    assert shard_map["budget_borrowing_allowed"] is False


def test_committed_materialization_locks_are_exact() -> None:
    assert json.loads((ROOT / "research/d2_vnext_q3d/D2_VNEXT_Q3D_COHORT_LOCK.json").read_text()) == materializer.build_cohort_lock()
    assert json.loads((ROOT / "research/d2_vnext_q3d/D2_VNEXT_Q3D_SHARD_MAP.json").read_text()) == materializer.build_shard_map()


def _fake_response(content: str | None):
    message = SimpleNamespace(content=content, tool_calls=[])
    choice = SimpleNamespace(message=message, finish_reason="stop")
    usage = SimpleNamespace(prompt_tokens=7, completion_tokens=3, total_tokens=10)
    return SimpleNamespace(model="glm-5.3", choices=[choice], usage=usage)


def test_provider_view_minimizes_content() -> None:
    raw = "sensitive-response-content"
    view = client.provider_completion_view(_fake_response(raw), agent_invocation_index=1, semantic_response_index=1)
    assert view["assistant_content_present"] is True
    assert view["assistant_content_length"] == len(raw)
    assert view["assistant_content_sha256"]
    assert raw not in json.dumps(view, sort_keys=True)
    client.assert_no_raw_content(view)


def test_semantic_wrapper_returns_identical_response_and_calls_once() -> None:
    response = _fake_response("abc")
    calls = {"n": 0}

    def original(*args, **kwargs):
        calls["n"] += 1
        return response

    create = SimpleNamespace(create=original)
    agent = SimpleNamespace(client=SimpleNamespace(chat=SimpleNamespace(completions=create)))
    recorder = client.SemanticRecorder()
    client.instrument_chat_completions(agent, agent_invocation_index=1, recorder=recorder)
    returned = agent.client.chat.completions.create(model="glm-5.3")
    assert returned is response
    assert calls["n"] == 1
    assert len(recorder.rows()) == 1


def test_boundary_classification_is_structural() -> None:
    assert client.classify_boundary(runtime_exception=False, provider_semantic=[{"assistant_content_present": False}], candidate_present=False, parse_valid=False, effective_completed=False) == "provider_content_absent"
    assert client.classify_boundary(runtime_exception=False, provider_semantic=[{"assistant_content_present": True}], candidate_present=False, parse_valid=False, effective_completed=False) == "provider_content_present_hermes_terminal_absent"
    assert client.classify_boundary(runtime_exception=False, provider_semantic=[{"assistant_content_present": True}], candidate_present=True, parse_valid=False, effective_completed=False) == "adapter_candidate_nonempty_parse_invalid"
    assert client.classify_boundary(runtime_exception=False, provider_semantic=[{"assistant_content_present": True}], candidate_present=True, parse_valid=True, effective_completed=True) == "accepted_exact_completion"


def test_authority_gate_fails_without_env_or_marker(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(runner.AUTH_ENV, raising=False)
    with pytest.raises(RuntimeError, match="not authorized"):
        runner.assert_authorized()
    monkeypatch.setenv(runner.AUTH_ENV, "1")
    assert not (ROOT / runner.MARKER_PATH).exists()
    with pytest.raises(RuntimeError, match="marker is absent"):
        runner.assert_authorized()


def test_contract_remains_behaviorally_identical_to_q2() -> None:
    contract = json.loads((ROOT / "research/d2_vnext_q3d/D2_VNEXT_Q3D_CONTRACT.json").read_text())
    invariance = contract["behavioral_invariance"]
    assert invariance["requested_model"] == client.MODEL == "glm-5.3"
    assert invariance["sampling_temperature"] == client.TEMPERATURE == 0.8
    assert invariance["max_agent_invocations_per_logical_call"] == client.MAX_AGENT_INVOCATIONS == 2
    assert invariance["max_agent_iterations_per_invocation"] == client.MAX_ITERATIONS == 2
    assert invariance["max_physical_provider_sends_per_logical_call"] == client.MAX_PHYSICAL_SENDS_PER_LOGICAL_CALL == 36
    assert invariance["parser_relaxation_allowed"] is False
    assert invariance["third_invocation_allowed"] is False


def _diagnostic_attempt(boundary: str, *, clean_empty: bool) -> dict:
    return {
        "agent_invocation_index": 1,
        "api_calls": 2,
        "loop_termination_reason": "iteration_budget_exhausted",
        "provider_semantic_completions": [{"assistant_content_present": boundary != "provider_content_absent"}],
        "terminal_adapter": {"candidate_present": not clean_empty},
        "boundary_classification": boundary,
        "exact_attributed_clean_transport": True,
        "logical_attribution_integrity": True,
        "adapter_reason": "final_response_empty" if clean_empty else "structured_parse_invalid",
        "exact_structured_parse_valid": False,
        "parse_diagnostic": "json_decode_failure",
        "runtime_exception": False,
        "final_response_length": 0 if clean_empty else 8,
    }


def _evaluate_payload(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, payload: dict) -> dict:
    source = tmp_path / "provider.json"
    output_dir = tmp_path / "evaluation"
    source.write_text(json.dumps(payload))
    monkeypatch.setattr(sys, "argv", ["evaluate", str(source), "--output-dir", str(output_dir)])
    evaluator.main()
    return json.loads((output_dir / "d2-vnext-q3d-diagnostic-evaluation.json").read_text())


def _provider_payload(attempt: dict, *, integrity_defects: list[str] | None = None) -> dict:
    return {
        "attempted_pairs": 16,
        "complete_pairs": 0,
        "failed_pairs": 16,
        "physical_provider_sends_observed": 32,
        "integrity_defects": integrity_defects or [],
        "pair_records": [{"q3d_observability": {"first_attempt": attempt, "second_attempt": None}}],
    }


def test_evaluator_fails_closed_on_integrity_defect(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    result = _evaluate_payload(tmp_path, monkeypatch, _provider_payload(_diagnostic_attempt("provider_content_absent", clean_empty=True), integrity_defects=["synthetic_defect"]))
    assert result["classification"] == "Q3-D-INTEGRITY-FAIL"


def test_evaluator_localizes_clean_terminal_empty(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    result = _evaluate_payload(tmp_path, monkeypatch, _provider_payload(_diagnostic_attempt("provider_content_absent", clean_empty=True)))
    assert result["classification"] == "Q3-D-BOUNDARY-LOCALIZED"
    assert result["clean_terminal_empty_target_events"] == 1


def test_evaluator_reports_no_target_event(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    result = _evaluate_payload(tmp_path, monkeypatch, _provider_payload(_diagnostic_attempt("adapter_candidate_nonempty_parse_invalid", clean_empty=False)))
    assert result["classification"] == "Q3-D-NO-TARGET-EVENT"
