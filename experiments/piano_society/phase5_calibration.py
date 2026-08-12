"""Pre-inference deterministic capability calibration for PIANO Phase 5.

Fresh Field sources enter through Experiment 063; this module performs no model calls.
"""

from __future__ import annotations

import argparse
import copy
import json
import statistics
from pathlib import Path
from typing import Any

from resonance_world import w5_institution as w5
from resonance_world.w5a_organization import STRATEGIES


def _read(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def calibrate(capsules_path: str | Path, missions_path: str | Path) -> dict[str, Any]:
    config = _read(missions_path)
    calibration_fields = [str(item) for item in config["calibration_fields"]]
    confirmatory_fields = [str(item) for item in config["confirmatory_fields"]]
    if set(calibration_fields) & set(confirmatory_fields):
        raise ValueError("calibration and confirmatory fields must be disjoint")
    if len(calibration_fields) != 2 or len(confirmatory_fields) != 6:
        raise ValueError("Phase 5 requires 2 calibration and 6 untouched confirmatory fields")

    formation = [w5._mission(dict(row)) for row in config["formation"]]
    evaluation = [w5._mission(dict(row)) for row in config["evaluation"]]
    if len(formation) != 4 or len(evaluation) != 4:
        raise ValueError("Phase 5 calibration requires four formation/evaluation contexts")
    if [mission.public.context for mission in formation] != [
        mission.public.context for mission in evaluation
    ]:
        raise ValueError("formation and evaluation contexts must match in fixed order")

    depth = int(config["formation_depth"])
    trials = int(config["evaluation_trials_per_strategy"])
    strategy_order = [str(item) for item in config["formation_strategy_order"]]
    if depth != 12 or trials != 128 or tuple(strategy_order) != STRATEGIES:
        raise ValueError("Phase 5 calibration training/evaluation constants differ from lock")

    designs = w5._load_designs(capsules_path, calibration_fields, 4)
    environment = w5.InstitutionEnvironment()
    unit_rows: list[dict[str, Any]] = []
    for field_id in calibration_fields:
        design = designs[field_id]
        trained = w5._organization(design, f"phase5-calibration-{field_id}")
        w5._train(
            trained,
            formation,
            depth,
            strategy_order,  # type: ignore[arg-type]
            salt="phase5-capability-formation",
        )
        replacement = design.replacement_roster(len(design.initial_members))
        retained = copy.deepcopy(trained)
        retained.replace_members(replacement)

        for mission_index, mission in enumerate(evaluation):
            values: dict[str, float] = {}
            for strategy in STRATEGIES:
                decision = w5._forced_decision(retained, mission.public, strategy)
                outcomes = []
                for trial in range(trials):
                    outcomes.append(
                        float(
                            environment.evaluate(
                                decision.lead,
                                decision.support,
                                mission,
                                seed=w5._seed(
                                    field_id,
                                    "phase5-capability-eval",
                                    mission_index,
                                    trial,
                                ),
                            )
                        )
                    )
                values[strategy] = statistics.mean(outcomes)

            historical_best = trained.memory.best_strategy(mission.public.context)
            if historical_best is None:
                raise ValueError("formation failed to create context-indexed procedure memory")
            attempts = trained.memory.strategy_attempts[mission.public.context]
            successes = trained.memory.strategy_successes[mission.public.context]
            historical_rates = {
                strategy: successes[strategy] / attempts[strategy]
                for strategy in STRATEGIES
            }
            historical_value = values[historical_best]
            uniform_mean = statistics.mean(values.values())
            oracle_value = max(values.values())
            unit_rows.append(
                {
                    "field_id": field_id,
                    "mission_id": mission.public.mission_id,
                    "context": mission.public.context,
                    "hidden_regime": mission.regime,
                    "historical_success_rates": historical_rates,
                    "historical_best_strategy": historical_best,
                    "replacement_strategy_success_rates": values,
                    "historical_best_replacement_value": historical_value,
                    "uniform_strategy_mean": uniform_mean,
                    "oracle_replacement_value": oracle_value,
                    "historical_best_lift_over_uniform": historical_value - uniform_mean,
                    "oracle_gap": oracle_value - historical_value,
                }
            )

    acceptance = config["calibration_acceptance"]
    required_units = int(acceptance["required_units"])
    if len(unit_rows) != required_units:
        raise ValueError("Phase 5 calibration unit count differs from preregistration")
    lifts = [float(row["historical_best_lift_over_uniform"]) for row in unit_rows]
    mean_lift = statistics.mean(lifts)
    nonnegative_units = sum(value >= 0.0 for value in lifts)
    accepted = (
        mean_lift
        >= float(acceptance["min_mean_historical_best_lift_over_uniform_strategy_mean"])
        and nonnegative_units >= int(acceptance["min_nonnegative_units"])
    )
    return {
        "phase": "pre-inference-deterministic-capability-calibration",
        "model_calls": 0,
        "calibration_fields": calibration_fields,
        "confirmatory_fields_untouched": confirmatory_fields,
        "unit_count": len(unit_rows),
        "mean_historical_best_lift_over_uniform_strategy_mean": mean_lift,
        "nonnegative_units": nonnegative_units,
        "acceptance": dict(acceptance),
        "accepted": accepted,
        "units": unit_rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("capsules")
    parser.add_argument("missions")
    parser.add_argument("output")
    args = parser.parse_args()
    result = calibrate(args.capsules, args.missions)
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    if not result["accepted"]:
        raise SystemExit(3)


if __name__ == "__main__":
    main()
