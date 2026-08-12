import copy
import json
from pathlib import Path

import pytest

from experiments.piano_society.phase3 import (
    _board_digest,
    config_digest,
    expected_outcome,
)
from experiments.piano_society.phase4_authority_v2 import (
    analyze,
    materialize_authority_roles,
    scientific_projection_digest,
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


def test_phase4_v2_is_transport_only_and_locked() -> None:
    config = _config()
    normalized = validate_config(config)

    assert config["preregistration_revision"] == "glm5.2-authority-provenance-v2-transport"
    assert normalized["field_revision"] == "e877bf03dbf6681ce7cbd98d984e73c032e911aa"
    assert normalized["scientific_projection_digest"] == (
        "8b197ce8a3a57260e7215974be66be8fb7558465336aa2420838751c9804fd24"
    )
    assert scientific_projection_digest(config) == normalized["scientific_projection_digest"]
    assert config["transport_amendment"]["v1_complete_scientific_artifacts"] == 0
    assert config["transport_amendment"]["scientific_user_prompts_unchanged"] is True
    assert config["model_backend"]["max_attempts"] == 12
    assert config["model_backend"]["contract_retry_prompt_hardening"] is True
    assert config["model_backend"]["unique_request_id_per_attempt"] is True
    assert len(normalized["roles"]) == 60


def test_phase4_v2_rejects_scientific_or_transport_drift() -> None:
    config = _config()

    scientific_drift = copy.deepcopy(config)
    scientific_drift["joint_cases"][0]["case_seed"] = 9999
    with pytest.raises(ValueError, match="scientific design"):
        validate_config(scientific_drift)

    transport_drift = copy.deepcopy(config)
    transport_drift["model_backend"]["max_attempts"] = 8
    with pytest.raises(ValueError, match="provider transport"):
        validate_config(transport_drift)


def test_phase4_v2_analyzer_retains_frozen_primary_gate() -> None:
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
    assert result["phase4_v1_transport_invalidated"] is True
    assert result["advance_to_phase5_institutional_memory"] is True
