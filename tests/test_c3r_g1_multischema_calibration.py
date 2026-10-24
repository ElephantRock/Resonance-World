"""G1 two-schema three-arm output calibration and bounded Z.AI prompt reuse."""

from __future__ import annotations

import json
from dataclasses import dataclass, field

import pytest

from resonance_world.c3r_g1_model_boundary import ModelChoiceCompletion
from resonance_world.c3r_g1_multischema_calibration import (
    LOGICAL_BUDGET,
    CalibrationRunner,
    make_calibration_plan,
    run_offline_calibration,
)
from resonance_world.c3r_g1_zai_transport import (
    PhysicalSendLedger,
    TransportResponse,
    ZaiStandardModelPort,
)


def test_calibration_studies_two_task_schemas_without_using_G1_holdouts() -> None:
    plan = make_calibration_plan()
    assert len(plan) == LOGICAL_BUDGET == 8
    assert [p.stage for p in plan] == [
        "development", "development", *["qualification"] * 6
    ]
    assert [p.family for p in plan] == [
        "arithmetic", "text", *["arithmetic"] * 3, *["text"] * 3
    ]
    assert set(p.arm for p in plan[2:5]) == {"learned", "fresh", "placebo"}
    assert set(p.arm for p in plan[5:]) == {"learned", "fresh", "placebo"}
    assert all(p.task.task_id.startswith("cal-") for p in plan)
    assert all(p.task.context.startswith("technical-cal-") for p in plan)
    assert all("Prior graded development attempts:" in p.prompt() for p in plan)
    assert all("expected_answer" not in p.prompt() for p in plan)
    assert "text.replace" in plan[1].prompt()
    assert "value + offset" in plan[0].prompt()


def test_no_network_fixture_yields_zero_authority_even_when_all_valid() -> None:
    report = run_offline_calibration()
    data = report.to_dict()
    assert data["prescribed_logical_calls"] == 8
    assert data["answered_calls"] == 8
    assert data["development_parseable"] == 2
    assert data["qualification_complete_triplets"] == 2
    assert data["technical_yield_gate"]["passed"] is True
    assert data["technical_yield_gate"]["authorizes_provider_sends"] is False
    assert data["technical_yield_gate"]["authorizes_scientific_study"] is False
    assert data["scientific_acceptance"] is False
    assert data["provider_sends_verified"] is False
    assert all(v["parseable"] == 4 for v in data["per_family"].values())
    assert report.canonical_bytes() == run_offline_calibration().canonical_bytes()


@dataclass
class _Capture:
    model_id: str = "glm-5.3"
    outputs: list[str] = field(default_factory=lambda: ["A"] * 8)
    prompts: list[str] = field(default_factory=list)

    def complete_prompt(self, prompt: str) -> ModelChoiceCompletion:
        self.prompts.append(prompt)
        choice = self.outputs[len(self.prompts) - 1]
        return ModelChoiceCompletion(
            choice, self.model_id, finish_reason="stop",
            completion_tokens_reported=12, reasoning_tokens_reported=10,
        )


def test_all_parseable_outputs_are_calibration_only_without_grading() -> None:
    port = _Capture()
    data = CalibrationRunner("glm-5.3").run(port).to_dict()
    assert len(port.prompts) == 8
    assert len(data["attempt_records"]) == 8
    assert data["answered_calls"] == 8
    assert {x["status"] for x in data["attempt_records"]} == {"accepted"}
    assert all(x["reported_completion_tokens"] == 12
               for x in data["attempt_records"])
    assert "success" not in json.dumps(data)
    assert data["technical_yield_gate"]["passed"] is True
    assert data["scientific_acceptance"] is False


def test_first_bad_format_stops_remaining_calls_and_preserves_denominator() -> None:
    port = _Capture(outputs=["A", "B", "The answer is A", *["A"] * 5])
    data = CalibrationRunner("glm-5.3").run(port).to_dict()
    assert len(port.prompts) == 3
    assert data["answered_calls"] == 2
    assert data["prescribed_logical_calls"] == 8
    assert data["qualification_complete_triplets"] == 0
    assert data["attempt_records"][2]["status"] == "invalid_format"
    assert all(row["status"] == "not_sent_after_failure"
               for row in data["attempt_records"][3:])
    assert data["technical_yield_gate"]["passed"] is False


def test_wrong_model_circuits_before_extra_calls() -> None:
    port = _Capture(model_id="unapproved-model")
    result = CalibrationRunner("glm-5.3").run(port).to_dict()
    assert len(port.prompts) == 1
    assert result["attempt_records"][0]["status"] == "wrong_model"
    assert result["attempt_records"][1]["status"] == "not_sent_after_failure"


def test_truncated_answer_counts_failure_even_if_exact_A() -> None:
    class LengthPort:
        attempts = 0

        def complete_prompt(self, _prompt):
            self.attempts += 1
            return ModelChoiceCompletion(
                "A", "glm-5.3", finish_reason="length",
                completion_tokens_reported=512,
            )

    port = LengthPort()
    report = CalibrationRunner("glm-5.3").run(port).to_dict()
    assert port.attempts == 1
    assert report["attempt_records"][0]["status"] == "unfinished_output"
    assert report["answered_calls"] == 0


def test_raised_provider_error_is_sanitized_and_stops_immediately() -> None:
    class Failure:
        attempts = 0

        def complete_prompt(self, _prompt):
            self.attempts += 1
            raise RuntimeError("contains PRIVATE_PROVIDER_RESPONSE_STRING")

    port = Failure()
    data = CalibrationRunner("glm-5.3").run(port).to_dict()
    assert port.attempts == 1
    assert data["attempt_records"][0]["status"] == "adapter_exception"
    assert "PRIVATE_PROVIDER_RESPONSE_STRING" not in json.dumps(data)
    assert data["answered_calls"] == 0
    assert len(data["attempt_records"]) == 8


def test_zai_port_can_calibrate_text_schema_with_shared_eight_send_budget() -> None:
    sends = []

    def fake_transport(url, headers, body, timeout):
        sends.append((url, headers, json.loads(body), timeout))
        return TransportResponse(
            200, json.dumps({
                "choices": [{"message": {"content": "B"}, "finish_reason": "stop"}],
                "usage": {"completion_tokens": 45},
            }).encode("utf-8")
        )

    ledger = PhysicalSendLedger(max_total_sends=8)
    port = ZaiStandardModelPort(
        api_key="synthetic-never-sent", model_id="glm-5.3",
        ledger=ledger, enabled=True, transport=fake_transport,
        route="standard", max_tokens=512,
    )
    data = CalibrationRunner("glm-5.3").run(port).to_dict()
    assert len(sends) == ledger.consumed == 8
    assert data["answered_calls"] == 8
    assert data["qualification_complete_triplets"] == 2
    assert all("/api/paas/" in send[0] for send in sends)
    assert any("text.replace" in send[2]["messages"][0]["content"] for send in sends)
    assert any("value + offset" in send[2]["messages"][0]["content"] for send in sends)
    assert all(send[2]["max_tokens"] == 512 for send in sends)
    assert all(send[2]["reasoning_effort"] == "low" for send in sends)
    assert all(send[2]["temperature"] == 0 for send in sends)
    assert all(row.failure_class is None for row in ledger.records)
    assert data["provider_sends_verified"] is False


def test_raw_prompt_is_bounded_and_disabled_by_default_without_reservation() -> None:
    send_count = 0

    def fake_send(*_args):
        nonlocal send_count
        send_count += 1
        raise AssertionError("disabled adapter must not dispatch")

    ledger = PhysicalSendLedger(8)
    port = ZaiStandardModelPort(
        api_key="synthetic", model_id="glm-5.3",
        ledger=ledger, enabled=False, transport=fake_send,
    )
    with pytest.raises(PermissionError):
        port.complete_prompt("Choose exactly A or B")
    for bad in ("", " " * 5, "\x00", "x" * 8193):
        with pytest.raises(ValueError):
            port.complete_prompt(bad)
    assert ledger.consumed == 0
    assert send_count == 0


def test_provider_non200_preserves_failclosed_denominator() -> None:
    sends = 0

    def fail_transport(*_args):
        nonlocal sends
        sends += 1
        return TransportResponse(429, b"")

    ledger = PhysicalSendLedger(8)
    port = ZaiStandardModelPort(
        api_key="synthetic", model_id="glm-5.3",
        ledger=ledger, enabled=True, transport=fail_transport,
    )
    data = CalibrationRunner("glm-5.3").run(port).to_dict()
    assert sends == ledger.consumed == 1
    assert ledger.records[0].http_status == 429
    assert all(row["status"] == "not_sent_after_failure"
               for row in data["attempt_records"][1:])
    assert data["technical_yield_gate"]["passed"] is False
