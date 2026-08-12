"""Phase-3 v2 analysis: identical social science, provider-robustness amendment."""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from experiments.piano_society.phase3 import (
    _agent_failure,
    _exact_sign_test,
    _records,
    _score,
    _social_units,
    _validate_boards,
    config_digest,
    materialize_roles,
)

_CONFIG_EXPERIMENT = "piano-society-runtime-v0-phase3-social"
_REVISION = "glm5.2-social-dyads-v2-provider-robustness"
_PHASE2B_DIGEST = "sha256:6fdc5d0ddf1aa693c81801b78aae4f71f4807215d27960d19bbc9d2c0b62a7e2"
_PHASE2C_DIGEST = "sha256:f330a4d5153327a3bca37ea9e30ab8fd7eb3f167f0cb474f708ef0e4fc5a698b"
_FIELD_SHA = "c16d5ffd8fc8543eff0e401ddcdbca2b6bfb6ecd"
_V1_WORLD_SHA = "7f6868aa01fdef0a28103ee33a2639a5256c757e"


def _mapping(value: object, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} must be an object")
    return value


def validate_config(config: Mapping[str, Any]) -> dict[str, Any]:
    if config.get("experiment") != _CONFIG_EXPERIMENT:
        raise ValueError("unsupported Phase-3 v2 experiment identifier")
    if config.get("preregistration_revision") != _REVISION:
        raise ValueError("unexpected Phase-3 v2 preregistration revision")
    if config.get("campaign_locked") is not True:
        raise ValueError("Phase-3 v2 campaign must be locked")
    if config.get("field_revision") != _FIELD_SHA:
        raise ValueError("Phase-3 v2 Field revision differs from lock")
    if config.get("required_model_snapshot") != "glm-5.2":
        raise ValueError("Phase-3 v2 model must be glm-5.2")
    if config.get("agent_count") != 10 or config.get("pair_count") != 5:
        raise ValueError("Phase-3 v2 requires ten agents arranged as five dyads")
    if config.get("calls_per_agent") != 4:
        raise ValueError("Phase-3 v2 requires four logical calls per agent")
    if config.get("max_output_tokens_per_call") != 128:
        raise ValueError("Phase-3 v2 output limit must remain 128")
    if config.get("action_vocabulary") != ["OBSERVE", "REQUEST_TOOL", "SLEEP"]:
        raise ValueError("Phase-3 v2 action vocabulary differs from v1")
    if config.get("arms") != ["decentralized", "piano"]:
        raise ValueError("Phase-3 v2 arms differ from v1")

    prereq = _mapping(config.get("validated_prerequisites"), "validated_prerequisites")
    if prereq.get("acknowledgement_validated") is not True:
        raise ValueError("Phase-3 v2 requires validated acknowledgement")
    if prereq.get("controller_broadcast_validated") is not True:
        raise ValueError("Phase-3 v2 requires validated controller broadcast")
    if prereq.get("phase2b_artifact_digest") != _PHASE2B_DIGEST:
        raise ValueError("unexpected Phase-2B artifact binding")
    if prereq.get("phase2c_artifact_digest") != _PHASE2C_DIGEST:
        raise ValueError("unexpected Phase-2C artifact binding")

    invalidation = _mapping(config.get("v1_invalidation_record"), "v1_invalidation_record")
    if invalidation.get("world_revision") != _V1_WORLD_SHA:
        raise ValueError("Phase-3 v2 must bind the invalid v1 World revision")
    if invalidation.get("workflow_run") != 31624267333:
        raise ValueError("Phase-3 v2 must bind the invalid v1 workflow run")
    if invalidation.get("complete_artifact_generated") is not False:
        raise ValueError("v1 invalidation record must state no complete artifact")
    if invalidation.get("scientific_scoring_performed") is not False:
        raise ValueError("v1 invalidation record must state no scientific scoring")

    backend = _mapping(config.get("model_backend"), "model_backend")
    expected_backend = {
        "provider": "zai",
        "endpoint": "coding_chat_completions",
        "base_url": "https://api.z.ai/api/coding/paas/v4",
        "thinking": "disabled",
        "do_sample": False,
        "temperature": 0.0,
        "provider_seed_supported": False,
        "retry_timeout": True,
        "retry_contract_errors": True,
        "timeout_seconds": 60.0,
        "max_attempts": 8,
        "retry_backoff_cap_seconds": 30.0,
        "max_workers": 3,
        "arm_order": "counterbalanced_by_case_seed_parity",
        "agent_order_within_round": "ascending_agent_index",
    }
    for key, expected in expected_backend.items():
        if backend.get(key) != expected:
            raise ValueError(f"model_backend.{key} must equal {expected!r}")

    roles = materialize_roles(config)
    if config.get("required_joint_cases") != 6 or len(roles) != 60:
        raise ValueError("Phase-3 v2 requires the unchanged six cases and sixty roles")

    gate = _mapping(config.get("advancement_gate"), "advancement_gate")
    expected_gate = {
        "max_dyad_failure_delta": -0.40,
        "max_agent_role_failure_delta": -0.40,
        "min_joint_case_completion_delta": 0.50,
        "max_contradiction_delta": -0.25,
        "max_outcome_report_mismatch_delta": 0.05,
        "max_primary_sign_test_p": 0.05,
    }
    if dict(gate) != expected_gate:
        raise ValueError("Phase-3 v2 advancement gate differs from v1")

    return {
        "field_revision": _FIELD_SHA,
        "required_model_snapshot": "glm-5.2",
        "roles": roles,
        "role_map": {role["scenario_id"]: role for role in roles},
        "joint_case_ids": tuple(dict.fromkeys(role["joint_case_id"] for role in roles)),
        "calls_per_agent": 4,
        "advancement_gate": gate,
        "config_digest": config_digest(config),
    }


def analyze(
    config: Mapping[str, Any],
    decentralized_payload: Mapping[str, Any],
    piano_payload: Mapping[str, Any],
) -> dict[str, Any]:
    normalized = validate_config(config)
    decentralized = _records(
        decentralized_payload,
        arm="decentralized",
        normalized=normalized,
    )
    piano = _records(piano_payload, arm="piano", normalized=normalized)
    expected_ids = set(normalized["role_map"])
    if set(decentralized) != expected_ids or set(piano) != expected_ids:
        raise ValueError("both Phase-3 v2 arms must contain all sixty roles exactly once")
    _validate_boards(decentralized, normalized)
    _validate_boards(piano, normalized)

    decentralized_score = _score(decentralized, normalized)
    piano_score = _score(piano, normalized)
    delta = {
        key: piano_score[key] - decentralized_score[key]
        for key in decentralized_score
        if key not in {"agent_observations", "dyads", "joint_cases"}
    }

    d_dyads, _ = _social_units(decentralized, normalized)
    p_dyads, _ = _social_units(piano, normalized)
    d_agents = [
        _agent_failure(decentralized[role["scenario_id"]])
        for role in normalized["roles"]
    ]
    p_agents = [
        _agent_failure(piano[role["scenario_id"]]) for role in normalized["roles"]
    ]
    dyad_sign = _exact_sign_test(d_dyads, p_dyads)
    agent_sign = _exact_sign_test(d_agents, p_agents)

    gate = normalized["advancement_gate"]
    advance = (
        delta["dyad_failure_rate"] <= float(gate["max_dyad_failure_delta"])
        and delta["agent_role_failure_rate"] <= float(gate["max_agent_role_failure_delta"])
        and delta["joint_case_completion_rate"]
        >= float(gate["min_joint_case_completion_delta"])
        and delta["cross_channel_contradiction_rate"]
        <= float(gate["max_contradiction_delta"])
        and delta["outcome_report_mismatch_rate"]
        <= float(gate["max_outcome_report_mismatch_delta"])
        and dyad_sign["p_value_two_sided"] <= float(gate["max_primary_sign_test_p"])
        and agent_sign["p_value_two_sided"] <= float(gate["max_primary_sign_test_p"])
    )

    return {
        "experiment": _CONFIG_EXPERIMENT,
        "preregistration_revision": _REVISION,
        "phase": "ten-agent-two-round-social-coordination",
        "field_revision": normalized["field_revision"],
        "model_snapshot": normalized["required_model_snapshot"],
        "config_digest": normalized["config_digest"],
        "joint_cases": 6,
        "agents_per_case": 10,
        "dyads_per_case": 5,
        "decentralized": decentralized_score,
        "piano": piano_score,
        "delta_piano_minus_decentralized": delta,
        "primary_exact_sign_tests": {
            "dyad_failure_rate": dyad_sign,
            "agent_role_failure_rate": agent_sign,
        },
        "v1_invalid_attempts_excluded_by_preregistration": True,
        "validated_prerequisites_bound": True,
        "scientific_interpretation_eligible": True,
        "advance_to_phase4_institutions": advance,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--decentralized")
    parser.add_argument("--piano")
    parser.add_argument("--output")
    args = parser.parse_args()
    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    normalized = validate_config(config)
    if args.decentralized is None and args.piano is None:
        print(
            json.dumps(
                {
                    "experiment": _CONFIG_EXPERIMENT,
                    "preregistration_revision": _REVISION,
                    "campaign_locked": True,
                    "field_revision": normalized["field_revision"],
                    "model_snapshot": normalized["required_model_snapshot"],
                    "joint_cases": 6,
                    "agent_records_per_arm": 60,
                    "config_digest": normalized["config_digest"],
                },
                indent=2,
                sort_keys=True,
            )
        )
        return
    if args.decentralized is None or args.piano is None:
        raise ValueError("both Phase-3 v2 arm payloads are required")
    decentralized_payload = json.loads(Path(args.decentralized).read_text(encoding="utf-8"))
    piano_payload = json.loads(Path(args.piano).read_text(encoding="utf-8"))
    result = analyze(config, decentralized_payload, piano_payload)
    encoded = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        Path(args.output).write_text(encoded, encoding="utf-8")
    else:
        print(encoded, end="")


if __name__ == "__main__":
    main()
