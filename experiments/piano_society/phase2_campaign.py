"""Execute the locked one-agent PIANO Phase-2-ZAI paired campaign."""

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
from resonance.experiments.piano_phase2 import Phase2Arm, Phase2Config, Phase2ExperimentAgent
from resonance.experiments.piano_phase2_zai import ZAIChatCompletionsBackend

from experiments.piano_society.phase2 import analyze, config_digest, validate_config

_PAYLOAD_SCHEMA = "resonance-world-piano-phase2-campaign-arm-v0.1"
_OBSERVED_AT = datetime(2026, 8, 12, 12, 0, tzinfo=UTC)


class EmptyTraceRepository:
    """Fresh zero-trace substrate used by every preregistered one-step episode."""

    def search(self, query_embedding, *, at, limit=10, weights=None):
        del query_embedding, at, limit, weights
        return ()


def _backend_config(config: dict[str, Any]) -> dict[str, Any]:
    value = config.get("model_backend")
    if not isinstance(value, dict):
        raise ValueError("locked Phase-2 config requires model_backend")
    expected = {
        "provider": "zai",
        "endpoint": "coding_chat_completions",
        "base_url": "https://api.z.ai/api/coding/paas/v4",
        "structured_output": "json_object_local_schema_validation",
        "thinking": "disabled",
        "do_sample": False,
        "provider_seed_supported": False,
        "trial_seed_role": "pair_identifier_only",
        "model_id_stability": "provider_alias_without_dated_snapshot",
        "retry_timeout": True,
        "pair_order": "counterbalanced_by_seed_parity",
    }
    for key, required in expected.items():
        if value.get(key) != required:
            raise ValueError(f"model_backend.{key} must equal {required!r}")
    temperature = value.get("temperature")
    if temperature != 0.0:
        raise ValueError("Phase-2-ZAI requires model_backend.temperature == 0.0")
    timeout_seconds = value.get("timeout_seconds")
    if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, (int, float)):
        raise ValueError("model_backend.timeout_seconds must be numeric")
    if timeout_seconds <= 0:
        raise ValueError("model_backend.timeout_seconds must be positive")
    max_attempts = value.get("max_attempts")
    if isinstance(max_attempts, bool) or not isinstance(max_attempts, int) or max_attempts <= 0:
        raise ValueError("model_backend.max_attempts must be positive")
    workers = value.get("max_workers")
    if isinstance(workers, bool) or not isinstance(workers, int) or workers <= 0:
        raise ValueError("model_backend.max_workers must be positive")
    return value


def _observation(scenario: dict[str, Any]) -> AgentObservation:
    return AgentObservation(
        trigger=str(scenario["trigger"]),
        observed_at=_OBSERVED_AT,
        query_embedding=(0.0,) * 1536,
        metadata={
            "scenario_id": scenario["scenario_id"],
            "expected_action": scenario["expected_action"],
            "expected_outcome_status": scenario["expected_outcome_status"],
        },
    )


def _run_arm(
    *,
    arm: Phase2Arm,
    scenario: dict[str, Any],
    seed: int,
    api_key: str,
    model_snapshot: str,
    action_vocabulary: tuple[str, ...],
    max_output_tokens: int,
    temperature: float,
    timeout_seconds: float,
    max_attempts: int,
) -> dict[str, object]:
    backend = ZAIChatCompletionsBackend(
        api_key=api_key,
        model_snapshot=model_snapshot,
        allowed_actions=action_vocabulary,
        temperature=temperature,
        timeout_seconds=timeout_seconds,
        max_attempts=max_attempts,
    )
    agent = Phase2ExperimentAgent(
        arm=arm,
        backend=backend,
        config=Phase2Config(
            trial_seed=seed,
            required_model_snapshot=model_snapshot,
            max_output_tokens_per_call=max_output_tokens,
        ),
        traces=EmptyTraceRepository(),
        events=InMemoryDecisionEventStore(),
        gateway=DefaultPolicyGateway(),
    )
    agent_id = uuid5(NAMESPACE_URL, f"resonance:piano-phase2-zai:{scenario['scenario_id']}:{seed}")
    return agent.step(agent_id, _observation(scenario)).to_world_record()


def _run_pair(
    *,
    scenario: dict[str, Any],
    seed: int,
    api_key: str,
    model_snapshot: str,
    action_vocabulary: tuple[str, ...],
    max_output_tokens: int,
    temperature: float,
    timeout_seconds: float,
    max_attempts: int,
) -> tuple[dict[str, object], dict[str, object]]:
    kwargs = {
        "scenario": scenario,
        "seed": seed,
        "api_key": api_key,
        "model_snapshot": model_snapshot,
        "action_vocabulary": action_vocabulary,
        "max_output_tokens": max_output_tokens,
        "temperature": temperature,
        "timeout_seconds": timeout_seconds,
        "max_attempts": max_attempts,
    }
    order = (
        (Phase2Arm.CONTROL, Phase2Arm.TREATMENT)
        if seed % 2
        else (Phase2Arm.TREATMENT, Phase2Arm.CONTROL)
    )
    records: dict[Phase2Arm, dict[str, object]] = {}
    for arm in order:
        records[arm] = _run_arm(arm=arm, **kwargs)
    return records[Phase2Arm.CONTROL], records[Phase2Arm.TREATMENT]


def run(
    config: dict[str, Any],
    *,
    api_key: str,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    normalized = validate_config(config)
    if not normalized["campaign_locked"]:
        raise ValueError("campaign must be locked before live execution")
    backend = _backend_config(config)
    model_snapshot = normalized["required_model_snapshot"]
    if not isinstance(model_snapshot, str) or not model_snapshot:
        raise ValueError("locked campaign requires required_model_snapshot")
    vocabulary_raw = config.get("action_vocabulary")
    if not isinstance(vocabulary_raw, list) or not vocabulary_raw:
        raise ValueError("action_vocabulary must be a non-empty list")
    action_vocabulary = tuple(str(value) for value in vocabulary_raw)
    max_output_tokens = int(config["max_output_tokens_per_call"])
    temperature = float(backend["temperature"])
    timeout_seconds = float(backend["timeout_seconds"])
    max_attempts = int(backend["max_attempts"])
    scenarios = [dict(value) for value in config["scenarios"]]
    seeds = [int(value) for value in config["seeds"]]
    scenario_order = {
        scenario["scenario_id"]: index for index, scenario in enumerate(scenarios)
    }

    control_records: list[dict[str, object]] = []
    treatment_records: list[dict[str, object]] = []
    futures = []
    with ThreadPoolExecutor(max_workers=int(backend["max_workers"])) as executor:
        for scenario in scenarios:
            for seed in seeds:
                futures.append(
                    executor.submit(
                        _run_pair,
                        scenario=scenario,
                        seed=seed,
                        api_key=api_key,
                        model_snapshot=model_snapshot,
                        action_vocabulary=action_vocabulary,
                        max_output_tokens=max_output_tokens,
                        temperature=temperature,
                        timeout_seconds=timeout_seconds,
                        max_attempts=max_attempts,
                    )
                )
        for future in as_completed(futures):
            control, treatment = future.result()
            control_records.append(control)
            treatment_records.append(treatment)

    def sort_key(record: dict[str, object]) -> tuple[int, int]:
        return (
            scenario_order[str(record["scenario_id"])],
            int(record["trial_seed"]),
        )

    control_records.sort(key=sort_key)
    treatment_records.sort(key=sort_key)
    field_revision = normalized["field_revision"]
    digest = config_digest(config)
    control_payload = {
        "schema": _PAYLOAD_SCHEMA,
        "arm": "control",
        "field_revision": field_revision,
        "config_digest": digest,
        "records": control_records,
    }
    treatment_payload = {
        "schema": _PAYLOAD_SCHEMA,
        "arm": "treatment",
        "field_revision": field_revision,
        "config_digest": digest,
        "records": treatment_records,
    }
    result = analyze(config, control_payload, treatment_payload)
    return control_payload, treatment_payload, result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    api_key = os.environ.get("ZAI_API_KEY", "")
    if not api_key:
        raise RuntimeError("ZAI_API_KEY is required for the locked Phase-2-ZAI campaign")
    config_path = Path(args.config)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        raise ValueError("Phase-2 config must be a JSON object")
    control, treatment, result = run(config, api_key=api_key)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, value in (
        ("control.json", control),
        ("treatment.json", treatment),
        ("result.json", result),
    ):
        (output_dir / name).write_text(
            json.dumps(value, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
