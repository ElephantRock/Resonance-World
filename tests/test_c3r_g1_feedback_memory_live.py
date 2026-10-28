"""Offline tests for the G1 feedback-acquired procedural memory campaign.

Pure-logic coverage: hand-computed evaluator vectors for the two new
families, unambiguity and role disjointness (evidence/probe/eval) of all
derived inputs, the 80-slot plan (learning blocks + three exec arms),
the O_EXCL ledger, manifest freeze, capsule format check, prompt
information separation (Learned sees capsule-only, Raw evidence-only,
Fresh neither), the learning loop over a faked model port (validate on
round 1/2, never-validate, empty-output guard, transport abort, budget
exhaustion), execution arms incl. the no-capsule path, and a full
offline campaign rehearsal feeding both gate branches. No network.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import scripts.run_c3r_g1_feedback_memory_live as feedback
from c3r_g1_feedback_families import (
    _execute as fb_execute,
    all_programs as fb_programs,
    is_unambiguous,
)

GOOD_CAPSULE = (
    "Step 1: swap the two halves.\n"
    "Step 2: shift every character two positions.\n"
    "Step 3: move the first character to the end.\n"
    "Step 4: swap the 1st and 3rd characters.\n"
    "Step 5: append the count as one digit."
)
BAD_CAPSULE = (
    "Step 1: leave the string unchanged.\n"
    "Step 2: shift every character one position.\n"
    "Step 3: leave the order unchanged.\n"
    "Step 4: leave the order unchanged.\n"
    "Step 5: prepend a random digit."
)


# --- evaluator: hand-computed vectors ---


def test_binary_hand_vectors() -> None:
    # AAAAA on 10110001:
    # flip -> 01001110; swap halves -> 11100100; first to end -> 11001001;
    # flip first -> 01001001 (three 1s); prefix count -> 301001001
    assert fb_execute("binary", {"value": "10110001"}, "AAAAA") == "301001001"
    # BBBBB on 10110001:
    # reverse -> 10001101; halves unchanged; last to front -> 11000110;
    # flip last -> 11000111 (five 1s); append count -> 110001115
    assert fb_execute("binary", {"value": "10110001"}, "BBBBB") == "110001115"


def test_alpha_hand_vectors() -> None:
    # AAAAA on abcdefgh:
    # swap halves -> efghabcd; +2 -> ghijcdef; first to end -> hijcdefg;
    # swap 1st/3rd -> jihcdefg; distinct = 8 -> prefix -> 8jihcdefg
    assert fb_execute("alpha", {"value": "abcdefgh"}, "AAAAA") == "8jihcdefg"
    # BBBBB on abcdefgh:
    # reverse -> hgfedcba; -2 -> fedcbazy; last to front -> yfedcbaz;
    # swap 2nd/4th -> ydefcbaz; distinct = 8 -> append -> ydefcbaz8
    assert fb_execute("alpha", {"value": "abcdefgh"}, "BBBBB") == "ydefcbaz8"


# --- inputs: unambiguous, role-disjoint, deterministic ---


def test_program_plans_unambiguous_and_role_disjoint() -> None:
    all_values: list[str] = []
    for plan in feedback.campaign_plan():
        inputs = (
            [pair["input"] for pair in plan["evidence"]]
            + list(plan["probes"])
            + [task["input"] for task in plan["eval"]]
        )
        assert len(inputs) == 10
        assert len(set(inputs)) == 10, plan["program_id"]
        all_values.extend(inputs)
        for value in inputs:
            assert is_unambiguous(plan["family"], value)
        again = next(
            p for p in feedback.campaign_plan()
            if p["program_id"] == plan["program_id"]
        )
        assert again == plan
        for pair in plan["evidence"]:
            assert pair["output"] == fb_execute(
                plan["family"], {"value": pair["input"]}, plan["program_code"]
            )
        for task in plan["eval"]:
            assert task["truth"] == fb_execute(
                plan["family"], {"value": task["input"]}, plan["program_code"]
            )
    # global uniqueness: no input value appears under two programs
    assert len(all_values) == 40
    assert len(set(all_values)) == 40


# --- slot plan and ledger ---


def test_slot_plan_tiles_80_exactly() -> None:
    plan = feedback.slot_plan()
    indices = [row["index"] for row in plan]
    assert sorted(indices) == list(range(80))
    assert len(indices) == 80
    learning = [row["index"] for row in plan if row["kind"] == "learning"]
    assert learning == list(range(32))
    for arm, base in feedback.EXEC_BASES.items():
        arm_rows = sorted(
            row["index"] for row in plan
            if row["kind"] == "exec" and row["arm"] == arm
        )
        assert arm_rows == list(range(base, base + 16))
    for program in fb_programs():
        base = feedback._program_position(program["program_id"]) * 8
        block = sorted(
            row["index"] for row in plan
            if row["kind"] == "learning"
            and row["program_id"] == program["program_id"]
        )
        assert block == list(range(base, base + 8))


def test_ledger_enforces_cap_and_double_dispatch(tmp_path: Path) -> None:
    ledger = feedback.FeedbackLedger(tmp_path / "fb-ledger", "run-x")
    for index in range(80):
        ledger.reserve(index, "full")
    assert ledger.consumed == 80
    with pytest.raises(RuntimeError, match="exceeds the 80-send cap"):
        ledger.reserve(80, "over-budget")
    with pytest.raises(RuntimeError, match="already reserved"):
        ledger.reserve(0, "double")


# --- manifest freeze and capsule format ---


def test_manifest_freezes_and_refuses_drift(tmp_path: Path) -> None:
    manifest = feedback.run_manifest(tmp_path, "run-m1")
    assert len(manifest["plan"]) == 4
    assert len(manifest["slots"]) == 80
    assert manifest["scientific_acceptance"] is False
    again = feedback.run_manifest(tmp_path, "run-m2")
    assert again["plan"] == manifest["plan"]
    path = tmp_path / "feedback-manifest.json"
    tampered = json.loads(path.read_text(encoding="utf-8"))
    tampered["plan"][0]["evidence"][0]["input"] = "zzzzzzzz"
    path.write_text(json.dumps(tampered), encoding="utf-8")
    with pytest.raises(ValueError, match="manifest drift"):
        feedback.run_manifest(tmp_path, "run-m3")
    with pytest.raises(ValueError, match="manifest drift"):
        feedback._load_manifest(tmp_path)


def test_capsule_format_check() -> None:
    assert feedback._capsule_five_steps(GOOD_CAPSULE) is True
    assert feedback._capsule_five_steps(BAD_CAPSULE) is True
    assert feedback._capsule_five_steps("Step 1: only one") is False
    assert feedback._capsule_five_steps("free text\nno steps here") is False
    assert feedback._capsule_five_steps(None) is False
    assert feedback._capsule_five_steps("") is False


# --- prompt information separation ---


def test_prompt_information_separation() -> None:
    plan = feedback.campaign_plan()[0]
    evidence = plan["evidence"]
    task_input = plan["eval"][0]["input"]

    draft = feedback.draft_prompt(evidence)
    assert draft.count("in=") == 3
    assert "Step 5" not in draft.split("Examples:")[0]

    apply_p = feedback.apply_prompt(GOOD_CAPSULE, task_input)
    assert GOOD_CAPSULE in apply_p
    assert json.dumps({"value": task_input}, sort_keys=True) in apply_p
    assert "in=" not in apply_p

    revise = feedback.revise_prompt(
        BAD_CAPSULE, evidence, plan["probes"][0], "wrong", "expected"
    )
    assert BAD_CAPSULE in revise
    assert revise.count("in=") == 4  # 3 examples + the failed probe
    assert "'wrong'" in revise and "out=expected" in revise

    learned = feedback.exec_learned_prompt(GOOD_CAPSULE, task_input)
    assert learned.startswith("This is a new isolated agent session.")
    assert GOOD_CAPSULE in learned and "in=" not in learned

    raw = feedback.exec_raw_prompt(evidence, task_input)
    assert raw.count("in=") == 3
    assert "Step 1:" not in raw and "procedure strictly" not in raw

    fresh = feedback.exec_fresh_prompt(task_input)
    assert json.dumps({"value": task_input}, sort_keys=True) in fresh
    assert "in=" not in fresh and "Step" not in fresh


# --- faked model port ---


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
    monkeypatch.setattr(feedback, "ZaiStandardModelPort", _FakePort)
    _FakePort.behavior = None
    yield _FakePort
    _FakePort.behavior = None


def _input_truth_index() -> dict[str, str]:
    index: dict[str, str] = {}
    for plan in feedback.campaign_plan():
        for pair in plan["evidence"]:
            index[pair["input"]] = pair["output"]
        for probe in plan["probes"]:
            index[probe] = fb_execute(
                plan["family"], {"value": probe}, plan["program_code"]
            )
        for task in plan["eval"]:
            index[task["input"]] = task["truth"]
    return index


def _parse_task(prompt: str) -> str:
    return json.loads(
        __import__("re").search(r"New task: (\{.*\})", prompt).group(1)
    )["value"]


LEARN_MARKER = "Execute the following procedure strictly in order"
DRAFT_MARKER = "Write the exact procedure"
REVISE_MARKER = "Revise it."
GUARD_MARKER = feedback.EMPTY_GUARD_SUFFIX.strip()


def _make_loop_behavior(mode: str):
    """Scripted model: mode in {good, revise_once, empty_first}.

    empty_first: the FIRST draft attempt returns empty; the guarded
    retry returns GOOD; applies behave like revise_once.
    """

    truth = _input_truth_index()
    state = {"drafts": 0}

    def behavior(prompt: str) -> _FakeCompletion:
        if DRAFT_MARKER in prompt:
            state["drafts"] += 1
            if mode == "good":
                return _FakeCompletion(GOOD_CAPSULE, "stop")
            if (mode == "empty_first" and state["drafts"] == 1
                    and GUARD_MARKER not in prompt):
                return _FakeCompletion("", "length")
            if mode == "empty_first":
                return _FakeCompletion(GOOD_CAPSULE, "stop")
            return _FakeCompletion(BAD_CAPSULE, "stop")
        if REVISE_MARKER in prompt:
            return _FakeCompletion(GOOD_CAPSULE, "stop")
        if LEARN_MARKER in prompt:
            value = _parse_task(prompt)
            if GOOD_CAPSULE in prompt:
                return _FakeCompletion(truth[value], "stop")
            return _FakeCompletion("WRONGVAL", "stop")
        raise AssertionError(f"unexpected prompt kind: {prompt[:80]!r}")

    return behavior


def _learn(fake, tmp_path: Path, program_id: str, mode: str):
    feedback.run_manifest(tmp_path, "run-learn")
    _FakePort.behavior = _make_loop_behavior(mode)
    return feedback.run_learn(tmp_path, "run-learn", program_id, "test-key")


def test_learn_validates_round_one(fake_port, tmp_path: Path) -> None:
    outcome = _learn(fake_port, tmp_path, "prog-binary-00", "good")
    assert outcome["validated"] is True
    assert outcome["validation_round"] == 1
    assert outcome["sends_used"] == 2
    assert outcome["capsule"] == GOOD_CAPSULE
    assert outcome["capsule_format_ok"] is True
    assert outcome["aborted"] is None


def test_learn_validates_after_revision(fake_port, tmp_path: Path) -> None:
    outcome = _learn(fake_port, tmp_path, "prog-alpha-01", "revise_once")
    assert outcome["validated"] is True
    assert outcome["validation_round"] == 2
    assert outcome["sends_used"] == 4  # draft, apply1, revise1, apply2
    assert outcome["capsule"] == GOOD_CAPSULE


def test_learn_never_validates_with_bad_revisions(fake_port, tmp_path: Path) -> None:
    feedback.run_manifest(tmp_path, "run-learn")
    truth = _input_truth_index()

    def behavior(prompt: str) -> _FakeCompletion:
        if DRAFT_MARKER in prompt:
            return _FakeCompletion(BAD_CAPSULE, "stop")
        if REVISE_MARKER in prompt:
            return _FakeCompletion(BAD_CAPSULE, "stop")
        value = _parse_task(prompt)
        return _FakeCompletion("NOPE", "stop")

    _FakePort.behavior = behavior
    outcome = feedback.run_learn(
        tmp_path, "run-learn", "prog-alpha-00", "test-key"
    )
    assert outcome["validated"] is False
    assert outcome["sends_used"] == 7  # draft + 3x(apply+revise)
    assert outcome["capsule"] == BAD_CAPSULE
    assert outcome["capsule_format_ok"] is True


def test_learn_empty_guard_continues_loop(fake_port, tmp_path: Path) -> None:
    outcome = _learn(fake_port, tmp_path, "prog-binary-00", "empty_first")
    # draft: empty then guarded GOOD (2 sends); apply1: truth (1 send)
    assert outcome["validated"] is True
    assert outcome["validation_round"] == 1
    assert outcome["sends_used"] == 3
    guards = [e for e in outcome["events"] if e["guard"]]
    assert len(guards) == 1


def test_learn_transport_abort_keeps_draft(fake_port, tmp_path: Path) -> None:
    feedback.run_manifest(tmp_path, "run-learn")

    def behavior(prompt: str) -> _FakeCompletion:
        if DRAFT_MARKER in prompt:
            return _FakeCompletion(BAD_CAPSULE, "stop")
        if REVISE_MARKER in prompt:
            return _FakeCompletion(BAD_CAPSULE, "stop")
        raise RuntimeError("ProviderTransportRejected")

    _FakePort.behavior = behavior
    outcome = feedback.run_learn(
        tmp_path, "run-learn", "prog-binary-00", "test-key"
    )
    assert outcome["aborted"] == "RuntimeError"
    assert outcome["validated"] is False
    assert outcome["capsule"] == BAD_CAPSULE  # last draft kept, no rescue
    assert outcome["sends_used"] == 2


def test_learn_budget_exhaustion_is_bounded(fake_port, tmp_path: Path) -> None:
    feedback.run_manifest(tmp_path, "run-learn")

    def behavior(prompt: str) -> _FakeCompletion:
        if DRAFT_MARKER in prompt:
            return _FakeCompletion(BAD_CAPSULE, "stop")
        if REVISE_MARKER in prompt:
            return _FakeCompletion(BAD_CAPSULE, "stop")
        if GUARD_MARKER in prompt:
            return _FakeCompletion("WRONGVAL", "stop")
        return _FakeCompletion("", "length")  # every apply needs the guard

    _FakePort.behavior = behavior
    outcome = feedback.run_learn(
        tmp_path, "run-learn", "prog-alpha-01", "test-key"
    )
    assert outcome["budget_exhausted"] is True
    assert outcome["sends_used"] == 8  # hard block bound respected
    assert outcome["validated"] is False
    ledger = feedback.FeedbackLedger(tmp_path / "feedback-ledger", "run-learn")
    assert ledger.consumed == 8


# --- execution arms ---


def _make_exec_behavior(learned_wrong: set, raw_wrong: set):
    truth = _input_truth_index()

    def behavior(prompt: str) -> _FakeCompletion:
        value = _parse_task(prompt)
        if prompt.startswith("This is a new isolated agent session."):
            if value in learned_wrong:
                return _FakeCompletion("LEARNEDWRONG", "stop")
            return _FakeCompletion(truth[value], "stop")
        if "Work out the transformation" in prompt:
            if value in raw_wrong:
                return _FakeCompletion("RAWWRONG", "stop")
            return _FakeCompletion(truth[value], "stop")
        return _FakeCompletion("FRESHGUESS", "stop")

    return behavior


def test_exec_learned_uses_capsule_verbatim(fake_port, tmp_path: Path) -> None:
    feedback.run_manifest(tmp_path, "run-exec")
    for program in fb_programs():
        feedback._write_json(
            tmp_path / f"capsule-{program['program_id']}.json",
            {"schema": feedback.SCHEMA, "program_id": program["program_id"],
             "capsule": GOOD_CAPSULE, "validated": True},
        )
    seen_prompts: list[str] = []

    def behavior(prompt: str) -> _FakeCompletion:
        seen_prompts.append(prompt)
        value = _parse_task(prompt)
        return _FakeCompletion(_input_truth_index()[value], "stop")

    _FakePort.behavior = behavior
    summary = feedback.run_exec(tmp_path, "run-exec", "learned", "test-key")
    assert summary["sends"] == 16
    assert summary["itt_successes"] == 16
    for prompt in seen_prompts:
        assert GOOD_CAPSULE in prompt
        assert "in=" not in prompt


def test_exec_learned_no_capsule_fails_without_sends(
    fake_port, tmp_path: Path
) -> None:
    feedback.run_manifest(tmp_path, "run-exec2")
    for program in fb_programs():
        feedback._write_json(
            tmp_path / f"capsule-{program['program_id']}.json",
            {"schema": feedback.SCHEMA, "program_id": program["program_id"],
             "capsule": None if program["program_id"] == "prog-binary-00"
             else GOOD_CAPSULE, "validated": False},
        )
    _FakePort.behavior = _make_exec_behavior(set(), set())
    summary = feedback.run_exec(tmp_path, "run-exec2", "learned", "test-key")
    assert summary["sends"] == 12  # 4 tasks of binary-00 sent nothing
    assert summary["itt_successes"] == 12
    assert summary["taxonomy"]["no_capsule"] == 4


def test_exec_raw_and_fresh(fake_port, tmp_path: Path) -> None:
    feedback.run_manifest(tmp_path, "run-exec3")
    raw_wrong = {
        task["input"] for task in feedback.campaign_tasks()
        if task["input_index"] % 2 == 1
    }
    _FakePort.behavior = _make_exec_behavior(set(), raw_wrong)
    raw = feedback.run_exec(tmp_path, "run-exec3", "raw", "test-key")
    assert raw["itt_successes"] == 8
    assert raw["taxonomy"]["wrong_value"] == 8
    fresh = feedback.run_exec(tmp_path, "run-exec3", "fresh", "test-key")
    assert fresh["itt_successes"] == 0
    assert fresh["taxonomy"]["wrong_value"] == 16


# --- full rehearsal and gate ---


def _run_full_campaign(fake, tmp_path: Path, learned_wrong: set) -> dict:
    feedback.run_manifest(tmp_path, "run-full")
    _FakePort.behavior = _make_loop_behavior("revise_once")
    for program in fb_programs():
        feedback.run_learn(
            tmp_path, "run-full", program["program_id"], "test-key"
        )
    _FakePort.behavior = _make_exec_behavior(learned_wrong, {
        task["input"] for task in feedback.campaign_tasks()
        if task["input_index"] % 2 == 1
    })
    for arm in ("learned", "raw", "fresh"):
        feedback.run_exec(tmp_path, "run-full", arm, "test-key")
    return feedback.run_report(tmp_path)


def test_full_rehearsal_gate_passed(fake_port, tmp_path: Path) -> None:
    report = _run_full_campaign(fake_port, tmp_path / "pass", set())
    assert report["learning"]["validated"] == 4
    assert report["learning"]["learning_sends"] == 16  # 4 sends x 4
    assert report["learned_itt"] == 16
    assert report["raw_itt"] == 8
    assert report["fresh_itt"] == 0
    assert report["paired_learned_vs_raw"] == {
        "both": 8, "x_only": 8, "y_only": 0, "neither": 0,
    }
    assert report["gate_g1_repeatable_value"] is True
    assert report["gate_g2_beats_rederivation"] is True
    assert "GATE PASSED" in report["verdict"]
    ledger = feedback.FeedbackLedger(
        tmp_path / "pass" / "feedback-ledger", "run-full"
    )
    assert ledger.consumed == 16 + 48


def test_full_rehearsal_gate_failed(fake_port, tmp_path: Path) -> None:
    learned_wrong = {
        task["input"] for task in feedback.campaign_tasks()
        if task["input_index"] >= 2  # 8 wrong -> learned 8/16 < 10
    }
    report = _run_full_campaign(fake_port, tmp_path / "fail", learned_wrong)
    assert report["learned_itt"] == 8
    assert report["gate_g1_repeatable_value"] is False
    assert "GATE FAILED" in report["verdict"]


def test_report_refuses_incomplete_campaign(fake_port, tmp_path: Path) -> None:
    feedback.run_manifest(tmp_path, "run-partial")
    feedback._write_json(
        tmp_path / "summary-fresh.json",
        {"schema": feedback.SCHEMA, "arm": "fresh", "rows": []},
    )
    with pytest.raises(FileNotFoundError, match="campaign incomplete"):
        feedback.run_report(tmp_path)
