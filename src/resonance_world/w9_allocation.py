"""W9-01 criticality-aware recruitment against the frozen W7/W8 market law."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from .w7_competition import TalentMarket, TalentOffer
from .w8_campaign import (
    W8Population,
    _generate_offers,
    _market_agent_ids,
    _new_market,
    _unrestricted_allocation,
    capped_rival_allocation,
    load_population,
    summarize_allocation,
)
from .w9_calibration_execution import _estimate_marginal_cost

RESULT_VERSION = "w9-01-criticality-allocation-result-v0.1"


@dataclass(frozen=True, slots=True)
class CriticalityAllocation:
    market: TalentMarket
    decisions: tuple[dict[str, Any], ...]
    predicted_loss_pp_by_field: dict[str, float]
    conservative_budget_pp_by_field: dict[str, float]


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


def _public_candidates_by_field(
    population: W8Population,
) -> tuple[dict[str, dict[str, Any]], dict[str, tuple[dict[str, Any], ...]]]:
    by_agent: dict[str, dict[str, Any]] = {}
    by_field: dict[str, list[dict[str, Any]]] = {}
    for candidate in population.candidates:
        agent_id = str(candidate["agent_id"])
        field_id = str(candidate["field_id"])
        if agent_id in by_agent:
            raise ValueError(f"duplicate public candidate: {agent_id}")
        by_agent[agent_id] = candidate
        by_field.setdefault(field_id, []).append(candidate)
    return (
        by_agent,
        {
            field_id: tuple(sorted(rows, key=lambda row: str(row["agent_id"])))
            for field_id, rows in by_field.items()
        },
    )


def _assert_frozen_selector(config: Mapping[str, Any]) -> None:
    offer_selector = dict(config["selector"])
    estimator_selector = dict(config["public_estimator"]["selector"])
    if offer_selector != estimator_selector:
        raise ValueError("offer and source-cost selectors must remain identical")


def criticality_aware_allocation(
    population: W8Population,
    offers: Sequence[TalentOffer],
    config: Mapping[str, Any],
    *,
    window_id: str,
) -> CriticalityAllocation:
    """Run W7 settlement order with only the registered source-cost constraint added."""

    _assert_frozen_selector(config)
    candidate_by_id, candidates_by_field = _public_candidates_by_field(population)
    by_agent: dict[str, list[TalentOffer]] = {}
    for offer in offers:
        by_agent.setdefault(offer.agent_id, []).append(offer)

    balances = {
        str(row["organization_id"]): int(config["organization_budget"])
        for row in config["organizations"]
    }
    unavailable_by_field: dict[str, set[str]] = {
        field_id: set() for field_id in candidates_by_field
    }
    predicted_loss_by_field = {field_id: 0.0 for field_id in candidates_by_field}
    conservative_budget_by_field = {field_id: 0.0 for field_id in candidates_by_field}
    source_budget_pp = float(config["source_loss_budget_pp"])
    winners: list[TalentOffer] = []
    decisions: list[dict[str, Any]] = []

    for agent_id in sorted(by_agent):
        candidate = candidate_by_id.get(agent_id)
        if candidate is None:
            raise ValueError(f"offer has no public candidate: {agent_id}")
        field_id = str(candidate["field_id"])
        ranked = sorted(
            by_agent[agent_id],
            key=lambda offer: (-offer.bid, offer.organization_id, offer.offer_id),
        )
        winner = next(
            (
                offer
                for offer in ranked
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

        current_unavailable = frozenset(unavailable_by_field[field_id])
        estimate = _estimate_marginal_cost(
            candidates_by_field[field_id],
            agent_id=agent_id,
            unavailable_agent_ids=current_unavailable,
            config=config,
        )
        current_budget = conservative_budget_by_field[field_id]
        would_use = current_budget + estimate.budget_cost_pp
        decision = {
            "agent_id": agent_id,
            "bid": winner.bid,
            "estimated_loss_pp": estimate.estimated_loss_pp,
            "evidence_refs": list(estimate.evidence_refs),
            "msc_budget_pp": estimate.budget_cost_pp,
            "organization_id": winner.organization_id,
            "quote_context_agent_ids": sorted(current_unavailable),
            "source_budget_before_pp": current_budget,
            "source_budget_if_awarded_pp": would_use,
            "source_field_id": field_id,
        }
        if would_use > source_budget_pp + 1e-12:
            decisions.append({**decision, "decision": "rejected_source_budget"})
            continue

        balances[winner.organization_id] -= winner.bid
        unavailable_by_field[field_id].add(agent_id)
        predicted_loss_by_field[field_id] += estimate.estimated_loss_pp
        conservative_budget_by_field[field_id] = would_use
        winners.append(winner)
        decisions.append({**decision, "decision": "awarded"})

    market = _new_market(population, config)
    for offer in winners:
        market.submit_offer(offer)
    settled = market.settle(window_id)
    if {contract.agent_id for contract in settled} != {offer.agent_id for offer in winners}:
        raise AssertionError("W9 criticality settlement diverged from preregistered winners")

    return CriticalityAllocation(
        market=market,
        decisions=tuple(decisions),
        predicted_loss_pp_by_field=predicted_loss_by_field,
        conservative_budget_pp_by_field=conservative_budget_by_field,
    )


def _allocation_summary(
    population: W8Population,
    market: TalentMarket,
    config: Mapping[str, Any],
    *,
    window_id: str,
    seed_salt: str,
) -> dict[str, Any]:
    summary = summarize_allocation(
        population,
        market,
        config,
        window_id=window_id,
        seed_salt=seed_salt,
    )
    ids = sorted(_market_agent_ids(market, window_id=window_id))
    return {
        "contract_count": len(ids),
        "contracted_agent_ids": ids,
        "field_source_loss_pp": {
            field_id: value * 100.0
            for field_id, value in sorted(summary.field_source_loss.items())
        },
        "mean_organization_success_pct": summary.mean_organization_success * 100.0,
        "mean_source_loss_pp": summary.mean_source_loss * 100.0,
        "organization_rates_pct": {
            org_id: value * 100.0
            for org_id, value in sorted(summary.organization_rates.items())
        },
    }


def _composition_delta(reference: Sequence[str], candidate: Sequence[str]) -> dict[str, Any]:
    reference_set, candidate_set = set(reference), set(candidate)
    union = reference_set | candidate_set
    return {
        "added_agent_ids": sorted(candidate_set - reference_set),
        "jaccard": len(reference_set & candidate_set) / len(union) if union else 1.0,
        "omitted_agent_ids": sorted(reference_set - candidate_set),
        "overlap_count": len(reference_set & candidate_set),
    }


def _source_reduction_fraction(unrestricted_pp: float, criticality_pp: float) -> float:
    if unrestricted_pp <= 1e-15:
        return 1.0 if criticality_pp <= 1e-15 else float("-inf")
    return (unrestricted_pp - criticality_pp) / unrestricted_pp


def run_w9_01(
    population: W8Population,
    config: Mapping[str, Any],
    calibration_acceptance: Mapping[str, Any],
    *,
    phase: str,
) -> dict[str, Any]:
    _assert_frozen_selector(config)
    if str(calibration_acceptance.get("classification")) != "calibrated_source_cost_estimator":
        raise ValueError("W9-01 principal claim requires accepted calibrated source-cost estimator")
    if not bool(calibration_acceptance.get("authorizes_w9_01_principal_claim")):
        raise ValueError("W9-00B acceptance does not authorize W9-01")

    window_id = f"w9-01:{phase}"
    seed_salt = f"w9-01:{phase}"
    offers = _generate_offers(population, config, window_id=window_id)
    unrestricted_market = _unrestricted_allocation(
        population,
        offers,
        config,
        window_id=window_id,
    )
    cap_market = capped_rival_allocation(
        population,
        offers,
        config,
        window_id=window_id,
        cap=int(config["source_reserve_cap_comparator"]),
    )
    criticality = criticality_aware_allocation(
        population,
        offers,
        config,
        window_id=window_id,
    )

    unrestricted = _allocation_summary(
        population,
        unrestricted_market,
        config,
        window_id=window_id,
        seed_salt=seed_salt,
    )
    cap2 = _allocation_summary(
        population,
        cap_market,
        config,
        window_id=window_id,
        seed_salt=seed_salt,
    )
    aware = _allocation_summary(
        population,
        criticality.market,
        config,
        window_id=window_id,
        seed_salt=seed_salt,
    )

    predicted_mean_loss = sum(criticality.predicted_loss_pp_by_field.values()) / len(
        criticality.predicted_loss_pp_by_field
    )
    conservative_mean_budget = sum(
        criticality.conservative_budget_pp_by_field.values()
    ) / len(criticality.conservative_budget_pp_by_field)
    realized_mean_loss = float(aware["mean_source_loss_pp"])
    reduction_fraction = _source_reduction_fraction(
        float(unrestricted["mean_source_loss_pp"]),
        realized_mean_loss,
    )
    contract_count = int(aware["contract_count"])
    loss_per_service = realized_mean_loss / contract_count if contract_count else None

    source_gate = realized_mean_loss <= float(config["source_loss_budget_pp"]) + 1e-12
    reduction_gate = reduction_fraction + 1e-12 >= float(
        config["required_source_loss_reduction_fraction"]
    )
    organization_gate = float(aware["mean_organization_success_pct"]) + 1e-12 >= (
        float(unrestricted["mean_organization_success_pct"])
        - float(config["effect_band_pp"])
    )
    gate = source_gate and reduction_gate and organization_gate

    aware["actual_allocation_calibration_residual_pp"] = (
        predicted_mean_loss - realized_mean_loss
    )
    aware["conservative_budget_pp_by_field"] = dict(
        sorted(criticality.conservative_budget_pp_by_field.items())
    )
    aware["mean_conservative_budget_used_pp"] = conservative_mean_budget
    aware["predicted_source_loss_pp_by_field"] = dict(
        sorted(criticality.predicted_loss_pp_by_field.items())
    )
    aware["predicted_mean_source_loss_pp"] = predicted_mean_loss
    aware["realized_source_loss_per_external_service_unit_pp"] = loss_per_service
    aware["source_loss_reduction_fraction_vs_unrestricted"] = reduction_fraction

    return {
        "calibration_classification": str(calibration_acceptance["classification"]),
        "cap_2": cap2,
        "classification": (
            "criticality_allocation_effective"
            if gate
            else "criticality_allocation_ineffective"
        ),
        "composition_vs_cap_2": _composition_delta(
            cap2["contracted_agent_ids"], aware["contracted_agent_ids"]
        ),
        "composition_vs_unrestricted": _composition_delta(
            unrestricted["contracted_agent_ids"], aware["contracted_agent_ids"]
        ),
        "criticality_aware": aware,
        "decisions": list(criticality.decisions),
        "gate": gate,
        "gates": {
            "organization_noninferiority": organization_gate,
            "source_loss_at_most_2pp": source_gate,
            "source_loss_reduction_at_least_50pct": reduction_gate,
        },
        "offer_count": len(offers),
        "phase": phase,
        "unrestricted": unrestricted,
        "version": RESULT_VERSION,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", required=True, choices=("discovery", "replication"))
    parser.add_argument("--source-dir", required=True, type=Path)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--calibration-acceptance", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)

    config = _read_json(args.config)
    acceptance = _read_json(args.calibration_acceptance)
    if not isinstance(config, dict) or not isinstance(acceptance, dict):
        raise ValueError("W9 allocation config and calibration acceptance must be objects")
    population = load_population(args.source_dir, expected_seeds=_phase_seeds(config, args.phase))
    result = run_w9_01(population, config, acceptance, phase=args.phase)
    _write_json(args.output, result)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
