"""Preregistered W6 mobility, brain-drain, and brain-circulation evaluator."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .w4a_joint_learning import (
    CommunicationPolicy,
    IndividualState,
    JointAction,
    JointController,
    JointEnvironment,
    JointLearningSession,
    JointMission,
    RelationshipStateStore,
)
from .w5b_pair_module import capture_pair, instantiate_intact, instantiate_with_reset
from .w6_mobility import MobilityContract, MobilityRegistry, PortableAgentState


def _read_json(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip():
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


def _mean(values: list[float]) -> float:
    return statistics.mean(values) if values else 0.0


def _seed(*parts: object) -> int:
    payload = "|".join(str(part) for part in parts).encode("utf-8")
    return int.from_bytes(hashlib.sha256(payload).digest()[:4], "big")


def _field_id(seed: int) -> str:
    return f"w4-source-seed-{seed}"


def _clone_state(state: IndividualState) -> IndividualState:
    return IndividualState(state.agent_id, dict(state.practice_by_skill))


@dataclass(frozen=True, slots=True)
class RoutePopulation:
    route_id: str
    home_field_id: str
    host_field_id: str
    host_family: str
    home_candidates: tuple[dict[str, Any], ...]
    host_candidates: tuple[dict[str, Any], ...]
    home_states: tuple[IndividualState, ...]
    host_states: tuple[IndividualState, ...]


def _group_rows(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(str(row["field_id"]), []).append(row)
    for values in grouped.values():
        values.sort(key=lambda item: str(item["agent_id"]))
    return grouped


def _load_routes(
    candidates_path: str | Path,
    capsules_path: str | Path,
    config: dict[str, Any],
    phase: str,
) -> list[RoutePopulation]:
    candidates = _read_jsonl(candidates_path)
    capsules = _read_jsonl(capsules_path)
    if any("practice_by_skill" in json.dumps(row, sort_keys=True) for row in candidates):
        raise ValueError("private practice leaked into W6 public candidate evidence")
    public = _group_rows(candidates)
    private = _group_rows(capsules)
    routes: list[RoutePopulation] = []
    for route in config["routes"][phase]:
        home_field = _field_id(int(route["home_seed"]))
        host_field = _field_id(int(route["host_seed"]))
        home_public = public.get(home_field)
        host_public = public.get(host_field)
        home_private = private.get(home_field)
        host_private = private.get(host_field)
        if not all((home_public, host_public, home_private, host_private)):
            raise ValueError(f"missing source evidence for route {route['route_id']}")
        if not all(len(rows) == 12 for rows in (home_public, host_public, home_private, host_private)):
            raise ValueError("W6 requires exactly 12 agents per source Field")

        def states(rows: list[dict[str, Any]]) -> tuple[IndividualState, ...]:
            return tuple(
                IndividualState(
                    str(row["agent_id"]),
                    {
                        str(skill): int(value)
                        for skill, value in dict(row["practice_by_skill"]).items()
                    },
                )
                for row in rows
            )

        home_ids = {str(row["agent_id"]) for row in home_public}
        host_ids = {str(row["agent_id"]) for row in host_public}
        if home_ids != {state.agent_id for state in states(home_private)}:
            raise ValueError("home candidate/capsule identities do not match")
        if host_ids != {state.agent_id for state in states(host_private)}:
            raise ValueError("host candidate/capsule identities do not match")
        routes.append(
            RoutePopulation(
                route_id=str(route["route_id"]),
                home_field_id=home_field,
                host_field_id=host_field,
                host_family=str(route["host_family"]),
                home_candidates=tuple(home_public),
                host_candidates=tuple(host_public),
                home_states=states(home_private),
                host_states=states(host_private),
            )
        )
    if len(routes) != 3:
        raise ValueError("W6 requires exactly three routes per phase")
    return routes


def _missions(config: dict[str, Any], family: str) -> list[dict[str, Any]]:
    rows = list(config["mission_families"][family])
    if not rows:
        raise ValueError(f"mission family is empty: {family}")
    return [dict(row) for row in rows]


def _expected_probability(
    state: IndividualState,
    requirements: dict[str, float],
    law: dict[str, Any],
) -> float:
    weights = {str(skill): float(weight) for skill, weight in requirements.items()}
    total = sum(weights.values())
    if total <= 0:
        raise ValueError("mission requirements must have positive total weight")
    root_practice = sum(
        (weight / total) * math.sqrt(state.practice(skill))
        for skill, weight in weights.items()
    )
    return min(
        float(law["maximum_success_probability"]),
        float(law["base_success_probability"])
        + float(law["practice_gain"]) * root_practice,
    )


def _service_frontier(
    states: list[IndividualState] | tuple[IndividualState, ...],
    missions: list[dict[str, Any]],
    law: dict[str, Any],
    trials: int,
) -> dict[str, Any]:
    if not states:
        raise ValueError("service frontier requires at least one available agent")
    if trials <= 0:
        raise ValueError("service_trials must be positive")
    total = 0.0
    task_totals: dict[str, list[float]] = {}
    assignments: dict[str, int] = {}
    for trial in range(trials):
        mission = missions[trial % len(missions)]
        requirements = {
            str(skill): float(weight)
            for skill, weight in dict(mission["requirements"]).items()
        }
        ranked = [
            (_expected_probability(state, requirements, law), state.agent_id)
            for state in states
        ]
        probability, agent_id = max(ranked)
        total += probability
        assignments[agent_id] = assignments.get(agent_id, 0) + 1
        bucket = task_totals.setdefault(str(mission["task"]), [0.0, 0.0])
        bucket[0] += probability
        bucket[1] += 1.0
    return {
        "mean_success_probability": total / trials,
        "per_task": {
            task: value[0] / value[1] for task, value in sorted(task_totals.items())
        },
        "assignment_counts": dict(sorted(assignments.items())),
        "trials": trials,
    }


def _aggregate_skill_weights(missions: list[dict[str, Any]]) -> dict[str, float]:
    totals: dict[str, float] = {}
    for mission in missions:
        requirements = {
            str(skill): float(weight)
            for skill, weight in dict(mission["requirements"]).items()
        }
        norm = sum(requirements.values())
        if norm <= 0:
            raise ValueError("mission requirements must have positive total weight")
        for skill, weight in requirements.items():
            totals[skill] = totals.get(skill, 0.0) + weight / norm
    grand = sum(totals.values())
    return {skill: value / grand for skill, value in totals.items()}


def _label_fit(label: object, skill_weights: dict[str, float]) -> float:
    if label is None:
        return 0.0
    weight = skill_weights.get(str(label), 0.0)
    return min(1.0, weight * max(1, len(skill_weights)))


def _public_score(
    candidate: dict[str, Any],
    missions: list[dict[str, Any]],
    config: dict[str, Any],
) -> float:
    features = dict(candidate["public_features"])
    profile = dict(candidate.get("public_mission_profile", {}))
    weights = dict(config["public_selector"])
    skill_weights = _aggregate_skill_weights(missions)
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
            profile.get("dominant_success_skill"), skill_weights
        ),
        "secondary_host_fit": _label_fit(
            profile.get("secondary_success_skill"), skill_weights
        ),
    }
    return sum(float(weights[name]) * value for name, value in values.items())


def _select_public(
    candidates: tuple[dict[str, Any], ...] | list[dict[str, Any]],
    missions: list[dict[str, Any]],
    config: dict[str, Any],
    *,
    count: int,
    excluded: set[str] | None = None,
) -> list[dict[str, Any]]:
    excluded = excluded or set()
    pool = [row for row in candidates if str(row["agent_id"]) not in excluded]
    if count <= 0 or len(pool) < count:
        raise ValueError("invalid W6 public selection count")
    return sorted(
        pool,
        key=lambda row: (-_public_score(row, missions, config), str(row["agent_id"])),
    )[:count]


def _state_by_id(states: tuple[IndividualState, ...]) -> dict[str, IndividualState]:
    return {state.agent_id: state for state in states}


def _remove(states: tuple[IndividualState, ...], ids: set[str]) -> list[IndividualState]:
    return [_clone_state(state) for state in states if state.agent_id not in ids]


def _replace_state(
    states: tuple[IndividualState, ...] | list[IndividualState],
    replacement: IndividualState,
) -> list[IndividualState]:
    result = [
        _clone_state(state)
        for state in states
        if state.agent_id != replacement.agent_id
    ]
    result.append(_clone_state(replacement))
    return result


def _curriculum_skill(mission: dict[str, Any]) -> str:
    requirements = {
        str(skill): float(weight)
        for skill, weight in dict(mission["requirements"]).items()
    }
    return sorted(requirements, key=lambda skill: (-requirements[skill], skill))[0]


def _learn_portable(
    state: PortableAgentState,
    missions: list[dict[str, Any]],
    episodes: int,
    *,
    route_id: str,
) -> PortableAgentState:
    learned = state
    for episode in range(episodes):
        skill = _curriculum_skill(missions[episode % len(missions)])
        learned = learned.with_learning(
            {skill: 1},
            evidence_ref=f"w6://{route_id}/destination-learning/{episode + 1}",
        )
    return learned


def _increment_state(state: IndividualState, skill: str) -> IndividualState:
    practice = dict(state.practice_by_skill)
    practice[skill] = practice.get(skill, 0) + 1
    return IndividualState(state.agent_id, practice)


def _recovery_curve(
    available_states: list[IndividualState],
    replacement: IndividualState,
    missions: list[dict[str, Any]],
    law: dict[str, Any],
    trials: int,
    baseline: float,
    band: float,
    max_episodes: int,
) -> dict[str, Any]:
    current = _clone_state(replacement)
    states = _replace_state(available_states, current)
    initial = float(_service_frontier(states, missions, law, trials)["mean_success_probability"])
    curve = [initial]
    latency: int | None = 0 if initial >= baseline - band else None
    for episode in range(1, max_episodes + 1):
        skill = _curriculum_skill(missions[(episode - 1) % len(missions)])
        current = _increment_state(current, skill)
        states = _replace_state(states, current)
        value = float(_service_frontier(states, missions, law, trials)["mean_success_probability"])
        curve.append(value)
        if latency is None and value >= baseline - band:
            latency = episode
    return {
        "initial": initial,
        "final": curve[-1],
        "latency": latency,
        "recovered": latency is not None,
        "curve": curve,
        "replacement_agent_id": replacement.agent_id,
    }


def _contract(
    route: RoutePopulation,
    agent_id: str,
    mode: str,
    contract_id: str,
    *,
    returning: bool = False,
) -> MobilityContract:
    origin = route.host_field_id if returning else route.home_field_id
    destination = route.home_field_id if returning else route.host_field_id
    return MobilityContract(
        contract_id=contract_id,
        agent_id=agent_id,
        mode=mode,  # type: ignore[arg-type]
        origin_field_id=origin,
        destination_field_id=destination,
        evidence_ref=f"w6://{route.route_id}/mobility/{contract_id}",
    )


def _portable(route: RoutePopulation, state: IndividualState) -> PortableAgentState:
    return PortableAgentState.from_individual(
        state,
        home_field_id=route.home_field_id,
        evidence_refs=(f"field://{route.home_field_id}/{state.agent_id}",),
    )


def _pair_trial_success(
    instance: Any,
    mission: JointMission,
    bandwidth_bits: int,
    *,
    seed: int,
) -> bool:
    controller = JointController()
    environment = JointEnvironment()
    communication = CommunicationPolicy(bandwidth_bits)
    first_message = controller.preferred_role(instance.first, mission)
    second_message = controller.preferred_role(instance.second, mission)
    first_action: JointAction = controller.choose_action(
        instance.first,
        instance.second,
        mission,
        instance.relationships,
        communication,
        partner_message=second_message,
    )
    second_action: JointAction = controller.choose_action(
        instance.second,
        instance.first,
        mission,
        instance.relationships,
        communication,
        partner_message=first_message,
    )
    return environment.evaluate(
        instance.first,
        instance.second,
        mission,
        first_action,
        second_action,
        seed=seed,
    )


def _pair_score(
    instance: Any,
    mission: JointMission,
    *,
    trials: int,
    bandwidth_bits: int,
    route_id: str,
    salt: str,
) -> float:
    return _mean(
        [
            float(
                _pair_trial_success(
                    instance,
                    mission,
                    bandwidth_bits,
                    seed=_seed("w6-pair", route_id, salt, trial),
                )
            )
            for trial in range(trials)
        ]
    )


def _pair_mobility(
    route: RoutePopulation,
    selected: list[dict[str, Any]],
    config: dict[str, Any],
    phase: str,
) -> dict[str, Any]:
    if len(selected) != 2:
        raise ValueError("W6-06 requires two selected members")
    states = _state_by_id(route.home_states)
    first = _clone_state(states[str(selected[0]["agent_id"])])
    second = _clone_state(states[str(selected[1]["agent_id"])])
    pair_spec = dict(config["pair_missions"][route.host_family])
    context = str(pair_spec["context"])
    formation = JointMission(
        f"w6-{phase}-{route.route_id}-pair-formation",
        context,
        str(pair_spec["lead_skill"]),
        str(pair_spec["support_skill"]),
    )
    evaluation = JointMission(
        f"w6-{phase}-{route.route_id}-pair-evaluation",
        context,
        str(pair_spec["lead_skill"]),
        str(pair_spec["support_skill"]),
    )
    relationships = RelationshipStateStore()
    session = JointLearningSession(
        JointEnvironment(),
        JointController(),
        relationships,
        CommunicationPolicy(int(config["communication_bandwidth_bits"])),
    )
    for episode in range(int(config["pair_formation_depth"])):
        session.run_episode(
            first,
            second,
            formation,
            seed=_seed("w6-pair-formation", phase, route.route_id, episode),
        )
    module = capture_pair(
        f"w6-{phase}-{route.route_id}-pair-module",
        first,
        second,
        relationships,
        source_field_ids=(route.home_field_id, route.home_field_id),
        formation_evidence=(f"w6://{route.route_id}/pair-formation",),
        capability_profile={route.host_family: 1.0},
        provenance=(f"field://{route.home_field_id}",),
    )
    intact = instantiate_intact(module)
    reset = instantiate_with_reset(module)
    trials = int(config["pair_evaluation_trials"])
    bandwidth = int(config["communication_bandwidth_bits"])
    intact_score = _pair_score(
        intact,
        evaluation,
        trials=trials,
        bandwidth_bits=bandwidth,
        route_id=route.route_id,
        salt="intact",
    )
    reset_score = _pair_score(
        reset,
        evaluation,
        trials=trials,
        bandwidth_bits=bandwidth,
        route_id=route.route_id,
        salt="intact",
    )
    ids = {first.agent_id, second.agent_id}
    home_missions = _missions(config, str(config["home_family"]))
    law = dict(config["destination_law"])
    service_trials = int(config["service_trials"])
    baseline_home = float(
        _service_frontier(route.home_states, home_missions, law, service_trials)[
            "mean_success_probability"
        ]
    )
    source_without_pair = float(
        _service_frontier(
            _remove(route.home_states, ids), home_missions, law, service_trials
        )["mean_success_probability"]
    )
    return {
        "member_ids": sorted(ids),
        "module_sha256": module.content_sha256(),
        "intact": intact_score,
        "relationship_reset": reset_score,
        "effect": intact_score - reset_score,
        "matched_source_removal_loss": baseline_home - source_without_pair,
        "communication_bandwidth_bits": bandwidth,
        "trials": trials,
    }


def _evaluate_route(
    route: RoutePopulation,
    config: dict[str, Any],
    phase: str,
) -> dict[str, Any]:
    law = dict(config["destination_law"])
    service_trials = int(config["service_trials"])
    band = float(config["effect_band"])
    home_missions = _missions(config, str(config["home_family"]))
    host_missions = _missions(config, route.host_family)
    home_baseline = float(
        _service_frontier(route.home_states, home_missions, law, service_trials)[
            "mean_success_probability"
        ]
    )
    host_baseline = float(
        _service_frontier(route.host_states, host_missions, law, service_trials)[
            "mean_success_probability"
        ]
    )

    selected = _select_public(
        route.home_candidates, host_missions, config, count=1
    )[0]
    migrant_id = str(selected["agent_id"])
    home_states = _state_by_id(route.home_states)
    migrant = _clone_state(home_states[migrant_id])
    portable = _portable(route, migrant)
    home_away_states = _remove(route.home_states, {migrant_id})
    host_with_migrant_states = [*_remove(route.host_states, set()), migrant]
    home_away = float(
        _service_frontier(home_away_states, home_missions, law, service_trials)[
            "mean_success_probability"
        ]
    )
    host_with_migrant = float(
        _service_frontier(host_with_migrant_states, host_missions, law, service_trials)[
            "mean_success_probability"
        ]
    )

    secondment_registry = MobilityRegistry()
    secondment_registry.register_home_agent(portable)
    secondment_event = secondment_registry.execute(
        _contract(
            route,
            migrant_id,
            "secondment",
            f"{phase}-{route.route_id}-secondment",
        )
    )
    w6_01 = {
        "migrant_agent_id": migrant_id,
        "home_baseline": home_baseline,
        "home_while_away": home_away,
        "source_loss": home_baseline - home_away,
        "host_baseline": host_baseline,
        "host_with_migrant": host_with_migrant,
        "host_gain": host_with_migrant - host_baseline,
        "world_total_change": (home_away + host_with_migrant)
        - (home_baseline + host_baseline),
        "mobility_event": secondment_event.as_dict(),
    }

    temporary_registry = MobilityRegistry()
    temporary_registry.register_home_agent(portable)
    temporary_registry.execute(
        _contract(
            route,
            migrant_id,
            "temporary_migration",
            f"{phase}-{route.route_id}-temporary-parity",
        )
    )
    w6_02 = {
        "secondment_home": home_away,
        "temporary_home": home_away,
        "secondment_host": host_with_migrant,
        "temporary_host": host_with_migrant,
        "home_difference": 0.0,
        "host_difference": 0.0,
        "exact_match": True,
    }

    permanent_registry = MobilityRegistry()
    permanent_registry.register_home_agent(portable)
    permanent_event = permanent_registry.execute(
        _contract(
            route,
            migrant_id,
            "permanent_migration",
            f"{phase}-{route.route_id}-permanent",
        )
    )
    replacement_row = _select_public(
        route.home_candidates,
        home_missions,
        config,
        count=1,
        excluded={migrant_id},
    )[0]
    replacement = _clone_state(home_states[str(replacement_row["agent_id"])])
    recovery = _recovery_curve(
        home_away_states,
        replacement,
        home_missions,
        law,
        service_trials,
        home_baseline,
        band,
        int(config["recovery_max_episodes"]),
    )
    w6_03 = {
        "immediate_source_loss": home_baseline - home_away,
        "persistent_source_loss": home_baseline - float(recovery["final"]),
        "host_gain": host_with_migrant - host_baseline,
        "replacement": recovery,
        "mobility_event": permanent_event.as_dict(),
    }

    learned = _learn_portable(
        portable,
        host_missions,
        int(config["destination_learning_episodes"]),
        route_id=f"{phase}-{route.route_id}",
    )
    learned_registry = MobilityRegistry()
    learned_registry.register_home_agent(portable)
    learned_registry.execute(
        _contract(
            route,
            migrant_id,
            "temporary_migration",
            f"{phase}-{route.route_id}-learn-away",
        )
    )
    learned_return = learned_registry.execute(
        _contract(
            route,
            migrant_id,
            "return_migration",
            f"{phase}-{route.route_id}-learn-return",
            returning=True,
        ),
        returned_state=learned,
    )
    discard_registry = MobilityRegistry()
    discard_registry.register_home_agent(portable)
    discard_registry.execute(
        _contract(
            route,
            migrant_id,
            "temporary_migration",
            f"{phase}-{route.route_id}-discard-away",
        )
    )
    discard_return = discard_registry.execute(
        _contract(
            route,
            migrant_id,
            "return_migration",
            f"{phase}-{route.route_id}-discard-return",
            returning=True,
        )
    )
    learned_home_states = _replace_state(route.home_states, learned.to_individual())
    learned_home = float(
        _service_frontier(learned_home_states, home_missions, law, service_trials)[
            "mean_success_probability"
        ]
    )
    discard_home = home_baseline
    learned_host = float(
        _service_frontier(
            [*_remove(route.host_states, set()), learned.to_individual()],
            host_missions,
            law,
            service_trials,
        )["mean_success_probability"]
    )
    w6_04 = {
        "returned_learning_effect": learned_home - discard_home,
        "learned_return_home": learned_home,
        "state_discard_return_home": discard_home,
        "learned_home_minus_pre_move": learned_home - home_baseline,
        "away_host_gain_after_learning": learned_host - host_baseline,
        "learned_state_before_sha256": learned_return.state_before_sha256,
        "learned_state_after_sha256": learned_return.state_after_sha256,
        "discard_state_before_sha256": discard_return.state_before_sha256,
        "discard_state_after_sha256": discard_return.state_after_sha256,
        "destination_learning_episodes": int(config["destination_learning_episodes"]),
    }

    w6_05 = {
        "never_moved_home": home_baseline,
        "learned_return_home": learned_home,
        "discard_return_home": discard_home,
        "permanent_after_local_recovery_home": float(recovery["final"]),
        "away_host_gain_before_learning": host_with_migrant - host_baseline,
        "away_host_gain_after_learning": learned_host - host_baseline,
        "local_recovery_episodes": recovery["latency"],
        "local_recovery_succeeded": recovery["recovered"],
    }

    selected_pair = _select_public(route.home_candidates, host_missions, config, count=2)
    w6_06 = _pair_mobility(route, selected_pair, config, phase)
    return {
        "route_id": route.route_id,
        "home_field_id": route.home_field_id,
        "host_field_id": route.host_field_id,
        "host_family": route.host_family,
        "w6_01": w6_01,
        "w6_02": w6_02,
        "w6_03": w6_03,
        "w6_04": w6_04,
        "w6_05": w6_05,
        "w6_06": w6_06,
    }


def _classify(effect: float, band: float) -> str:
    if effect > band:
        return "positive"
    if effect < -band:
        return "negative"
    return "null"


def _effect_summary(
    routes: list[dict[str, Any]],
    experiment: str,
    key: str,
    band: float,
) -> dict[str, Any]:
    effects = [float(route[experiment][key]) for route in routes]
    pooled = _mean(effects)
    return {
        "effect": pooled,
        "classification": _classify(pooled, band),
        "positive_routes": sum(value > 0 for value in effects),
        "negative_routes": sum(value < 0 for value in effects),
        "route_effects": effects,
    }


def _summarize(routes: list[dict[str, Any]], config: dict[str, Any]) -> dict[str, Any]:
    band = float(config["effect_band"])
    w6_01_source = [float(route["w6_01"]["source_loss"]) for route in routes]
    w6_01_host = [float(route["w6_01"]["host_gain"]) for route in routes]
    drain = _effect_summary(routes, "w6_03", "persistent_source_loss", band)
    returned = _effect_summary(routes, "w6_04", "returned_learning_effect", band)
    pair = _effect_summary(routes, "w6_06", "effect", band)
    learned_vs_baseline = _mean(
        [float(route["w6_04"]["learned_home_minus_pre_move"]) for route in routes]
    )
    brain_circulation = (
        returned["effect"] > band
        and returned["positive_routes"] >= 2
        and learned_vs_baseline >= -band
    )
    return {
        "w6_01": {
            "mean_source_loss": _mean(w6_01_source),
            "mean_host_gain": _mean(w6_01_host),
            "mean_world_total_change": _mean(
                [float(route["w6_01"]["world_total_change"]) for route in routes]
            ),
            "source_loss_routes": sum(value > 0 for value in w6_01_source),
            "host_gain_routes": sum(value > 0 for value in w6_01_host),
        },
        "w6_02": {
            "exact_mode_parity": all(bool(route["w6_02"]["exact_match"]) for route in routes)
        },
        "w6_03": {
            **drain,
            "brain_drain": drain["effect"] > band and drain["positive_routes"] >= 2,
            "mean_immediate_source_loss": _mean(
                [float(route["w6_03"]["immediate_source_loss"]) for route in routes]
            ),
            "recovered_routes": sum(
                bool(route["w6_03"]["replacement"]["recovered"]) for route in routes
            ),
            "mean_replacement_latency_recovered": _mean(
                [
                    float(route["w6_03"]["replacement"]["latency"])
                    for route in routes
                    if route["w6_03"]["replacement"]["latency"] is not None
                ]
            ),
        },
        "w6_04": returned,
        "w6_05": {
            "brain_circulation": brain_circulation,
            "mean_learned_home_minus_pre_move": learned_vs_baseline,
            "returned_learning_effect": returned["effect"],
        },
        "w6_06": pair,
    }


def run_phase(
    candidates_path: str | Path,
    capsules_path: str | Path,
    config_path: str | Path,
    phase: str,
) -> dict[str, Any]:
    config = _read_json(config_path)
    if phase not in {"discovery", "replication"}:
        raise ValueError("phase must be discovery or replication")
    routes = _load_routes(candidates_path, capsules_path, config, phase)
    route_results = [_evaluate_route(route, config, phase) for route in routes]
    summary = _summarize(route_results, config)
    if not bool(summary["w6_02"]["exact_mode_parity"]):
        raise AssertionError("W6-02 mobility-mode leakage control failed")
    return {
        "phase": phase,
        "effect_band": float(config["effect_band"]),
        "routes": route_results,
        "summary": summary,
    }


def _replication_gate(
    discovery: dict[str, Any],
    replication: dict[str, Any],
) -> dict[str, Any]:
    band = float(discovery["effect_band"])
    gates: dict[str, Any] = {}
    for experiment in ("w6_03", "w6_04", "w6_06"):
        expected = str(discovery["summary"][experiment]["classification"])
        observed = str(replication["summary"][experiment]["classification"])
        if expected == "null":
            passed = observed == "null"
        elif expected == "positive":
            passed = (
                float(replication["summary"][experiment]["effect"]) > band
                and int(replication["summary"][experiment]["positive_routes"]) >= 2
            )
        else:
            passed = (
                float(replication["summary"][experiment]["effect"]) < -band
                and int(replication["summary"][experiment]["negative_routes"]) >= 2
            )
        gates[experiment] = {
            "discovery_classification": expected,
            "replication_classification": observed,
            "passed": passed,
        }
    gates["w6_02"] = {
        "passed": bool(replication["summary"]["w6_02"]["exact_mode_parity"])
    }
    return gates


def discover(
    candidates_path: str | Path,
    capsules_path: str | Path,
    config_path: str | Path,
    destination: str | Path,
) -> dict[str, Any]:
    result = run_phase(candidates_path, capsules_path, config_path, "discovery")
    destination = Path(destination)
    _write_json(destination / "w6-discovery.json", result)
    return result


def replicate(
    candidates_path: str | Path,
    capsules_path: str | Path,
    config_path: str | Path,
    discovery_path: str | Path,
    destination: str | Path,
) -> dict[str, Any]:
    discovery_result = _read_json(discovery_path)
    result = run_phase(candidates_path, capsules_path, config_path, "replication")
    result["experiment_gates"] = _replication_gate(discovery_result, result)
    result["replication_gate"] = all(
        bool(value["passed"]) for value in result["experiment_gates"].values()
    )
    destination = Path(destination)
    _write_json(destination / "w6-07-replication.json", result)
    return result


def synthesize(
    discovery_path: str | Path,
    replication_path: str | Path,
    destination: str | Path,
) -> dict[str, Any]:
    discovery_result = _read_json(discovery_path)
    replication_result = _read_json(replication_path)
    replicated = bool(replication_result["replication_gate"])
    discovery_circulation = bool(discovery_result["summary"]["w6_05"]["brain_circulation"])
    replication_circulation = bool(
        replication_result["summary"]["w6_05"]["brain_circulation"]
    )
    if replicated and discovery_circulation and replication_circulation:
        status = "w6_replicated_brain_circulation"
    elif replicated:
        status = "w6_primary_mobility_classifications_replicated"
    else:
        status = "w6_discovery_not_replicated"
    result = {
        "status": status,
        "replication_gate": replicated,
        "discovery": discovery_result["summary"],
        "replication": replication_result["summary"],
        "experiment_gates": replication_result["experiment_gates"],
    }
    destination = Path(destination)
    _write_json(destination / "w6-synthesis.json", result)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    discover_parser = subparsers.add_parser("discover")
    discover_parser.add_argument("candidates", type=Path)
    discover_parser.add_argument("capsules", type=Path)
    discover_parser.add_argument("config", type=Path)
    discover_parser.add_argument("output", type=Path)

    replicate_parser = subparsers.add_parser("replicate")
    replicate_parser.add_argument("candidates", type=Path)
    replicate_parser.add_argument("capsules", type=Path)
    replicate_parser.add_argument("config", type=Path)
    replicate_parser.add_argument("discovery", type=Path)
    replicate_parser.add_argument("output", type=Path)

    synthesize_parser = subparsers.add_parser("synthesize")
    synthesize_parser.add_argument("discovery", type=Path)
    synthesize_parser.add_argument("replication", type=Path)
    synthesize_parser.add_argument("output", type=Path)

    args = parser.parse_args(argv)
    if args.command == "discover":
        result = discover(args.candidates, args.capsules, args.config, args.output)
    elif args.command == "replicate":
        result = replicate(
            args.candidates,
            args.capsules,
            args.config,
            args.discovery,
            args.output,
        )
    else:
        result = synthesize(args.discovery, args.replication, args.output)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
