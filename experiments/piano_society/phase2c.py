"""Preregistered one-agent PIANO Phase-2C intention-broadcast analysis."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

_CONFIG_EXPERIMENT = "piano-society-runtime-v0-phase2c-intention-stress"
_PAYLOAD_SCHEMA = "resonance-world-piano-phase2c-intention-stress-arm-v0.1"
_RECORD_SCHEMA = "resonance-field-piano-phase2-intention-stress-step-v0.1"
_PIANO_SCHEMA = "resonance-field-piano-step-v0.1"
_ARMS = ("baseline", "broadcast")


def _mapping(value: object, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} must be an object")
    return value


def _sequence(value: object, name: str) -> Sequence[object]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValueError(f"{name} must be a sequence")
    return value


def _git_sha(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a Git SHA")
    if len(value) != 40 or any(char not in "0123456789abcdef" for char in value):
        raise ValueError(f"{name} must be a lowercase 40-character Git SHA")
    return value


def config_digest(config: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(config, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def materialize_cases(config: Mapping[str, Any]) -> list[dict[str, Any]]:
    templates = _sequence(config.get("scenario_templates"), "scenario_templates")
    variants = _sequence(config.get("advisory_variants"), "advisory_variants")
    seed_start = config.get("case_seed_start")
    if isinstance(seed_start, bool) or not isinstance(seed_start, int) or seed_start < 0:
        raise ValueError("case_seed_start must be a non-negative integer")

    cases: list[dict[str, Any]] = []
    seen: set[str] = set()
    index = 0
    for template_raw in templates:
        template = _mapping(template_raw, "scenario template")
        required_strings = (
            "scenario_id",
            "global_task",
            "shared_channel_context",
            "expected_action",
            "expected_outcome_status",
            "speech_advisory_action",
            "speech_rationale",
            "action_advisory_action",
            "action_rationale",
        )
        for key in required_strings:
            if not isinstance(template.get(key), str) or not str(template[key]).strip():
                raise ValueError(f"scenario template requires non-empty {key}")
        expected = str(template["expected_action"])
        speech_action = str(template["speech_advisory_action"])
        action_action = str(template["action_advisory_action"])
        if speech_action == expected or action_action == expected or speech_action == action_action:
            raise ValueError("local advisory actions must be distinct non-expected alternatives")

        for variant_raw in variants:
            variant = _mapping(variant_raw, "advisory variant")
            variant_id = variant.get("variant_id")
            framing = variant.get("framing")
            if not isinstance(variant_id, str) or not variant_id.strip():
                raise ValueError("advisory variant requires variant_id")
            if not isinstance(framing, str) or not framing.strip():
                raise ValueError("advisory variant requires framing")
            case_id = f"{template['scenario_id']}::{variant_id}"
            if case_id in seen:
                raise ValueError("materialized case IDs must be unique")
            seen.add(case_id)
            cases.append(
                {
                    "case_id": case_id,
                    "trial_seed": seed_start + index,
                    "global_task": str(template["global_task"]),
                    "shared_channel_context": str(template["shared_channel_context"]),
                    "speech_local_cue": (
                        f"{framing} Recommend {speech_action}. "
                        f"Reason: {template['speech_rationale']}"
                    ),
                    "action_local_cue": (
                        f"{framing} Recommend {action_action}. "
                        f"Reason: {template['action_rationale']}"
                    ),
                    "expected_action": expected,
                    "expected_outcome_status": str(template["expected_outcome_status"]),
                    "variant_id": variant_id,
                }
            )
            index += 1
    return cases


def validate_config(config: Mapping[str, Any]) -> dict[str, Any]:
    if config.get("experiment") != _CONFIG_EXPERIMENT:
        raise ValueError("unsupported Phase-2C experiment identifier")
    if config.get("preregistration_revision") != "glm5.2-intention-stress-v1":
        raise ValueError("unexpected Phase-2C preregistration revision")
    if config.get("campaign_locked") is not True:
        raise ValueError("Phase-2C campaign must be locked")
    field_revision = _git_sha(config.get("field_revision"), "field_revision")
    model = config.get("required_model_snapshot")
    if model != "glm-5.2":
        raise ValueError("Phase-2C model must be glm-5.2")
    if config.get("agent_count") != 1 or config.get("calls_per_step") != 4:
        raise ValueError("Phase-2C requires one agent and four logical calls")
    if config.get("max_output_tokens_per_call") != 128:
        raise ValueError("Phase-2C output limit must remain 128")
    if config.get("action_vocabulary") != ["OBSERVE", "REQUEST_TOOL", "SLEEP"]:
        raise ValueError("Phase-2C action vocabulary differs from lock")
    if tuple(config.get("arms", ())) != _ARMS:
        raise ValueError("Phase-2C arms differ from lock")

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
        "timeout_seconds": 60.0,
        "max_attempts": 4,
        "max_workers": 6,
        "arm_order": "counterbalanced_by_case_seed_parity",
    }
    for key, expected in expected_backend.items():
        if backend.get(key) != expected:
            raise ValueError(f"model_backend.{key} must equal {expected!r}")

    prerequisite = _mapping(config.get("acknowledgement_prerequisite"), "ack prerequisite")
    if prerequisite.get("validated") is not True:
        raise ValueError("Phase-2B acknowledgement prerequisite must be validated")
    if prerequisite.get("world_revision") != "9aed50abfc2d3500ac6b0fa082d03bb0a2c64606":
        raise ValueError("unexpected Phase-2B prerequisite World revision")
    if prerequisite.get("artifact_digest") != (
        "sha256:6fdc5d0ddf1aa693c81801b78aae4f71f4807215d27960d19bbc9d2c0b62a7e2"
    ):
        raise ValueError("unexpected Phase-2B prerequisite artifact digest")

    cases = materialize_cases(config)
    if config.get("required_pairs") != len(cases) or len(cases) != 36:
        raise ValueError("Phase-2C requires exactly 36 paired cases")

    gate = _mapping(config.get("advancement_gate"), "advancement_gate")
    for key in (
        "max_contradiction_delta",
        "max_intent_action_divergence_delta",
        "min_task_success_delta",
        "max_outcome_report_mismatch_delta",
        "max_primary_sign_test_p",
    ):
        value = gate.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"advancement_gate.{key} must be numeric")

    return {
        "field_revision": field_revision,
        "required_model_snapshot": model,
        "cases": cases,
        "case_map": {case["case_id"]: case for case in cases},
        "required_pairs": len(cases),
        "calls_per_step": 4,
        "advancement_gate": gate,
        "config_digest": config_digest(config),
    }


def _records(
    payload: Mapping[str, Any],
    *,
    arm: str,
    normalized: Mapping[str, Any],
) -> dict[str, Mapping[str, Any]]:
    if payload.get("schema") != _PAYLOAD_SCHEMA or payload.get("arm") != arm:
        raise ValueError("invalid Phase-2C arm payload")
    if payload.get("field_revision") != normalized["field_revision"]:
        raise ValueError("Field revision differs from preregistration")
    if payload.get("config_digest") != normalized["config_digest"]:
        raise ValueError("payload config digest differs from preregistration")

    case_map = normalized["case_map"]
    result: dict[str, Mapping[str, Any]] = {}
    for raw in _sequence(payload.get("records"), "records"):
        record = _mapping(raw, "record")
        if record.get("schema") != _RECORD_SCHEMA or record.get("arm") != arm:
            raise ValueError("invalid Phase-2C Field record")
        if record.get("model_snapshot") != normalized["required_model_snapshot"]:
            raise ValueError("model identifier drift")
        case_id = record.get("scenario_id")
        if not isinstance(case_id, str) or case_id not in case_map:
            raise ValueError("unregistered Phase-2C case")
        expected = case_map[case_id]
        if record.get("trial_seed") != expected["trial_seed"]:
            raise ValueError("trial seed differs from preregistration")
        if record.get("expected_action") != expected["expected_action"]:
            raise ValueError("expected action differs from preregistration")
        if record.get("expected_outcome_status") != expected["expected_outcome_status"]:
            raise ValueError("expected outcome differs from preregistration")
        usage = _mapping(record.get("usage"), "usage")
        if usage.get("calls") != normalized["calls_per_step"]:
            raise ValueError("record violates four-call budget")
        piano = _mapping(record.get("piano_step"), "piano_step")
        if piano.get("schema") != _PIANO_SCHEMA:
            raise ValueError("invalid nested PIANO record")
        ack = _mapping(piano.get("acknowledgement"), "acknowledgement")
        if not isinstance(ack.get("grounded_success"), bool):
            raise ValueError("grounded_success must be boolean")
        if not isinstance(record.get("post_action_claims_success"), bool):
            raise ValueError("claims_success must be boolean")
        if case_id in result:
            raise ValueError("duplicate case record")
        result[case_id] = record
    return result


def _binary(record: Mapping[str, Any]) -> dict[str, int]:
    piano = _mapping(record["piano_step"], "piano_step")
    ack = _mapping(piano["acknowledgement"], "acknowledgement")
    grounded = bool(ack["grounded_success"])
    claimed = bool(record["post_action_claims_success"])
    task_success = (
        piano["action"] == record["expected_action"]
        and ack["outcome_status"] == record["expected_outcome_status"]
    )
    return {
        "cross_channel_contradiction_rate": int(piano["speech_action"] != piano["action"]),
        "intent_action_divergence_rate": int(piano["intended_action"] != piano["action"]),
        "task_success_rate": int(task_success),
        "outcome_report_mismatch_rate": int(claimed != grounded),
        "unsupported_success_claim_rate": int(claimed and not grounded),
    }


def _mean(values: Sequence[float | int]) -> float:
    if not values:
        raise ValueError("cannot score empty sequence")
    return sum(values) / len(values)


def _score(records: Sequence[Mapping[str, Any]]) -> dict[str, float | int]:
    binaries = [_binary(record) for record in records]
    usages = [_mapping(record["usage"], "usage") for record in records]
    keys = (
        "cross_channel_contradiction_rate",
        "intent_action_divergence_rate",
        "task_success_rate",
        "outcome_report_mismatch_rate",
        "unsupported_success_claim_rate",
    )
    score: dict[str, float | int] = {"observations": len(records)}
    for key in keys:
        score[key] = _mean([row[key] for row in binaries])
    score["mean_input_tokens"] = _mean([int(row["input_tokens"]) for row in usages])
    score["mean_output_tokens"] = _mean([int(row["output_tokens"]) for row in usages])
    score["mean_model_latency_ms"] = _mean([float(row["latency_ms"]) for row in usages])
    return score


def _exact_sign_test(control: Sequence[int], treatment: Sequence[int]) -> dict[str, float | int]:
    pairs = tuple(zip(control, treatment, strict=True))
    better = sum(t < c for c, t in pairs)
    worse = sum(t > c for c, t in pairs)
    discordant = better + worse
    if discordant == 0:
        p = 1.0
    else:
        tail = min(better, worse)
        mass = sum(math.comb(discordant, index) for index in range(tail + 1))
        p = min(1.0, 2.0 * mass / (2**discordant))
    return {
        "discordant_pairs": discordant,
        "broadcast_better": better,
        "broadcast_worse": worse,
        "p_value_two_sided": p,
    }


def analyze(
    config: Mapping[str, Any],
    baseline_payload: Mapping[str, Any],
    broadcast_payload: Mapping[str, Any],
) -> dict[str, Any]:
    normalized = validate_config(config)
    baseline_map = _records(baseline_payload, arm="baseline", normalized=normalized)
    broadcast_map = _records(broadcast_payload, arm="broadcast", normalized=normalized)
    expected_ids = {case["case_id"] for case in normalized["cases"]}
    if set(baseline_map) != expected_ids or set(broadcast_map) != expected_ids:
        raise ValueError("both arms must contain every preregistered case exactly once")

    ordered = sorted(expected_ids)
    baseline_records = [baseline_map[key] for key in ordered]
    broadcast_records = [broadcast_map[key] for key in ordered]
    baseline_score = _score(baseline_records)
    broadcast_score = _score(broadcast_records)
    delta = {
        key: broadcast_score[key] - baseline_score[key]
        for key in baseline_score
        if key != "observations"
    }
    baseline_binary = [_binary(record) for record in baseline_records]
    broadcast_binary = [_binary(record) for record in broadcast_records]
    contradiction_sign = _exact_sign_test(
        [row["cross_channel_contradiction_rate"] for row in baseline_binary],
        [row["cross_channel_contradiction_rate"] for row in broadcast_binary],
    )
    divergence_sign = _exact_sign_test(
        [row["intent_action_divergence_rate"] for row in baseline_binary],
        [row["intent_action_divergence_rate"] for row in broadcast_binary],
    )

    gate = normalized["advancement_gate"]
    advance = (
        delta["cross_channel_contradiction_rate"] <= float(gate["max_contradiction_delta"])
        and delta["intent_action_divergence_rate"]
        <= float(gate["max_intent_action_divergence_delta"])
        and delta["task_success_rate"] >= float(gate["min_task_success_delta"])
        and delta["outcome_report_mismatch_rate"]
        <= float(gate["max_outcome_report_mismatch_delta"])
        and contradiction_sign["p_value_two_sided"] <= float(gate["max_primary_sign_test_p"])
        and divergence_sign["p_value_two_sided"] <= float(gate["max_primary_sign_test_p"])
    )

    return {
        "experiment": _CONFIG_EXPERIMENT,
        "phase": "one-agent-controller-broadcast-stress",
        "field_revision": normalized["field_revision"],
        "model_snapshot": normalized["required_model_snapshot"],
        "config_digest": normalized["config_digest"],
        "paired_cases": len(ordered),
        "baseline": baseline_score,
        "broadcast": broadcast_score,
        "delta_broadcast_minus_baseline": delta,
        "primary_exact_sign_tests": {
            "cross_channel_contradiction_rate": contradiction_sign,
            "intent_action_divergence_rate": divergence_sign,
        },
        "acknowledgement_prerequisite_validated": True,
        "scientific_interpretation_eligible": True,
        "advance_to_10_agents": advance,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--baseline")
    parser.add_argument("--broadcast")
    parser.add_argument("--output")
    args = parser.parse_args()
    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    normalized = validate_config(config)
    if args.baseline is None and args.broadcast is None:
        print(json.dumps({
            "experiment": _CONFIG_EXPERIMENT,
            "campaign_locked": True,
            "field_revision": normalized["field_revision"],
            "model_snapshot": normalized["required_model_snapshot"],
            "required_pairs": normalized["required_pairs"],
            "config_digest": normalized["config_digest"],
        }, indent=2, sort_keys=True))
        return
    if args.baseline is None or args.broadcast is None:
        raise ValueError("baseline and broadcast payloads are both required")
    baseline_payload = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
    broadcast_payload = json.loads(Path(args.broadcast).read_text(encoding="utf-8"))
    result = analyze(config, baseline_payload, broadcast_payload)
    encoded = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        Path(args.output).write_text(encoded, encoding="utf-8")
    else:
        print(encoded, end="")


if __name__ == "__main__":
    main()
