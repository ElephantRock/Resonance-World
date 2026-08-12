from __future__ import annotations

import json
from pathlib import Path

import pytest

from resonance_world.w9_calibration_execution import (
    build_prediction_manifest,
    evaluate_prediction_manifest,
    _public_skill_probability,
)


SKILLS = (
    "urban_heat",
    "water_systems",
    "energy_storage",
    "supply_networks",
    "public_health",
    "mobility",
)


def _config() -> dict[str, object]:
    return {
        "field_sha": "field-pin",
        "discovery_seeds": [3611],
        "replication_seeds": [4211],
        "agents_per_field": 12,
        "service_trials": 12,
        "source_loss_budget_pp": 2.0,
        "conservative_z": 1.645,
        "estimator_residual_se_pp": 0.70,
        "principal_context_partner_offset": 1,
        "calibration": {
            "max_mae_pp": 1.0,
            "max_abs_bias_pp": 0.5,
            "min_spearman_rho": 0.60,
            "min_high_cost_safe_rate": 0.90,
            "max_high_cost_underprediction_pp": 1.0,
        },
        "public_estimator": {
            "selector": {
                "home_success_rate": 0.30,
                "bid_win_rate": 0.20,
                "mean_bid_confidence": 0.10,
                "experience": 0.10,
                "dominant_host_fit": 0.20,
                "secondary_host_fit": 0.10,
                "experience_scale": 12.0,
            }
        },
        "source_service_law": {
            "base_success_probability": 0.38,
            "practice_gain": 0.14,
            "maximum_success_probability": 0.90,
        },
        "home_service_missions": [
            {"mission_id": f"home-{skill}", "skill": skill} for skill in SKILLS
        ],
    }


def _write_public_source(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    field_id = "w4-source-seed-3611"
    candidates = []
    for index in range(12):
        dominant = SKILLS[index % len(SKILLS)]
        secondary = SKILLS[(index + 1) % len(SKILLS)]
        candidates.append(
            {
                "agent_id": f"agent-{index:02d}",
                "checkpoint_id": "checkpoint-public",
                "field_id": field_id,
                "public_features": {
                    "bid_count": 12.0,
                    "bid_win_rate": 0.25 + index * 0.01,
                    "completed_tasks": float(2 + index),
                    "home_success_rate": 0.45 + index * 0.02,
                    "mean_bid_confidence": 0.40 + index * 0.01,
                    "request_count": 6.0,
                    "skill_concentration": 0.5,
                    "skill_entropy": 0.8,
                    "task_domain_concentration": 0.5,
                    "win_share": 0.1,
                },
                "public_mission_profile": {
                    "dominant_success_skill": dominant,
                    "secondary_success_skill": secondary,
                },
                "seed": 3611,
                "source_evidence_sha256": f"evidence-{index:02d}",
            }
        )
    (path / "candidates.jsonl").write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in candidates),
        encoding="utf-8",
    )
    (path / "source-fields.json").write_text(
        json.dumps(
            [
                {
                    "checkpoint_id": "checkpoint-public",
                    "environment": {"agents": 12, "cycles": 72, "domains": list(SKILLS)},
                    "field_id": field_id,
                    "run_id": "run-public",
                    "seed": 3611,
                    "source_evidence_sha256": "field-evidence",
                }
            ]
        ),
        encoding="utf-8",
    )


def _write_private_capsules(path: Path) -> None:
    rows = []
    for index in range(12):
        practice = {skill: 0 for skill in SKILLS}
        practice[SKILLS[index % len(SKILLS)]] = 2 + index
        practice[SKILLS[(index + 1) % len(SKILLS)]] = 1 + index // 2
        rows.append(
            {
                "agent_id": f"agent-{index:02d}",
                "checkpoint_id": "checkpoint-public",
                "field_id": "w4-source-seed-3611",
                "intrinsic_state_sha256": f"private-{index:02d}",
                "practice_by_skill": practice,
            }
        )
    (path / "capsules.private.jsonl").write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def test_prepare_materializes_predictions_without_private_capsules(tmp_path: Path) -> None:
    source = tmp_path / "source"
    _write_public_source(source)
    config = _config()

    manifest = build_prediction_manifest(source, config, phase="discovery")

    assert not (source / "capsules.private.jsonl").exists()
    assert manifest["field_count"] == 1
    assert manifest["agent_count"] == 12
    assert manifest["principal_observation_count"] == 24
    assert manifest["interaction_observation_count"] == 132
    assert "practice_by_skill" not in json.dumps(manifest, sort_keys=True)
    assert manifest["manifest_sha256"]


def test_public_skill_probability_reuses_frozen_selector_and_source_range(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    _write_public_source(source)
    candidate = json.loads((source / "candidates.jsonl").read_text().splitlines()[0])

    value = _public_skill_probability(candidate, "urban_heat", _config())

    assert 0.38 <= value <= 0.90
    other = _public_skill_probability(candidate, "public_health", _config())
    assert value > other


def test_evaluate_reads_private_truth_only_after_frozen_manifest(tmp_path: Path) -> None:
    source = tmp_path / "source"
    _write_public_source(source)
    config = _config()
    manifest = build_prediction_manifest(source, config, phase="discovery")
    _write_private_capsules(source)

    result = evaluate_prediction_manifest(source, config, manifest, phase="discovery")

    assert result["field_count"] == 1
    assert result["agent_count"] == 12
    assert result["calibration"]["observation_count"] == 24
    assert result["interaction_diagnostic"]["observation_count"] == 132
    assert len(result["principal_observations"]) == 24
    assert len(result["pairwise_interactions"]) == 132
    assert result["calibration"]["label"] in {
        "calibrated_source_cost_estimator",
        "biased_but_rank_informative",
        "uncalibrated_source_cost_estimator",
    }
    assert "practice_by_skill" not in json.dumps(result, sort_keys=True)
    assert result["result_sha256"]


def test_evaluate_rejects_tampered_prediction_manifest(tmp_path: Path) -> None:
    source = tmp_path / "source"
    _write_public_source(source)
    _write_private_capsules(source)
    config = _config()
    manifest = build_prediction_manifest(source, config, phase="discovery")
    manifest["principal_observations"][0]["predicted_loss_pp"] += 1.0

    with pytest.raises(ValueError, match="digest mismatch"):
        evaluate_prediction_manifest(source, config, manifest, phase="discovery")
