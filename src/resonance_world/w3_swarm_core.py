"""Core scoring and selection primitives for W3 swarm recruitment."""

from __future__ import annotations

import hashlib
import json
import math
import statistics
from itertools import combinations
from pathlib import Path
from typing import Any


def _read_json(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain an object")
    return value


def _read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"{path} contains a non-object row")
            rows.append(value)
    return rows


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _sha256(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def _uniform(*parts: object) -> float:
    payload = "|".join(str(part) for part in parts).encode()
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big") / 2**64


def _agent_key(row: dict[str, Any]) -> tuple[str, str]:
    return str(row["field_id"]), str(row["agent_id"])


def _pair_key(field_id: str, first: str, second: str) -> tuple[str, str, str]:
    agent_a, agent_b = sorted((first, second))
    return field_id, agent_a, agent_b


def _fields(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(str(row["field_id"]), []).append(row)
    for field_rows in grouped.values():
        field_rows.sort(key=lambda item: str(item["agent_id"]))
    return grouped


def _filter_fields(rows: list[dict[str, Any]], allowed: list[str]) -> list[dict[str, Any]]:
    wanted = set(allowed)
    result = [row for row in rows if str(row["field_id"]) in wanted]
    found = {str(row["field_id"]) for row in result}
    if found != wanted:
        raise ValueError(f"missing expected fields: {sorted(wanted - found)}")
    return result


def _requirements(mission: dict[str, Any]) -> dict[str, float]:
    values = {str(key): float(value) for key, value in mission["requirements"].items()}
    if sum(values.values()) <= 0:
        raise ValueError("mission requirements must have positive total weight")
    return values


def _general_score(candidate: dict[str, Any]) -> float:
    features = candidate["public_features"]
    experience = min(1.0, float(features["completed_tasks"]) / 12.0)
    return (
        0.35 * float(features["home_success_rate"])
        + 0.20 * float(features["bid_win_rate"])
        + 0.15 * float(features["mean_bid_confidence"])
        + 0.10 * float(features["skill_concentration"])
        + 0.10 * (1.0 - float(features["skill_entropy"]))
        + 0.10 * experience
    )


def _mission_fit(
    candidate: dict[str, Any], mission: dict[str, Any], config: dict[str, Any]
) -> float:
    requirements = _requirements(mission)
    profile = candidate["public_mission_profile"]
    dominant = profile.get("dominant_success_skill")
    secondary = profile.get("secondary_success_skill")
    weights = config["recruiter"]
    return (
        float(weights["dominant_fit_weight"])
        * float(requirements.get(str(dominant), 0.0))
        + float(weights["secondary_fit_weight"])
        * float(requirements.get(str(secondary), 0.0))
    )


def _individual_score(
    candidate: dict[str, Any], mission: dict[str, Any], config: dict[str, Any]
) -> float:
    alpha = float(config["recruiter"]["individual_alpha"])
    return _general_score(candidate) + alpha * _mission_fit(
        candidate, mission, config
    )


def _pair_competence_score(
    first: dict[str, Any], second: dict[str, Any], mission: dict[str, Any], config: dict[str, Any]
) -> float:
    requirements = _requirements(mission)
    profiles = [first["public_mission_profile"], second["public_mission_profile"]]
    covered: set[str] = set()
    for profile in profiles:
        for key in ("dominant_success_skill", "secondary_success_skill"):
            value = profile.get(key)
            if value is not None:
                covered.add(str(value))
    coverage = sum(requirements.get(skill, 0.0) for skill in covered) / sum(requirements.values())
    individual = (
        _individual_score(first, mission, config) + _individual_score(second, mission, config)
    ) / 2.0
    complementarity = 1.0 if (
        profiles[0].get("dominant_success_skill") != profiles[1].get("dominant_success_skill")
    ) else 0.0
    return individual + float(config["recruiter"]["coverage_weight"]) * coverage + float(
        config["recruiter"]["complementarity_weight"]
    ) * complementarity


def _relationship_score(edge: dict[str, Any], config: dict[str, Any]) -> float:
    public = edge["public_relationship"]
    band = str(public["collaboration_band"])
    weights = config["recruiter"]["relationship_band_scores"]
    value = float(weights[band])
    if bool(public["repeated_success"]):
        value += float(config["recruiter"]["repeated_success_bonus"])
    return value


def _practice(capsule: dict[str, Any]) -> dict[str, float]:
    return {
        str(skill): float(value)
        for skill, value in dict(capsule["practice_by_skill"]).items()
    }


def _index_private(
    candidates: list[dict[str, Any]],
    capsules: list[dict[str, Any]],
    pair_edges: list[dict[str, Any]],
    pair_state: list[dict[str, Any]],
) -> tuple[
    dict[tuple[str, str], dict[str, Any]],
    dict[tuple[str, str, str], dict[str, Any]],
    dict[tuple[str, str, str], dict[str, Any]],
]:
    private_agents = {_agent_key(row): row for row in capsules}
    if {_agent_key(row) for row in candidates} != set(private_agents):
        raise ValueError("candidate/capsule identities do not match")
    public_pairs = {
        _pair_key(str(row["field_id"]), str(row["agent_a"]), str(row["agent_b"])): row
        for row in pair_edges
    }
    private_pairs = {
        _pair_key(str(row["field_id"]), str(row["agent_a"]), str(row["agent_b"])): row
        for row in pair_state
    }
    if set(public_pairs) != set(private_pairs):
        raise ValueError("public/private pair identities do not match")
    public_text = json.dumps({"candidates": candidates, "pairs": pair_edges}, sort_keys=True)
    if "practice_by_skill" in public_text or "coordination_exposure" in public_text:
        raise ValueError("private W3 state leaked into public evidence")
    return private_agents, public_pairs, private_pairs


def _combined_practice(first: dict[str, float], second: dict[str, float]) -> dict[str, float]:
    skills = set(first) | set(second)
    return {skill: max(first.get(skill, 0.0), second.get(skill, 0.0)) for skill in skills}


def _base_probability(
    practice: dict[str, float], mission: dict[str, Any], config: dict[str, Any]
) -> float:
    law = config["destination_law"]
    requirements = _requirements(mission)
    total = sum(requirements.values())
    signal = sum(
        (weight / total) * math.sqrt(max(0.0, practice.get(skill, 0.0)))
        for skill, weight in requirements.items()
    )
    return min(
        float(law["maximum_success_probability"]),
        float(law["base_success_probability"]) + float(law["practice_gain"]) * signal,
    )


def _team_probability(
    first: dict[str, float],
    second: dict[str, float],
    coordination_exposure: float,
    mission: dict[str, Any],
    config: dict[str, Any],
) -> float:
    law = config["destination_law"]
    base = _base_probability(_combined_practice(first, second), mission, config)
    bonus = float(law["coordination_gain"]) * math.sqrt(max(0.0, coordination_exposure))
    bonus = min(float(law["maximum_coordination_bonus"]), bonus)
    return min(
        float(law["team_maximum_success_probability"]),
        max(0.0, base + bonus - float(law["team_overhead_penalty"])),
    )


def _sample_probability(probability: float, *, identity: str, salt: str, trials: int) -> float:
    successes = sum(
        _uniform("resonance-world-w3", salt, identity, trial) < probability
        for trial in range(trials)
    )
    return successes / trials


def _pair_candidates(
    field_rows: list[dict[str, Any]],
    public_pairs: dict[tuple[str, str, str], dict[str, Any]],
) -> list[tuple[dict[str, Any], dict[str, Any], dict[str, Any]]]:
    field_id = str(field_rows[0]["field_id"])
    output: list[tuple[dict[str, Any], dict[str, Any], dict[str, Any]]] = []
    for first, second in combinations(field_rows, 2):
        key = _pair_key(field_id, str(first["agent_id"]), str(second["agent_id"]))
        output.append((first, second, public_pairs[key]))
    return output


def _select_individual(
    field_rows: list[dict[str, Any]], mission: dict[str, Any], config: dict[str, Any]
) -> dict[str, Any]:
    return max(
        field_rows,
        key=lambda row: (_individual_score(row, mission, config), str(row["agent_id"])),
    )


def _select_pair(
    field_rows: list[dict[str, Any]],
    public_pairs: dict[tuple[str, str, str], dict[str, Any]],
    mission: dict[str, Any],
    config: dict[str, Any],
    beta: float,
    *,
    shuffled_relationships: dict[tuple[str, str, str], float] | None = None,
) -> tuple[dict[str, Any], dict[str, Any], float]:
    ranked: list[tuple[float, str, dict[str, Any], dict[str, Any]]] = []
    field_id = str(field_rows[0]["field_id"])
    for first, second, edge in _pair_candidates(field_rows, public_pairs):
        key = _pair_key(field_id, str(first["agent_id"]), str(second["agent_id"]))
        relationship = (
            shuffled_relationships[key]
            if shuffled_relationships is not None
            else _relationship_score(edge, config)
        )
        score = _pair_competence_score(first, second, mission, config) + beta * relationship
        identity = f"{key[1]}::{key[2]}"
        ranked.append((score, identity, first, second))
    score, _identity, first, second = max(ranked, key=lambda row: (row[0], row[1]))
    return first, second, score


def _shuffled_relationships(
    field_rows: list[dict[str, Any]],
    public_pairs: dict[tuple[str, str, str], dict[str, Any]],
    config: dict[str, Any],
) -> dict[tuple[str, str, str], float]:
    field_id = str(field_rows[0]["field_id"])
    pairs = _pair_candidates(field_rows, public_pairs)
    keys = [
        _pair_key(field_id, str(first["agent_id"]), str(second["agent_id"]))
        for first, second, _edge in pairs
    ]
    values = [_relationship_score(edge, config) for _first, _second, edge in pairs]
    if values:
        shift = int(config["recruiter"]["shuffle_offset"]) % len(values)
        values = values[shift:] + values[:shift]
    return dict(zip(keys, values, strict=True))


def _mission_rows(config: dict[str, Any], family: str) -> list[dict[str, Any]]:
    rows = config["families"].get(family)
    if not isinstance(rows, list) or not rows:
        raise ValueError(f"missing mission family: {family}")
    return rows


def _mean_delta(rows: list[dict[str, Any]], first: str, second: str) -> float:
    return statistics.mean(float(row[first]) - float(row[second]) for row in rows)


def _field_deltas(rows: list[dict[str, Any]], baseline: str) -> dict[str, float]:
    grouped: dict[str, list[float]] = {}
    for row in rows:
        grouped.setdefault(str(row["field_id"]), []).append(
            float(row["swarm_success"]) - float(row[baseline])
        )
    return {field: statistics.mean(values) for field, values in grouped.items()}
