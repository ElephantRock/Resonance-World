"""Model-free feasibility audit for the frozen Phase-5C roster geometry.

This script reads only pre-treatment competence capsules. It does not train
institutional memory, sample mission outcomes, or make model calls.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from resonance_world import w5_institution as w5

from experiments.piano_society.phase5c_constructor import (
    _choose_distinct_fields,
    _field_options,
    _read,
)

_TARGETS = ("role_specific", "cross_coverage")


def audit(capsules_path: str | Path, config_path: str | Path) -> dict[str, Any]:
    config = _read(config_path)
    if config.get("revision") != "piano-phase5c-roster-conditional-v1":
        raise ValueError("geometry audit requires the frozen Phase-5C v1 constructor config")
    source = config["source_fields"]
    calibration_pool = [str(item) for item in source["calibration_pool"]]
    confirmatory_pool = [str(item) for item in source["confirmatory_pool"]]
    skills = tuple(str(item) for item in config["skills"])
    eligibility = dict(config["eligibility"])
    designs = w5._load_designs(
        capsules_path,
        calibration_pool + confirmatory_pool,
        4,
    )
    options_by_field = {
        field_id: _field_options(designs[field_id], skills, eligibility)
        for field_id in calibration_pool + confirmatory_pool
    }

    field_geometry: dict[str, dict[str, Any]] = {}
    for field_id in calibration_pool + confirmatory_pool:
        field_geometry[field_id] = {}
        for target in _TARGETS:
            options = options_by_field[field_id][target]
            field_geometry[field_id][target] = {
                "eligible_candidate_count": len(options),
                "best_constructor_score": (
                    float(options[0]["constructor_score"]) if options else None
                ),
                "best_lead_skill": str(options[0]["lead_skill"]) if options else None,
                "best_support_skill": str(options[0]["support_skill"]) if options else None,
            }

    confirmatory_options = {
        field_id: options_by_field[field_id] for field_id in confirmatory_pool
    }
    feasible_twelve_unit_balances: list[dict[str, Any]] = []
    for role_count in range(13):
        cross_count = 12 - role_count
        try:
            selected = _choose_distinct_fields(
                confirmatory_options,
                role_count=role_count,
                cross_count=cross_count,
            )
        except ValueError:
            continue
        feasible_twelve_unit_balances.append(
            {
                "role_specific": role_count,
                "cross_coverage": cross_count,
                "summed_constructor_score": sum(
                    float(row["constructor_score"]) for row in selected
                ),
                "minimum_constructor_score": min(
                    float(row["constructor_score"]) for row in selected
                ),
                "selected_fields": [str(row["field_id"]) for row in selected],
            }
        )

    calibration_2_by_2_feasible = True
    try:
        calibration_selected = _choose_distinct_fields(
            {field_id: options_by_field[field_id] for field_id in calibration_pool},
            role_count=2,
            cross_count=2,
        )
    except ValueError:
        calibration_2_by_2_feasible = False
        calibration_selected = []

    return {
        "phase": "pre-treatment-geometry-feasibility-audit",
        "constructor_revision": config["revision"],
        "model_calls": 0,
        "memory_training_performed": False,
        "mission_outcomes_evaluated": False,
        "calibration_pool": calibration_pool,
        "confirmatory_pool": confirmatory_pool,
        "field_geometry": field_geometry,
        "calibration_2_by_2_feasible": calibration_2_by_2_feasible,
        "calibration_2_by_2_selected_fields": [
            str(row["field_id"]) for row in calibration_selected
        ],
        "confirmatory_fields_with_role_specific_option": sum(
            bool(options_by_field[field_id]["role_specific"])
            for field_id in confirmatory_pool
        ),
        "confirmatory_fields_with_cross_coverage_option": sum(
            bool(options_by_field[field_id]["cross_coverage"])
            for field_id in confirmatory_pool
        ),
        "confirmatory_fields_with_both_target_options": sum(
            bool(options_by_field[field_id]["role_specific"])
            and bool(options_by_field[field_id]["cross_coverage"])
            for field_id in confirmatory_pool
        ),
        "feasible_twelve_unit_balances": feasible_twelve_unit_balances,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("capsules")
    parser.add_argument("config")
    parser.add_argument("output")
    args = parser.parse_args()
    result = audit(args.capsules, args.config)
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
