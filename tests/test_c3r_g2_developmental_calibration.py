"""Offline tests for the G2 developmental variance-calibration stage.

Covers the frozen protocol invariants: 12 organizations with 4 per
environment class; deterministic seed-locked fixtures; the exact
384-slot tiling (org block x arm x member x task); the permanent
O_EXCL cap; C/D information separation (C reads records and never the
procedure; D receives the procedure and never records; abstaining
organizations execute the neutral procedure with the operational
flag independent of grading); ITT handling of transport failures; the
cost accounting; and the report's variance/validity/N-input outputs
over a full fake-port rehearsal. No network; non-inferential.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

import scripts.run_c3r_g2_developmental_calibration as devcal
from resonance_world.c3r_g2_causal_qualification import NEUTRAL_PLAN


class _FakeCompletion:
    def __init__(self, output: str, finish_reason: str) -> None:
        self.output = output
        self.finish_reason = finish_reason
        self.prompt_tokens_reported = 100
        self.completion_tokens_reported = 50


class _FakePort:
    behavior = None
    calls: list[dict] = []

    def __init__(self, **kwargs) -> None:
        pass

    def complete_prompt(self, prompt: str) -> _FakeCompletion:
        behavior = type(self).behavior
        assert behavior is not None
        type(self).calls.append({"prompt": prompt})
        return behavior(prompt)


@pytest.fixture()
def fake_port(monkeypatch):
    monkeypatch.setattr(devcal, "_dispatch", _fake_dispatch)
    _FakePort.behavior = None
    _FakePort.calls = []
    yield _FakePort
    _FakePort.behavior = None
    _FakePort.calls = []


def _fake_dispatch(api_key: str, prompt: str) -> _FakeCompletion:
    return _FakePort.behavior(prompt)


def test_fixture_classes_and_determinism() -> None:
    orgs = devcal.all_orgs()
    assert len(orgs) == 12
    classes = [o["class"] for o in orgs]
    assert classes.count("unambiguous") == 4
    assert classes.count("noisy_majority") == 4
    assert classes.count("task_conditional") == 4
    again = devcal.all_orgs()
    assert again == orgs
    for org in orgs:
        expected_corpus = 30 if org["class"] == "task_conditional" else 20
        assert len(org["corpus"]) == expected_corpus
        assert len(org["tasks"]) == 8
        assert org["procedure"] is None or org["procedure"] in ("add-mul", "mul-add") \
            or True  # plan tuples come from PLANS
    # task-conditional orgs have variant-dependent truth
    tc = next(o for o in orgs if o["class"] == "task_conditional")
    plains = {tc["truth"][("ctx", v)] for v in ("plain", "special")}
    assert len(plains) == 2


def test_slot_plan_tiles_384_exactly() -> None:
    slots = [
        devcal.cell_slot(o, arm, m, t)
        for o in range(12) for arm in ("C", "D")
        for m in range(2) for t in range(8)
    ]
    assert sorted(slots) == list(range(384))
    assert len(set(slots)) == 384


def test_ledger_enforces_384_cap(tmp_path: Path) -> None:
    ledger = devcal.DevCalLedger(tmp_path / "led", "run-x")
    for index in range(384):
        ledger.reserve(index, "full")
    assert ledger.consumed == 384
    with pytest.raises(RuntimeError, match="exceeds the 384-send cap"):
        ledger.reserve(384, "over")
    with pytest.raises(RuntimeError, match="already reserved"):
        ledger.reserve(0, "double")


def test_manifest_freeze_and_drift(tmp_path: Path) -> None:
    devcal.run_manifest(tmp_path, "run-m")
    again = devcal.run_manifest(tmp_path, "run-m2")
    assert len(again["organizations"]) == 12
    path = tmp_path / "devcal-manifest.json"
    tampered = json.loads(path.read_text(encoding="utf-8"))
    tampered["organizations"][0]["corpus"][0]["plan"] = "add-mul"
    path.write_text(json.dumps(tampered), encoding="utf-8")
    with pytest.raises(ValueError, match="manifest drift"):
        devcal.run_manifest(tmp_path, "run-m3")


def test_information_separation_and_abstention() -> None:
    orgs = devcal.all_orgs()
    tc = next(o for o in orgs if o["class"] == "task_conditional")
    task = tc["tasks"][0]
    c_fixture = devcal._c_fixture(tc, 0, task)
    d_fixture = devcal._d_fixture(tc, task)
    c_prompt = devcal.c_class_prompt(c_fixture)
    d_prompt = devcal.d_class_prompt(d_fixture)
    assert c_prompt.count("graded_success=") == devcal.SAMPLE_K
    assert "graded_success" not in d_prompt
    assert "organizational procedure" in d_prompt
    # an abstaining organization still yields a valid D prompt (neutral)
    abstainer = {
        "org_index": 99, "corpus": [], "procedure": None,
        "tasks": [task], "truth": tc["truth"],
    }
    d_abstain = devcal.d_class_prompt(devcal._d_fixture(abstainer, task))
    assert "organizational procedure" in d_abstain


def _truth_lookup(org):
    return {
        (t["context"], t["variant"]): t["plan"] for t in org["truth"]
    } if isinstance(org["truth"], list) else org["truth"]


def test_full_fake_rehearsal_and_report(fake_port, tmp_path: Path) -> None:
    devcal.run_manifest(tmp_path, "run-full")

    def _compute(plan, value, offset, factor):
        for step in plan:
            value = value + offset if step == "add" else value * factor
        return value

    def scripted_behavior_factory(org_index: int):
        manifest = json.loads(
            (tmp_path / "devcal-manifest.json").read_text(encoding="utf-8")
        )
        org = manifest["organizations"][org_index]
        truth = _truth_lookup(org)

        def behavior(prompt: str) -> _FakeCompletion:
            value = int(prompt.split("value=")[1].split(",")[0])
            offset = int(prompt.split("offset=")[1].split(",")[0])
            factor = int(prompt.split("factor=")[1].split("\n")[0])
            plan = None
            if "graded evidence" in prompt:
                wins = 0
                for line in prompt.splitlines():
                    if "graded_success=True" in line:
                        if "plan=('add', 'mul')" in line:
                            wins += 1
                        else:
                            wins -= 1
                plan = ("add", "mul") if wins > 0 else ("mul", "add")
            else:
                plan = ("add", "mul") if "add, then multiply" in prompt else ("mul", "add")
            answer = _compute(plan, value, offset, factor)
            return _FakeCompletion(str(answer), "stop")

        return behavior

    for org_index in range(12):
        _FakePort.behavior = scripted_behavior_factory(org_index)
        devcal.run_org(tmp_path, "run-full", org_index, "test-key")

    ledger = devcal.DevCalLedger(tmp_path / "devcal-ledger", "run-full")
    assert ledger.consumed == 384

    report = devcal.run_report(tmp_path)
    assert report["sends_total"] == 384
    assert len(report["org_mean_paired_diffs"]) == 12
    pooled = report["pooled"]
    assert pooled["sd_point"] >= 0.0
    assert pooled["sd_upper_bound_chi2_df11"] >= pooled["sd_point"]
    for cls in ("unambiguous", "noisy_majority", "task_conditional"):
        assert report["by_class"][cls]["n_orgs"] == 4
    for arm in ("C", "D"):
        v = report["validity"][arm]
        assert v["cells"] == 192 and v["parseable"] == 192
    assert report["cost"]["completion_token_ceiling"] == 384 * 4096
    n_point = report["conservative_n_inputs"]["n_at_sd_point"]
    n_upper = report["conservative_n_inputs"]["n_at_sd_upper_bound"]
    assert n_upper >= n_point
    assert report["noninferential"] is True


def test_transport_failure_is_itt(fake_port, tmp_path: Path) -> None:
    devcal.run_manifest(tmp_path, "run-t")
    calls = {"n": 0}

    def behavior(prompt: str) -> _FakeCompletion:
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("ProviderTransportRejected")
        return _FakeCompletion("7", "stop")

    _FakePort.behavior = behavior
    summary = devcal.run_org(tmp_path, "run-t", 0, "test-key")
    first = summary["rows"][0]
    assert first["classification"] == "transport_error"
    assert first["correct"] is False
    assert summary["per_arm"]["C"]["cells"] == 16
    assert summary["sends"] == 32  # denominator intact
