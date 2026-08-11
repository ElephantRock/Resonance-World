"""Build W1 public candidates and private competence capsules from Field evidence."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
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


def _as_bool(value: str) -> bool:
    return value.strip().lower() in {"t", "true", "1", "yes"}


def _as_float(value: str) -> float:
    return float(value) if value.strip() else 0.0


def _entropy(counts: Counter[str], domain_count: int) -> float:
    total = sum(counts.values())
    if total <= 0 or domain_count <= 1:
        return 0.0
    value = 0.0
    for count in counts.values():
        if count <= 0:
            continue
        p = count / total
        value -= p * math.log(p)
    return value / math.log(domain_count)


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> str:
    payload = b"".join(_canonical_bytes(row) + b"\n" for row in rows)
    path.write_bytes(payload)
    return hashlib.sha256(payload).hexdigest()


def export_sources(
    runs_path: str | Path,
    outcomes_path: str | Path,
    tasks_path: str | Path,
    bids_path: str | Path,
    destination: str | Path,
) -> dict[str, Any]:
    """Export public W1-01 evidence and private intrinsic practice capsules."""

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

    source_fields: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []
    capsules: list[dict[str, Any]] = []
    seen_seeds: set[int] = set()

    for run in sorted(runs, key=lambda item: int(item["seed"])):
        run_id = run["run_id"]
        seed = int(run["seed"])
        if seed in seen_seeds:
            raise ValueError(f"duplicate source seed: {seed}")
        seen_seeds.add(seed)
        if run.get("arm_label") != "immortal_control":
            raise ValueError(f"unexpected source arm: {run.get('arm_label')}")

        environment = json.loads(run["environment"])
        if not isinstance(environment, dict):
            raise ValueError("run environment must be an object")
        skills = [str(item) for item in environment.get("domains", [])]
        expected_agents = int(environment.get("agents", 0))
        cycles = int(environment.get("cycles", 0))
        if not skills or expected_agents <= 0 or cycles <= 0:
            raise ValueError("source environment is missing domains/agents/cycles")

        run_outcomes = sorted(
            outcomes_by_run[run_id], key=lambda item: int(item["cycle"])
        )
        run_tasks = sorted(tasks_by_run[run_id], key=lambda item: item["task_id"])
        run_bids = sorted(
            bids_by_run[run_id],
            key=lambda item: (item["task_id"], item["bidder_agent_id"]),
        )
        if len(run_outcomes) != cycles:
            raise ValueError(
                f"seed {seed} outcome count mismatch: expected {cycles}, "
                f"got {len(run_outcomes)}"
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

        evidence_bundle = {
            "run": run,
            "outcomes": run_outcomes,
            "tasks": run_tasks,
            "bids": run_bids,
        }
        evidence_digest = _sha256(evidence_bundle)
        checkpoint_id = f"{run_id}@sha256:{evidence_digest}"
        field_id = f"w1-source-seed-{seed}"
        source_fields.append(
            {
                "checkpoint_id": checkpoint_id,
                "environment": environment,
                "field_id": field_id,
                "run_id": run_id,
                "seed": seed,
                "source_evidence_sha256": evidence_digest,
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
            successes = sum(_as_bool(row["success"]) for row in won)
            skill_counts = Counter(row["required_skill"] for row in won)
            task_domain_counts = Counter(row["task_domain"] for row in won)
            win_count = len(won)
            bid_count = len(agent_bids)
            public_features = {
                "bid_count": float(bid_count),
                "bid_win_rate": win_count / bid_count if bid_count else 0.0,
                "completed_tasks": float(win_count),
                "home_success_rate": successes / win_count if win_count else 0.0,
                "mean_bid_confidence": _mean(
                    [_as_float(row["confidence"]) for row in agent_bids]
                ),
                "request_count": float(len(requested)),
                "skill_concentration": (
                    max(skill_counts.values()) / win_count if win_count else 0.0
                ),
                "skill_entropy": _entropy(skill_counts, len(skills)),
                "task_domain_concentration": (
                    max(task_domain_counts.values()) / win_count if win_count else 0.0
                ),
                "win_share": win_count / cycles,
            }
            agent_evidence = {
                "run": run,
                "outcomes": won,
                "bids": agent_bids,
                "requested_tasks": requested,
            }
            agent_evidence_digest = _sha256(agent_evidence)
            candidate = {
                "agent_id": agent_id,
                "checkpoint_id": checkpoint_id,
                "field_id": field_id,
                "public_features": public_features,
                "seed": seed,
                "source_evidence_sha256": agent_evidence_digest,
            }
            if "practice_by_skill" in json.dumps(candidate, sort_keys=True):
                raise AssertionError("private practice leaked into public candidate")
            candidates.append(candidate)

            practice_by_skill = {skill: int(skill_counts.get(skill, 0)) for skill in skills}
            intrinsic_state = {
                "agent_id": agent_id,
                "checkpoint_id": checkpoint_id,
                "field_id": field_id,
                "practice_by_skill": practice_by_skill,
            }
            capsules.append(
                {
                    **intrinsic_state,
                    "intrinsic_state_sha256": _sha256(intrinsic_state),
                }
            )

    candidates.sort(key=lambda row: (row["field_id"], row["agent_id"]))
    capsules.sort(key=lambda row: (row["field_id"], row["agent_id"]))
    source_fields.sort(key=lambda row: row["field_id"])
    if len(candidates) != len(capsules):
        raise AssertionError("candidate/capsule cardinality mismatch")

    candidate_sha = _write_jsonl(destination / "candidates.jsonl", candidates)
    capsule_sha = _write_jsonl(destination / "capsules.private.jsonl", capsules)
    _write_json(destination / "source-fields.json", source_fields)
    summary = {
        "agent_count": len(candidates),
        "candidate_sha256": candidate_sha,
        "capsule_sha256": capsule_sha,
        "field_count": len(source_fields),
        "seeds": sorted(seen_seeds),
        "source_fields_sha256": _sha256(source_fields),
    }
    _write_json(destination / "w1-01-summary.json", summary)
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
