"""Execute the locked PIANO Phase-2C controller-broadcast stress campaign."""

from __future__ import annotations

import argparse
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from resonance.agents import AgentObservation, DefaultPolicyGateway, InMemoryDecisionEventStore
from resonance.experiments.piano_phase2 import Phase2Config
from resonance.experiments.piano_phase2_intention_stress import (
    IntentionStressArm,
    IntentionStressExperimentAgent,
)
from resonance.experiments.piano_phase2_zai import ZAIChatCompletionsBackend

from experiments.piano_society.phase2c import (
    analyze,
    config_digest,
    materialize_cases,
    validate_config,
)

_PAYLOAD_SCHEMA = "resonance-world-piano-phase2c-intention-stress-arm-v0.1"
_OBSERVED_AT = datetime(2026, 8, 12, 12, 0, tzinfo=UTC)


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


def _observation(case: dict[str, Any]) -> AgentObservation:
    return AgentObservation(
        trigger=str(case["global_task"]),
        observed_at=_OBSERVED_AT,
        query_embedding=(0.0,) * 1536,
        metadata={
            "scenario_id": case["case_id"],
            "expected_action": case["expected_action"],
            "expected_outcome_status": case["expected_outcome_status"],
            "case_family": "controller-global-vs-channel-local",
            "advisory_variant": case["variant_id"],
            "shared_channel_context": case["shared_channel_context"],
            "speech_local_cue": case["speech_local_cue"],
            "action_local_cue": case["action_local_cue"],
        },
    )


def _run_arm(
    *,
    arm: IntentionStressArm,
    case: dict[str, Any],
    config: dict[str, Any],
    api_key: str,
) -> dict[str, object]:
    agent = IntentionStressExperimentAgent(
        arm=arm,
        backend=_backend(config, api_key=api_key),
        config=Phase2Config(
            trial_seed=int(case["trial_seed"]),
            required_model_snapshot=str(config["required_model_snapshot"]),
            max_output_tokens_per_call=int(config["max_output_tokens_per_call"]),
        ),
        traces=EmptyTraceRepository(),
        events=InMemoryDecisionEventStore(),
        gateway=DefaultPolicyGateway(),
    )
    agent_id = uuid5(NAMESPACE_URL, f"resonance:piano-phase2c:{case['case_id']}")
    return agent.step(agent_id, _observation(case)).to_world_record()


def _run_pair(
    case: dict[str, Any],
    *,
    config: dict[str, Any],
    api_key: str,
) -> tuple[dict[str, object], dict[str, object]]:
    baseline_first = int(case["trial_seed"]) % 2 == 1
    order = (
        (IntentionStressArm.BASELINE, IntentionStressArm.BROADCAST)
        if baseline_first
        else (IntentionStressArm.BROADCAST, IntentionStressArm.BASELINE)
    )
    records: dict[IntentionStressArm, dict[str, object]] = {}
    for arm in order:
        records[arm] = _run_arm(arm=arm, case=case, config=config, api_key=api_key)
    return records[IntentionStressArm.BASELINE], records[IntentionStressArm.BROADCAST]


def run(config: dict[str, Any], *, api_key: str):
    normalized = validate_config(config)
    cases = materialize_cases(config)
    baseline_records: list[dict[str, object]] = []
    broadcast_records: list[dict[str, object]] = []

    with ThreadPoolExecutor(max_workers=int(config["model_backend"]["max_workers"])) as executor:
        futures = [
            executor.submit(_run_pair, case, config=config, api_key=api_key)
            for case in cases
        ]
        for future in as_completed(futures):
            baseline, broadcast = future.result()
            baseline_records.append(baseline)
            broadcast_records.append(broadcast)

    order = {case["case_id"]: index for index, case in enumerate(cases)}
    baseline_records.sort(key=lambda record: order[str(record["scenario_id"])])
    broadcast_records.sort(key=lambda record: order[str(record["scenario_id"])])
    digest = config_digest(config)
    baseline_payload = {
        "schema": _PAYLOAD_SCHEMA,
        "arm": "baseline",
        "field_revision": normalized["field_revision"],
        "config_digest": digest,
        "records": baseline_records,
    }
    broadcast_payload = {
        "schema": _PAYLOAD_SCHEMA,
        "arm": "broadcast",
        "field_revision": normalized["field_revision"],
        "config_digest": digest,
        "records": broadcast_records,
    }
    result = analyze(config, baseline_payload, broadcast_payload)
    return baseline_payload, broadcast_payload, result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    api_key = os.environ.get("ZAI_API_KEY", "")
    if not api_key:
        raise RuntimeError("ZAI_API_KEY is required for Phase-2C")
    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    baseline, broadcast, result = run(config, api_key=api_key)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, payload in (("baseline", baseline), ("broadcast", broadcast)):
        (output_dir / f"{name}.json").write_text(
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
