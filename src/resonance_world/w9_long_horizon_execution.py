"""Execution wrapper for corrected W9-06 full-compute accounting."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping

from . import w8_campaign as w8
from . import w9_long_horizon as base
from .w9_integrated import _phase_seeds, _read_json, _write_json

RESULT_VERSION = "w9-06-long-horizon-result-v0.5"


def _recompute_efficiencies(value: dict[str, Any]) -> None:
    compute = value["compute"]
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


def _correct_selected_compute(
    arm: Mapping[str, Any],
    config: Mapping[str, Any],
    *,
    field_count: int,
) -> dict[str, Any]:
    """Count the two source diagnostic frontier blocks omitted by the base formula."""

    value = json.loads(json.dumps(arm))
    horizon = int(config["long_horizon"]["cycles"])
    trials = int(config["service_trials"])
    source_diagnostic_compute = float(2 * horizon * field_count * trials)

    compute = value["compute"]
    compute["source_diagnostic_mission_execution_compute"] = source_diagnostic_compute
    compute["mission_execution_compute"] = (
        float(compute["mission_execution_compute"]) + source_diagnostic_compute
    )
    compute["incremental_total_measured_compute"] = (
        float(compute["incremental_total_measured_compute"]) + source_diagnostic_compute
    )
    compute["final_total_measured_compute_including_cycle0_embodied"] = (
        float(compute["final_total_measured_compute_including_cycle0_embodied"])
        + source_diagnostic_compute
    )
    _recompute_efficiencies(value)
    return value


def _correct_w8_compute(
    arm: Mapping[str, Any],
    config: Mapping[str, Any],
    *,
    field_count: int,
    organization_count: int,
) -> dict[str, Any]:
    """Count all reviewed W8 assay, coordination, and accounting operations."""

    value = json.loads(json.dumps(arm))
    horizon = int(config["long_horizon"]["cycles"])
    trials = int(config["service_trials"])
    coalition_mission_compute = float(3 * horizon * trials)
    source_diagnostic_compute = float((horizon + 1) * field_count * trials)
    standalone_coordination_compute = float(2 * horizon)
    withholding_cycles = {
        int(cycle)
        for cycle in config["long_horizon"]["stress_schedule"]["withholding_cycles"]
        if 0 <= int(cycle) < horizon
    }
    withholding_substitution_compute = float(len(withholding_cycles))
    budget_update_compute = float(horizon * organization_count)
    successor_activation_check_compute = float(horizon * field_count)
    total_added = (
        coalition_mission_compute
        + source_diagnostic_compute
        + standalone_coordination_compute
        + withholding_substitution_compute
        + budget_update_compute
        + successor_activation_check_compute
    )

    compute = value["compute"]
    compute["coalition_mission_execution_compute"] = coalition_mission_compute
    compute["source_diagnostic_mission_execution_compute"] = source_diagnostic_compute
    compute["standalone_comparator_pair_selection_compute"] = (
        standalone_coordination_compute
    )
    compute["withholding_substitution_coordination_compute"] = (
        withholding_substitution_compute
    )
    compute["neutral_budget_update_regulatory_compute"] = budget_update_compute
    compute["successor_activation_check_regulatory_compute"] = (
        successor_activation_check_compute
    )
    compute["mission_execution_compute"] = (
        float(compute["mission_execution_compute"])
        + coalition_mission_compute
        + source_diagnostic_compute
    )
    compute["organization_coordination_compute"] = (
        float(compute["organization_coordination_compute"])
        + standalone_coordination_compute
        + withholding_substitution_compute
    )
    compute["world_regulatory_estimation_compute"] = (
        float(compute["world_regulatory_estimation_compute"])
        + budget_update_compute
        + successor_activation_check_compute
    )
    compute["incremental_total_measured_compute"] = (
        float(compute["incremental_total_measured_compute"]) + total_added
    )
    compute["final_total_measured_compute_including_cycle0_embodied"] = (
        float(compute["final_total_measured_compute_including_cycle0_embodied"])
        + total_added
    )
    _recompute_efficiencies(value)
    return value


def _refresh_selected_gate(result: dict[str, Any], long_config: Mapping[str, Any]) -> None:
    selected = result["arms"]["selected_W9"]
    growth = selected["compute_normalized_world_stock_growth"]
    result["gates"]["compute_normalized_world_stock_growth_gt_2pct"] = (
        growth is not None
        and float(growth)
        > float(long_config["required_compute_normalized_growth_fraction"])
    )
    gate = all(bool(value) for value in result["gates"].values())
    result["long_horizon_gate"] = gate
    source_org_pass = bool(result["gates"]["source_loss_at_most_2pp"]) and bool(
        result["gates"]["organization_within_minus_2pp_of_W7"]
    )
    if gate:
        result["classification"] = "regenerative_allocation"
    elif source_org_pass:
        result["classification"] = "sustainable_but_non_generative_allocation"
    else:
        result["classification"] = "long_horizon_gate_failed"


def run_w9_06_execution(
    population: w8.W8Population,
    market_config: Mapping[str, Any],
    long_horizon_config: Mapping[str, Any],
    replacement: Mapping[str, Any],
    *,
    phase: str,
) -> dict[str, Any]:
    """Run W9-06 and apply reviewed full-compute accounting corrections."""

    result = base.run_w9_06(
        population,
        market_config,
        long_horizon_config,
        replacement,
        phase=phase,
    )
    merged = base._merged_config(market_config, long_horizon_config)
    horizon = int(merged["long_horizon"]["cycles"])
    trials = int(merged["service_trials"])
    field_count = len(population.portable_by_field)
    organization_count = len(merged["organizations"])

    selected = _correct_selected_compute(
        result["arms"]["selected_W9"],
        merged,
        field_count=field_count,
    )
    result["arms"]["selected_W9"] = selected
    result["arms"]["W7_unrestricted"] = selected
    result["arms"]["W9_without_portfolio_development"] = selected
    result["arms"]["W8_neutral_full_regulatory_charter"] = _correct_w8_compute(
        result["arms"]["W8_neutral_full_regulatory_charter"],
        merged,
        field_count=field_count,
        organization_count=organization_count,
    )
    _refresh_selected_gate(result, long_horizon_config)

    withholding_cycles = {
        int(cycle)
        for cycle in merged["long_horizon"]["stress_schedule"]["withholding_cycles"]
        if 0 <= int(cycle) < horizon
    }
    result["version"] = RESULT_VERSION
    result["accounting_corrections"] = {
        "selected_source_frontier_diagnostics": {
            "additional_blocks_per_field_cycle": 2,
            "cycles": horizon,
            "field_count": field_count,
            "trials_per_block": trials,
            "mission_execution_compute_added": float(
                2 * horizon * field_count * trials
            ),
        },
        "w8_coalition_mission_execution": {
            "trial_blocks_per_cycle": 3,
            "cycles": horizon,
            "trials_per_block": trials,
            "mission_execution_compute_added": float(3 * horizon * trials),
        },
        "w8_source_frontier_diagnostics": {
            "additional_field_blocks": (horizon + 1) * field_count,
            "cycles": horizon,
            "field_count": field_count,
            "trials_per_block": trials,
            "mission_execution_compute_added": float(
                (horizon + 1) * field_count * trials
            ),
        },
        "w8_standalone_comparator_pair_selection": {
            "pair_selections_per_cycle": 2,
            "cycles": horizon,
            "organization_coordination_compute_added": float(2 * horizon),
        },
        "w8_withholding_substitution": {
            "withholding_cycles": sorted(withholding_cycles),
            "organization_coordination_compute_added": float(len(withholding_cycles)),
        },
        "w8_neutral_budget_updates": {
            "updates_per_cycle": organization_count,
            "cycles": horizon,
            "world_regulatory_estimation_compute_added": float(
                horizon * organization_count
            ),
        },
        "w8_successor_activation_checks": {
            "checks_per_cycle": field_count,
            "cycles": horizon,
            "world_regulatory_estimation_compute_added": float(horizon * field_count),
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
