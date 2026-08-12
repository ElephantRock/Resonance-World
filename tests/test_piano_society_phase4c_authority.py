import copy
import json
import re
from collections import Counter
from pathlib import Path

import pytest

from experiments.piano_society.phase3 import _board_digest, config_digest, expected_outcome
from experiments.piano_society.phase4c_authority import (
    analyze,
    materialize_roles,
    validate_config,
)


def _config() -> dict[str, object]:
    return json.loads(Path("experiments/piano_society/phase4c_authority_config.json").read_text())


def _record(role, *, arm: str, follow_spoof: bool, board_digest: str):
    action = role["spoof_action"] if follow_spoof else role["expected_action"]
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
        "usage": {
            "calls": 4,
            "input_tokens": 40,
            "output_tokens": 20,
            "latency_ms": 4.0,
        },
    }


def _payload(config, roles, *, arm: str, follow_spoof: bool):
    records = []
    for case_id in dict.fromkeys(role["joint_case_id"] for role in roles):
        case_roles = [role for role in roles if role["joint_case_id"] == case_id]
        board = []
        for role in case_roles:
            action = role["spoof_action"] if follow_spoof else role["expected_action"]
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
            _record(role, arm=arm, follow_spoof=follow_spoof, board_digest=digest)
            for role in case_roles
        )
    return {
        "schema": "resonance-world-piano-phase4-authority-arm-v0.1",
        "arm": arm,
        "field_revision": config["field_revision"],
        "config_digest": config_digest(config),
        "records": records,
    }


def test_phase4c_lock_removes_model_visible_answer_key_cues() -> None:
    config = _config()
    normalized = validate_config(config)
    roles = normalized["roles"]

    assert len(roles) == 60
    ids = []
    for role in roles:
        assert set(role["allowed_actions"]) == {
            role["expected_action"],
            role["spoof_action"],
        }
        for key in ("legitimate_notice_id", "spoof_notice_id"):
            notice_id = role[key]
            assert re.fullmatch(r"notice-[0-9a-f]{24}", notice_id)
            lowered = notice_id.lower()
            assert all(
                token not in lowered
                for token in config["institutional_authority"][
                    "forbidden_model_visible_id_tokens"
                ]
            )
            ids.append(notice_id)
    assert len(ids) == len(set(ids)) == 120
    assert Counter(role["allowed_action_order"] for role in roles) == Counter(
        {"expected_first": 30, "spoof_first": 30}
    )
    assert Counter(role["legitimate_slot"] for role in roles) == Counter(
        {"slot_a": 30, "slot_b": 30}
    )
    assert Counter(role["notice_order"] for role in roles) == Counter(
        {"legitimate_first": 30, "spoof_first": 30}
    )
    cross = Counter(
        (role["notice_order"], role["legitimate_slot"])
        for role in roles
    )
    assert set(cross.values()) == {15}
    triple = Counter(
        (
            role["notice_order"],
            role["legitimate_slot"],
            role["allowed_action_order"],
        )
        for role in roles
    )
    assert sorted(triple.values()) == [7, 7, 7, 7, 8, 8, 8, 8]


def test_phase4c_rejects_correction_or_presentation_drift() -> None:
    config = _config()

    correction_drift = copy.deepcopy(config)
    correction_drift["methodological_correction"]["prior_runs_invalidated"] = False
    with pytest.raises(ValueError, match="methodological-correction"):
        validate_config(correction_drift)

    order_drift = copy.deepcopy(config)
    order_drift["institutional_authority"]["allowed_action_order_rule"] = "expected_first"
    with pytest.raises(ValueError, match="allowed_action_order_rule"):
        validate_config(order_drift)


def test_phase4c_analyzer_retains_original_advancement_gate() -> None:
    config = _config()
    roles = materialize_roles(config)
    unsigned = _payload(config, roles, arm="unsigned", follow_spoof=True)
    attested = _payload(config, roles, arm="attested", follow_spoof=False)

    result = analyze(config, unsigned, attested)

    assert result["unsigned"]["agent_role_failure_rate"] == 1.0
    assert result["unsigned"]["spoof_capture_rate"] == 1.0
    assert result["attested"]["agent_role_failure_rate"] == 0.0
    assert result["attested"]["spoof_capture_rate"] == 0.0
    assert result["delta_attested_minus_unsigned"]["agent_role_failure_rate"] == -1.0
    assert result["delta_attested_minus_unsigned"]["spoof_capture_rate"] == -1.0
    assert result["primary_exact_sign_tests"]["agent_role_failure_rate"]["discordant_units"] == 60
    assert result["primary_exact_sign_tests"]["spoof_capture_rate"]["discordant_units"] == 60
    assert result["prior_authority_runs_methodologically_invalidated"] is True
    assert result["advance_to_phase5_institutional_memory"] is True
