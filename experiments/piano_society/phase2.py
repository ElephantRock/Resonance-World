"""Preregistered Phase-2 validator and paired mechanical analysis."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

_CONFIG_EXPERIMENT = "piano-society-runtime-v0-phase2"
_PAYLOAD_SCHEMA = "resonance-world-piano-phase2-campaign-arm-v0.1"
_RECORD_SCHEMA = "resonance-field-piano-phase2-step-v0.1"
_PIANO_SCHEMA = "resonance-field-piano-step-v0.1"


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
    encoded = json.dumps(config, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def validate_config(config: Mapping[str, Any]) -> dict[str, Any]:
    if config.get("experiment") != _CONFIG_EXPERIMENT:
        raise ValueError("unsupported Phase-2 experiment identifier")
    locked = config.get("campaign_locked")
    if not isinstance(locked, bool):
        raise ValueError("campaign_locked must be boolean")
    field_revision = _git_sha(config.get("field_revision"), "field_revision")
    model_snapshot = config.get("required_model_snapshot")
    if locked and (not isinstance(model_snapshot, str) or not model_snapshot.strip()):
        raise ValueError("locked campaign requires an immutable model snapshot")
    if not locked and model_snapshot is not None:
        if not isinstance(model_snapshot, str) or not model_snapshot.strip():
            raise ValueError("required_model_snapshot must be null or non-empty")

    if config.get("agent_count") != 1:
        raise ValueError("Phase 2 is preregistered for exactly one agent")
    calls_per_step = config.get("calls_per_step")
    if calls_per_step != 4:
        raise ValueError("Phase 2 requires exactly four model calls per step")
    max_tokens = config.get("max_output_tokens_per_call")
    if not isinstance(max_tokens, int) or max_tokens <= 0:
        raise ValueError("max_output_tokens_per_call must be positive")

    seeds_raw = _sequence(config.get("seeds"), "seeds")
    seeds = tuple(seeds_raw)
    if not seeds or any(isinstance(seed, bool) or not isinstance(seed, int) for seed in seeds):
        raise ValueError("seeds must contain integers")
    if len(set(seeds)) != len(seeds):
        raise ValueError("seeds must be unique")

    scenarios_raw = _sequence(config.get("scenarios"), "scenarios")
    scenarios: dict[str, Mapping[str, Any]] = {}
    for index, value in enumerate(scenarios_raw):
        scenario = _mapping(value, f"scenarios[{index}]")
        scenario_id = scenario.get("scenario_id")
        if not isinstance(scenario_id, str) or not scenario_id.strip():
            raise ValueError("each scenario requires scenario_id")
        if scenario_id in scenarios:
            raise ValueError("scenario_id values must be unique")
        if not isinstance(scenario.get("expected_action"), str):
            raise ValueError("each scenario requires expected_action")
        if not isinstance(scenario.get("expected_outcome_status"), str):
            raise ValueError("each scenario requires expected_outcome_status")
        scenarios[scenario_id] = scenario

    expected_pairs = len(seeds) * len(scenarios)
    if config.get("required_pairs") != expected_pairs:
        raise ValueError("required_pairs must equal seeds x scenarios")

    gate = _mapping(config.get("advancement_gate"), "advancement_gate")
    for key in (
        "max_cross_channel_delta",
        "max_unsupported_success_delta",
        "min_task_success_delta",
        "max_primary_sign_test_p",
    ):
        value = gate.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"advancement_gate.{key} must be numeric")

    return {
        "campaign_locked": locked,
        "field_revision": field_revision,
        "required_model_snapshot": model_snapshot,
        "calls_per_step": calls_per_step,
        "seeds": seeds,
        "scenarios": scenarios,
        "required_pairs": expected_pairs,
        "advancement_gate": gate,
        "config_digest": config_digest(config),
    }


def _campaign_records(
    payload: Mapping[str, Any],
    *,
    arm: str,
    normalized: Mapping[str, Any],
) -> dict[tuple[str, int], Mapping[str, Any]]:
    if payload.get("schema") != _PAYLOAD_SCHEMA:
        raise ValueError("unsupported Phase-2 campaign payload schema")
    if payload.get("arm") != arm:
        raise ValueError(f"expected {arm} arm payload")
    if payload.get("field_revision") != normalized["field_revision"]:
        raise ValueError("campaign Field revision does not match preregistration")

    raw_records = _sequence(payload.get("records"), "records")
    records: dict[tuple[str, int], Mapping[str, Any]] = {}
    scenarios = normalized["scenarios"]
    seeds = set(normalized["seeds"])
    required_snapshot = normalized["required_model_snapshot"]

    for index, value in enumerate(raw_records):
        record = _mapping(value, f"records[{index}]")
        if record.get("schema") != _RECORD_SCHEMA:
            raise ValueError("unsupported Field Phase-2 record schema")
        if record.get("arm") != arm:
            raise ValueError("record arm does not match campaign arm")
        if record.get("model_snapshot") != required_snapshot:
            raise ValueError("record model snapshot does not match preregistration")
        seed = record.get("trial_seed")
        if isinstance(seed, bool) or not isinstance(seed, int) or seed not in seeds:
            raise ValueError("record trial_seed is not preregistered")
        scenario_id = record.get("scenario_id")
        if not isinstance(scenario_id, str) or scenario_id not in scenarios:
            raise ValueError("record scenario_id is not preregistered")
        scenario = scenarios[scenario_id]
        if record.get("expected_action") != scenario["expected_action"]:
            raise ValueError("record expected_action differs from preregistration")
        if record.get("expected_outcome_status") != scenario["expected_outcome_status"]:
            raise ValueError("record expected outcome differs from preregistration")

        usage = _mapping(record.get("usage"), "usage")
        if usage.get("calls") != normalized["calls_per_step"]:
            raise ValueError("record violates the frozen model-call budget")
        for key in ("input_tokens", "output_tokens"):
            count = usage.get(key)
            if isinstance(count, bool) or not isinstance(count, int) or count < 0:
                raise ValueError(f"usage.{key} must be a non-negative integer")
        latency = usage.get("latency_ms")
        if isinstance(latency, bool) or not isinstance(latency, (int, float)):
            raise ValueError("usage.latency_ms must be numeric")
        if latency < 0:
            raise ValueError("usage.latency_ms must be non-negative")

        piano = _mapping(record.get("piano_step"), "piano_step")
        if piano.get("schema") != _PIANO_SCHEMA:
            raise ValueError("unsupported nested PIANO record schema")
        for key in ("action", "speech_action", "intended_action"):
            if not isinstance(piano.get(key), str):
                raise ValueError(f"piano_step.{key} must be a structured action label")
        acknowledgement = _mapping(piano.get("acknowledgement"), "acknowledgement")
        if not isinstance(acknowledgement.get("grounded_success"), bool):
            raise ValueError("acknowledgement.grounded_success must be boolean")
        if not isinstance(acknowledgement.get("outcome_status"), str):
            raise ValueError("acknowledgement.outcome_status must be a string")
        if not isinstance(record.get("post_action_claims_success"), bool):
            raise ValueError("post_action_claims_success must be boolean")

        pair_key = (scenario_id, seed)
        if pair_key in records:
            raise ValueError(f"duplicate record for pair {pair_key!r}")
        records[pair_key] = record
    return records


def _binary_metrics(record: Mapping[str, Any]) -> dict[str, int]:
    piano = _mapping(record["piano_step"], "piano_step")
    acknowledgement = _mapping(piano["acknowledgement"], "acknowledgement")
    action = piano["action"]
    grounded_success = bool(acknowledgement["grounded_success"])
    task_success = (
        action == record["expected_action"]
        and acknowledgement["outcome_status"] == record["expected_outcome_status"]
    )
    return {
        "cross_channel_contradiction_rate": int(piano["speech_action"] != action),
        "intent_action_divergence_rate": int(piano["intended_action"] != action),
        "unsupported_success_claim_rate": int(
            bool(record["post_action_claims_success"]) and not grounded_success
        ),
        "task_success_rate": int(task_success),
    }


def _mean(values: Sequence[float | int]) -> float:
    if not values:
        raise ValueError("cannot compute mean of empty sequence")
    return sum(values) / len(values)


def _arm_score(records: Sequence[Mapping[str, Any]]) -> dict[str, float | int]:
    binaries = [_binary_metrics(record) for record in records]
    usage = [_mapping(record["usage"], "usage") for record in records]
    return {
        "observations": len(records),
        "cross_channel_contradiction_rate": _mean(
            [row["cross_channel_contradiction_rate"] for row in binaries]
        ),
        "intent_action_divergence_rate": _mean(
            [row["intent_action_divergence_rate"] for row in binaries]
        ),
        "unsupported_success_claim_rate": _mean(
            [row["unsupported_success_claim_rate"] for row in binaries]
        ),
        "task_success_rate": _mean([row["task_success_rate"] for row in binaries]),
        "mean_input_tokens": _mean([int(row["input_tokens"]) for row in usage]),
        "mean_output_tokens": _mean([int(row["output_tokens"]) for row in usage]),
        "mean_model_latency_ms": _mean([float(row["latency_ms"]) for row in usage]),
    }


def _exact_sign_test(
    control: Sequence[int],
    treatment: Sequence[int],
) -> dict[str, float | int]:
    if len(control) != len(treatment):
        raise ValueError("paired sign test requires equal lengths")
    pairs = tuple(zip(control, treatment, strict=True))
    treatment_better = sum(
        treatment_value < control_value
        for control_value, treatment_value in pairs
    )
    treatment_worse = sum(
        treatment_value > control_value
        for control_value, treatment_value in pairs
    )
    discordant = treatment_better + treatment_worse
    if discordant == 0:
        p_value = 1.0
    else:
        tail = min(treatment_better, treatment_worse)
        probability = sum(math.comb(discordant, index) for index in range(tail + 1))
        p_value = min(1.0, 2.0 * probability / (2**discordant))
    return {
        "discordant_pairs": discordant,
        "treatment_better": treatment_better,
        "treatment_worse": treatment_worse,
        "p_value_two_sided": p_value,
    }


def analyze(
    config: Mapping[str, Any],
    control_payload: Mapping[str, Any],
    treatment_payload: Mapping[str, Any],
) -> dict[str, Any]:
    normalized = validate_config(config)
    if not normalized["campaign_locked"]:
        raise ValueError("Phase-2 campaign must be locked before outcome analysis")

    control_map = _campaign_records(control_payload, arm="control", normalized=normalized)
    treatment_map = _campaign_records(
        treatment_payload,
        arm="treatment",
        normalized=normalized,
    )
    expected_keys = {
        (scenario_id, seed)
        for scenario_id in normalized["scenarios"]
        for seed in normalized["seeds"]
    }
    if set(control_map) != expected_keys or set(treatment_map) != expected_keys:
        raise ValueError("campaign must contain every preregistered pair with no extras")

    ordered_keys = sorted(expected_keys)
    control = [control_map[key] for key in ordered_keys]
    treatment = [treatment_map[key] for key in ordered_keys]
    control_score = _arm_score(control)
    treatment_score = _arm_score(treatment)
    metric_names = (
        "cross_channel_contradiction_rate",
        "intent_action_divergence_rate",
        "unsupported_success_claim_rate",
        "task_success_rate",
        "mean_input_tokens",
        "mean_output_tokens",
        "mean_model_latency_ms",
    )
    deltas = {
        metric: treatment_score[metric] - control_score[metric]
        for metric in metric_names
    }

    control_binary = [_binary_metrics(record) for record in control]
    treatment_binary = [_binary_metrics(record) for record in treatment]
    sign_tests = {}
    for metric in (
        "cross_channel_contradiction_rate",
        "unsupported_success_claim_rate",
    ):
        sign_tests[metric] = _exact_sign_test(
            [row[metric] for row in control_binary],
            [row[metric] for row in treatment_binary],
        )

    gate = normalized["advancement_gate"]
    eligible = bool(normalized["required_model_snapshot"])
    advance = (
        eligible
        and deltas["cross_channel_contradiction_rate"]
        <= float(gate["max_cross_channel_delta"])
        and deltas["unsupported_success_claim_rate"]
        <= float(gate["max_unsupported_success_delta"])
        and deltas["task_success_rate"] >= float(gate["min_task_success_delta"])
        and sign_tests["cross_channel_contradiction_rate"]["p_value_two_sided"]
        <= float(gate["max_primary_sign_test_p"])
        and sign_tests["unsupported_success_claim_rate"]["p_value_two_sided"]
        <= float(gate["max_primary_sign_test_p"])
    )

    return {
        "experiment": _CONFIG_EXPERIMENT,
        "phase": "one-agent-model-backed",
        "field_revision": normalized["field_revision"],
        "model_snapshot": normalized["required_model_snapshot"],
        "config_digest": normalized["config_digest"],
        "paired_episodes": len(ordered_keys),
        "scientific_interpretation_eligible": eligible,
        "control": control_score,
        "treatment": treatment_score,
        "delta_treatment_minus_control": deltas,
        "primary_exact_sign_tests": sign_tests,
        "advance_to_10_agents": advance,
    }


def _load(path: str | Path) -> Mapping[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    return _mapping(value, str(path))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--control")
    parser.add_argument("--treatment")
    parser.add_argument("--output")
    args = parser.parse_args()

    config = _load(args.config)
    normalized = validate_config(config)
    if args.control is None and args.treatment is None:
        print(
            json.dumps(
                {
                    "experiment": _CONFIG_EXPERIMENT,
                    "campaign_locked": normalized["campaign_locked"],
                    "required_pairs": normalized["required_pairs"],
                    "field_revision": normalized["field_revision"],
                    "model_snapshot": normalized["required_model_snapshot"],
                    "config_digest": normalized["config_digest"],
                },
                indent=2,
                sort_keys=True,
            )
        )
        return
    if args.control is None or args.treatment is None or args.output is None:
        raise SystemExit("--control, --treatment, and --output are required together")

    result = analyze(config, _load(args.control), _load(args.treatment))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
