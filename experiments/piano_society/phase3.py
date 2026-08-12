"""Preregistered 10-agent PIANO Phase-3 social coordination analysis."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

_CONFIG_EXPERIMENT = "piano-society-runtime-v0-phase3-social"
_PAYLOAD_SCHEMA = "resonance-world-piano-phase3-social-arm-v0.1"
_RECORD_SCHEMA = "resonance-field-piano-phase3-social-step-v0.1"
_PIANO_SCHEMA = "resonance-field-piano-step-v0.1"
_ARMS = ("decentralized", "piano")
_ACTIONS = ("OBSERVE", "REQUEST_TOOL", "SLEEP")


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


def expected_outcome(action: str) -> str:
    if action == "REQUEST_TOOL":
        return "rejected"
    if action in {"OBSERVE", "SLEEP"}:
        return "succeeded"
    raise ValueError(f"unsupported registered action {action!r}")


def materialize_roles(config: Mapping[str, Any]) -> list[dict[str, Any]]:
    cases = _sequence(config.get("joint_cases"), "joint_cases")
    roles: list[dict[str, Any]] = []
    seen_cases: set[str] = set()
    action_counts: Counter[str] = Counter()
    for case_raw in cases:
        case = _mapping(case_raw, "joint case")
        case_id = case.get("case_id")
        case_seed = case.get("case_seed")
        actions = _sequence(case.get("role_actions"), "role_actions")
        if not isinstance(case_id, str) or not case_id.strip() or case_id in seen_cases:
            raise ValueError("joint cases require unique non-empty case_id")
        seen_cases.add(case_id)
        if isinstance(case_seed, bool) or not isinstance(case_seed, int) or case_seed < 0:
            raise ValueError("joint cases require non-negative integer case_seed")
        if len(actions) != 10 or any(action not in _ACTIONS for action in actions):
            raise ValueError("each joint case must contain ten registered role actions")
        for pair_index in range(5):
            left = str(actions[pair_index * 2])
            right = str(actions[pair_index * 2 + 1])
            if left == right:
                raise ValueError("each Phase-3 dyad must have distinct role actions")
        for agent_index, action_raw in enumerate(actions):
            action = str(action_raw)
            action_counts[action] += 1
            roles.append(
                {
                    "joint_case_id": case_id,
                    "case_seed": case_seed,
                    "scenario_id": f"{case_id}::agent-{agent_index}",
                    "trial_seed": case_seed * 100 + agent_index,
                    "agent_index": agent_index,
                    "pair_index": agent_index // 2,
                    "counterpart_index": agent_index + 1 if agent_index % 2 == 0 else agent_index - 1,
                    "expected_action": action,
                    "expected_outcome_status": expected_outcome(action),
                }
            )
    if action_counts != Counter({"OBSERVE": 20, "REQUEST_TOOL": 20, "SLEEP": 20}):
        raise ValueError("Phase-3 role assignments must balance all three actions 20/20/20")
    return roles


def validate_config(config: Mapping[str, Any]) -> dict[str, Any]:
    if config.get("experiment") != _CONFIG_EXPERIMENT:
        raise ValueError("unsupported Phase-3 experiment identifier")
    if config.get("preregistration_revision") != "glm5.2-social-dyads-v1":
        raise ValueError("unexpected Phase-3 preregistration revision")
    if config.get("campaign_locked") is not True:
        raise ValueError("Phase-3 campaign must be locked")
    field_revision = _git_sha(config.get("field_revision"), "field_revision")
    if config.get("required_model_snapshot") != "glm-5.2":
        raise ValueError("Phase-3 model must be glm-5.2")
    if config.get("agent_count") != 10 or config.get("pair_count") != 5:
        raise ValueError("Phase-3 requires ten agents arranged as five dyads")
    if config.get("calls_per_agent") != 4:
        raise ValueError("Phase-3 requires exactly four logical calls per agent")
    if config.get("max_output_tokens_per_call") != 128:
        raise ValueError("Phase-3 output limit must remain 128")
    if config.get("action_vocabulary") != ["OBSERVE", "REQUEST_TOOL", "SLEEP"]:
        raise ValueError("Phase-3 action vocabulary differs from lock")
    if tuple(config.get("arms", ())) != _ARMS:
        raise ValueError("Phase-3 arms differ from lock")

    prerequisites = _mapping(config.get("validated_prerequisites"), "validated_prerequisites")
    if prerequisites.get("acknowledgement_validated") is not True:
        raise ValueError("Phase-3 requires validated acknowledgement")
    if prerequisites.get("controller_broadcast_validated") is not True:
        raise ValueError("Phase-3 requires validated controller broadcast")
    if prerequisites.get("phase2b_artifact_digest") != (
        "sha256:6fdc5d0ddf1aa693c81801b78aae4f71f4807215d27960d19bbc9d2c0b62a7e2"
    ):
        raise ValueError("unexpected Phase-2B prerequisite artifact")
    if prerequisites.get("phase2c_artifact_digest") != (
        "sha256:f330a4d5153327a3bca37ea9e30ab8fd7eb3f167f0cb474f708ef0e4fc5a698b"
    ):
        raise ValueError("unexpected Phase-2C prerequisite artifact")

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
        "max_attempts": 6,
        "max_workers": 3,
        "arm_order": "counterbalanced_by_case_seed_parity",
        "agent_order_within_round": "ascending_agent_index",
    }
    for key, expected in expected_backend.items():
        if backend.get(key) != expected:
            raise ValueError(f"model_backend.{key} must equal {expected!r}")

    roles = materialize_roles(config)
    if config.get("required_joint_cases") != 6 or len(roles) != 60:
        raise ValueError("Phase-3 requires six joint cases and sixty roles")

    gate = _mapping(config.get("advancement_gate"), "advancement_gate")
    for key in (
        "max_dyad_failure_delta",
        "max_agent_role_failure_delta",
        "min_joint_case_completion_delta",
        "max_contradiction_delta",
        "max_outcome_report_mismatch_delta",
        "max_primary_sign_test_p",
    ):
        value = gate.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"advancement_gate.{key} must be numeric")

    return {
        "field_revision": field_revision,
        "required_model_snapshot": "glm-5.2",
        "roles": roles,
        "role_map": {role["scenario_id"]: role for role in roles},
        "joint_case_ids": tuple(dict.fromkeys(role["joint_case_id"] for role in roles)),
        "calls_per_agent": 4,
        "advancement_gate": gate,
        "config_digest": config_digest(config),
    }


def _canonical_board(entries: Sequence[Mapping[str, object]]) -> tuple[dict[str, object], ...]:
    result = []
    for entry in entries:
        result.append(
            {
                "agent_index": int(entry["agent_index"]),
                "pair_index": int(entry["pair_index"]),
                "speech": str(entry["speech"]),
                "speech_action": entry["speech_action"],
            }
        )
    result.sort(key=lambda item: int(item["agent_index"]))
    return tuple(result)


def _board_digest(entries: Sequence[Mapping[str, object]]) -> str:
    encoded = json.dumps(
        _canonical_board(entries),
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _records(
    payload: Mapping[str, Any],
    *,
    arm: str,
    normalized: Mapping[str, Any],
) -> dict[str, Mapping[str, Any]]:
    if payload.get("schema") != _PAYLOAD_SCHEMA or payload.get("arm") != arm:
        raise ValueError("invalid Phase-3 arm payload")
    if payload.get("field_revision") != normalized["field_revision"]:
        raise ValueError("Field revision differs from Phase-3 lock")
    if payload.get("config_digest") != normalized["config_digest"]:
        raise ValueError("payload config digest differs from Phase-3 lock")

    role_map = normalized["role_map"]
    result: dict[str, Mapping[str, Any]] = {}
    for raw in _sequence(payload.get("records"), "records"):
        record = _mapping(raw, "record")
        if record.get("schema") != _RECORD_SCHEMA or record.get("arm") != arm:
            raise ValueError("invalid Phase-3 Field record")
        if record.get("model_snapshot") != normalized["required_model_snapshot"]:
            raise ValueError("Phase-3 model identifier drift")
        scenario_id = record.get("scenario_id")
        if not isinstance(scenario_id, str) or scenario_id not in role_map:
            raise ValueError("unregistered Phase-3 role record")
        role = role_map[scenario_id]
        for key in (
            "trial_seed",
            "agent_index",
            "pair_index",
            "expected_action",
            "expected_outcome_status",
        ):
            if record.get(key) != role[key]:
                raise ValueError(f"Phase-3 record {key} differs from preregistration")
        digest = record.get("peer_board_digest")
        if not isinstance(digest, str) or len(digest) != 64:
            raise ValueError("Phase-3 peer-board digest must be SHA-256 hex")
        usage = _mapping(record.get("usage"), "usage")
        if usage.get("calls") != normalized["calls_per_agent"]:
            raise ValueError("Phase-3 record violates four-call budget")
        piano = _mapping(record.get("piano_step"), "piano_step")
        if piano.get("schema") != _PIANO_SCHEMA:
            raise ValueError("invalid nested PIANO record")
        ack = _mapping(piano.get("acknowledgement"), "acknowledgement")
        if not isinstance(ack.get("grounded_success"), bool):
            raise ValueError("grounded_success must be boolean")
        if not isinstance(record.get("post_action_claims_success"), bool):
            raise ValueError("claims_success must be boolean")
        if scenario_id in result:
            raise ValueError("duplicate Phase-3 role record")
        result[scenario_id] = record
    return result


def _validate_boards(
    records: Mapping[str, Mapping[str, Any]],
    normalized: Mapping[str, Any],
) -> None:
    for case_id in normalized["joint_case_ids"]:
        case_records = [
            record
            for scenario_id, record in records.items()
            if normalized["role_map"][scenario_id]["joint_case_id"] == case_id
        ]
        if len(case_records) != 10:
            raise ValueError("each Phase-3 arm/case requires ten agent records")
        board = []
        for record in case_records:
            piano = _mapping(record["piano_step"], "piano_step")
            board.append(
                {
                    "agent_index": record["agent_index"],
                    "pair_index": record["pair_index"],
                    "speech": piano["speech"],
                    "speech_action": piano["speech_action"],
                }
            )
        digest = _board_digest(board)
        if any(record["peer_board_digest"] != digest for record in case_records):
            raise ValueError("Phase-3 agent records disagree with reconstructed peer board")


def _agent_failure(record: Mapping[str, Any]) -> int:
    piano = _mapping(record["piano_step"], "piano_step")
    ack = _mapping(piano["acknowledgement"], "acknowledgement")
    return int(
        piano["action"] != record["expected_action"]
        or ack["outcome_status"] != record["expected_outcome_status"]
    )


def _binary(record: Mapping[str, Any]) -> dict[str, int]:
    piano = _mapping(record["piano_step"], "piano_step")
    ack = _mapping(piano["acknowledgement"], "acknowledgement")
    grounded = bool(ack["grounded_success"])
    claimed = bool(record["post_action_claims_success"])
    return {
        "agent_role_failure_rate": _agent_failure(record),
        "cross_channel_contradiction_rate": int(piano["speech_action"] != piano["action"]),
        "intent_action_divergence_rate": int(piano["intended_action"] != piano["action"]),
        "outcome_report_mismatch_rate": int(claimed != grounded),
        "unsupported_success_claim_rate": int(claimed and not grounded),
    }


def _mean(values: Sequence[float | int]) -> float:
    if not values:
        raise ValueError("cannot score empty sequence")
    return sum(values) / len(values)


def _social_units(
    records: Mapping[str, Mapping[str, Any]],
    normalized: Mapping[str, Any],
) -> tuple[list[int], list[int]]:
    dyad_failures: list[int] = []
    case_failures: list[int] = []
    for case_id in normalized["joint_case_ids"]:
        roles = [role for role in normalized["roles"] if role["joint_case_id"] == case_id]
        case_failed = False
        for pair_index in range(5):
            pair = [role for role in roles if role["pair_index"] == pair_index]
            pair_failed = any(_agent_failure(records[role["scenario_id"]]) for role in pair)
            dyad_failures.append(int(pair_failed))
            case_failed = case_failed or pair_failed
        case_failures.append(int(case_failed))
    return dyad_failures, case_failures


def _score(
    records: Mapping[str, Mapping[str, Any]],
    normalized: Mapping[str, Any],
) -> dict[str, float | int]:
    ordered = [records[role["scenario_id"]] for role in normalized["roles"]]
    binaries = [_binary(record) for record in ordered]
    usages = [_mapping(record["usage"], "usage") for record in ordered]
    dyad_failures, case_failures = _social_units(records, normalized)
    score: dict[str, float | int] = {
        "agent_observations": len(ordered),
        "dyads": len(dyad_failures),
        "joint_cases": len(case_failures),
        "dyad_failure_rate": _mean(dyad_failures),
        "joint_case_failure_rate": _mean(case_failures),
        "joint_case_completion_rate": 1.0 - _mean(case_failures),
    }
    for key in (
        "agent_role_failure_rate",
        "cross_channel_contradiction_rate",
        "intent_action_divergence_rate",
        "outcome_report_mismatch_rate",
        "unsupported_success_claim_rate",
    ):
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
        "discordant_units": discordant,
        "piano_better": better,
        "piano_worse": worse,
        "p_value_two_sided": p,
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
        raise ValueError("both Phase-3 arms must contain all sixty roles exactly once")
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
    d_agents = [_agent_failure(decentralized[role["scenario_id"]]) for role in normalized["roles"]]
    p_agents = [_agent_failure(piano[role["scenario_id"]]) for role in normalized["roles"]]
    dyad_sign = _exact_sign_test(d_dyads, p_dyads)
    agent_sign = _exact_sign_test(d_agents, p_agents)

    gate = normalized["advancement_gate"]
    advance = (
        delta["dyad_failure_rate"] <= float(gate["max_dyad_failure_delta"])
        and delta["agent_role_failure_rate"] <= float(gate["max_agent_role_failure_delta"])
        and delta["joint_case_completion_rate"] >= float(gate["min_joint_case_completion_delta"])
        and delta["cross_channel_contradiction_rate"] <= float(gate["max_contradiction_delta"])
        and delta["outcome_report_mismatch_rate"]
        <= float(gate["max_outcome_report_mismatch_delta"])
        and dyad_sign["p_value_two_sided"] <= float(gate["max_primary_sign_test_p"])
        and agent_sign["p_value_two_sided"] <= float(gate["max_primary_sign_test_p"])
    )

    return {
        "experiment": _CONFIG_EXPERIMENT,
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
        print(json.dumps({
            "experiment": _CONFIG_EXPERIMENT,
            "campaign_locked": True,
            "field_revision": normalized["field_revision"],
            "model_snapshot": normalized["required_model_snapshot"],
            "joint_cases": 6,
            "agent_records_per_arm": 60,
            "config_digest": normalized["config_digest"],
        }, indent=2, sort_keys=True))
        return
    if args.decentralized is None or args.piano is None:
        raise ValueError("both Phase-3 arm payloads are required")
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
