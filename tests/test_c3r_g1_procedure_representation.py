"""Offline tests for the procedure representation comparison.

Pure-logic coverage: paired prompts (same task, only the representation
differs), natural-language rendering fidelity to the code's branches,
deterministic unambiguous holdouts, and the cross-process 64-slot
campaign ledger (double dispatch fails visibly; cap enforced).
No network anywhere: model ports are faked.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.c3r_g1_procedure_representation import (
    REPRESENTATIONS,
    WAVES,
    all_programs,
    holdout_task,
    representation_prompt,
)
from scripts.run_c3r_g1_procedure_representation_live import (
    CampaignLedger,
    slot_indices,
)


def test_slot_indices_tile_the_campaign_exactly() -> None:
    seen: list[int] = []
    for representation in REPRESENTATIONS:
        for wave in WAVES:
            for half in ("a", "b"):
                indices = slot_indices(representation, wave, half)
                assert len(indices) == 8
                seen.extend(indices)
    assert sorted(seen) == list(range(64))
    assert len(set(seen)) == 64


def test_campaign_ledger_enforces_cap_and_double_dispatch(tmp_path: Path) -> None:
    ledger = CampaignLedger(tmp_path / "campaign-ledger", "run-repr-001")
    ledger.reserve_block(list(range(64)), "first-dispatch")
    assert ledger.consumed == 64
    with pytest.raises(RuntimeError, match="outside the 64-send cap"):
        ledger.reserve_block([64, 65], "over-budget")
    with pytest.raises(RuntimeError, match="already reserved"):
        ledger.reserve_block([0], "double-dispatch")


def test_holdouts_deterministic_and_unambiguous() -> None:
    for program in all_programs():
        for wave in WAVES:
            for input_index in (0, 1):
                task = holdout_task(
                    program["family"], program["program"], wave, input_index
                )
                again = holdout_task(
                    program["family"], program["program"], wave, input_index
                )
                assert task == again
                codes = [
                    "".join(bits) for bits in __import__("itertools").product(
                        "AB", repeat=5
                    )
                ]
                outputs = [
                    __import__("scripts.c3r_g1_novel_grammar_families",
                               fromlist=["_execute"])._execute(
                        program["family"], task, code
                    )
                    for code in codes
                ]
                assert len(set(outputs)) == 32


def test_representation_prompts_pair_on_the_same_task() -> None:
    program = all_programs()[0]
    task = holdout_task(program["family"], program["program"], "wave1", 0)
    code_prompt = representation_prompt(
        "code", program["family"], program["program"], task
    )
    natural_prompt = representation_prompt(
        "natural", program["family"], program["program"], task
    )
    task_json = json.dumps(task, sort_keys=True)
    assert task_json in code_prompt
    assert task_json in natural_prompt
    assert "Procedure capsule:" in code_prompt
    assert "Procedure capsule" not in natural_prompt
    # The head and domain lines are identical; only the procedure body differs.
    assert code_prompt.splitlines()[0] == natural_prompt.splitlines()[0]


def test_natural_rendering_describes_code_branches() -> None:
    program = all_programs()[2]
    family = program["family"]
    code = program["program"]
    natural = representation_prompt("natural", family, code, {"value": "1234"})
    markers = {
        "digits": {
            0: ("swap the two middle digits", "leave the digit order unchanged"),
            1: ("keep only the first two digits", "keep only the last two digits"),
            2: ("(d+1) mod 10", "(d+9) mod 10"),
            3: ("descending order", "ascending order"),
            4: ("prefix the result", "append the digit count"),
        },
        "rotate": {
            0: ("rotate the string left by 2 characters",
                "rotate the string right by 2 characters"),
            1: ("insert '-' after every second character",
                "insert '_' after every third character"),
            2: ("keep the first 6 characters", "keep the last 6 characters"),
            3: ("swap every adjacent character pair",
                "leave the character order unchanged"),
            4: ("append '9' to the end", "prepend '5' to the beginning"),
        },
    }
    for position, (a_text, b_text) in markers[family].items():
        expected = a_text if code[position] == "A" else b_text
        assert expected in natural, (position, expected)
