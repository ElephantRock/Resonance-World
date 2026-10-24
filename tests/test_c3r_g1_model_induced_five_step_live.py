"""Offline model-authored five-step policy, restart, no-replay and controls."""

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
    spec = importlib.util.spec_from_file_location(
        "g1_model_induction_five_step_test",
        scripts / "run_c3r_g1_model_induced_five_step_live.py",
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class FakeModel:
    def complete_prompt(self, prompt: str) -> ModelChoiceCompletion:
        module = _load()
        if "Correct training examples:" in prompt:
            assert "private_program" not in prompt
            assert "context_id" not in prompt
            examples = json.loads(
                prompt.split("Correct training examples: ", 1)[1].splitlines()[0]
            )
            family = "arithmetic" if "a" in examples[0]["input"] else "text"
            matches = [
                code for code in module.CODES
                if all(
                    module._execute(family, x["input"], code)
                    == x["correct_final_output"] for x in examples
                )
            ]
            assert len(matches) == 1
            result = matches[0]
        else:
            assert "Correct training examples" not in prompt
            assert "correct_final_output" not in prompt
            code = re.search(r"Procedure capsule: ([AB]{5})", prompt)
            assert code is not None
            task = json.loads(prompt.split("New task: ", 1)[1].splitlines()[0])
            family = "arithmetic" if "a" in task else "text"
            result = module._execute(family, task, code.group(1))
        return ModelChoiceCompletion(
            output=result, model_id="glm-5.3", physical_sends_reported=1,
            prompt_tokens_reported=100, completion_tokens_reported=11,
            reasoning_tokens_reported=8, finish_reason="stop",
        )


class InvalidSource:
    def complete_prompt(self, _prompt):
        return ModelChoiceCompletion(
            output="not-a-code", model_id="glm-5.3",
            physical_sends_reported=1, finish_reason="stop",
        )


class DeadModel:
    def complete_prompt(self, _prompt):
        raise TimeoutError("secret provider exception body")


class WrongInduction(FakeModel):
    def complete_prompt(self, prompt):
        if "Correct training examples:" in prompt:
            return ModelChoiceCompletion(
                output="AAAAA", model_id="glm-5.3",
                physical_sends_reported=1, finish_reason="stop",
            )
        return super().complete_prompt(prompt)


def _workspace(tmp_path: Path) -> Path:
    root = tmp_path / "owned"
    root.mkdir(mode=0o700)
    return root


def test_model_proposal_is_saved_without_repair_then_reused_twice(tmp_path: Path):
    m = _load()
    root = _workspace(tmp_path)
    run_id = "g1-induction-real-contract-20261024-01"
    src = m.run_source(root, run_id, FakeModel)
    assert src["source_prescribed"] == 8
    assert src["physical_source_reservations"] == 8
    assert src["valid_policy_proposals"] == 8
    assert src["policy_match_to_hidden_target"] == 8
    path = m._run_dir(root, run_id)
    manifest = m._read(path, "manifest.json")
    capsule = m._read(path, "capsules.json")
    assert len(capsule["policies"]) == 8
    assert all(len(c["code"]) == 5 for c in capsule["policies"])
    assert all(
        len({m._execute(u["family"], task, c) for c in m.CODES}) == 32
        for u in manifest["units"] for task in (
            *u["source_tasks"], *u["holdouts"].values()
        )
    )
    for name in ("manifest.json", "source.json", "capsules.json"):
        assert (path / name).stat().st_mode & 0o077 == 0
    wave1 = _load().run_retention(root, run_id, "retention1", FakeModel)
    wave2 = _load().run_retention(root, run_id, "retention2", FakeModel)
    for wave in (wave1, wave2):
        assert wave["qualification_prescribed"] == 24
        assert wave["physical_holdout_reservations"] == 24
        assert wave["qualification_by_arm"]["learned"]["correct"] == 8
        assert wave["qualification_by_arm"]["learned"]["accepted"] == 8
        assert wave["qualification_by_arm"]["fresh"]["prescribed"] == 8
        assert wave["qualification_by_arm"]["neutral"]["prescribed"] == 8
        assert wave["status_counts"] == {"accepted": 24}
        assert wave["controls_prior_match_probability"] == 1/32
        assert wave["scientific_acceptance"] is False
        public = json.dumps(wave)
        assert "private_program" not in public
        assert "correct_final_output" not in public
        assert "source_tasks" not in public
        assert "Procedure capsule:" not in public
    assert [row["index"] for row in wave1["qualification_rows_redacted"]] == list(
        range(8, 32)
    )
    assert [row["index"] for row in wave2["qualification_rows_redacted"]] == list(
        range(32, 56)
    )


def test_invalid_policy_source_stops_both_holdout_waves(tmp_path: Path):
    m = _load()
    root = _workspace(tmp_path)
    run = "g1-model-invalid-proposal-20261024-02"
    source = m.run_source(root, run, InvalidSource)
    assert source["valid_policy_proposals"] == 0
    for wave in m.WAVES:
        summary = m.run_retention(root, run, wave, DeadModel)
        assert summary["physical_holdout_reservations"] == 0
        assert summary["status_counts"] == {"not_sent": 24}
        assert all(summary["qualification_by_arm"][arm]["correct"] == 0
                   for arm in m.ARMS)


def test_model_wrong_code_not_corrected_by_agent_controller(tmp_path: Path):
    m = _load()
    root = _workspace(tmp_path)
    run = "g1-model-wrong-but-accepted-20261024-03"
    summary = m.run_source(root, run, WrongInduction)
    assert summary["valid_policy_proposals"] == 8
    private = m._read(m._run_dir(root, run), "manifest.json")
    expected = sum(u["private_program"] == "AAAAA" for u in private["units"])
    assert summary["policy_match_to_hidden_target"] == expected
    capsule = m._read(m._run_dir(root, run), "capsules.json")
    assert {x["code"] for x in capsule["policies"]} == {"AAAAA"}
    qual = m.run_retention(root, run, "retention1", WrongInduction)
    assert qual["physical_holdout_reservations"] == 24
    assert qual["qualification_by_arm"]["learned"]["correct"] == expected


def test_tamper_or_replay_fail_before_holdout_send(tmp_path: Path):
    m = _load()
    root = _workspace(tmp_path)
    run = "g1-model-integrity-and-no-retry-20261024-04"
    m.run_source(root, run, FakeModel)
    with pytest.raises(FileExistsError):
        m.run_source(root, run, DeadModel)
    directory = m._run_dir(root, run)
    with pytest.raises(FileNotFoundError):
        m.run_retention(root, run, "retention2", DeadModel)
    capsule = m._read(directory, "capsules.json")
    capsule["policies"][0]["code"] = "not a policy"
    (directory / "capsules.json").write_text(json.dumps(capsule))
    with pytest.raises(ValueError, match="integrity"):
        m.run_retention(root, run, "retention1", DeadModel)
    assert not (directory / "retention1-start.json").exists()


def test_retention_cannot_replay_same_exclusive_start(tmp_path: Path):
    m = _load()
    root = _workspace(tmp_path)
    run = "g1-model-double-retention-20261024-05"
    m.run_source(root, run, FakeModel)
    m.run_retention(root, run, "retention1", FakeModel)
    with pytest.raises(FileExistsError):
        m.run_retention(root, run, "retention1", DeadModel)
    m.run_retention(root, run, "retention2", FakeModel)
    with pytest.raises(FileExistsError):
        m.run_retention(root, run, "retention2", DeadModel)


def test_balanced_hidden_steps_and_uniform_independent_5bit_controls():
    m = _load()
    manifest = m._manifest("g1-model-five-step-balanced-20261024-06")
    assert len(m.CODES) == 32
    assert len(manifest["units"]) == 8
    for family in m.FAMILIES:
        units = [u for u in manifest["units"] if u["family"] == family]
        for i in range(5):
            assert sum(u["private_program"][i] == "A" for u in units) == 2
        for unit in units:
            assert unit["control_fresh"] in m.CODES
            assert unit["control_neutral"] in m.CODES
            assert len(unit["source_tasks"]) == 2
            assert unit["holdouts"]["retention1"] != unit["holdouts"]["retention2"]
    assert m.main(["--phase", "source", "--run-id", "test-offline-20261024"]) == 0
