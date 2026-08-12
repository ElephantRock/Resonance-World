"""Deterministic pre-inference mission search for Phase-5 institutional memory."""

from __future__ import annotations

import argparse
import copy
import itertools
import json
import statistics
from pathlib import Path
from typing import Any

from resonance_world import w5_institution as w5

_STRATEGIES = ("specialist", "balanced")


def _read(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _candidate_mission(lead: str, support: str, regime: str, *, phase: str):
    context = f"calibration::{lead}::{support}::{regime}"
    return w5._mission(
        {
            "mission_id": f"phase5-search-{phase}-{lead}-{support}-{regime}",
            "context": context,
            "lead_skill": lead,
            "support_skill": support,
            "regime": regime,
        }
    )


def _unit(
    design,
    *,
    lead: str,
    support: str,
    regime: str,
    depth: int,
    trials: int,
) -> dict[str, Any]:
    formation = _candidate_mission(lead, support, regime, phase="formation")
    evaluation = _candidate_mission(lead, support, regime, phase="evaluation")
    organization = w5._organization(
        design,
        f"phase5-search-{design.field_id}-{lead}-{support}-{regime}",
    )
    w5._train(
        organization,
        [formation],
        depth,
        list(_STRATEGIES),  # type: ignore[arg-type]
        salt="phase5-mission-search-formation",
    )
    historical_best = organization.memory.best_strategy(formation.public.context)
    if historical_best not in _STRATEGIES:
        raise ValueError("binary formation produced an unsupported historical strategy")
    attempts = organization.memory.strategy_attempts[formation.public.context]
    successes = organization.memory.strategy_successes[formation.public.context]
    historical_rates = {
        strategy: successes[strategy] / attempts[strategy] for strategy in _STRATEGIES
    }

    replacement = copy.deepcopy(organization)
    replacement.replace_members(design.replacement_roster(len(design.initial_members)))
    environment = w5.InstitutionEnvironment()
    values: dict[str, float] = {}
    for strategy in _STRATEGIES:
        decision = w5._forced_decision(replacement, evaluation.public, strategy)
        outcomes = [
            float(
                environment.evaluate(
                    decision.lead,
                    decision.support,
                    evaluation,
                    seed=w5._seed(
                        design.field_id,
                        "phase5-mission-search-evaluation",
                        lead,
                        support,
                        regime,
                        trial,
                    ),
                )
            )
            for trial in range(trials)
        ]
        values[strategy] = statistics.mean(outcomes)
    binary_mean = statistics.mean(values.values())
    historical_value = values[historical_best]
    oracle_value = max(values.values())
    return {
        "field_id": design.field_id,
        "lead_skill": lead,
        "support_skill": support,
        "regime": regime,
        "historical_success_rates": historical_rates,
        "historical_best_strategy": historical_best,
        "replacement_strategy_success_rates": values,
        "historical_best_replacement_value": historical_value,
        "binary_strategy_mean": binary_mean,
        "oracle_replacement_value": oracle_value,
        "historical_best_lift_over_binary_mean": historical_value - binary_mean,
        "oracle_gap": oracle_value - historical_value,
    }


def search(capsules_path: str | Path, config_path: str | Path) -> dict[str, Any]:
    config = _read(config_path)
    if config.get("revision") != "piano-phase5-mission-search-v1":
        raise ValueError("unsupported Phase-5 mission-search revision")
    source_fields = config["source_fields"]
    calibration_fields = [str(item) for item in source_fields["calibration"]]
    untouched = [str(item) for item in source_fields["confirmatory_untouched"]]
    if len(calibration_fields) != 2 or len(untouched) != 6:
        raise ValueError("mission search requires two calibration and six untouched fields")
    if set(calibration_fields) & set(untouched):
        raise ValueError("calibration and confirmatory fields must be disjoint")
    if config.get("no_model_calls") is not True:
        raise ValueError("mission search must prohibit model calls")

    skills = tuple(str(item) for item in config["skills"])
    regimes = tuple(str(item) for item in config["regimes"])
    strategies = tuple(str(item) for item in config["turnover_strategy_vocabulary"])
    if len(skills) != 6 or len(set(skills)) != 6:
        raise ValueError("mission search requires six unique skills")
    if regimes != ("specialist", "balanced") or strategies != _STRATEGIES:
        raise ValueError("mission search regime/strategy vocabulary differs from lock")
    depth = int(config["formation_depth"])
    trials = int(config["evaluation_trials_per_strategy"])
    if depth != 48 or trials != 256:
        raise ValueError("mission search depth/trials differ from lock")

    designs = w5._load_designs(capsules_path, calibration_fields, 4)
    candidates: list[dict[str, Any]] = []
    for regime in regimes:
        for lead, support in itertools.permutations(skills, 2):
            units = [
                _unit(
                    designs[field_id],
                    lead=lead,
                    support=support,
                    regime=regime,
                    depth=depth,
                    trials=trials,
                )
                for field_id in calibration_fields
            ]
            candidates.append(
                {
                    "lead_skill": lead,
                    "support_skill": support,
                    "regime": regime,
                    "mean_historical_best_lift_over_binary_mean": statistics.mean(
                        float(unit["historical_best_lift_over_binary_mean"]) for unit in units
                    ),
                    "mean_oracle_gap": statistics.mean(
                        float(unit["oracle_gap"]) for unit in units
                    ),
                    "nonnegative_fields": sum(
                        float(unit["historical_best_lift_over_binary_mean"]) >= 0.0
                        for unit in units
                    ),
                    "units": units,
                }
            )

    selection = config["selection"]
    if (
        int(selection["selected_contexts"]) != 4
        or int(selection["selected_per_regime"]) != 2
        or selection["require_distinct_ordered_skill_pairs"] is not True
    ):
        raise ValueError("mission-search selection constants differ from lock")

    by_regime = {
        regime: [candidate for candidate in candidates if candidate["regime"] == regime]
        for regime in regimes
    }
    combinations = []
    for specialist_pair in itertools.combinations(by_regime["specialist"], 2):
        for balanced_pair in itertools.combinations(by_regime["balanced"], 2):
            chosen = list(specialist_pair + balanced_pair)
            skill_pairs = {
                (candidate["lead_skill"], candidate["support_skill"])
                for candidate in chosen
            }
            if len(skill_pairs) != 4:
                continue
            mean_lift = statistics.mean(
                float(candidate["mean_historical_best_lift_over_binary_mean"])
                for candidate in chosen
            )
            mean_gap = statistics.mean(float(candidate["mean_oracle_gap"]) for candidate in chosen)
            lexical = tuple(
                sorted(
                    (
                        str(candidate["regime"]),
                        str(candidate["lead_skill"]),
                        str(candidate["support_skill"]),
                    )
                    for candidate in chosen
                )
            )
            combinations.append((-mean_lift, mean_gap, lexical, chosen))
    if not combinations:
        raise ValueError("mission search found no admissible four-context selection")
    combinations.sort(key=lambda item: (item[0], item[1], item[2]))
    selected = combinations[0][3]
    selected.sort(
        key=lambda candidate: (
            str(candidate["regime"]),
            str(candidate["lead_skill"]),
            str(candidate["support_skill"]),
        )
    )
    selected_units = [unit for candidate in selected for unit in candidate["units"]]
    mean_selected_lift = statistics.mean(
        float(unit["historical_best_lift_over_binary_mean"]) for unit in selected_units
    )
    nonnegative_selected = sum(
        float(unit["historical_best_lift_over_binary_mean"]) >= 0.0
        for unit in selected_units
    )
    acceptance = config["acceptance"]
    accepted = (
        len(selected_units) == int(acceptance["required_selected_units"])
        and mean_selected_lift
        >= float(acceptance["min_mean_selected_historical_best_lift_over_binary_mean"])
        and nonnegative_selected >= int(acceptance["min_nonnegative_selected_units"])
    )
    return {
        "phase": "pre-inference-deterministic-mission-search",
        "model_calls": 0,
        "calibration_fields": calibration_fields,
        "confirmatory_fields_untouched": untouched,
        "candidate_count": len(candidates),
        "selected": selected,
        "selected_unit_count": len(selected_units),
        "mean_selected_historical_best_lift_over_binary_mean": mean_selected_lift,
        "nonnegative_selected_units": nonnegative_selected,
        "acceptance": dict(acceptance),
        "accepted": accepted,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("capsules")
    parser.add_argument("config")
    parser.add_argument("output")
    args = parser.parse_args()
    result = search(args.capsules, args.config)
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
