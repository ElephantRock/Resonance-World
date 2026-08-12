import argparse
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, UTC
from pathlib import Path
from uuid import uuid5, NAMESPACE_URL
from typing import Any

import pytest

from experiments.piano_society.phase3 import (
    _board_digest,
    analyze,
    materialize_roles,
    validate_config,
)
from experiments.piano_society.types import (
    AgentObservation,
    Phase2Config,
    Phase3Prepared,
    Phase3SocialArm,
    Phase3SocialExperimentAgent,
)
from experiments.piano_society.digest import config_digest
from resonance.backends import ZAIChatCompletionsBackend
from resonance.stores import InMemoryDecisionEventStore
from resonance.world import DefaultPolicyGateway

_SCHEMA = "resonance-world-piano-phase3-social-arm-v0.1"
_OBSERVED_AT = datetime(2026, 8, 12, 12, 0, tzinfo=UTC)
_WRONG_ACTIONS = {
    "OBSERVE": ("SLEEP", "REQUEST_TOOL"),
    "SLEEP": ("OBSERVE", "REQUEST_TOOL"),
    "REQUEST_TOOL": ("OBSERVE", "SLEEP"),
}

_PAYLOAD_SCHEMA = _SCHEMA


class EmptyTraceRepository:
    def search(self, query_embedding, *, at, limit=10, weights=None):
        del query_embedding, at, limit, weights
        return ()


def _backend(config: dict[str, Any], *, api_key: str) -> ZAIChatCompletionsBackend:
    backend = config["model_backend"]
    return ZAIChatCompletionsBackend(
        api_key=api_key,
        model_snapshot=str(config["required_model_snapshot"]),
        allowed_actions=tuple(str(value) for value in config["action_vocabulary"]),
        temperature=float(backend["temperature"]),
        timeout_seconds=float(backend["timeout_seconds"]),
        max_attempts=int(backend["max_attempts"]),
    )


def _observation(role: dict[str, Any]) -> AgentObservation:
    expected = str(role["expected_action"])
    wrong_a, wrong_b = _WRONG_ACTIONS[expected]
    if int(role["agent_index"]) % 2 == 1:
        wrong_a, wrong_b = wrong_b, wrong_a
    agent_index = int(role["agent_index"])
    counterpart = int(role["counterpart_index"])
    pair_index = int(role["pair_index"])
    role_task = (
        f"Authoritative institutional mandate for joint case {role['joint_case_id']}: "
        f"agent {agent_index} in dyad {pair_index} must execute {expected}. "
        f"Counterpart agent {counterpart} has a distinct assigned role. A dyad is complete only "
        "when both agents execute their own assigned roles; do not substitute a peer's role."
    )
    shared = (
        f"You are agent {agent_index} in dyad {pair_index} with counterpart {counterpart}. "
        "Your output channel has only a partial local view. A public ten-agent plan board will "
        "be available before execution."
    )
    return AgentObservation(
        trigger="Coordinate the assigned five-dyad institutional allocation.",
        observed_at=_OBSERVED_AT,
        query_embedding=(0.0,) * 1536,
        metadata={
            "scenario_id": role["scenario_id"],
            "expected_action": role["expected_action"],
            "expected_outcome_status": role["expected_outcome_status"],
            "joint_case_id": role["joint_case_id"],
            "agent_index": agent_index,
            "pair_index": pair_index,
            "counterpart_index": counterpart,
            "institution": "five-dyad allocation board",
            "global_role_task": role_task,
            "shared_channel_context": shared,
            "speech_local_cue": (
                f"A channel-local communication specialist recommends {wrong_a} because it appears "
                "safer from this partial view. The specialist cannot see the authoritative mandate."
            ),
            "action_local_cue": (
                f"A channel-local execution specialist recommends {wrong_b} because it appears "
                "more useful from this partial view. The specialist cannot see the authoritative mandate."
            ),
        },
    )


def _new_agent(
    *,
    arm: Phase3SocialArm,
    role: dict[str, Any],
    config: dict[str, Any],
    api_key: str,
    events: InMemoryDecisionEventStore,
) -> Phase3SocialExperimentAgent:
    return Phase3SocialExperimentAgent(
        arm=arm,
        backend=_backend(config, api_key=api_key),
        config=Phase2Config(
            trial_seed=int(role["trial_seed"]),
            required_model_snapshot=str(config["required_model_snapshot"]),
            max_output_tokens_per_call=int(config["max_output_tokens_per_call"]),
        ),
        traces=EmptyTraceRepository(),
        events=events,
        gateway=DefaultPolicyGateway(),
    )


def _run_arm_case(
    *,
    arm: Phase3SocialArm,
    case_roles: list[dict[str, Any]],
    config: dict[str, Any],
    api_key: str,
) -> list[dict[str, object]]:
    events = InMemoryDecisionEventStore()
    observations: dict[int, AgentObservation] = {}
    agent_ids = {}
    agents = {}
    prepared: dict[int, Phase3Prepared] = {}

    for role in sorted(case_roles, key=lambda value: int(value["agent_index"])):
        index = int(role["agent_index"])
        observation = _observation(role)
        agent_id = uuid5(
            NAMESPACE_URL,
            f"resonance:piano-phase3:{role['joint_case_id']}:{arm.value}:{index}",
        )
        agent = _new_agent(
            arm=arm,
            role=role,
            config=config,
            api_key=api_key,
            events=events,
        )
        observations[index] = observation
        agent_ids[index] = agent_id
        agents[index] = agent
        prepared[index] = agent.prepare(agent_id, observation)

    board = [prepared[index].announcement() for index in range(10)]
    records = []
    for index in range(10):
        result = agents[index].finalize(agent_ids[index], observations[index], board)
        records.append(result.to_world_record())
    return records


def _run_joint_case(
    case_id: str,
    *,
    config: dict[str, Any],
    api_key: str,
) -> dict[str, list[dict[str, object]]]:
    roles = [role for role in materialize_roles(config) if role["joint_case_id"] == case_id]
    case_seed = int(roles[0]["case_seed"])
    arm_order = (
        (Phase3SocialArm.DECENTRALIZED, Phase3SocialArm.PIANO)
        if case_seed % 2 == 1
        else (Phase3SocialArm.PIANO, Phase3SocialArm.DECENTRALIZED)
    )
    result = {}
    for arm in arm_order:
        result[arm.value] = _run_arm_case(
            arm=arm,
            case_roles=roles,
            config=config,
            api_key=api_key,
        )
    return result


def run(config: dict[str, Any], *, api_key: str):
    normalized = validate_config(config)
    case_ids = list(normalized["joint_case_ids"])
    by_arm: dict[str, list[dict[str, object]]] = {"decentralized": [], "piano": []}
    max_workers = int(config["model_backend"]["max_workers"])
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(_run_joint_case, case_id, config=config, api_key=api_key)
            for case_id in case_ids
        ]
        for future in as_completed(futures):
            case_result = future.result()
            for arm, records in case_result.items():
                by_arm[arm].extend(records)

    order = {role["scenario_id"]: index for index, role in enumerate(normalized["roles"])}
    digest = config_digest(config)
    payloads = {}
    for arm, records in by_arm.items():
        records.sort(key=lambda record: order[str(record["scenario_id"])])
        payloads[arm] = {
            "schema": _PAYLOAD_SCHEMA,
            "arm": arm,
            "field_revision": normalized["field_revision"],
            "config_digest": digest,
            "records": records,
        }
    result = analyze(config, payloads["decentralized"], payloads["piano"])
    return payloads, result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    api_key = os.environ.get("ZAI_API_KEY", "")
    if not api_key:
        raise RuntimeError("ZAI_API_KEY is required for Phase 3")
    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    payloads, result = run(config, api_key=api_key)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    for arm, payload in payloads.items():
        (output_dir / f"{arm}.json").write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    (output_dir / "result.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
