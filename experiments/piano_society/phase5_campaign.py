"""Execute the locked PIANO Phase-5 institutional-memory campaign."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from resonance.experiments.piano_phase4_authority import Phase4AuthorityArm

from resonance_world import w5_institution as w5

from experiments.piano_society.phase3 import config_digest
from experiments.piano_society.phase5 import analyze, materialize_units, validate_config
from experiments.piano_society.phase5_controller import (
    InstitutionalControllerConfig,
    InstitutionalPianoController,
)
from experiments.piano_society.phase5_zai import Phase5ZAIChatCompletionsBackend

_PAYLOAD_SCHEMA = "resonance-world-piano-phase5-memory-arm-v0.1"
_RECORD_SCHEMA = "resonance-world-piano-phase5-memory-unit-v0.1"


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical(value).encode()).hexdigest()


def _sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _formation_missions(config: dict[str, Any]):
    return [
        w5._mission(
            {
                "mission_id": row["formation_mission_id"],
                "context": row["context"],
                "lead_skill": row["lead_skill"],
                "support_skill": row["support_skill"],
                "regime": row["hidden_regime"],
            }
        )
        for row in config["missions"]
    ]


def _evaluation_mission(row: dict[str, Any]):
    return w5._mission(
        {
            "mission_id": row["mission_id"],
            "context": row["context"],
            "lead_skill": row["lead_skill"],
            "support_skill": row["support_skill"],
            "regime": row["hidden_regime"],
        }
    )


def _historical_stats(organization, context: str) -> dict[str, dict[str, object]]:
    attempts = organization.memory.strategy_attempts.get(context, {})
    successes = organization.memory.strategy_successes.get(context, {})
    result: dict[str, dict[str, object]] = {}
    for strategy in ("specialist", "balanced"):
        attempt_count = int(attempts.get(strategy, 0))
        success_count = int(successes.get(strategy, 0))
        if attempt_count <= 0:
            raise ValueError("Phase-5 formation failed to create binary procedure history")
        result[strategy] = {
            "attempts": attempt_count,
            "successes": success_count,
            "rate": success_count / attempt_count,
        }
    return result


def _memory_text(stats: dict[str, dict[str, object]], arm: str) -> str:
    if arm == "memory_retained":
        value = stats
    elif arm == "memory_reset":
        value = {
            strategy: {"attempts": 0, "successes": 0, "rate": None}
            for strategy in ("specialist", "balanced")
        }
    else:
        raise ValueError(f"unsupported Phase-5 arm {arm!r}")
    return _canonical(value)


def _mission_text(mission: dict[str, Any]) -> str:
    return (
        f"context={mission['context']}; lead_skill={mission['public_lead_skill']}; "
        f"support_skill={mission['public_support_skill']}"
    )


def _roster_views(roster, aliases: dict[str, str]):
    model_rows = []
    audit_rows = []
    label_by_agent: dict[str, str] = {}
    for index, member in enumerate(roster):
        label = f"member-{index}"
        label_by_agent[member.agent_id] = label
        public_practice = {
            aliases[skill]: int(member.practice(skill))
            for skill in sorted(aliases, key=lambda item: aliases[item])
        }
        model_rows.append({"member": label, "practice": public_practice})
        audit_rows.append(
            {
                "agent_id": member.agent_id,
                "practice_by_skill": {
                    skill: int(member.practice(skill)) for skill in sorted(aliases)
                },
            }
        )
    return _canonical(model_rows), _digest(audit_rows), label_by_agent


def _make_backend(config: dict[str, Any], *, api_key: str, strategy_order: tuple[str, ...]):
    backend = config["model_backend"]
    return Phase5ZAIChatCompletionsBackend(
        api_key=api_key,
        model_snapshot=config["required_model_snapshot"],
        allowed_actions=strategy_order,
        temperature=float(backend["temperature"]),
        timeout_seconds=float(backend["timeout_seconds"]),
        max_attempts=int(backend["max_attempts"]),
        retry_backoff_cap_seconds=float(backend["retry_backoff_cap_seconds"]),
        retry_contract_errors=bool(backend["retry_contract_errors"]),
        contract_retry_prompt_hardening=bool(backend["contract_retry_prompt_hardening"]),
        unique_request_id_per_attempt=bool(backend["unique_request_id_per_attempt"]),
    )


def _run_arm(
    *,
    arm: str,
    unit: dict[str, Any],
    trained,
    replacement_roster,
    config: dict[str, Any],
    api_key: str,
) -> dict[str, object]:
    organization = copy.deepcopy(trained)
    organization.replace_members(list(replacement_roster))
    historical_stats = _historical_stats(trained, str(unit["mission"]["context"]))
    if arm == "memory_reset":
        organization.reset_memory()
    elif arm != "memory_retained":
        raise ValueError(f"unsupported Phase-5 arm {arm!r}")

    mission = dict(unit["mission"])
    aliases = {str(k): str(v) for k, v in config["skill_aliases"].items()}
    roster_text, roster_digest, label_by_agent = _roster_views(replacement_roster, aliases)
    mission_text = _mission_text(mission)
    memory_text = _memory_text(historical_stats, arm)
    strategy_order = tuple(str(item) for item in unit["strategy_order"])
    backend = _make_backend(config, api_key=api_key, strategy_order=strategy_order)
    controller = InstitutionalPianoController(
        backend=backend,
        config=InstitutionalControllerConfig(
            trial_seed=int(unit["trial_seed"]),
            required_model_snapshot=config["required_model_snapshot"],
            strategy_order=strategy_order,
            max_output_tokens_per_call=int(config["max_output_tokens_per_call"]),
        ),
    )
    plan = controller.plan(
        mission_text=mission_text,
        roster_text=roster_text,
        memory_text=memory_text,
    )

    evaluation_mission = _evaluation_mission(mission)
    decision = w5._forced_decision(organization, evaluation_mission.public, plan.strategy)
    environment = w5.InstitutionEnvironment()
    seeds = [
        w5._seed(
            unit["field_id"],
            "phase5-evaluation",
            int(unit["mission_index"]),
            trial,
        )
        for trial in range(128)
    ]
    outcomes = [
        environment.evaluate(
            decision.lead,
            decision.support,
            evaluation_mission,
            seed=seed,
        )
        for seed in seeds
    ]
    success_count = sum(outcomes)
    success_rate = success_count / 128.0
    grounded_success = success_rate >= float(
        config["institutional_memory"]["grounded_success_threshold"]
    )
    acknowledgement = (
        f"trials=128; successes={success_count}; success_rate={success_rate:.8f}; "
        f"grounded_success={str(grounded_success).lower()}"
    )
    report = controller.report_after_execution(plan, acknowledgement_text=acknowledgement)
    historical_best = max(
        (
            float(historical_stats[strategy]["rate"]),
            int(historical_stats[strategy]["attempts"]),
            strategy,
        )
        for strategy in ("specialist", "balanced")
    )[2]
    return {
        "schema": _RECORD_SCHEMA,
        "arm": arm,
        "unit_id": unit["unit_id"],
        "field_id": unit["field_id"],
        "mission_id": mission["mission_id"],
        "trial_seed": unit["trial_seed"],
        "model_snapshot": config["required_model_snapshot"],
        "strategy_order": list(strategy_order),
        "strategy_order_label": unit["strategy_order_label"],
        "arm_order_label": unit["arm_order_label"],
        "intention": plan.intention,
        "intended_strategy": plan.intended_strategy,
        "speech": plan.speech,
        "speech_strategy": plan.speech_strategy,
        "selected_strategy": plan.strategy,
        "confidence": plan.confidence,
        "selected_lead_member": label_by_agent[decision.lead.agent_id],
        "selected_support_member": label_by_agent[decision.support.agent_id],
        "roster_digest": roster_digest,
        "environment_seed_digest": _digest(seeds),
        "evaluation_trials": 128,
        "success_count": success_count,
        "mission_success_rate": success_rate,
        "grounded_success": grounded_success,
        "post_action_report": report.report,
        "post_action_claims_success": report.claims_success,
        "historical_best_strategy": historical_best,
        "model_visible": {
            "mission_text": mission_text,
            "roster_text": roster_text,
            "memory_text": memory_text,
        },
        "audit": {
            "historical_strategy_stats": historical_stats,
            "hidden_regime": mission["hidden_regime"],
            "real_lead_skill": mission["lead_skill"],
            "real_support_skill": mission["support_skill"],
            "evaluation_updates_memory": False,
            "environment_reads_memory": False,
        },
        "usage": {
            "calls": report.usage.calls,
            "input_tokens": report.usage.input_tokens,
            "output_tokens": report.usage.output_tokens,
            "latency_ms": report.usage.latency_ms,
        },
    }


def _run_paired_unit(
    unit: dict[str, Any],
    *,
    trained,
    replacement_roster,
    config: dict[str, Any],
    api_key: str,
) -> dict[str, dict[str, object]]:
    result: dict[str, dict[str, object]] = {}
    for arm in unit["arm_order"]:
        result[str(arm)] = _run_arm(
            arm=str(arm),
            unit=unit,
            trained=trained,
            replacement_roster=replacement_roster,
            config=config,
            api_key=api_key,
        )
    return result


def run(config: dict[str, Any], capsules_path: str | Path, *, api_key: str):
    normalized = validate_config(config)
    if _sha256_file(capsules_path) != normalized["source_capsule_sha256"]:
        raise ValueError("Phase-5 frozen capsule bytes differ from scientific lock")
    fields = [str(item) for item in config["source_lock"]["confirmatory_fields"]]
    designs = w5._load_designs(capsules_path, fields, 4)
    formation = _formation_missions(config)
    trained_by_field = {}
    replacement_by_field = {}
    for field_id in fields:
        design = designs[field_id]
        organization = w5._organization(design, f"phase5-org-{field_id}")
        w5._train(
            organization,
            formation,
            int(config["institutional_memory"]["formation_depth"]),
            list(config["institutional_memory"]["formation_strategy_order"]),
            salt="phase5-formation",
        )
        trained_by_field[field_id] = organization
        replacement_by_field[field_id] = tuple(
            design.replacement_roster(len(design.initial_members))
        )

    units = materialize_units(config)
    by_arm: dict[str, list[dict[str, object]]] = {arm: [] for arm in config["arms"]}
    max_workers = int(config["model_backend"]["max_workers"])
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_map = {
            executor.submit(
                _run_paired_unit,
                unit,
                trained=trained_by_field[unit["field_id"]],
                replacement_roster=replacement_by_field[unit["field_id"]],
                config=config,
                api_key=api_key,
            ): unit["unit_id"]
            for unit in units
        }
        for future in as_completed(future_map):
            pair = future.result()
            for arm, record in pair.items():
                by_arm[arm].append(record)

    order = {unit["unit_id"]: index for index, unit in enumerate(units)}
    digest = config_digest(config)
    payloads = {}
    for arm, records in by_arm.items():
        records.sort(key=lambda row: order[str(row["unit_id"])])
        payloads[arm] = {
            "schema": _PAYLOAD_SCHEMA,
            "arm": arm,
            "field_revision": normalized["field_revision"],
            "source_capsule_sha256": normalized["source_capsule_sha256"],
            "config_digest": digest,
            "records": records,
        }
    result = analyze(config, payloads["memory_reset"], payloads["memory_retained"])
    return payloads, result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--capsules", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    api_key = os.environ.get("ZAI_API_KEY", "")
    if not api_key:
        raise RuntimeError("ZAI_API_KEY is required for Phase 5")
    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    payloads, result = run(config, args.capsules, api_key=api_key)
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
