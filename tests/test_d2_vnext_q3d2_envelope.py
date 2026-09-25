from __future__ import annotations

import json
import sys
from pathlib import Path

import d2_vnext_q3d2_diagnostic_core as core
import d2_vnext_q3d2_hermes_client as observer
import d2_vnext_q3d_hermes_client as q3d
import evaluate_d2_vnext_q3d2_diagnostic as evaluator
import materialize_d2_vnext_q3d2_diagnostic as materializer
import pytest
import run_d2_vnext_q3d2_diagnostic as runner

ROOT = Path(__file__).resolve().parents[1]


def test_fresh_cohort_and_send_envelope() -> None:
    lock = materializer.build_cohort_lock()
    shard_map = materializer.build_shard_map()

    assert lock["cohort_pairs_sha256"] == materializer.EXPECTED_COHORT_SHA256
    assert lock["pair_count"] == 8
    assert lock["schema_order"] == ["pairwise_order"]
    assert all(value == 0 for value in lock["predecessor_seed_namespace_overlap"].values())
    assert core.NAMESPACE == "rw.d2-vnext-q3d2-request-scoped-terminal-boundary-diagnostic.v1"
    assert core.pair_seed_for(0) == 16_000_000
    assert core.pair_seed_for(7) == 16_000_700

    assert shard_map["shard_count"] == 2
    assert [row["pair_indices"] for row in shard_map["shards"]] == [
        [0, 1, 2, 3],
        [4, 5, 6, 7],
    ]
    assert shard_map["maximum_registered_logical_calls_per_shard"] == 220
    assert shard_map["maximum_physical_provider_sends_per_logical_call"] == 36
    assert shard_map["maximum_physical_provider_sends_per_shard"] == 1152
    assert shard_map["maximum_physical_provider_sends_campaign"] == 2304
    assert shard_map["budget_borrowing_allowed"] is False


def test_committed_materialization_locks_are_exact() -> None:
    assert json.loads(
        (ROOT / "research/d2_vnext_q3d2/D2_VNEXT_Q3D2_COHORT_LOCK.json").read_text()
    ) == materializer.build_cohort_lock()
    assert json.loads(
        (ROOT / "research/d2_vnext_q3d2/D2_VNEXT_Q3D2_SHARD_MAP.json").read_text()
    ) == materializer.build_shard_map()


def test_request_scoped_observer_activation_is_scoped() -> None:
    original = q3d.instrument_chat_completions
    with observer.activate_request_scoped_observer():
        assert q3d.instrument_chat_completions is observer.instrument_request_scoped_chat_completions
    assert q3d.instrument_chat_completions is original


def test_authority_gate_fails_without_env_or_marker(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(runner.AUTH_ENV, raising=False)
    with pytest.raises(RuntimeError, match="not authorized"):
        runner.assert_authorized()
    monkeypatch.setenv(runner.AUTH_ENV, "1")
    assert not (ROOT / runner.MARKER_PATH).exists()
    with pytest.raises(RuntimeError, match="marker is absent"):
        runner.assert_authorized()


def _semantic(invocation_index: int, response_index: int, *, assistant_present: bool) -> dict:
    return {
        "agent_invocation_index": invocation_index,
        "semantic_response_index": response_index,
        "semantic_response_observed": True,
        "semantic_response_error_type": None,
        "effective_model_if_returned": "glm-5.3",
        "choice_count": 1,
        "finish_reason_present": True,
        "finish_reason": "stop",
        "assistant_message_present": True,
        "assistant_content_present": assistant_present,
        "assistant_content_type": "string",
        "assistant_content_length": 4 if assistant_present else 0,
        "assistant_content_sha256": "a" * 64 if assistant_present else None,
        "tool_calls_present": False,
        "tool_calls_count": 0,
        "usage_prompt_tokens": 7,
        "usage_completion_tokens": 3,
        "usage_total_tokens": 10,
        "provider_sends": [
            {
                "logical_send_index": response_index,
                "total_send_index": response_index,
                "http_status": 200,
                "transport_error_type": None,
            }
        ],
    }


def _invocation(invocation_index: int, *, clean_empty: bool, boundary: str) -> dict:
    semantic = [
        _semantic(invocation_index, 1, assistant_present=boundary != "provider_content_absent"),
        _semantic(invocation_index, 2, assistant_present=boundary != "provider_content_absent"),
    ]
    hermes_terminal = {
        "present": not clean_empty,
        "type": "string",
        "length": 8 if not clean_empty else 0,
        "sha256": "b" * 64 if not clean_empty else None,
    }
    adapter = {
        "candidate_source": "hermes_final_response_after_q2_string_normalization",
        "candidate_present": not clean_empty,
        "candidate_type": "string",
        "candidate_length": 8 if not clean_empty else 0,
        "candidate_sha256": "b" * 64 if not clean_empty else None,
        "candidate_matches_hermes_terminal": True,
        "adapter_reason": "final_response_empty" if clean_empty else "structured_parse_invalid",
        "parse_diagnostic": "json_decode_failure",
        "exact_structured_parse_valid": False,
        "accepted_exact_completion": False,
    }
    return {
        "agent_invocation_index": invocation_index,
        "api_calls": 2,
        "hermes_completed_flag_valid": True,
        "hermes_completed": False,
        "hermes_failed": False,
        "hermes_partial": False,
        "hermes_interrupted": False,
        "hermes_error_present": False,
        "loop_termination_reason": "iteration_budget_exhausted",
        "terminal_iteration_override_used": False,
        "physical_provider_sends_observed": 2,
        "exact_attributed_clean_transport": True,
        "logical_attribution_integrity": True,
        "json_mode_compatibility_failure": False,
        "semantic_completions": semantic,
        "hermes_terminal": hermes_terminal,
        "adapter_snapshot": adapter,
        "boundary_classification": boundary,
    }


def _record(*, clean_empty_target: bool, boundary: str) -> dict:
    first = _invocation(1, clean_empty=clean_empty_target, boundary=boundary)
    invocations = [first]
    trigger = None
    retry_used = False
    if clean_empty_target:
        trigger = "clean_terminal_empty"
        retry_used = True
        invocations.append(
            _invocation(2, clean_empty=True, boundary="provider_content_absent")
        )
    return {
        "schema": "d2-vnext-q3d2-structural-observability-record-v0.1",
        "study_stream": "D2-vNext-Q3-D2",
        "stage": "Q3-D2",
        "pair_public_id": "d2-vnext-q3d2-pairwise_order-pair-000",
        "schema_id": "pairwise_order",
        "arm": "fresh",
        "phase": "fresh/evaluation1",
        "logical_call_index": 0,
        "physical_provider_sends_observed": 4 if retry_used else 2,
        "agent_invocations": invocations,
        "retry_eligible_after_first": trigger is not None,
        "retry_trigger_class": trigger,
        "retry_used": retry_used,
        "accepted_attempt_index": None,
        "accepted_exact_completion": False,
        "boundary_classification": invocations[-1]["boundary_classification"],
        "observability_defects": [],
    }


def _provider_payload(record: dict, *, integrity_defects: list[str] | None = None) -> dict:
    return {
        "attempted_pairs": 8,
        "complete_pairs": 0,
        "failed_pairs": 8,
        "physical_provider_sends_observed": 4,
        "integrity_defects": integrity_defects or [],
        "pair_records": [
            {
                "pair_public_id": record["pair_public_id"],
                "schema_id": record["schema_id"],
                "q3d2_observability_records": [record],
            }
        ],
    }


def _evaluate_payload(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    payload: dict,
) -> dict:
    source = tmp_path / "provider.json"
    output_dir = tmp_path / "evaluation"
    source.write_text(json.dumps(payload))
    monkeypatch.setattr(
        sys,
        "argv",
        ["evaluate", str(source), "--output-dir", str(output_dir)],
    )
    evaluator.main()
    return json.loads((output_dir / "d2-vnext-q3d2-diagnostic-evaluation.json").read_text())


def test_evaluator_localizes_fully_observed_clean_empty(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    record = _record(clean_empty_target=True, boundary="provider_content_absent")
    result = _evaluate_payload(tmp_path, monkeypatch, _provider_payload(record))
    assert result["classification"] == "Q3-D2-BOUNDARY-LOCALIZED"
    assert result["clean_terminal_empty_target_events"] == 1
    assert result["target_event_boundary_counts"] == {"provider_content_absent": 1}


def test_evaluator_fails_closed_on_integrity_defect(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    record = _record(clean_empty_target=True, boundary="provider_content_absent")
    result = _evaluate_payload(
        tmp_path,
        monkeypatch,
        _provider_payload(record, integrity_defects=["synthetic_defect"]),
    )
    assert result["classification"] == "Q3-D2-INTEGRITY-FAIL"


def test_evaluator_reports_no_target_event(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    record = _record(
        clean_empty_target=False,
        boundary="adapter_candidate_nonempty_parse_invalid",
    )
    result = _evaluate_payload(tmp_path, monkeypatch, _provider_payload(record))
    assert result["classification"] == "Q3-D2-NO-TARGET-EVENT"
