"""Offline negative and end-to-end tests for terminal-only longitudinal G1."""

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
    name = "c3r_g1_terminal_retention_test"
    spec = importlib.util.spec_from_file_location(
        name, scripts / "run_c3r_g1_terminal_retention_live.py",
    )
    assert spec and spec.loader
    instance = importlib.util.module_from_spec(spec)
    sys.modules[name] = instance
    spec.loader.exec_module(instance)
    return instance


def _workspace(tmp_path: Path) -> Path:
    root = tmp_path / "private"
    root.mkdir(mode=0o700)
    return root


class Model:
    def complete_prompt(self, prompt: str) -> ModelChoiceCompletion:
        capsule = re.search(r"Procedure capsule: ([AB]{3})", prompt)
        assert capsule is not None
        payload = json.loads(prompt.split("Public input: ", 1)[1].splitlines()[0])
        family = "arithmetic" if "k1" in payload else "text"
        module = _load()
        return ModelChoiceCompletion(
            output=module._execute(family, payload, capsule.group(1)),
            model_id="glm-5.3", physical_sends_reported=1,
            prompt_tokens_reported=70, completion_tokens_reported=9,
            reasoning_tokens_reported=7, finish_reason="stop",
        )


class DeadModel:
    def complete_prompt(self, _prompt: str):
        raise TimeoutError("private provider body must not leak")


def test_terminal_grade_only_source_and_two_retention_processes(tmp_path: Path):
    m = _load()
    root = _workspace(tmp_path)
    run_id = "terminal-3step-longitudinal-20261023-a"
    source = m.run_source(root, run_id, Model, workers=3)
    assert source["source_slots_prescribed"] == 56
    assert 8 <= source["source_sends_reserved"] <= 56
    assert source["source_accepted"] == source["source_sends_reserved"]
    assert source["source_not_sent"] == 56-source["source_sends_reserved"]
    assert source["eligible_contexts"] == 8
    folder = m._run_dir(root, run_id)
    manifest = m._read(folder, "manifest.json")
    capsules = m._read(folder, "capsules.json")
    assert len(capsules["learned_policies"]) == 8
    assert len({u["context_id"] for u in manifest["units"]}) == 8
    for unit in manifest["units"]:
        assert len(unit["holdout_tasks"]) == 2
        assert unit["holdout_tasks"]["retention1"] != (
            unit["holdout_tasks"]["retention2"]
        )
        assert all(
            len(unit[code]) == 3 for code in (
                "private_target", "fresh_policy", "neutral_policy"
            )
        )
        saved = next(c["policy"] for c in capsules["learned_policies"]
                     if c["unit_id"] == unit["unit_id"])
        assert saved == unit["private_target"]
    for name in ("manifest.json", "source.json", "capsules.json"):
        assert (folder / name).stat().st_mode & 0o077 == 0

    second_interpreter = _load()
    first = second_interpreter.run_retention(
        root, run_id, "retention1", Model, workers=3,
    )
    third_interpreter = _load()
    second = third_interpreter.run_retention(
        root, run_id, "retention2", Model, workers=3,
    )
    for wave in (first, second):
        assert wave["physical_holdout_reservations"] == 24
        assert wave["qualification_by_arm"]["learned"]["correct"] == 8
        assert wave["qualification_by_arm"]["learned"]["accepted"] == 8
        assert wave["qualification_by_arm"]["fresh"]["prescribed"] == 8
        assert wave["qualification_by_arm"]["neutral"]["prescribed"] == 8
        assert wave["equal_capacity_and_independent_uniform_control_capsules"]
        assert wave["chronological_elapsed_time_proven"] is False
        assert wave["scientific_acceptance"] is False
        assert wave["status_counts"] == {"accepted": 24}
        assert len(wave["qualification_rows_redacted"]) == 24
        assert all("private_target" not in row and "answer" not in row
                   for row in wave["qualification_rows_redacted"])
        report = json.dumps(wave)
        assert "probe_tasks" not in report
        assert "holdout_tasks" not in report
        assert "private_target" not in report
        assert "source_rows" not in report
    assert first["wave_order"] == 1
    assert second["wave_order"] == 2
    assert first["qualification_rows_redacted"][0]["index"] == 56
    assert second["qualification_rows_redacted"][-1]["index"] == 103
    assert m._read(folder, "retention1-terminal.json")["wave"] == "retention1"
    assert m._read(folder, "retention2-terminal.json")["wave"] == "retention2"


def test_retention2_cannot_run_before_retention1(tmp_path: Path):
    m = _load()
    root = _workspace(tmp_path)
    run_id = "terminal-before-earlier-20261023-b"
    m.run_source(root, run_id, Model)
    with pytest.raises(FileNotFoundError):
        m.run_retention(root, run_id, "retention2", Model)
    folder = m._run_dir(root, run_id)
    assert not (folder / "retention2-start.json").exists()
    assert not list(folder.glob("send-8[0-9].json"))


def test_terminal_only_feedback_never_reveals_step_grades(tmp_path: Path):
    m = _load()
    root = _workspace(tmp_path)
    run_id = "terminal-only-feedback-20261023-c"
    m.run_source(root, run_id, Model)
    folder = m._run_dir(root, run_id)
    source = m._read(folder, "source.json")["source_rows"]
    assert len(source) == 56
    assert all("step" not in row for row in source)
    assert all("correct" in row for row in source)
    assert not any("private_target" in row for row in source)
    for unit in m._read(folder, "manifest.json")["units"]:
        rows = [r for r in source if r["unit_id"] == unit["unit_id"]]
        assert [r["candidate"] for r in rows] == unit["candidate_order"][:7]
        policy = m._unit_decision(rows, unit["candidate_order"])
        assert policy == unit["private_target"]


def test_failed_source_skips_its_three_arms_in_both_waves(tmp_path: Path):
    m = _load()
    root = _workspace(tmp_path)
    run_id = "terminal-failed-source-20261023-d"
    source = m.run_source(root, run_id, DeadModel)
    assert source["source_sends_reserved"] == 56
    assert source["eligible_contexts"] == 0
    one = m.run_retention(root, run_id, "retention1", DeadModel)
    two = m.run_retention(root, run_id, "retention2", DeadModel)
    assert one["physical_holdout_reservations"] == 0
    assert two["physical_holdout_reservations"] == 0
    assert one["status_counts"] == {"not_sent": 24}
    assert two["status_counts"] == {"not_sent": 24}
    assert "private provider body" not in json.dumps(one)
    assert "private provider body" not in json.dumps(two)


def test_tampered_capsule_prevents_both_retention_sessions(tmp_path: Path):
    m = _load()
    root = _workspace(tmp_path)
    run_id = "terminal-tamper-20261023-e"
    m.run_source(root, run_id, Model)
    folder = m._run_dir(root, run_id)
    capsule = m._read(folder, "capsules.json")
    first = capsule["learned_policies"][0]
    first["policy"] = "AAA" if first["policy"] != "AAA" else "BBB"
    (folder / "capsules.json").write_text(json.dumps(capsule))
    with pytest.raises(ValueError, match="integrity"):
        m.run_retention(root, run_id, "retention1", Model)
    assert not (folder / "retention1-start.json").exists()


def test_frozen_run_cannot_dispatch_duplicate_attempts(tmp_path: Path):
    m = _load()
    root = _workspace(tmp_path)
    run_id = "terminal-no-retry-20261023-f"
    m.run_source(root, run_id, Model)
    with pytest.raises(FileExistsError):
        m.run_source(root, run_id, Model)
    m.run_retention(root, run_id, "retention1", Model)
    with pytest.raises(FileExistsError):
        m.run_retention(root, run_id, "retention1", Model)
    m.run_retention(root, run_id, "retention2", Model)
    with pytest.raises(FileExistsError):
        m.run_retention(root, run_id, "retention2", Model)


def test_control_distribution_is_independent_and_balanced_in_expectation():
    m = _load()
    manifest = m._manifest("terminal-null-controls-20261023-g")
    assert len(manifest["units"]) == 8
    for family in m.FAMILIES:
        group = [u for u in manifest["units"] if u["family"] == family]
        assert len(group) == 4
        for step in range(3):
            assert sum(u["private_target"][step] == "A" for u in group) == 2
    for u in manifest["units"]:
        assert u["fresh_policy"] in m.CODES
        assert u["neutral_policy"] in m.CODES
        assert u["candidate_order"] and set(u["candidate_order"]) == set(m.CODES)
        assert len(set(u["candidate_order"])) == 8
        assert len(u["probe_tasks"]) == 7
    # Since controls are sampled independently from a uniform eight-code
    # set, their *pre-outcome* chance of full equality is 1/8 each.
    assert 1 / len(m.CODES) == .125


def test_offline_command_does_not_dispatch(capsys):
    m = _load()
    for phase in ("source", "retention1", "retention2"):
        assert m.main(["--phase", phase,
                       "--run-id", "terminal-offline-20261023-h"]) == 0
        assert json.loads(capsys.readouterr().out)["status"] == (
            "offline_zero_sends"
        )
