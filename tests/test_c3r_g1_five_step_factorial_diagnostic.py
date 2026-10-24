"""Offline factorial GLM-5.3 five-step diagnosis contract and no-replay tests."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

from resonance_world.c3r_g1_model_boundary import ModelChoiceCompletion


def _load():
    scripts = Path(__file__).resolve().parents[1] / "scripts"
    sys.path.insert(0, str(scripts))
    name = "g1_five_step_factorial_diagnostic_test"
    spec = importlib.util.spec_from_file_location(
        name, scripts / "run_c3r_g1_five_step_factorial_diagnostic.py",
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _workspace(tmp_path: Path) -> Path:
    private = tmp_path / "owner"
    private.mkdir(mode=0o700)
    return private


def _correct_policy(prompt: str) -> str:
    m = _load()
    samples = json.loads(
        prompt.split("Correct training examples: ", 1)[1].splitlines()[0]
    )
    family = "arithmetic" if "a" in samples[0]["input"] else "text"
    matches = [
        code for code in m.CODES
        if all(
            _execute_for_test(family, sample["input"], code)
            == sample["correct_final_output"] for sample in samples
        )
    ]
    assert len(matches) == 1
    return matches[0]


def _execute_for_test(family, task, code):
    from run_c3r_g1_model_induced_five_step_live import _execute
    return _execute(family, task, code)


class Port:
    def __init__(self, effort: str, cap: int, behavior: str):
        self.effort = effort
        self.cap = cap
        self.behavior = behavior

    def complete_prompt(self, prompt: str) -> ModelChoiceCompletion:
        target = _correct_policy(prompt)
        if self.behavior == "error" and self.effort == "high" and self.cap == 8192:
            raise TimeoutError("provider secret should not appear in public outputs")
        if self.effort == "low" and self.cap == 4096:
            answer, finish, completion = "", "length", 4096
        elif self.effort == "high" and self.cap == 4096:
            answer, finish, completion = (
                "B" if target[0] == "A" else "A"
            ) + target[1:], "stop", 120
        elif self.effort == "low" and self.cap == 8192:
            answer, finish, completion = target, "stop", 170
        else:
            answer, finish, completion = (
                target if self.behavior != "invalid" else "Answer: " + target
            ), "stop", 300
        return ModelChoiceCompletion(
            output=answer, model_id="glm-5.3",
            physical_sends_reported=1,
            prompt_tokens_reported=150,
            completion_tokens_reported=completion,
            reasoning_tokens_reported=min(completion, 100),
            finish_reason=finish,
        )


def _factory(behavior: str = "normal"):
    return lambda effort, cap: Port(effort, cap, behavior)


def test_four_conditions_same_prompts_and_original_denominators(tmp_path: Path):
    m = _load()
    root = _workspace(tmp_path)
    report = m.run_factorial(
        workspace=root, run_id="g1-five-factorial-test-20261024-01",
        port_factory=_factory(), workers=3,
    )
    assert report["prescribed_logical_attempts"] == 32
    assert report["physical_sends_reserved"] == 32
    assert len(report["records"]) == 32
    assert report["source_only_no_holdout_or_memory_claim"] is True
    assert report["scientific_acceptance"] is False
    for i in range(8):
        subset = report["records"][i*4:(i+1)*4]
        assert len({r["prompt_sha256"] for r in subset}) == 1
        assert len({r["condition"] for r in subset}) == 4
        assert len({r["unit_id"] for r in subset}) == 1
    expected = {
        "low-4096": ("length_exhausted", 0),
        "low-8192": ("valid_correct", 8),
        "high-4096": ("valid_wrong", 0),
        "high-8192": ("valid_correct", 8),
    }
    for condition, (outcome, correct) in expected.items():
        result = report["conditions"][condition]
        assert result["outcome_counts"] == {outcome: 8}
        assert result["prescribed"] == 8
        assert result["reserved_physical_sends"] == 8
        assert result["correct_policy_count"] == correct
        assert result["provider_reported_tokens"]["completion_tokens"][
            "reported_attempts"
        ] == 8
    for row in report["records"]:
        assert "answer" not in row
        assert "private_program" not in row
        assert row["reasoning_tokens"] is not None
    assert "provider secret" not in json.dumps(report)
    run_dir = m._run_dir(root, "g1-five-factorial-test-20261024-01")
    for name in ("manifest.json", "terminal.json"):
        assert (run_dir / name).stat().st_mode & 0o077 == 0
    stored = json.loads((run_dir / "terminal.json").read_text())
    assert len(stored["rows"]) == 32


def test_invalid_format_is_not_conflated_with_length_or_wrong(tmp_path: Path):
    m = _load()
    report = m.run_factorial(
        workspace=_workspace(tmp_path),
        run_id="g1-five-factorial-format-test-20261024",
        port_factory=_factory("invalid"),
    )
    assert report["conditions"]["high-8192"]["outcome_counts"] == {
        "invalid_format": 8
    }
    assert report["conditions"]["high-8192"]["finish_reason_counts"] == {
        "stop": 8
    }


def test_provider_error_is_isolated_without_raw_error_content(tmp_path: Path):
    m = _load()
    report = m.run_factorial(
        workspace=_workspace(tmp_path),
        run_id="g1-five-factorial-error-test-20261024",
        port_factory=_factory("error"), workers=4,
    )
    assert report["physical_sends_reserved"] == 32
    assert report["conditions"]["high-8192"]["outcome_counts"] == {
        "provider_error": 8
    }
    assert report["conditions"]["low-8192"]["correct_policy_count"] == 8
    assert "provider secret" not in json.dumps(report)


def test_run_id_replay_denied_before_any_additional_dispatch(tmp_path: Path):
    m = _load()
    workspace = _workspace(tmp_path)
    run_id = "g1-five-factorial-no-replay-20261024"
    m.run_factorial(
        workspace=workspace, run_id=run_id, port_factory=_factory(),
    )
    with pytest.raises(FileExistsError):
        m.run_factorial(
            workspace=workspace, run_id=run_id, port_factory=_factory(),
        )


def test_validation_and_default_cli_no_sends(tmp_path: Path, capsys):
    m = _load()
    private = _workspace(tmp_path)
    assert m.main(["--run-id", "g1-offline-five-factorial"]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["status"] == "offline_zero_sends"
    assert output["prescribed_logical_attempts"] == 32
    with pytest.raises(ValueError, match="workers"):
        m.run_factorial(
            workspace=private, run_id="g1-invalid-workers-20261024",
            port_factory=_factory(), workers=0,
        )
    with pytest.raises(ValueError, match="run identity"):
        m.run_factorial(
            workspace=private, run_id="../unsafe",
            port_factory=_factory(),
        )
    assert list(private.iterdir()) == []
