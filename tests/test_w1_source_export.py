from __future__ import annotations

import csv
import json
from pathlib import Path

from resonance_world.w1_source_export import export_sources


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _fixture(root: Path) -> tuple[Path, Path, Path, Path]:
    environment = {
        "agents": 2,
        "cycles": 4,
        "domains": ["alpha", "beta"],
        "base_success_probability": 0.38,
        "practice_gain": 0.14,
        "maximum_success_probability": 0.90,
    }
    runs = root / "runs.csv"
    outcomes = root / "outcomes.csv"
    tasks = root / "tasks.csv"
    bids = root / "bids.csv"
    _write_csv(
        runs,
        [
            {
                "run_id": "run-101",
                "seed": 101,
                "arm_label": "immortal_control",
                "environment": json.dumps(environment, sort_keys=True),
                "metrics": "{}",
                "completed_at": "2026-08-11T00:00:00+00:00",
            }
        ],
    )
    outcome_rows = []
    task_rows = []
    bid_rows = []
    winners = ["a1", "a1", "a2", "a1"]
    skills = ["alpha", "alpha", "beta", "beta"]
    successes = ["t", "f", "t", "t"]
    for cycle in range(4):
        task_id = f"t{cycle}"
        outcome_rows.append(
            {
                "run_id": "run-101",
                "cycle": cycle,
                "task_id": task_id,
                "task_domain": skills[cycle],
                "required_skill": skills[cycle],
                "winner_agent_id": winners[cycle],
                "winner_slot": 0,
                "success": successes[cycle],
                "winning_price": 8,
                "task_budget": 12,
                "created_at": f"2026-08-11T00:00:0{cycle}+00:00",
            }
        )
        task_rows.append(
            {
                "run_id": "run-101",
                "task_id": task_id,
                "requester_agent_id": "a1" if cycle % 2 == 0 else "a2",
            }
        )
        for agent in ("a1", "a2"):
            bid_rows.append(
                {
                    "run_id": "run-101",
                    "task_id": task_id,
                    "bidder_agent_id": agent,
                    "price": 8,
                    "confidence": 0.7 if agent == "a1" else 0.6,
                    "status": "selected" if agent == winners[cycle] else "rejected",
                }
            )
    _write_csv(outcomes, outcome_rows)
    _write_csv(tasks, task_rows)
    _write_csv(bids, bid_rows)
    return runs, outcomes, tasks, bids


def test_source_export_separates_public_and_private_state(tmp_path: Path) -> None:
    runs, outcomes, tasks, bids = _fixture(tmp_path)
    output = tmp_path / "output"
    summary = export_sources(runs, outcomes, tasks, bids, output)

    assert summary["field_count"] == 1
    assert summary["agent_count"] == 2

    candidates = [json.loads(line) for line in (output / "candidates.jsonl").read_text().splitlines()]
    capsules = [
        json.loads(line) for line in (output / "capsules.private.jsonl").read_text().splitlines()
    ]
    assert "practice_by_skill" not in json.dumps(candidates, sort_keys=True)
    by_agent = {row["agent_id"]: row for row in capsules}
    assert by_agent["a1"]["practice_by_skill"] == {"alpha": 2, "beta": 1}
    assert by_agent["a2"]["practice_by_skill"] == {"alpha": 0, "beta": 1}


def test_source_export_is_idempotent_for_same_evidence(tmp_path: Path) -> None:
    runs, outcomes, tasks, bids = _fixture(tmp_path)
    first = export_sources(runs, outcomes, tasks, bids, tmp_path / "a")
    second = export_sources(runs, outcomes, tasks, bids, tmp_path / "b")
    assert first == second
    for name in (
        "candidates.jsonl",
        "capsules.private.jsonl",
        "source-fields.json",
        "w1-01-summary.json",
    ):
        assert (tmp_path / "a" / name).read_bytes() == (tmp_path / "b" / name).read_bytes()
