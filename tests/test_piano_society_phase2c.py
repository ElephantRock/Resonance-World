import json
from pathlib import Path

from experiments.piano_society.phase2c import analyze, materialize_cases, validate_config


def _config() -> dict[str, object]:
    return json.loads(Path("experiments/piano_society/phase2c_config.json").read_text())


def _local_alternatives(expected: str) -> tuple[str, str]:
    return {
        "OBSERVE": ("SLEEP", "REQUEST_TOOL"),
        "SLEEP": ("OBSERVE", "REQUEST_TOOL"),
        "REQUEST_TOOL": ("OBSERVE", "SLEEP"),
    }[expected]


def _record(arm: str, case: dict[str, object]) -> dict[str, object]:
    expected = str(case["expected_action"])
    expected_status = str(case["expected_outcome_status"])
    speech_alt, action_alt = _local_alternatives(expected)
    if arm == "baseline":
        speech_action = speech_alt
        action = action_alt
        outcome_status = "rejected" if action == "REQUEST_TOOL" else "succeeded"
    else:
        speech_action = expected
        action = expected
        outcome_status = expected_status
    grounded = outcome_status == "succeeded"

    return {
        "schema": "resonance-field-piano-phase2-intention-stress-step-v0.1",
        "arm": arm,
        "trial_seed": case["trial_seed"],
        "model_snapshot": "glm-5.2",
        "scenario_id": case["case_id"],
        "expected_action": expected,
        "expected_outcome_status": expected_status,
        "piano_step": {
            "schema": "resonance-field-piano-step-v0.1",
            "agent_id": "00000000-0000-0000-0000-000000000011",
            "occurred_at": "2026-08-12T12:00:00+00:00",
            "intention": "Follow the global controller decision.",
            "speech": "Synthetic fixture.",
            "intended_action": expected,
            "speech_action": speech_action,
            "speech_claims_success": False,
            "action": action,
            "action_payload": {},
            "expected_outcome_status": None,
            "expected_effects": {},
            "acknowledgement": {
                "action_request_id": "00000000-0000-0000-0000-000000000012",
                "correlation_id": "00000000-0000-0000-0000-000000000013",
                "policy_result": "reject" if outcome_status == "rejected" else "allow",
                "outcome_status": outcome_status,
                "expectation_met": None,
                "grounded_success": grounded,
                "output_trace_ids": [],
                "error": None,
            },
        },
        "post_action_report": "Synthetic audited report.",
        "post_action_claims_success": grounded,
        "usage": {
            "calls": 4,
            "input_tokens": 100,
            "output_tokens": 20,
            "latency_ms": 10.0,
        },
    }


def _payload(config: dict[str, object], arm: str) -> dict[str, object]:
    normalized = validate_config(config)
    return {
        "schema": "resonance-world-piano-phase2c-intention-stress-arm-v0.1",
        "arm": arm,
        "field_revision": normalized["field_revision"],
        "config_digest": normalized["config_digest"],
        "records": [_record(arm, case) for case in materialize_cases(config)],
    }


def test_repository_phase2c_lock_materializes_36_unique_cases() -> None:
    config = _config()
    normalized = validate_config(config)
    cases = materialize_cases(config)

    assert normalized["field_revision"] == "f9ce80dd51cc3bd3adf9b810972f832263b3fe87"
    assert normalized["required_model_snapshot"] == "glm-5.2"
    assert normalized["required_pairs"] == 36
    assert len({case["case_id"] for case in cases}) == 36
    assert [case["trial_seed"] for case in cases] == list(range(5001, 5037))


def test_phase2c_analysis_can_pass_only_with_coordination_and_utility_gain() -> None:
    config = _config()
    result = analyze(config, _payload(config, "baseline"), _payload(config, "broadcast"))

    assert result["scientific_interpretation_eligible"] is True
    assert result["acknowledgement_prerequisite_validated"] is True
    assert result["paired_cases"] == 36
    delta = result["delta_broadcast_minus_baseline"]
    assert delta["cross_channel_contradiction_rate"] == -1.0
    assert delta["intent_action_divergence_rate"] == -1.0
    assert delta["task_success_rate"] == 1.0
    assert delta["outcome_report_mismatch_rate"] == 0.0
    sign_tests = result["primary_exact_sign_tests"]
    assert sign_tests["cross_channel_contradiction_rate"]["p_value_two_sided"] < 0.05
    assert sign_tests["intent_action_divergence_rate"]["p_value_two_sided"] < 0.05
    assert result["advance_to_10_agents"] is True
