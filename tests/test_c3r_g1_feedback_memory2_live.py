"""Offline tests for the G1 feedback memory v2 operational rehabilitation.

Covers: the new v2 units (codes/inputs disjoint from v1 by seed AND by
exclusion), the 96-slot plan (qualification 88..95, learning 0..39,
Learned/Raw/Fresh 40..87), the independent O_EXCL ledger, manifest
freeze including the qualification plan, the qualification gate over a
faked port (pass / capsule-fail / transport-fail / wrong-but-complete
raw), budget and timeout wiring (induction 16384, exec arms 4096, all
sends 300 s), execution arms incl. no-capsule, and the report's three
owner-table verdicts. No network anywhere.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import scripts.run_c3r_g1_feedback_memory2_live as fb2
from c3r_g1_feedback_families import (
    _execute as fb_execute,
    all_programs as v1_programs,
    all_programs_v2,
    is_unambiguous,
    qualification_program,
)
from scripts.run_c3r_g1_feedback_memory_live import campaign_plan as v1_plan

from tests.test_c3r_g1_feedback_memory_live import (
    BAD_CAPSULE,
    DRAFT_MARKER,
    GOOD_CAPSULE,
    GUARD_MARKER,
    LEARN_MARKER,
    REVISE_MARKER,
    _parse_task,
)


# --- units ---


def test_v2_units_are_new_and_deterministic() -> None:
    v1 = {p["program_id"]: p["program"] for p in v1_programs()}
    again = all_programs_v2()
    assert [p["program_id"] for p in again] == [p["program_id"] for p in v1_programs()]
    for program in again:
        assert program["program"] != v1[program["program_id"]]
    assert all_programs_v2() == again
    qual = qualification_program()
    assert qual["program_id"] == "prog-binary-qual"
    assert qualification_program() == qual
    assert qual["program"] not in {p["program"] for p in again}


def test_v2_inputs_unambiguous_unique_and_disjoint_from_v1() -> None:
    v1_inputs: set[str] = set()
    for plan in v1_plan():
        v1_inputs |= {pair["input"] for pair in plan["evidence"]}
        v1_inputs |= set(plan["probes"])
        v1_inputs |= {task["input"] for task in plan["eval"]}

    v2_inputs: set[str] = set()
    for plan in fb2.campaign_plan_v2():
        inputs = (
            [pair["input"] for pair in plan["evidence"]]
            + list(plan["probes"])
            + [task["input"] for task in plan["eval"]]
        )
        assert len(inputs) == 10 and len(set(inputs)) == 10
        for value in inputs:
            assert is_unambiguous(plan["family"], value)
            assert value not in v1_inputs
        v2_inputs |= set(inputs)
    assert len(v2_inputs) == 40

    qual = fb2.qualification_plan()
    qual_inputs = (
        [pair["input"] for pair in qual["evidence"]]
        + [qual["probe"], qual["raw_input"]]
    )
    for value in qual_inputs:
        assert is_unambiguous("binary", value)
        assert value not in v1_inputs
        assert value not in v2_inputs
    for pair in qual["evidence"]:
        assert pair["output"] == fb_execute(
            "binary", {"value": pair["input"]}, qual["program_code"]
        )


# --- slot plan and ledger ---


def test_slot_plan_tiles_96_exactly() -> None:
    plan = fb2.slot_plan_v2()
    indices = [row["index"] for row in plan]
    assert sorted(indices) == list(range(96))
    qual = sorted(row["index"] for row in plan if row["kind"] == "qualification")
    assert qual == list(range(88, 96))
    for position, program in enumerate(all_programs_v2()):
        block = sorted(
            row["index"] for row in plan
            if row["kind"] == "learning"
            and row["program_id"] == program["program_id"]
        )
        assert block == list(range(position * 10, position * 10 + 10))
    for arm, base in fb2.EXEC_BASES.items():
        arm_rows = sorted(
            row["index"] for row in plan
            if row["kind"] == "exec" and row["arm"] == arm
        )
        assert arm_rows == list(range(base, base + 16))


def test_ledger_enforces_cap_and_double_dispatch(tmp_path: Path) -> None:
    ledger = fb2.Feedback2Ledger(tmp_path / "fb2-ledger", "run-x")
    for index in range(96):
        ledger.reserve(index, "full")
    assert ledger.consumed == 96
    with pytest.raises(RuntimeError, match="exceeds the 96-send cap"):
        ledger.reserve(96, "over")
    with pytest.raises(RuntimeError, match="already reserved"):
        ledger.reserve(0, "double")


# --- manifest ---


def test_manifest_freezes_and_refuses_drift(tmp_path: Path) -> None:
    manifest = fb2.run_manifest(tmp_path, "run-m1")
    assert len(manifest["plan"]) == 4
    assert len(manifest["slots"]) == 96
    assert manifest["max_tokens_induction"] == 16384
    assert manifest["max_tokens_exec"] == 4096
    assert manifest["timeout_seconds"] == 300.0
    assert manifest["scientific_acceptance"] is False
    again = fb2.run_manifest(tmp_path, "run-m2")
    assert again["plan"] == manifest["plan"]
    path = tmp_path / "feedback2-manifest.json"
    tampered = json.loads(path.read_text(encoding="utf-8"))
    tampered["qualification"]["probe"] = "01010101"
    path.write_text(json.dumps(tampered), encoding="utf-8")
    with pytest.raises(ValueError, match="manifest drift"):
        fb2.run_manifest(tmp_path, "run-m3")
    with pytest.raises(ValueError, match="manifest drift"):
        fb2._load_manifest(tmp_path)


# --- faked model port ---


class _FakeCompletion:
    def __init__(self, output: str, finish_reason: str) -> None:
        self.output = output
        self.finish_reason = finish_reason


class _FakePort:
    behavior = None
    calls: list[dict] = []

    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs

    def complete_prompt(self, prompt: str) -> _FakeCompletion:
        behavior = type(self).behavior
        assert behavior is not None
        type(self).calls.append({
            "prompt": prompt,
            "max_tokens": self.kwargs.get("max_tokens"),
            "timeout": self.kwargs.get("timeout_seconds"),
        })
        return behavior(prompt)


@pytest.fixture()
def fake_port(monkeypatch):
    monkeypatch.setattr(fb2, "ZaiStandardModelPort", _FakePort)
    _FakePort.behavior = None
    _FakePort.calls = []
    yield _FakePort
    _FakePort.behavior = None
    _FakePort.calls = []


def _v2_truth_index() -> dict[str, str]:
    index: dict[str, str] = {}
    qual = fb2.qualification_plan()
    for pair in qual["evidence"]:
        index[pair["input"]] = pair["output"]
    index[qual["probe"]] = qual["probe_truth"]
    index[qual["raw_input"]] = qual["raw_truth"]
    for plan in fb2.campaign_plan_v2():
        for pair in plan["evidence"]:
            index[pair["input"]] = pair["output"]
        for probe in plan["probes"]:
            index[probe] = fb_execute(
                plan["family"], {"value": probe}, plan["program_code"]
            )
        for task in plan["eval"]:
            index[task["input"]] = task["truth"]
    return index


# --- qualification gate ---


def test_qualification_passes(fake_port, tmp_path: Path) -> None:
    fb2.run_manifest(tmp_path, "run-q")
    truth = _v2_truth_index()

    def behavior(prompt: str) -> _FakeCompletion:
        if DRAFT_MARKER in prompt:
            return _FakeCompletion(GOOD_CAPSULE, "stop")
        if LEARN_MARKER in prompt:
            value = _parse_task(prompt)
            return _FakeCompletion(truth[value], "stop")
        if "Work out the transformation" in prompt:
            value = _parse_task(prompt)
            return _FakeCompletion("WRONGBUTCOMPLETE", "stop")
        raise AssertionError(f"unexpected prompt: {prompt[:60]!r}")

    _FakePort.behavior = behavior
    outcome = fb2.run_qualify(tmp_path, "run-q", "test-key")
    assert outcome["qualified"] is True
    assert outcome["failure"] is None
    assert outcome["sends_used"] == 3
    assert outcome["checks"]["capsule_five_step"] is True
    assert outcome["checks"]["apply_completed"] is True
    assert outcome["checks"]["apply_correct_informational"] is True
    assert outcome["checks"]["raw_completed"] is True
    assert outcome["checks"]["raw_correct_informational"] is False
    # qualification sends: induction budget + 300 s timeout
    assert [c["max_tokens"] for c in _FakePort.calls] == [16384] * 3
    assert {c["timeout"] for c in _FakePort.calls} == {300.0}


def test_qualification_fails_on_empty_draft(fake_port, tmp_path: Path) -> None:
    fb2.run_manifest(tmp_path, "run-q2")

    def behavior(prompt: str) -> _FakeCompletion:
        if DRAFT_MARKER in prompt:
            return _FakeCompletion("", "length")
        raise AssertionError("no further sends expected")

    _FakePort.behavior = behavior
    outcome = fb2.run_qualify(tmp_path, "run-q2", "test-key")
    assert outcome["qualified"] is False
    assert outcome["failure"] == "capsule_not_five_step"
    assert outcome["sends_used"] == 2  # draft + empty-guard retry


def test_qualification_fails_on_transport(fake_port, tmp_path: Path) -> None:
    fb2.run_manifest(tmp_path, "run-q3")

    def behavior(prompt: str) -> _FakeCompletion:
        if DRAFT_MARKER in prompt:
            return _FakeCompletion(GOOD_CAPSULE, "stop")
        raise RuntimeError("ProviderTransportRejected")

    _FakePort.behavior = behavior
    outcome = fb2.run_qualify(tmp_path, "run-q3", "test-key")
    assert outcome["qualified"] is False
    assert outcome["failure"] == "transport:RuntimeError"
    assert outcome["sends_used"] == 2


# --- learning loop ---


def test_learn_loop_validates_after_revision(fake_port, tmp_path: Path) -> None:
    fb2.run_manifest(tmp_path, "run-l")
    truth = _v2_truth_index()

    def behavior(prompt: str) -> _FakeCompletion:
        if DRAFT_MARKER in prompt:
            return _FakeCompletion(BAD_CAPSULE, "stop")
        if REVISE_MARKER in prompt:
            return _FakeCompletion(GOOD_CAPSULE, "stop")
        value = _parse_task(prompt)
        if GOOD_CAPSULE in prompt:
            return _FakeCompletion(truth[value], "stop")
        return _FakeCompletion("WRONGVAL", "stop")

    _FakePort.behavior = behavior
    outcome = fb2.run_learn(
        tmp_path, "run-l", all_programs_v2()[0]["program_id"], "test-key"
    )
    assert outcome["validated"] is True
    assert outcome["validation_round"] == 2
    assert outcome["sends_used"] == 4
    assert all(c["max_tokens"] == 16384 for c in _FakePort.calls)
    assert all(c["timeout"] == 300.0 for c in _FakePort.calls)


# --- execution arms ---


def test_exec_budgets_split(fake_port, tmp_path: Path) -> None:
    fb2.run_manifest(tmp_path, "run-e")
    for program in all_programs_v2():
        fb2._write_json(
            tmp_path / f"capsule-{program['program_id']}.json",
            {"schema": fb2.SCHEMA, "program_id": program["program_id"],
             "capsule": GOOD_CAPSULE, "validated": True},
        )
    truth = _v2_truth_index()

    def behavior(prompt: str) -> _FakeCompletion:
        value = _parse_task(prompt)
        return _FakeCompletion(truth[value], "stop")

    _FakePort.behavior = behavior
    learned = fb2.run_exec(tmp_path, "run-e", "learned", "test-key")
    assert learned["itt_successes"] == 16
    assert {c["max_tokens"] for c in _FakePort.calls} == {4096}

    _FakePort.calls = []
    raw = fb2.run_exec(tmp_path, "run-e", "raw", "test-key")
    assert raw["max_tokens"] == 16384
    assert {c["max_tokens"] for c in _FakePort.calls} == {16384}
    assert all(c["timeout"] == 300.0 for c in _FakePort.calls)


def test_exec_learned_no_capsule(fake_port, tmp_path: Path) -> None:
    fb2.run_manifest(tmp_path, "run-e2")
    for program in all_programs_v2():
        fb2._write_json(
            tmp_path / f"capsule-{program['program_id']}.json",
            {"schema": fb2.SCHEMA, "program_id": program["program_id"],
             "capsule": None if program["family"] == "binary"
             else GOOD_CAPSULE, "validated": False},
        )
    _FakePort.behavior = lambda prompt: _FakeCompletion("X", "stop")
    summary = fb2.run_exec(tmp_path, "run-e2", "learned", "test-key")
    assert summary["sends"] == 8
    assert summary["taxonomy"]["no_capsule"] == 8


# --- report: the owner's three verdicts ---


def _fake_qualified(tmp_path: Path) -> None:
    fb2._write_json(
        tmp_path / "qualification.json",
        {"schema": fb2.SCHEMA, "qualified": True, "failure": None,
         "sends_used": 3, "checks": {}},
    )


def test_report_operating_point_closed(fake_port, tmp_path: Path) -> None:
    fb2._write_json(
        tmp_path / "qualification.json",
        {"schema": fb2.SCHEMA, "qualified": False,
         "failure": "transport:ProviderTransportRejected",
         "sends_used": 2, "checks": {}},
    )
    report = fb2.run_report(tmp_path)
    assert "OPERATING POINT CLOSED" in report["verdict"]


def _run_full_v2(fake, tmp_path: Path, learned_wrong: set,
                 raw_wrong: set) -> dict:
    fb2.run_manifest(tmp_path, "run-full")
    truth = _v2_truth_index()

    def behavior(prompt: str) -> _FakeCompletion:
        if DRAFT_MARKER in prompt:
            return _FakeCompletion(BAD_CAPSULE, "stop")
        if REVISE_MARKER in prompt:
            return _FakeCompletion(GOOD_CAPSULE, "stop")
        value = _parse_task(prompt)
        if prompt.startswith("This is a new isolated agent session."):
            if value in learned_wrong:
                return _FakeCompletion("LWRONG", "stop")
            return _FakeCompletion(truth[value], "stop")
        if "Work out the transformation" in prompt:
            if value in raw_wrong:
                return _FakeCompletion("RWRONG", "stop")
            return _FakeCompletion(truth[value], "stop")
        if GOOD_CAPSULE in prompt:
            return _FakeCompletion(truth[value], "stop")
        return _FakeCompletion("WRONGVAL", "stop")

    _FakePort.behavior = behavior
    qual = fb2.run_qualify(tmp_path, "run-full", "test-key")
    assert qual["qualified"] is True
    for program in all_programs_v2():
        fb2.run_learn(tmp_path, "run-full", program["program_id"], "test-key")
    for arm in ("learned", "raw", "fresh"):
        fb2.run_exec(tmp_path, "run-full", arm, "test-key")
    return fb2.run_report(tmp_path)


def test_full_rehearsal_gate_passed(fake_port, tmp_path: Path) -> None:
    raw_wrong = {
        t["input"] for t in fb2.campaign_tasks_v2() if t["input_index"] % 2
    }
    report = _run_full_v2(fake_port, tmp_path / "pass", set(), raw_wrong)
    assert report["learned_itt"] == 16
    assert report["raw_itt"] == 8
    assert report["fresh_itt"] == 0
    assert report["gate_g1_repeatable_value"] is True
    assert report["gate_g2_beats_rederivation"] is True
    assert "GATE PASSED" in report["verdict"]
    assert "C3R-G2" in report["verdict"]


def test_full_rehearsal_gate_failed(fake_port, tmp_path: Path) -> None:
    learned_wrong = {
        t["input"] for t in fb2.campaign_tasks_v2() if t["input_index"] >= 2
    }
    report = _run_full_v2(fake_port, tmp_path / "fail", learned_wrong, set())
    assert report["learned_itt"] == 8
    assert report["gate_g1_repeatable_value"] is False
    assert "GATE FAILED" in report["verdict"]
    assert "scientific result" in report["verdict"]


def test_report_refuses_incomplete_after_qualification(
    fake_port, tmp_path: Path
) -> None:
    _fake_qualified(tmp_path)
    with pytest.raises(FileNotFoundError, match="campaign incomplete"):
        fb2.run_report(tmp_path)
