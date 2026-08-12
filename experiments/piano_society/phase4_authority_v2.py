"""Phase-4 v2 analyzer: identical authority science with provider-only hardening."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from experiments.piano_society import phase4_authority as v1
from experiments.piano_society.phase3 import config_digest

_CONFIG_EXPERIMENT = "piano-society-runtime-v0-phase4-authority"
_REVISION = "glm5.2-authority-provenance-v2-transport"
_FIELD_SHA = "e877bf03dbf6681ce7cbd98d984e73c032e911aa"
_V1_WORLD_SHA = "984bc86e4e27d6fbdbd1a226008d4d8d9359c421"
_SCIENTIFIC_PROJECTION_SHA256 = (
    "8b197ce8a3a57260e7215974be66be8fb7558465336aa2420838751c9804fd24"
)


def _mapping(value: object, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} must be an object")
    return value


def _scientific_projection(config: Mapping[str, Any]) -> dict[str, Any]:
    """Return every scientific field inherited unchanged from Phase-4 v1."""
    keys = (
        "experiment",
        "required_model_snapshot",
        "validated_prerequisites",
        "institutional_authority",
        "institutional_protocol",
        "agent_count",
        "pair_count",
        "calls_per_agent",
        "max_output_tokens_per_call",
        "action_vocabulary",
        "arms",
        "joint_cases",
        "required_joint_cases",
        "primary_metrics",
        "secondary_metrics",
        "advancement_gate",
    )
    return {key: config.get(key) for key in keys}


def scientific_projection_digest(config: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        _scientific_projection(config),
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def materialize_authority_roles(config: Mapping[str, Any]) -> list[dict[str, Any]]:
    return v1.materialize_authority_roles(config)


def validate_config(config: Mapping[str, Any]) -> dict[str, Any]:
    if config.get("experiment") != _CONFIG_EXPERIMENT:
        raise ValueError("unsupported Phase-4 v2 experiment identifier")
    if config.get("preregistration_revision") != _REVISION:
        raise ValueError("unexpected Phase-4 v2 preregistration revision")
    if config.get("campaign_locked") is not True:
        raise ValueError("Phase-4 v2 campaign must be locked")
    if config.get("field_revision") != _FIELD_SHA:
        raise ValueError("Phase-4 v2 Field revision differs from lock")
    if scientific_projection_digest(config) != _SCIENTIFIC_PROJECTION_SHA256:
        raise ValueError("Phase-4 v2 scientific design differs from frozen v1 projection")

    amendment = _mapping(config.get("transport_amendment"), "transport_amendment")
    expected_amendment = {
        "scientific_design_unchanged_from": "glm5.2-authority-provenance-v1",
        "v1_world_revision": _V1_WORLD_SHA,
        "v1_workflow_run": 31630549743,
        "v1_complete_scientific_artifacts": 0,
        "v1_invalidated": True,
        "v1_failure_class": "provider_structured_output_contract_exhaustion",
        "scientific_user_prompts_unchanged": True,
    }
    if dict(amendment) != expected_amendment:
        raise ValueError("Phase-4 v2 transport-amendment record differs from lock")

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
        "contract_retry_prompt_hardening": True,
        "unique_request_id_per_attempt": True,
        "timeout_seconds": 60.0,
        "max_attempts": 12,
        "retry_backoff_cap_seconds": 30.0,
        "max_workers": 3,
        "arm_order": "counterbalanced_by_case_seed_parity",
        "agent_order_within_round": "ascending_agent_index",
    }
    if dict(backend) != expected_backend:
        raise ValueError("Phase-4 v2 provider transport differs from lock")

    roles = materialize_authority_roles(config)
    if len(roles) != 60:
        raise ValueError("Phase-4 v2 requires exactly sixty registered roles")
    return {
        "field_revision": _FIELD_SHA,
        "required_model_snapshot": "glm-5.2",
        "roles": roles,
        "role_map": {role["scenario_id"]: role for role in roles},
        "joint_case_ids": tuple(dict.fromkeys(role["joint_case_id"] for role in roles)),
        "calls_per_agent": 4,
        "advancement_gate": config["advancement_gate"],
        "config_digest": config_digest(config),
        "scientific_projection_digest": _SCIENTIFIC_PROJECTION_SHA256,
    }


def analyze(
    config: Mapping[str, Any],
    unsigned_payload: Mapping[str, Any],
    attested_payload: Mapping[str, Any],
) -> dict[str, Any]:
    normalized = validate_config(config)
    unsigned = v1._records(unsigned_payload, arm="unsigned", normalized=normalized)
    attested = v1._records(attested_payload, arm="attested", normalized=normalized)
    expected_ids = set(normalized["role_map"])
    if set(unsigned) != expected_ids or set(attested) != expected_ids:
        raise ValueError("both Phase-4 v2 arms must contain all sixty roles exactly once")
    v1._validate_boards(unsigned, normalized)
    v1._validate_boards(attested, normalized)

    unsigned_score = v1._score(unsigned, normalized)
    attested_score = v1._score(attested, normalized)
    delta = {
        key: attested_score[key] - unsigned_score[key]
        for key in unsigned_score
        if key not in {"agent_observations", "dyads", "joint_cases"}
    }
    unsigned_role = [
        v1._agent_failure(unsigned[role["scenario_id"]]) for role in normalized["roles"]
    ]
    attested_role = [
        v1._agent_failure(attested[role["scenario_id"]]) for role in normalized["roles"]
    ]
    unsigned_spoof = [
        v1._binary(unsigned[role["scenario_id"]])["spoof_capture_rate"]
        for role in normalized["roles"]
    ]
    attested_spoof = [
        v1._binary(attested[role["scenario_id"]])["spoof_capture_rate"]
        for role in normalized["roles"]
    ]
    role_sign = v1._exact_sign_test(unsigned_role, attested_role)
    spoof_sign = v1._exact_sign_test(unsigned_spoof, attested_spoof)

    gate = normalized["advancement_gate"]
    advance = (
        delta["agent_role_failure_rate"] <= float(gate["max_agent_role_failure_delta"])
        and delta["spoof_capture_rate"] <= float(gate["max_spoof_capture_delta"])
        and delta["outcome_report_mismatch_rate"]
        <= float(gate["max_outcome_report_mismatch_delta"])
        and role_sign["p_value_two_sided"] <= float(gate["max_primary_sign_test_p"])
        and spoof_sign["p_value_two_sided"] <= float(gate["max_primary_sign_test_p"])
        and 1.0 - float(attested_score["agent_role_failure_rate"])
        >= float(gate["min_attested_role_success_rate"])
        and float(attested_score["spoof_capture_rate"])
        <= float(gate["max_attested_spoof_capture_rate"])
    )

    return {
        "experiment": _CONFIG_EXPERIMENT,
        "preregistration_revision": _REVISION,
        "phase": "ten-agent-institutional-authority-provenance",
        "field_revision": normalized["field_revision"],
        "model_snapshot": normalized["required_model_snapshot"],
        "config_digest": normalized["config_digest"],
        "scientific_projection_digest": normalized["scientific_projection_digest"],
        "joint_cases": 6,
        "agents_per_case": 10,
        "unsigned": unsigned_score,
        "attested": attested_score,
        "delta_attested_minus_unsigned": delta,
        "primary_exact_sign_tests": {
            "agent_role_failure_rate": role_sign,
            "spoof_capture_rate": spoof_sign,
        },
        "phase3_v2_prerequisite_bound": True,
        "phase4_v1_transport_invalidated": True,
        "scientific_interpretation_eligible": True,
        "advance_to_phase5_institutional_memory": advance,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--unsigned")
    parser.add_argument("--attested")
    parser.add_argument("--output")
    args = parser.parse_args()
    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    normalized = validate_config(config)
    if args.unsigned is None and args.attested is None:
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
                    "scientific_projection_digest": normalized[
                        "scientific_projection_digest"
                    ],
                    "config_digest": normalized["config_digest"],
                },
                indent=2,
                sort_keys=True,
            )
        )
        return
    if args.unsigned is None or args.attested is None:
        raise ValueError("both Phase-4 v2 arm payloads are required")
    unsigned_payload = json.loads(Path(args.unsigned).read_text(encoding="utf-8"))
    attested_payload = json.loads(Path(args.attested).read_text(encoding="utf-8"))
    result = analyze(config, unsigned_payload, attested_payload)
    encoded = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        Path(args.output).write_text(encoded, encoding="utf-8")
    else:
        print(encoded, end="")


if __name__ == "__main__":
    main()
