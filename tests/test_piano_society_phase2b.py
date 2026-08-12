import json
from pathlib import Path

from experiments.piano_society.phase2b import analyze, materialize_cases, validate_config


def _config() -> dict[str, object]:
    return json.loads(Path("experiments/piano_society/phase2b_config.json").read_text())


def _alt(action: str) -> str:
    return {"OBSERVE": "SLEEP", "SLEEP": "OBSERVE", "REQUEST_TOOL": "OBSERVE"}[action]


def _record(arm: str, case: dict[str, object]) -> dict[str, object]:
    expected_action = str(case["expected_action"])
    expected_status = str(case["expected_outcome_status"])
    grounded = expected_status == "succeeded"

    contradiction = arm in {"baseline", "ack_only"}
    mismatch = arm in {"baseline", "intention_only"}
    speech_action = _alt(expected_action) if contradiction else expected_action
    claims_success = (not grounded) if mismatch else grounded

    return {
        "schema": "resonance-field-piano-phase2-factorial-step-v0.1",
        "arm": arm,
        "trial_seed": case["trial_seed"],
        "model_snapshot": "glm-5.2",
        "scenario_id": case["case_id"],
        "expected_action": expected_action,
        "expected_outcome_status": expected_status,
        "piano_step": {
            "schema": "resonance-field-piano-step-v0.1",
            "agent_id": "00000000-0000-0000-0000-000000000001",
            "occurred_at": "2026-08-12T12:00:00+00:00",
            "intention": "Follow the current rule.",
            "speech": "I will follow the current rule.",
            "intended_action": expected_action,
            "speech_action": speech_action,
            "speech_claims_success": False,
            "action": expected_action,
            "action_payload": {},
            "expected_outcome_status": None,
            "expected_effects": {},
            "acknowledgement": {
                "action_request_id": "00000000-0000-0000-0000-000000000002",
                "correlation_id": "00000000-0000-0000-0000-000000000003",
                "policy_result": "allow" if grounded else "reject",
                "outcome_status": expected_status,
                "expectation_met": None,
                "grounded_success": grounded,
                "output_trace_ids": [],
                "error": None,
            },
        },
        "post_action_report": "Synthetic analyzer fixture.",
        "post_action_claims_success": claims_success,
        "usage": {
            "calls": 4,
            "input_tokens": 100,
            "output_tokens": 20,
            "latency_ms": 10.0,
        },
    }


def _payloads(config: dict[str, object]) -> dict[str, dict[str, object]]:
    normalized = validate_config(config)
    digest = normalized["config_digest"]
    field_revision = normalized["field_revision"]
    cases = materialize_cases(config)
    result = {}
    for arm in ("baseline", "intention_only", "ack_only", "full"):
        result[arm] = {
            "schema": "resonance-world-piano-phase2b-factorial-arm-v0.1",
            "arm": arm,
            "field_revision": field_revision,
            "config_digest": digest,
            "records": [_record(arm, case) for case in cases],
        }
    return result


def test_repository_phase2b_lock_materializes_40_unique_cases() -> None:
    config = _config()
    normalized = validate_config(config)
    cases = materialize_cases(config)

    assert normalized["field_revision"] == "54913b4ede896589b03dae5fd1f7ee653d9e6acc"
    assert normalized["required_model_snapshot"] == "glm-5.2"
    assert normalized["required_pairs"] == 40
    assert len({case["case_id"] for case in cases}) == 40
    assert [case["trial_seed"] for case in cases] == list(range(3001, 3041))


def test_factorial_analysis_is_mechanical_and_can_pass_registered_gate() -> None:
    config = _config()
    result = analyze(config, _payloads(config))

    assert result["scientific_interpretation_eligible"] is True
    assert result["paired_cases"] == 40
    contrasts = result["contrasts"]
    assert contrasts["intention_only_minus_baseline"]["cross_channel_contradiction_rate"] == -1.0
    assert contrasts["ack_only_minus_baseline"]["outcome_report_mismatch_rate"] == -1.0
    assert contrasts["full_minus_baseline"]["cross_channel_contradiction_rate"] == -1.0
    assert contrasts["full_minus_baseline"]["outcome_report_mismatch_rate"] == -1.0
    assert result["primary_exact_sign_tests"]["intention_effect_on_contradiction"]["p_value_two_sided"] < 0.05
    assert result["primary_exact_sign_tests"]["ack_effect_on_outcome_mismatch"]["p_value_two_sided"] < 0.05
    assert result["advance_to_10_agents"] is True
