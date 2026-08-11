from __future__ import annotations

import json
from pathlib import Path

from resonance_world.w0_campaign import run_cohort
from tests.test_resonance_field_artifacts import write_artifacts


def prepare_field(root: Path, artifact_name: str, run_id: str, seed: int) -> None:
    artifact_dir = root / artifact_name
    artifact_dir.mkdir(parents=True)
    write_artifacts(artifact_dir)
    experiment_path = artifact_dir / "experiment.json"
    summary = json.loads(experiment_path.read_text(encoding="utf-8"))
    summary.update(
        {
            "run_id": run_id,
            "seed": seed,
            "code_sha": "abc123",
            "ablation": "full",
            "agents": 2,
        }
    )
    experiment_path.write_text(
        json.dumps(summary, sort_keys=True), encoding="utf-8"
    )


def write_manifest(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "cohort_id": "test-cohort",
                "source_repository": "ElephantRock/Resonance-Field",
                "expected_agents_per_field": 2,
                "fields": [
                    {
                        "field_id": "field-a",
                        "seed": 101,
                        "run_id": "run-a",
                        "artifact_name": "artifact-a",
                        "code_sha": "abc123",
                        "ablation": "full",
                    },
                    {
                        "field_id": "field-b",
                        "seed": 202,
                        "run_id": "run-b",
                        "artifact_name": "artifact-b",
                        "code_sha": "abc123",
                        "ablation": "full",
                    },
                    {
                        "field_id": "field-c",
                        "seed": 303,
                        "run_id": "run-c",
                        "artifact_name": "artifact-c",
                        "code_sha": "abc123",
                        "ablation": "full",
                    },
                ],
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )


def test_three_field_cohort_is_deterministic(tmp_path: Path) -> None:
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir()
    prepare_field(artifact_root, "artifact-a", "run-a", 101)
    prepare_field(artifact_root, "artifact-b", "run-b", 202)
    prepare_field(artifact_root, "artifact-c", "run-c", 303)
    manifest = tmp_path / "manifest.json"
    write_manifest(manifest)

    output_a = tmp_path / "output-a"
    output_b = tmp_path / "output-b"
    first = run_cohort(manifest, artifact_root, output_a)
    second = run_cohort(manifest, artifact_root, output_b)

    assert first == second
    assert first["field_count"] == 3
    assert first["total_agents"] == 6
    assert first["passport_count"] == 6
    assert first["evidence_reference_count"] > 0
    assert first["evidence_digest_count"] > 0

    for filename in ("cohort-summary.json", "field-registry.json", "passports.jsonl"):
        assert (output_a / filename).read_bytes() == (output_b / filename).read_bytes()


def test_cohort_rejects_wrong_run_identity(tmp_path: Path) -> None:
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir()
    prepare_field(artifact_root, "artifact-a", "actual-run", 101)
    prepare_field(artifact_root, "artifact-b", "run-b", 202)
    prepare_field(artifact_root, "artifact-c", "run-c", 303)
    manifest = tmp_path / "manifest.json"
    write_manifest(manifest)

    try:
        run_cohort(manifest, artifact_root, tmp_path / "output")
    except ValueError as exc:
        assert "run mismatch" in str(exc)
    else:
        raise AssertionError("cohort should reject a run identity mismatch")
