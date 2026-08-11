from __future__ import annotations

import json
from pathlib import Path

from resonance_world.w1_transfer import (
    run_discovery_holdout,
    run_replication,
    run_training,
)


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def _dataset(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    fields = [
        "w1-source-seed-101",
        "w1-source-seed-202",
        "w1-source-seed-303",
        "w1-source-seed-404",
        "w1-source-seed-505",
        "w1-source-seed-707",
        "w1-source-seed-808",
        "w1-source-seed-909",
    ]
    candidates = []
    capsules = []
    for field_index, field_id in enumerate(fields):
        for rank in range(4):
            agent_id = f"a-{field_index}-{rank}"
            candidates.append(
                {
                    "agent_id": agent_id,
                    "checkpoint_id": f"cp-{field_index}",
                    "field_id": field_id,
                    "seed": field_index,
                    "source_evidence_sha256": "a" * 64,
                    "public_features": {
                        "bid_count": 12.0 + rank,
                        "bid_win_rate": 0.05 + 0.10 * rank,
                        "completed_tasks": float(rank + 1),
                        "home_success_rate": 0.35 + 0.15 * rank,
                        "mean_bid_confidence": 0.4 + 0.1 * rank,
                        "request_count": 3.0,
                        "skill_concentration": 0.4 + 0.15 * rank,
                        "skill_entropy": 0.9 - 0.2 * rank,
                        "task_domain_concentration": 0.4 + 0.15 * rank,
                        "win_share": 0.03 + 0.04 * rank,
                    },
                }
            )
            capsules.append(
                {
                    "agent_id": agent_id,
                    "checkpoint_id": f"cp-{field_index}",
                    "field_id": field_id,
                    "intrinsic_state_sha256": "b" * 64,
                    "practice_by_skill": {
                        "alpha": rank * rank + rank,
                        "beta": rank * rank + rank,
                    },
                }
            )
    candidates_path = tmp_path / "candidates.jsonl"
    capsules_path = tmp_path / "capsules.jsonl"
    _write_jsonl(candidates_path, candidates)
    _write_jsonl(capsules_path, capsules)

    config = {
        "training_fields": fields[:3],
        "discovery_holdout_fields": fields[3:5],
        "replication_fields": fields[5:],
        "trials_per_agent": 120,
        "selected_per_field": 1,
        "destination_law": {
            "base_success_probability": 0.38,
            "practice_gain": 0.14,
            "maximum_success_probability": 0.90,
        },
        "families": {
            "alias_a": [
                {"task": "x", "requirements": {"alpha": 1.0}},
                {"task": "y", "requirements": {"beta": 1.0}},
            ],
            "shift_25": [
                {"task": "xy25", "requirements": {"alpha": 0.75, "beta": 0.25}}
            ],
            "shift_50": [
                {"task": "xy50", "requirements": {"alpha": 0.5, "beta": 0.5}}
            ],
            "replication_b": [
                {"task": "yx", "requirements": {"alpha": 0.4, "beta": 0.6}}
            ],
        },
        "adaptation": {"family": "shift_50", "trials": 24},
    }
    config_path = tmp_path / "config.json"
    _write_json(config_path, config)

    campaign = {
        "decision_gates": {
            "w1_04_min_selected_lift": 0.0,
            "w1_04_min_rank_correlation": 0.0,
            "w1_07_min_selected_lift": 0.0,
            "w1_07_min_positive_fields": 1,
            "w1_07_min_rank_correlation": 0.0,
        }
    }
    campaign_path = tmp_path / "campaign.json"
    _write_json(campaign_path, campaign)
    return candidates_path, capsules_path, config_path, campaign_path


def test_w1_model_freezes_before_holdout_and_replicates(tmp_path: Path) -> None:
    candidates, capsules, config, campaign = _dataset(tmp_path)
    train_dir = tmp_path / "train"
    train_summary = run_training(candidates, capsules, config, train_dir)
    model_path = train_dir / "w1-04-frozen-model.json"
    model = json.loads(model_path.read_text())

    assert model["frozen_before_discovery_holdout"] is True
    assert "practice_by_skill" not in json.dumps(model, sort_keys=True)
    assert train_summary["training_agent_count"] == 12

    holdout_dir = tmp_path / "holdout"
    holdout = run_discovery_holdout(
        candidates, capsules, config, model_path, campaign, holdout_dir
    )
    assert holdout["model_sha256"] == model["model_sha256"]
    assert (holdout_dir / "w1-05-domain-shift.json").is_file()
    assert (holdout_dir / "w1-06-summary.json").is_file()

    replication_dir = tmp_path / "replication"
    replication = run_replication(
        candidates, capsules, config, model_path, campaign, replication_dir
    )
    assert replication["model_sha256"] == model["model_sha256"]
    assert replication["replication_agent_count"] == 12


def test_training_is_deterministic(tmp_path: Path) -> None:
    candidates, capsules, config, _ = _dataset(tmp_path)
    first = run_training(candidates, capsules, config, tmp_path / "first")
    second = run_training(candidates, capsules, config, tmp_path / "second")
    assert first == second
    assert (tmp_path / "first" / "w1-04-frozen-model.json").read_bytes() == (
        tmp_path / "second" / "w1-04-frozen-model.json"
    ).read_bytes()
