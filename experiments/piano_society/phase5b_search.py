"""Deterministic pre-inference search for transferable Phase-5B memory contexts."""

from __future__ import annotations

import argparse
import copy
import itertools
import json
import statistics
from pathlib import Path
from typing import Any

from resonance_world import w5_institution as w5

from experiments.piano_society.phase5b_transfer_memory import (
    fit_transfer_posterior,
    forecast_strategies,
    neutral_posterior,
    select_forecast_strategy,
)

_STRATEGIES = ("specialist", "balanced")
_REVISION_DEPTH = {
    "piano-phase5b-transfer-search-v1": 48,
    "piano-phase5b-transfer-search-v2": 96,
}


def _read(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _mission(lead: str, support: str, regime: str, *, phase: str):
    context = f"transfer::{lead}::{support}::{regime}"
    return w5._mission(
        {
            "mission_id": f"phase5b-{phase}-{lead}-{support}-{regime}",
            "context": context,
            "lead_skill": lead,
            "support_skill": support,
            "regime": regime,
        }
    )


def _evaluate_strategy_values(
    organization,
    mission,
    *,
    field_id: str,
    lead: str,
    support: str,
    regime: str,
    trials: int,
) -> dict[str, float]:
    environment = w5.InstitutionEnvironment()
    values: dict[str, float] = {}
    for strategy in _STRATEGIES:
        decision = w5._forced_decision(organization, mission.public, strategy)
        outcomes = [
            float(
                environment.evaluate(
                    decision.lead,
                    decision.support,
                    mission,
                    seed=w5._seed(
                        field_id,
                        "phase5b-transfer-search-evaluation",
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
    return values


def _unit(
    design,
    *,
    lead: str,
    support: str,
    regime: str,
    depth: int,
    trials: int,
) -> dict[str, Any]:
    formation = _mission(lead, support, regime, phase="formation")
    evaluation = _mission(lead, support, regime, phase="evaluation")
    trained = w5._organization(
        design,
        f"phase5b-search-{design.field_id}-{lead}-{support}-{regime}",
    )
    w5._train(
        trained,
        [formation],
        depth,
        list(_STRATEGIES),  # type: ignore[arg-type]
        salt="phase5b-transfer-search-formation",
    )
    retained_posterior = fit_transfer_posterior(trained, formation)

    replacement = copy.deepcopy(trained)
    replacement.replace_members(design.replacement_roster(len(design.initial_members)))
    retained_forecasts = forecast_strategies(replacement, evaluation, retained_posterior)
    neutral_forecasts = forecast_strategies(replacement, evaluation, neutral_posterior())
    retained_strategy = select_forecast_strategy(retained_forecasts)
    neutral_strategy = select_forecast_strategy(neutral_forecasts)
    values = _evaluate_strategy_values(
        replacement,
        evaluation,
        field_id=design.field_id,
        lead=lead,
        support=support,
        regime=regime,
        trials=trials,
    )
    retained_value = values[retained_strategy]
    neutral_value = values[neutral_strategy]
    return {
        "field_id": design.field_id,
        "lead_skill": lead,
        "support_skill": support,
        "regime": regime,
        "retained_structural_posterior": retained_posterior.as_dict(),
        "retained_current_roster_forecasts": retained_forecasts,
        "neutral_current_roster_forecasts": neutral_forecasts,
        "retained_transfer_strategy": retained_strategy,
        "neutral_policy_strategy": neutral_strategy,
        "replacement_strategy_success_rates": values,
        "retained_transfer_value": retained_value,
        "neutral_policy_value": neutral_value,
        "transfer_policy_lift_over_neutral_policy": retained_value - neutral_value,
        "posterior_prefers_hidden_structure": (
            retained_posterior.role_specific > retained_posterior.cross_coverage
            if regime == "specialist"
            else retained_posterior.cross_coverage > retained_posterior.role_specific
        ),
    }


def search(capsules_path: str | Path, config_path: str | Path) -> dict[str, Any]:
    config = _read(config_path)
    revision = str(config.get("revision", ""))
    if revision not in _REVISION_DEPTH:
        raise ValueError("unsupported Phase-5B transfer-search revision")
    if config.get("no_model_calls") is not True:
        raise ValueError("Phase-5B transfer search must prohibit model calls")

    source_fields = config["source_fields"]
    calibration_fields = [str(item) for item in source_fields["calibration"]]
    untouched = [str(item) for item in source_fields["confirmatory_untouched"]]
    if len(calibration_fields) != 2 or len(untouched) != 6:
        raise ValueError("Phase-5B search requires two calibration and six untouched fields")
    if set(calibration_fields) & set(untouched):
        raise ValueError("calibration and confirmatory fields must be disjoint")

    skills = tuple(str(item) for item in config["skills"])
    regimes = tuple(str(item) for item in config["regimes"])
    strategies = tuple(str(item) for item in config["turnover_strategy_vocabulary"])
    if len(skills) != 6 or len(set(skills)) != 6:
        raise ValueError("Phase-5B search requires six unique skills")
    if regimes != ("specialist", "balanced") or strategies != _STRATEGIES:
        raise ValueError("Phase-5B regime/strategy vocabulary differs from lock")
    depth = int(config["formation_depth"])
    trials = int(config["evaluation_trials_per_policy"])
    if depth != _REVISION_DEPTH[revision] or trials != 256:
        raise ValueError("Phase-5B formation/evaluation constants differ from revision lock")

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
                    "mean_transfer_policy_lift_over_neutral_policy": statistics.mean(
                        float(unit["transfer_policy_lift_over_neutral_policy"])
                        for unit in units
                    ),
                    "nonnegative_fields": sum(
                        float(unit["transfer_policy_lift_over_neutral_policy"]) >= 0.0
                        for unit in units
                    ),
                    "posterior_structure_matches": sum(
                        bool(unit["posterior_prefers_hidden_structure"]) for unit in units
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
        raise ValueError("Phase-5B search selection constants differ from lock")

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
            units = [unit for candidate in chosen for unit in candidate["units"]]
            mean_lift = statistics.mean(
                float(unit["transfer_policy_lift_over_neutral_policy"]) for unit in units
            )
            nonnegative = sum(
                float(unit["transfer_policy_lift_over_neutral_policy"]) >= 0.0
                for unit in units
            )
            posterior_matches = sum(
                bool(unit["posterior_prefers_hidden_structure"]) for unit in units
            )
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
            combinations.append(
                (-mean_lift, -nonnegative, -posterior_matches, lexical, chosen)
            )
    if not combinations:
        raise ValueError("Phase-5B transfer search found no admissible selection")
    combinations.sort(key=lambda item: item[:4])
    selected = combinations[0][4]
    selected.sort(
        key=lambda candidate: (
            str(candidate["regime"]),
            str(candidate["lead_skill"]),
            str(candidate["support_skill"]),
        )
    )
    selected_units = [unit for candidate in selected for unit in candidate["units"]]
    mean_selected_lift = statistics.mean(
        float(unit["transfer_policy_lift_over_neutral_policy"]) for unit in selected_units
    )
    nonnegative_selected = sum(
        float(unit["transfer_policy_lift_over_neutral_policy"]) >= 0.0
        for unit in selected_units
    )
    posterior_matches = sum(
        bool(unit["posterior_prefers_hidden_structure"]) for unit in selected_units
    )
    acceptance = config["acceptance"]
    accepted = (
        len(selected_units) == int(acceptance["required_selected_units"])
        and mean_selected_lift
        >= float(acceptance["min_mean_transfer_policy_lift_over_neutral_policy"])
        and nonnegative_selected >= int(acceptance["min_nonnegative_selected_units"])
    )
    return {
        "phase": "pre-inference-deterministic-transfer-search",
        "revision": revision,
        "formation_depth": depth,
        "model_calls": 0,
        "calibration_fields": calibration_fields,
        "confirmatory_fields_untouched": untouched,
        "candidate_count": len(candidates),
        "selected": selected,
        "selected_unit_count": len(selected_units),
        "mean_selected_transfer_policy_lift_over_neutral_policy": mean_selected_lift,
        "nonnegative_selected_units": nonnegative_selected,
        "posterior_structure_matches": posterior_matches,
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
