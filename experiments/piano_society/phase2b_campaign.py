"""Execute the locked four-arm one-agent PIANO Phase-2B campaign."""

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
from resonance.experiments.piano_phase2_factorial import (
    Phase2FactorialArm,
    Phase2FactorialExperimentAgent,
)
from resonance.experiments.piano_phase2_zai import ZAIChatCompletionsBackend

from experiments.piano_society.phase2b import (
    analyze,
    config_digest,
    materialize_cases,
    validate_config,
)

_PAYLOAD_SCHEMA = "resonance-world-piano-phase2b-factorial-arm-v0.1"
_OBSERVED_AT = datetime(2026, 8, 12, 12, 0, tzinfo=UTC)
_ARM_BY_NAME = {
    "baseline": Phase2FactorialArm.BASELINE,
    "intention_only": Phase2FactorialArm.INTENTION_ONLY,
    "ack_only": Phase2FactorialArm.ACK_ONLY,
    "full": Phase2FactorialArm.FULL,
}
_LATIN_ORDERS = (
    ("baseline", "intention_only", "ack_only", "full"),
    ("intention_only", "full", "baseline", "ack_only"),
    ("ack_only", "baseline", "full", "intention_only"),
    ("full", "ack_only", "intention_only", "baseline"),
)


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
        trigger=str(case["trigger"]),
        observed_at=_OBSERVED_AT,
        query_embedding=(0.0,) * 1536,
        metadata={
            "scenario_id": case["case_id"],
            "expected_action": case["expected_action"],
            "expected_outcome_status": case["expected_outcome_status"],
            "challenge_family": case["challenge_family"],
            "distractor_variant": case["variant_id"],
            "evidence_state": "current policy conflicts with a stale or misleading cue",
        },
    )


def _run_arm(
    *,
    arm_name: str,
    case: dict[str, Any],
    config: dict[str, Any],
    api_key: str,
) -> dict[str, object]:
    backend = _backend(config, api_key=api_key)
    agent = Phase2FactorialExperimentAgent(
        arm=_ARM_BY_NAME[arm_name],
        backend=backend,
        config=Phase2Config(
            trial_seed=int(case["trial_seed"]),
            required_model_snapshot=str(config["required_model_snapshot"]),
            max_output_tokens_per_call=int(config["max_output_tokens_per_call"]),
        ),
        traces=EmptyTraceRepository(),
        events=InMemoryDecisionEventStore(),
        gateway=DefaultPolicyGateway(),
    )
    agent_id = uuid5(NAMESPACE_URL, f"resonance:piano-phase2b:{case['case_id']}")
    return agent.step(agent_id, _observation(case)).to_world_record()


def _run_case(
    case: dict[str, Any],
    *,
    config: dict[str, Any],
    api_key: str,
) -> dict[str, dict[str, object]]:
    index = (int(case["trial_seed"]) - int(config["case_seed_start"])) % 4
    order = _LATIN_ORDERS[index]
    records: dict[str, dict[str, object]] = {}
    for arm_name in order:
        records[arm_name] = _run_arm(
            arm_name=arm_name,
            case=case,
            config=config,
            api_key=api_key,
        )
    return records


def run(config: dict[str, Any], *, api_key: str):
    normalized = validate_config(config)
    cases = materialize_cases(config)
    by_arm: dict[str, list[dict[str, object]]] = {arm: [] for arm in _ARM_BY_NAME}
    with ThreadPoolExecutor(max_workers=int(config["model_backend"]["max_workers"])) as executor:
        futures = [
            executor.submit(_run_case, case, config=config, api_key=api_key)
            for case in cases
        ]
        for future in as_completed(futures):
            records = future.result()
            for arm, record in records.items():
                by_arm[arm].append(record)

    order = {case["case_id"]: index for index, case in enumerate(cases)}
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
    result = analyze(config, payloads)
    return payloads, result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    api_key = os.environ.get("ZAI_API_KEY", "")
    if not api_key:
        raise RuntimeError("ZAI_API_KEY is required for Phase-2B")
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
