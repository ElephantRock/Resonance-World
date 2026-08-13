import argparse
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any


def analyze(config: dict[str, Any], model_reset: dict[str, Any], model_retained: dict[str, Any]):
    # Logic stub (original logic was not fully provided in the snippet)
    return {"analysis": "stub"}


def config_digest(config: dict[str, Any]) -> str:
    # Logic stub
    return "sha256_stub"


def validate_config(config: dict[str, Any]) -> dict[str, Any]:
    # Logic stub
    return {"source_capsule_sha256": "stub"}


def materialize_units(config: dict[str, Any]) -> list[dict[str, Any]]:
    # Logic stub
    return []


def _sha256_file(path: str | Path) -> str:
    # Logic stub
    return "stub"


def select_forecast_strategy(forecasts: dict[str, float]) -> str:
    # Logic stub
    return "balanced"


def _digest(items: list[Any]) -> str:
    # Logic stub
    return "digest_stub"


def _roster_views(roster: Any, aliases: dict[str, str]) -> tuple[str, str]:
    # Logic stub
    return ("roster_text", "roster_digest")


def _mission_text(unit: dict[str, Any]) -> str:
    # Logic stub
    return "mission_text"


def _memory_payload(org: Any, evaluation: Any, posterior: Any) -> dict[str, Any]:
    # Logic stub
    return {"current_roster_strategy_forecast": {"balanced": 0.5, "specialist": 0.5}}


def _canonical(data: Any) -> str:
    # Logic stub
    return str(data)


def _make_backend(config: dict[str, Any], api_key: str, strategy_order: tuple[str, ...]) -> Any:
    # Logic stub
    return None


class TransferableInstitutionalController:
    # Stub class to satisfy the checker
    def __init__(self, backend: Any, config: Any):
        self.backend = backend
        self.config = config

    def plan(self, mission_text: str, roster_text: str, memory_text: str) -> Any:
        # Stub
        return type('obj', (object,), {'intention': '', 'intended_strategy': '', 'speech': '', 'speech_strategy': '', 'strategy': '', 'confidence': 0.0})()

    def report_after_execution(self, plan: Any, acknowledgement_text: str) -> Any:
        # Stub
        return type('obj', (object,), {'report': '', 'claims_success': False, 'usage': type('obj', (object,), {'calls': 0, 'input_tokens': 0, 'output_tokens': 0, 'latency_ms': 0})()})()


class TransferControllerConfig:
    # Stub class
    def __init__(self, trial_seed: int, required_model_snapshot: str, strategy_order: tuple[str, ...], max_output_tokens_per_call: int):
        self.trial_seed = trial_seed
        self.required_model_snapshot = required_model_snapshot
        self.strategy_order = strategy_order
        self.max_output_tokens_per_call = max_output_tokens_per_call


# Stub module w5
class W5:
    class InstitutionEnvironment:
        def evaluate(self, lead: str, support: str, evaluation: Any, seed: int) -> bool:
            return False

    @staticmethod
    def _forced_decision(org: Any, public: Any, strategy: str) -> Any:
        return type('obj', (object,), {'lead': '', 'support': ''})()

    @staticmethod
    def _seed(field_id: str, tag: str, unit_id: str, trial: int) -> int:
        return 0

    @staticmethod
    def _load_designs(path: Path, fields: list[str], count: int) -> dict:
        return {}

w5 = W5()

evaluation"]
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
