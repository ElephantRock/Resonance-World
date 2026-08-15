"""Deterministic D1 capability-development and reproduction substrate."""
from __future__ import annotations

import hashlib
import json
import math
import statistics
from dataclasses import dataclass
from typing import Any

SKILLS = ("skill-a", "skill-b", "skill-c")
FORBIDDEN_EXPORT_KEYS = {
    "agent_id",
    "private_practice_state",
    "practice_by_skill",
    "source_conversation_state",
    "source_seed",
    "source_environment_seed",
    "evaluator_truth",
    "evaluation_answers",
}


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def sha256(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def uniform(*parts: object) -> float:
    raw = "|".join(str(part) for part in parts).encode()
    return int.from_bytes(hashlib.sha256(raw).digest()[:8], "big") / 2**64


def choose_weighted(items: tuple[str, ...], weights: tuple[float, ...], *salt: object) -> str:
    total = sum(weights)
    draw = uniform(*salt) * total
    running = 0.0
    for item, weight in zip(items, weights, strict=True):
        running += weight
        if draw < running:
            return item
    return items[-1]


def success_probability(practice: float, *, base: float, gain: float, maximum: float) -> float:
    return min(maximum, base + gain * math.sqrt(max(0.0, practice)))


@dataclass
class AgentState:
    agent_id: str
    practice: dict[str, float]
    wins: dict[str, int]
    successes: dict[str, int]


def fresh_population(prefix: str, size: int) -> list[AgentState]:
    return [
        AgentState(
            agent_id=f"{prefix}-agent-{index:02d}",
            practice={skill: 0.0 for skill in SKILLS},
            wins={skill: 0 for skill in SKILLS},
            successes={skill: 0 for skill in SKILLS},
        )
        for index in range(size)
    ]


def task_skill(seed: int, cycle: int, target_skill: str, target_share: float) -> str:
    distractors = tuple(skill for skill in SKILLS if skill != target_skill)
    return choose_weighted(
        (target_skill, *distractors),
        (target_share, (1.0 - target_share) / 2.0, (1.0 - target_share) / 2.0),
        "d1-task-skill",
        seed,
        cycle,
    )


def pick_worker(
    agents: list[AgentState],
    skill: str,
    *,
    seed: int,
    cycle: int,
    exploration_rate: float,
) -> AgentState:
    if uniform("d1-explore", seed, cycle) < exploration_rate:
        ranked = sorted(
            agents,
            key=lambda agent: uniform("d1-explore-rank", seed, cycle, agent.agent_id),
        )
        return ranked[0]
    return max(
        agents,
        key=lambda agent: (
            agent.practice[skill],
            uniform("d1-bid-tie", seed, cycle, agent.agent_id),
        ),
    )


def develop_population(
    *,
    seed: int,
    prefix: str,
    target_skill: str,
    population_size: int,
    cycles: int,
    target_share: float,
    exploration_rate: float,
    base_success: float,
    practice_gain: float,
    maximum_success: float,
    failure_learning: float,
) -> tuple[list[AgentState], list[dict[str, Any]]]:
    agents = fresh_population(prefix, population_size)
    public_events: list[dict[str, Any]] = []
    for cycle in range(cycles):
        skill = task_skill(seed, cycle, target_skill, target_share)
        worker = pick_worker(
            agents,
            skill,
            seed=seed,
            cycle=cycle,
            exploration_rate=exploration_rate,
        )
        p = success_probability(
            worker.practice[skill],
            base=base_success,
            gain=practice_gain,
            maximum=maximum_success,
        )
        succeeded = uniform("d1-development-outcome", seed, cycle, worker.agent_id, skill) < p
        worker.wins[skill] += 1
        worker.successes[skill] += int(succeeded)
        worker.practice[skill] += 1.0 if succeeded else failure_learning
        public_events.append(
            {
                "cycle": cycle,
                "required_skill": skill,
                "worker_id": worker.agent_id,
                "success": succeeded,
            }
        )
    return agents, public_events


def evaluate_agent(
    agent: AgentState,
    *,
    target_skill: str,
    seed: int,
    phase: str,
    trials: int,
    base_success: float,
    practice_gain: float,
    maximum_success: float,
) -> float:
    p = success_probability(
        agent.practice[target_skill],
        base=base_success,
        gain=practice_gain,
        maximum=maximum_success,
    )
    successes = sum(
        uniform("d1-eval", phase, seed, agent.agent_id, trial) < p
        for trial in range(trials)
    )
    return successes / trials


def select_specialist(
    agents: list[AgentState],
    *,
    target_skill: str,
    seed: int,
    selection_trials: int,
    base_success: float,
    practice_gain: float,
    maximum_success: float,
) -> tuple[AgentState, dict[str, float]]:
    scores = {
        agent.agent_id: evaluate_agent(
            agent,
            target_skill=target_skill,
            seed=seed,
            phase="selection",
            trials=selection_trials,
            base_success=base_success,
            practice_gain=practice_gain,
            maximum_success=maximum_success,
        )
        for agent in agents
    }
    selected = max(agents, key=lambda agent: (scores[agent.agent_id], agent.agent_id))
    return selected, scores


def infer_target_skill(public_events: list[dict[str, Any]]) -> str:
    counts = {skill: 0 for skill in SKILLS}
    for event in public_events:
        counts[str(event["required_skill"])] += 1
    return max(SKILLS, key=lambda skill: (counts[skill], skill))


def capability_artifact(
    *,
    public_events: list[dict[str, Any]],
    config: dict[str, Any],
) -> dict[str, Any]:
    target_skill = infer_target_skill(public_events)
    event_digest = hashlib.sha256(canonical_bytes(public_events)).hexdigest()
    artifact = {
        "schema": "d1-capability-artifact-v0.1",
        "capability_class": "individual_specialist",
        "behavioral_objective": {"target_skill": target_skill},
        "source_evidence": {"public_event_sha256": event_digest},
        "required_task_ecology": {
            "skills": list(SKILLS),
            "target_share": config["target_share"],
            "exploration_rate": config["exploration_rate"],
        },
        "required_substrate": {
            "success_law": {
                "base_success": config["base_success"],
                "practice_gain": config["practice_gain"],
                "maximum_success": config["maximum_success"],
            },
            "learning_state": "agent_local_practice_count_by_skill",
            "private_state_transfer_allowed": False,
        },
        "development_protocol": {
            "population_size": config["population_size"],
            "cycles": config["cycles"],
            "feedback": "binary_outcome",
            "learning_rule": "success=1.0 practice unit; failure=failure_learning units",
            "failure_learning": config["failure_learning"],
            "selection_trials": config["selection_trials"],
        },
        "resource_requirements": {"tooling": "none", "simulator_cycles": config["cycles"]},
        "stopping_rule": {"type": "fixed_cycles", "cycles": config["cycles"]},
        "evaluation_contract": {"holdout_trials": config["evaluation_trials"]},
        "forbidden_transfers": sorted(FORBIDDEN_EXPORT_KEYS),
    }
    serialized = json.dumps(artifact, sort_keys=True)
    for forbidden in FORBIDDEN_EXPORT_KEYS:
        if f'"{forbidden}"' in serialized and forbidden != "agent_id":
            occurrences = serialized.count(f'"{forbidden}"')
            if occurrences != 1:
                raise AssertionError(f"forbidden private key leaked: {forbidden}")
    return artifact


def run_field_pair(pair_seed: int, config: dict[str, Any]) -> dict[str, Any]:
    target_skill = SKILLS[pair_seed % len(SKILLS)]
    source_seed = 100_000 + pair_seed * 2
    destination_seed = 100_001 + pair_seed * 2

    source_agents, source_events = develop_population(
        seed=source_seed,
        prefix=f"source-{pair_seed}",
        target_skill=target_skill,
        population_size=int(config["population_size"]),
        cycles=int(config["cycles"]),
        target_share=float(config["target_share"]),
        exploration_rate=float(config["exploration_rate"]),
        base_success=float(config["base_success"]),
        practice_gain=float(config["practice_gain"]),
        maximum_success=float(config["maximum_success"]),
        failure_learning=float(config["failure_learning"]),
    )
    source_selected, _ = select_specialist(
        source_agents,
        target_skill=target_skill,
        seed=source_seed,
        selection_trials=int(config["selection_trials"]),
        base_success=float(config["base_success"]),
        practice_gain=float(config["practice_gain"]),
        maximum_success=float(config["maximum_success"]),
    )
    artifact = capability_artifact(
        public_events=source_events,
        config=config,
    )
    if artifact["behavioral_objective"]["target_skill"] != target_skill:
        raise AssertionError("artifact extracted wrong specialization")

    destination_agents, destination_events = develop_population(
        seed=destination_seed,
        prefix=f"destination-{pair_seed}",
        target_skill=str(artifact["behavioral_objective"]["target_skill"]),
        population_size=int(artifact["development_protocol"]["population_size"]),
        cycles=int(artifact["development_protocol"]["cycles"]),
        target_share=float(artifact["required_task_ecology"]["target_share"]),
        exploration_rate=float(artifact["required_task_ecology"]["exploration_rate"]),
        base_success=float(artifact["required_substrate"]["success_law"]["base_success"]),
        practice_gain=float(artifact["required_substrate"]["success_law"]["practice_gain"]),
        maximum_success=float(artifact["required_substrate"]["success_law"]["maximum_success"]),
        failure_learning=float(artifact["development_protocol"]["failure_learning"]),
    )
    destination_selected, _ = select_specialist(
        destination_agents,
        target_skill=target_skill,
        seed=destination_seed,
        selection_trials=int(config["selection_trials"]),
        base_success=float(config["base_success"]),
        practice_gain=float(config["practice_gain"]),
        maximum_success=float(config["maximum_success"]),
    )

    fresh_agents = fresh_population(f"fresh-{pair_seed}", int(config["population_size"]))
    fresh_selected, _ = select_specialist(
        fresh_agents,
        target_skill=target_skill,
        seed=destination_seed + 7_000_000,
        selection_trials=int(config["selection_trials"]),
        base_success=float(config["base_success"]),
        practice_gain=float(config["practice_gain"]),
        maximum_success=float(config["maximum_success"]),
    )

    oracle = AgentState(
        agent_id=f"oracle-{pair_seed}",
        practice=dict(source_selected.practice),
        wins=dict(source_selected.wins),
        successes=dict(source_selected.successes),
    )

    eval_trials = int(config["evaluation_trials"])
    scores = {
        "source_developed": evaluate_agent(
            source_selected,
            target_skill=target_skill,
            seed=pair_seed,
            phase="source-confirmatory-holdout",
            trials=eval_trials,
            base_success=float(config["base_success"]),
            practice_gain=float(config["practice_gain"]),
            maximum_success=float(config["maximum_success"]),
        ),
        "reproduced_protocol": evaluate_agent(
            destination_selected,
            target_skill=target_skill,
            seed=pair_seed,
            phase="destination-confirmatory-holdout",
            trials=eval_trials,
            base_success=float(config["base_success"]),
            practice_gain=float(config["practice_gain"]),
            maximum_success=float(config["maximum_success"]),
        ),
        "fresh_no_development": evaluate_agent(
            fresh_selected,
            target_skill=target_skill,
            seed=pair_seed,
            phase="fresh-confirmatory-holdout",
            trials=eval_trials,
            base_success=float(config["base_success"]),
            practice_gain=float(config["practice_gain"]),
            maximum_success=float(config["maximum_success"]),
        ),
        "private_state_oracle": evaluate_agent(
            oracle,
            target_skill=target_skill,
            seed=pair_seed,
            phase="oracle-confirmatory-holdout",
            trials=eval_trials,
            base_success=float(config["base_success"]),
            practice_gain=float(config["practice_gain"]),
            maximum_success=float(config["maximum_success"]),
        ),
    }

    export_text = json.dumps(artifact, sort_keys=True)
    if str(source_seed) in export_text:
        raise AssertionError("reconstructive source seed leaked into capability artifact")
    if source_selected.agent_id in export_text:
        raise AssertionError("source agent identity leaked into capability artifact")
    forbidden_leaks = [
        key
        for key in (
            "practice_by_skill",
            "private_practice_state",
            "source_conversation_state",
            "source_seed",
            "source_environment_seed",
            "evaluator_truth",
            "evaluation_answers",
        )
        if f'"{key}":' in export_text
    ]
    return {
        "pair_seed": pair_seed,
        "target_skill": target_skill,
        "source_agent_id": source_selected.agent_id,
        "destination_agent_id": destination_selected.agent_id,
        "source_destination_identity_disjoint": source_selected.agent_id
        != destination_selected.agent_id,
        "source_public_event_count": len(source_events),
        "destination_public_event_count": len(destination_events),
        "capability_artifact": artifact,
        "capability_artifact_sha256": sha256(artifact),
        "capability_artifact_bytes": len(canonical_bytes(artifact)),
        "forbidden_private_export_keys_found": forbidden_leaks,
        "scores": scores,
        "source_private_state_sha256": sha256(source_selected.practice),
        "destination_private_state_sha256": sha256(destination_selected.practice),
    }


def mean(values: list[float]) -> float:
    return statistics.mean(values) if values else 0.0


def pstdev(values: list[float]) -> float:
    return statistics.pstdev(values) if len(values) > 1 else 0.0
