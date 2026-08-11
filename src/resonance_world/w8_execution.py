# ruff: noqa: E501
"""Execution wrapper for the preregistered W8 campaign.

The base evaluator was frozen before outcomes. This wrapper tightens one pre-execution
accounting invariant: a native replacement may enter the long-horizon economy only
after its source has accumulated the exact funded development cost recorded by W8-03.
All other W8 functions delegate to :mod:`resonance_world.w8_campaign` unchanged.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from . import w8_campaign as base
from .w6_mobility import PortableAgentState
from .w8_regulation import BudgetUpdatePolicy, CirculationSchedule, SourceDividendPolicy


def replacement_activation_costs(
    replacement: Mapping[str, Any],
    config: Mapping[str, Any],
) -> dict[str, int]:
    """Return actual native-development spend required before successor activation."""
    basis = str(int(config["dividend"]["primary_basis_points"]))
    cost_per_cycle = int(config["dividend"]["development_credit_per_cycle"])
    rows = replacement.get("basis_points", {}).get(basis, {}).get("fields", [])
    costs: dict[str, int] = {}
    for row in rows:
        if row.get("status") != "native_successor_developed":
            continue
        funded_cycles = int(row.get("funded_cycles", 0))
        if funded_cycles <= 0:
            continue
        costs[str(row["field_id"])] = funded_cycles * cost_per_cycle
    return costs


def run_long_horizon_arm(
    population: base.W8Population,
    config: Mapping[str, Any],
    replacement: Mapping[str, Any],
    *,
    phase: str,
    budget_mode: str,
) -> dict[str, Any]:
    horizon = int(config["long_horizon"]["cycles"])
    base_budget = int(config["long_horizon"]["neutral_base_budget"])
    reward = int(config["long_horizon"]["compounding_reward_per_successful_trial"])
    max_budget = int(config["long_horizon"]["compounding_max_budget"])
    policy = BudgetUpdatePolicy(
        mode=budget_mode,
        base_budget=base_budget,
        reward_per_success=0 if budget_mode == "neutral" else reward,
        max_budget=max_budget,
    )
    budgets = {
        str(row["organization_id"]): base_budget for row in config["organizations"]
    }
    states = dict(population.portable_by_id)
    compute = float(
        sum(sum(count for _, count in state.practice_by_skill) for state in states.values())
    )
    initial_compute = compute
    available_replacements = {
        field_id: list(rows)
        for field_id, rows in base._primary_additions(replacement, config).items()
    }
    activation_cost = replacement_activation_costs(replacement, config)
    activated: dict[str, list[PortableAgentState]] = {}
    dividends: dict[str, int] = {}
    previous = {org: set() for org in budgets}
    contract_counts: dict[str, int] = {}
    budget_hhi: list[float] = []
    talent_hhi: list[float] = []
    source_losses: list[float] = []
    max_losses: list[float] = []
    org_rates: list[float] = []
    churn: list[float] = []
    stock_rows: list[dict[str, Any]] = []
    coalition_effects: list[float] = []
    exposures = 0
    schedule = CirculationSchedule(
        int(config["integrated_charter"]["external_windows"]),
        int(config["integrated_charter"]["home_windows"]),
    )
    stress = dict(config["long_horizon"]["stress_schedule"])
    field_ids = sorted(population.portable_by_field)
    initial_stock = base.capability_stock(
        list(states.values()), config, cumulative_compute=compute
    )
    activation_events: list[dict[str, Any]] = []

    for cycle in range(horizon):
        org_rows = base._cycle_organizations(config, cycle)
        cycle_cfg = base._cycle_config(config, org_rows)
        window = f"w8-06:{phase}:{budget_mode}:{cycle}"
        offers = base._generate_offers(population, cycle_cfg, window_id=window)
        excluded: set[str] = set()
        if cycle in {int(value) for value in stress["source_shortage_cycles"]}:
            stride = int(stress["source_shortage_field_stride"])
            excluded.add(field_ids[((cycle // 8) * stride) % len(field_ids)])
        eligible: set[str] = set()
        offsets = [int(value) for value in config["circulation"]["roster_offsets"]]
        for index, agent_id in enumerate(sorted(population.portable_by_id)):
            if schedule.phase(cycle + offsets[index % len(offsets)]) == "external":
                eligible.add(agent_id)
        rosters, spend, contracts = base._dynamic_allocation(
            population,
            offers,
            cap=int(config["integrated_charter"]["reserve_cap"]),
            budgets=budgets,
            excluded_fields=excluded,
            eligible_agent_ids=eligible,
        )
        external_ids = {str(row["agent_id"]) for row in contracts}
        exposures += len(external_ids)
        dividend_policy = SourceDividendPolicy(
            int(config["integrated_charter"]["dividend_basis_points"])
        )
        for row in contracts:
            agent_id = str(row["agent_id"])
            contract_counts[agent_id] = contract_counts.get(agent_id, 0) + 1
            field_id = str(row["source_field_id"])
            dividends[field_id] = dividends.get(field_id, 0) + dividend_policy.dividend(
                int(row["price"])
            )

        success_counts: dict[str, int] = {}
        rates: dict[str, float] = {}
        for row in org_rows:
            org = str(row["organization_id"])
            mission = base._organization_mission(row, suffix=f":long:{cycle}")
            result = base._trial_rate(
                [states[agent_id].to_individual() for agent_id in rosters.get(org, [])],
                mission,
                config,
                seed_salt=f"w8-06:{phase}:{budget_mode}:{cycle}:{org}",
            )
            rates[org] = float(result["success_rate"])
            success_counts[org] = int(result["successes"])
            if result["lead_agent_id"] and result["support_agent_id"]:
                lead = str(result["lead_agent_id"])
                support = str(result["support_agent_id"])
                states[lead] = states[lead].with_learning(
                    {mission.lead_skill: 1},
                    evidence_ref=(
                        f"world://w8/{phase}/long/{budget_mode}/{cycle}/{org}/lead"
                    ),
                )
                states[support] = states[support].with_learning(
                    {mission.support_skill: 1},
                    evidence_ref=(
                        f"world://w8/{phase}/long/{budget_mode}/{cycle}/{org}/support"
                    ),
                )
                compute += 2.0
        org_rates.append(base._mean(list(rates.values())))

        for field_id in field_ids:
            required = activation_cost.get(field_id)
            if (
                field_id not in activated
                and available_replacements.get(field_id)
                and required is not None
                and dividends.get(field_id, 0) >= required
            ):
                state = available_replacements[field_id].pop(0)
                activated[field_id] = [state]
                compute += sum(count for _, count in state.practice_by_skill)
                activation_events.append(
                    {
                        "cycle": cycle,
                        "field_id": field_id,
                        "required_development_credits": required,
                        "accumulated_dividend_credits": dividends[field_id],
                        "successor_agent_id": state.agent_id,
                    }
                )

        mean_loss, field_loss = base._field_losses(
            population,
            states,
            config,
            external_ids=external_ids,
            additions=activated,
        )
        source_losses.append(mean_loss)
        max_losses.append(max(field_loss.values()) if field_loss else 0.0)
        all_living = list(states.values()) + [
            state for rows in activated.values() for state in rows
        ]
        source_accessible = [
            state for state in states.values() if state.agent_id not in external_ids
        ] + [state for rows in activated.values() for state in rows]
        org_accessible = [states[agent_id] for agent_id in external_ids]
        stock_rows.append(
            {
                "cycle": cycle,
                "world": base.capability_stock(
                    all_living, config, cumulative_compute=compute
                ),
                "source_accessible": base.capability_stock(
                    source_accessible, config, cumulative_compute=compute
                ),
                "organization_accessible": base.capability_stock(
                    org_accessible, config, cumulative_compute=compute
                ),
                "cumulative_compute": compute,
            }
        )

        coal = config["coalition_missions"][cycle % len(config["coalition_missions"])]
        lead_org = str(coal["lead_organization_id"])
        support_org = str(coal["support_organization_id"])
        mission = base._mission(dict(coal["mission"]))
        structure = str(coal["structure"])
        lead_roster = [
            states[agent_id].to_individual() for agent_id in rosters.get(lead_org, [])
        ]
        support_roster = [
            states[agent_id].to_individual() for agent_id in rosters.get(support_org, [])
        ]
        pair = base._best_structured_pair(
            lead_roster,
            support_roster,
            mission,
            config,
            structure=structure,
            allow_swap=True,
        )
        if pair is None:
            coalition_effects.append(0.0)
        else:
            lead, support, _ = pair
            if (
                cycle in {int(value) for value in stress["withholding_cycles"]}
                and len(support_roster) >= 2
            ):
                ranked = sorted(
                    support_roster,
                    key=lambda state: (
                        state.practice(mission.support_skill),
                        state.agent_id,
                    ),
                    reverse=True,
                )
                support = next(
                    (state for state in ranked if state.agent_id != support.agent_id),
                    support,
                )
            coalition_rate = base._structured_rate(
                lead,
                support,
                mission,
                config,
                structure=structure,
                seed_salt=f"w8-06:{phase}:{budget_mode}:coalition:{cycle}",
            )
            standalone = max(
                base._standalone_structured_rate(
                    lead_roster,
                    mission,
                    config,
                    structure=structure,
                    seed_salt=f"w8-06:{phase}:{budget_mode}:coalition:{cycle}",
                ),
                base._standalone_structured_rate(
                    support_roster,
                    mission,
                    config,
                    structure=structure,
                    seed_salt=f"w8-06:{phase}:{budget_mode}:coalition:{cycle}",
                ),
            )
            coalition_effects.append(coalition_rate - standalone)

        current = {org: set(agent_ids) for org, agent_ids in rosters.items()}
        changed: list[float] = []
        for org, values in current.items():
            union = values | previous[org]
            changed.append(
                0.0 if not union else 1.0 - len(values & previous[org]) / len(union)
            )
            previous[org] = values
        churn.append(base._mean(changed))
        total_budget = sum(budgets.values())
        budget_hhi.append(
            sum((value / total_budget) ** 2 for value in budgets.values())
            if total_budget
            else 0.0
        )
        total_contracts = sum(contract_counts.values())
        talent_hhi.append(
            sum((count / total_contracts) ** 2 for count in contract_counts.values())
            if total_contracts
            else 0.0
        )
        budgets = {
            org: policy.next_budget(
                current_budget=budgets[org],
                spend=spend.get(org, 0),
                successes=success_counts.get(org, 0),
            )
            for org in budgets
        }

    initial_norm = initial_stock["compute_normalized_stock"]
    final_norm = (
        stock_rows[-1]["world"]["compute_normalized_stock"]
        if stock_rows
        else initial_stock["compute_normalized_stock"]
    )
    growth = (
        float(final_norm) / float(initial_norm) - 1.0
        if initial_norm not in (None, 0) and final_norm is not None
        else 0.0
    )
    mean_source = base._mean(source_losses)
    band = float(config["effect_band"])
    stock_band = float(config["stock_growth_band"])
    if growth > stock_band and mean_source <= band:
        label = "generative_circulation"
    elif abs(growth) <= stock_band and mean_source <= band:
        label = "conservative_circulation"
    elif growth < -stock_band or mean_source > band:
        label = "extractive"
    else:
        label = "mixed"
    return {
        "budget_mode": budget_mode,
        "long_run_label": label,
        "compute_normalized_world_stock_growth": growth,
        "initial_world_stock": initial_stock,
        "final_world_stock": stock_rows[-1]["world"] if stock_rows else initial_stock,
        "mean_source_loss": mean_source,
        "max_single_field_loss": max(max_losses) if max_losses else 0.0,
        "mean_organization_success": base._mean(org_rates),
        "mean_coalition_effect": base._mean(coalition_effects),
        "mean_roster_churn": base._mean(churn),
        "mean_budget_hhi": base._mean(budget_hhi),
        "final_budget_hhi": budget_hhi[-1] if budget_hhi else 0.0,
        "mean_talent_hhi": base._mean(talent_hhi),
        "final_budgets": budgets,
        "circulation_exposures": exposures,
        "activated_native_replacement_fields": sorted(activated),
        "replacement_activation_costs": activation_cost,
        "replacement_activation_events": activation_events,
        "initial_development_compute": initial_compute,
        "final_development_compute": compute,
        "capability_stock_series": stock_rows,
    }


def run_w8_06(
    population: base.W8Population,
    config: Mapping[str, Any],
    replacement: Mapping[str, Any],
    *,
    phase: str,
) -> dict[str, Any]:
    neutral = run_long_horizon_arm(
        population, config, replacement, phase=phase, budget_mode="neutral"
    )
    compounding = run_long_horizon_arm(
        population, config, replacement, phase=phase, budget_mode="compounding"
    )
    return {
        "neutral": neutral,
        "compounding": compounding,
        "compounding_minus_neutral_budget_hhi": (
            float(compounding["mean_budget_hhi"]) - float(neutral["mean_budget_hhi"])
        ),
        "compounding_minus_neutral_talent_hhi": (
            float(compounding["mean_talent_hhi"]) - float(neutral["mean_talent_hhi"])
        ),
    }


def main(argv: Sequence[str] | None = None) -> int:
    # Python resolves globals in base.run_phase at execution time. Replacing only this
    # function keeps W8-01..05, preparation and synthesis byte-for-byte on the frozen
    # evaluator while hardening W8-06's replacement accounting.
    base.run_w8_06 = run_w8_06
    return base.main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
