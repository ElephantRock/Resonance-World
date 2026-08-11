from pathlib import Path
from shutil import copytree

from resonance_world.resonance_field_artifacts import ResonanceFieldArtifactAdapter
from tests.test_resonance_field_artifacts import write_artifacts


def test_checkpoint_identity_is_stable_for_same_evidence(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    write_artifacts(source)

    first = ResonanceFieldArtifactAdapter(source, field_id="field-a")
    second = ResonanceFieldArtifactAdapter(source, field_id="field-a")

    assert first.descriptor().checkpoint_id == second.descriptor().checkpoint_id
    assert first.descriptor().checkpoint_id.startswith("run-001@sha256:")
    assert (
        first.passport("agent-02").canonical_bytes()
        == second.passport("agent-02").canonical_bytes()
    )


def test_same_logical_run_with_different_raw_evidence_is_new_checkpoint(
    tmp_path: Path,
) -> None:
    original = tmp_path / "original"
    changed = tmp_path / "changed"
    original.mkdir()
    write_artifacts(original)
    copytree(original, changed)

    tasks_path = changed / "tasks.csv"
    tasks_path.write_text(
        tasks_path.read_text(encoding="utf-8").replace("task-01", "task-opaque-99"),
        encoding="utf-8",
    )

    first = ResonanceFieldArtifactAdapter(original, field_id="field-a")
    second = ResonanceFieldArtifactAdapter(changed, field_id="field-a")

    assert first.descriptor().experiment_id == second.descriptor().experiment_id
    assert first.descriptor().checkpoint_id != second.descriptor().checkpoint_id
    assert first.passport("agent-02").checkpoint_id != second.passport("agent-02").checkpoint_id
