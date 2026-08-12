: Mapping[str, Any],
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
        >= float(w8["mean_organization_success_pct"])
        - float(market_config["effect_band_pp"]),
        "compute_normalized_world_stock_growth_gt_2pct": selected[
            "compute_normalized_world_stock_growth"
        ]
        is not None
        and float(selected["compute_normalized_world_stock_growth"])
        > float(long_horizon_config["required_compute_normalized_growth_fraction"]),
        "positive_source_accessible_capability_growth": float(
            selected["source_accessible_capability_growth"])
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
