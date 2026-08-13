"""Phase-5C v2 constructor: same geometry, feasible 5/7 confirmatory composition."""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path
from typing import Any

from resonance_world import w5_institution as w5

from experiments.piano_society.phase5c_constructor import (
    _TARGETS,
    _calibrate_unit,
    _choose_distinct_fields,
    _field_options,
    _read,
)

_EXPECTED_ELIGIBILITY = {
    "require_distinct_ordered_policy_assignments": True,
    "min_role_specific_specialist_advantage": 0.02,
    "min_cross_coverage_balanced_advantage": 0.02,
    "min_neutral_forecast_margin": 0.0005,
    "min_formation_hypothesis_identifiability": 0.005,
}
_EXPECTED_ACCEPTANCE = {
    "min_mean_retained_minus_neutral_success_rate": 0.03,
    "min_nonnegative_units": 4,
    "min_forecast_preference_change_units": 4,
    "min_target_posterior_match_units": 4,
}
_EXPECTED_SOURCE_LOCK = {
    "workflow_run": 31652358960,
    "world_revision": "88baf131c78bf37fe49fab858890cce7f4740729",
    "artifact_id": 9163101495,
    "artifact_name": "piano-society-phase5c-frozen-source",
    "artifact_digest": "sha256:2caf65e6f2839f243ad0c6e59f7d12ad196f48ddf79aab7c3cca42b0904f22f6",
    "capsule_sha256": "b44926d70fe91ae3ad546351bd42096ad54a10d7d50eb954060e1bc56dcd1ea8",
    "candidate_sha256": "a750b8b110a26a60e74a4561493c3359b29524cca2ebec1061bccff6cb3ad0b7",
}
_EXPECTED_GEOMETRY_LOCK = {
    "workflow_run": 31652891403,
    "world_revision": "f01f85369013ff8a74e0c9600e5e7eefc7036a78",
    "artifact_id": 9163248092,
    "artifact_name": "piano-society-phase5c-geometry-audit",
    "artifact_digest": "sha256:c30535d8d14e93e35605db5690a7abda08e42f0ffcff1a49354dfc1b4a42ed2c",
    "model_calls": 0,
    "memory_training_performed": False,
    "mission_outcomes_evaluated": False,
    "confirmatory_fields_with_role_specific_option": 5,
    "confirmatory_fields_with_cross_coverage_option": 13,
    "most_balanced_feasible_twelve_unit_role_specific": 5,
    "most_balanced_feasible_twelve_unit_cross_coverage": 7,
}


def construct(capsules_path: str | Path, config_path: str | Path) -> dict[str, Any]:
    config = _read(config_path)
    if config.get("revision") != "piano-phase5c-roster-conditional-v2":
        raise ValueError("unsupported Phase-5C v2 constructor revision")
    if config.get("no_model_calls") is not True:
        raise ValueError("Phase-5C v2 construction must remain model-free")
    if dict(config.get("source_lock", {})) != _EXPECTED_SOURCE_LOCK:
        raise ValueError("Phase-5C v2 frozen-source lock differs")
    if dict(config.get("geometry_audit_lock", {})) != _EXPECTED_GEOMETRY_LOCK:
        raise ValueError("Phase-5C v2 geometry-audit lock differs")
    if tuple(config.get("strategy_vocabulary", ())) != ("specialist", "balanced"):
        raise ValueError("Phase-5C v2 strategy vocabulary differs")
    if tuple(config.get("structural_hypotheses", ())) != _TARGETS:
        raise ValueError("Phase-5C v2 structural hypothesis vocabulary differs")
    if config.get("neutral_prior") != {"role_specific": 0.5, "cross_coverage": 0.5}:
        raise ValueError("Phase-5C v2 neutral prior differs")
    if dict(config.get("eligibility", {})) != _EXPECTED_ELIGIBILITY:
        raise ValueError("Phase-5C v2 eligibility thresholds differ")
    if config.get("target_rule") != (
        "choose_the_structural_regime_whose_optimal_policy_opposes_the_neutral_prior_preference"
    ):
        raise ValueError("Phase-5C v2 target rule differs")
    if config.get("score_rule") != (
        "min_hypothesis_policy_advantage_times_formation_identifiability"
    ):
        raise ValueError("Phase-5C v2 score rule differs")
    if int(config.get("formation_depth", -1)) != 96:
        raise ValueError("Phase-5C v2 formation depth differs")
    if int(config.get("calibration_evaluation_trials_per_policy", -1)) != 512:
        raise ValueError("Phase-5C v2 calibration trial count differs")
    if dict(config.get("calibration_acceptance", {})) != _EXPECTED_ACCEPTANCE:
        raise ValueError("Phase-5C v2 calibration gate differs")

    source = config["source_fields"]
    calibration_pool = [str(item) for item in source["calibration_pool"]]
    confirmatory_pool = [str(item) for item in source["confirmatory_pool"]]
    if len(calibration_pool) != 6 or len(confirmatory_pool) != 18:
        raise ValueError("Phase-5C v2 source pools differ from lock")
    if set(calibration_pool) & set(confirmatory_pool):
        raise ValueError("Phase-5C v2 source pools must remain disjoint")
    skills = tuple(str(item) for item in config["skills"])
    if len(skills) != 6 or len(set(skills)) != 6:
        raise ValueError("Phase-5C v2 requires six unique skills")

    selection = dict(config["selection"])
    if selection != {
        "calibration_units": 4,
        "calibration_target_role_specific": 2,
        "calibration_target_cross_coverage": 2,
        "confirmatory_units": 12,
        "confirmatory_target_role_specific": 5,
        "confirmatory_target_cross_coverage": 7,
        "one_unit_per_field": True,
        "composition_rule": (
            "most_balanced_feasible_twelve_unit_composition_from_locked_geometry_audit"
        ),
    }:
        raise ValueError("Phase-5C v2 selection lock differs")

    designs = w5._load_designs(
        capsules_path,
        calibration_pool + confirmatory_pool,
        4,
    )
    options_by_field = {
        field_id: _field_options(designs[field_id], skills, _EXPECTED_ELIGIBILITY)
        for field_id in calibration_pool + confirmatory_pool
    }
    geometry_summary = {
        field_id: {
            target: len(options_by_field[field_id][target]) for target in _TARGETS
        }
        for field_id in calibration_pool + confirmatory_pool
    }

    calibration_selected = _choose_distinct_fields(
        {field_id: options_by_field[field_id] for field_id in calibration_pool},
        role_count=2,
        cross_count=2,
    )
    confirmatory_selected = _choose_distinct_fields(
        {field_id: options_by_field[field_id] for field_id in confirmatory_pool},
        role_count=5,
        cross_count=7,
    )
    calibration_units = [
        _calibrate_unit(
            designs[str(candidate["field_id"])],
            candidate,
            depth=96,
            trials=512,
        )
        for candidate in calibration_selected
    ]
    effects = [float(unit["retained_minus_neutral_success_rate"]) for unit in calibration_units]
    mean_effect = statistics.mean(effects)
    nonnegative = sum(value >= 0.0 for value in effects)
    forecast_changes = sum(bool(unit["forecast_preference_changed"]) for unit in calibration_units)
    posterior_matches = sum(bool(unit["target_posterior_match"]) for unit in calibration_units)
    accepted = (
        mean_effect >= _EXPECTED_ACCEPTANCE["min_mean_retained_minus_neutral_success_rate"]
        and nonnegative >= _EXPECTED_ACCEPTANCE["min_nonnegative_units"]
        and forecast_changes >= _EXPECTED_ACCEPTANCE["min_forecast_preference_change_units"]
        and posterior_matches >= _EXPECTED_ACCEPTANCE["min_target_posterior_match_units"]
    )
    return {
        "phase": "pre-inference-roster-conditional-construction-and-calibration",
        "revision": config["revision"],
        "model_calls": 0,
        "formation_depth": 96,
        "calibration_evaluation_trials_per_policy": 512,
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
        "calibration_acceptance": dict(_EXPECTED_ACCEPTANCE),
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
