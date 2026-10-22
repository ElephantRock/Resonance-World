"""Strict independent reconstruction of G1 multischema calibration send ledger."""

from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

from resonance_world.c3r_g1_calibration_audit import audit_calibration_transport
from resonance_world.c3r_g1_model_boundary import ModelChoiceCompletion
from resonance_world.c3r_g1_multischema_calibration import (
    CalibrationRunner,
    run_offline_calibration,
)
from resonance_world.c3r_g1_zai_transport import (
    PhysicalSendLedger,
    TransportResponse,
    ZaiStandardModelPort,
)


def _fixture(*, bad_index: int | None = None, failure: str = ""):
    sends = []

    def transport(_url, _headers, body, _timeout):
        sends.append(json.loads(body))
        index = len(sends) - 1
        if index == bad_index:
            if failure == "http":
                return TransportResponse(429, b"")
            if failure == "empty_length":
                answer, reason = "", "length"
            else:
                answer, reason = "not_exact_A", "stop"
        else:
            answer, reason = "A", "stop"
        return TransportResponse(
            200, json.dumps({
                "choices": [{"message": {"content": answer}, "finish_reason": reason}],
                "usage": {"completion_tokens": 15,
                          "completion_tokens_details": {"reasoning_tokens": 7}},
            }).encode(),
        )

    ledger = PhysicalSendLedger(8)
    port = ZaiStandardModelPort(
        api_key="synthetic-test-only", model_id="glm-5.3",
        ledger=ledger, enabled=True, transport=transport, max_tokens=512,
        route="coding",
    )
    report = CalibrationRunner("glm-5.3").run(port).to_dict()
    return report, ledger.to_dict(), sends


def _audit(report, ledger, **kwargs):
    return audit_calibration_transport(report, ledger, **{"max_tokens": 512, **kwargs})


def test_recomputes_each_prescribed_body_and_all_summary_counts() -> None:
    report, ledger, sends = _fixture()
    assert len(sends) == 8
    assert len(ledger["entries"]) == 8
    audit = _audit(report, ledger)
    assert audit.verdict == "structurally_consistent_unattested"
    assert audit.reserved == 8
    data = audit.to_dict()
    assert data["physical_sends_authenticated"] is False
    assert data["billing_authenticated"] is False
    assert data["scientific_acceptance"] is False
    assert data["authorizes_provider_execution"] is False
    assert all(x["status"] == "accepted" for x in report["attempt_records"])


@pytest.mark.parametrize(("path", "value", "expected"), [
    (("public_plan_digest",), "0" * 64, "public_plan_lock_invalid"),
    (("answered_calls",), 7, "aggregate_or_family_count_mismatch"),
    (("answer_yield",), 0.5, "aggregate_or_family_count_mismatch"),
    (("qualification_complete_triplets",), 1, "aggregate_or_family_count_mismatch"),
    (("per_family", "arithmetic", "parseable"), 1,
     "aggregate_or_family_count_mismatch"),
    (("technical_yield_gate", "passed"), False, "technical_gate_invalid"),
    (("technical_yield_gate", "authorizes_provider_sends"), True,
     "technical_gate_invalid"),
    (("scientific_acceptance",), True, "scientific_acceptance_must_remain_false"),
    (("attempt_records", 2, "task_id"), "fake", "attempt_identity_or_order_mismatch"),
    (("attempt_records", 3, "finish_reason"), None,
     "accepted_without_normal_termination"),
    (("attempt_records", 4, "answer_accepted"), False,
     "accepted_status_disagreement"),
    (("attempt_records", 4, "status"), "not_sent_after_failure",
     "unsent_without_prior_failure"),
    (("attempt_records", 4, "reported_reasoning_tokens"), -1,
     "reported_token_usage_invalid"),
    (("entries", 0, "request_digest"), "f" * 64, "provider_request_body_mismatch"),
    (("entries", 1, "http_status"), 429, "model_reply_without_successful_http"),
    (("entries", 2, "failure_class"), "reserved",
     "incomplete_pre_send_reservation"),
])
def test_rejects_modified_report_or_ledger(path, value, expected) -> None:
    report, ledger, _sends = _fixture()
    target = ledger if path[0] == "entries" else report
    ref = copy.deepcopy(target)
    cursor = ref
    for name in path[:-1]:
        cursor = cursor[name]
    cursor[path[-1]] = value
    if path[0] == "entries":
        ledger = ref
    else:
        report = ref
    verdict = _audit(report, ledger)
    assert verdict.verdict == "rejected"
    assert expected in verdict.issues
    assert verdict.to_dict()["scientific_acceptance"] is False


def test_first_invalid_format_keeps_full_logical_denominator() -> None:
    report, ledger, sends = _fixture(bad_index=2)
    assert len(sends) == ledger["reserved"] == 3
    assert report["attempt_records"][2]["status"] == "invalid_format"
    assert all(x["status"] == "not_sent_after_failure"
               for x in report["attempt_records"][3:])
    audit = _audit(report, ledger)
    assert audit.verdict == "structurally_consistent_unattested"
    assert audit.prescribed == 8
    assert report["qualification_complete_triplets"] == 0
    assert report["technical_yield_gate"]["passed"] is False


def test_exhausted_reasoning_budget_is_reconciled_as_terminal() -> None:
    report, ledger, sends = _fixture(bad_index=0, failure="empty_length")
    assert len(sends) == 1
    assert ledger["entries"][0]["failure_class"] == "EmptyFinalOutputLengthCap"
    assert report["attempt_records"][0]["status"] == "unfinished_output"
    assert _audit(report, ledger).verdict == "structurally_consistent_unattested"


def test_http_error_counts_reserved_send_and_stops() -> None:
    report, ledger, sends = _fixture(bad_index=0, failure="http")
    assert len(sends) == 1
    assert ledger["entries"][0]["failure_class"] == "HttpNon200"
    assert report["attempt_records"][0]["status"] == "adapter_exception"
    assert _audit(report, ledger).verdict == "structurally_consistent_unattested"


def test_unsent_offline_fixture_cannot_pass_as_transport_evidence() -> None:
    report = run_offline_calibration().to_dict()
    ledger = PhysicalSendLedger(8).to_dict()
    audit = _audit(report, ledger)
    assert audit.verdict == "rejected"
    assert "physical_send_count_vs_attempt_mismatch" in audit.issues


def test_budget_or_model_change_breaks_reconstructed_body_lock() -> None:
    report, ledger, _sends = _fixture()
    assert _audit(report, ledger, max_tokens=256).verdict == "rejected"
    assert _audit(report, ledger, expected_model="glm-5.3-flash").verdict == "rejected"


def test_duplicate_or_missing_reserved_record_rejected() -> None:
    report, ledger, _sends = _fixture()
    mutated = copy.deepcopy(ledger)
    mutated["entries"][1] = copy.deepcopy(mutated["entries"][0])
    assert "send_sequence_invalid" in _audit(report, mutated).issues
    mutated = copy.deepcopy(ledger)
    mutated["entries"].pop()
    assert "send_ledger_shape_invalid" in _audit(report, mutated).issues


def test_missing_finish_reason_is_never_accepted_in_calibration() -> None:
    class UnreportedFinish:
        seen = 0

        def complete_prompt(self, _prompt):
            self.seen += 1
            return ModelChoiceCompletion("A", "glm-5.3", finish_reason=None)

    port = UnreportedFinish()
    report = CalibrationRunner("glm-5.3").run(port).to_dict()
    assert port.seen == 1
    assert report["attempt_records"][0]["status"] == "unfinished_output"
    assert report["answered_calls"] == 0
    assert report["prescribed_logical_calls"] == 8
    assert report["scientific_acceptance"] is False


def test_bad_input_is_rejected_without_raise_or_provider_activity() -> None:
    ledger = PhysicalSendLedger(8).to_dict()
    assert _audit(None, ledger).verdict == "rejected"
    assert _audit({}, ledger).verdict == "rejected"
    with pytest.raises(ValueError):
        _audit({}, ledger, max_tokens=131073)



def test_standalone_cli_verifies_only_bounded_local_artifacts(tmp_path: Path) -> None:
    report, ledger, _ = _fixture()
    report_path = tmp_path / "calibration.json"
    ledger_path = tmp_path / "reservations.json"
    report_path.write_text(json.dumps(report), encoding="utf-8")
    ledger_path.write_text(json.dumps(ledger), encoding="utf-8")
    cmd = [
        sys.executable, "-m", "resonance_world.c3r_g1_calibration_audit",
        "--report", str(report_path), "--ledger", str(ledger_path),
        "--model", "glm-5.3", "--route", "coding", "--max-tokens", "512",
    ]
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(cmd, cwd=root, capture_output=True, text=True,
                            check=False, timeout=15)
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["verdict"] == "structurally_consistent_unattested"
    assert payload["physical_sends_authenticated"] is False
    assert payload["scientific_acceptance"] is False

    ledger_path.write_text("{invalid", encoding="utf-8")
    rejected = subprocess.run(cmd, cwd=root, capture_output=True, text=True,
                              check=False, timeout=15)
    assert rejected.returncode == 2
    assert json.loads(rejected.stdout)["scientific_acceptance"] is False
    ledger_path.unlink()
    ledger_path.symlink_to(report_path)
    rejected_symlink = subprocess.run(
        cmd, cwd=root, capture_output=True, text=True, check=False, timeout=15
    )
    assert rejected_symlink.returncode == 2


def test_early_exception_before_transport_reservation_is_distinguished() -> None:
    class PreSendFailure:
        calls = 0

        def complete_prompt(self, _prompt):
            self.calls += 1
            raise RuntimeError("synthetic failure before transport reserve")

    port = PreSendFailure()
    report = CalibrationRunner("glm-5.3").run(port).to_dict()
    ledger = PhysicalSendLedger(8).to_dict()
    assert port.calls == 1
    audit = _audit(report, ledger)
    assert audit.verdict == "structurally_consistent_unattested"
    assert audit.reserved == 0
    assert audit.to_dict()["physical_sends_authenticated"] is False
    assert report["attempt_records"][0]["status"] == "adapter_exception"
