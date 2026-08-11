"""Build W3 public individual/pair evidence and private swarm capsules."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path
from typing import Any


def _read_csv(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open(newline="", encoding="utf-8") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> str:
    payload = b"".join(_canonical_bytes(row) + b"\n" for row in rows)
    path.write_bytes(payload)
    return hashlib.sha256(payload).hexdigest()


def _as_bool(value: str) -> bool:
    return value.strip().lower() in {"t", "true", "1", "yes"}


def _as_float(value: str) -> float:
    return float(value) if value.strip() else 0.0


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _entropy(counts: Counter[str], domain_count: int) -> float:
    total = sum(counts.values())
    if total <= 0 or domain_count <= 1:
        return 0.0
    value = 0.0
    for count in counts.values():
        if count <= 0:
            continue
        probability = count / total
        value -= probability * math.log(probability)
    return value / math.log(domain_count)


def _pair_key(first: str, second: str) -> tuple[str, str]:
    return tuple(sorted((first, second)))  # type: ignore[return-value]


def _collaboration_band(successes: int) -> str:
    if successes >= 3:
        return "strong"
    if successes >= 1:
        return "observed"
    return "none"


def export_sources(
    runs_path: str | Path,
    outcomes_path: str | Path,
    tasks_path: str | Path,
    bids_path: str | Path,
    destination: str | Path,
) -> dict[str, Any]:
    """Export W3 public phenotypes/edges while keeping intrinsic state private."""

    runs = _read_csv(runs_path)
    outcomes = _read_csv(outcomes_path)
    tasks = _read_csv(tasks_path)
    bids = _read_csv(bids_path)
    if not runs:
        raise ValueError("runs.csv is empty")

    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)

    outcomes_by_run: dict[str, list[dict[str, str]]] = defaultdict(list)
    tasks_by_run: dict[str, list[dict[str, str]]] = defaultdict(list)
    bids_by_run: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in outcomes:
        outcomes_by_run[row["run_id"]].append(row)
    for row in tasks:
        tasks_by_run[row["run_id"]].append(row)
    for row in bids:
        bids_by_run[row["run_id"]].append(row)

    candidates: list[dict[str, Any]] = []
    capsules: list[dict[str, Any]] = []
    pair_edges: list[dict[str, Any]] = []
    pair_private: list[dict[str, Any]] = []
    source_fields: list[dict[str, Any]] = []
    seen_seeds: set[int] = set()

    for run in sorted(runs, key=lambda row: int(row["seed"])):
        run_id = run["run_id"]
        seed = int(run["seed"])
        if seed in seen_seeds:
            raise ValueError(f"duplicate seed: {seed}")
        seen_seeds.add(seed)
        if run.get("arm_label") != "immortal_control":
            raise ValueError(f"unexpected source arm: {run.get('arm_label')}")

        environment = json.loads(run["environment"])
        skills = [str(item) for item in environment.get("domains", [])]
        expected_agents = int(environment.get("agents", 0))
        cycles = int(environment.get("cycles", 0))
        if not skills or expected_agents <= 1 or cycles <= 0:
            raise ValueError("source environment missing domains/agents/cycles")

        run_outcomes = sorted(
            outcomes_by_run[run_id], key=lambda row: int(row["cycle"])
        )
        run_tasks = sorted(tasks_by_run[run_id], key=lambda row: row["task_id"])
        run_bids = sorted(
            bids_by_run[run_id], key=lambda row: (row["task_id"], row["bidder_agent_id"])
        )
        if len(run_outcomes) != cycles:
            raise ValueError(
                f"seed {seed} outcome count mismatch: expected {cycles}, got {len(run_outcomes)}"
            )

        population = {
            row["winner_agent_id"] for row in run_outcomes if row["winner_agent_id"]
        }
        population.update(
            row["requester_agent_id"] for row in run_tasks if row["requester_agent_id"]
        )
        population.update(
            row["bidder_agent_id"] for row in run_bids if row["bidder_agent_id"]
        )
        if len(population) != expected_agents:
            raise ValueError(
                f"seed {seed} population mismatch: expected {expected_agents}, "
                f"observed {len(population)}"
            )

        field_id = f"w3-source-seed-{seed}"
        source_digest = _sha256(
            {"run": run, "outcomes": run_outcomes, "tasks": run_tasks, "bids": run_bids}
        )
        source_fields.append(
            {
                "field_id": field_id,
                "run_id": run_id,
                "seed": seed,
                "source_evidence_sha256": source_digest,
            }
        )

        outcome_by_agent: dict[str, list[dict[str, str]]] = defaultdict(list)
        bid_by_agent: dict[str, list[dict[str, str]]] = defaultdict(list)
        task_by_requester: dict[str, list[dict[str, str]]] = defaultdict(list)
        for row in run_outcomes:
            outcome_by_agent[row["winner_agent_id"]].append(row)
        for row in run_bids:
            bid_by_agent[row["bidder_agent_id"]].append(row)
        for row in run_tasks:
            task_by_requester[row["requester_agent_id"]].append(row)

        for agent_id in sorted(population):
            won = outcome_by_agent[agent_id]
            agent_bids = bid_by_agent[agent_id]
            requested = task_by_requester[agent_id]
            successes = [row for row in won if _as_bool(row["success"])]
            skill_counts = Counter(row["required_skill"] for row in won)
            success_skill_counts = Counter(row["required_skill"] for row in successes)
            ranked_success_skills = sorted(
                success_skill_counts,
                key=lambda skill: (-success_skill_counts[skill], skill),
            )
            win_count = len(won)
            bid_count = len(agent_bids)
            candidate = {
                "agent_id": agent_id,
                "field_id": field_id,
                "public_features": {
                    "bid_count": float(bid_count),
                    "bid_win_rate": win_count / bid_count if bid_count else 0.0,
                    "completed_tasks": float(win_count),
                    "home_success_rate": len(successes) / win_count if win_count else 0.0,
                    "mean_bid_confidence": _mean(
                        [_as_float(row["confidence"]) for row in agent_bids]
                    ),
                    "request_count": float(len(requested)),
                    "skill_concentration": (
                        max(skill_counts.values()) / win_count if win_count else 0.0
                    ),
                    "skill_entropy": _entropy(skill_counts, len(skills)),
                    "win_share": win_count / cycles,
                },
                "public_mission_profile": {
                    "dominant_success_skill": (
                        ranked_success_skills[0] if ranked_success_skills else None
                    ),
                    "secondary_success_skill": (
                        ranked_success_skills[1] if len(ranked_success_skills) > 1 else None
                    ),
                },
            }
            if "practice_by_skill" in json.dumps(candidate, sort_keys=True):
                raise AssertionError("private practice leaked into public candidate")
            candidates.append(candidate)
            capsules.append(
                {
                    "agent_id": agent_id,
                    "field_id": field_id,
                    "practice_by_skill": {
                        skill: int(skill_counts.get(skill, 0)) for skill in skills
                    },
                }
            )

        requester_by_task = {row["task_id"]: row["requester_agent_id"] for row in run_tasks}
        interaction_counts: Counter[tuple[str, str]] = Counter()
        success_counts: Counter[tuple[str, str]] = Counter()
        for row in run_outcomes:
            requester = requester_by_task.get(row["task_id"])
            winner = row["winner_agent_id"]
            if not requester or not winner or requester == winner:
                continue
            key = _pair_key(requester, winner)
            interaction_counts[key] += 1
            if _as_bool(row["success"]):
                success_counts[key] += 1

        for first, second in combinations(sorted(population), 2):
            key = _pair_key(first, second)
            interactions = int(interaction_counts.get(key, 0))
            successful = int(success_counts.get(key, 0))
            edge = {
                "agent_a": first,
                "agent_b": second,
                "field_id": field_id,
                "public_relationship": {
                    "collaboration_band": _collaboration_band(successful),
                    "observed_interaction": interactions > 0,
                    "repeated_success": successful >= 2,
                },
            }
            if "coordination_exposure" in json.dumps(edge, sort_keys=True):
                raise AssertionError("private coordination leaked into public pair edge")
            pair_edges.append(edge)
            pair_private.append(
                {
                    "agent_a": first,
                    "agent_b": second,
                    "coordination_exposure": successful,
                    "field_id": field_id,
                    "interaction_count": interactions,
                }
            )

    candidates.sort(key=lambda row: (row["field_id"], row["agent_id"]))
    capsules.sort(key=lambda row: (row["field_id"], row["agent_id"]))
    pair_edges.sort(key=lambda row: (row["field_id"], row["agent_a"], row["agent_b"]))
    pair_private.sort(key=lambda row: (row["field_id"], row["agent_a"], row["agent_b"]))
    source_fields.sort(key=lambda row: row["field_id"])

    candidate_sha = _write_jsonl(destination / "candidates.jsonl", candidates)
    capsule_sha = _write_jsonl(destination / "capsules.private.jsonl", capsules)
    edge_sha = _write_jsonl(destination / "pair-edges.jsonl", pair_edges)
    pair_private_sha = _write_jsonl(destination / "pair-state.private.jsonl", pair_private)
    _write_json(destination / "source-fields.json", source_fields)
    summary = {
        "agent_count": len(candidates),
        "candidate_sha256": candidate_sha,
        "capsule_sha256": capsule_sha,
        "field_count": len(source_fields),
        "pair_edge_count": len(pair_edges),
        "pair_edge_sha256": edge_sha,
        "pair_private_sha256": pair_private_sha,
        "seeds": sorted(seen_seeds),
    }
    _write_json(destination / "w3-01-source-summary.json", summary)
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("runs", type=Path)
    parser.add_argument("outcomes", type=Path)
    parser.add_argument("tasks", type=Path)
    parser.add_argument("bids", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args(argv)
    summary = export_sources(args.runs, args.outcomes, args.tasks, args.bids, args.output)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
