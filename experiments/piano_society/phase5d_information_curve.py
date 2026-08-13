"""Model-free information-quality curve for PIANO institutional memory.

Calibration chooses the minimum registered formation depth that clears all frozen
mechanism/effect gates. The validation pool is not outcome-evaluated unless such a
depth exists. No model backend or credential is used by this module.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
from pathlib import Path
from typing import Any

from resonance_world import w5_institution as w5

from experiments.piano_society.phase5c_constructor import (
    _calibrate_unit,
    _choose_distinct_fields,
    _field_options,
    _read,
)

_STRATEGIES = ("specialist", "balanced")
_TARGETS = ("role_specific", "cross_coverage")
_DEPTHS = (24, 48, 96, 192, 384)
_EXPECTED_GEOMETRY = {
    "require_distinct_ordered_policy_assignments": True,
    "min_role_specific_specialist_advantage": 0.02,
    "min_cross_coverage_balanced_advantage": 0.02,
    "min_neutral_forecast_margin": 0.0005,
    "min_formation_hypothesis_identifiability": 0.005,
}
_EXPECTED_CALIBRATION_GATE = {
    "min_mean_retained_minus_neutral_success_rate": 0.03,
    "min_nonnegative_unit_rate": 0.90,
    "min_target_posterior_match_rate": 0.90,
    "min_forecast_preference_change_rate": 0.90,
}
_EXPECTED_VALIDATION_GATE = {
    "min_mean_retained_minus_neutral_success_rate": 0.03,
    "max_exact_two_sided_sign_test_p": 0.05,
    "min_nonnegative_unit_rate": 0.90,
    "min_target_posterior_match_rate": 0.90,
    "min_forecast_preference_change_rate": 0.90,
}


def _exact_sign_test(better: int, worse: int) -> float:
    discordant = better + worse
    if discordant == 0:
        return 1.0
    tail = min(better, worse)
    one_tail = sum(math.comb(discordant, k) for k in range(tail + 1)) / (2**discordant)
    return min(1.0, 2.0 * one_tail)


def _maximally_balanced_selection(
    options_by_field: dict[str, dict[str, list[dict[str, Any]]]],
    *,
    minimum_each: int,
) -> tuple[int, list[dict[str, Any]]]:
    maximum_each = len(options_by_field) // 2
    for count_each in range(maximum_each, minimum_each - 1, -1):
        try:
            selected = _choose_distinct_fields(
                options_by_field,
                role_count=count_each,
                cross_count=count_each,
            )
        except ValueError:
            continue
        return count_each, selected
    raise ValueError(
        "Phase-5D source geometry cannot satisfy the preregistered minimum balanced target set"
    )


def _summarize_units(units: list[dict[str, Any]]) -> dict[str, Any]:
    effects = [float(unit["retained_minus_neutral_success_rate"]) for unit in units]
    nonnegative = sum(effect >= 0.0 for effect in effects)
    posterior_matches = sum(bool(unit["target_posterior_match"]) for unit in units)
    forecast_changes = sum(bool(unit["forecast_preference_changed"]) for unit in units)
    better = sum(effect > 0.0 for effect in effects)
    worse = sum(effect < 0.0 for effect in effects)
    ties = len(effects) - better - worse
    return {
        "unit_count": len(units),
        "mean_retained_minus_neutral_success_rate": statistics.mean(effects),
        "nonnegative_units": nonnegative,
        "nonnegative_unit_rate": nonnegative / len(units),
        "target_posterior_match_units": posterior_matches,
        "target_posterior_match_rate": posterior_matches / len(units),
        "forecast_preference_change_units": forecast_changes,
        "forecast_preference_change_rate": forecast_changes / len(units),
        "paired_better": better,
        "paired_worse": worse,
        "paired_ties": ties,
        "paired_discordant": better + worse,
        "exact_two_sided_sign_test_p": _exact_sign_test(better, worse),
    }


def _passes_calibration(summary: dict[str, Any]) -> bool:
    return (
        float(summary["mean_retained_minus_neutral_success_rate"])
        >= _EXPECTED_CALIBRATION_GATE["min_mean_retained_minus_neutral_success_rate"]
        and float(summary["nonnegative_unit_rate"])
        >= _EXPECTED_CALIBRATION_GATE["min_nonnegative_unit_rate"]
        and float(summary["target_posterior_match_rate"])
        >= _EXPECTED_CALIBRATION_GATE["min_target_posterior_match_rate"]
        and float(summary["forecast_preference_change_rate"])
        >= _EXPECTED_CALIBRATION_GATE["min_forecast_preference_change_rate"]
    )


def _passes_validation(summary: dict[str, Any]) -> bool:
    return (
        float(summary["mean_retained_minus_neutral_success_rate"])
        >= _EXPECTED_VALIDATION_GATE["min_mean_retained_minus_neutral_success_rate"]
        and float(summary["exact_two_sided_sign_test_p"])
        <= _EXPECTED_VALIDATION_GATE["max_exact_two_sided_sign_test_p"]
        and float(summary["nonnegative_unit_rate"])
        >= _EXPECTED_VALIDATION_GATE["min_nonnegative_unit_rate"]
        and float(summary["target_posterior_match_rate"])
        >= _EXPECTED_VALIDATION_GATE["min_target_posterior_match_rate"]
        and float(summary["forecast_preference_change_rate"])
        >= _EXPECTED_VALIDATION_GATE["min_forecast_preference_change_rate"]
    )


def _validate_config(config: dict[str, Any]) -> tuple[list[str], list[str], tuple[str, ...]]:
    if config.get("revision") != "piano-phase5d-memory-information-curve-v1":
        raise ValueError("unsupported Phase-5D information-curve revision")
    if config.get("no_model_calls") is not True:
        raise ValueError("Phase-5D information curve must prohibit model calls")
    source = config["source_fields"]
    calibration_pool = [str(item) for item in source["calibration_pool"]]
    validation_pool = [str(item) for item in source["validation_pool"]]
    if len(calibration_pool) != 12 or len(validation_pool) != 24:
        raise ValueError("Phase-5D requires 12 calibration and 24 validation Fields")
    if set(calibration_pool) & set(validation_pool):
        raise ValueError("Phase-5D calibration and validation pools must be disjoint")
    skills = tuple(str(item) for item in config["skills"])
    if len(skills) != 6 or len(set(skills)) != 6:
        raise ValueError("Phase-5D requires six unique skills")
    if tuple(config.get("strategy_vocabulary", ())) != _STRATEGIES:
        raise ValueError("Phase-5D strategy vocabulary differs from lock")
    if tuple(config.get("structural_hypotheses", ())) != _TARGETS:
        raise ValueError("Phase-5D structural hypotheses differ from lock")
    if config.get("neutral_prior") != {"role_specific": 0.5, "cross_coverage": 0.5}:
        raise ValueError("Phase-5D neutral prior differs from lock")
    if dict(config.get("geometry_eligibility", {})) != _EXPECTED_GEOMETRY:
        raise ValueError("Phase-5D geometry thresholds differ from Phase-5C lock")
    if config.get("target_rule") != (
        "choose_the_structural_regime_whose_optimal_policy_opposes_the_neutral_prior_preference"
    ):
        raise ValueError("Phase-5D target rule differs from lock")
    if config.get("selection_rule") != (
        "maximally_balanced_distinct_field_set_by_constructor_score"
    ):
        raise ValueError("Phase-5D selection rule differs from lock")
    if config.get("minimum_balanced_target_count") != {
        "calibration_each": 3,
        "validation_each": 5,
    }:
        raise ValueError("Phase-5D minimum balanced target counts differ from lock")
    if tuple(int(item) for item in config.get("formation_depths", ())) != _DEPTHS:
        raise ValueError("Phase-5D evidence-depth grid differs from lock")
    if tuple(config.get("formation_strategy_order", ())) != _STRATEGIES:
        raise ValueError("Phase-5D formation strategy order differs from lock")
    if int(config.get("policy_evaluation_trials", -1)) != 1024:
        raise ValueError("Phase-5D policy evaluation trial count differs from lock")
    if dict(config.get("calibration_depth_gate", {})) != _EXPECTED_CALIBRATION_GATE:
        raise ValueError("Phase-5D calibration depth gate differs from lock")
    if config.get("depth_selection_rule") != (
        "minimum_registered_depth_passing_all_calibration_gates"
    ):
        raise ValueError("Phase-5D depth selection rule differs from lock")
    if dict(config.get("validation_gate", {})) != _EXPECTED_VALIDATION_GATE:
        raise ValueError("Phase-5D validation gate differs from lock")
    return calibration_pool, validation_pool, skills


def run(capsules_path: str | Path, config_path: str | Path) -> dict[str, Any]:
    config = _read(config_path)
    calibration_pool, validation_pool, skills = _validate_config(config)
    designs = w5._load_designs(
        capsules_path,
        calibration_pool + validation_pool,
        4,
    )
    options_by_field = {
        field_id: _field_options(designs[field_id], skills, _EXPECTED_GEOMETRY)
        for field_id in calibration_pool + validation_pool
    }
    calibration_each, calibration_selected = _maximally_balanced_selection(
        {field_id: options_by_field[field_id] for field_id in calibration_pool},
        minimum_each=3,
    )
    validation_each, validation_selected = _maximally_balanced_selection(
        {field_id: options_by_field[field_id] for field_id in validation_pool},
        minimum_each=5,
    )

    calibration_curve: list[dict[str, Any]] = []
    selected_depth: int | None = None
    for depth in _DEPTHS:
        units = [
            _calibrate_unit(
                designs[str(candidate["field_id"])],
                candidate,
                depth=depth,
                trials=1024,
            )
            for candidate in calibration_selected
        ]
        summary = _summarize_units(units)
        passes = _passes_calibration(summary)
        calibration_curve.append(
            {
                "formation_depth": depth,
                "summary": summary,
                "passes_calibration_depth_gate": passes,
                "units": units,
            }
        )
        if selected_depth is None and passes:
            selected_depth = depth

    result: dict[str, Any] = {
        "phase": "model-free-institutional-memory-information-curve",
        "revision": config["revision"],
        "model_calls": 0,
        "calibration_pool": calibration_pool,
        "validation_pool": validation_pool,
        "calibration_balanced_target_count_each": calibration_each,
        "validation_balanced_target_count_each": validation_each,
        "calibration_selected_pre_outcome": calibration_selected,
        "validation_selected_pre_outcome": validation_selected,
        "calibration_curve": calibration_curve,
        "selected_formation_depth": selected_depth,
        "validation_outcomes_evaluated": False,
        "validation": None,
        "advance_to_model_backed_replication": False,
    }
    if selected_depth is None:
        return result

    validation_units = [
        _calibrate_unit(
            designs[str(candidate["field_id"])],
            candidate,
            depth=selected_depth,
            trials=1024,
        )
        for candidate in validation_selected
    ]
    validation_summary = _summarize_units(validation_units)
    validation_passes = _passes_validation(validation_summary)
    result["validation_outcomes_evaluated"] = True
    result["validation"] = {
        "formation_depth": selected_depth,
        "summary": validation_summary,
        "passes_validation_gate": validation_passes,
        "units": validation_units,
    }
    result["advance_to_model_backed_replication"] = validation_passes
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("capsules")
    parser.add_argument("config")
    parser.add_argument("output")
    args = parser.parse_args()
    result = run(args.capsules, args.config)
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    if not result["advance_to_model_backed_replication"]:
        raise SystemExit(3)


if __name__ == "__main__":
    main()
