# ruff: noqa: E501
"""W8 sustainable/generative capability-circulation evaluation.

Regulation changes allocation, timing, payments, coordination decisions and budget
trajectories only. Capability and task-success laws remain the validated Field/W4 laws.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from .w4a_joint_learning import IndividualState, JointAction, JointEnvironment, JointMission
from .w5a_organization import OrganizationState
from .w6_mobility import PortableAgentState
from .w7_campaign import _canonical_bytes, _contract_rows, _evidence_ref, _mean, _mission, _public_score, _seed
from .w7_competition import TalentMarket, TalentOffer
from .w8_regulation import BudgetUpdatePolicy, CirculationSchedule, SourceDividendPolicy


@dataclass(frozen=True, slots=True)
class AllocationSummary:
    market: TalentMarket
    mean_organization_success: float
    organization_rates: dict[str, float]
    mean_source_loss: float
    field_source_loss: dict[str, float]


@dataclass(frozen=True, slots=True)
class W8Population:
    candidates: tuple[dict[str, Any], ...]
    portable_by_id: dict[str, PortableAgentState]
    portable_by_field: dict[str, tuple[PortableAgentState, ...]]
    source_fields: tuple[dict[str, Any], ...]


def _read_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_json(path: str | Path, value: Any) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _field_seed(field_id: str) -> int:
    try:
        return int(field_id.rsplit("-", 1)[-1])
    except ValueError as exc:
        raise ValueError(f"cannot parse source seed from field_id: {field_id}") from exc


def load_population(source_dir: str | Path, *, expected_seeds: Sequence[int]) -> W8Population:
    source = Path(source_dir)
    candidates = _read_jsonl(source / "candidates.jsonl")
    capsules = _read_jsonl(source / "capsules.private.jsonl")
    source_fields = _read_json(source / "source-fields.json")
    expected = sorted(int(seed) for seed in expected_seeds)
    observed = sorted(int(row["seed"]) for row in source_fields)
    if observed != expected:
        raise ValueError(f"source seed mismatch: expected {expected}, observed {observed}")
    if "practice_by_skill" in json.dumps(candidates, sort_keys=True):
        raise ValueError("private practice leaked into W8 public source")
    by_candidate = {str(row["agent_id"]): row for row in candidates}
    if len(by_candidate) != len(candidates):
        raise ValueError("duplicate public candidate")
    states: dict[str, PortableAgentState] = {}
    by_field: dict[str, list[PortableAgentState]] = {}
    for row in capsules:
        agent_id = str(row["agent_id"])
        candidate = by_candidate.get(agent_id)
        if candidate is None:
            raise ValueError(f"private capsule lacks public candidate: {agent_id}")
        if str(candidate["field_id"]) != str(row["field_id"]):
            raise ValueError("public/private source-field mismatch")
        state = PortableAgentState(
            agent_id=agent_id,
            home_field_id=str(row["field_id"]),
            practice_by_skill=tuple((str(skill), int(count)) for skill, count in dict(row["practice_by_skill"]).items()),
            evidence_refs=(str(candidate["checkpoint_id"]), f"sha256:{candidate['source_evidence_sha256']}"),
        )
        states[agent_id] = state
        by_field.setdefault(state.home_field_id, []).append(state)
    expected_agents = len(expected) * 12
    if len(states) != expected_agents or len(candidates) != expected_agents:
        raise ValueError(f"W8 population mismatch: expected {expected_agents}, got {len(candidates)} public / {len(states)} private")
    if len(by_field) != len(expected) or any(len(rows) != 12 for rows in by_field.values()):
        raise ValueError("W8 requires 12 agents in each source Field")
    return W8Population(
        candidates=tuple(sorted(candidates, key=lambda row: (str(row["field_id"]), str(row["agent_id"])))),
        portable_by_id=states,
        portable_by_field={key: tuple(sorted(rows, key=lambda item: item.agent_id)) for key, rows in by_field.items()},
        source_fields=tuple(source_fields),
    )


def _source_probability(state: PortableAgentState, skill: str, config: Mapping[str, Any]) -> float:
    law = dict(config["source_service_law"])
    practiced = dict(state.practice_by_skill).get(skill, 0)
    return min(float(law["maximum_success_probability"]), float(law["base_success_probability"]) + float(law["practice_gain"]) * math.sqrt(practiced))


def _source_frontier(states: Sequence[PortableAgentState], config: Mapping[str, Any]) -> float:
    if not states:
        return 0.0
    missions = list(config["home_service_missions"])
    trials = int(config["service_trials"])
    total = 0.0
    for trial in range(trials):
        skill = str(missions[trial % len(missions)]["skill"])
        total += max(_source_probability(state, skill, config) for state in states)
    return total / trials


def _new_market(population: W8Population, config: Mapping[str, Any], *, organization_ids: Sequence[str] | None = None, budget: int | None = None) -> TalentMarket:
    market = TalentMarket()
    for agent_id in sorted(population.portable_by_id):
        market.register_agent(population.portable_by_id[agent_id])
    ids = list(organization_ids) if organization_ids is not None else [str(row["organization_id"]) for row in config["organizations"]]
    frozen_budget = int(config["organization_budget"]) if budget is None else int(budget)
    for organization_id in sorted(ids):
        market.register_organization(OrganizationState(organization_id, {}), budget=frozen_budget)
    return market


def _generate_offers(population: W8Population, config: Mapping[str, Any], *, window_id: str) -> tuple[TalentOffer, ...]:
    score_config = {"public_selector": dict(config["selector"])}
    offer_count = int(config["offer_count"])
    output: list[TalentOffer] = []
    for organization in config["organizations"]:
        organization_id = str(organization["organization_id"])
        requirements = {str(organization["lead_skill"]): 0.5, str(organization["support_skill"]): 0.5}
        ranked = sorted(
            ((_public_score(candidate, requirements, score_config), str(candidate["field_id"]), str(candidate["agent_id"]), candidate) for candidate in population.candidates),
            key=lambda item: (-item[0], item[1], item[2]),
        )
        for rank, (score, _field, agent_id, candidate) in enumerate(ranked[:offer_count], 1):
            output.append(TalentOffer(
                offer_id=f"{window_id}:{organization_id}:{rank:02d}:{agent_id}",
                organization_id=organization_id,
                agent_id=agent_id,
                window_id=window_id,
                bid=int(config["bid_base"]) + int(round(int(config["bid_span"]) * score)),
                evidence_refs=(_evidence_ref(candidate),),
            ))
    return tuple(output)


def _organization_mission(row: Mapping[str, Any], *, suffix: str = "") -> JointMission:
    return JointMission(f"w8-org:{row['organization_id']}{suffix}", f"w8-org:{row['organization_id']}{suffix}", str(row["lead_skill"]), str(row["support_skill"]))


def _environment(config: Mapping[str, Any]) -> JointEnvironment:
    law = dict(config["organization_environment"])
    return JointEnvironment(float(law["base_success_probability"]), float(law["practice_gain"]), float(law["maximum_role_success"]))


def _best_pair(states: Sequence[IndividualState], mission: JointMission, config: Mapping[str, Any]) -> tuple[IndividualState, IndividualState] | None:
    if len(states) < 2:
        return None
    env = _environment(config)
    best: tuple[float, str, str, IndividualState, IndividualState] | None = None
    for lead in states:
        for support in states:
            if lead.agent_id == support.agent_id:
                continue
            score = env.role_probability(lead, mission.lead_skill) * env.role_probability(support, mission.support_skill)
            candidate = (score, lead.agent_id, support.agent_id, lead, support)
            if best is None or candidate[:3] > best[:3]:
                best = candidate
    return None if best is None else (best[3], best[4])


def _trial_rate(states: Sequence[IndividualState], mission: JointMission, config: Mapping[str, Any], *, seed_salt: str) -> dict[str, Any]:
    pair = _best_pair(states, mission, config)
    if pair is None:
        return {"success_rate": 0.0, "lead_agent_id": None, "support_agent_id": None, "successes": 0}
    env = _environment(config)
    lead, support = pair
    successes = 0
    for trial in range(int(config["service_trials"])):
        successes += env.evaluate(lead, support, mission, JointAction(lead.agent_id, "lead"), JointAction(support.agent_id, "support"), seed=_seed(seed_salt, mission.mission_id, trial))
    return {"success_rate": successes / int(config["service_trials"]), "lead_agent_id": lead.agent_id, "support_agent_id": support.agent_id, "successes": successes}


def _expected_org_success(states: Sequence[PortableAgentState], mission: JointMission, config: Mapping[str, Any]) -> float:
    pair = _best_pair([state.to_individual() for state in states], mission, config)
    if pair is None:
        return 0.0
    env = _environment(config)
    return env.role_probability(pair[0], mission.lead_skill) * env.role_probability(pair[1], mission.support_skill)


def _organization_rates(market: TalentMarket, config: Mapping[str, Any], *, window_id: str, seed_salt: str) -> dict[str, float]:
    rates: dict[str, float] = {}
    for row in config["organizations"]:
        org_id = str(row["organization_id"])
        roster = [state.to_individual() for state in market.contracted_agents(org_id, window_id)]
        rates[org_id] = float(_trial_rate(roster, _organization_mission(row), config, seed_salt=f"{seed_salt}:{org_id}")["success_rate"])
    return rates


def _market_agent_ids(market: TalentMarket, *, window_id: str) -> set[str]:
    return {str(row["agent_id"]) for row in _contract_rows(market) if str(row["window_id"]) == window_id}


def _source_loss_from_ids(population: W8Population, removed_agent_ids: set[str], config: Mapping[str, Any], *, additions_by_field: Mapping[str, Sequence[PortableAgentState]] | None = None) -> tuple[float, dict[str, float]]:
    additions_by_field = additions_by_field or {}
    losses: dict[str, float] = {}
    for field_id, baseline in population.portable_by_field.items():
        remaining = [state for state in baseline if state.agent_id not in removed_agent_ids]
        remaining.extend(additions_by_field.get(field_id, ()))
        losses[field_id] = _source_frontier(baseline, config) - _source_frontier(remaining, config)
    return _mean(list(losses.values())), losses


def summarize_allocation(population: W8Population, market: TalentMarket, config: Mapping[str, Any], *, window_id: str, seed_salt: str, additions_by_field: Mapping[str, Sequence[PortableAgentState]] | None = None) -> AllocationSummary:
    rates = _organization_rates(market, config, window_id=window_id, seed_salt=seed_salt)
    loss, field_loss = _source_loss_from_ids(population, _market_agent_ids(market, window_id=window_id), config, additions_by_field=additions_by_field)
    return AllocationSummary(market, _mean(list(rates.values())), rates, loss, field_loss)


def _unrestricted_allocation(population: W8Population, offers: Sequence[TalentOffer], config: Mapping[str, Any], *, window_id: str) -> TalentMarket:
    market = _new_market(population, config)
    for offer in offers:
        market.submit_offer(offer)
    market.settle(window_id)
    return market


def capped_rival_allocation(population: W8Population, offers: Sequence[TalentOffer], config: Mapping[str, Any], *, window_id: str, cap: int) -> TalentMarket:
    by_agent: dict[str, list[TalentOffer]] = {}
    for offer in offers:
        by_agent.setdefault(offer.agent_id, []).append(offer)
    balances = {str(row["organization_id"]): int(config["organization_budget"]) for row in config["organizations"]}
    source_counts: dict[str, int] = {}
    winners: list[TalentOffer] = []
    for agent_id in sorted(by_agent):
        field_id = population.portable_by_id[agent_id].home_field_id
        if source_counts.get(field_id, 0) >= cap:
            continue
        winner = next((offer for offer in sorted(by_agent[agent_id], key=lambda item: (-item.bid, item.organization_id, item.offer_id)) if balances[offer.organization_id] >= offer.bid), None)
        if winner is None:
            continue
        balances[winner.organization_id] -= winner.bid
        source_counts[field_id] = source_counts.get(field_id, 0) + 1
        winners.append(winner)
    market = _new_market(population, config)
    for offer in winners:
        market.submit_offer(offer)
    market.settle(window_id)
    return market


def _roster_options(offers: Sequence[TalentOffer], size: int, budget: int) -> list[tuple[TalentOffer, ...]]:
    if size <= 0:
        return [()]
    return [combo for combo in itertools.combinations(offers, size) if sum(item.bid for item in combo) <= budget]


def matched_source_loss_frontier(population: W8Population, offers: Sequence[TalentOffer], capped: AllocationSummary, config: Mapping[str, Any], *, window_id: str) -> tuple[TalentMarket | None, float | None]:
    by_org: dict[str, list[TalentOffer]] = {}
    for offer in offers:
        by_org.setdefault(offer.organization_id, []).append(offer)
    org_rows = list(config["organizations"])
    org_ids = [str(row["organization_id"]) for row in org_rows]
    options: list[list[tuple[TalentOffer, ...]]] = []
    for row in org_rows:
        org_id = str(row["organization_id"])
        size = len(capped.market.contracted_agents(org_id, window_id))
        values = _roster_options(by_org.get(org_id, ()), size, int(config["organization_budget"]))
        if not values:
            return None, None
        options.append(values)
    missions = {str(row["organization_id"]): _organization_mission(row) for row in org_rows}
    loss_cache: dict[frozenset[str], float] = {}
    expected_cache: dict[tuple[str, tuple[str, ...]], float] = {}
    limit = capped.mean_source_loss + float(config["source_loss_match_tolerance"])
    best_score = -1.0
    best: tuple[tuple[TalentOffer, ...], ...] | None = None
    for combo_set in itertools.product(*options):
        ids = [offer.agent_id for combo in combo_set for offer in combo]
        if len(ids) != len(set(ids)):
            continue
        removed = frozenset(ids)
        if removed not in loss_cache:
            loss_cache[removed] = _source_loss_from_ids(population, set(removed), config)[0]
        if loss_cache[removed] > limit + 1e-12:
            continue
        scores: list[float] = []
        for org_id, combo in zip(org_ids, combo_set, strict=True):
            key = (org_id, tuple(sorted(item.agent_id for item in combo)))
            if key not in expected_cache:
                expected_cache[key] = _expected_org_success([population.portable_by_id[item.agent_id] for item in combo], missions[org_id], config)
            scores.append(expected_cache[key])
        score = _mean(scores)
        tie = tuple(tuple(sorted(item.agent_id for item in combo)) for combo in combo_set)
        old_tie = tuple(tuple(sorted(item.agent_id for item in combo)) for combo in best) if best is not None else None
        if score > best_score + 1e-15 or (abs(score - best_score) <= 1e-15 and (old_tie is None or tie < old_tie)):
            best_score = score
            best = combo_set
    if best is None:
        return None, None
    market = _new_market(population, config)
    for combo in best:
        for offer in combo:
            market.submit_offer(offer)
    market.settle(window_id)
    return market, best_score


def run_w8_01(population: W8Population, config: Mapping[str, Any], *, phase: str) -> tuple[dict[str, Any], dict[str, TalentMarket], tuple[TalentOffer, ...]]:
    window_id = f"w8-01:{phase}"
    offers = _generate_offers(population, config, window_id=window_id)
    unrestricted = _unrestricted_allocation(population, offers, config, window_id=window_id)
    unrestricted_summary = summarize_allocation(population, unrestricted, config, window_id=window_id, seed_salt=f"w8-01:{phase}")
    primary = int(config["source_reserve"]["primary_cap"])
    caps = list(dict.fromkeys([primary, *[int(v) for v in config["source_reserve"]["sensitivity_caps"]]]))
    markets: dict[str, TalentMarket] = {"unrestricted": unrestricted}
    results: dict[str, Any] = {}
    primary_summary: AllocationSummary | None = None
    for cap in caps:
        market = capped_rival_allocation(population, offers, config, window_id=window_id, cap=cap)
        summary = summarize_allocation(population, market, config, window_id=window_id, seed_salt=f"w8-01:{phase}")
        markets[f"cap-{cap}"] = market
        results[str(cap)] = {"mean_organization_success": summary.mean_organization_success, "organization_rates": summary.organization_rates, "mean_source_loss": summary.mean_source_loss, "field_source_loss": summary.field_source_loss, "contract_count": len(_market_agent_ids(market, window_id=window_id))}
        if cap == primary:
            primary_summary = summary
    assert primary_summary is not None
    frontier, expected = matched_source_loss_frontier(population, offers, primary_summary, config, window_id=window_id)
    frontier_rate = None
    composition_loss = None
    if frontier is not None:
        markets["matched-frontier"] = frontier
        frontier_rate = summarize_allocation(population, frontier, config, window_id=window_id, seed_salt=f"w8-01:{phase}").mean_organization_success
        composition_loss = frontier_rate - primary_summary.mean_organization_success
    band = float(config["effect_band"])
    gate = primary_summary.mean_source_loss <= band and primary_summary.mean_organization_success >= unrestricted_summary.mean_organization_success - band
    return ({"primary_cap": primary, "primary_gate": gate, "unrestricted": {"mean_organization_success": unrestricted_summary.mean_organization_success, "organization_rates": unrestricted_summary.organization_rates, "mean_source_loss": unrestricted_summary.mean_source_loss, "field_source_loss": unrestricted_summary.field_source_loss}, "caps": results, "matched_frontier": {"expected_mean_organization_success": expected, "trial_mean_organization_success": frontier_rate, "composition_efficiency_loss": composition_loss, "source_loss_limit": primary_summary.mean_source_loss + float(config["source_loss_match_tolerance"])}}, markets, offers)


def _market_rosters(market: TalentMarket, config: Mapping[str, Any], window_id: str) -> dict[str, list[str]]:
    return {str(row["organization_id"]): [state.agent_id for state in market.contracted_agents(str(row["organization_id"]), window_id)] for row in config["organizations"]}


def simulate_circulation(population: W8Population, market: TalentMarket, config: Mapping[str, Any], *, phase: str, window_id: str, mode: str, additions_by_field: Mapping[str, Sequence[PortableAgentState]] | None = None) -> dict[str, Any]:
    circ = dict(config["circulation"])
    horizon = int(circ["horizon_windows"])
    if mode == "permanent":
        schedule = None
    elif mode == "4:2":
        schedule = CirculationSchedule(int(circ["primary_external_windows"]), int(circ["primary_home_windows"]))
    elif mode == "3:3":
        schedule = CirculationSchedule(int(circ["sensitivity_external_windows"]), int(circ["sensitivity_home_windows"]))
    else:
        raise ValueError(f"unsupported circulation mode: {mode}")
    offsets = [int(value) for value in circ["roster_offsets"]]
    states = dict(population.portable_by_id)
    rosters = _market_rosters(market, config, window_id)
    additions_by_field = additions_by_field or {}
    baseline = {field_id: _source_frontier(rows, config) for field_id, rows in population.portable_by_field.items()}
    org_windows = {org: [] for org in rosters}
    org_active = {org: [] for org in rosters}
    pair_history: dict[str, list[tuple[str, str] | None]] = {org: [] for org in rosters}
    source_losses: list[float] = []
    field_losses = {field_id: [] for field_id in population.portable_by_field}
    exposures = 0
    learning_events = 0
    for window in range(horizon):
        external_ids: set[str] = set()
        for org_id, roster_ids in rosters.items():
            available: list[PortableAgentState] = []
            for index, agent_id in enumerate(sorted(roster_ids)):
                external = schedule is None or schedule.phase(window + offsets[index % len(offsets)]) == "external"
                if external:
                    available.append(states[agent_id])
                    external_ids.add(agent_id)
            exposures += len(available)
            org_row = next(row for row in config["organizations"] if row["organization_id"] == org_id)
            mission = _organization_mission(org_row, suffix=f":{mode}")
            result = _trial_rate([state.to_individual() for state in available], mission, config, seed_salt=f"w8-02:{phase}:{window}:{org_id}")
            rate = float(result["success_rate"])
            org_windows[org_id].append(rate)
            if len(available) >= 2:
                org_active[org_id].append(rate)
            lead_id, support_id = result["lead_agent_id"], result["support_agent_id"]
            pair_history[org_id].append((str(lead_id), str(support_id)) if lead_id and support_id else None)
            if lead_id and support_id:
                delta = int(circ["learning_per_executed_role"])
                states[str(lead_id)] = states[str(lead_id)].with_learning({mission.lead_skill: delta}, evidence_ref=f"world://w8/{phase}/circulation/{mode}/{window}/{org_id}/lead")
                states[str(support_id)] = states[str(support_id)].with_learning({mission.support_skill: delta}, evidence_ref=f"world://w8/{phase}/circulation/{mode}/{window}/{org_id}/support")
                learning_events += 2
        per_window: list[float] = []
        for field_id, baseline_rows in population.portable_by_field.items():
            home = [states[state.agent_id] for state in baseline_rows if state.agent_id not in external_ids]
            home.extend(additions_by_field.get(field_id, ()))
            loss = baseline[field_id] - _source_frontier(home, config)
            field_losses[field_id].append(loss)
            per_window.append(loss)
        source_losses.append(_mean(per_window))
    calendar = {org: _mean(values) for org, values in org_windows.items()}
    active = {org: _mean(values) if values else 0.0 for org, values in org_active.items()}
    continuity: dict[str, float] = {}
    for org, values in pair_history.items():
        comparisons = [(a, b) for a, b in zip(values, values[1:], strict=False) if a is not None and b is not None]
        continuity[org] = _mean([float(a == b) for a, b in comparisons]) if comparisons else 0.0
    return {"mode": mode, "mean_organization_success": _mean(list(calendar.values())), "mean_active_exposure_success": _mean(list(active.values())), "organization_calendar_rates": calendar, "organization_active_rates": active, "mean_source_loss": _mean(source_losses), "field_mean_source_loss": {field_id: _mean(values) for field_id, values in field_losses.items()}, "external_agent_window_exposures": exposures, "learning_events": learning_events, "final_states": {agent_id: state.as_dict() for agent_id, state in states.items()}, "pair_continuity": continuity, "forced_substitution_fraction": _mean([float(pair is None) for values in pair_history.values() for pair in values])}


def run_w8_02(population: W8Population, market: TalentMarket, config: Mapping[str, Any], *, phase: str, window_id: str) -> dict[str, Any]:
    results = {mode: simulate_circulation(population, market, config, phase=phase, window_id=window_id, mode=mode) for mode in ("permanent", "4:2", "3:3")}
    band = float(config["effect_band"])
    permanent = results["permanent"]
    qualifying = [mode for mode in ("4:2", "3:3") if results[mode]["mean_organization_success"] >= permanent["mean_organization_success"] - band and results[mode]["mean_source_loss"] <= band]
    return {**results, "gate": bool(qualifying), "qualifying_duty_cycles": qualifying, "calendar_tradeoff_4_2_minus_3_3": results["4:2"]["mean_organization_success"] - results["3:3"]["mean_organization_success"], "source_tradeoff_4_2_minus_3_3": results["4:2"]["mean_source_loss"] - results["3:3"]["mean_source_loss"]}


def _replacement_state(row: Mapping[str, Any]) -> PortableAgentState:
    return PortableAgentState(str(row["agent_id"]), str(row["home_field_id"]), tuple((str(skill), int(value)) for skill, value in dict(row["practice_by_skill"]).items()), tuple(str(item) for item in row.get("evidence_refs", ())))


def load_replacement_assay(path: str | Path | None) -> dict[str, Any]:
    if path is None:
        return {"status": "architectural_limitation", "reason": "native replacement assay not supplied", "basis_points": {}}
    value = _read_json(path)
    if not isinstance(value, dict):
        raise ValueError("replacement assay must be a JSON object")
    return value


def replacement_additions(replacement: Mapping[str, Any], *, basis_points: int, arm: str = "extracted") -> dict[str, list[PortableAgentState]]:
    rows = replacement.get("basis_points", {}).get(str(basis_points), {}).get("fields", [])
    additions: dict[str, list[PortableAgentState]] = {}
    for row in rows:
        state_row = row.get(f"{arm}_successor_state")
        if state_row:
            state = _replacement_state(state_row)
            additions.setdefault(state.home_field_id, []).append(state)
    return additions


def run_w8_03(population: W8Population, primary_market: TalentMarket, replacement: Mapping[str, Any], config: Mapping[str, Any], *, window_id: str) -> dict[str, Any]:
    if replacement.get("status") != "completed":
        return {"status": str(replacement.get("status", "architectural_limitation")), "classification": "architectural_limitation", "reason": replacement.get("reason"), "basis_points": replacement.get("basis_points", {})}
    recruited = _market_agent_ids(primary_market, window_id=window_id)
    rows_by_basis: dict[str, Any] = {}
    thresholds = dict(config["replacement_classification"])
    for basis_key, assay in dict(replacement.get("basis_points", {})).items():
        additions = replacement_additions(replacement, basis_points=int(basis_key), arm="extracted")
        mean_loss, field_loss = _source_loss_from_ids(population, recruited, config, additions_by_field=additions)
        rows_by_basis[str(basis_key)] = {**dict(assay), "mean_source_loss_after_replacement": mean_loss, "field_source_loss_after_replacement": field_loss, "native_replacement_fields": sorted(additions)}
    primary_key = str(int(config["dividend"]["primary_basis_points"]))
    primary = rows_by_basis.get(primary_key)
    if primary is None or int(primary.get("developed_fields", 0)) == 0:
        classification, gate = "architectural_limitation", False
    else:
        recovery = float(primary["mean_source_loss_after_replacement"]) <= float(thresholds["recovery_source_loss_max"])
        distance = float(primary["mean_extracted_vs_vacancy_cosine_distance"])
        similarity = float(primary["mean_successor_vs_source_target_cosine"])
        dominant = float(primary["dominant_match_share"])
        if recovery and distance >= float(thresholds["contingency_cosine_distance"]):
            classification = "ecological_regeneration"
        elif recovery and distance < float(thresholds["contingency_cosine_distance"]) and similarity >= float(thresholds["replication_cosine_similarity"]) and dominant >= float(thresholds["replication_dominant_match_share"]):
            classification = "capability_replication"
        elif recovery:
            classification = "replacement_recovery_without_clear_contingency"
        else:
            classification = "replacement_not_sustainable"
        gate = recovery
    return {"status": "completed", "classification": classification, "recovery_gate": gate, "primary_basis_points": int(primary_key), "primary": primary, "basis_points": rows_by_basis, "thresholds": thresholds}


def _structured_expected(lead: IndividualState, support: IndividualState, mission: JointMission, config: Mapping[str, Any], *, structure: str) -> float:
    env = _environment(config)
    primary = env.role_probability(lead, mission.lead_skill) * env.role_probability(support, mission.support_skill)
    if structure == "decomposable":
        return primary
    coal = dict(config["coalition"])
    cross_practice = 0.5 * (lead.practice(mission.support_skill) + support.practice(mission.lead_skill))
    cross_p = min(float(coal["nondecomposable_cross_max"]), float(coal["nondecomposable_cross_base"]) + float(coal["nondecomposable_cross_gain"]) * math.sqrt(cross_practice))
    return primary * cross_p


def _structured_rate(lead: IndividualState, support: IndividualState, mission: JointMission, config: Mapping[str, Any], *, structure: str, seed_salt: str) -> float:
    env = _environment(config)
    coal = dict(config["coalition"])
    cross_practice = 0.5 * (lead.practice(mission.support_skill) + support.practice(mission.lead_skill))
    cross_p = min(float(coal["nondecomposable_cross_max"]), float(coal["nondecomposable_cross_base"]) + float(coal["nondecomposable_cross_gain"]) * math.sqrt(cross_practice))
    successes = 0
    for trial in range(int(config["service_trials"])):
        seed = _seed(seed_salt, mission.mission_id, trial)
        primary = env.evaluate(lead, support, mission, JointAction(lead.agent_id, "lead"), JointAction(support.agent_id, "support"), seed=seed)
        if not primary:
            continue
        if structure == "decomposable":
            successes += 1
        else:
            u = (_seed("w8-nondecomp", mission.mission_id, trial, seed_salt) % 10_000_000) / 10_000_000
            successes += u < cross_p
    return successes / int(config["service_trials"])


def _best_structured_pair(first_roster: Sequence[IndividualState], second_roster: Sequence[IndividualState], mission: JointMission, config: Mapping[str, Any], *, structure: str, allow_swap: bool) -> tuple[IndividualState, IndividualState, bool] | None:
    best: tuple[float, str, str, bool, IndividualState, IndividualState] | None = None
    for first in first_roster:
        for second in second_roster:
            if first.agent_id == second.agent_id:
                continue
            orientations = [(first, second, False)] + ([(second, first, True)] if allow_swap else [])
            for lead, support, swapped in orientations:
                candidate = (_structured_expected(lead, support, mission, config, structure=structure), lead.agent_id, support.agent_id, swapped, lead, support)
                if best is None or candidate[:4] > best[:4]:
                    best = candidate
    return None if best is None else (best[4], best[5], best[3])


def _standalone_structured_rate(roster: Sequence[IndividualState], mission: JointMission, config: Mapping[str, Any], *, structure: str, seed_salt: str) -> float:
    pair = _best_structured_pair(roster, roster, mission, config, structure=structure, allow_swap=True)
    return 0.0 if pair is None else _structured_rate(pair[0], pair[1], mission, config, structure=structure, seed_salt=seed_salt)


def run_w8_04(market: TalentMarket, config: Mapping[str, Any], *, phase: str, window_id: str) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    effects: list[float] = []
    simple_effects: list[float] = []
    structures = {"decomposable": [], "nondecomposable": []}
    for row in config["coalition_missions"]:
        structure = str(row["structure"])
        lead_org, support_org = str(row["lead_organization_id"]), str(row["support_organization_id"])
        mission = _mission(dict(row["mission"]))
        lead_roster = [state.to_individual() for state in market.contracted_agents(lead_org, window_id)]
        support_roster = [state.to_individual() for state in market.contracted_agents(support_org, window_id)]
        salt = f"w8-04:{phase}:{row['coalition_id']}"
        standalone = max(_standalone_structured_rate(lead_roster, mission, config, structure=structure, seed_salt=salt), _standalone_structured_rate(support_roster, mission, config, structure=structure, seed_salt=salt))
        simple_pair = _best_structured_pair(lead_roster, support_roster, mission, config, structure=structure, allow_swap=False)
        simple = 0.0 if simple_pair is None else _structured_rate(simple_pair[0], simple_pair[1], mission, config, structure=structure, seed_salt=salt)
        coordinated_pair = _best_structured_pair(lead_roster, support_roster, mission, config, structure=structure, allow_swap=True)
        coordinated = 0.0 if coordinated_pair is None else _structured_rate(coordinated_pair[0], coordinated_pair[1], mission, config, structure=structure, seed_salt=salt)
        swapped = bool(coordinated_pair[2]) if coordinated_pair else False
        effect, simple_effect = coordinated - standalone, simple - standalone
        effects.append(effect); simple_effects.append(simple_effect); structures[structure].append(effect)
        rows.append({"coalition_id": str(row["coalition_id"]), "structure": structure, "best_standalone_success": standalone, "simple_coalition_success": simple, "simple_effect": simple_effect, "coordinated_coalition_success": coordinated, "coordinated_effect": effect, "coordination_bit": int(swapped)})
    required = int(config["coalition"]["required_positive_missions"])
    positive = sum(value > 0 for value in effects)
    gate = _mean(effects) > float(config["effect_band"]) and positive >= required
    return {"gate": gate, "mean_coordinated_effect": _mean(effects), "mean_simple_effect": _mean(simple_effects), "positive_missions": positive, "negative_missions": sum(value < 0 for value in effects), "required_positive_missions": required, "decomposable_mean_effect": _mean(structures["decomposable"]), "nondecomposable_mean_effect": _mean(structures["nondecomposable"]), "mission_results": rows}


def _primary_additions(replacement: Mapping[str, Any], config: Mapping[str, Any]) -> dict[str, list[PortableAgentState]]:
    return replacement_additions(replacement, basis_points=int(config["dividend"]["primary_basis_points"]), arm="extracted")


def _inequality(values: Mapping[str, float]) -> float:
    return statistics.pstdev(values.values()) if values else 0.0


def _integrated_arm(population: W8Population, market: TalentMarket, config: Mapping[str, Any], *, phase: str, window_id: str, circulation_mode: str, additions: Mapping[str, Sequence[PortableAgentState]], coordinated: bool) -> dict[str, Any]:
    circulation = simulate_circulation(population, market, config, phase=f"{phase}:w8-05", window_id=window_id, mode=circulation_mode, additions_by_field=additions)
    coalition = run_w8_04(market, config, phase=f"{phase}:w8-05", window_id=window_id)
    effect = float(coalition["mean_coordinated_effect"] if coordinated else coalition["mean_simple_effect"])
    rates = dict(circulation["organization_calendar_rates"])
    return {"mean_organization_success": circulation["mean_organization_success"], "organization_rates": rates, "outcome_sd": _inequality(rates), "mean_source_loss": circulation["mean_source_loss"], "coalition_effect": effect, "pair_continuity": circulation["pair_continuity"], "forced_substitution_fraction": circulation["forced_substitution_fraction"], "turnover_per_cycle": 0.0, "median_member_tenure_windows": int(config["circulation"]["horizon_windows"])}


def run_w8_05(population: W8Population, markets: Mapping[str, TalentMarket], replacement: Mapping[str, Any], config: Mapping[str, Any], *, phase: str, window_id: str) -> dict[str, Any]:
    cap = int(config["source_reserve"]["primary_cap"])
    capped, unrestricted = markets[f"cap-{cap}"], markets["unrestricted"]
    additions, none = _primary_additions(replacement, config), {}
    baseline = _integrated_arm(population, unrestricted, config, phase=phase, window_id=window_id, circulation_mode="permanent", additions=none, coordinated=False)
    arms = {
        "R+C+D+K": _integrated_arm(population, capped, config, phase=phase, window_id=window_id, circulation_mode="4:2", additions=additions, coordinated=True),
        "C+D+K": _integrated_arm(population, unrestricted, config, phase=phase, window_id=window_id, circulation_mode="4:2", additions=additions, coordinated=True),
        "R+D+K": _integrated_arm(population, capped, config, phase=phase, window_id=window_id, circulation_mode="permanent", additions=additions, coordinated=True),
        "R+C+K": _integrated_arm(population, capped, config, phase=phase, window_id=window_id, circulation_mode="4:2", additions=none, coordinated=True),
        "R+C+D": _integrated_arm(population, capped, config, phase=phase, window_id=window_id, circulation_mode="4:2", additions=additions, coordinated=False),
    }
    full = arms["R+C+D+K"]
    band = float(config["effect_band"])
    gate = float(full["mean_organization_success"]) >= float(baseline["mean_organization_success"]) - band and float(full["mean_source_loss"]) <= band and float(full["coalition_effect"]) > band and float(full["outcome_sd"]) <= float(baseline["outcome_sd"]) + band
    return {"gate": gate, "unrestricted_baseline": baseline, "arms": arms, "leave_one_out_effects": {name: {"organization_delta": float(arm["mean_organization_success"]) - float(full["mean_organization_success"]), "source_loss_delta": float(arm["mean_source_loss"]) - float(full["mean_source_loss"]), "coalition_delta": float(arm["coalition_effect"]) - float(full["coalition_effect"])} for name, arm in arms.items() if name != "R+C+D+K"}}


def _hungarian_max(scores: Sequence[Sequence[float]]) -> list[tuple[int, int]]:
    n = len(scores)
    if not n:
        return []
    m = len(scores[0])
    if n > m or any(len(row) != m for row in scores):
        raise ValueError("assignment matrix must be rectangular with rows <= columns")
    u, v, p, way = [0.0] * (n + 1), [0.0] * (m + 1), [0] * (m + 1), [0] * (m + 1)
    for i in range(1, n + 1):
        p[0] = i; minv = [math.inf] * (m + 1); used = [False] * (m + 1); j0 = 0
        while True:
            used[j0] = True; i0 = p[j0]; delta = math.inf; j1 = 0
            for j in range(1, m + 1):
                if used[j]: continue
                cur = -float(scores[i0 - 1][j - 1]) - u[i0] - v[j]
                if cur < minv[j]: minv[j], way[j] = cur, j0
                if minv[j] < delta: delta, j1 = minv[j], j
            for j in range(m + 1):
                if used[j]: u[p[j]] += delta; v[j] -= delta
                else: minv[j] -= delta
            j0 = j1
            if p[j0] == 0: break
        while True:
            j1 = way[j0]; p[j0] = p[j1]; j0 = j1
            if j0 == 0: break
    return sorted((p[j] - 1, j - 1) for j in range(1, m + 1) if p[j])


def capability_stock(states: Sequence[PortableAgentState], config: Mapping[str, Any], *, cumulative_compute: float) -> dict[str, float | None]:
    missions = list(config["benchmark_missions"])
    if len(states) < len(missions):
        return {"stock": 0.0, "compute_normalized_stock": 0.0 if cumulative_compute else None}
    matrix = [[_source_probability(state, str(mission["skill"]), config) for state in states] for mission in missions]
    stock = sum(matrix[i][j] for i, j in _hungarian_max(matrix))
    return {"stock": stock, "compute_normalized_stock": stock / cumulative_compute if cumulative_compute > 0 else None}


def _cycle_organizations(config: Mapping[str, Any], cycle: int) -> list[dict[str, Any]]:
    rows = [dict(row) for row in config["organizations"]]
    stress = dict(config["long_horizon"]["stress_schedule"])
    shifts = sum(1 for value in stress["demand_shift_cycles"] if int(value) <= cycle)
    rotation = int(stress["demand_shift_skill_rotation"])
    if not shifts: return rows
    skills = ["urban_heat", "water_systems", "energy_storage", "supply_networks", "public_health", "mobility"]
    for row in rows:
        row["lead_skill"] = skills[(skills.index(str(row["lead_skill"])) + shifts * rotation) % len(skills)]
        row["support_skill"] = skills[(skills.index(str(row["support_skill"])) + shifts * rotation) % len(skills)]
    return rows


def _cycle_config(config: Mapping[str, Any], organizations: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    value = json.loads(json.dumps(config)); value["organizations"] = [dict(row) for row in organizations]; return value


def _dynamic_allocation(population: W8Population, offers: Sequence[TalentOffer], *, cap: int, budgets: Mapping[str, int], excluded_fields: set[str], eligible_agent_ids: set[str]) -> tuple[dict[str, list[str]], dict[str, int], list[dict[str, Any]]]:
    by_agent: dict[str, list[TalentOffer]] = {}
    for offer in offers:
        state = population.portable_by_id[offer.agent_id]
        if state.home_field_id not in excluded_fields and offer.agent_id in eligible_agent_ids:
            by_agent.setdefault(offer.agent_id, []).append(offer)
    remaining = {org: int(value) for org, value in budgets.items()}; counts: dict[str, int] = {}; rosters = {org: [] for org in budgets}; contracts: list[dict[str, Any]] = []
    for agent_id in sorted(by_agent):
        field_id = population.portable_by_id[agent_id].home_field_id
        if counts.get(field_id, 0) >= cap: continue
        winner = next((offer for offer in sorted(by_agent[agent_id], key=lambda item: (-item.bid, item.organization_id, item.offer_id)) if remaining.get(offer.organization_id, 0) >= offer.bid), None)
        if winner is None: continue
        remaining[winner.organization_id] -= winner.bid; counts[field_id] = counts.get(field_id, 0) + 1; rosters[winner.organization_id].append(agent_id); contracts.append({"agent_id": agent_id, "organization_id": winner.organization_id, "price": winner.bid, "source_field_id": field_id})
    return rosters, {org: int(budgets[org]) - remaining[org] for org in budgets}, contracts


def _field_losses(population: W8Population, state_map: Mapping[str, PortableAgentState], config: Mapping[str, Any], *, external_ids: set[str], additions: Mapping[str, Sequence[PortableAgentState]]) -> tuple[float, dict[str, float]]:
    losses: dict[str, float] = {}
    for field_id, baseline in population.portable_by_field.items():
        home = [state_map[state.agent_id] for state in baseline if state.agent_id not in external_ids]; home.extend(additions.get(field_id, ())); losses[field_id] = _source_frontier(baseline, config) - _source_frontier(home, config)
    return _mean(list(losses.values())), losses


def run_long_horizon_arm(population: W8Population, config: Mapping[str, Any], replacement: Mapping[str, Any], *, phase: str, budget_mode: str) -> dict[str, Any]:
    horizon = int(config["long_horizon"]["cycles"]); base_budget = int(config["long_horizon"]["neutral_base_budget"]); reward = int(config["long_horizon"]["compounding_reward_per_successful_trial"]); max_budget = int(config["long_horizon"]["compounding_max_budget"])
    policy = BudgetUpdatePolicy(mode=budget_mode, base_budget=base_budget, reward_per_success=0 if budget_mode == "neutral" else reward, max_budget=max_budget)
    budgets = {str(row["organization_id"]): base_budget for row in config["organizations"]}; states = dict(population.portable_by_id)
    compute = float(sum(sum(count for _, count in state.practice_by_skill) for state in states.values())); initial_compute = compute
    available_replacements = {field_id: list(rows) for field_id, rows in _primary_additions(replacement, config).items()}; activated: dict[str, list[PortableAgentState]] = {}; dividends: dict[str, int] = {}
    previous = {org: set() for org in budgets}; contract_counts: dict[str, int] = {}; budget_hhi: list[float] = []; talent_hhi: list[float] = []; source_losses: list[float] = []; max_losses: list[float] = []; org_rates: list[float] = []; churn: list[float] = []; stock_rows: list[dict[str, Any]] = []; coalition_effects: list[float] = []; exposures = 0
    schedule = CirculationSchedule(int(config["integrated_charter"]["external_windows"]), int(config["integrated_charter"]["home_windows"])); stress = dict(config["long_horizon"]["stress_schedule"]); field_ids = sorted(population.portable_by_field)
    initial_stock = capability_stock(list(states.values()), config, cumulative_compute=compute)
    for cycle in range(horizon):
        org_rows = _cycle_organizations(config, cycle); cycle_cfg = _cycle_config(config, org_rows); window = f"w8-06:{phase}:{budget_mode}:{cycle}"; offers = _generate_offers(population, cycle_cfg, window_id=window)
        excluded: set[str] = set()
        if cycle in {int(value) for value in stress["source_shortage_cycles"]}:
            stride = int(stress["source_shortage_field_stride"]); excluded.add(field_ids[((cycle // 8) * stride) % len(field_ids)])
        eligible: set[str] = set()
        offsets = [int(v) for v in config["circulation"]["roster_offsets"]]
        for index, agent_id in enumerate(sorted(population.portable_by_id)):
            if schedule.phase(cycle + offsets[index % len(offsets)]) == "external": eligible.add(agent_id)
        rosters, spend, contracts = _dynamic_allocation(population, offers, cap=int(config["integrated_charter"]["reserve_cap"]), budgets=budgets, excluded_fields=excluded, eligible_agent_ids=eligible)
        external_ids = {row["agent_id"] for row in contracts}; exposures += len(external_ids)
        for row in contracts:
            contract_counts[row["agent_id"]] = contract_counts.get(row["agent_id"], 0) + 1; field_id = str(row["source_field_id"]); dividends[field_id] = dividends.get(field_id, 0) + SourceDividendPolicy(int(config["integrated_charter"]["dividend_basis_points"])).dividend(int(row["price"]))
        success_counts: dict[str, int] = {}; rates: dict[str, float] = {}
        for row in org_rows:
            org = str(row["organization_id"]); mission = _organization_mission(row, suffix=f":long:{cycle}"); result = _trial_rate([states[a].to_individual() for a in rosters.get(org, [])], mission, config, seed_salt=f"w8-06:{phase}:{budget_mode}:{cycle}:{org}"); rates[org] = float(result["success_rate"]); success_counts[org] = int(result["successes"])
            if result["lead_agent_id"] and result["support_agent_id"]:
                lead, support = str(result["lead_agent_id"]), str(result["support_agent_id"]); states[lead] = states[lead].with_learning({mission.lead_skill: 1}, evidence_ref=f"world://w8/{phase}/long/{budget_mode}/{cycle}/{org}/lead"); states[support] = states[support].with_learning({mission.support_skill: 1}, evidence_ref=f"world://w8/{phase}/long/{budget_mode}/{cycle}/{org}/support"); compute += 2.0
        org_rates.append(_mean(list(rates.values())))
        cost = int(config["dividend"]["development_credit_per_cycle"])
        for field_id in field_ids:
            if field_id not in activated and available_replacements.get(field_id) and dividends.get(field_id, 0) >= cost:
                state = available_replacements[field_id].pop(0); activated[field_id] = [state]; compute += sum(count for _, count in state.practice_by_skill)
        mean_loss, field_loss = _field_losses(population, states, config, external_ids=external_ids, additions=activated); source_losses.append(mean_loss); max_losses.append(max(field_loss.values()) if field_loss else 0.0)
        all_living = list(states.values()) + [state for rows in activated.values() for state in rows]; source_accessible = [state for state in states.values() if state.agent_id not in external_ids] + [state for rows in activated.values() for state in rows]; org_accessible = [states[a] for a in external_ids]
        stock_rows.append({"cycle": cycle, "world": capability_stock(all_living, config, cumulative_compute=compute), "source_accessible": capability_stock(source_accessible, config, cumulative_compute=compute), "organization_accessible": capability_stock(org_accessible, config, cumulative_compute=compute), "cumulative_compute": compute})
        coal = config["coalition_missions"][cycle % len(config["coalition_missions"])]; lead_org, support_org = str(coal["lead_organization_id"]), str(coal["support_organization_id"]); mission = _mission(dict(coal["mission"])); structure = str(coal["structure"]); lead_roster = [states[a].to_individual() for a in rosters.get(lead_org, [])]; support_roster = [states[a].to_individual() for a in rosters.get(support_org, [])]; pair = _best_structured_pair(lead_roster, support_roster, mission, config, structure=structure, allow_swap=True)
        if pair is None: coalition_effects.append(0.0)
        else:
            lead, support, _ = pair
            if cycle in {int(value) for value in stress["withholding_cycles"]} and len(support_roster) >= 2:
                ranked = sorted(support_roster, key=lambda state: (state.practice(mission.support_skill), state.agent_id), reverse=True); support = next((state for state in ranked if state.agent_id != support.agent_id), support)
            coalition_rate = _structured_rate(lead, support, mission, config, structure=structure, seed_salt=f"w8-06:{phase}:{budget_mode}:coalition:{cycle}"); standalone = max(_standalone_structured_rate(lead_roster, mission, config, structure=structure, seed_salt=f"w8-06:{phase}:{budget_mode}:coalition:{cycle}"), _standalone_structured_rate(support_roster, mission, config, structure=structure, seed_salt=f"w8-06:{phase}:{budget_mode}:coalition:{cycle}")); coalition_effects.append(coalition_rate - standalone)
        current = {org: set(ids) for org, ids in rosters.items()}; changed = []
        for org, values in current.items():
            union = values | previous[org]; changed.append(0.0 if not union else 1.0 - len(values & previous[org]) / len(union)); previous[org] = values
        churn.append(_mean(changed)); total_budget = sum(budgets.values()); budget_hhi.append(sum((v / total_budget) ** 2 for v in budgets.values()) if total_budget else 0.0); total_contracts = sum(contract_counts.values()); talent_hhi.append(sum((count / total_contracts) ** 2 for count in contract_counts.values()) if total_contracts else 0.0)
        budgets = {org: policy.next_budget(current_budget=budgets[org], spend=spend.get(org, 0), successes=success_counts.get(org, 0)) for org in budgets}
    initial_norm, final_norm = initial_stock["compute_normalized_stock"], stock_rows[-1]["world"]["compute_normalized_stock"] if stock_rows else initial_stock["compute_normalized_stock"]
    growth = float(final_norm) / float(initial_norm) - 1.0 if initial_norm not in (None, 0) and final_norm is not None else 0.0; mean_source = _mean(source_losses); band = float(config["effect_band"]); stock_band = float(config["stock_growth_band"])
    if growth > stock_band and mean_source <= band: label = "generative_circulation"
    elif abs(growth) <= stock_band and mean_source <= band: label = "conservative_circulation"
    elif growth < -stock_band or mean_source > band: label = "extractive"
    else: label = "mixed"
    return {"budget_mode": budget_mode, "long_run_label": label, "compute_normalized_world_stock_growth": growth, "initial_world_stock": initial_stock, "final_world_stock": stock_rows[-1]["world"] if stock_rows else initial_stock, "mean_source_loss": mean_source, "max_single_field_loss": max(max_losses) if max_losses else 0.0, "mean_organization_success": _mean(org_rates), "mean_coalition_effect": _mean(coalition_effects), "mean_roster_churn": _mean(churn), "mean_budget_hhi": _mean(budget_hhi), "final_budget_hhi": budget_hhi[-1] if budget_hhi else 0.0, "mean_talent_hhi": _mean(talent_hhi), "final_budgets": budgets, "circulation_exposures": exposures, "activated_native_replacement_fields": sorted(activated), "initial_development_compute": initial_compute, "final_development_compute": compute, "capability_stock_series": stock_rows}


def run_w8_06(population: W8Population, config: Mapping[str, Any], replacement: Mapping[str, Any], *, phase: str) -> dict[str, Any]:
    neutral = run_long_horizon_arm(population, config, replacement, phase=phase, budget_mode="neutral"); compounding = run_long_horizon_arm(population, config, replacement, phase=phase, budget_mode="compounding")
    return {"neutral": neutral, "compounding": compounding, "compounding_minus_neutral_budget_hhi": float(compounding["mean_budget_hhi"]) - float(neutral["mean_budget_hhi"]), "compounding_minus_neutral_talent_hhi": float(compounding["mean_talent_hhi"]) - float(neutral["mean_talent_hhi"])}


def run_phase(*, phase: str, source_dir: str | Path, config_path: str | Path, replacement_path: str | Path | None, output_path: str | Path) -> dict[str, Any]:
    config = _read_json(config_path); expected = config["discovery_seeds"] if phase == "discovery" else config["replication_seeds"]; population = load_population(source_dir, expected_seeds=expected); replacement = load_replacement_assay(replacement_path)
    w801, markets, offers = run_w8_01(population, config, phase=phase); window_id = f"w8-01:{phase}"; w802 = run_w8_02(population, markets["unrestricted"], config, phase=phase, window_id=window_id); primary = markets[f"cap-{int(config['source_reserve']['primary_cap'])}"]; w803 = run_w8_03(population, primary, replacement, config, window_id=window_id); w804 = run_w8_04(markets["unrestricted"], config, phase=phase, window_id=window_id); w805 = run_w8_05(population, markets, replacement, config, phase=phase, window_id=window_id); w806 = run_w8_06(population, config, replacement, phase=phase)
    result = {"phase": phase, "field_sha": str(config["field_sha"]), "field_count": len(population.portable_by_field), "agent_count": len(population.portable_by_id), "offer_scientific_sha256": _sha256([{"agent_id": offer.agent_id, "bid": offer.bid, "organization_id": offer.organization_id} for offer in offers]), "w8_01_source_reserve": w801, "w8_02_circulation": w802, "w8_03_replacement": w803, "w8_04_coalitions": w804, "w8_05_integrated_charter": w805, "w8_06_long_horizon": w806}; _write_json(output_path, result); return result


def _replacement_classification(value: Mapping[str, Any]) -> str:
    return str(value.get("classification", value.get("status", "unknown")))


def synthesize(*, discovery_path: str | Path, replication_path: str | Path, output_path: str | Path) -> dict[str, Any]:
    discovery, replication = _read_json(discovery_path), _read_json(replication_path)
    gates = {"w8_01_source_reserve": bool(discovery["w8_01_source_reserve"]["primary_gate"]) and bool(replication["w8_01_source_reserve"]["primary_gate"]), "w8_02_circulation": bool(discovery["w8_02_circulation"]["gate"]) and bool(replication["w8_02_circulation"]["gate"]), "w8_03_replacement_classification_match": _replacement_classification(discovery["w8_03_replacement"]) == _replacement_classification(replication["w8_03_replacement"]), "w8_04_coalition_surplus": bool(discovery["w8_04_coalitions"]["gate"]) and bool(replication["w8_04_coalitions"]["gate"]), "w8_05_integrated_charter": bool(discovery["w8_05_integrated_charter"]["gate"]) and bool(replication["w8_05_integrated_charter"]["gate"])}
    dlong, rlong = discovery["w8_06_long_horizon"]["neutral"], replication["w8_06_long_horizon"]["neutral"]; gates["w8_06_long_horizon_classification_match"] = str(dlong["long_run_label"]) == str(rlong["long_run_label"])
    sustainable = all(gates[key] for key in ("w8_01_source_reserve", "w8_02_circulation", "w8_04_coalition_surplus", "w8_05_integrated_charter", "w8_06_long_horizon_classification_match")) and str(rlong["long_run_label"]) in {"conservative_circulation", "generative_circulation"}
    generative = sustainable and str(dlong["long_run_label"]) == "generative_circulation" and str(rlong["long_run_label"]) == "generative_circulation"
    status = "replicated_generative_circulation" if generative else "replicated_sustainable_circulation" if sustainable else "replicated_regulatory_null_or_negative" if all(gates.values()) else "w8_discovery_not_replicated"
    result = {"status": status, "gates": gates, "replicated_sustainable_circulation": sustainable, "replicated_generative_circulation": generative, "discovery_replacement_classification": _replacement_classification(discovery["w8_03_replacement"]), "replication_replacement_classification": _replacement_classification(replication["w8_03_replacement"]), "discovery_long_run_label": str(dlong["long_run_label"]), "replication_long_run_label": str(rlong["long_run_label"]), "discovery_stock_growth": float(dlong["compute_normalized_world_stock_growth"]), "replication_stock_growth": float(rlong["compute_normalized_world_stock_growth"])}; _write_json(output_path, result); return result


def prepare_plan(*, phase: str, source_dir: str | Path, config_path: str | Path, output_path: str | Path) -> dict[str, Any]:
    from uuid import UUID, uuid5
    config = _read_json(config_path); expected = config["discovery_seeds"] if phase == "discovery" else config["replication_seeds"]; population = load_population(source_dir, expected_seeds=expected); w801, markets, offers = run_w8_01(population, config, phase=phase); primary = int(config["source_reserve"]["primary_cap"]); market = markets[f"cap-{primary}"]; contracted = _contract_rows(market); by_field: dict[str, list[dict[str, Any]]] = {}
    for row in contracted:
        agent_id = str(row["agent_id"]); by_field.setdefault(population.portable_by_id[agent_id].home_field_id, []).append(dict(row))
    source_rows = {str(row["field_id"]): row for row in population.source_fields}; targets: list[dict[str, Any]] = []
    for field_id in sorted(population.portable_by_field):
        field_contracts = sorted(by_field.get(field_id, ()), key=lambda row: str(row["agent_id"])); recruited = [str(row["agent_id"]) for row in field_contracts]
        if not recruited: continue
        target_id = max(recruited, key=lambda agent_id: (sum(count for _, count in population.portable_by_id[agent_id].practice_by_skill), agent_id)); run_id = UUID(str(source_rows[field_id]["run_id"])); slot = next((candidate for candidate in range(12) if str(uuid5(run_id, f"agent:{candidate}:generation:0")) == target_id), None)
        if slot is None: raise ValueError(f"cannot resolve Field slot for target agent {target_id}")
        blocked = []
        for other_id in recruited:
            if other_id == target_id: continue
            other_slot = next((candidate for candidate in range(12) if str(uuid5(run_id, f"agent:{candidate}:generation:0")) == other_id), None)
            if other_slot is not None: blocked.append(other_slot)
        targets.append({"field_id": field_id, "seed": _field_seed(field_id), "source_run_id": str(run_id), "target_agent_id": target_id, "target_slot": slot, "additional_unavailable_slots": sorted(blocked), "contracted_agent_ids": recruited, "contract_prices": [int(row["price"]) for row in field_contracts], "source_target_practice_by_skill": dict(population.portable_by_id[target_id].practice_by_skill), "source_target_evidence_refs": list(population.portable_by_id[target_id].evidence_refs)})
    result = {"phase": phase, "field_sha": str(config["field_sha"]), "primary_cap": primary, "target_count": len(targets), "targets": targets, "w8_01_primary_gate_pre_replacement": bool(w801["primary_gate"]), "offer_scientific_sha256": _sha256([{"agent_id": offer.agent_id, "bid": offer.bid, "organization_id": offer.organization_id} for offer in offers])}; _write_json(output_path, result); return result


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__); sub = parser.add_subparsers(dest="command", required=True)
    plan = sub.add_parser("prepare"); plan.add_argument("--phase", choices=["discovery", "replication"], required=True); plan.add_argument("--source-dir", required=True); plan.add_argument("--config", required=True); plan.add_argument("--output", required=True)
    phase = sub.add_parser("phase"); phase.add_argument("--phase", choices=["discovery", "replication"], required=True); phase.add_argument("--source-dir", required=True); phase.add_argument("--config", required=True); phase.add_argument("--replacement"); phase.add_argument("--output", required=True)
    syn = sub.add_parser("synthesize"); syn.add_argument("--discovery", required=True); syn.add_argument("--replication", required=True); syn.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    if args.command == "prepare": result = prepare_plan(phase=args.phase, source_dir=args.source_dir, config_path=args.config, output_path=args.output)
    elif args.command == "phase": result = run_phase(phase=args.phase, source_dir=args.source_dir, config_path=args.config, replacement_path=args.replacement, output_path=args.output)
    else: result = synthesize(discovery_path=args.discovery, replication_path=args.replication, output_path=args.output)
    print(json.dumps(result, indent=2, sort_keys=True)); return 0


if __name__ == "__main__":
    raise SystemExit(main())
