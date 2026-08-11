from __future__ import annotations

import csv
import json
from pathlib import Path

from resonance_world.w3_source_export import export_sources


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def test_source_export_separates_public_pair_edges_from_private_state(tmp_path: Path) -> None:
    environment = {"agents": 3, "domains": ["alpha", "beta"], "cycles": 3}
    _write_csv(
        tmp_path / "runs.csv",
        ["run_id", "seed", "arm_label", "environment", "metrics", "completed_at"],
        [
            {
                "run_id": "run-1",
                "seed": 121,
                "arm_label": "immortal_control",
                "environment": json.dumps(environment),
                "metrics": "{}",
                "completed_at": "now",
            }
        ],
    )
    _write_csv(
        tmp_path / "outcomes.csv",
        [
            "run_id",
            "cycle",
            "task_id",
            "task_domain",
            "required_skill",
            "winner_agent_id",
            "winner_slot",
            "success",
            "winning_price",
            "task_budget",
            "created_at",
        ],
        [
            {
                "run_id": "run-1",
                "cycle": 1,
                "task_id": "t1",
                "task_domain": "x",
                "required_skill": "alpha",
                "winner_agent_id": "a",
                "winner_slot": 0,
                "success": "true",
                "winning_price": 1,
                "task_budget": 2,
                "created_at": "now",
            },
            {
                "run_id": "run-1",
                "cycle": 2,
                "task_id": "t2",
                "task_domain": "x",
                "required_skill": "beta",
                "winner_agent_id": "b",
                "winner_slot": 1,
                "success": "true",
                "winning_price": 1,
                "task_budget": 2,
                "created_at": "now",
            },
            {
                "run_id": "run-1",
                "cycle": 3,
                "task_id": "t3",
                "task_domain": "x",
                "required_skill": "alpha",
                "winner_agent_id": "a",
                "winner_slot": 0,
                "success": "true",
                "winning_price": 1,
                "task_budget": 2,
                "created_at": "now",
            },
        ],
    )
    _write_csv(
        tmp_path / "tasks.csv",
        ["run_id", "task_id", "requester_agent_id"],
        [
            {"run_id": "run-1", "task_id": "t1", "requester_agent_id": "b"},
            {"run_id": "run-1", "task_id": "t2", "requester_agent_id": "a"},
            {"run_id": "run-1", "task_id": "t3", "requester_agent_id": "c"},
        ],
    )
    bids = []
    for task_id in ("t1", "t2", "t3"):
        for agent in ("a", "b", "c"):
            bids.append(
                {
                    "run_id": "run-1",
                    "task_id": task_id,
                    "bidder_agent_id": agent,
                    "price": 1,
                    "confidence": 0.5,
                    "status": "submitted",
                }
            )
    _write_csv(
        tmp_path / "bids.csv",
        ["run_id", "task_id", "bidder_agent_id", "price", "confidence", "status"],
        bids,
    )

    output = tmp_path / "output"
    summary = export_sources(
        tmp_path / "runs.csv",
        tmp_path / "outcomes.csv",
        tmp_path / "tasks.csv",
        tmp_path / "bids.csv",
        output,
    )

    assert summary["agent_count"] == 3
    assert summary["pair_edge_count"] == 3
    assert "practice_by_skill" not in (output / "candidates.jsonl").read_text()
    assert "coordination_exposure" not in (output / "pair-edges.jsonl").read_text()
    assert "coordination_exposure" in (output / "pair-state.private.jsonl").read_text()
