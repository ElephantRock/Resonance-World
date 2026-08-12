"""W9-05 integrated regenerative-market diagnostic matrix and eligibility gate."""

from __future__ import annotations

import argparse
import itertools
import json
import statistics
from pathlib import Path
from typing import Any, Mapping, Sequence

from .w7_competition import TalentMarket, TalentOffer
from .w8_campaign import (
    W8Population,
    _generate_offers,
    _market_agent_ids,
    _mean,
    _new_market,
    _primary_additions,
    _unrestricted_allocation,
    capped_rival_allocation,
    load_population,
    run_w8_05,
    simulate_circulation,
)
from .w9_calibration_execution import _estimate_marginal_cost
from .w9_leasing import simulate_w9_02_arm
from .w9_portfolio import _public_frontier

RESULT_VERSION = "w9-05-integrated-market-result-v0.1"
MECHANISMS = ("C", "L", "P")


def _read_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _write_json(path: str | Path, value: object) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _phase_seeds(config: Mapping[str, Any], phase: str) -> list[int]:
    key = f"{phase}_seeds"
    if key not in config:
        raise ValueError(f"unsupported W9 phase: {phase}")
    return [int(value) for value in config[key]]


def _bits_key(bits: Mapping[str, bool]) -> str:
    return "".join(f"{name}{int(bool(bits[name]))}" for name in MECHANISMS)


def _bits(c: bool, l: bool, p: bool) -> dict[str, bool]:
    return {"C": c, "L": l, "P": p}


def _public_candidates_by_field(
    population: W8Population,
) -> tuple[dict[str, Mapping[str, Any]], dict[str, tuple[Mapping[str, Any], ...]]]:
    by_id: dict[str, Mapping[str, Any]] = {}
    by_field: dict[str, list[Mapping[str, Any]]] = {}
    for row in population.candidates:
        agent_id = str(row["agent_id"])
        field_id = str(row["field_id"])
        by_id[agent_id] = row
        by_field.setdefault(field_id, []).append(row)
    return by_id, {
        field_id: tuple(sorted(rows, key=lambda item: str(item["agent_id"])))
        for field_id, rows in by_field.items()
    }


def conjunctive_allocation(
    population: W8Population,
    offers: Sequence[TalentOffer],
    config: Mapping[str, Any],
    *,
    window_id: str,
    use_criticality: bool,
    use_portfolio_permission: bool,
) -> tuple[TalentMarket, tuple[dict[str, Any], ...]]:
    """Apply frozen C and P gates conjunctively in unchanged W7 settlement order."""

    if not use_criticality and not use_portfolio_permission:
        return (
            _unrestricted_allocation(population, offers, config, window_id=window_id),
            (),
        )

    candidate_by_id, candidates_by_field = _public_candidates_by_field(population)
    by_agent: dict[str, list[TalentOffer]] = {}
    for offer in offers:
        by_agent.setdefault(offer.agent_id, []).append(offer)
    balances = {
        str(row["organization_id"]): int(config["organization_budget"])
        for row in config["organizations"]
    }
    unavailable = {field_id: set() for field_id in candidates_by_field}
    conservative_budget = {field_id: 0.0 for field_id in candidates_by_field}
    baseline_frontier = {
        field_id: _public_frontier(rows, config, unavailable_agent_ids=frozenset())
        for field_id, rows in candidates_by_field.items()
    }
    winners: list[TalentOffer] = []
    decisions: list[dict[str, Any]] = []

    for agent_id in sorted(by_agent):
        candidate = candidate_by_id.get(agent_id)
        if candidate is None:
            raise ValueError(f"offer has no public candidate: {agent_id}")
        field_id = str(candidate["field_id"])
        winner = next(
            (
                offer
                for offer in sorted(
                    by_agent[agent_id],
                    key=lambda item: (-item.bid, item.organization_id, item.offer_id),
                )
                if balances.get(offer.organization_id, 0) >= offer.bid
            ),
            None,
        )
        if winner is None:
            decisions.append(
                {
                    "agent_id": agent_id,
                    "decision": "no_affordable_offer",
                    "source_field_id": field_id,
                }
            )
            continue

        before_ids = frozenset(unavailable[field_id])
        row: dict[str, Any] = {
            "agent_id": agent_id,
            "bid": winner.bid,
            "organization_id": winner.organization_id,
            "quote_context_agent_ids": sorted(before_ids),
            "source_field_id": field_id,
        }
        criticality_ok = True
        portfolio_ok = True

        if use_criticality:
            estimate = _estimate_marginal_cost(
                candidates_by_field[field_id],
                agent_id=agent_id,
                unavailable_agent_ids=before_ids,
                config=config,
            )
            would_use = conservative_budget[field_id] + estimate.budget_cost_pp
            criticality_ok = would_use <= float(config["source_loss_budget_pp"]) + 1e-12
            row.update(
                {
                    "criticality_estimated_loss_pp": estimate.estimated_loss_pp,
                    "criticality_msc_budget_pp": estimate.budget_cost_pp,
                    "criticality_source_budget_before_pp": conservative_budget[field_id],
                    "criticality_source_budget_if_awarded_pp": would_use,
                }
            )
        else:
            estimate = None
            would_use = conservative_budget[field_id]

        if use_portfolio_permission:
            after_ids = before_ids | {agent_id}
            before = _public_frontier(
                candidates_by_field[field_id],
                config,
                unavailable_agent_ids=before_ids,
            )
            after = _public_frontier(
                candidates_by_field[field_id],
                config,
                unavailable_agent_ids=after_ids,
            )
            baseline = baseline_frontier[field_id]
            incremental_pp = (before.weighted_value - after.weighted_value) * 100.0
            cumulative_pp = (baseline.weighted_value - after.weighted_value) * 100.0
            stratum_declines = {
                skill: (baseline.by_skill[skill] - after.by_skill[skill]) * 100.0
                for skill in baseline.by_skill
            }
            max_stratum_pp = max(stratum_declines.values(), default=0.0)
            portfolio_ok = (
                incremental_pp <= float(config["source_incremental_bound_pp"]) + 1e-12
                and cumulative_pp <= float(config["source_cumulative_bound_pp"]) + 1e-12
                and max_stratum_pp <= float(config["stratum_cumulative_bound_pp"]) + 1e-12
            )
            row.update(
                {
                    "portfolio_cumulative_predicted_loss_pp": cumulative_pp,
                    "portfolio_incremental_predicted_loss_pp": incremental_pp,
                    "portfolio_max_stratum_predicted_loss_pp": max_stratum_pp,
                }
            )

        if not criticality_ok or not portfolio_ok:
            reasons: list[str] = []
            if not criticality_ok:
                reasons.append("criticality_budget")
            if not portfolio_ok:
                reasons.append("functional_coverage")
            decisions.append({**row, "decision": "rejected", "reasons": reasons})
            continue

        balances[winner.organization_id] -= winner.bid
        unavailable[field_id].add(agent_id)
        if use_criticality and estimate is not None:
            conservative_budget[field_id] = would_use
        winners.append(winner)
        decisions.append({**row, "decision": "awarded"})

    market = _new_market(population, config)
    for offer in winners:
        market.submit_offer(offer)
    settled = market.settle(window_id)
    if {contract.agent_id for contract in settled} != {offer.agent_id for offer in winners}:
        raise AssertionError("W9-05 conjunctive settlement diverged from frozen winners")
    return market, tuple(decisions)


def _inequality_pct(rates_pct: Mapping[str, float]) -> float:
    values = [float(value) for value in rates_pct.values()]
    return statistics.pstdev(values) if values else 0.0


def _mean_continuity(value: Mapping[str, float]) -> float:
    return _mean([float(item) for item in value.values()]) if value else 0.0


def _arm_result(
    base_population: W8Population,
    portfolio_population: W8Population,
    config: Mapping[str, Any],
    *,
    phase: str,
    bits: Mapping[str, bool],
) -> dict[str, Any]:
    population = portfolio_population if bits["P"] else base_population
    key = _bits_key(bits)
    window_id = f"w9-05:{phase}:{key}"
    offers = _generate_offers(population, config, window_id=window_id)
    market, decisions = conjunctive_allocation(
        population,
        offers,
        config,
        window_id=window_id,
        use_criticality=bool(bits["C"]),
        use_portfolio_permission=bool(bits["P"]),
    )
    mode = "lease-zero-recovery" if bits["L"] else "permanent"
    service = simulate_w9_02_arm(
        population,
        market,
        config,
        phase=f"{phase}:w9-05",
        window_id=window_id,
        mode=mode,
    )
    rates = {
        str(org): float(value)
        for org, value in dict(service["organization_rates_pct"]).items()
    }
    field_count = len(_phase_seeds(config, phase))
    development_compute = (
        field_count * int(config["development_resident_agent_cycle_units_per_field"])
        if bits["P"]
        else 0
    )
    result: dict[str, Any] = {
        "allocation_churn": 0.0,
        "bits": {name: bool(bits[name]) for name in MECHANISMS},
        "contract_count": len(_market_agent_ids(market, window_id=window_id)),
        "contracted_agent_ids": sorted(_market_agent_ids(market, window_id=window_id)),
        "development_compute_units": development_compute,
        "external_service_volume_agent_windows": int(service["external_agent_window_exposures"]),
        "forced_substitution_fraction": float(service["forced_substitution_fraction"]),
        "mean_organization_success_pct": float(service["mean_organization_success_pct"]),
        "mean_source_loss_pp": float(service["mean_source_loss_pp"]),
        "organization_outcome_inequality_sd_pp": _inequality_pct(rates),
        "organization_rates_pct": rates,
        "roster_pair_continuity": _mean_continuity(service["pair_continuity"]),
        "source_unavailable_equivalent_agent_windows": float(
            service["source_unavailable_equivalent_agent_windows"]
        ),
        "useful_external_service_per_source_unavailable_window": service[
            "useful_external_service_per_source_unavailable_window"
        ],
        "window_mode": mode,
    }
    if decisions:
        result["allocation_decision_counts"] = {
            "awarded": sum(row.get("decision") == "awarded" for row in decisions),
            "rejected": sum(row.get("decision") == "rejected" for row in decisions),
            "no_affordable_offer": sum(
                row.get("decision") == "no_affordable_offer" for row in decisions
            ),
        }
    if bits["L"]:
        recovery = simulate_w9_02_arm(
            population,
            market,
            config,
            phase=f"{phase}:w9-05",
            window_id=window_id,
            mode="lease-one-window-recovery",
        )
        result["one_window_recovery_sensitivity"] = {
            "mean_organization_success_pct": float(recovery["mean_organization_success_pct"]),
            "mean_source_loss_pp": float(recovery["mean_source_loss_pp"]),
            "recovery_idle_source_agent_slots": int(
                recovery["recovery_idle_source_agent_slots"]
            ),
            "source_unavailable_equivalent_agent_windows": float(
                recovery["source_unavailable_equivalent_agent_windows"]
            ),
        }
    return result


def _registered_aliases() -> dict[str, str]:
    return {
        "full_C+L+P+K": "C1L1P1",
        "leave_one_out_C": "C0L1P1",
        "leave_one_out_L": "C1L0P1",
        "leave_one_out_P": "C1L1P0",
        "leave_one_out_K": "C1L1P1",
        "leave_two_out_C_L": "C0L0P1",
        "leave_two_out_C_P": "C0L1P0",
        "leave_two_out_C_K": "C0L1P1",
        "leave_two_out_L_P": "C1L0P0",
        "leave_two_out_L_K": "C1L0P1",
        "leave_two_out_P_K": "C1L1P0",
        "W7_unrestricted": "C0L0P0",
        "criticality_only": "C1L0P0",
        "leasing_only": "C0L1P0",
        "substitution_only": "C0L0P1",
        "leasing_plus_substitution": "C0L1P1",
    }


def _factorial_interactions(arms: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    results: dict[str, Any] = {}
    for first_index, first in enumerate(MECHANISMS):
        for second in MECHANISMS[first_index + 1 :]:
            other = next(name for name in MECHANISMS if name not in {first, second})
            org_interactions: list[float] = []
            source_interactions: list[float] = []
            for other_value in (False, True):
                cells: dict[tuple[bool, bool], Mapping[str, Any]] = {}
                for a, b in itertools.product((False, True), repeat=2):
                    bits = {name: False for name in MECHANISMS}
                    bits[first] = a
                    bits[second] = b
                    bits[other] = other_value
                    cells[(a, b)] = arms[_bits_key(bits)]
                org_interactions.append(
                    float(cells[(True, True)]["mean_organization_success_pct"])
                    - float(cells[(True, False)]["mean_organization_success_pct"])
                    - float(cells[(False, True)]["mean_organization_success_pct"])
                    + float(cells[(False, False)]["mean_organization_success_pct"])
                )
                source_interactions.append(
                    float(cells[(True, True)]["mean_source_loss_pp"])
                    - float(cells[(True, False)]["mean_source_loss_pp"])
                    - float(cells[(False, True)]["mean_source_loss_pp"])
                    + float(cells[(False, False)]["mean_source_loss_pp"])
                )
            results[f"{first}:{second}"] = {
                "organization_interaction_pp": _mean(org_interactions),
                "source_loss_interaction_pp": _mean(source_interactions),
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
