import json
from pathlib import Path

import pytest

from experiments.piano_society.phase3 import _board_digest, analyze, materialize_roles, validate_config


def _config() -> dict[str, object]:
    return json.loads(Path("experiments/piano_society/phase3_config.json").read_text())


def _wrong_action(expected: str, agent_index: int) -> str:
    alternatives = {
        "OBSERVE": ("SLEEP", "REQUEST_TOOL"),
        "SLEEP": ("OBSERVE", "REQUEST_TOOL"),
        "REQUEST_TOOL": ("OBSERVE", "SLEEP"),
    }[expected]
    return alternatives[agent_index % 2]


def _status(action: str) -> str:
    return "rejected" if action == "REQUEST_TOOL" else "succeeded"


def _record(arm: str, role: dict[str, object]) -> dict[str, object]:
    expected = str(role["expected_action"])
    agent_index = int(role["agent_index"])
    if arm == "decentralized":
        action = _wrong_action(expected, agent_index)
        speech_action = _wrong_action(expected, agent_index + 1)
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
        "agent_index": agent_index,
        "pair_index": role["pair_index"],
        "expected_action": expected,
        "expected_outcome_status": role["expected_outcome_status"],
        "peer_board_digest": "0" * 64,
        "piano_step": {
            "schema": "resonance-field-piano-step-v0.1",
            "agent_id": f"00000000-0000-0000-0000-{agent_index:012d}",
            "occurred_at": "2026-08-12T12:00:00+00:00",
            "intention": f"Execute {expected} as assigned.",
            "speech": f"Agent {agent_index} announces {speech_action}.",
            "intended_action": expected,
            "speech_action": speech_action,
            "speech_claims_success": False,
            "action": action,
            "action_payload": {},
            "expected_outcome_status": None,
            "expected_effects": {},
            "acknowledgement": {
                "action_request_id": "00000000-0000-0000-0000-000000000101",
                "correlation_id": "00000000-0000-0000-0000-000000000102",
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


def test_phase3_lock_materializes_balanced_ten_agent_cases() -> None:
    config = _config()
    normalized = validate_config(config)
    roles = materialize_roles(config)

    assert normalized["field_revision"] == "cc8dbcedf6366f687c9acc7050b5654c1867bd8e"
    assert len(normalized["joint_case_ids"]) == 6
    assert len(roles) == 60
    assert sum(role["expected_action"] == "OBSERVE" for role in roles) == 20
    assert sum(role["expected_action"] == "SLEEP" for role in roles) == 20
    assert sum(role["expected_action"] == "REQUEST_TOOL" for role in roles) == 20


def test_phase3_mechanical_social_analysis_can_pass_registered_gate() -> None:
    config = _config()
    result = analyze(config, _payload(config, "decentralized"), _payload(config, "piano"))

    assert result["scientific_interpretation_eligible"] is True
    assert result["validated_prerequisites_bound"] is True
    delta = result["delta_piano_minus_decentralized"]
    assert delta["dyad_failure_rate"] == -1.0
    assert delta["agent_role_failure_rate"] == -1.0
    assert delta["joint_case_completion_rate"] == 1.0
    assert delta["cross_channel_contradiction_rate"] == -1.0
    assert delta["outcome_report_mismatch_rate"] == 0.0
    assert result["primary_exact_sign_tests"]["dyad_failure_rate"]["p_value_two_sided"] < 0.05
    assert result["primary_exact_sign_tests"]["agent_role_failure_rate"]["p_value_two_sided"] < 0.05
    assert result["advance_to_phase4_institutions"] is True


def test_phase3_rejects_peer_board_tampering() -> None:
    config = _config()
    decentralized = _payload(config, "decentralized")
    piano = _payload(config, "piano")
    piano["records"][0]["peer_board_digest"] = "f" * 64

    with pytest.raises(ValueError, match="peer board"):
        analyze(config, decentralized, piano)
