"""Execution wrapper for corrected W9-06 full-compute accounting."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping

from . import w8_campaign as w8
from . import w9_long_horizon as base
from .w9_integrated import _phase_seeds, _read_json, _write_json

RESULT_VERSION = "w9-06-long-horizon-result-v0.3"


def _correct_w8_coalition_compute(
    arm: Mapping[str, Any],
    config: Mapping[str, Any],
) -> dict[str, Any]:
    """Count W8 coalition assay trials and standalone comparator selections."""

    value = json.loads(json.dumps(arm))
    horizon = int(config["long_horizon"]["cycles"])
    trials = int(config["service_trials"])
    coalition_mission_compute = float(3 * horizon * trials)
    standalone_coordination_compute = float(2 * horizon)
    total_added = coalition_mission_compute + standalone_coordination_compute

    compute = value["compute"]
    compute["coalition_mission_execution_compute"] = coalition_mission_compute
    compute["standalone_comparator_pair_selection_compute"] = (
        standalone_coordination_compute
    )
    compute["mission_execution_compute"] = (
        float(compute["mission_execution_compute"]) + coalition_mission_compute
    )
    compute["organization_coordination_compute"] = (
        float(compute["organization_coordination_compute"])
        + standalone_coordination_compute
    )
    compute["incremental_total_measured_compute"] = (
        float(compute["incremental_total_measured_compute"]) + total_added
    )
    compute["final_total_measured_compute_including_cycle0_embodied"] = (
        float(compute["final_total_measured_compute_including_cycle0_embodied"])
        + total_added
    )

    mission_compute = float(compute["mission_execution_compute"])
    value["service_efficiency"] = (
        float(value["successful_mission_evaluations"]) / mission_compute
        if mission_compute > 0
        else None
    )
    final_total = float(compute["final_total_measured_compute_including_cycle0_embodied"])
    value["total_efficiency_final"] = (
        float(value["final_world_stock"]) / final_total if final_total > 0 else None
    )
    initial_efficiency = value["total_efficiency_cycle0"]
    final_efficiency = value["total_efficiency_final"]
    value["compute_normalized_world_stock_growth"] = (
        float(final_efficiency) / float(initial_efficiency) - 1.0
        if initial_efficiency not in (None, 0.0) and final_efficiency is not None
        else None
    )
    return value


def run_w9_06_execution(
    population: w8.W8Population,
    market_config: Mapping[str, Any],
    long_horizon_config: Mapping[str, Any],
    replacement: Mapping[str, Any],
    *,
    phase: str,
) -> dict[str, Any]:
    """Run W9-06 and correct the W8 comparator's full-compute accounting."""

    result = base.run_w9_06(
        population,
        market_config,
        long_horizon_config,
        replacement,
        phase=phase,
    )
    merged = base._merged_config(market_config, long_horizon_config)
    w8_arm = result["arms"]["W8_neutral_full_regulatory_charter"]
    result["arms"]["W8_neutral_full_regulatory_charter"] = (
        _correct_w8_coalition_compute(w8_arm, merged)
    )
    horizon = int(merged["long_horizon"]["cycles"])
    trials = int(merged["service_trials"])
    result["version"] = RESULT_VERSION
    result["accounting_corrections"] = {
        "w8_coalition_mission_execution": {
            "trial_blocks_per_cycle": 3,
            "cycles": horizon,
            "trials_per_block": trials,
            "mission_execution_compute_added": float(3 * horizon * trials),
        },
        "w8_standalone_comparator_pair_selection": {
            "pair_selections_per_cycle": 2,
            "cycles": horizon,
            "organization_coordination_compute_added": float(2 * horizon),
        },
    }
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", required=True, choices=("discovery", "replication"))
    parser.add_argument("--source-dir", required=True, type=Path)
    parser.add_argument("--market-config", required=True, type=Path)
    parser.add_argument("--long-horizon-config", required=True, type=Path)
    parser.add_argument("--w8-replacement", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)

    market_config = _read_json(args.market_config)
    long_horizon_config = _read_json(args.long_horizon_config)
    replacement = _read_json(args.w8_replacement)
    if not all(
        isinstance(value, dict)
        for value in (market_config, long_horizon_config, replacement)
    ):
        raise ValueError("W9-06 inputs must be JSON objects")
    seeds = _phase_seeds(market_config, args.phase)
    population = w8.load_population(args.source_dir, expected_seeds=seeds)
    result = run_w9_06_execution(
        population,
        market_config,
        long_horizon_config,
        replacement,
        phase=args.phase,
    )
    _write_json(args.output, result)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
