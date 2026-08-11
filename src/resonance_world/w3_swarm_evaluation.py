"""Destination evaluation helpers for W3 swarm recruitment."""

from __future__ import annotations

import statistics
from itertools import combinations
from typing import Any

from .w3_swarm_core import (
    _agent_key,
    _base_probability,
    _fields,
    _mission_rows,
    _pair_key,
    _practice,
    _sample_probability,
    _select_individual,
    _select_pair,
    _shuffled_relationships,
    _team_probability,
)


def _evaluate_pair(
    first: dict[str, Any],
    second: dict[str, Any],
    mission: dict[str, Any],
    private_agents: dict[tuple[str, str], dict[str, Any]],
    private_pairs: dict[tuple[str, str, str], dict[str, Any]],
    config: dict[str, Any],
    *,
    salt: str,
) -> float:
    field_id = str(first["field_id"])
    key = _pair_key(field_id, str(first["agent_id"]), str(second["agent_id"]))
    probability = _team_probability(
        _practice(private_agents[_agent_key(first)]),
        _practice(private_agents[_agent_key(second)]),
        float(private_pairs[key]["coordination_exposure"]),
        mission,
        config,
    )
    identity = f"{field_id}:{key[1]}::{key[2]}:{mission['mission']}"
    return _sample_probability(
        probability, identity=identity, salt=salt, trials=int(config["trials_per_mission"])
    )


def _evaluate_individual(
    candidate: dict[str, Any],
    mission: dict[str, Any],
    private_agents: dict[tuple[str, str], dict[str, Any]],
    config: dict[str, Any],
    *,
    salt: str,
) -> float:
    practice = _practice(private_agents[_agent_key(candidate)])
    probability = _base_probability(practice, mission, config)
    identity = f"{candidate['field_id']}:{candidate['agent_id']}:{mission['mission']}"
    return _sample_probability(
        probability, identity=identity, salt=salt, trials=int(config["trials_per_mission"])
    )


def _oracle_pair(
    field_rows: list[dict[str, Any]],
    mission: dict[str, Any],
    private_agents: dict[tuple[str, str], dict[str, Any]],
    private_pairs: dict[tuple[str, str, str], dict[str, Any]],
    config: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], float]:
    best: tuple[float, str, dict[str, Any], dict[str, Any]] | None = None
    field_id = str(field_rows[0]["field_id"])
    for first, second in combinations(field_rows, 2):
        key = _pair_key(field_id, str(first["agent_id"]), str(second["agent_id"]))
        probability = _team_probability(
            _practice(private_agents[_agent_key(first)]),
            _practice(private_agents[_agent_key(second)]),
            float(private_pairs[key]["coordination_exposure"]),
            mission,
            config,
        )
        identity = f"{key[1]}::{key[2]}"
        candidate = (probability, identity, first, second)
        if best is None or (candidate[0], candidate[1]) > (best[0], best[1]):
            best = candidate
    if best is None:
        raise ValueError("field does not contain a pair")
    return best[2], best[3], best[0]


def _discover_rows(
    rows: list[dict[str, Any]],
    private_agents: dict[tuple[str, str], dict[str, Any]],
    public_pairs: dict[tuple[str, str, str], dict[str, Any]],
    private_pairs: dict[tuple[str, str, str], dict[str, Any]],
    missions: list[dict[str, Any]],
    config: dict[str, Any],
    recruiter: dict[str, Any],
    *,
    salt: str,
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    beta = float(recruiter["beta"])
    for field_id, field_rows in sorted(_fields(rows).items()):
        shuffled = _shuffled_relationships(field_rows, public_pairs, config)
        for mission in missions:
            swarm_a, swarm_b, swarm_score = _select_pair(
                field_rows, public_pairs, mission, config, beta
            )
            assembled_a, assembled_b, assembled_score = _select_pair(
                field_rows, public_pairs, mission, config, 0.0
            )
            shuffled_a, shuffled_b, shuffled_score = _select_pair(
                field_rows,
                public_pairs,
                mission,
                config,
                beta,
                shuffled_relationships=shuffled,
            )
            individual = _select_individual(field_rows, mission, config)
            oracle_a, oracle_b, oracle_expected = _oracle_pair(
                field_rows, mission, private_agents, private_pairs, config
            )
            output.append(
                {
                    "assembled_pair": [assembled_a["agent_id"], assembled_b["agent_id"]],
                    "assembled_score": assembled_score,
                    "assembled_success": _evaluate_pair(
                        assembled_a,
                        assembled_b,
                        mission,
                        private_agents,
                        private_pairs,
                        config,
                        salt=f"{salt}:pair",
                    ),
                    "field_id": field_id,
                    "individual_agent_id": individual["agent_id"],
                    "individual_success": _evaluate_individual(
                        individual,
                        mission,
                        private_agents,
                        config,
                        salt=f"{salt}:individual",
                    ),
                    "mission": mission["mission"],
                    "oracle_expected_success": oracle_expected,
                    "oracle_pair": [oracle_a["agent_id"], oracle_b["agent_id"]],
                    "oracle_success": _evaluate_pair(
                        oracle_a,
                        oracle_b,
                        mission,
                        private_agents,
                        private_pairs,
                        config,
                        salt=f"{salt}:pair",
                    ),
                    "shuffled_pair": [shuffled_a["agent_id"], shuffled_b["agent_id"]],
                    "shuffled_score": shuffled_score,
                    "shuffled_success": _evaluate_pair(
                        shuffled_a,
                        shuffled_b,
                        mission,
                        private_agents,
                        private_pairs,
                        config,
                        salt=f"{salt}:pair",
                    ),
                    "swarm_pair": [swarm_a["agent_id"], swarm_b["agent_id"]],
                    "swarm_score": swarm_score,
                    "swarm_success": _evaluate_pair(
                        swarm_a,
                        swarm_b,
                        mission,
                        private_agents,
                        private_pairs,
                        config,
                        salt=f"{salt}:pair",
                    ),
                }
            )
    return output


def _resilience(
    rows: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    private_agents: dict[tuple[str, str], dict[str, Any]],
    public_pairs: dict[tuple[str, str, str], dict[str, Any]],
    private_pairs: dict[tuple[str, str, str], dict[str, Any]],
    config: dict[str, Any],
    recruiter: dict[str, Any],
) -> dict[str, float]:
    values: list[dict[str, float]] = []
    beta = float(recruiter["beta"])
    candidates_by_field = _fields(candidates)
    field_ids = sorted(candidates_by_field)
    for index, mission in enumerate(_mission_rows(config, "drift")):
        field_id = field_ids[index % len(field_ids)]
        field_rows = candidates_by_field[field_id]
        first, second, _score = _select_pair(field_rows, public_pairs, mission, config, beta)
        intact = _evaluate_pair(
            first,
            second,
            mission,
            private_agents,
            private_pairs,
            config,
            salt="w3-06:intact",
        )
        first_success = _evaluate_individual(
            first, mission, private_agents, config, salt="w3-06:first"
        )
        second_success = _evaluate_individual(
            second, mission, private_agents, config, salt="w3-06:second"
        )
        member_loss = max(first_success, second_success)
        best_individual = _select_individual(field_rows, mission, config)
        best_individual_success = _evaluate_individual(
            best_individual,
            mission,
            private_agents,
            config,
            salt="w3-06:best-individual",
        )
        values.append(
            {
                "intact": intact,
                "member_loss": member_loss,
                "best_individual": best_individual_success,
            }
        )
    return {
        "intact_mean_success": statistics.mean(item["intact"] for item in values),
        "intact_vs_best_individual": statistics.mean(
            item["intact"] - item["best_individual"] for item in values
        ),
        "member_loss_mean_success": statistics.mean(item["member_loss"] for item in values),
        "member_loss_degradation": statistics.mean(
            item["intact"] - item["member_loss"] for item in values
        ),
        "member_loss_vs_best_individual": statistics.mean(
            item["member_loss"] - item["best_individual"] for item in values
        ),
    }
