"""Execute Phase-4 v2 with unchanged science and hardened provider formatting retries."""

from __future__ import annotations

import argparse
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from resonance.agents import DefaultPolicyGateway, InMemoryDecisionEventStore
from resonance.experiments.piano_phase2 import Phase2Config
from resonance.experiments.piano_phase2_zai import ZAIChatCompletionsBackend
from resonance.experiments.piano_phase4_authority import (
    Phase4AuthorityArm,
    Phase4AuthorityExperimentAgent,
)

from experiments.piano_society import phase4_authority_campaign as v1_campaign
from experiments.piano_society.phase3 import config_digest
from experiments.piano_society.phase4_authority_v2 import (
    analyze,
    materialize_authority_roles,
    validate_config,
)

_PAYLOAD_SCHEMA = "resonance-world-piano-phase4-authority-arm-v0.1"


def _backend(config: dict[str, Any], *, api_key: str) -> ZAIChatCompletionsBackend:
    backend = config["model_backend"]
    return ZAIChatCompletionsBackend(
        api_key=api_key,
        model_snapshot=str(config["required_model_snapshot"]),
        allowed_actions=tuple(str(value) for value in config["action_vocabulary"]),
        temperature=float(backend["temperature"]),
        timeout_seconds=float(backend["timeout_seconds"]),
        max_attempts=int(backend["max_attempts"]),
        retry_backoff_cap_seconds=float(backend["retry_backoff_cap_seconds"]),
        retry_contract_errors=bool(backend["retry_contract_errors"]),
        contract_retry_prompt_hardening=bool(backend["contract_retry_prompt_hardening"]),
        unique_request_id_per_attempt=bool(backend["unique_request_id_per_attempt"]),
    )


def _new_agent(
    *,
    arm: Phase4AuthorityArm,
    role: dict[str, Any],
    config: dict[str, Any],
    api_key: str,
    events: InMemoryDecisionEventStore,
) -> Phase4AuthorityExperimentAgent:
    return Phase4AuthorityExperimentAgent(
        arm=arm,
        backend=_backend(config, api_key=api_key),
        config=Phase2Config(
            trial_seed=int(role["trial_seed"]),
            required_model_snapshot=str(config["required_model_snapshot"]),
            max_output_tokens_per_call=int(config["max_output_tokens_per_call"]),
        ),
        traces=v1_campaign.EmptyTraceRepository(),
        events=events,
        gateway=DefaultPolicyGateway(),
    )


def _run_arm_case(
    *,
    arm: Phase4AuthorityArm,
    case_roles: list[dict[str, Any]],
    config: dict[str, Any],
    api_key: str,
) -> list[dict[str, object]]:
    events = InMemoryDecisionEventStore()
    ledger = v1_campaign._ledger_for_case(case_roles)
    observations = {}
    agent_ids = {}
    agents = {}
    prepared = {}
    for role in sorted(case_roles, key=lambda value: int(value["agent_index"])):
        index = int(role["agent_index"])
        observation = v1_campaign._observation(role, ledger)
        agent_id = uuid5(
            NAMESPACE_URL,
            f"resonance:piano-phase4-v2:{role['joint_case_id']}:{arm.value}:{index}",
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
    roles = [
        role for role in materialize_authority_roles(config) if role["joint_case_id"] == case_id
    ]
    case_seed = int(roles[0]["case_seed"])
    arm_order = (
        (Phase4AuthorityArm.UNSIGNED, Phase4AuthorityArm.ATTESTED)
        if case_seed % 2 == 1
        else (Phase4AuthorityArm.ATTESTED, Phase4AuthorityArm.UNSIGNED)
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
    by_arm: dict[str, list[dict[str, object]]] = {"unsigned": [], "attested": []}
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
    result = analyze(config, payloads["unsigned"], payloads["attested"])
    return payloads, result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    api_key = os.environ.get("ZAI_API_KEY", "")
    if not api_key:
        raise RuntimeError("ZAI_API_KEY is required for Phase 4 v2")
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
