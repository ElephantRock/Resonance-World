"""Preregistered factorial one-agent PIANO Phase-2B analysis."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

_CONFIG_EXPERIMENT = "piano-society-runtime-v0-phase2b-factorial"
_PAYLOAD_SCHEMA = "resonance-world-piano-phase2b-factorial-arm-v0.1"
_RECORD_SCHEMA = "resonance-field-piano-phase2-factorial-step-v0.1"
_PIANO_SCHEMA = "resonance-field-piano-step-v0.1"
_ARMS = ("baseline", "intention_only", "ack_only", "full")


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
    variants = _sequence(config.get("distractor_variants"), "distractor_variants")
    seed_start = config.get("case_seed_start")
    if isinstance(seed_start, bool) or not isinstance(seed_start, int) or seed_start < 0:
        raise ValueError("case_seed_start must be a non-negative integer")

    cases: list[dict[str, Any]] = []
    seen: set[str] = set()
    index = 0
    for template_raw in templates:
        template = _mapping(template_raw, "scenario template")
        base_id = template.get("scenario_id")
        trigger = template.get("trigger")
        expected_action = template.get("expected_action")
        expected_status = template.get("expected_outcome_status")
        family = template.get("challenge_family")
        if not all(isinstance(value, str) and value.strip() for value in (
            base_id,
            trigger,
            expected_action,
            expected_status,
            family,
        )):
            raise ValueError("scenario templates require non-empty string fields")
        for variant_raw in variants:
            variant = _mapping(variant_raw, "distractor variant")
            variant_id = variant.get("variant_id")
            distractor = variant.get("distractor")
            if not isinstance(variant_id, str) or not variant_id.strip():
                raise ValueError("distractor variants require variant_id")
            if not isinstance(distractor, str) or not distractor.strip():
                raise ValueError("distractor variants require distractor")
            case_id = f"{base_id}::{variant_id}"
            if case_id in seen:
                raise ValueError("materialized case IDs must be unique")
            seen.add(case_id)
            cases.append(
                {
                    "case_id": case_id,
                    "trial_seed": seed_start + index,
                    "trigger": f"{trigger} Distractor cue: {distractor}",
                    "expected_action": expected_action,
                    "expected_outcome_status": expected_status,
                    "challenge_family": family,
                    "variant_id": variant_id,
                }
            )
            index += 1
    return cases


def validate_config(config: Mapping[str, Any]) -> dict[str, Any]:
    if config.get("experiment") != _CONFIG_EXPERIMENT:
        raise ValueError("unsupported Phase-2B experiment identifier")
    if config.get("preregistration_revision") != "glm5.2-factorial-hard-v1":
        raise ValueError("unexpected Phase-2B preregistration revision")
    if config.get("campaign_locked") is not True:
        raise ValueError("Phase-2B campaign must be locked")
    field_revision = _git_sha(config.get("field_revision"), "field_revision")
    model = config.get("required_model_snapshot")
    if not isinstance(model, str) or not model.strip():
        raise ValueError("required_model_snapshot must be non-empty")
    if config.get("agent_count") != 1 or config.get("calls_per_step") != 4:
        raise ValueError("Phase-2B requires one agent and four calls per arm")
    if tuple(config.get("arms", ())) != _ARMS:
        raise ValueError("Phase-2B arms differ from preregistration")
    cases = materialize_cases(config)
    if config.get("required_pairs") != len(cases):
        raise ValueError("required_pairs must equal materialized cases")

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
    }
    for key, expected in expected_backend.items():
        if backend.get(key) != expected:
            raise ValueError(f"model_backend.{key} must equal {expected!r}")

    gate = _mapping(config.get("advancement_gate"), "advancement_gate")
    for key in (
        "max_intention_contradiction_delta",
        "max_ack_outcome_mismatch_delta",
        "max_full_contradiction_delta",
        "max_full_outcome_mismatch_delta",
        "min_component_task_success_delta",
        "min_full_task_success_delta",
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
        raise ValueError("invalid Phase-2B arm payload")
    if payload.get("field_revision") != normalized["field_revision"]:
        raise ValueError("Field revision differs from preregistration")
    if payload.get("config_digest") != normalized["config_digest"]:
        raise ValueError("payload config digest differs from preregistration")

    result: dict[str, Mapping[str, Any]] = {}
    case_map = normalized["case_map"]
    for raw in _sequence(payload.get("records"), "records"):
        record = _mapping(raw, "record")
        if record.get("schema") != _RECORD_SCHEMA or record.get("arm") != arm:
            raise ValueError("invalid factorial Field record")
        if record.get("model_snapshot") != normalized["required_model_snapshot"]:
            raise ValueError("model identifier drift")
        case_id = record.get("scenario_id")
        if not isinstance(case_id, str) or case_id not in case_map:
            raise ValueError("unregistered case")
        expected = case_map[case_id]
        if record.get("trial_seed") != expected["trial_seed"]:
            raise ValueError("trial seed differs from registered case")
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
        "outcome_report_mismatch_rate": int(claimed != grounded),
        "unsupported_success_claim_rate": int(claimed and not grounded),
        "task_success_rate": int(task_success),
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
        "outcome_report_mismatch_rate",
        "unsupported_success_claim_rate",
        "task_success_rate",
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
        mass = sum(math.comb(discordant, i) for i in range(tail + 1))
        p = min(1.0, 2.0 * mass / (2**discordant))
    return {
        "discordant_pairs": discordant,
        "treatment_better": better,
        "treatment_worse": worse,
        "p_value_two_sided": p,
    }


def analyze(config: Mapping[str, Any], payloads: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    normalized = validate_config(config)
    expected_ids = {case["case_id"] for case in normalized["cases"]}
    arm_maps = {
        arm: _records(payloads[arm], arm=arm, normalized=normalized)
        for arm in _ARMS
    }
    for arm, records in arm_maps.items():
        if set(records) != expected_ids:
            raise ValueError(f"{arm} must contain every preregistered case exactly once")

    ordered = sorted(expected_ids)
    arm_records = {arm: [arm_maps[arm][key] for key in ordered] for arm in _ARMS}
    scores = {arm: _score(records) for arm, records in arm_records.items()}
    baseline = scores["baseline"]
    contrasts = {}
    for arm in ("intention_only", "ack_only", "full"):
        contrasts[f"{arm}_minus_baseline"] = {
            key: scores[arm][key] - baseline[key]
            for key in baseline
            if key != "observations"
        }

    binaries = {
        arm: [_binary(record) for record in records]
        for arm, records in arm_records.items()
    }
    intention_sign = _exact_sign_test(
        [row["cross_channel_contradiction_rate"] for row in binaries["baseline"]],
        [row["cross_channel_contradiction_rate"] for row in binaries["intention_only"]],
    )
    ack_sign = _exact_sign_test(
        [row["outcome_report_mismatch_rate"] for row in binaries["baseline"]],
        [row["outcome_report_mismatch_rate"] for row in binaries["ack_only"]],
    )

    gate = normalized["advancement_gate"]
    intention_delta = contrasts["intention_only_minus_baseline"]
    ack_delta = contrasts["ack_only_minus_baseline"]
    full_delta = contrasts["full_minus_baseline"]
    advance = (
        intention_delta["cross_channel_contradiction_rate"]
        <= float(gate["max_intention_contradiction_delta"])
        and ack_delta["outcome_report_mismatch_rate"]
        <= float(gate["max_ack_outcome_mismatch_delta"])
        and full_delta["cross_channel_contradiction_rate"]
        <= float(gate["max_full_contradiction_delta"])
        and full_delta["outcome_report_mismatch_rate"]
        <= float(gate["max_full_outcome_mismatch_delta"])
        and intention_delta["task_success_rate"]
        >= float(gate["min_component_task_success_delta"])
        and ack_delta["task_success_rate"]
        >= float(gate["min_component_task_success_delta"])
        and full_delta["task_success_rate"] >= float(gate["min_full_task_success_delta"])
        and intention_sign["p_value_two_sided"] <= float(gate["max_primary_sign_test_p"])
        and ack_sign["p_value_two_sided"] <= float(gate["max_primary_sign_test_p"])
    )

    return {
        "experiment": _CONFIG_EXPERIMENT,
        "phase": "one-agent-factorial-hard-cases",
        "field_revision": normalized["field_revision"],
        "model_snapshot": normalized["required_model_snapshot"],
        "config_digest": normalized["config_digest"],
        "paired_cases": len(ordered),
        "arms": scores,
        "contrasts": contrasts,
        "primary_exact_sign_tests": {
            "intention_effect_on_contradiction": intention_sign,
            "ack_effect_on_outcome_mismatch": ack_sign,
        },
        "scientific_interpretation_eligible": True,
        "advance_to_10_agents": advance,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--baseline")
    parser.add_argument("--intention-only")
    parser.add_argument("--ack-only")
    parser.add_argument("--full")
    parser.add_argument("--output")
    args = parser.parse_args()
    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    normalized = validate_config(config)
    paths = [args.baseline, args.intention_only, args.ack_only, args.full]
    if all(path is None for path in paths):
        print(json.dumps({
            "experiment": _CONFIG_EXPERIMENT,
            "campaign_locked": True,
            "field_revision": normalized["field_revision"],
            "model_snapshot": normalized["required_model_snapshot"],
            "required_pairs": normalized["required_pairs"],
            "config_digest": normalized["config_digest"],
        }, indent=2, sort_keys=True))
        return
    if any(path is None for path in paths):
        raise ValueError("all four arm payloads are required for analysis")
    payloads = {
        "baseline": json.loads(Path(args.baseline).read_text(encoding="utf-8")),
        "intention_only": json.loads(Path(args.intention_only).read_text(encoding="utf-8")),
        "ack_only": json.loads(Path(args.ack_only).read_text(encoding="utf-8")),
        "full": json.loads(Path(args.full).read_text(encoding="utf-8")),
    }
    result = analyze(config, payloads)
    encoded = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        Path(args.output).write_text(encoded, encoding="utf-8")
    else:
        print(encoded, end="")


if __name__ == "__main__":
    main()
