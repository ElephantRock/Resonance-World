"""Preregistered W7 competing-organizations and coopetition evaluator."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .w4a_joint_learning import IndividualState, JointAction, JointEnvironment, JointMission
from .w5a_organization import OrganizationState
from .w6_mobility import PortableAgentState
from .w7_competition import CooperationAgreement, TalentMarket, TalentOffer


def _read_json(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"{path} contains a non-object JSONL row")
        rows.append(value)
    return rows


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _seed(*parts: object) -> int:
    payload = "|".join(str(part) for part in parts).encode("utf-8")
    return int.from_bytes(hashlib.sha256(payload).digest()[:4], "big")


def _mean(values: list[float]) -> float:
    return statistics.mean(values) if values else 0.0


def _field_id(seed: int) -> str:
    return f"w4-source-seed-{seed}"


def _classify(effect: float, band: float) -> str:
    if effect > band:
        return "positive"
    if effect < -band:
        return "negative"
    return "null"


@dataclass(frozen=True, slots=True)
class Population:
    candidates: tuple[dict[str, Any], ...]
    portable_by_id: dict[str, PortableAgentState]
    states_by_field: dict[str, tuple[IndividualState, ...]]


def _group_rows(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(str(row["field_id"]), []).append(row)
    for values in grouped.values():
        values.sort(key=lambda item: str(item["agent_id"]))
    return grouped


def _load_population(
    candidates_path: str | Path,
    capsules_path: str | Path,
    config: dict[str, Any],
    phase: str,
) -> Population:
    candidates = _read_jsonl(candidates_path)
    capsules = _read_jsonl(capsules_path)
    public_text = json.dumps(candidates, sort_keys=True)
    if "practice_by_skill" in public_text:
        raise ValueError("private practice leaked into W7 public candidate evidence")

    expected_fields = {_field_id(int(seed)) for seed in config["fields"][phase]}
    public = _group_rows(candidates)
    private = _group_rows(capsules)
    if set(public) != expected_fields or set(private) != expected_fields:
        raise ValueError("W7 source Fields do not match the frozen phase manifest")

    portable_by_id: dict[str, PortableAgentState] = {}
    states_by_field: dict[str, tuple[IndividualState, ...]] = {}
    for field_id in sorted(expected_fields):
        public_rows = public[field_id]
        private_rows = private[field_id]
        if len(public_rows) != 12 or len(private_rows) != 12:
            raise ValueError("W7 requires exactly 12 agents per source Field")
        public_ids = {str(row["agent_id"]) for row in public_rows}
        private_ids = {str(row["agent_id"]) for row in private_rows}
        if public_ids != private_ids:
            raise ValueError("W7 public/private source identities do not match")

        states: list[IndividualState] = []
        for row in private_rows:
            agent_id = str(row["agent_id"])
            practice = {
                str(skill): int(value)
                for skill, value in dict(row["practice_by_skill"]).items()
            }
            state = IndividualState(agent_id, practice)
            states.append(state)
            portable_by_id[agent_id] = PortableAgentState.from_individual(
                state,
                home_field_id=field_id,
                evidence_refs=(f"field://{field_id}/agent/{agent_id}",),
            )
        states_by_field[field_id] = tuple(states)

    if len(candidates) != 36 or len(portable_by_id) != 36:
        raise ValueError("W7 requires exactly 36 agents per phase")
    candidates.sort(key=lambda row: (str(row["field_id"]), str(row["agent_id"])))
    return Population(tuple(candidates), portable_by_id, states_by_field)


def _skill_weights(requirements: dict[str, Any]) -> dict[str, float]:
    weights = {str(skill): float(value) for skill, value in requirements.items()}
    total = sum(weights.values())
    if total <= 0:
        raise ValueError("bidding requirements must have positive total weight")
    return {skill: value / total for skill, value in weights.items()}


def _label_fit(label: object, skill_weights: dict[str, float]) -> float:
    if label is None:
        return 0.0
    weight = skill_weights.get(str(label), 0.0)
    return min(1.0, weight * max(1, len(skill_weights)))


def _public_score(
    candidate: dict[str, Any],
    requirements: dict[str, Any],
    config: dict[str, Any],
) -> float:
    if "practice_by_skill" in candidate:
        raise ValueError("private practice leaked into W7 bidding")
    features = dict(candidate["public_features"])
    profile = dict(candidate.get("public_mission_profile", {}))
    weights = dict(config["public_selector"])
    mission_weights = _skill_weights(requirements)
    experience = min(
        1.0,
        float(features["completed_tasks"]) / float(weights["experience_scale"]),
    )
    values = {
        "home_success_rate": float(features["home_success_rate"]),
        "bid_win_rate": float(features["bid_win_rate"]),
        "mean_bid_confidence": float(features["mean_bid_confidence"]),
        "experience": experience,
        "dominant_host_fit": _label_fit(
            profile.get("dominant_success_skill"), mission_weights
        ),
        "secondary_host_fit": _label_fit(
            profile.get("secondary_success_skill"), mission_weights
        ),
    }
    score = sum(float(weights[key]) * values[key] for key in values)
    return min(1.0, max(0.0, score))


def _evidence_ref(candidate: dict[str, Any]) -> str:
    field_id = str(candidate["field_id"])
    agent_id = str(candidate["agent_id"])
    token = candidate.get("source_evidence_sha256") or candidate.get("checkpoint_id")
    suffix = str(token) if token else "public-evidence"
    return f"public://{field_id}/{agent_id}/{suffix}"


def _generate_offers(
    population: Population,
    config: dict[str, Any],
    *,
    window_id: str,
    requirement_key: str,
) -> dict[str, tuple[TalentOffer, ...]]:
    offers: dict[str, tuple[TalentOffer, ...]] = {}
    offer_count = int(config["offer_count"])
    bid_base = int(config["bid_base"])
    bid_span = int(config["bid_span"])
    for organization in config["organizations"]:
        organization_id = str(organization["organization_id"])
        requirements = dict(organization[requirement_key])
        ranked = sorted(
            (
                (
                    _public_score(candidate, requirements, config),
                    str(candidate["field_id"]),
                    str(candidate["agent_id"]),
                    candidate,
                )
                for candidate in population.candidates
            ),
            key=lambda item: (-item[0], item[1], item[2]),
        )
        selected: list[TalentOffer] = []
        for rank, (score, _field, agent_id, candidate) in enumerate(ranked[:offer_count], 1):
            bid = bid_base + int(round(bid_span * score))
            selected.append(
                TalentOffer(
                    offer_id=f"{window_id}:{organization_id}:{rank:02d}:{agent_id}",
                    organization_id=organization_id,
                    agent_id=agent_id,
                    window_id=window_id,
                    bid=bid,
                    evidence_refs=(_evidence_ref(candidate),),
                )
            )
        offers[organization_id] = tuple(selected)
    return offers


def _offer_digest(offers: dict[str, tuple[TalentOffer, ...]]) -> str:
    rows = [
        offer.as_dict()
        for organization_id in sorted(offers)
        for offer in offers[organization_id]
    ]
    return _sha256(rows)


def _new_market(
    population: Population,
    organization_ids: list[str],
    budget: int,
) -> TalentMarket:
    market = TalentMarket()
    for agent_id in sorted(population.portable_by_id):
        market.register_agent(population.portable_by_id[agent_id])
    for organization_id in sorted(organization_ids):
        market.register_organization(OrganizationState(organization_id, {}), budget=budget)
    return market


def _rival_allocation(
    population: Population,
    offers: dict[str, tuple[TalentOffer, ...]],
    config: dict[str, Any],
    window_id: str,
) -> TalentMarket:
    organization_ids = [str(row["organization_id"]) for row in config["organizations"]]
    market = _new_market(population, organization_ids, int(config["organization_budget"]))
    for organization_id in sorted(offers):
        for offer in offers[organization_id]:
            market.submit_offer(offer)
    market.settle(window_id)
    return market


def _nonrival_allocations(
    population: Population,
    offers: dict[str, tuple[TalentOffer, ...]],
    config: dict[str, Any],
    window_id: str,
) -> dict[str, TalentMarket]:
    result: dict[str, TalentMarket] = {}
    for organization_id in sorted(offers):
        market = _new_market(
            population,
            [organization_id],
            int(config["organization_budget"]),
        )
        for offer in offers[organization_id]:
            market.submit_offer(offer)
        market.settle(window_id)
        result[organization_id] = market
    return result


def _roster(market: TalentMarket, organization_id: str, window_id: str) -> list[IndividualState]:
    return [
        portable.to_individual()
        for portable in market.contracted_agents(organization_id, window_id)
    ]


def _mission(row: dict[str, Any]) -> JointMission:
    return JointMission(
        str(row["mission_id"]),
        str(row["context"]),
        str(row["lead_skill"]),
        str(row["support_skill"]),
    )


def _environment(config: dict[str, Any]) -> JointEnvironment:
    law = dict(config["organization_joint_law"])
    return JointEnvironment(
        base_success_probability=float(law["base_success_probability"]),
        practice_gain=float(law["practice_gain"]),
        maximum_role_success=float(law["maximum_role_success"]),
    )


def _best_pair(
    states: list[IndividualState], mission: JointMission
) -> tuple[IndividualState, IndividualState] | None:
    if len(states) < 2:
        return None
    lead = max(states, key=lambda state: (state.practice(mission.lead_skill), state.agent_id))
    support = max(
        (state for state in states if state.agent_id != lead.agent_id),
        key=lambda state: (state.practice(mission.support_skill), state.agent_id),
    )
    return lead, support


def _pair_rate(
    first: IndividualState,
    second: IndividualState,
    mission: JointMission,
    config: dict[str, Any],
    *,
    seed_salt: str,
) -> float:
    environment = _environment(config)
    trials = int(config["service_trials"])
    successes = 0
    for trial in range(trials):
        successes += int(
            environment.evaluate(
                first,
                second,
                mission,
                JointAction(first.agent_id, "lead"),
                JointAction(second.agent_id, "support"),
                seed=_seed(seed_salt, trial),
            )
        )
    return successes / trials


def _organization_rate(
    states: list[IndividualState],
    mission: JointMission,
    config: dict[str, Any],
    *,
    seed_salt: str,
) -> dict[str, Any]:
    pair = _best_pair(states, mission)
    if pair is None:
        return {
            "lead_agent_id": None,
            "support_agent_id": None,
            "success_rate": 0.0,
            "trials": int(config["service_trials"]),
        }
    lead, support = pair
    return {
        "lead_agent_id": lead.agent_id,
        "support_agent_id": support.agent_id,
        "success_rate": _pair_rate(
            lead,
            support,
            mission,
            config,
            seed_salt=seed_salt,
        ),
        "trials": int(config["service_trials"]),
    }


def _expected_probability(
    state: IndividualState,
    requirements: dict[str, Any],
    law: dict[str, Any],
) -> float:
    weights = _skill_weights(requirements)
    root_practice = sum(
        weight * math.sqrt(state.practice(skill)) for skill, weight in weights.items()
    )
    return min(
        float(law["maximum_success_probability"]),
        float(law["base_success_probability"])
        + float(law["practice_gain"]) * root_practice,
    )


def _source_frontier(
    states: list[IndividualState], config: dict[str, Any]
) -> float:
    if not states:
        return 0.0
    missions = [dict(row) for row in config["home_service"]]
    law = dict(config["source_service_law"])
    trials = int(config["service_trials"])
    total = 0.0
    for trial in range(trials):
        mission = missions[trial % len(missions)]
        requirements = dict(mission["requirements"])
        total += max(_expected_probability(state, requirements, law) for state in states)
    return total / trials


def _contract_rows(market: TalentMarket) -> list[dict[str, Any]]:
    snapshot = market.snapshot()
    return [dict(row) for row in snapshot["contracts"]]  # type: ignore[arg-type]


def _contract_ids(
    market: TalentMarket, organization_id: str, window_id: str
) -> set[str]:
    return {
        str(row["agent_id"])
        for row in _contract_rows(market)
        if row["organization_id"] == organization_id and row["window_id"] == window_id
    }


def _contested_metrics(offers: dict[str, tuple[TalentOffer, ...]]) -> dict[str, Any]:
    demand: dict[str, set[str]] = {}
    for organization_id, values in offers.items():
        for offer in values:
            demand.setdefault(offer.agent_id, set()).add(organization_id)
    contested = {agent_id for agent_id, organizations in demand.items() if len(organizations) >= 2}
    denominator = len(demand)
    return {
        "contested_agent_count": len(contested),
        "contested_agent_share": len(contested) / denominator if denominator else 0.0,
        "offered_agent_count": denominator,
    }


def _hhi(values: list[str]) -> float:
    if not values:
        return 0.0
    counts = Counter(values)
    total = len(values)
    return sum((count / total) ** 2 for count in counts.values())


def _market_metrics(
    rival: TalentMarket,
    nonrival: dict[str, TalentMarket],
    offers: dict[str, tuple[TalentOffer, ...]],
    population: Population,
    window_id: str,
) -> dict[str, Any]:
    contracts = _contract_rows(rival)
    pressure = _contested_metrics(offers)
    organization_ids = sorted(offers)
    preferred_loss: dict[str, int] = {}
    spend: dict[str, int] = {}
    roster_sizes: dict[str, int] = {}
    for organization_id in organization_ids:
        rival_ids = _contract_ids(rival, organization_id, window_id)
        nonrival_ids = _contract_ids(nonrival[organization_id], organization_id, window_id)
        preferred_loss[organization_id] = len(nonrival_ids - rival_ids)
        spend[organization_id] = sum(
            int(row["price"])
            for row in contracts
            if row["organization_id"] == organization_id
        )
        roster_sizes[organization_id] = len(rival_ids)

    organization_values = [str(row["organization_id"]) for row in contracts]
    source_values = [
        population.portable_by_id[str(row["agent_id"])].home_field_id for row in contracts
    ]
    prices = [int(row["price"]) for row in contracts]
    pressure.update(
        {
            "competition_active": pressure["contested_agent_count"] > 0
            and sum(value > 0 for value in preferred_loss.values()) >= 2,
            "contract_count": len(contracts),
            "contract_share_hhi": _hhi(organization_values),
            "mean_winning_bid": _mean([float(value) for value in prices]),
            "preferred_candidate_loss": preferred_loss,
            "roster_sizes": roster_sizes,
            "source_field_hhi": _hhi(source_values),
            "spend": spend,
            "winning_bids": prices,
        }
    )
    return pressure


def _competition_effects(
    rival: TalentMarket,
    nonrival: dict[str, TalentMarket],
    config: dict[str, Any],
    *,
    phase: str,
    window_id: str,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    rival_rates: list[float] = []
    nonrival_rates: list[float] = []
    effects: list[float] = []
    for organization in config["organizations"]:
        organization_id = str(organization["organization_id"])
        mission = _mission(dict(organization["mission"]))
        salt = f"w7-01:{phase}:{organization_id}"
        rival_result = _organization_rate(
            _roster(rival, organization_id, window_id),
            mission,
            config,
            seed_salt=salt,
        )
        nonrival_result = _organization_rate(
            _roster(nonrival[organization_id], organization_id, window_id),
            mission,
            config,
            seed_salt=salt,
        )
        rival_rate = float(rival_result["success_rate"])
        nonrival_rate = float(nonrival_result["success_rate"])
        effect = rival_rate - nonrival_rate
        rival_rates.append(rival_rate)
        nonrival_rates.append(nonrival_rate)
        effects.append(effect)
        rows.append(
            {
                "competition_effect": effect,
                "nonrival": nonrival_result,
                "organization_id": organization_id,
                "rival": rival_result,
            }
        )

    pooled = _mean(effects)
    band = float(config["effect_band"])
    return {
        "classification": _classify(pooled, band),
        "mean_competition_effect": pooled,
        "mean_nonrival_success": _mean(nonrival_rates),
        "mean_rival_success": _mean(rival_rates),
        "negative_organizations": sum(effect < 0 for effect in effects),
        "nonrival_outcome_sd": statistics.pstdev(nonrival_rates),
        "organization_results": rows,
        "positive_organizations": sum(effect > 0 for effect in effects),
        "rival_outcome_sd": statistics.pstdev(rival_rates),
    }


def _source_extraction(
    population: Population,
    rival: TalentMarket,
    config: dict[str, Any],
    *,
    window_id: str,
) -> dict[str, Any]:
    recruited = {
        str(row["agent_id"])
        for row in _contract_rows(rival)
        if row["window_id"] == window_id
    }
    rows: list[dict[str, Any]] = []
    losses: list[float] = []
    for field_id in sorted(population.states_by_field):
        baseline_states = list(population.states_by_field[field_id])
        remaining = [state for state in baseline_states if state.agent_id not in recruited]
        baseline = _source_frontier(baseline_states, config)
        after = _source_frontier(remaining, config)
        loss = baseline - after
        losses.append(loss)
        rows.append(
            {
                "agents_remaining": len(remaining),
                "agents_recruited": len(baseline_states) - len(remaining),
                "field_id": field_id,
                "home_after_recruitment": after,
                "home_baseline": baseline,
                "source_loss": loss,
            }
        )
    pooled = _mean(losses)
    band = float(config["effect_band"])
    positive = sum(value > 0 for value in losses)
    negative = sum(value < 0 for value in losses)
    if pooled > band and positive >= 2:
        classification = "positive"
    elif pooled < -band and negative >= 2:
        classification = "negative"
    else:
        classification = "null"
    return {
        "classification": classification,
        "extraction_regime": classification == "positive",
        "field_results": rows,
        "mean_source_loss": pooled,
        "negative_fields": negative,
        "positive_fields": positive,
    }


def _rank_for_skill(states: list[IndividualState], skill: str) -> list[IndividualState]:
    return sorted(
        states,
        key=lambda state: (state.practice(skill), state.agent_id),
        reverse=True,
    )


def _coalition_experiments(
    rival: TalentMarket,
    config: dict[str, Any],
    *,
    phase: str,
    window_id: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    coalition_rows: list[dict[str, Any]] = []
    withholding_rows: list[dict[str, Any]] = []
    effects: list[float] = []
    withholding_costs: list[float] = []
    for row in config["coalition_missions"]:
        coalition_id = str(row["coalition_id"])
        lead_org = str(row["lead_organization_id"])
        support_org = str(row["support_organization_id"])
        mission = _mission(dict(row["mission"]))
        lead_roster = _roster(rival, lead_org, window_id)
        support_roster = _roster(rival, support_org, window_id)
        lead_ranked = _rank_for_skill(lead_roster, mission.lead_skill)
        support_ranked = _rank_for_skill(support_roster, mission.support_skill)
        salt = f"w7-05:{phase}:{coalition_id}"

        standalone_lead = _organization_rate(
            lead_roster,
            mission,
            config,
            seed_salt=salt,
        )
        standalone_support = _organization_rate(
            support_roster,
            mission,
            config,
            seed_salt=salt,
        )
        best_standalone = max(
            float(standalone_lead["success_rate"]),
            float(standalone_support["success_rate"]),
        )

        if not lead_ranked or not support_ranked:
            coalition_rate = 0.0
            available = False
            lead_agent_id = lead_ranked[0].agent_id if lead_ranked else None
            support_agent_id = support_ranked[0].agent_id if support_ranked else None
        else:
            available = True
            lead_state = lead_ranked[0]
            support_state = support_ranked[0]
            lead_agent_id = lead_state.agent_id
            support_agent_id = support_state.agent_id
            agreement = CooperationAgreement(
                agreement_id=f"{phase}:{coalition_id}",
                window_id=window_id,
                mission_id=mission.mission_id,
                contributions=(
                    (lead_org, lead_state.agent_id),
                    (support_org, support_state.agent_id),
                ),
                evidence_refs=(f"world://w7/{phase}/coalition/{coalition_id}",),
            )
            rival.prepare_coalition(agreement)
            coalition_rate = _pair_rate(
                lead_state,
                support_state,
                mission,
                config,
                seed_salt=salt,
            )

        effect = coalition_rate - best_standalone
        effects.append(effect)
        coalition_rows.append(
            {
                "available": available,
                "best_standalone_success": best_standalone,
                "coalition_effect": effect,
                "coalition_id": coalition_id,
                "coalition_success": coalition_rate,
                "lead_agent_id": lead_agent_id,
                "lead_organization_id": lead_org,
                "support_agent_id": support_agent_id,
                "support_organization_id": support_org,
            }
        )

        degraded_available = len(support_ranked) >= 2 and bool(lead_ranked)
        if degraded_available:
            degraded_rate = _pair_rate(
                lead_ranked[0],
                support_ranked[1],
                mission,
                config,
                seed_salt=salt,
            )
            degraded_agent_id = support_ranked[1].agent_id
        else:
            degraded_rate = coalition_rate
            degraded_agent_id = None
        withholding_cost = coalition_rate - degraded_rate
        withholding_costs.append(withholding_cost)
        withholding_rows.append(
            {
                "coalition_id": coalition_id,
                "degraded_contributor_available": degraded_available,
                "degraded_support_agent_id": degraded_agent_id,
                "degraded_success": degraded_rate,
                "intact_success": coalition_rate,
                "withholding_cost": withholding_cost,
                "withholding_side": str(config["withholding_side"]),
            }
        )

    pooled = _mean(effects)
    band = float(config["effect_band"])
    positive = sum(value > 0 for value in effects)
    negative = sum(value < 0 for value in effects)
    if pooled > band and positive >= 2:
        classification = "positive"
    elif pooled < -band and negative >= 2:
        classification = "negative"
    else:
        classification = "null"
    coalition = {
        "classification": classification,
        "coalition_results": coalition_rows,
        "coopetition_supported": classification == "positive",
        "mean_coalition_effect": pooled,
        "negative_missions": negative,
        "positive_missions": positive,
    }
    withholding = {
        "mean_withholding_cost": _mean(withholding_costs),
        "mission_results": withholding_rows,
    }
    return coalition, withholding


def run_phase(
    candidates_path: str | Path,
    capsules_path: str | Path,
    config_path: str | Path,
    phase: str,
) -> dict[str, Any]:
    if phase not in {"discovery", "replication"}:
        raise ValueError("phase must be discovery or replication")
    config = _read_json(config_path)
    population = _load_population(candidates_path, capsules_path, config, phase)
    window_id = f"w7-{phase}-overlap"
    offers = _generate_offers(
        population,
        config,
        window_id=window_id,
        requirement_key="overlap_bidding_requirements",
    )
    offer_digest = _offer_digest(offers)
    rival = _rival_allocation(population, offers, config, window_id)
    nonrival = _nonrival_allocations(population, offers, config, window_id)

    w7_01 = _competition_effects(
        rival,
        nonrival,
        config,
        phase=phase,
        window_id=window_id,
    )
    w7_02 = _market_metrics(rival, nonrival, offers, population, window_id)

    disjoint_window = f"w7-{phase}-disjoint"
    disjoint_offers = _generate_offers(
        population,
        config,
        window_id=disjoint_window,
        requirement_key="disjoint_bidding_requirements",
    )
    disjoint_rival = _rival_allocation(
        population,
        disjoint_offers,
        config,
        disjoint_window,
    )
    disjoint_metrics = _market_metrics(
        disjoint_rival,
        _nonrival_allocations(population, disjoint_offers, config, disjoint_window),
        disjoint_offers,
        population,
        disjoint_window,
    )
    w7_03 = {
        "contested_share_difference": float(w7_02["contested_agent_share"])
        - float(disjoint_metrics["contested_agent_share"]),
        "disjoint_contested_agent_share": disjoint_metrics["contested_agent_share"],
        "disjoint_mean_winning_bid": disjoint_metrics["mean_winning_bid"],
        "overlap_contested_agent_share": w7_02["contested_agent_share"],
        "overlap_mean_winning_bid": w7_02["mean_winning_bid"],
        "overlap_price_pressure": float(w7_02["mean_winning_bid"])
        - float(disjoint_metrics["mean_winning_bid"]),
    }
    w7_04 = _source_extraction(population, rival, config, window_id=window_id)
    w7_05, w7_06 = _coalition_experiments(
        rival,
        config,
        phase=phase,
        window_id=window_id,
    )

    state_before = {
        agent_id: state.digest() for agent_id, state in population.portable_by_id.items()
    }
    state_after = {
        agent_id: state.digest() for agent_id, state in population.portable_by_id.items()
    }
    if state_before != state_after:
        raise AssertionError("W7 market/coalition execution mutated portable agent state")

    return {
        "field_count": len(population.states_by_field),
        "market_digest": rival.digest(),
        "offer_digest": offer_digest,
        "phase": phase,
        "population_count": len(population.portable_by_id),
        "w7_01": w7_01,
        "w7_02": w7_02,
        "w7_03": w7_03,
        "w7_04": w7_04,
        "w7_05": w7_05,
        "w7_06": w7_06,
    }


def _directional_gate(
    discovery: dict[str, Any],
    replication: dict[str, Any],
    *,
    effect_key: str,
    positive_key: str,
    negative_key: str,
    band: float,
) -> bool:
    classification = str(discovery["classification"])
    replication_classification = str(replication["classification"])
    effect = float(replication[effect_key])
    if classification == "null":
        return replication_classification == "null" and abs(effect) <= band
    if classification == "positive":
        return (
            replication_classification == "positive"
            and effect > band
            and int(replication[positive_key]) >= 2
        )
    return (
        replication_classification == "negative"
        and effect < -band
        and int(replication[negative_key]) >= 2
    )


def synthesize(
    discovery: dict[str, Any],
    replication: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, Any]:
    band = float(config["effect_band"])
    w7_01_gate = _directional_gate(
        dict(discovery["w7_01"]),
        dict(replication["w7_01"]),
        effect_key="mean_competition_effect",
        positive_key="positive_organizations",
        negative_key="negative_organizations",
        band=band,
    )
    w7_04_gate = _directional_gate(
        dict(discovery["w7_04"]),
        dict(replication["w7_04"]),
        effect_key="mean_source_loss",
        positive_key="positive_fields",
        negative_key="negative_fields",
        band=band,
    )
    w7_05_gate = _directional_gate(
        dict(discovery["w7_05"]),
        dict(replication["w7_05"]),
        effect_key="mean_coalition_effect",
        positive_key="positive_missions",
        negative_key="negative_missions",
        band=band,
    )
    competition_active = bool(discovery["w7_02"]["competition_active"]) and bool(
        replication["w7_02"]["competition_active"]
    )
    gates = {
        "competition_active": competition_active,
        "w7_01_competition_classification": w7_01_gate,
        "w7_04_extraction_classification": w7_04_gate,
        "w7_05_coopetition_classification": w7_05_gate,
    }
    passed = all(gates.values())
    return {
        "discovery_classifications": {
            "competition": discovery["w7_01"]["classification"],
            "coopetition": discovery["w7_05"]["classification"],
            "extraction": discovery["w7_04"]["classification"],
        },
        "gates": gates,
        "replication_classifications": {
            "competition": replication["w7_01"]["classification"],
            "coopetition": replication["w7_05"]["classification"],
            "extraction": replication["w7_04"]["classification"],
        },
        "status": (
            "w7_primary_classifications_replicated"
            if passed
            else "w7_discovery_not_replicated"
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("discover", "replicate"):
        phase_parser = subparsers.add_parser(command)
        phase_parser.add_argument("candidates", type=Path)
        phase_parser.add_argument("capsules", type=Path)
        phase_parser.add_argument("config", type=Path)
        phase_parser.add_argument("output", type=Path)
    synthesis_parser = subparsers.add_parser("synthesize")
    synthesis_parser.add_argument("discovery", type=Path)
    synthesis_parser.add_argument("replication", type=Path)
    synthesis_parser.add_argument("config", type=Path)
    synthesis_parser.add_argument("output", type=Path)
    args = parser.parse_args(argv)

    if args.command in {"discover", "replicate"}:
        phase = "discovery" if args.command == "discover" else "replication"
        result = run_phase(args.candidates, args.capsules, args.config, phase)
        filename = "w7-discovery.json" if phase == "discovery" else "w7-07-replication.json"
        _write_json(args.output / filename, result)
    else:
        discovery = _read_json(args.discovery)
        replication = _read_json(args.replication)
        config = _read_json(args.config)
        result = synthesize(discovery, replication, config)
        _write_json(args.output / "w7-synthesis.json", result)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
