import copy
import json
from collections import Counter
from pathlib import Path

import pytest

from experiments.piano_society.phase3 import _board_digest, expected_outcome
from experiments.piano_society.phase4_authority import (
    analyze,
    config_digest,
    materialize_authority_roles,
    validate_config,
)


def _config() -> dict[str, object]:
    return json.loads(Path("experiments/piano_society/phase4_authority_config.json").read_text())


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
        board = [
            {
                "agent_index": role["agent_index"],
                "pair_index": role["pair_index"],
                "speech": (
                    f"I will execute "
                    f"{role['spoof_action'] if follow_spoof else role['expected_action']}."
                ),
                "speech_action": role["spoof_action"] if follow_spoof else role["expected_action"],
            }
            for role in case_roles
        ]
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


def test_phase4_lock_is_balanced_and_pinned() -> None:
    config = _config()
    normalized = validate_config(config)
    roles = normalized["roles"]

    assert config["campaign_locked"] is True
    assert config["field_revision"] == "fe416fe5d04d9db8e43bce7f923f522d7164cc7c"
    assert config["validated_prerequisites"]["phase3_v2_artifact_digest"] == (
        "sha256:8eb56824df7b5ccce88204cb34f4212fbdcad6025e011208183059388d049498"
    )
    assert len(roles) == 60
    assert Counter(role["spoof_action"] for role in roles) == Counter(
        {"OBSERVE": 20, "REQUEST_TOOL": 20, "SLEEP": 20}
    )
    assert Counter(role["notice_order"] for role in roles) == Counter(
        {"legitimate_first": 30, "spoof_first": 30}
    )
    pairs = Counter((role["expected_action"], role["spoof_action"]) for role in roles)
    assert len(pairs) == 6
    assert set(pairs.values()) == {10}


def test_phase4_analyzer_detects_attestation_effect_mechanically() -> None:
    config = _config()
    roles = materialize_authority_roles(config)
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
    assert result["advance_to_phase5_institutional_memory"] is True
    assert result["scientific_interpretation_eligible"] is True


def test_phase4_analyzer_rejects_authority_or_board_tampering() -> None:
    config = _config()
    roles = materialize_authority_roles(config)
    unsigned = _payload(config, roles, arm="unsigned", follow_spoof=True)
    attested = _payload(config, roles, arm="attested", follow_spoof=False)

    tampered_grant = copy.deepcopy(attested)
    tampered_grant["records"][0]["authority_grant_digest"] = "0" * 64
    with pytest.raises(ValueError, match="authority_grant_digest"):
        analyze(config, unsigned, tampered_grant)

    tampered_board = copy.deepcopy(attested)
    tampered_board["records"][0]["piano_step"]["speech"] = "Tampered public plan."
    with pytest.raises(ValueError, match="reconstructed peer board"):
        analyze(config, unsigned, tampered_board)
