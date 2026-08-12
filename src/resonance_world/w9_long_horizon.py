"""W9-06 long-horizon sustainability and generativity assay."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from . import w8_campaign as base
from .w8_execution import run_long_horizon_arm as run_w8_long_horizon_arm
from .w6_mobility import PortableAgentState
from .w9_integrated import _phase_seeds, _read_json, _write_json

RESULT_VERSION = "w9-06-long-horizon-result-v0.1"


def _merged_config(
    market_config: Mapping[str, Any], long_horizon_config: Mapping[str, Any]
) -> dict[str, Any]:
    value = json.loads(json.dumps(market_config))
    value["long_horizon"] = {
        key: item
        for key, item in long_horizon_config.items()
        if key
        in {
            "cycles",
            "neutral_base_budget",
            "compounding_reward_per_successful_trial",
            "compounding_max_budget",
            "stress_schedule",
        }
    }
    return value


def _embodied_compute(population: base.W8Population) -> float:
    return float(
        sum(
            sum(count for _, count in state.practice_by_skill)
            for state in population.portable_by_id.values()
        )
    )


def _raw_stock(states: Sequence[PortableAgentState], config: Mapping[str, Any]) -> float:
    value = base.capability_stock(states, config, cumulative_compute=1.0)
    return float(value["stock"])


def _mean_source_frontier(
    population: base.W8Population, config: Mapping[str, Any]
) -> float:
    return base._mean(
        [base._source_frontier(rows, config) for rows in population.portable_by_field.values()]
    )


def _efficiency_fields(
    *,
    initial_world_stock: float,
    final_world_stock: float,
    initial_source_stock: float,
    final_source_stock: float,
    embodied_compute: float,
    source_development_compute: float,
    mission_execution_compute: float,
    organization_coordination_compute: float,
    world_regulatory_estimation_compute: float,
    successful_mission_evaluations: float,
) -> dict[str, Any]:
    incremental_total = (
        source_development_compute
        + mission_execution_compute
        + organization_coordination_compute
        + world_regulatory_estimation_compute
    )
    final_total = embodied_compute + incremental_total
    initial_total_efficiency = (
        initial_world_stock / embodied_compute if embodied_compute > 0 else None
    )
    final_total_efficiency = final_world_stock / final_total if final_total > 0 else None
    normalized_growth = (
        final_total_efficiency / initial_total_efficiency - 1.0
        if initial_total_efficiency not in (None, 0.0)
        and final_total_efficiency is not None
        else None
    )
    source_growth = final_source_stock - initial_source_stock
    developmental_efficiency = (
        source_growth / source_development_compute
        if source_development_compute > 0
        else None
    )
    service_efficiency = (
        successful_mission_evaluations / mission_execution_compute
        if mission_execution_compute > 0
        else None
    )
    return {
        "compute": {
            "cycle0_embodied_compute": embodied_compute,
            "incremental_source_development_compute": source_development_compute,
            "mission_execution_compute": mission_execution_compute,
            "organization_coordination_compute": organization_coordination_compute,
            "world_regulatory_estimation_compute": world_regulatory_estimation_compute,
            "incremental_total_measured_compute": incremental_total,
            "final_total_measured_compute_including_cycle0_embodied": final_total,
        },
        "developmental_efficiency": developmental_efficiency,
        "service_efficiency": service_efficiency,
        "total_efficiency_cycle0": initial_total_efficiency,
        "total_efficiency_final": final_total_efficiency,
        "compute_normalized_world_stock_growth": normalized_growth,
        "source_accessible_capability_growth": source_growth,
        "successful_mission_evaluations": successful_mission_evaluations,
    }


def run_unrestricted_long_horizon(
    population: base.W8Population,
    config: Mapping[str, Any],
    *,
    phase: str,
) -> dict[str, Any]:
    horizon = int(config["long_horizon"]["cycles"])
    trials = int(config["service_trials"])
    field_ids = sorted(population.portable_by_field)
    org_ids = [str(row["organization_id"]) for row in config["organizations"]]
    stress = dict(config["long_horizon"]["stress_schedule"])
    source_shortage_cycles = {int(value) for value in stress["source_shortage_cycles"]}
    stride = int(stress["source_shortage_field_stride"])

    states = dict(population.portable_by_id)
    initial_world_stock = _raw_stock(list(states.values()), config)
    initial_source_stock = initial_world_stock
    embodied_compute = _embodied_compute(population)

    org_successes = {org_id: 0 for org_id in org_ids}
    source_success_equivalents = 0.0
    source_losses: list[float] = []
    max_field_losses: list[float] = []
    exposures = 0
    market_offer_evaluations = 0
    coordination_decisions = 0
    series: list[dict[str, Any]] = []

    for cycle in range(horizon):
        org_rows = base._cycle_organizations(config, cycle)
        cycle_cfg = base._cycle_config(config, org_rows)
        window = f"w9-06:{phase}:selected:{cycle}"
        offers = base._generate_offers(population, cycle_cfg, window_id=window)
        market_offer_evaluations += len(offers)

        excluded_fields: set[str] = set()
        if cycle in source_shortage_cycles:
            excluded_fields.add(field_ids[((cycle // 8) * stride) % len(field_ids)])
        eligible_offers = tuple(
            offer
            for offer in offers
            if population.portable_by_id[offer.agent_id].home_field_id not in excluded_fields
        )
        market = base._unrestricted_allocation(
            population, eligible_offers, cycle_cfg, window_id=window
        )
        external_ids = base._market_agent_ids(market, window_id=window)
        exposures += len(external_ids)

        for row in org_rows:
            org_id = str(row["organization_id"])
            roster_ids = [
                state.agent_id for state in market.contracted_agents(org_id, window)
            ]
            mission = base._organization_mission(row, suffix=f":w9-06:{cycle}")
            result = base._trial_rate(
                [states[agent_id].to_individual() for agent_id in roster_ids],
                mission,
                cycle_cfg,
                seed_salt=f"w9-06:{phase}:selected:{cycle}:{org_id}",
            )
            org_successes[org_id] += int(result["successes"])
            coordination_decisions += 1
            if result["lead_agent_id"] and result["support_agent_id"]:
                lead = str(result["lead_agent_id"])
                support = str(result["support_agent_id"])
                states[lead] = states[lead].with_learning(
                    {mission.lead_skill: 1},
                    evidence_ref=f"world://w9/{phase}/06/{cycle}/{org_id}/lead",
                )
                states[support] = states[support].with_learning(
                    {mission.support_skill: 1},
                    evidence_ref=f"world://w9/{phase}/06/{cycle}/{org_id}/support",
                )

        mean_loss, field_loss = base._field_losses(
            population,
            states,
            cycle_cfg,
            external_ids=external_ids,
            additions={},
        )
        source_losses.append(float(mean_loss))
        max_field_losses.append(max(field_loss.values()) if field_loss else 0.0)

        source_accessible: list[PortableAgentState] = []
        for field_id, baseline_rows in population.portable_by_field.items():
            home = [
                states[state.agent_id]
                for state in baseline_rows
                if state.agent_id not in external_ids
            ]
            source_accessible.extend(home)
            source_success_equivalents += base._source_frontier(home, cycle_cfg) * trials
        organization_accessible = [states[agent_id] for agent_id in external_ids]
        series.append(
            {
                "cycle": cycle,
                "world_stock": _raw_stock(list(states.values()), cycle_cfg),
                "source_accessible_stock": _raw_stock(source_accessible, cycle_cfg),
                "organization_accessible_stock": _raw_stock(
                    organization_accessible, cycle_cfg
                ),
                "external_agent_count": len(external_ids),
                "mean_source_loss_pp": float(mean_loss) * 100.0,
            }
        )

    org_trial_count = horizon * len(org_ids) * trials
    organization_successes = float(sum(org_successes.values()))
    mission_execution_compute = float(
        horizon * (len(org_ids) + len(field_ids)) * trials
    )
    final_world_stock = series[-1]["world_stock"] if series else initial_world_stock
    final_source_stock = (
        series[-1]["source_accessible_stock"] if series else initial_source_stock
    )
    efficiency = _efficiency_fields(
        initial_world_stock=initial_world_stock,
        final_world_stock=float(final_world_stock),
        initial_source_stock=initial_source_stock,
        final_source_stock=float(final_source_stock),
        embodied_compute=embodied_compute,
        source_development_compute=0.0,
        mission_execution_compute=mission_execution_compute,
        organization_coordination_compute=float(coordination_decisions),
        world_regulatory_estimation_compute=float(market_offer_evaluations),
        successful_mission_evaluations=organization_successes
        + source_success_equivalents,
    )
    return {
        "arm": "selected_W9_equals_W7_unrestricted",
        "mean_organization_success_pct": (
            100.0 * organization_successes / org_trial_count if org_trial_count else 0.0
        ),
        "organization_rates_pct": {
            org_id: 100.0 * successes / (horizon * trials)
            for org_id, successes in org_successes.items()
        },
        "mean_source_loss_pp": 100.0 * base._mean(source_losses),
        "max_single_field_loss_pp": 100.0 * max(max_field_losses, default=0.0),
        "external_agent_cycle_exposures": exposures,
        "initial_world_stock": initial_world_stock,
        "final_world_stock": float(final_world_stock),
        "initial_source_accessible_stock": initial_source_stock,
        "final_source_accessible_stock": float(final_source_stock),
        "stock_series": series,
        **efficiency,
    }


def summarize_w8_neutral(
    population: base.W8Population,
    config: Mapping[str, Any],
    replacement: Mapping[str, Any],
    *,
    phase: str,
) -> dict[str, Any]:
    raw = run_w8_long_horizon_arm(
        population, config, replacement, phase=phase, budget_mode="neutral"
    )
    horizon = int(config["long_horizon"]["cycles"])
    trials = int(config["service_trials"])
    org_count = len(config["organizations"])
    field_count = len(population.portable_by_field)
    embodied_compute = _embodied_compute(population)
    initial_world_stock = float(raw["initial_world_stock"]["stock"])
    final_world_stock = float(raw["final_world_stock"]["stock"])
    series = list(raw["capability_stock_series"])
    final_source_stock = (
        float(series[-1]["source_accessible"]["stock"])
        if series
        else initial_world_stock
    )

    development_credit_per_cycle = int(config["dividend"]["development_credit_per_cycle"])
    agents_per_field = int(config["agents_per_field"])
    development_compute = 0.0
    for event in raw.get("replacement_activation_events", []):
        credits = int(event["required_development_credits"])
        funded_cycles = credits / development_credit_per_cycle
        development_compute += funded_cycles * agents_per_field

    mission_execution_compute = float(
        horizon * (org_count + field_count) * trials
    )
    organization_coordination_compute = float(horizon * (org_count + 1))
    market_offer_evaluations = horizon * org_count * int(config["offer_count"])
    duty_cycle_checks = horizon * len(population.portable_by_id)
    dividend_accounting_events = int(raw["circulation_exposures"])
    regulatory_compute = float(
        market_offer_evaluations + duty_cycle_checks + dividend_accounting_events
    )

    organization_successes = (
        float(raw["mean_organization_success"]) * horizon * org_count * trials
    )
    baseline_source = _mean_source_frontier(population, config)
    mean_source_frontier = baseline_source - float(raw["mean_source_loss"])
    source_success_equivalents = mean_source_frontier * horizon * field_count * trials

    efficiency = _efficiency_fields(
        initial_world_stock=initial_world_stock,
        final_world_stock=final_world_stock,
        initial_source_stock=initial_world_stock,
        final_source_stock=final_source_stock,
        embodied_compute=embodied_compute,
        source_development_compute=development_compute,
        mission_execution_compute=mission_execution_compute,
        organization_coordination_compute=organization_coordination_compute,
        world_regulatory_estimation_compute=regulatory_compute,
        successful_mission_evaluations=organization_successes
        + source_success_equivalents,
    )
    return {
        "arm": "W8_neutral_full_regulatory_charter",
        "mean_organization_success_pct": 100.0
        * float(raw["mean_organization_success"]),
        "mean_source_loss_pp": 100.0 * float(raw["mean_source_loss"]),
        "max_single_field_loss_pp": 100.0 * float(raw["max_single_field_loss"]),
        "external_agent_cycle_exposures": int(raw["circulation_exposures"]),
        "activated_native_replacement_fields": list(
            raw["activated_native_replacement_fields"]
        ),
        "replacement_activation_events": list(raw["replacement_activation_events"]),
        "initial_world_stock": initial_world_stock,
        "final_world_stock": final_world_stock,
        "initial_source_accessible_stock": initial_world_stock,
        "final_source_accessible_stock": final_source_stock,
        **efficiency,
    }


def _developmental_efficiency_gate(
    candidate: float | None,
    comparator: float | None,
    improvement_fraction: float,
) -> bool:
    if candidate is None or comparator is None:
        return False
    return candidate + 1e-15 >= comparator + improvement_fraction * abs(comparator)


def run_w9_06(
    population: base.W8Population,
    market_config: Mapping[str, Any],
    long_horizon_config: Mapping[str, Any],
    replacement: Mapping[str, Any],
    *,
    phase: str,
) -> dict[str, Any]:
    config = _merged_config(market_config, long_horizon_config)
    selected = run_unrestricted_long_horizon(population, config, phase=phase)
    w8 = summarize_w8_neutral(population, config, replacement, phase=phase)

    selected_de = selected["developmental_efficiency"]
    w8_de = w8["developmental_efficiency"]
    gates = {
        "source_loss_at_most_2pp": float(selected["mean_source_loss_pp"])
        <= float(market_config["source_loss_bound_pp"]) + 1e-12,
        "organization_within_minus_2pp_of_W7": float(
            selected["mean_organization_success_pct"]
        )
        + 1e-12
        >= float(selected["mean_organization_success_pct"])
        - float(market_config["effect_band_pp"]),
        "compute_normalized_world_stock_growth_gt_2pct": selected[
            "compute_normalized_world_stock_growth"
        ]
        is not None
        and float(selected["compute_normalized_world_stock_growth"])
        > float(long_horizon_config["required_compute_normalized_growth_fraction"]),
        "positive_source_accessible_capability_growth": float(
            selected["source_accessible_capability_growth"]
        )
        > 0.0,
        "developmental_efficiency_at_least_20pct_better_than_W8": _developmental_efficiency_gate(
            None if selected_de is None else float(selected_de),
            None if w8_de is None else float(w8_de),
            float(long_horizon_config["developmental_efficiency_improvement_fraction"]),
        ),
    }
    gate = all(gates.values())
    source_org_pass = gates["source_loss_at_most_2pp"] and gates[
        "organization_within_minus_2pp_of_W7"
    ]
    if gate:
        classification = "regenerative_allocation"
    elif source_org_pass:
        classification = "sustainable_but_non_generative_allocation"
    else:
        classification = "long_horizon_gate_failed"

    return {
        "version": RESULT_VERSION,
        "phase": phase,
        "classification": classification,
        "long_horizon_gate": gate,
        "gates": gates,
        "selected_mechanisms": [],
        "structural_status": "selected_W9_equals_W7_and_noP_control",
        "arms": {
            "selected_W9": selected,
            "W7_unrestricted": selected,
            "W9_without_portfolio_development": selected,
            "W8_neutral_full_regulatory_charter": w8,
        },
        "alias_map": {
            "W7_unrestricted": "selected_W9",
            "W9_without_portfolio_development": "selected_W9",
        },
        "accounting": dict(long_horizon_config["compute_accounting"]),
    }


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
    population = base.load_population(args.source_dir, expected_seeds=seeds)
    result = run_w9_06(
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
