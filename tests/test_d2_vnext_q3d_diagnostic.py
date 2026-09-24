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


def test_boundary_classification_separates_hermes_and_adapter() -> None:
    provider_present = [{"semantic_response_observed": True, "assistant_content_present": True}]
    provider_absent = [{"semantic_response_observed": True, "assistant_content_present": False}]
    empty = {"present": False}
    present = {"present": True}
    assert client.classify_boundary(runtime_exception=False, provider_semantic=provider_absent, hermes_terminal=empty, adapter_candidate=empty, parse_valid=False, effective_completed=False) == "provider_content_absent"
    assert client.classify_boundary(runtime_exception=False, provider_semantic=provider_present, hermes_terminal=empty, adapter_candidate=empty, parse_valid=False, effective_completed=False) == "provider_content_present_hermes_terminal_absent"
    assert client.classify_boundary(runtime_exception=False, provider_semantic=provider_present, hermes_terminal=present, adapter_candidate=empty, parse_valid=False, effective_completed=False) == "hermes_terminal_present_adapter_candidate_absent"
    assert client.classify_boundary(runtime_exception=False, provider_semantic=provider_present, hermes_terminal=present, adapter_candidate=present, parse_valid=False, effective_completed=False) == "adapter_candidate_nonempty_parse_invalid"


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


def test_observability_schema_matches_v02_record_shape() -> None:
    schema = json.loads((ROOT / "research/d2_vnext_q3d/D2_VNEXT_Q3D_OBSERVABILITY_SCHEMA.json").read_text())
    assert schema["properties"]["schema"]["const"] == "d2-vnext-q3d-structural-observability-record-v0.2"
    assert "pair_public_id" in schema["required"]
    assert "agent_invocations" in schema["required"]
    invocation = schema["$defs"]["agent_invocation"]
    assert "semantic_completions" in invocation["required"]
    semantic = schema["$defs"]["semantic_completion"]
    assert "provider_sends" in semantic["required"]
    adapter = schema["$defs"]["adapter_snapshot"]
    assert "candidate_matches_hermes_terminal" in adapter["required"]


def _semantic(invocation_index: int, response_index: int, *, assistant_present: bool) -> dict:
    return {"agent_invocation_index": invocation_index, "semantic_response_index": response_index, "semantic_response_observed": True, "semantic_response_error_type": None, "effective_model_if_returned": "glm-5.3", "choice_count": 1, "finish_reason_present": True, "finish_reason": "stop", "assistant_message_present": True, "assistant_content_present": assistant_present, "assistant_content_type": "string", "assistant_content_length": 4 if assistant_present else 0, "assistant_content_sha256": "a" * 64 if assistant_present else None, "tool_calls_present": False, "tool_calls_count": 0, "usage_prompt_tokens": 7, "usage_completion_tokens": 3, "usage_total_tokens": 10, "provider_sends": [{"logical_send_index": response_index, "total_send_index": response_index, "http_status": 200, "transport_error_type": None}]}


def _invocation(invocation_index: int, *, clean_empty: bool, boundary: str) -> dict:
    semantic = [_semantic(invocation_index, 1, assistant_present=boundary != "provider_content_absent"), _semantic(invocation_index, 2, assistant_present=boundary != "provider_content_absent")]
    hermes_terminal = {"present": not clean_empty, "type": "string", "length": 8 if not clean_empty else 0, "sha256": "b" * 64 if not clean_empty else None}
    adapter = {"candidate_source": "hermes_final_response_after_q2_string_normalization", "candidate_present": not clean_empty, "candidate_type": "string", "candidate_length": 8 if not clean_empty else 0, "candidate_sha256": "b" * 64 if not clean_empty else None, "candidate_matches_hermes_terminal": True, "adapter_reason": "final_response_empty" if clean_empty else "structured_parse_invalid", "parse_diagnostic": "json_decode_failure", "exact_structured_parse_valid": False, "accepted_exact_completion": False}
    return {"agent_invocation_index": invocation_index, "api_calls": 2, "hermes_completed_flag_valid": True, "hermes_completed": False, "hermes_failed": False, "hermes_partial": False, "hermes_interrupted": False, "hermes_error_present": False, "loop_termination_reason": "iteration_budget_exhausted", "terminal_iteration_override_used": False, "physical_provider_sends_observed": 2, "exact_attributed_clean_transport": True, "logical_attribution_integrity": True, "json_mode_compatibility_failure": False, "semantic_completions": semantic, "hermes_terminal": hermes_terminal, "adapter_snapshot": adapter, "boundary_classification": boundary}


def _record(*, clean_empty_target: bool, boundary: str) -> dict:
    first = _invocation(1, clean_empty=clean_empty_target, boundary=boundary)
    invocations = [first]
    trigger = None
    retry_used = False
    if clean_empty_target:
        trigger = "clean_terminal_empty"
        retry_used = True
        invocations.append(_invocation(2, clean_empty=True, boundary="provider_content_absent"))
    return {"schema": "d2-vnext-q3d-structural-observability-record-v0.2", "study_stream": "D2-vNext-Q3-D", "stage": "Q3-D", "pair_public_id": "d2-vnext-q3d-pairwise_order-pair-000", "schema_id": "pairwise_order", "arm": "fresh", "phase": "fresh/evaluation1", "logical_call_index": 0, "physical_provider_sends_observed": 4 if retry_used else 2, "agent_invocations": invocations, "retry_eligible_after_first": trigger is not None, "retry_trigger_class": trigger, "retry_used": retry_used, "accepted_attempt_index": None, "accepted_exact_completion": False, "boundary_classification": invocations[-1]["boundary_classification"], "observability_defects": []}


def _provider_payload(record: dict, *, integrity_defects: list[str] | None = None) -> dict:
    return {"attempted_pairs": 16, "complete_pairs": 0, "failed_pairs": 16, "physical_provider_sends_observed": 32, "integrity_defects": integrity_defects or [], "pair_records": [{"pair_public_id": record["pair_public_id"], "schema_id": record["schema_id"], "q3d_observability_records": [record]}]}


def _evaluate_payload(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, payload: dict) -> dict:
    source = tmp_path / "provider.json"
    output_dir = tmp_path / "evaluation"
    source.write_text(json.dumps(payload))
    monkeypatch.setattr(sys, "argv", ["evaluate", str(source), "--output-dir", str(output_dir)])
    evaluator.main()
    return json.loads((output_dir / "d2-vnext-q3d-diagnostic-evaluation.json").read_text())


def test_evaluator_fails_closed_on_integrity_defect(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    record = _record(clean_empty_target=True, boundary="provider_content_absent")
    result = _evaluate_payload(tmp_path, monkeypatch, _provider_payload(record, integrity_defects=["synthetic_defect"]))
    assert result["classification"] == "Q3-D-INTEGRITY-FAIL"


def test_evaluator_localizes_only_frozen_clean_terminal_empty(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    record = _record(clean_empty_target=True, boundary="provider_content_absent")
    result = _evaluate_payload(tmp_path, monkeypatch, _provider_payload(record))
    assert result["classification"] == "Q3-D-BOUNDARY-LOCALIZED"
    assert result["clean_terminal_empty_target_events"] == 1
    assert result["target_event_boundary_counts"] == {"provider_content_absent": 1}


def test_evaluator_reports_no_target_event(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    record = _record(clean_empty_target=False, boundary="adapter_candidate_nonempty_parse_invalid")
    result = _evaluate_payload(tmp_path, monkeypatch, _provider_payload(record))
    assert result["classification"] == "Q3-D-NO-TARGET-EVENT"


def test_evaluator_fails_closed_when_trigger_predicate_does_not_match(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    record = _record(clean_empty_target=True, boundary="provider_content_absent")
    record["agent_invocations"][0]["hermes_failed"] = True
    result = _evaluate_payload(tmp_path, monkeypatch, _provider_payload(record))
    assert result["classification"] == "Q3-D-OBSERVABILITY-FAIL"


def test_evaluator_fails_closed_on_missing_semantic_completion(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    record = _record(clean_empty_target=True, boundary="provider_content_absent")
    record["agent_invocations"][0]["semantic_completions"] = []
    result = _evaluate_payload(tmp_path, monkeypatch, _provider_payload(record))
    assert result["classification"] == "Q3-D-OBSERVABILITY-FAIL"
