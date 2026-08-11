"""Mathematically exact execution acceleration for W8.

This module changes no scientific rule. It replaces two hot calculations with equivalent
cached implementations before delegating to the frozen W8 execution wrapper, and installs
an outcome-neutral synthesis label correction.
"""

from __future__ import annotations

import itertools
from collections.abc import Mapping, Sequence
from typing import Any

from . import w8_campaign as base
from . import w8_execution as execution
from . import w8_synthesis
from .w6_mobility import PortableAgentState
from .w7_competition import TalentMarket, TalentOffer


def exact_source_frontier(
    states: Sequence[PortableAgentState],
    config: Mapping[str, Any],
) -> float:
    """Bitwise-equivalent source frontier with cached per-skill maxima."""
    if not states:
        return 0.0
    missions = list(config["home_service_missions"])
    trials = int(config["service_trials"])
    if not missions or trials <= 0:
        return 0.0
    skills = {str(mission["skill"]) for mission in missions}
    best_by_skill = {
        skill: max(base._source_probability(state, skill, config) for state in states)
        for skill in skills
    }
    total = 0.0
    for trial in range(trials):
        skill = str(missions[trial % len(missions)]["skill"])
        total += best_by_skill[skill]
    return total / trials


def fast_matched_source_loss_frontier(
    population: base.W8Population,
    offers: Sequence[TalentOffer],
    capped: base.AllocationSummary,
    config: Mapping[str, Any],
    *,
    window_id: str,
) -> tuple[TalentMarket | None, float | None]:
    """Same exhaustive allocation search with per-Field source-loss memoization."""
    by_org: dict[str, list[TalentOffer]] = {}
    for offer in offers:
        by_org.setdefault(offer.organization_id, []).append(offer)
    org_rows = list(config["organizations"])
    org_ids = [str(row["organization_id"]) for row in org_rows]
    options: list[list[tuple[TalentOffer, ...]]] = []
    for row in org_rows:
        org_id = str(row["organization_id"])
        size = len(capped.market.contracted_agents(org_id, window_id))
        values = base._roster_options(
            by_org.get(org_id, ()),
            size,
            int(config["organization_budget"]),
        )
        if not values:
            return None, None
        options.append(values)

    missions = {
        str(row["organization_id"]): base._organization_mission(row) for row in org_rows
    }
    expected_cache: dict[tuple[str, tuple[str, ...]], float] = {}
    baseline_by_field = {
        field_id: exact_source_frontier(states, config)
        for field_id, states in population.portable_by_field.items()
    }
    field_loss_cache: dict[tuple[str, frozenset[str]], float] = {}

    def aggregate_source_loss(removed: frozenset[str]) -> float:
        losses: list[float] = []
        for field_id, baseline_states in population.portable_by_field.items():
            local_removed = frozenset(
                agent_id
                for agent_id in removed
                if population.portable_by_id[agent_id].home_field_id == field_id
            )
            key = (field_id, local_removed)
            if key not in field_loss_cache:
                remaining = [
                    state for state in baseline_states if state.agent_id not in local_removed
                ]
                field_loss_cache[key] = baseline_by_field[field_id] - exact_source_frontier(
                    remaining, config
                )
            losses.append(field_loss_cache[key])
        return base._mean(losses)

    limit = capped.mean_source_loss + float(config["source_loss_match_tolerance"])
    best_score = -1.0
    best: tuple[tuple[TalentOffer, ...], ...] | None = None
    best_tie: tuple[tuple[str, ...], ...] | None = None

    for combo_set in itertools.product(*options):
        ids = [offer.agent_id for combo in combo_set for offer in combo]
        if len(ids) != len(set(ids)):
            continue
        removed = frozenset(ids)
        if aggregate_source_loss(removed) > limit + 1e-12:
            continue
        scores: list[float] = []
        for org_id, combo in zip(org_ids, combo_set, strict=True):
            key = (org_id, tuple(sorted(item.agent_id for item in combo)))
            if key not in expected_cache:
                expected_cache[key] = base._expected_org_success(
                    [population.portable_by_id[item.agent_id] for item in combo],
                    missions[org_id],
                    config,
                )
            scores.append(expected_cache[key])
        score = base._mean(scores)
        tie = tuple(tuple(sorted(item.agent_id for item in combo)) for combo in combo_set)
        if score > best_score + 1e-15 or (
            abs(score - best_score) <= 1e-15 and (best_tie is None or tie < best_tie)
        ):
            best_score = score
            best = combo_set
            best_tie = tie

    if best is None:
        return None, None
    market = base._new_market(population, config)
    for combo in best:
        for offer in combo:
            market.submit_offer(offer)
    market.settle(window_id)
    return market, best_score


def install_fastpath() -> None:
    base._source_frontier = exact_source_frontier
    base.matched_source_loss_frontier = fast_matched_source_loss_frontier
    base.synthesize = w8_synthesis.synthesize


def main(argv: Sequence[str] | None = None) -> int:
    install_fastpath()
    return execution.main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
