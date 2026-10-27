"""Offline tests for the interactive acquisition & execution fidelity pilot.

Pure-logic tests (families, prompts, send classification) run on every
platform. The full session-flow test (run_c1/run_c2_group/run_execute)
requires the POSIX private-workspace validator and runs on CI ubuntu.
No network anywhere: model ports are faked.
"""

from __future__ import annotations

import itertools
import json
import os
import random
from pathlib import Path

import pytest

from scripts.c3r_g1_interactive_fidelity_families import (
    FAMILIES,
    _execute,
    _grammar,
    _task,
)
from scripts.run_c3r_g1_interactive_fidelity_live import (
    _execute_prompt,
    _induce_prompt,
    _manifest,
    _raw_prompt,
    _revise_prompt,
)


def test_families_deterministic_and_unambiguous() -> None:
    rng = random.Random(20261026)
    for family in FAMILIES:
        for _ in range(30):
            task = _task(rng, family)
            codes = [
                "".join(bits) for bits in itertools.product("AB", repeat=5)
            ]
            outputs = [_execute(family, task, code) for code in codes]
            assert len(set(outputs)) == 32, (family, task)
            assert all(
                _execute(family, task, code) == output
                for code, output in zip(codes, outputs, strict=False)
            )


def test_families_do_not_reuse_prior_vocabulary() -> None:
    for family in FAMILIES:
        grammar = _grammar(family)
        assert "multiply 5" not in grammar and "multiply 3" not in grammar
        assert "prefix lowercase q" not in grammar
        assert "swap the two middle digits" not in grammar
        assert "rotate the string" not in grammar


def test_bracket_flip_step_is_visible() -> None:
    task = {"value": "<<><>"}
    flip_on = _execute("bracket", task, "AAAAA")
    flip_off = _execute("bracket", task, "BAAAA")
    assert flip_on != flip_off  # step1 must matter


def test_modpair_order_step_is_visible() -> None:
    task = {"a": 23, "b": 91}
    asc = _execute("modpair", task, "AAAAA")
    desc = _execute("modpair", task, "BAAAA")
    assert asc != desc


def test_manifest_eight_units_four_groups() -> None:
    manifest = _manifest("run-fidelity-manifest", 3)
    assert len(manifest["units"]) == 8
    assert sorted({unit["group"] for unit in manifest["units"]}) == [0, 1, 2, 3]
    families = [unit["family"] for unit in manifest["units"]]
    assert families.count("bracket") == 4
    assert families.count("modpair") == 4
    assert manifest["feedback_rounds"] == 3


# -- prompt structure ---------------------------------------------------------


def _unit() -> dict:
    manifest = _manifest("run-fidelity-prompts", 3)
    return manifest["units"][0]


def test_induce_prompt_structure() -> None:
    unit = _unit()
    prompt = _induce_prompt(unit)
    assert "FIVE letters" in prompt
    assert "Operations:" in prompt
    examples_text = prompt.split("Correct training examples: ")[1].split("\n")[0]
    examples = json.loads(examples_text)
    assert len(examples) == 2
    for example in examples:
        assert example["correct_final_output"] == _execute(
            unit["family"], example["input"], unit["private_program"]
        )


def test_revise_prompt_reports_own_outputs_and_passfail() -> None:

    unit = _manifest("run-fidelity-revise", 3)["units"][0]
    proposal = "A" * 5
    outcomes = [
        {
            "task_input": unit["source_tasks"][0],
            "produced": "produced-one",
            "correct": False,
        },
        {
            "task_input": unit["source_tasks"][1],
            "produced": "produced-two",
            "correct": True,
        },
    ]
    prompt = _revise_prompt(unit, proposal, outcomes)
    assert proposal in prompt
    assert "produced-one" in prompt and "produced-two" in prompt
    # The CORRECT outputs are never disclosed in feedback.
    for task in unit["source_tasks"]:
        assert _execute(unit["family"], task, unit["private_program"]) not in prompt


def test_invalid_round_does_not_vacuously_end_interaction(tmp_path: Path) -> None:
    """Regression: an invalid round-1 answer produced an empty outcome list
    and `all([])` was True - aborting the interaction after one malformed
    round. The loop must keep the interaction alive instead."""

    if os.name == "nt":
        pytest.skip("POSIX-only _run_dir validator")
    from scripts.run_c3r_g1_interactive_fidelity_live import (
        _manifest,
        _run_dir,
        run_c2_group,
    )

    run_id = "fidelity-invalid-round"
    root = _run_dir(tmp_path, run_id)
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    manifest = _manifest(run_id, 3)
    (root / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
    )
    workspace = tmp_path / "workspace"
    workspace.mkdir(mode=0o700)
    os.chmod(workspace, 0o700)

    answers = ["not-a-valid-capsule", "ABAAB"]  # malformed, then valid
    calls = {"n": 0}

    def factory():
        from resonance_world.c3r_g1_model_boundary import ModelChoiceCompletion

        class FakePort:
            model_id = "glm-5.3"

            def complete_prompt(self, prompt: str):
                answer = answers[min(calls["n"], len(answers) - 1)]
                calls["n"] += 1
                return ModelChoiceCompletion(
                    output=answer, model_id="glm-5.3", finish_reason="stop"
                )

        return FakePort()

    summary = run_c2_group(
        tmp_path, "fidelity-invalid-round", 0, "key", workers=1,
        feedback_rounds=3, port_factory=factory,
    )
    row = summary["rows"][0]
    assert row["rounds_used"] >= 2  # malformed round did not end the loop
    assert row["capsule"] == "ABAAB"


def test_execution_prompt_contains_supplied_capsule() -> None:
    unit = _unit()
    prompt = _execute_prompt(unit, "ABBAB", "wave1")
    assert "Procedure capsule: ABBAB" in prompt
    assert json.dumps(unit["holdouts"]["wave1"], sort_keys=True) in prompt


def test_raw_prompt_contains_examples_not_capsule() -> None:
    unit = _unit()
    prompt = _raw_prompt(unit, "wave2")
    assert "Procedure capsule" not in prompt
    assert "Corrected training examples" in prompt
    for task in unit["source_tasks"]:
        assert json.dumps(task, sort_keys=True)[1:-1] in prompt




# -- session flows (POSIX private-workspace validator; CI ubuntu) -------------


class _FakePort:
    model_id = "glm-5.3"

    def __init__(self, answer: str):
        self._answer = answer

    def complete_prompt(self, prompt: str):
        from resonance_world.c3r_g1_model_boundary import ModelChoiceCompletion

        return ModelChoiceCompletion(
            output=self._answer, model_id="glm-5.3", finish_reason="stop"
        )


@pytest.mark.skipif(os.name == "nt", reason="POSIX-only _run_dir validator")
def test_session_flows_c1_c2_execute(tmp_path: Path) -> None:
    from scripts.run_c3r_g1_interactive_fidelity_live import (
        run_c1,
        run_c2_group,
        run_execute,
    )

    run_id = "fidelity-flow-001"
    workspace = tmp_path / "workspace"
    workspace.mkdir(mode=0o700)
    os.chmod(workspace, 0o700)

    summary_c1 = run_c1(
        workspace, run_id, "key", workers=2, feedback_rounds=3,
        port_factory=lambda: _FakePort("BBBBA"),
    )
    assert summary_c1["sends"] == 8
    assert len(summary_c1["rows"]) == 8

    summary_c2 = run_c2_group(
        workspace, run_id, 0, "key", workers=1, feedback_rounds=3,
        port_factory=lambda: _FakePort("ABAAB"),
    )
    assert summary_c2["sends"] <= 6
    for row in summary_c2["rows"]:
        assert row["rounds_used"] >= 1
        assert row["capsule"] is not None

    for wave in ("wave1", "wave2"):
        summary_c3 = run_execute(
            workspace, run_id, "C3", wave, "key", workers=2,
            port_factory=lambda: _FakePort("9rq_rll"),
        )
        assert summary_c3["sends"] == 8
        summary_c4 = run_execute(
            workspace, run_id, "C4", wave, "key", workers=2,
            port_factory=lambda: _FakePort("9rq_rll"),
        )
        assert summary_c4["sends"] == 8
