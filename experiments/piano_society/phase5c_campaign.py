"""Execute the locked PIANO Phase-5C decision-relevant memory campaign."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from resonance_world import w5_institution as w5

from experiments.piano_society.phase3 import config_digest
from experiments.piano_society.phase5_zai import Phase5ZAIChatCompletionsBackend
from experiments.piano_society.phase5b_controller import (
    TransferableInstitutionalController,
    TransferControllerConfig,
)
from experiments.piano_society.phase5b_transfer_memory import (
    TransferPosterior,
    fit_transfer_posterior,
    forecast_strategies,
    neutral_posterior,
    select_forecast_strategy,
)
from experiments.piano_society.phase5c import analyze, materialize_units, validate_config

_PAYLOAD_SCHEMA = "resonance-world-piano-phase5c-arm-v0.1"
_RECORD_SCHEMA = "resonance-world-piano-phase5c-unit-v0.1"
_STRATEGIES = ("specialist", "balanced")


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


def _mission(unit: dict[str, Any], *, phase: str):
    return w5._mission(
        {
            "mission_id": f"phase5c-{phase}-{unit['unit_id']}",
            "context": unit["unit_id"],
            "lead_skill": unit["lead_skill"],
            "support_skill": unit["support_skill"],
            "regime": unit["hidden_regime"],
        }
    )


def _mission_text(unit: dict[str, Any]) -> str:
    return (
        f"context={unit['unit_id']}; lead_skill={unit['public_lead_skill']}; "
        f"support_skill={unit['public_support_skill']}"
    )


def _roster_views(roster, aliases: dict[str, str]) -> tuple[str, str]:
    model_rows = []
    audit_rows = []
    for index, member in enumerate(roster, start=1):
        model_rows.append(
            {
                "member": f"member-{index}",
                "practice": {
                    aliases[skill]: int(member.practice(skill))
                    for skill in sorted(aliases, key=lambda item: aliases[item])
                },
            }
        )
        audit_rows.append(
            {
                "agent_id": member.agent_id,
                "practice_by_skill": {
                    skill: int(member.practice(skill)) for skill in sorted(aliases)
                },
            }
        )
    return _canonical(model_rows), _digest(audit_rows)


def _memory_payload(organization, mission, posterior: TransferPosterior) -> dict[str, object]:
    forecasts = forecast_strategies(organization, mission, posterior)
    return {
        "structural_posterior": posterior.as_dict(),
        "current_roster_strategy_forecast": {
            strategy: float(forecasts[strategy]) for strategy in _STRATEGIES
        },
        "forecast_semantics": {
            "role_specific": (
                "success is explained by distinct lead-skill and support-skill role competence"
            ),
            "cross_coverage": (
                "success is explained by both selected members covering both mission skills"
            ),
        },
    }


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


def _prepare_unit(unit: dict[str, Any], design, config: dict[str, Any]) -> dict[str, Any]:
    formation = _mission(unit, phase="formation")
    trained = w5._organization(design, f"phase5c-live-{unit['field_id']}-{unit['unit_id']}")
    memory = config["institutional_model_memory"]
    w5._train(
        trained,
        [formation],
        int(memory["formation_depth"]),
        list(memory["formation_strategy_order"]),
        salt="phase5c-live-formation",
    )
    retained_posterior = fit_transfer_posterior(trained, formation)
    replacement_roster = tuple(design.replacement_roster(len(design.initial_members)))
    replacement = copy.deepcopy(trained)
    replacement.replace_members(list(replacement_roster))
    return {
        "replacement": replacement,
        "replacement_roster": replacement_roster,
        "evaluation": _mission(unit, phase="evaluation"),
        "retained_posterior": retained_posterior,
    }


def _run_arm(
    *,
    arm: str,
    unit: dict[str, Any],
    prepared: dict[str, Any],
    config: dict[str, Any],
    api_key: str,
) -> dict[str, object]:
    if arm == "model_retained":
        posterior = prepared["retained_posterior"]
    elif arm == "model_reset":
        posterior = neutral_posterior()
    else:
        raise ValueError(f"unsupported Phase-5C arm {arm!r}")

    organization = copy.deepcopy(prepared["replacement"])
    evaluation = prepared["evaluation"]
    aliases = {str(key): str(value) for key, value in config["skill_aliases"].items()}
    roster_text, roster_digest = _roster_views(prepared["replacement_roster"], aliases)
    mission_text = _mission_text(unit)
    memory_payload = _memory_payload(organization, evaluation, posterior)
    forecasts = memory_payload["current_roster_strategy_forecast"]
    if not isinstance(forecasts, dict):
        raise ValueError("Phase-5C forecast payload must be an object")
    preferred = select_forecast_strategy({str(k): float(v) for k, v in forecasts.items()})
    forecast_margin = abs(float(forecasts["specialist"]) - float(forecasts["balanced"]))
    decisive = forecast_margin > float(config["institutional_model_memory"]["decisive_forecast_epsilon"])

    strategy_order = tuple(str(item) for item in unit["strategy_order"])
    controller = TransferableInstitutionalController(
        backend=_make_backend(config, api_key=api_key, strategy_order=strategy_order),
        config=TransferControllerConfig(
            trial_seed=int(unit["trial_seed"]),
            required_model_snapshot=str(config["required_model_snapshot"]),
            strategy_order=(strategy_order[0], strategy_order[1]),
            max_output_tokens_per_call=int(config["max_output_tokens_per_call"]),
        ),
    )
    plan = controller.plan(
        mission_text=mission_text,
        roster_text=roster_text,
        memory_text=_canonical(memory_payload),
    )

    decision = w5._forced_decision(organization, evaluation.public, plan.strategy)
    environment = w5.InstitutionEnvironment()
    trials = int(config["institutional_model_memory"]["evaluation_trials_per_unit"])
    seeds = [
        w5._seed(unit["field_id"], "phase5c-live-evaluation", unit["unit_id"], trial)
        for trial in range(trials)
    ]
    outcomes = [
        environment.evaluate(
            decision.lead,
            decision.support,
            evaluation,
            seed=seed,
        )
        for seed in seeds
    ]
    success_count = sum(outcomes)
    success_rate = success_count / trials
    grounded_success = success_rate >= float(config["institutional_model_memory"]["grounded_success_threshold"])
    acknowledgement = (
        f"trials={trials}; successes={success_count}; success_rate={success_rate:.8f}; "
        f"grounded_success={str(grounded_success).lower()}"
    )
    report = controller.report_after_execution(plan, acknowledgement_text=acknowledgement)

    return {
        "schema": _RECORD_SCHEMA,
        "arm": arm,
        "unit_id": unit["unit_id"],
        "field_id": unit["field_id"],
        "trial_seed": unit["trial_seed"],
        "field_revision": config["field_revision"],
        "model_snapshot": config["required_model_snapshot"],
        "config_digest": config_digest(config),
        "strategy_order": list(strategy_order),
        "arm_order_label": unit["arm_order_label"],
        "replacement_roster_digest": roster_digest,
        "environment_trial_seed_digest": _digest(seeds),
        "model_visible": {
            "mission_text": mission_text,
            "roster_text": roster_text,
            "institutional_model_memory": memory_payload,
        },
        "audit": {
            "hidden_regime": unit["hidden_regime"],
            "target_hypothesis": unit["target_hypothesis"],
            "target_policy": unit["target_policy"],
            "neutral_preferred_policy": unit["neutral_preferred_policy"],
            "forecast_preferred_strategy": preferred,
            "forecast_margin": forecast_margin,
            "decisive_forecast": decisive,
            "intention": plan.intention,
            "intended_strategy": plan.intended_strategy,
            "speech": plan.speech,
            "speech_strategy": plan.speech_strategy,
            "chosen_strategy": plan.strategy,
            "confidence": plan.confidence,
            "evaluation_trials": trials,
            "success_count": success_count,
            "mission_success_rate": success_rate,
            "grounded_success": grounded_success,
            "post_action_report": report.report,
            "post_action_claims_success": report.claims_success,
            "environment_reads_memory": False,
            "evaluation_updates_memory": False,
        },
        "usage": {
            "calls": report.usage.calls,
            "input_tokens": report.usage.input_tokens,
            "output_tokens": report.usage.output_tokens,
            "latency_ms": report.usage.latency_ms,
        },
    }


def _run_pair(unit: dict[str, Any], *, prepared: dict[str, Any], config: dict[str, Any], api_key: str):
    result: dict[str, dict[str, object]] = {}
    for arm in unit["arm_order"]:
        result[str(arm)] = _run_arm(
            arm=str(arm),
            unit=unit,
            prepared=prepared,
            config=config,
            api_key=api_key,
        )
    return result


def run(config: dict[str, Any], capsules_path: str | Path, *, api_key: str):
    lock = validate_config(config)
    if _sha256_file(capsules_path) != lock["source_capsule_sha256"]:
        raise ValueError("Phase-5C frozen capsule bytes differ from scientific lock")
    units = materialize_units(config)
    fields = [str(unit["field_id"]) for unit in units]
    if len(set(fields)) != 12:
        raise ValueError("Phase-5C requires one distinct confirmatory organization per unit")
    designs = w5._load_designs(capsules_path, fields, 4)
    prepared = {
        unit["unit_id"]: _prepare_unit(unit, designs[unit["field_id"]], config)
        for unit in units
    }

    by_arm: dict[str, list[dict[str, object]]] = {arm: [] for arm in config["arms"]}
    with ThreadPoolExecutor(max_workers=int(config["model_backend"]["max_workers"])) as executor:
        future_map = {
            executor.submit(
                _run_pair,
                unit,
                prepared=prepared[unit["unit_id"]],
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
    payloads: dict[str, dict[str, object]] = {}
    for arm, records in by_arm.items():
        records.sort(key=lambda row: order[str(row["unit_id"])])
        payloads[arm] = {
            "schema": _PAYLOAD_SCHEMA,
            "arm": arm,
            "field_revision": config["field_revision"],
            "model_snapshot": config["required_model_snapshot"],
            "source_capsule_sha256": lock["source_capsule_sha256"],
            "config_digest": digest,
            "records": records,
        }
    result = analyze(config, payloads["model_reset"], payloads["model_retained"])
    return payloads, result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--capsules", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    api_key = os.environ.get("ZAI_API_KEY", "")
    if not api_key:
        raise RuntimeError("ZAI_API_KEY is required for Phase 5C")
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
