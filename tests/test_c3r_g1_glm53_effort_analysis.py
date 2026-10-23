"""Offline three-effort summary tests; never call a model provider."""

from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest

from resonance_world.c3r_g1_model_boundary import ModelChoiceCompletion


def _load(file: str):
    scripts = Path(__file__).resolve().parents[1] / "scripts"
    spec = importlib.util.spec_from_file_location(
        file.replace(".py", ""), scripts / file,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class FakePort:
    def complete_prompt(self, _prompt: str) -> ModelChoiceCompletion:
        return ModelChoiceCompletion(
            output="A", model_id="glm-5.3", physical_sends_reported=1,
            prompt_tokens_reported=100, completion_tokens_reported=11,
            reasoning_tokens_reported=8, finish_reason="stop",
        )


def _three(tmp_path: Path) -> tuple[Path, ...]:
    runner = _load("run_c3r_g1_fourth_crossed_live.py")
    paths = []
    for effort in ("low", "high", "max"):
        folder = tmp_path / effort
        folder.mkdir(mode=0o700)
        outcome = runner.run_crossed_live(
            run_id=f"g1-model-comparison-{effort}-20261023",
            workspace=folder, target_seed=os.urandom(32),
            port_factory=FakePort, reasoning_effort=effort,
            max_workers=2,
        )
        path = tmp_path / f"{effort}.json"
        path.write_text(json.dumps(outcome), encoding="utf-8")
        paths.append(path)
    return tuple(paths)


def test_three_effort_summary_complete_and_privacy_preserving(tmp_path: Path):
    analyzer = _load("analyze_c3r_g1_glm53_efforts.py")
    result = analyzer.analyze(_three(tmp_path))
    assert result["planned_logical_attempts"] == 120
    assert result["physical_sends_reserved"] == 120
    assert result["same_public_tasks_reused"] is True
    assert result["private_target_assignments_paired_across_efforts"] is False
    assert result["scientific_acceptance"] is False
    for effort in ("low", "high", "max"):
        report = result["models"][effort]
        assert report["source"]["attempts"] == 16
        assert report["qualification"]["attempts"] == 24
        assert report["qualification"]["valid_answer_count"] == 24
        assert report["qualification"]["latency_reporting_rows"] == 24
        assert report["qualification_by_arm"]["learned"]["prescribed"] == 8
        assert report["qualification_by_arm"]["neutral"]["accepted"] == 8
        assert report["source"]["reported_usage"][
            "reasoning_tokens_reported"
        ]["observed_sum"] == 16 * 8
    public = json.dumps(result)
    assert "records" not in public
    assert "choice_sha256" not in public
    assert "private_target_seed" not in public


def test_rejects_duplicate_effort_or_wrong_plan(tmp_path: Path):
    analyzer = _load("analyze_c3r_g1_glm53_efforts.py")
    paths = list(_three(tmp_path))
    with pytest.raises(ValueError, match="cohort metadata"):
        analyzer.analyze((paths[0], paths[0], paths[2]))
    data = json.loads(paths[1].read_text())
    data["plan_digest"] = "0" * 64
    paths[1].write_text(json.dumps(data))
    with pytest.raises(ValueError, match="different public task plans"):
        analyzer.analyze(tuple(paths))


def test_rejects_missing_attempt_or_grade_mutation(tmp_path: Path):
    analyzer = _load("analyze_c3r_g1_glm53_efforts.py")
    paths = list(_three(tmp_path))
    data = json.loads(paths[0].read_text())
    data["records"] = data["records"][:-1]
    paths[0].write_text(json.dumps(data))
    with pytest.raises(ValueError, match="40 retained"):
        analyzer.analyze(tuple(paths))
    data = json.loads(paths[1].read_text())
    arm = next(row for row in data["records"] if row["stage"] == "qualification"
               and row["arm"] == "learned")
    arm["correct"] = not arm["correct"]
    paths[1].write_text(json.dumps(data))
    with pytest.raises(ValueError, match="reported arm grade"):
        analyzer.analyze(tuple(paths))
