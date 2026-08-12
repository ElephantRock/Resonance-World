mean(source_interactions),
            }
    for factor in MECHANISMS:
        results[f"{factor}:K"] = {
            "organization_interaction_pp": 0.0,
            "source_loss_interaction_pp": 0.0,
            "structurally_zero_because_K_none": True,
        }
    return results


def _source_reduction_fraction(reference_pp: float, candidate_pp: float) -> float:
    if reference_pp <= 1e-15:
        return 1.0 if candidate_pp <= reference_pp + 1e-15 else float("-inf")
    return (reference_pp - candidate_pp) / reference_pp


def _w8_comparator(
    population: W8Population,
    config: Mapping[str, Any],
    replacement: Mapping[str, Any],
    *,
    phase: str,
) -> dict[str, Any]:
    window_id = f"w8-01:{phase}:w9-05-comparator"
    offers = _generate_offers(population, config, window_id=window_id)
    unrestricted = _unrestricted_allocation(population, offers, config, window_id=window_id)
    cap = int(config["source_reserve"]["primary_cap"])
    capped = capped_rival_allocation(
        population,
        offers,
        config,
        window_id=window_id,
        cap=cap,
    )
    markets = {"unrestricted": unrestricted, f"cap-{cap}": capped}
    integrated = run_w8_05(
        population,
        markets,
        replacement,
        config,
        phase=f"{phase}:w9-05-comparator",
        window_id=window_id,
    )
    full = integrated["arms"]["R+C+D+K"]
    additions = _primary_additions(replacement, config)
    circulation = simulate_circulation(
        population,
        capped,
        config,
        phase=f"{phase}:w9-05-comparator",
        window_id=window_id,
        mode="4:2",
        additions_by_field=additions,
    )
    rates_pct = {
        str(org): float(value) * 100.0
        for org, value in dict(full["organization_rates"]).items()
    }
    primary_key = str(int(config["dividend"]["primary_basis_points"]))
    replacement_rows = replacement.get("basis_points", {}).get(primary_key, {}).get("fields", [])
    funded_cycles = sum(int(row.get("funded_cycles", 0)) for row in replacement_rows)
    return {
        "development_compute_units": funded_cycles,
        "development_credit_spend": funded_cycles
        * int(config["dividend"]["development_credit_per_cycle"]),
        "external_service_volume_agent_windows": int(
            circulation["external_agent_window_exposures"]
        ),
        "gate_under_original_w8_definition": bool(integrated["gate"]),
        "mean_organization_success_pct": float(full["mean_organization_success"]) * 100.0,
        "mean_source_loss_pp": float(full["mean_source_loss"]) * 100.0,
        "organization_outcome_inequality_sd_pp": _inequality_pct(rates_pct),
        "organization_rates_pct": rates_pct,
        "roster_pair_continuity": _mean_continuity(full["pair_continuity"]),
        "source_unavailable_equivalent_agent_windows": float(
            circulation["external_agent_window_exposures"]
        ),
        "w8_coalition_effect_pp": float(full["coalition_effect"]) * 100.0,
    }


def run_w9_05(
    base_population: W8Population,
    portfolio_population: W8Population,
    config: Mapping[str, Any],
    w8_replacement: Mapping[str, Any],
    *,
    phase: str,
) -> dict[str, Any]:
    if set(base_population.portable_by_id) != set(portfolio_population.portable_by_id):
        raise ValueError("W9-05 portfolio source must preserve the original 60 agent identities")

    canonical: dict[str, dict[str, Any]] = {}
    for values in itertools.product((False, True), repeat=3):
        bits = dict(zip(MECHANISMS, values, strict=True))
        canonical[_bits_key(bits)] = _arm_result(
            base_population,
            portfolio_population,
            config,
            phase=phase,
            bits=bits,
        )

    aliases = _registered_aliases()
    registered = {name: canonical[key] for name, key in aliases.items()}
    eligibility = dict(config["upstream_eligibility"])
    selected_bits = {
        "C": bool(eligibility.get("C", False)),
        "L": bool(eligibility.get("L", False)),
        "P": bool(eligibility.get("P", False)),
    }
    selected_key = _bits_key(selected_bits)
    selected = canonical[selected_key]
    baseline = canonical["C0L0P0"]

    baseline_source = float(baseline["mean_source_loss_pp"])
    selected_source = float(selected["mean_source_loss_pp"])
    reduction = _source_reduction_fraction(baseline_source, selected_source)
    gates = {
        "organization_noninferiority": (
            float(selected["mean_organization_success_pct"]) + 1e-12
            >= float(baseline["mean_organization_success_pct"])
            - float(config["effect_band_pp"])
        ),
        "source_loss_at_most_2pp": selected_source
        <= float(config["source_loss_bound_pp"]) + 1e-12,
        "source_loss_reduction_at_least_50pct": reduction + 1e-12
        >= float(config["required_source_loss_reduction_fraction"]),
        "organization_inequality_not_worse_by_more_than_2pp": (
            float(selected["organization_outcome_inequality_sd_pp"]) + 1e-12
            <= float(baseline["organization_outcome_inequality_sd_pp"])
            + float(config["organization_inequality_worsening_bound_pp"])
        ),
        "all_included_mechanisms_upstream_eligible": all(
            bool(eligibility.get(name, False)) for name in MECHANISMS if selected_bits[name]
        )
        and not bool(eligibility.get("K")),
    }
    gate = all(gates.values())
    selected_mechanisms = [name for name in MECHANISMS if selected_bits[name]]

    return {
        "canonical_diagnostic_arms": canonical,
        "classification": "integrated_static_gate_pass" if gate else "integrated_static_gate_failed",
        "direct_L_vs_P_vs_LP": {
            "L": canonical["C0L1P0"],
            "P": canonical["C0L0P1"],
            "L+P": canonical["C0L1P1"],
        },
        "gates": gates,
        "integrated_static_gate": gate,
        "pairwise_interactions": _factorial_interactions(canonical),
        "phase": phase,
        "registered_diagnostic_labels": aliases,
        "selected_mechanisms": selected_mechanisms,
        "selected_regime": selected,
        "selected_regime_source_loss_reduction_fraction_vs_W7": reduction,
        "structural_status": (
            "no_upstream_eligible_w9_mechanisms"
            if not selected_mechanisms and not eligibility.get("K")
            else "upstream_eligible_mechanisms_present"
        ),
        "upstream_eligibility": eligibility,
        "version": RESULT_VERSION,
        "W7_unrestricted": baseline,
        "W8_integrated_charter_comparator": _w8_comparator(
            base_population,
            config,
            w8_replacement,
            phase=phase,
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", required=True, choices=("discovery", "replication"))
    parser.add_argument("--base-source-dir", required=True, type=Path)
    parser.add_argument("--portfolio-source-dir", required=True, type=Path)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--w8-replacement", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)

    config = _read_json(args.config)
    replacement = _read_json(args.w8_replacement)
    if not isinstance(config, dict) or not isinstance(replacement, dict):
        raise ValueError("W9-05 config and W8 replacement comparator must be JSON objects")
    seeds = _phase_seeds(config, args.phase)
    base = load_population(args.base_source_dir, expected_seeds=seeds)
    portfolio = load_population(args.portfolio_source_dir, expected_seeds=seeds)
    result = run_w9_05(base, portfolio, config, replacement, phase=args.phase)
    _write_json(args.output, result)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())