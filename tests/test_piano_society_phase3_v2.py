import json
from pathlib import Path

from experiments.piano_society.phase3 import _board_digest, materialize_roles
from experiments.piano_society.phase3_v2 import analyze, validate_config


def _config() -> dict[str, object]:
    return json.loads(Path("experiments/piano_society/phase3_config.json").read_text())


def _wrong_action(expected: str, agent_index: int) -> str:
    choices = {
        "OBSERVE": ("SLEEP", "REQUEST_TOOL"),
        "SLEEP": ("OBSERVE", "REQUEST_TOOL"),
        "REQUEST_TOOL": ("OBSERVE", "SLEEP"),
    }[expected]
    return choices[agent_index % 2]


def _status(action: str) -> str:
    return "rejected" if action == "REQUEST_TOOL" else "succeeded"


def _record(arm: str, role: dict[str, object]) -> dict[str, object]:
    expected = str(role["expected_action"])
    index = int(role["agent_index"])
    if arm == "decentralized":
        action = _wrong_action(expected, index)
        speech_action = _wrong_action(expected, index + 1)
    else:
        action = expected
        speech_action = expected
    outcome = _status(action)
    grounded = outcome == "succeeded"
    return {
        "schema": "resonance-field-piano-phase3-social-step-v0.1",
        "arm": arm,
        "trial_seed": role["trial_seed"],
        "model_snapshot": "glm-5.2",
        "scenario_id": role["scenario_id"],
        "agent_index": index,
        "pair_index": role["pair_index"],
        "expected_action": expected,
        "expected_outcome_status": role["expected_outcome_status"],
        "peer_board_digest": "0" * 64,
        "piano_step": {
            "schema": "resonance-field-piano-step-v0.1",
            "agent_id": f"00000000-0000-0000-0000-{index:012d}",
            "occurred_at": "2026-08-12T12:00:00+00:00",
            "intention": f"Execute {expected} as assigned.",
            "speech": f"Agent {index} announces {speech_action}.",
            "intended_action": expected,
            "speech_action": speech_action,
            "speech_claims_success": False,
            "action": action,
            "action_payload": {},
            "expected_outcome_status": None,
            "expected_effects": {},
            "acknowledgement": {
                "action_request_id": "00000000-0000-0000-0000-000000000201",
                "correlation_id": "00000000-0000-0000-0000-000000000202",
                "policy_result": "reject" if outcome == "rejected" else "allow",
                "outcome_status": outcome,
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
    roles = materialize_roles(config)
    records = [_record(arm, role) for role in roles]
    for case_id in normalized["joint_case_ids"]:
        case_records = [
            record
            for record, role in zip(records, roles, strict=True)
            if role["joint_case_id"] == case_id
        ]
        board = [
            {
                "agent_index": record["agent_index"],
                "pair_index": record["pair_index"],
                "speech": record["piano_step"]["speech"],
                "speech_action": record["piano_step"]["speech_action"],
            }
            for record in case_records
        ]
        digest = _board_digest(board)
        for record in case_records:
            record["peer_board_digest"] = digest
    return {
        "schema": "resonance-world-piano-phase3-social-arm-v0.1",
        "arm": arm,
        "field_revision": normalized["field_revision"],
        "config_digest": normalized["config_digest"],
        "records": records,
    }


def test_phase3_v2_is_provider_only_amendment() -> None:
    config = _config()
    normalized = validate_config(config)

    assert config["preregistration_revision"] == "glm5.2-social-dyads-v2-provider-robustness"
    assert normalized["field_revision"] == "c16d5ffd8fc8543eff0e401ddcdbca2b6bfb6ecd"
    assert len(normalized["roles"]) == 60
    assert config["required_joint_cases"] == 6
    assert config["primary_metrics"] == ["dyad_failure_rate", "agent_role_failure_rate"]
    assert config["advancement_gate"] == {
        "max_dyad_failure_delta": -0.40,
        "max_agent_role_failure_delta": -0.40,
        "min_joint_case_completion_delta": 0.50,
        "max_contradiction_delta": -0.25,
        "max_outcome_report_mismatch_delta": 0.05,
        "max_primary_sign_test_p": 0.05,
    }
    backend = config["model_backend"]
    assert backend["retry_contract_errors"] is True
    assert backend["max_attempts"] == 8
    assert backend["retry_backoff_cap_seconds"] == 30.0
    assert backend["max_workers"] == 3
    invalidation = config["v1_invalidation_record"]
    assert invalidation["complete_artifact_generated"] is False
    assert invalidation["scientific_scoring_performed"] is False


def test_phase3_v2_mechanical_analysis_can_pass_unchanged_social_gate() -> None:
    config = _config()
    result = analyze(config, _payload(config, "decentralized"), _payload(config, "piano"))

    assert result["scientific_interpretation_eligible"] is True
    assert result["v1_invalid_attempts_excluded_by_preregistration"] is True
    delta = result["delta_piano_minus_decentralized"]
    assert delta["dyad_failure_rate"] == -1.0
    assert delta["agent_role_failure_rate"] == -1.0
    assert delta["joint_case_completion_rate"] == 1.0
    assert delta["cross_channel_contradiction_rate"] == -1.0
    assert delta["outcome_report_mismatch_rate"] == 0.0
    assert result["advance_to_phase4_institutions"] is True
