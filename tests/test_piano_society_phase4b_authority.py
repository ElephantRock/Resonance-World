import copy
import json
from collections import Counter
from pathlib import Path

import pytest

from experiments.piano_society.phase3 import _board_digest, config_digest, expected_outcome
from experiments.piano_society.phase4b_authority import analyze, materialize_roles, validate_config


def _config() -> dict[str, object]:
    return json.loads(Path("experiments/piano_society/phase4b_authority_config.json").read_text())


def _record(role, *, arm: str, use_spoof: bool, board_digest: str):
    action = role["spoof_action"] if use_spoof else role["expected_action"]
    outcome = expected_outcome(action)
    grounded = outcome == "succeeded"
    return {
        "schema": "resonance-field-piano-phase4-authority-step-v0.1",
        "arm": arm,
        "trial_seed": role["trial_seed"],
        "model_snapshot": "glm-5.2",
        "scenario_id": role["scenario_id"],
        "agent_index": role["agent_index"],
        "pair_index": role["pair_index"],
        "expected_action": role["expected_action"],
        "expected_outcome_status": role["expected_outcome_status"],
        "legitimate_notice_id": role["legitimate_notice_id"],
        "spoof_notice_id": role["spoof_notice_id"],
        "spoof_action": role["spoof_action"],
        "authority_grant_digest": role["authority_grant_digest"],
        "legitimate_verified": True,
        "spoof_verified": False,
        "peer_board_digest": board_digest,
        "piano_step": {
            "schema": "resonance-field-piano-step-v0.1",
            "agent_id": f"agent-{role['agent_index']}",
            "occurred_at": "2026-08-12T12:00:00+00:00",
            "intention": f"Execute {action}.",
            "speech": f"I will execute {action}.",
            "intended_action": action,
            "speech_action": action,
            "speech_claims_success": False,
            "action": action,
            "action_payload": {},
            "expected_outcome_status": None,
            "expected_effects": {},
            "acknowledgement": {
                "action_request_id": "request",
                "correlation_id": "correlation",
                "policy_result": "allowed" if action != "REQUEST_TOOL" else "rejected",
                "outcome_status": outcome,
                "expectation_met": None,
                "grounded_success": grounded,
                "output_trace_ids": [],
                "error": None,
            },
        },
        "post_action_report": "Audited outcome reported.",
        "post_action_claims_success": grounded,
        "usage": {"calls": 4, "input_tokens": 40, "output_tokens": 20, "latency_ms": 4.0},
    }


def _payload(config, roles, *, arm: str, use_spoof: bool):
    records = []
    for case_id in dict.fromkeys(role["joint_case_id"] for role in roles):
        case_roles = [role for role in roles if role["joint_case_id"] == case_id]
        board = []
        for role in case_roles:
            action = role["spoof_action"] if use_spoof else role["expected_action"]
            board.append(
                {
                    "agent_index": role["agent_index"],
                    "pair_index": role["pair_index"],
                    "speech": f"I will execute {action}.",
                    "speech_action": action,
                }
            )
        digest = _board_digest(board)
        records.extend(
            _record(role, arm=arm, use_spoof=use_spoof, board_digest=digest)
            for role in case_roles
        )
    return {
        "schema": "resonance-world-piano-phase4-authority-arm-v0.1",
        "arm": arm,
        "field_revision": config["field_revision"],
        "config_digest": config_digest(config),
        "records": records,
    }


def test_phase4b_lock_is_fresh_balanced_binary_and_bound() -> None:
    config = _config()
    normalized = validate_config(config)
    roles = normalized["roles"]

    assert config["campaign_locked"] is True
    assert config["validated_prerequisites"]["phase4_v2_artifact_digest"] == (
        "sha256:49e8d3dce67d8319501480fa0b91bff7a3eae6ce25dd61c3fe6f436b0983f08a"
    )
    assert config["validated_prerequisites"]["phase4_v2_advance_to_phase5"] is False
    assert len(roles) == 60
    assert all(str(role["joint_case_id"]).startswith("binary-authority-") for role in roles)
    assert all(len(role["allowed_actions"]) == 2 for role in roles)
    assert all(
        set(role["allowed_actions"]) == {role["expected_action"], role["spoof_action"]}
        for role in roles
    )
    assert Counter(role["expected_action"] for role in roles) == Counter(
        {"OBSERVE": 20, "REQUEST_TOOL": 20, "SLEEP": 20}
    )
    assert Counter(role["spoof_action"] for role in roles) == Counter(
        {"OBSERVE": 20, "REQUEST_TOOL": 20, "SLEEP": 20}
    )
    assert Counter(role["notice_order"] for role in roles) == Counter(
        {"legitimate_first": 30, "spoof_first": 30}
    )
    pairs = Counter((role["expected_action"], role["spoof_action"]) for role in roles)
    assert len(pairs) == 6
    assert set(pairs.values()) == {10}


def test_phase4b_analyzer_retains_original_authority_gate() -> None:
    config = _config()
    roles = materialize_roles(config)
    unsigned = _payload(config, roles, arm="unsigned", use_spoof=True)
    attested = _payload(config, roles, arm="attested", use_spoof=False)

    result = analyze(config, unsigned, attested)

    assert result["unsigned"]["agent_role_failure_rate"] == 1.0
    assert result["unsigned"]["spoof_capture_rate"] == 1.0
    assert result["attested"]["agent_role_failure_rate"] == 0.0
    assert result["attested"]["spoof_capture_rate"] == 0.0
    assert result["delta_attested_minus_unsigned"]["agent_role_failure_rate"] == -1.0
    assert result["delta_attested_minus_unsigned"]["spoof_capture_rate"] == -1.0
    assert result["advance_to_phase5_institutional_memory"] is True


def test_phase4b_analyzer_rejects_third_action_escape() -> None:
    config = _config()
    roles = materialize_roles(config)
    unsigned = _payload(config, roles, arm="unsigned", use_spoof=True)
    attested = _payload(config, roles, arm="attested", use_spoof=False)

    tampered = copy.deepcopy(unsigned)
    record = tampered["records"][0]
    allowed = set(roles[0]["allowed_actions"])
    third = next(action for action in ("OBSERVE", "REQUEST_TOOL", "SLEEP") if action not in allowed)
    record["piano_step"]["action"] = third
    with pytest.raises(ValueError, match="escaped the registered binary action pair"):
        analyze(config, tampered, attested)
