"""Zero-provider acceptance and negative tests for split-session G1 memory."""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest

from resonance_world.c3r_g1_model_boundary import ModelChoiceCompletion


def _load():
    scripts = Path(__file__).resolve().parents[1] / "scripts"
    sys.path.insert(0, str(scripts))
    name = "g1_memory_transfer_real_test"
    spec = importlib.util.spec_from_file_location(
        name, scripts / "run_c3r_g1_persistent_experience_live.py",
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class FakeModel:
    source_count = 0
    holdout_count = 0
    saw_raw_grade = False

    def complete_prompt(self, prompt: str):
        if "Memory capsule: policy=" in prompt:
            FakeModel.holdout_count += 1
            assert "success=true" not in prompt
            assert "success=false" not in prompt
            assert "Past development evidence:" not in prompt
            policy = re.search(r"Memory capsule: policy=([AB?])", prompt)
            assert policy
            choice = policy.group(1)
            if choice == "?":
                choice = "A"
        else:
            FakeModel.source_count += 1
            assert "Memory capsule" not in prompt
            choice = "A"
        return ModelChoiceCompletion(
            output=choice, model_id="glm-5.3",
            physical_sends_reported=1, prompt_tokens_reported=50,
            completion_tokens_reported=5, reasoning_tokens_reported=3,
            finish_reason="stop",
        )


class BrokenModel:
    def complete_prompt(self, _prompt: str):
        raise TimeoutError("never leak raw model provider failures")


def _workspace(tmp_path: Path) -> Path:
    path = tmp_path / "private-store"
    path.mkdir(mode=0o700)
    return path


def test_new_tasks_cross_process_capsule_and_full_grade_comparison(
    tmp_path: Path,
) -> None:
    m = _load()
    path = _workspace(tmp_path)
    name = "g1-experience-novel-20261023-01"
    FakeModel.source_count = 0
    FakeModel.holdout_count = 0
    source = m.run_source(
        workspace=path, run_id=name,
        port_factory=FakeModel, workers=3,
    )
    assert source["source_attempts_reserved"] == 16
    assert source["source_accepted"] == 16
    assert source["eligible_contexts"] == 8
    assert FakeModel.source_count == 16
    folder = m._run_dir(path, name)
    manifest = m._read(folder, "manifest.json")
    capsules = m._read(folder, "experience.json")
    assert set(row["policy"] for row in capsules["capsules"]) == {"A", "B"}
    assert len({u["context_id"] for u in manifest["units"]}) == 8
    assert all(
        source_task["operands"] != unit["tasks"][2]["operands"]
        for unit in manifest["units"] for source_task in unit["tasks"][:2]
    )
    for item in ("manifest.json", "experience.json", "source.json"):
        assert (folder / item).stat().st_mode & 0o077 == 0
    # Re-import under a distinct module identity to simulate the separate
    # qualification interpreter; no in-memory feedback is carried over.
    second = _load()
    result = second.run_holdout(
        workspace=path, run_id=name,
        port_factory=FakeModel, workers=4,
    )
    assert FakeModel.holdout_count == 24
    assert result["holdout_attempts_reserved"] == 24
    assert result["status_counts"] == {"accepted": 24}
    assert result["qualification_by_arm"]["learned"]["correct"] == 8
    assert result["qualification_by_arm"]["fresh"]["correct"] == 4
    assert result["qualification_by_arm"]["neutral"]["prescribed"] == 8
    assert result["raw_development_feedback_in_holdout_prompts"] is False
    assert result["agent_experience_read_from_private_file"] is True
    assert result["scientific_acceptance"] is False
    public = json.dumps(result)
    assert "private_target" not in public
    assert '"source_attempts"' not in public
    assert "Memory capsule: policy" not in public
    assert "source task" not in public
    terminal = second._read(folder, "terminal.json")
    assert len(terminal["holdout"]) == 24


def test_run_id_reuse_cannot_resend_source_or_holdout(
    tmp_path: Path,
) -> None:
    m = _load()
    path = _workspace(tmp_path)
    name = "g1-experience-replay-20261023-02"
    m.run_source(workspace=path, run_id=name, port_factory=FakeModel)
    with pytest.raises(FileExistsError):
        m.run_source(workspace=path, run_id=name, port_factory=BrokenModel)
    m.run_holdout(workspace=path, run_id=name, port_factory=FakeModel)
    with pytest.raises(FileExistsError):
        m.run_holdout(workspace=path, run_id=name, port_factory=BrokenModel)


def test_source_capsule_tampering_blocks_holdout_before_any_send(
    tmp_path: Path,
) -> None:
    m = _load()
    root = _workspace(tmp_path)
    run_id = "g1-experience-tamper-20261023-03"
    m.run_source(workspace=root, run_id=run_id, port_factory=FakeModel)
    folder = m._run_dir(root, run_id)
    capsule = m._read(folder, "experience.json")
    original = capsule["capsules"][0]["policy"]
    capsule["capsules"][0]["policy"] = "B" if original == "A" else "A"
    (folder / "experience.json").write_text(json.dumps(capsule))
    with pytest.raises(ValueError, match="integrity"):
        m.run_holdout(
            workspace=root, run_id=run_id, port_factory=BrokenModel,
        )
    assert not list(folder.glob("send-1[6-9].json"))
    assert not (folder / "holdout-start.json").exists()


def test_failed_sources_never_trigger_holdout_sends(
    tmp_path: Path,
) -> None:
    m = _load()
    root = _workspace(tmp_path)
    run_id = "g1-experience-fail-20261023-04"
    source = m.run_source(
        workspace=root, run_id=run_id, port_factory=BrokenModel,
    )
    assert source["source_attempts_reserved"] == 16
    assert source["eligible_contexts"] == 0
    result = m.run_holdout(
        workspace=root, run_id=run_id, port_factory=BrokenModel,
    )
    assert result["holdout_attempts_reserved"] == 0
    assert result["status_counts"] == {"not_sent": 24}
    assert all(result["qualification_by_arm"][arm]["accepted"] == 0
               for arm in ("learned", "fresh", "neutral"))
    assert "never leak raw" not in json.dumps(result)


def test_invalid_workspace_or_run_id_does_not_dispatch(
    tmp_path: Path,
) -> None:
    m = _load()
    workspace = _workspace(tmp_path)
    with pytest.raises(ValueError, match="run ID"):
        m.run_source(workspace=workspace, run_id="../bad",
                     port_factory=BrokenModel)
    workspace.chmod(0o755)
    with pytest.raises(ValueError, match="private"):
        m.run_source(workspace=workspace, run_id="valid-run-20261023",
                     port_factory=BrokenModel)
    assert not list(workspace.iterdir())


def test_cli_without_live_mode_sends_zero_requests(capsys) -> None:
    m = _load()
    assert m.main(["--phase", "source", "--run-id", "g1-offline-20261023"]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "offline_zero_sends"
    assert m.main(["--phase", "holdout", "--run-id", "g1-offline-20261023"]) == 0
    assert json.loads(capsys.readouterr().out)["prescribed_model_attempts"] == 24
