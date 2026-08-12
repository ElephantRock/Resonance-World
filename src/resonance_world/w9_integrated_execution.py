"""Execution wrapper for the preregistered W9-05 integrated-market assay."""

from __future__ import annotations

import argparse
import itertools
import json
from pathlib import Path
from typing import Any, Mapping

from .w8_campaign import W8Population, load_population
from .w9_integrated import (
    MECHANISMS,
    RESULT_VERSION,
    _arm_result,
    _bits_key,
    _factorial_interactions,
    _phase_seeds,
    _read_json,
    _registered_aliases,
    _source_reduction_fraction,
    _w8_comparator,
    _write_json,
)


def run_w9_05_execution(
    base_population: W8Population,
    portfolio_population: W8Population,
    config: Mapping[str, Any],
    w8_replacement: Mapping[str, Any],
    *,
    phase: str,
) -> dict[str, Any]:
    """Run the frozen diagnostic matrix while enforcing upstream eligibility on primary."""

    if len(base_population.portable_by_id) != len(portfolio_population.portable_by_id):
        raise ValueError("W9-05 base and portfolio populations must have equal headcount")
    if set(base_population.portable_by_field) != set(portfolio_population.portable_by_field):
        raise ValueError("W9-05 base and portfolio sources must cover the same Fields")

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
    included_upstream_eligible = all(
        bool(eligibility.get(name, False))
        for name in MECHANISMS
        if selected_bits[name]
    ) and not bool(eligibility.get("K"))
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
        "all_included_mechanisms_upstream_eligible": included_upstream_eligible,
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
        "registered_diagnostic_arms": registered,
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
    result = run_w9_05_execution(base, portfolio, config, replacement, phase=args.phase)
    _write_json(args.output, result)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
