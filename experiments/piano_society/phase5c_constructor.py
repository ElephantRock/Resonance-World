"""Roster-conditional, model-free mission constructor for PIANO Phase 5C.

The constructor reads only frozen pre-treatment competence state. It never reads
sampled confirmatory outcomes or a learned institutional posterior when selecting
confirmatory organizations/missions.
"""

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
    structural_probabilities,
)

_STRATEGIES = ("specialist", "balanced")
_TARGETS = ("role_specific", "cross_coverage")


def _read(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _mission(
    *,
    mission_id: str,
    context: str,
    lead_skill: str,
    support_skill: str,
    regime: str,
):
    return w5._mission(
        {
            "mission_id": mission_id,
            "context": context,
            "lead_skill": lead_skill,
            "support_skill": support_skill,
            "regime": regime,
        }
    )


def _organization_views(design, lead_skill: str, support_skill: str):
    probe = _mission(
        mission_id="phase5c-geometry-probe",
        context="phase5c-geometry-probe",
        lead_skill=lead_skill,
        support_skill=support_skill,
        regime="specialist",
    )
    initial = w5._organization(design, f"phase5c-geometry-initial-{design.field_id}")
    replacement = w5._organization(
        design,
        f"phase5c-geometry-replacement-{design.field_id}",
        design.replacement_roster(len(design.initial_members)),
    )
    return probe, initial, replacement


def _policy_geometry(organization, mission) -> dict[str, Any]:
    environment = w5.InstitutionEnvironment()
    result: dict[str, Any] = {}
    for strategy in _STRATEGIES:
        decision = w5._forced_decision(organization, mission.public, strategy)
        result[strategy] = {
            "lead_agent_id": decision.lead.agent_id,
            "support_agent_id": decision.support.agent_id,
            "structural": structural_probabilities(
                environment,
                decision.lead,
                decision.support,
                mission,
            ),
        }
    return result


def _candidate(
    design,
    *,
    lead_skill: str,
    support_skill: str,
    eligibility: dict[str, Any],
) -> dict[str, Any] | None:
    probe, initial, replacement = _organization_views(design, lead_skill, support_skill)
    replacement_geometry = _policy_geometry(replacement, probe)
    specialist_pair = (
        replacement_geometry["specialist"]["lead_agent_id"],
        replacement_geometry["specialist"]["support_agent_id"],
    )
    balanced_pair = (
        replacement_geometry["balanced"]["lead_agent_id"],
        replacement_geometry["balanced"]["support_agent_id"],
    )
    pair_distinct = specialist_pair != balanced_pair
    if eligibility["require_distinct_ordered_policy_assignments"] is True and not pair_distinct:
        return None

    specialist_structural = replacement_geometry["specialist"]["structural"]
    balanced_structural = replacement_geometry["balanced"]["structural"]
    role_advantage = float(specialist_structural["role_specific"]) - float(
        balanced_structural["role_specific"]
    )
    cross_advantage = float(balanced_structural["cross_coverage"]) - float(
        specialist_structural["cross_coverage"]
    )
    if role_advantage < float(eligibility["min_role_specific_specialist_advantage"]):
        return None
    if cross_advantage < float(eligibility["min_cross_coverage_balanced_advantage"]):
        return None

    neutral_forecasts = {
        strategy: 0.5 * float(replacement_geometry[strategy]["structural"]["role_specific"])
        + 0.5 * float(replacement_geometry[strategy]["structural"]["cross_coverage"])
        for strategy in _STRATEGIES
    }
    neutral_preferred = select_forecast_strategy(neutral_forecasts)
    neutral_margin = abs(neutral_forecasts["specialist"] - neutral_forecasts["balanced"])
    if neutral_margin < float(eligibility["min_neutral_forecast_margin"]):
        return None

    initial_geometry = _policy_geometry(initial, probe)
    formation_identifiability = statistics.mean(
        abs(
            float(initial_geometry[strategy]["structural"]["role_specific"])
            - float(initial_geometry[strategy]["structural"]["cross_coverage"])
        )
        for strategy in _STRATEGIES
    )
    if formation_identifiability < float(
        eligibility["min_formation_hypothesis_identifiability"]
    ):
        return None

    if neutral_preferred == "specialist":
        target_hypothesis = "cross_coverage"
        hidden_regime = "balanced"
        target_policy = "balanced"
    else:
        target_hypothesis = "role_specific"
        hidden_regime = "specialist"
        target_policy = "specialist"

    decision_leverage = min(role_advantage, cross_advantage)
    score = decision_leverage * formation_identifiability
    return {
        "field_id": design.field_id,
        "lead_skill": lead_skill,
        "support_skill": support_skill,
        "target_hypothesis": target_hypothesis,
        "hidden_regime": hidden_regime,
        "target_policy": target_policy,
        "neutral_preferred_policy": neutral_preferred,
        "neutral_forecasts": neutral_forecasts,
        "neutral_forecast_margin": neutral_margin,
        "role_specific_specialist_advantage": role_advantage,
        "cross_coverage_balanced_advantage": cross_advantage,
        "decision_leverage": decision_leverage,
        "formation_hypothesis_identifiability": formation_identifiability,
        "constructor_score": score,
        "replacement_policy_assignments": {
            "specialist": {
                "lead_agent_id": specialist_pair[0],
                "support_agent_id": specialist_pair[1],
            },
            "balanced": {
                "lead_agent_id": balanced_pair[0],
                "support_agent_id": balanced_pair[1],
            },
        },
        "replacement_structural_predictions": {
            strategy: dict(replacement_geometry[strategy]["structural"])
            for strategy in _STRATEGIES
        },
    }


def _candidate_rank(candidate: dict[str, Any]) -> tuple[Any, ...]:
    return (
        -float(candidate["constructor_score"]),
        -float(candidate["decision_leverage"]),
        -float(candidate["formation_hypothesis_identifiability"]),
        -float(candidate["neutral_forecast_margin"]),
        str(candidate["lead_skill"]),
        str(candidate["support_skill"]),
    )


def _field_options(design, skills: tuple[str, ...], eligibility: dict[str, Any]):
    options: dict[str, list[dict[str, Any]]] = {target: [] for target in _TARGETS}
    for lead_skill, support_skill in itertools.permutations(skills, 2):
        candidate = _candidate(
            design,
            lead_skill=lead_skill,
            support_skill=support_skill,
            eligibility=eligibility,
        )
        if candidate is not None:
            options[str(candidate["target_hypothesis"])].append(candidate)
    for target in _TARGETS:
        options[target].sort(key=_candidate_rank)
    return options


def _selection_lexical(rows: list[dict[str, Any]]) -> tuple[tuple[str, str, str, str], ...]:
    return tuple(
        sorted(
            (
                str(row["field_id"]),
                str(row["target_hypothesis"]),
                str(row["lead_skill"]),
                str(row["support_skill"]),
            )
            for row in rows
        )
    )


def _choose_distinct_fields(
    options_by_field: dict[str, dict[str, list[dict[str, Any]]]],
    *,
    role_count: int,
    cross_count: int,
) -> list[dict[str, Any]]:
    fields = tuple(sorted(options_by_field))
    target_counts = {"role_specific": role_count, "cross_coverage": cross_count}
    states: dict[tuple[int, int], tuple[float, list[dict[str, Any]]]] = {
        (0, 0): (0.0, [])
    }
    for field_id in fields:
        next_states = dict(states)
        for (role_used, cross_used), (score, rows) in states.items():
            for target in _TARGETS:
                candidates = options_by_field[field_id][target]
                if not candidates:
                    continue
                new_role = role_used + int(target == "role_specific")
                new_cross = cross_used + int(target == "cross_coverage")
                if new_role > target_counts["role_specific"] or new_cross > target_counts["cross_coverage"]:
                    continue
                candidate = candidates[0]
                new_rows = rows + [candidate]
                new_score = score + float(candidate["constructor_score"])
                state = (new_role, new_cross)
                incumbent = next_states.get(state)
                if incumbent is None:
                    next_states[state] = (new_score, new_rows)
                    continue
                incumbent_score, incumbent_rows = incumbent
                if new_score > incumbent_score + 1e-15:
                    next_states[state] = (new_score, new_rows)
                elif abs(new_score - incumbent_score) <= 1e-15 and _selection_lexical(
                    new_rows
                ) < _selection_lexical(incumbent_rows):
                    next_states[state] = (new_score, new_rows)
        states = next_states
    key = (role_count, cross_count)
    if key not in states:
        raise ValueError(
            "Phase-5C roster geometry cannot satisfy the registered target-balanced field selection"
        )
    result = states[key][1]
    result.sort(key=lambda row: str(row["field_id"]))
    if len({str(row["field_id"]) for row in result}) != len(result):
        raise AssertionError("Phase-5C selection reused a field")
    return result


def _calibrate_unit(
    design,
    candidate: dict[str, Any],
    *,
    depth: int,
    trials: int,
) -> dict[str, Any]:
    context = (
        f"phase5c::{design.field_id}::{candidate['lead_skill']}::"
        f"{candidate['support_skill']}::{candidate['hidden_regime']}"
    )
    formation = _mission(
        mission_id=f"phase5c-calibration-formation-{design.field_id}",
        context=context,
        lead_skill=str(candidate["lead_skill"]),
        support_skill=str(candidate["support_skill"]),
        regime=str(candidate["hidden_regime"]),
    )
    evaluation = _mission(
        mission_id=f"phase5c-calibration-evaluation-{design.field_id}",
        context=context,
        lead_skill=str(candidate["lead_skill"]),
        support_skill=str(candidate["support_skill"]),
        regime=str(candidate["hidden_regime"]),
    )
    trained = w5._organization(design, f"phase5c-calibration-{design.field_id}")
    w5._train(
        trained,
        [formation],
        depth,
        list(_STRATEGIES),  # type: ignore[arg-type]
        salt="phase5c-constructor-formation",
    )
    posterior = fit_transfer_posterior(trained, formation)
    replacement = copy.deepcopy(trained)
    replacement.replace_members(design.replacement_roster(len(design.initial_members)))
    retained_forecasts = forecast_strategies(replacement, evaluation, posterior)
    neutral_forecasts = forecast_strategies(replacement, evaluation, neutral_posterior())
    retained_policy = select_forecast_strategy(retained_forecasts)
    neutral_policy = select_forecast_strategy(neutral_forecasts)

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
                        "phase5c-constructor-calibration-evaluation",
                        candidate["lead_skill"],
                        candidate["support_skill"],
                        candidate["hidden_regime"],
                        trial,
                    ),
                )
            )
            for trial in range(trials)
        ]
        values[strategy] = statistics.mean(outcomes)

    retained_value = values[retained_policy]
    neutral_value = values[neutral_policy]
    target_match = (
        posterior.role_specific > posterior.cross_coverage
        if candidate["target_hypothesis"] == "role_specific"
        else posterior.cross_coverage > posterior.role_specific
    )
    return {
        "constructor": candidate,
        "retained_posterior": posterior.as_dict(),
        "retained_forecasts": retained_forecasts,
        "neutral_forecasts": neutral_forecasts,
        "retained_policy": retained_policy,
        "neutral_policy": neutral_policy,
        "forecast_preference_changed": retained_policy != neutral_policy,
        "target_posterior_match": target_match,
        "replacement_strategy_success_rates": values,
        "retained_value": retained_value,
        "neutral_value": neutral_value,
        "retained_minus_neutral_success_rate": retained_value - neutral_value,
    }


def construct(capsules_path: str | Path, config_path: str | Path) -> dict[str, Any]:
    config = _read(config_path)
    if config.get("revision") != "piano-phase5c-roster-conditional-v1":
        raise ValueError("unsupported Phase-5C constructor revision")
    if config.get("no_model_calls") is not True:
        raise ValueError("Phase-5C construction must remain model-free")
    if tuple(config.get("strategy_vocabulary", ())) != _STRATEGIES:
        raise ValueError("Phase-5C strategy vocabulary differs from lock")
    if tuple(config.get("structural_hypotheses", ())) != _TARGETS:
        raise ValueError("Phase-5C structural hypothesis vocabulary differs from lock")
    if config.get("neutral_prior") != {"role_specific": 0.5, "cross_coverage": 0.5}:
        raise ValueError("Phase-5C neutral prior differs from lock")
    if config.get("target_rule") != (
        "choose_the_structural_regime_whose_optimal_policy_opposes_the_neutral_prior_preference"
    ):
        raise ValueError("Phase-5C target rule differs from lock")
    if config.get("score_rule") != (
        "min_hypothesis_policy_advantage_times_formation_identifiability"
    ):
        raise ValueError("Phase-5C score rule differs from lock")

    source = config["source_fields"]
    calibration_pool = [str(item) for item in source["calibration_pool"]]
    confirmatory_pool = [str(item) for item in source["confirmatory_pool"]]
    if len(calibration_pool) != 6 or len(confirmatory_pool) != 18:
        raise ValueError("Phase-5C requires a 6-field calibration pool and 18-field confirmatory pool")
    if set(calibration_pool) & set(confirmatory_pool):
        raise ValueError("Phase-5C source pools must be disjoint")
    skills = tuple(str(item) for item in config["skills"])
    if len(skills) != 6 or len(set(skills)) != 6:
        raise ValueError("Phase-5C requires six unique skills")
    eligibility = dict(config["eligibility"])
    expected_eligibility = {
        "require_distinct_ordered_policy_assignments": True,
        "min_role_specific_specialist_advantage": 0.02,
        "min_cross_coverage_balanced_advantage": 0.02,
        "min_neutral_forecast_margin": 0.0005,
        "min_formation_hypothesis_identifiability": 0.005,
    }
    if eligibility != expected_eligibility:
        raise ValueError("Phase-5C eligibility thresholds differ from lock")
    depth = int(config["formation_depth"])
    trials = int(config["calibration_evaluation_trials_per_policy"])
    if depth != 96 or trials != 512:
        raise ValueError("Phase-5C formation/evaluation constants differ from lock")

    all_fields = calibration_pool + confirmatory_pool
    designs = w5._load_designs(capsules_path, all_fields, 4)
    options_by_field = {
        field_id: _field_options(designs[field_id], skills, eligibility)
        for field_id in all_fields
    }
    geometry_summary = {
        field_id: {
            target: len(options_by_field[field_id][target]) for target in _TARGETS
        }
        for field_id in all_fields
    }

    selection = dict(config["selection"])
    if selection != {
        "calibration_units": 4,
        "calibration_target_role_specific": 2,
        "calibration_target_cross_coverage": 2,
        "confirmatory_units": 12,
        "confirmatory_target_role_specific": 6,
        "confirmatory_target_cross_coverage": 6,
        "one_unit_per_field": True,
    }:
        raise ValueError("Phase-5C selection lock differs")

    calibration_selected = _choose_distinct_fields(
        {field_id: options_by_field[field_id] for field_id in calibration_pool},
        role_count=2,
        cross_count=2,
    )
    confirmatory_selected = _choose_distinct_fields(
        {field_id: options_by_field[field_id] for field_id in confirmatory_pool},
        role_count=6,
        cross_count=6,
    )

    calibration_units = [
        _calibrate_unit(
            designs[str(candidate["field_id"])],
            candidate,
            depth=depth,
            trials=trials,
        )
        for candidate in calibration_selected
    ]
    effects = [float(unit["retained_minus_neutral_success_rate"]) for unit in calibration_units]
    mean_effect = statistics.mean(effects)
    nonnegative = sum(value >= 0.0 for value in effects)
    forecast_changes = sum(bool(unit["forecast_preference_changed"]) for unit in calibration_units)
    posterior_matches = sum(bool(unit["target_posterior_match"]) for unit in calibration_units)
    acceptance = dict(config["calibration_acceptance"])
    expected_acceptance = {
        "min_mean_retained_minus_neutral_success_rate": 0.03,
        "min_nonnegative_units": 4,
        "min_forecast_preference_change_units": 4,
        "min_target_posterior_match_units": 4,
    }
    if acceptance != expected_acceptance:
        raise ValueError("Phase-5C calibration gate differs from lock")
    accepted = (
        mean_effect >= float(acceptance["min_mean_retained_minus_neutral_success_rate"])
        and nonnegative >= int(acceptance["min_nonnegative_units"])
        and forecast_changes >= int(acceptance["min_forecast_preference_change_units"])
        and posterior_matches >= int(acceptance["min_target_posterior_match_units"])
    )

    return {
        "phase": "pre-inference-roster-conditional-construction-and-calibration",
        "revision": config["revision"],
        "model_calls": 0,
        "formation_depth": depth,
        "calibration_evaluation_trials_per_policy": trials,
        "geometry_eligibility_counts": geometry_summary,
        "calibration_selected": calibration_selected,
        "calibration_units": calibration_units,
        "calibration_mean_retained_minus_neutral_success_rate": mean_effect,
        "calibration_nonnegative_units": nonnegative,
        "calibration_forecast_preference_change_units": forecast_changes,
        "calibration_target_posterior_match_units": posterior_matches,
        "confirmatory_selected_pre_outcome": confirmatory_selected,
        "confirmatory_selected_count": len(confirmatory_selected),
        "confirmatory_target_counts": {
            target: sum(
                str(row["target_hypothesis"]) == target for row in confirmatory_selected
            )
            for target in _TARGETS
        },
        "confirmatory_outcomes_evaluated": False,
        "calibration_acceptance": acceptance,
        "accepted": accepted,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("capsules")
    parser.add_argument("config")
    parser.add_argument("output")
    args = parser.parse_args()
    result = construct(args.capsules, args.config)
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
