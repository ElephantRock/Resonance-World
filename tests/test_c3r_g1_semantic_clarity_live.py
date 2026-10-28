"""Offline tests for the G1 semantic clarity campaign.

Pure-logic coverage: the 32-slot plan (disjoint 8-slot session blocks),
the cross-process O_EXCL ledger (cap and double dispatch fail visibly),
deterministic fresh unambiguous rotate-only inputs, the single-variable
design (arm prompts differ ONLY in the step-2 line; everything else
identical including the corrected step-5 '9' branch), an independent
reference re-derivation of the precise join semantics composing to the
evaluator truth, ITT accounting over a faked model port, and a full
offline campaign rehearsal feeding the report verdict. No network.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

import scripts.run_c3r_g1_semantic_clarity_live as clarity
from scripts.c3r_g1_novel_grammar_families import _execute as novel_execute
from scripts.c3r_g1_procedure_representation import (
    WAVES,
    all_programs,
    holdout_task,
)
from scripts.run_c3r_g1_stepwise_execution_live import (
    _campaign_tasks as stepwise_tasks,
)


# --- independent reference implementation (precise join semantics) ---


def _reference_chain(code: str, value: str) -> list[str]:
    states = []
    n = len(value)
    shift = 2 if code[0] == "A" else n - 2
    value = value[shift % n:] + value[: shift % n]
    states.append(value)
    if code[1] == "A":
        value = "-".join(value[i:i + 2] for i in range(0, len(value), 2))
    else:
        value = "_".join(value[i:i + 3] for i in range(0, len(value), 3))
    states.append(value)
    value = value[:6] if code[2] == "A" else value[-6:]
    states.append(value)
    if code[3] == "A":
        chars = list(value)
        for i in range(0, len(chars) - 1, 2):
            chars[i], chars[i + 1] = chars[i + 1], chars[i]
        value = "".join(chars)
    states.append(value)
    value = (value + "9") if code[4] == "A" else ("9" + value)
    states.append(value)
    return states


# --- slot plan and ledger ---


def test_slot_plan_tiles_32_exactly() -> None:
    plan = clarity.slot_plan()
    indices = [row["index"] for row in plan]
    assert sorted(indices) == list(range(32))
    assert len(set(indices)) == 32
    for arm in ("a", "b"):
        for wave in WAVES:
            block = sorted(
                row["index"] for row in plan
                if row["arm"] == arm and row["wave"] == wave
            )
            base = (0 if arm == "a" else 16) + WAVES.index(wave) * 8
            assert block == list(range(base, base + 8))
    a_indices = {row["index"] for row in plan if row["arm"] == "a"}
    assert a_indices == set(range(16))


def test_ledger_enforces_cap_and_double_dispatch(tmp_path: Path) -> None:
    ledger = clarity.ClarityLedger(tmp_path / "clarity-ledger", "run-x")
    for index in range(32):
        ledger.reserve(index, "full-campaign")
    assert ledger.consumed == 32
    with pytest.raises(RuntimeError, match="exceeds the 32-send cap"):
        ledger.reserve(32, "over-budget")
    with pytest.raises(RuntimeError, match="already reserved"):
        ledger.reserve(0, "double-dispatch")


# --- inputs: deterministic, unambiguous, fresh ---


def test_tasks_deterministic_unambiguous_and_fresh() -> None:
    import itertools

    codes = ["".join(bits) for bits in itertools.product("AB", repeat=5)]
    stepwise_inputs = {t["input"] for t in stepwise_tasks()}
    seen = set()
    tasks = clarity._campaign_tasks()
    assert len(tasks) == 16
    for task in tasks:
        assert task["family"] == "rotate"
        again = clarity._task_input(
            task["family"], task["program_id"], task["wave"], task["input_index"]
        )
        assert task["input"] == again
        outputs = {
            novel_execute("rotate", {"value": task["input"]}, code)
            for code in codes
        }
        assert len(outputs) == 32, (task["program_id"], task["wave"])
        assert task["input"] not in stepwise_inputs
        rep_holdouts = {
            holdout_task("rotate", task["program_code"], wave, idx)["value"]
            for wave in WAVES for idx in (0, 1)
        }
        assert task["input"] not in rep_holdouts
        seen.add((task["program_id"], task["wave"], task["input_index"]))
    assert len(seen) == 16


# --- the single-variable design ---


def test_arm_steps_differ_only_in_step2() -> None:
    for program in clarity.rotate_programs():
        ambiguous = clarity.arm_steps("rotate", program["program"], "a")
        precise = clarity.arm_steps("rotate", program["program"], "b")
        assert len(ambiguous) == 5 and len(precise) == 5
        branch = program["program"][1]
        assert ambiguous[1] == clarity.AMBIGUOUS_STEP2[branch]
        assert precise[1] == clarity.PRECISE_STEP2[branch]
        for position in (0, 2, 3, 4):
            assert ambiguous[position] == precise[position]
        # the corrected rotate step-5 branch is inherited from the
        # stepwise renderer and is identical in both arms
        if program["program"][4] == "B":
            assert ambiguous[4] == "Step 5: prepend '9' to the beginning."
            assert precise[4] == ambiguous[4]


def test_prompts_differ_only_in_step2_line() -> None:
    task = clarity._campaign_tasks()[0]
    prompt_a = clarity._build_prompt("rotate", task["steps_ambiguous"],
                                     task["input"])
    prompt_b = clarity._build_prompt("rotate", task["steps_precise"],
                                     task["input"])
    lines_a = prompt_a.splitlines()
    lines_b = prompt_b.splitlines()
    assert len(lines_a) == len(lines_b)
    differing = [
        i for i, (x, y) in enumerate(zip(lines_a, lines_b)) if x != y
    ]
    assert len(differing) == 1
    assert "no separator at the end" in lines_b[differing[0]]
    assert json.dumps({"value": task["input"]}, sort_keys=True) in prompt_a
    assert prompt_a.splitlines()[0] == prompt_b.splitlines()[0]
    assert "Answer with only the final result." in prompt_b


def test_reference_precise_semantics_compose_to_truth() -> None:
    for task in clarity._campaign_tasks():
        chain = _reference_chain(task["program_code"], task["input"])
        assert chain[-1] == task["truth"], (
            task["program_id"], task["wave"], task["input_index"]
        )
        # and the intermediate states are exactly the join semantics the
        # precise step-2 wording describes (no trailing separator)
        separated = chain[1]
        assert not separated.endswith("-") and not separated.endswith("_")


# --- manifest freeze ---


def test_manifest_freezes_and_refuses_drift(tmp_path: Path) -> None:
    manifest = clarity.run_manifest(tmp_path, "run-m1")
    assert len(manifest["tasks"]) == 16
    assert len(manifest["slots"]) == 32
    assert manifest["scientific_acceptance"] is False
    again = clarity.run_manifest(tmp_path, "run-m2")
    assert again["tasks"] == manifest["tasks"]
    path = tmp_path / "clarity-manifest.json"
    tampered = json.loads(path.read_text(encoding="utf-8"))
    tampered["tasks"][0]["input"] = "zzzzzz"
    path.write_text(json.dumps(tampered), encoding="utf-8")
    with pytest.raises(ValueError, match="manifest drift"):
        clarity.run_manifest(tmp_path, "run-m3")
    with pytest.raises(ValueError, match="manifest drift"):
        clarity._load_manifest(tmp_path)


# --- faked model port: ITT accounting and full rehearsal ---


class _FakeCompletion:
    def __init__(self, output: str, finish_reason: str) -> None:
        self.output = output
        self.finish_reason = finish_reason


class _FakePort:
    behavior = None

    def __init__(self, **kwargs) -> None:
        pass

    def complete_prompt(self, prompt: str) -> _FakeCompletion:
        behavior = type(self).behavior
        assert behavior is not None, "fake behavior not configured"
        return behavior(prompt)


@pytest.fixture()
def fake_port(monkeypatch):
    monkeypatch.setattr(clarity, "ZaiStandardModelPort", _FakePort)
    _FakePort.behavior = None
    yield _FakePort
    _FakePort.behavior = None


def _prompt_task(prompt: str) -> tuple[dict, str]:
    """Identify (task, arm) from the prompt: the step-2 line names the arm."""

    tasks = clarity._campaign_tasks()
    value = json.loads(
        re.search(r"New task: (\{.*\})", prompt).group(1)
    )["value"]
    task = next(t for t in tasks if t["input"] == value)
    if any(clarity.PRECISE_STEP2[b] in prompt for b in ("A", "B")):
        arm = "b"
    else:
        arm = "a"
    return task, arm


def test_send_session_itt_paths(fake_port, tmp_path: Path) -> None:
    clarity.run_manifest(tmp_path, "run-s1")
    wrong = {("prog-rotate-00", 0), ("prog-rotate-02", 1)}
    broken = {("prog-rotate-01", 0)}
    unscored = {("prog-rotate-03", 1)}

    def behavior(prompt: str) -> _FakeCompletion:
        task, arm = _prompt_task(prompt)
        key = (task["program_id"], task["input_index"])
        if key in broken:
            raise RuntimeError("ProviderTransportRejected")
        if key in unscored:
            return _FakeCompletion("", "length")
        if key in wrong:
            return _FakeCompletion("000000", "stop")
        return _FakeCompletion(task["truth"], "stop")

    _FakePort.behavior = behavior
    summary = clarity.run_send(tmp_path, "run-s1", "a", "wave1", "test-key")
    rows = {
        (row["program_id"], row["input_index"]): row
        for row in summary["rows"]
    }
    assert summary["sends"] == 8
    assert summary["itt_successes"] == 4
    assert rows[("prog-rotate-00", 0)]["itt_success"] is False
    assert rows[("prog-rotate-00", 0)]["correct"] is False
    assert rows[("prog-rotate-01", 0)]["status"] == "provider_error"
    assert rows[("prog-rotate-03", 1)]["status"] == "unscored"
    assert rows[("prog-rotate-03", 1)]["itt_success"] is False
    ledger = clarity.ClarityLedger(tmp_path / "clarity-ledger", "run-s1")
    assert ledger.consumed == 8


def _run_full_campaign(tmp_path: Path, a_wrong: set, b_wrong: set) -> dict:
    clarity.run_manifest(tmp_path, "run-rehearsal")

    def behavior(prompt: str) -> _FakeCompletion:
        task, arm = _prompt_task(prompt)
        key = (task["program_id"], task["wave"], task["input_index"])
        wrong = a_wrong if arm == "a" else b_wrong
        if key in wrong:
            return _FakeCompletion("000000", "stop")
        return _FakeCompletion(task["truth"], "stop")

    _FakePort.behavior = behavior
    for arm in ("a", "b"):
        for wave in WAVES:
            clarity.run_send(tmp_path, "run-rehearsal", arm, wave, "test-key")
    return clarity.run_report(tmp_path)


def test_full_offline_rehearsal_and_report(fake_port, tmp_path: Path) -> None:
    # boundary MET: b = 16/16, a = 12/16 -> paired exactly +4
    report = _run_full_campaign(
        tmp_path / "met",
        a_wrong={("prog-rotate-00", "wave1", 0), ("prog-rotate-01", "wave2", 1),
                 ("prog-rotate-02", "wave1", 0), ("prog-rotate-03", "wave2", 0)},
        b_wrong=set(),
    )
    assert report["sends_total"] == 32
    assert report["tasks"] == 16
    assert report["a_itt_ambiguous"] == 12
    assert report["b_itt_precise"] == 16
    assert report["paired_b_minus_a"] == 4
    assert report["paired_table"] == {
        "both_correct": 12, "b_only": 4, "a_only": 0, "both_failed": 0,
    }
    assert report["criterion_b_at_least_15_of_16"] is True
    assert report["criterion_paired_diff_at_least_4"] is True
    assert "MET" in report["verdict"]

    # NOT MET: precise arm below 15 despite a large paired gain
    report2 = _run_full_campaign(
        tmp_path / "not-met",
        a_wrong={("prog-rotate-00", "wave1", 0), ("prog-rotate-00", "wave2", 1),
                 ("prog-rotate-01", "wave1", 0)},
        b_wrong={("prog-rotate-02", "wave1", 1), ("prog-rotate-03", "wave2", 0),
                 ("prog-rotate-01", "wave2", 0)},
    )
    assert report2["a_itt_ambiguous"] == 13
    assert report2["b_itt_precise"] == 13
    assert report2["paired_b_minus_a"] == 0
    assert "NOT MET" in report2["verdict"]
    assert "CLOSED" in report2["verdict"]


def test_report_refuses_incomplete_campaign(fake_port, tmp_path: Path) -> None:
    clarity.run_manifest(tmp_path, "run-partial")
    clarity.run_send(tmp_path, "run-partial", "a", "wave1", "test-key")
    with pytest.raises(FileNotFoundError, match="campaign incomplete"):
        clarity.run_report(tmp_path)
