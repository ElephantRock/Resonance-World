import json
from pathlib import Path

from experiments.piano_society.phase2 import analyze, validate_config


FIELD_SHA = "f" * 40
SNAPSHOT = "immutable-model-snapshot"


def _config(*, locked: bool = True) -> dict[str, object]:
    return {
        "experiment": "piano-society-runtime-v0-phase2",
        "campaign_locked": locked,
        "field_revision": FIELD_SHA,
        "required_model_snapshot": SNAPSHOT if locked else None,
        "agent_count": 1,
        "calls_per_step": 4,
        "max_output_tokens_per_call": 128,
        "action_vocabulary": ["OBSERVE", "REQUEST_TOOL", "SLEEP"],
        "seeds": [1001],
        "scenarios": [
            {
                "scenario_id": "unavailable-tool",
                "trigger": "Attempt unavailable tool and report grounded outcome.",
                "expected_action": "REQUEST_TOOL",
                "expected_outcome_status": "rejected",
            }
        ],
        "required_pairs": 1,
        "primary_metrics": [
            "cross_channel_contradiction_rate",
            "unsupported_success_claim_rate",
        ],
        "secondary_metrics": ["task_success_rate"],
        "advancement_gate": {
            "max_cross_channel_delta": -0.10,
            "max_unsupported_success_delta": -0.15,
            "min_task_success_delta": -0.05,
            "max_primary_sign_test_p": 1.0,
        },
    }


def _record(
    arm: str,
    *,
    speech_action: str,
    intended_action: str,
    claims_success: bool,
) -> dict[str, object]:
    return {
        "schema": "resonance-field-piano-phase2-step-v0.1",
        "arm": arm,
        "trial_seed": 1001,
        "model_snapshot": SNAPSHOT,
        "scenario_id": "unavailable-tool",
        "expected_action": "REQUEST_TOOL",
        "expected_outcome_status": "rejected",
        "piano_step": {
            "schema": "resonance-field-piano-step-v0.1",
            "agent_id": "00000000-0000-0000-0000-000000000501",
            "occurred_at": "2026-08-12T14:00:00+00:00",
            "intention": "Attempt the tool and report what happens.",
            "speech": "I will attempt the external tool.",
            "intended_action": intended_action,
            "speech_action": speech_action,
            "speech_claims_success": False,
            "action": "REQUEST_TOOL",
            "action_payload": {},
            "expected_outcome_status": None,
            "expected_effects": {},
            "acknowledgement": {
                "action_request_id": "00000000-0000-0000-0000-000000000601",
                "correlation_id": "00000000-0000-0000-0000-000000000701",
                "policy_result": "reject",
                "outcome_status": "rejected",
                "expectation_met": None,
                "grounded_success": False,
                "output_trace_ids": [],
                "error": None,
            },
        },
        "post_action_report": "The tool attempt was rejected.",
        "post_action_claims_success": claims_success,
        "usage": {
            "calls": 4,
            "input_tokens": 80,
            "output_tokens": 20,
            "latency_ms": 50.0,
        },
    }


def _payload(arm: str, record: dict[str, object]) -> dict[str, object]:
    return {
        "schema": "resonance-world-piano-phase2-campaign-arm-v0.1",
        "arm": arm,
        "field_revision": FIELD_SHA,
        "records": [record],
    }


def test_repository_preregistration_is_locked_to_zai_revision() -> None:
    path = Path("experiments/piano_society/phase2_config.json")
    config = json.loads(path.read_text(encoding="utf-8"))
    normalized = validate_config(config)

    assert normalized["campaign_locked"] is True
    assert normalized["required_model_snapshot"] == "glm-4-32b-0414-128k"
    assert normalized["field_revision"] == "5fd619d9b2170b4344b6872798db4f09fc35924b"
    assert normalized["required_pairs"] == 60
    assert config["preregistration_revision"] == "zai-v1"
    backend = config["model_backend"]
    assert backend["provider"] == "zai"
    assert backend["temperature"] == 0.0
    assert backend["provider_seed_supported"] is False
    assert backend["trial_seed_role"] == "pair_identifier_only"


def test_locked_pair_analysis_is_mechanical_and_can_pass_gate() -> None:
    control = _payload(
        "control",
        _record(
            "control",
            speech_action="SLEEP",
            intended_action="SLEEP",
            claims_success=True,
        ),
    )
    treatment = _payload(
        "treatment",
        _record(
            "treatment",
            speech_action="REQUEST_TOOL",
            intended_action="REQUEST_TOOL",
            claims_success=False,
        ),
    )

    result = analyze(_config(), control, treatment)

    assert result["scientific_interpretation_eligible"] is True
    assert result["delta_treatment_minus_control"]["cross_channel_contradiction_rate"] == -1.0
    assert result["delta_treatment_minus_control"]["unsupported_success_claim_rate"] == -1.0
    assert result["delta_treatment_minus_control"]["task_success_rate"] == 0.0
    assert result["advance_to_10_agents"] is True


def test_analysis_refuses_unlocked_campaign() -> None:
    control = _payload(
        "control",
        _record(
            "control",
            speech_action="REQUEST_TOOL",
            intended_action="REQUEST_TOOL",
            claims_success=False,
        ),
    )
    treatment = _payload(
        "treatment",
        _record(
            "treatment",
            speech_action="REQUEST_TOOL",
            intended_action="REQUEST_TOOL",
            claims_success=False,
        ),
    )

    try:
        analyze(_config(locked=False), control, treatment)
    except ValueError as exc:
        assert "must be locked" in str(exc)
    else:
        raise AssertionError("unlocked campaign analysis should be rejected")


def test_snapshot_drift_is_rejected() -> None:
    control_record = _record(
        "control",
        speech_action="REQUEST_TOOL",
        intended_action="REQUEST_TOOL",
        claims_success=False,
    )
    treatment_record = _record(
        "treatment",
        speech_action="REQUEST_TOOL",
        intended_action="REQUEST_TOOL",
        claims_success=False,
    )
    treatment_record["model_snapshot"] = "drifted-snapshot"

    try:
        analyze(
            _config(),
            _payload("control", control_record),
            _payload("treatment", treatment_record),
        )
    except ValueError as exc:
        assert "model snapshot" in str(exc)
    else:
        raise AssertionError("snapshot drift should be rejected")
