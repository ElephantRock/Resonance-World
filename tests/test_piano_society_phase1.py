from __future__ import annotations

from experiments.piano_society.phase1 import run_pair, score_records


FIELD_SHA = "f" * 40


def _record(
    *,
    occurred_at: str,
    intended_action: str,
    speech_action: str,
    action: str,
    speech_claims_success: bool,
    grounded_success: bool,
    expectation_met: bool,
) -> dict[str, object]:
    return {
        "schema": "resonance-field-piano-step-v0.1",
        "agent_id": "00000000-0000-0000-0000-000000000501",
        "occurred_at": occurred_at,
        "intention": "fixture intention",
        "speech": "fixture speech",
        "intended_action": intended_action,
        "speech_action": speech_action,
        "speech_claims_success": speech_claims_success,
        "action": action,
        "action_payload": {},
        "expected_outcome_status": "succeeded",
        "expected_effects": {},
        "acknowledgement": {
            "action_request_id": "00000000-0000-0000-0000-000000000601",
            "correlation_id": "00000000-0000-0000-0000-000000000701",
            "policy_result": "allow",
            "outcome_status": "succeeded" if grounded_success else "rejected",
            "expectation_met": expectation_met,
            "grounded_success": grounded_success,
            "output_trace_ids": [],
            "error": None,
        },
    }


def _payload(arm: str, records: list[dict[str, object]]) -> dict[str, object]:
    return {
        "schema": "resonance-field-piano-fixture-v0.1",
        "arm": arm,
        "scientific_claim_allowed": False,
        "records": records,
    }


def test_mechanical_score_detects_cross_channel_and_grounding_failures() -> None:
    records = [
        _record(
            occurred_at="2026-08-12T12:00:00+00:00",
            intended_action="OBSERVE",
            speech_action="REQUEST_TOOL",
            action="OBSERVE",
            speech_claims_success=False,
            grounded_success=True,
            expectation_met=True,
        ),
        _record(
            occurred_at="2026-08-12T12:00:01+00:00",
            intended_action="REQUEST_TOOL",
            speech_action="REQUEST_TOOL",
            action="REQUEST_TOOL",
            speech_claims_success=True,
            grounded_success=False,
            expectation_met=False,
        ),
    ]

    score = score_records(records)

    assert score["cross_channel_contradiction_rate"] == 0.5
    assert score["intent_action_divergence_rate"] == 0.0
    assert score["unsupported_success_claim_rate"] == 0.5
    assert score["expectation_failure_rate"] == 0.5
    assert score["execution_success_rate"] == 0.5


def test_pair_is_non_scientific_and_preserves_field_revision() -> None:
    timestamp = "2026-08-12T12:00:00+00:00"
    control = _payload(
        "control",
        [
            _record(
                occurred_at=timestamp,
                intended_action="OBSERVE",
                speech_action="REQUEST_TOOL",
                action="OBSERVE",
                speech_claims_success=False,
                grounded_success=True,
                expectation_met=True,
            )
        ],
    )
    treatment = _payload(
        "treatment",
        [
            _record(
                occurred_at=timestamp,
                intended_action="OBSERVE",
                speech_action="OBSERVE",
                action="OBSERVE",
                speech_claims_success=False,
                grounded_success=True,
                expectation_met=True,
            )
        ],
    )

    result = run_pair(control, treatment, field_sha=FIELD_SHA)

    assert result["phase"] == "live-contract-smoke"
    assert result["scientific_claim_allowed"] is False
    assert result["field_revision"] == FIELD_SHA
    assert result["delta_treatment_minus_control"]["cross_channel_contradiction_rate"] == -1.0


def test_pair_rejects_unpaired_agent_time_sequences() -> None:
    control = _payload(
        "control",
        [
            _record(
                occurred_at="2026-08-12T12:00:00+00:00",
                intended_action="OBSERVE",
                speech_action="OBSERVE",
                action="OBSERVE",
                speech_claims_success=False,
                grounded_success=True,
                expectation_met=True,
            )
        ],
    )
    treatment = _payload(
        "treatment",
        [
            _record(
                occurred_at="2026-08-12T12:00:02+00:00",
                intended_action="OBSERVE",
                speech_action="OBSERVE",
                action="OBSERVE",
                speech_claims_success=False,
                grounded_success=True,
                expectation_met=True,
            )
        ],
    )

    try:
        run_pair(control, treatment, field_sha=FIELD_SHA)
    except ValueError as exc:
        assert "not paired by agent/time" in str(exc)
    else:
        raise AssertionError("unpaired records should be rejected")
