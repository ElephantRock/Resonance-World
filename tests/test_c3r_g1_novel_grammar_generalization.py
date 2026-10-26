"""Offline tests for the novel grammar generalization harness.

Covers: family determinism and 32-way unambiguity, novel-vocabulary
disclosure, induction/execution prompt structure per arm, holdout
correctness evaluation, and write-once slot discipline. No network.
"""

from __future__ import annotations

import itertools
import os
import random
from pathlib import Path

import pytest

from scripts.c3r_g1_novel_grammar_families import (
    _execute,
    _grammar,
    _task,
)
from scripts.run_c3r_g1_novel_grammar_generalization_live import (
    _exec_prompt,
    _holdout_correct,
    _induce_prompt,
    _manifest,
    _SlotGuard,
)


def test_novel_families_deterministic_and_unambiguous() -> None:
    rng = random.Random(20261026)
    for family in ("digits", "rotate"):
        for _ in range(12):
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


def test_novel_grammars_do_not_reuse_prior_family_vocabulary() -> None:
    digits, rotate = _grammar("digits"), _grammar("rotate")
    for grammar in (digits, rotate):
        assert "multiply 5" not in grammar  # arithmetic family op
        assert "multiply 3" not in grammar
        assert "prefix lowercase q" not in grammar  # text family op
        assert "uppercase B:lowercase" not in grammar
    assert "add a" not in digits and "subtract c" not in digits
    assert "rotate the string left by 2" in rotate


def test_manifest_units_and_programs() -> None:
    manifest = _manifest("run-novel-001")
    assert len(manifest["units"]) == 8
    families = [unit["family"] for unit in manifest["units"]]
    assert families.count("digits") == 4
    assert families.count("rotate") == 4
    for unit in manifest["units"]:
        program = unit["private_program"]
        assert len(program) == 5 and set(program) <= {"A", "B"}
        assert unit["control_fresh"] != unit["control_neutral"]
        assert len(unit["source_tasks"]) == 2
        assert set(unit["holdouts"]) == {"wave1", "wave2"}


def test_induce_prompt_carries_two_examples_and_grammar() -> None:
    manifest = _manifest("run-novel-002")
    unit = manifest["units"][0]
    prompt = _induce_prompt(unit)
    assert unit["family"] in prompt or "Step1" in prompt
    assert "FIVE letters" in prompt
    import json as _json

    for example in unit["source_tasks"]:
        assert _json.dumps(example, sort_keys=True)[:6] in prompt
    # The correct outputs must be the TRUE program's outputs.
    for example in _json.loads(
        prompt.split("Correct training examples: ")[1].split("\n")[0]
    ):
        assert example["correct_final_output"] == _execute(
            unit["family"], example["input"], unit["private_program"]
        )


def test_exec_prompt_arm_variants(tmp_path: Path) -> None:
    manifest = _manifest("run-novel-003")
    unit = manifest["units"][0]
    capsule = unit["private_program"]

    learned = _exec_prompt("learned", unit, capsule, "wave1")
    raw = _exec_prompt("raw", unit, capsule, "wave1")
    fresh = _exec_prompt("fresh", unit, unit["control_fresh"], "wave1")

    assert f"Procedure capsule: {capsule}" in learned
    assert "training examples" not in learned
    assert "Corrected training examples" in raw
    assert "no procedure capsule" in raw
    assert "Procedure capsule:" in fresh
    assert "training examples" not in fresh
    # The learned capsule and the raw examples derive from the SAME truth.
    for example in unit["source_tasks"]:
        assert _execute(unit["family"], example, capsule) == _execute(
            unit["family"], example, unit["private_program"]
        )


def test_holdout_correct_separates_true_from_wrong(tmp_path: Path) -> None:
    manifest = _manifest("run-novel-004")
    for unit in manifest["units"]:
        truth = _execute(
            unit["family"], unit["holdouts"]["wave1"], unit["private_program"]
        )
        assert _holdout_correct(
            unit["family"], unit, "wave1", truth
        ) is True
        wrong = next(
            candidate
            for candidate in (
                _execute(unit["family"], unit["holdouts"]["wave1"], code)
                for code in ("A" * 5, "B" * 5)
            )
            if candidate != truth
        )
        assert _holdout_correct(unit["family"], unit, "wave1", wrong) is False


def test_slot_guard_write_once_discipline(tmp_path: Path) -> None:
    """Linux/CI only: the private-run _write_once path is POSIX by design."""

    if os.name == "nt":
        pytest.skip("POSIX-only private workspace primitives")

    guard = _SlotGuard(tmp_path, "run-novel-005", "wave1", 8)
    guard.reserve(0, "prompt-0")
    guard.reserve(1, "prompt-1")
    with pytest.raises(FileExistsError):
        guard.reserve(0, "prompt-0-duplicate")
    assert guard.count == 2
    files = sorted(path.name for path in tmp_path.glob("send-*.json"))
    assert files == ["send-wave1-00.json", "send-wave1-01.json"]
