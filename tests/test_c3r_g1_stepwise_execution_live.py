"""Offline tests for the G1 stepwise execution fidelity campaign.

Pure-logic coverage: the 96-slot campaign plan (disjoint session blocks,
exact tiling), the cross-process O_EXCL ledger (double dispatch and the
cap fail visibly), deterministic fresh unambiguous inputs, the registered
prompts (single-shot carries the full procedure; step prompts carry one
bare instruction — no doubled "Step N:" prefix), an INDEPENDENT
re-derivation of the five per-family steps whose composition must equal
the evaluator's truth, ITT accounting over a faked model port (all
failure paths preserved in the denominator), and a full offline campaign
rehearsal feeding the report verdict. No network anywhere.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

import scripts.run_c3r_g1_stepwise_execution_live as stepwise
from scripts.c3r_g1_novel_grammar_families import _execute as novel_execute
from scripts.c3r_g1_procedure_representation import (
    WAVES,
    all_programs,
    holdout_task,
)


# --- independent reference implementation of the five natural steps ---


def _reference_step(family: str, code: str, step: int, value: str) -> str:
    """One step, implemented from the natural instruction text alone."""
    if family == "digits":
        if step == 1:
            if code[0] == "A":
                digits = list(value)
                digits[1], digits[2] = digits[2], digits[1]
                value = "".join(digits)
            return value
        if step == 2:
            return value[:2] if code[1] == "A" else value[-2:]
        if step == 3:
            mapping = (lambda d: str((int(d) + 1) % 10)) if code[2] == "A" \
                else (lambda d: str((int(d) + 9) % 10))
            return "".join(mapping(d) for d in value)
        if step == 4:
            return "".join(sorted(value, reverse=(code[3] == "A")))
        if step == 5:
            return (str(len(value)) + value) if code[4] == "A" \
                else (value + str(len(value)))
    else:
        if step == 1:
            n = len(value)
            shift = 2 if code[0] == "A" else n - 2
            return value[shift % n:] + value[: shift % n]
        if step == 2:
            if code[1] == "A":
                return "-".join(
                    value[i:i + 2] for i in range(0, len(value), 2)
                )
            return "_".join(value[i:i + 3] for i in range(0, len(value), 3))
        if step == 3:
            return value[:6] if code[2] == "A" else value[-6:]
        if step == 4:
            if code[3] == "A":
                chars = list(value)
                for i in range(0, len(chars) - 1, 2):
                    chars[i], chars[i + 1] = chars[i + 1], chars[i]
                return "".join(chars)
            return value
        if step == 5:
            return (value + "9") if code[4] == "A" else ("9" + value)
    raise AssertionError("unreachable step")


def _reference_chain(family: str, code: str, value: str) -> list[str]:
    states = []
    for step in range(1, 6):
        value = _reference_step(family, code, step, value)
        states.append(value)
    return states


# --- slot plan and ledger ---


def test_slot_plan_tiles_96_exactly() -> None:
    plan = stepwise.slot_plan()
    indices = [row["index"] for row in plan]
    assert sorted(indices) == list(range(96))
    assert len(set(indices)) == 96
    arm_rows = [row for row in plan if row["arm"] == "a"]
    b_rows = [row for row in plan if row["arm"] == "b"]
    assert len(arm_rows) == 16 and len(b_rows) == 80
    # per-session blocks are disjoint and contiguous where they must be
    for wave in WAVES:
        wave_index = WAVES.index(wave)
        for program in all_programs():
            position = stepwise._program_position(program["program_id"])
            block = stepwise.arm_b_slot_block(wave, position)
            assert block == list(range(16 + (wave_index * 8 + position) * 5,
                                        16 + (wave_index * 8 + position) * 5 + 5))
            assert stepwise.arm_a_slot(wave, position) == wave_index * 8 + position


def test_ledger_enforces_cap_and_double_dispatch(tmp_path: Path) -> None:
    ledger = stepwise.StepwiseLedger(tmp_path / "stepwise-ledger", "run-x")
    ledger.reserve_block(list(range(96)), "full-campaign")
    assert ledger.consumed == 96
    with pytest.raises(RuntimeError, match="exceeds the 96-send cap"):
        ledger.reserve(96, "over-budget")
    with pytest.raises(RuntimeError, match="already reserved"):
        ledger.reserve(0, "double-dispatch")


# --- inputs: deterministic, unambiguous, fresh ---


def test_inputs_deterministic_unambiguous_and_fresh() -> None:
    import itertools

    codes = ["".join(bits) for bits in itertools.product("AB", repeat=5)]
    seen_inputs = set()
    for program in all_programs():
        pid = program["program_id"]
        representation_holdouts = {
            holdout_task(program["family"], program["program"], wave, idx)["value"]
            for wave in WAVES for idx in (0, 1)
        }
        for wave in WAVES:
            value = stepwise._task_input(program["family"], pid, wave)
            again = stepwise._task_input(program["family"], pid, wave)
            assert value == again
            assert value not in representation_holdouts, (pid, wave)
            outputs = {
                novel_execute(program["family"], {"value": value}, code)
                for code in codes
            }
            assert len(outputs) == 32, (pid, wave)
            seen_inputs.add((pid, wave, value))
    assert len(seen_inputs) == 16


def test_reference_steps_compose_to_evaluator_truth() -> None:
    for program in all_programs():
        tasks = [
            t for t in stepwise._campaign_tasks()
            if t["program_id"] == program["program_id"]
        ]
        extras = (
            ["1234", "9090"] if program["family"] == "digits"
            else ["abcdef", "zzzzzz"]
        )
        values = [t["input"] for t in tasks] + extras
        for value in values:
            chain = _reference_chain(
                program["family"], program["program"], value
            )
            truth = novel_execute(
                program["family"], {"value": value}, program["program"]
            )
            assert chain[-1] == truth, (program["program_id"], value)


def test_rotate_step5_b_defect_is_corrected_to_match_evaluator() -> None:
    """Documented apparatus defect: frozen upstream text said '5', the
    frozen evaluator prepends '9'. This campaign renders the correct '9'."""
    from scripts.c3r_g1_procedure_representation import _natural_instructions

    upstream = _natural_instructions("rotate", "AAAAB").splitlines()[4].strip()
    assert upstream == "Step 5: prepend '5' to the beginning."  # frozen defect
    corrected = stepwise._natural_step_instructions("rotate", "AAAAB")[4]
    assert corrected == "Step 5: prepend '9' to the beginning."
    unaffected = stepwise._natural_step_instructions("rotate", "AAAAB"[:-1] + "A")[4]
    assert unaffected == "Step 5: append '9' to the end."
    # every frozen program's rendered steps must compose to its truth
    for task in stepwise._campaign_tasks():
        assert len(task["steps"]) == 5
        chain = _reference_chain(
            task["family"], task["program_code"], task["input"]
        )
        assert chain[-1] == task["truth"], task["program_id"]


# --- prompts ---


def test_single_shot_prompt_carries_full_procedure_and_task() -> None:
    program = all_programs()[0]
    steps = stepwise._natural_step_instructions(
        program["family"], program["program"]
    )
    assert len(steps) == 5
    prompt = stepwise._build_single_shot_prompt(
        program["family"], program["program"], "1234"
    )
    for line in steps:
        assert line in prompt
    assert json.dumps({"value": "1234"}, sort_keys=True) in prompt
    assert "Answer with only the final result." in prompt


def test_step_prompt_embeds_one_bare_instruction() -> None:
    program = all_programs()[4]  # first rotate program
    steps = stepwise._natural_step_instructions(
        program["family"], program["program"]
    )
    bare = stepwise._bare_step_instruction(steps, 3)
    assert not bare.startswith("Step")
    prompt = stepwise._build_step_prompt(3, bare, "ab-cd-ef")
    assert 'Current state: "ab-cd-ef"' in prompt
    assert f"Apply Step 3: {bare}" in prompt
    assert "Step 1" not in prompt and "Step 2" not in prompt
    assert prompt.count("Step ") == 1


def test_bare_instruction_rejects_malformed_lines() -> None:
    with pytest.raises(ValueError, match="malformed step line"):
        stepwise._bare_step_instruction(["Step 2: keep only the first two digits."], 1)


# --- manifest freeze ---


def test_manifest_freezes_and_refuses_drift(tmp_path: Path) -> None:
    manifest = stepwise.run_manifest(tmp_path, "run-manifest-1")
    assert len(manifest["tasks"]) == 16
    assert len(manifest["slots"]) == 96
    assert manifest["scientific_acceptance"] is False
    again = stepwise.run_manifest(tmp_path, "run-manifest-2")
    assert again["tasks"] == manifest["tasks"]
    path = tmp_path / "stepwise-manifest.json"
    tampered = json.loads(path.read_text(encoding="utf-8"))
    tampered["tasks"][0]["input"] = "9999"
    path.write_text(json.dumps(tampered), encoding="utf-8")
    with pytest.raises(ValueError, match="manifest drift"):
        stepwise.run_manifest(tmp_path, "run-manifest-3")
    with pytest.raises(ValueError, match="manifest drift"):
        stepwise._load_manifest(tmp_path)


# --- faked model port: ITT accounting ---


class _FakeCompletion:
    def __init__(self, output: str, finish_reason: str) -> None:
        self.output = output
        self.finish_reason = finish_reason


class _FakePort:
    behavior = None  # callable(prompt) -> _FakeCompletion | raises
    context_task = None  # explicit arm-b session context (one task per process)

    def __init__(self, **kwargs) -> None:
        pass

    def complete_prompt(self, prompt: str) -> _FakeCompletion:
        behavior = type(self).behavior
        assert behavior is not None, "fake behavior not configured"
        return behavior(prompt)


@pytest.fixture()
def fake_port(monkeypatch):
    monkeypatch.setattr(stepwise, "ZaiStandardModelPort", _FakePort)
    _FakePort.behavior = None
    _FakePort.context_task = None
    yield _FakePort
    _FakePort.behavior = None
    _FakePort.context_task = None


def _parse_arm_a_prompt(prompt: str) -> str:
    return json.loads(
        re.search(r"New task: (\{.*\})", prompt).group(1)
    )["value"]


def _parse_step_prompt(prompt: str) -> tuple[int, str]:
    state = json.loads(
        re.search(r'Current state: ("(?:[^"\\]|\\.)*")', prompt).group(1)
    )
    step = int(re.search(r"Apply Step (\d+):", prompt).group(1))
    return step, state


def _campaign_input_index() -> dict[str, dict]:
    return {
        t["input"]: t for t in stepwise._campaign_tasks()
    }


def test_arm_a_itt_paths(fake_port, tmp_path: Path) -> None:
    stepwise.run_manifest(tmp_path, "run-a")
    wrong = {"prog-digits-01", "prog-rotate-02"}
    broken = {"prog-digits-02"}

    def behavior(prompt: str) -> _FakeCompletion:
        value = _parse_arm_a_prompt(prompt)
        task = _campaign_input_index()[value]
        if task["program_id"] in broken:
            raise RuntimeError("ProviderTransportRejected")
        if task["program_id"] in wrong:
            return _FakeCompletion("0000", "stop")
        return _FakeCompletion(task["truth"], "stop")

    _FakePort.behavior = behavior
    summary = stepwise.run_arm_a(tmp_path, "run-a", "wave1", "test-key")
    rows = {row["program_id"]: row for row in summary["rows"]}
    assert summary["sends"] == 8
    assert rows["prog-digits-00"]["itt_success"] is True
    assert rows["prog-digits-00"]["correct"] is True
    assert rows["prog-digits-01"]["itt_success"] is False
    assert rows["prog-digits-01"]["correct"] is False
    assert rows["prog-digits-02"]["status"] == "provider_error"
    assert rows["prog-digits-02"]["itt_success"] is False
    assert summary["itt_successes"] == 5


def test_arm_b_stepwise_chain_all_correct(fake_port, tmp_path: Path) -> None:
    stepwise.run_manifest(tmp_path, "run-b")
    program = all_programs()[0]
    task = next(
        t for t in stepwise._campaign_tasks()
        if t["program_id"] == program["program_id"] and t["wave"] == "wave1"
    )
    chain = _reference_chain(task["family"], task["program_code"], task["input"])

    def behavior(prompt: str) -> _FakeCompletion:
        step, state = _parse_step_prompt(prompt)
        # the runner must feed exactly the registered chain state
        expected_state = task["input"] if step == 1 else chain[step - 2]
        assert state == expected_state
        return _FakeCompletion(chain[step - 1], "stop")

    _FakePort.behavior = behavior
    _FakePort.context_task = task
    summary = stepwise.run_arm_b(
        tmp_path, "run-b", "wave1", program["program_id"], "test-key"
    )
    row = summary["rows"][0]
    assert row["status"] == "evaluated"
    assert row["sends"] == 5
    assert row["final_state"] == task["truth"]
    assert row["itt_success"] is True
    assert row["slots"] == stepwise.arm_b_slot_block(
        "wave1", stepwise._program_position(program["program_id"])
    )


def test_arm_b_provider_error_mid_chain_fails_itt(fake_port, tmp_path: Path) -> None:
    stepwise.run_manifest(tmp_path, "run-b2")
    program = all_programs()[4]  # rotate
    task = next(
        t for t in stepwise._campaign_tasks()
        if t["program_id"] == program["program_id"] and t["wave"] == "wave2"
    )
    chain = _reference_chain(task["family"], task["program_code"], task["input"])
    calls = {"count": 0}

    def behavior(prompt: str) -> _FakeCompletion:
        step, state = _parse_step_prompt(prompt)
        calls["count"] += 1
        assert state == (task["input"] if step == 1 else chain[step - 2])
        if step == 3:
            raise RuntimeError("ProviderBudgetExhausted")
        return _FakeCompletion(chain[step - 1], "stop")

    _FakePort.behavior = behavior
    _FakePort.context_task = task
    summary = stepwise.run_arm_b(
        tmp_path, "run-b2", "wave2", program["program_id"], "test-key"
    )
    row = summary["rows"][0]
    assert calls["count"] == 3
    assert row["sends"] == 3
    assert row["status"] == "provider_error"
    assert row["itt_success"] is False
    # remaining slots for the task were never reserved: slot == attempted send
    ledger = stepwise.StepwiseLedger(tmp_path / "stepwise-ledger", "run-b2")
    assert ledger.consumed == 3


def test_arm_b_unparseable_step_fails_itt(fake_port, tmp_path: Path) -> None:
    stepwise.run_manifest(tmp_path, "run-b3")
    program = all_programs()[1]
    task = next(
        t for t in stepwise._campaign_tasks()
        if t["program_id"] == program["program_id"] and t["wave"] == "wave1"
    )
    chain = _reference_chain(task["family"], task["program_code"], task["input"])

    def behavior(prompt: str) -> _FakeCompletion:
        step, _ = _parse_step_prompt(prompt)
        if step == 5:
            return _FakeCompletion("", "length")
        return _FakeCompletion(chain[step - 1], "stop")

    _FakePort.behavior = behavior
    _FakePort.context_task = task
    summary = stepwise.run_arm_b(
        tmp_path, "run-b3", "wave1", program["program_id"], "test-key"
    )
    row = summary["rows"][0]
    assert row["sends"] == 5
    assert row["status"] == "unscored"
    assert row["itt_success"] is False


# --- full offline campaign rehearsal and report ---


def _run_full_campaign(tmp_path: Path, a_wrong: set, b_wrong_final: set,
                       b_unparseable: set = frozenset()) -> dict:
    stepwise.run_manifest(tmp_path, "run-rehearsal")
    index = _campaign_input_index()

    def arm_a_behavior(prompt: str) -> _FakeCompletion:
        value = _parse_arm_a_prompt(prompt)
        task = index[value]
        if (task["program_id"], task["wave"]) in a_wrong:
            return _FakeCompletion("0000", "stop")
        return _FakeCompletion(task["truth"], "stop")

    def arm_b_behavior(prompt: str) -> _FakeCompletion:
        task = _FakePort.context_task
        step, state = _parse_step_prompt(prompt)
        chain = _reference_chain(
            task["family"], task["program_code"], task["input"]
        )
        assert state == (task["input"] if step == 1 else chain[step - 2])
        key = (task["program_id"], task["wave"])
        if key in b_unparseable and step == 2:
            return _FakeCompletion("", "length")
        if key in b_wrong_final and step == 5:
            return _FakeCompletion("XX", "stop")
        return _FakeCompletion(chain[step - 1], "stop")

    def behavior(prompt: str) -> _FakeCompletion:
        if "Current state:" in prompt:
            return arm_b_behavior(prompt)
        return arm_a_behavior(prompt)

    _FakePort.behavior = behavior
    for wave in WAVES:
        stepwise.run_arm_a(tmp_path, "run-rehearsal", wave, "test-key")
        for program in all_programs():
            task = next(
                t for t in stepwise._campaign_tasks()
                if t["program_id"] == program["program_id"] and t["wave"] == wave
            )
            _FakePort.context_task = task
            stepwise.run_arm_b(
                tmp_path, "run-rehearsal", wave, program["program_id"],
                "test-key",
            )
    return stepwise.run_report(tmp_path)


def test_full_offline_rehearsal_and_report(fake_port, tmp_path: Path) -> None:
    report = _run_full_campaign(tmp_path, set(), set())
    assert report["sends_total"] == 96
    assert report["tasks"] == 16
    assert report["a_itt_successes"] == 16
    assert report["b_itt_successes"] == 16
    assert report["paired_b_minus_a"] == 0
    assert report["verdict"] == "predeclared success criterion NOT MET"

    # boundary values exactly at the predeclared thresholds: B=14/16, +3
    report2 = _run_full_campaign(
        tmp_path / "variant",
        a_wrong={("prog-digits-00", "wave1"), ("prog-digits-01", "wave1"),
                 ("prog-rotate-01", "wave2"), ("prog-rotate-03", "wave1"),
                 ("prog-digits-03", "wave2")},
        b_wrong_final={("prog-rotate-00", "wave2")},
        b_unparseable={("prog-digits-02", "wave1")},
    )
    assert report2["sends_total"] == 93  # the unparseable task stopped after step 2
    assert report2["a_itt_successes"] == 11
    assert report2["b_itt_successes"] == 14
    assert report2["paired_b_minus_a"] == 3
    assert report2["discordant_b_only"] == 5
    assert report2["discordant_a_only"] == 2
    assert report2["b_step_failure_positions"] == {"2": 1}
    assert report2["verdict"] == "predeclared success criterion MET"


def test_report_refuses_incomplete_campaign(fake_port, tmp_path: Path) -> None:
    stepwise.run_manifest(tmp_path, "run-partial")
    stepwise.run_arm_a(tmp_path, "run-partial", "wave1", "test-key")
    with pytest.raises(FileNotFoundError, match="campaign incomplete"):
        stepwise.run_report(tmp_path)
