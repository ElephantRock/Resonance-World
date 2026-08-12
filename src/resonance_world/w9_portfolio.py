"""W9-03 functional redundancy permission and portfolio evaluation."""

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
    load_population,
    summarize_allocation,
)
from .w9_calibration_execution import _public_skill_probability

RESULT_VERSION = "w9-03-portfolio-redundancy-result-v0.1"


@dataclass(frozen=True, slots=True)
class PublicFrontier:
    weighted_value: float
    by_skill: dict[str, float]


@dataclass(frozen=True, slots=True)
class FunctionalAllocation:
    market: TalentMarket
    decisions: tuple[dict[str, Any], ...]


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


def _mission_weights(config: Mapping[str, Any]) -> tuple[tuple[str, float], ...]:
    missions = list(config["home_service_missions"])
    trials = int(config["service_trials"])
    counts: dict[str, int] = {}
    order: list[str] = []
    for trial in range(trials):
        skill = str(missions[trial % len(missions)]["skill"])
        counts[skill] = counts.get(skill, 0) + 1
        if skill not in order:
            order.append(skill)
    return tuple((skill, counts[skill] / trials) for skill in order)


def _public_frontier(
    candidates: Sequence[Mapping[str, Any]],
    config: Mapping[str, Any],
    *,
    unavailable_agent_ids: frozenset[str],
) -> PublicFrontier:
    available = [
        row for row in candidates if str(row["agent_id"]) not in unavailable_agent_ids
    ]
    if not available:
        return PublicFrontier(0.0, {skill: 0.0 for skill, _weight in _mission_weights(config)})
    by_skill = {
        skill: max(_public_skill_probability(row, skill, config) for row in available)
        for skill, _weight in _mission_weights(config)
    }
    weighted = sum(weight * by_skill[skill] for skill, weight in _mission_weights(config))
    return PublicFrontier(weighted, by_skill)


def functional_redundancy_allocation(
    population: W8Population,
    offers: Sequence[TalentOffer],
    config: Mapping[str, Any],
    *,
    window_id: str,
) -> FunctionalAllocation:
    """Preserve W7 settlement order while enforcing public functional coverage."""

    candidate_by_id = {str(row["agent_id"]): row for row in population.candidates}
    candidates_by_field: dict[str, list[dict[str, Any]]] = {}
    for row in population.candidates:
        candidates_by_field.setdefault(str(row["field_id"]), []).append(row)
    candidates_by_field = {
        field_id: sorted(rows, key=lambda row: str(row["agent_id"]))
        for field_id, rows in candidates_by_field.items()
    }
    baseline = {
        field_id: _public_frontier(tuple(rows), config, unavailable_agent_ids=frozenset())
        for field_id, rows in candidates_by_field.items()
    }
    unavailable: dict[str, set[str]] = {field_id: set() for field_id in candidates_by_field}
    balances = {
        str(row["organization_id"]): int(config["organization_budget"])
        for row in config["organizations"]
    }
    by_agent: dict[str, list[TalentOffer]] = {}
    for offer in offers:
        by_agent.setdefault(offer.agent_id, []).append(offer)
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

        before_ids = frozenset(unavailable[field_id])
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
        base = baseline[field_id]
        incremental_pp = (before.weighted_value - after.weighted_value) * 100.0
        cumulative_pp = (base.weighted_value - after.weighted_value) * 100.0
        stratum_declines = {
            skill: (base.by_skill[skill] - after.by_skill[skill]) * 100.0
            for skill in base.by_skill
        }
        max_stratum_pp = max(stratum_declines.values(), default=0.0)
        permitted = (
            incremental_pp <= float(config["source_incremental_bound_pp"]) + 1e-12
            and cumulative_pp <= float(config["source_cumulative_bound_pp"]) + 1e-12
            and max_stratum_pp <= float(config["stratum_cumulative_bound_pp"]) + 1e-12
        )
        decision = {
            "agent_id": agent_id,
            "bid": winner.bid,
            "cumulative_predicted_loss_pp": cumulative_pp,
            "incremental_predicted_loss_pp": incremental_pp,
            "max_stratum_predicted_loss_pp": max_stratum_pp,
            "organization_id": winner.organization_id,
            "quote_context_agent_ids": sorted(before_ids),
            "source_field_id": field_id,
            "stratum_predicted_loss_pp": dict(sorted(stratum_declines.items())),
        }
        if not permitted:
            decisions.append({**decision, "decision": "rejected_functional_coverage"})
            continue
        balances[winner.organization_id] -= winner.bid
        unavailable[field_id].add(agent_id)
        winners.append(winner)
        decisions.append({**decision, "decision": "awarded"})

    market = _new_market(population, config)
    for offer in winners:
        market.submit_offer(offer)
    settled = market.settle(window_id)
    if {contract.agent_id for contract in settled} != {offer.agent_id for offer in winners}:
        raise AssertionError("functional redundancy settlement diverged from frozen winners")
    return FunctionalAllocation(market=market, decisions=tuple(decisions))


def _redundancy_diagnostics(
    population: W8Population,
    config: Mapping[str, Any],
    *,
    removed_agent_ids: set[str],
) -> dict[str, Any]:
    threshold = float(config["diagnostic_probability_threshold"])
    ratio_gate = float(config["diagnostic_redundancy_ratio_threshold"])
    by_field: dict[str, list[dict[str, Any]]] = {}
    for row in population.candidates:
        by_field.setdefault(str(row["field_id"]), []).append(row)
    rows: list[dict[str, Any]] = []
    unused_counts: list[int] = []
    passing: list[float] = []
    for field_id in sorted(by_field):
        for skill, _weight in _mission_weights(config):
            qualifying = [
                str(row["agent_id"])
                for row in by_field[field_id]
                if _public_skill_probability(row, skill, config) >= threshold
            ]
            unused = [agent_id for agent_id in qualifying if agent_id not in removed_agent_ids]
            ratio = float(len(qualifying))
            rows.append(
                {
                    "diagnostic_redundancy_ratio": ratio,
                    "field_id": field_id,
                    "qualifying_agent_count": len(qualifying),
                    "skill": skill,
                    "unused_qualifying_agent_count": len(unused),
                }
            )
            unused_counts.append(len(unused))
            passing.append(float(ratio >= ratio_gate))
    return {
        "mean_unused_qualifying_agents_per_stratum": (
            sum(unused_counts) / len(unused_counts) if unused_counts else 0.0
        ),
        "ratio_threshold_pass_share": sum(passing) / len(passing) if passing else 0.0,
        "strata": rows,
    }


def _arm_evaluation(
    source_dir: str | Path,
    config: Mapping[str, Any],
    *,
    phase: str,
    arm_name: str,
    development_compute_units: int,
    development_tasks: int,
) -> dict[str, Any]:
    population = load_population(source_dir, expected_seeds=_phase_seeds(config, phase))
    window_id = f"w9-03:{phase}:{arm_name}"
    offers = _generate_offers(population, config, window_id=window_id)
    unrestricted_market = _unrestricted_allocation(
        population,
        offers,
        config,
        window_id=window_id,
    )
    functional = functional_redundancy_allocation(
        population,
        offers,
        config,
        window_id=window_id,
    )
    seed_salt = f"w9-03:{phase}"
    unrestricted = summarize_allocation(
        population,
        unrestricted_market,
        config,
        window_id=window_id,
        seed_salt=seed_salt,
    )
    protected = summarize_allocation(
        population,
        functional.market,
        config,
        window_id=window_id,
        seed_salt=seed_salt,
    )
    removed = _market_agent_ids(functional.market, window_id=window_id)
    source_loss_pp = protected.mean_source_loss * 100.0
    org_pct = protected.mean_organization_success * 100.0
    unrestricted_org_pct = unrestricted.mean_organization_success * 100.0
    viable = (
        source_loss_pp <= float(config["source_cumulative_bound_pp"]) + 1e-12
        and org_pct + 1e-12 >= unrestricted_org_pct - float(config["effect_band_pp"])
    )
    return {
        "arm": arm_name,
        "contract_count": len(removed),
        "contracted_agent_ids": sorted(removed),
        "decisions": list(functional.decisions),
        "development_compute_units": development_compute_units,
        "development_tasks": development_tasks,
        "field_source_loss_pp": {
            field_id: value * 100.0
            for field_id, value in sorted(protected.field_source_loss.items())
        },
        "mean_organization_success_pct": org_pct,
        "mean_source_loss_pp": source_loss_pp,
        "organization_rates_pct": {
            org_id: value * 100.0
            for org_id, value in sorted(protected.organization_rates.items())
        },
        "redundancy_diagnostic": _redundancy_diagnostics(
            population,
            config,
            removed_agent_ids=removed,
        ),
        "source_recovery_vs_unrestricted_pp": (
            unrestricted.mean_source_loss - protected.mean_source_loss
        )
        * 100.0,
        "unrestricted": {
            "contract_count": len(_market_agent_ids(unrestricted_market, window_id=window_id)),
            "mean_organization_success_pct": unrestricted_org_pct,
            "mean_source_loss_pp": unrestricted.mean_source_loss * 100.0,
        },
        "viable": viable,
    }


def run_w9_03(
    *,
    no_preparation_dir: str | Path,
    matched_control_dir: str | Path,
    portfolio_dir: str | Path,
    config: Mapping[str, Any],
    phase: str,
) -> dict[str, Any]:
    field_count = len(_phase_seeds(config, phase))
    units_per_field = int(config["development_resident_agent_cycle_units_per_field"])
    tasks_per_field = int(config["development_cycles"])
    arms = {
        "no-preparation": _arm_evaluation(
            no_preparation_dir,
            config,
            phase=phase,
            arm_name="no-preparation",
            development_compute_units=0,
            development_tasks=0,
        ),
        "matched-compute-control": _arm_evaluation(
            matched_control_dir,
            config,
            phase=phase,
            arm_name="matched-compute-control",
            development_compute_units=field_count * units_per_field,
            development_tasks=field_count * tasks_per_field,
        ),
        "portfolio": _arm_evaluation(
            portfolio_dir,
            config,
            phase=phase,
            arm_name="portfolio",
            development_compute_units=field_count * units_per_field,
            development_tasks=field_count * tasks_per_field,
        ),
    }
    no_prep = bool(arms["no-preparation"]["viable"])
    control = bool(arms["matched-compute-control"]["viable"])
    portfolio = bool(arms["portfolio"]["viable"])
    if no_prep:
        classification = "redundancy_already_sufficient"
        eligible = False
    elif portfolio and control:
        classification = "generic_development_sufficient"
        eligible = False
    elif portfolio:
        classification = "portfolio_redundancy_effective"
        eligible = True
    else:
        classification = "redundancy_not_efficient"
        eligible = False
    return {
        "arms": arms,
        "classification": classification,
        "eligible_for_w9_05_P": eligible,
        "phase": phase,
        "version": RESULT_VERSION,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", required=True, choices=("discovery", "replication"))
    parser.add_argument("--no-preparation-dir", required=True, type=Path)
    parser.add_argument("--matched-control-dir", required=True, type=Path)
    parser.add_argument("--portfolio-dir", required=True, type=Path)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    config = _read_json(args.config)
    if not isinstance(config, dict):
        raise ValueError("W9 portfolio config must be an object")
    result = run_w9_03(
        no_preparation_dir=args.no_preparation_dir,
        matched_control_dir=args.matched_control_dir,
        portfolio_dir=args.portfolio_dir,
        config=config,
        phase=args.phase,
    )
    _write_json(args.output, result)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
