from __future__ import annotations

import json
from pathlib import Path

from resonance_world.w2_recruitment import calibrate, discover, replicate, synthesize


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))


def _fixture(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    fields = ["t1", "t2", "t3", "h1", "h2", "r1", "r2", "r3"]
    candidates: list[dict[str, object]] = []
    capsules: list[dict[str, object]] = []
    for field in fields:
        for label, dominant, secondary, practice in (
            ("a", "x", "y", {"x": 9, "y": 2}),
            ("b", "y", "x", {"x": 1, "y": 7}),
        ):
            agent_id = f"{field}-{label}"
            candidates.append(
                {
                    "agent_id": agent_id,
                    "checkpoint_id": f"checkpoint-{field}",
                    "field_id": field,
                    "public_features": {
                        "bid_win_rate": 0.55 if label == "a" else 0.45,
                        "completed_tasks": 11.0 if label == "a" else 8.0,
                        "home_success_rate": 0.75 if label == "a" else 0.60,
                        "mean_bid_confidence": 0.70,
                        "skill_concentration": 0.70,
                        "skill_entropy": 0.50,
                    },
                    "public_mission_profile": {
                        "dominant_success_skill": dominant,
                        "secondary_success_skill": secondary,
                    },
                }
            )
            capsules.append(
                {
                    "agent_id": agent_id,
                    "checkpoint_id": f"checkpoint-{field}",
                    "field_id": field,
                    "practice_by_skill": practice,
                }
            )
    candidates_path = tmp_path / "candidates.jsonl"
    capsules_path = tmp_path / "capsules.jsonl"
    _write_jsonl(candidates_path, candidates)
    _write_jsonl(capsules_path, capsules)

    missions = {
        "training_fields": ["t1", "t2", "t3"],
        "discovery_holdout_fields": ["h1", "h2"],
        "replication_fields": ["r1", "r2", "r3"],
        "trials_per_mission": 80,
        "destination_law": {
            "base_success_probability": 0.38,
            "practice_gain": 0.14,
            "maximum_success_probability": 0.90,
        },
        "purpose_built": {
            "response_practice_budget": 1.0,
            "response_compute_cost_per_practice": 1.0,
            "deployment_compute_cost": 12.0,
        },
        "utility": {
            "success_weight": 1.0,
            "response_compute_weight": 0.002,
            "latency_weight": 0.001,
        },
        "recruiter": {
            "alpha_grid": [0.0, 0.5, 1.0],
            "dominant_fit_weight": 1.0,
            "secondary_fit_weight": 0.5,
        },
        "families": {
            "calibration": [{"mission": "cal", "requirements": {"x": 1.0}}],
            "discovery": [{"mission": "disc", "requirements": {"x": 0.8, "y": 0.2}}],
            "abstention": [
                {"mission": "supported", "requirements": {"x": 1.0}, "supported": True},
                {"mission": "unsupported", "requirements": {"z": 1.0}, "supported": False},
            ],
            "drift": [
                {"mission": "a", "requirements": {"x": 1.0}},
                {"mission": "b", "requirements": {"x": 0.7, "y": 0.3}},
                {"mission": "c", "requirements": {"x": 0.5, "y": 0.5}},
            ],
            "replication": [
                {"mission": "rep", "requirements": {"x": 0.75, "y": 0.25}}
            ],
        },
    }
    campaign = {
        "decision_gates": {
            "w2_02_min_completion_lift": 0.0,
            "w2_02_min_positive_fields": 1,
            "w2_03_noninferiority_margin": 0.20,
            "w2_03_min_utility_delta": -1.0,
            "w2_05_min_selective_risk_reduction": 0.0,
            "w2_05_min_supported_coverage": 0.0,
            "w2_07_min_completion_lift": 0.0,
            "w2_07_noninferiority_margin": 0.20,
            "w2_07_min_positive_fields": 1,
            "w2_07_min_coverage": 0.0,
        }
    }
    missions_path = tmp_path / "missions.json"
    campaign_path = tmp_path / "campaign.json"
    _write_json(missions_path, missions)
    _write_json(campaign_path, campaign)
    return candidates_path, capsules_path, missions_path, campaign_path


def test_w2_full_lab_freezes_public_recruiter(tmp_path: Path) -> None:
    candidates, capsules, missions, campaign = _fixture(tmp_path)
    calibration_dir = tmp_path / "calibration"
    calibration = calibrate(candidates, capsules, missions, calibration_dir)
    recruiter_path = calibration_dir / "w2-01-frozen-recruiter.json"
    recruiter_text = recruiter_path.read_text()
    assert calibration["alpha"] in {0.0, 0.5, 1.0}
    assert "practice_by_skill" not in recruiter_text

    discovery_dir = tmp_path / "discovery"
    discovery = discover(
        candidates,
        capsules,
        missions,
        campaign,
        recruiter_path,
        discovery_dir,
    )
    assert discovery["w2_02"]["completion_lift"] > 0
    assert discovery["w2_03"]["recruited_mean_success"] > 0.38

    replication_dir = tmp_path / "replication"
    replication = replicate(
        candidates,
        capsules,
        missions,
        campaign,
        recruiter_path,
        replication_dir,
    )
    assert replication["completion_lift"] > 0

    synthesis = synthesize(
        discovery_dir / "w2-discovery-summary.json",
        replication_dir / "w2-07-summary.json",
        tmp_path / "synthesis",
    )
    assert synthesis["status"] in {
        "replicated_individual_ecological_recruitment",
        "individual_recruitment_not_replicated",
    }
