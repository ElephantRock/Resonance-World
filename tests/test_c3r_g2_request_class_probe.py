"""Offline tests for the G2 request-class qualification probe.

Covers: the permanent 2-send O_EXCL cap, the deterministic fixture and
prompt shapes (C reads records and names both plans; D receives only
the compiled procedure), classification paths (parseable / empty /
length / transport), informational-correctness marking, exit semantics
(both-complete => proceed-to-freeze interpretation; any failure =>
halt interpretation), and determinism of the fixture. No network.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import scripts.run_c3r_g2_request_class_probe as probe
from resonance_world.c3r_g2_causal_qualification import compile_procedure


class _FakeCompletion:
    def __init__(self, output: str, finish_reason: str) -> None:
        self.output = output
        self.finish_reason = finish_reason
        self.prompt_tokens_reported = 120
        self.completion_tokens_reported = 8


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
    monkeypatch.setattr(probe, "ZaiStandardModelPort", _FakePort)
    _FakePort.behavior = None
    _FakePort.calls = []
    yield _FakePort
    _FakePort.behavior = None
    _FakePort.calls = []


def test_permanent_two_send_cap(tmp_path: Path) -> None:
    ledger = probe.ProbeLedger(tmp_path / "led", "run-x")
    ledger.reserve(0, "c")
    ledger.reserve(1, "d")
    with pytest.raises(RuntimeError, match="permanent 2-send cap"):
        ledger.reserve(1, "double")
    with pytest.raises(RuntimeError, match="exceeds the permanent 2-send cap"):
        ledger.reserve(2, "third")
    # a second ledger over the same directory cannot re-spend the slots
    again = probe.ProbeLedger(tmp_path / "led", "run-y")
    with pytest.raises(RuntimeError, match="cap is exhausted"):
        again.reserve(0, "again")


def test_fixture_deterministic_and_compiled() -> None:
    first = probe.build_fixture()
    second = probe.build_fixture()
    assert first["sample"] == second["sample"]
    assert first["procedure"] == second["procedure"]
    assert first["procedure"] is not None
    assert probe._truth_answer(first) > 0


def test_prompt_shapes() -> None:
    fixture = probe.build_fixture()
    c_prompt = probe.c_class_prompt(fixture)
    d_prompt = probe.d_class_prompt(fixture)
    # C sees graded records and both plans; D sees only the procedure
    assert c_prompt.count("graded_success=") == len(fixture["sample"])
    assert "add-then-multiply" in c_prompt
    assert "graded_success" not in d_prompt
    assert "organizational procedure" in d_prompt
    assert fixture["procedure"] is not None


def test_probe_success_path(fake_port, tmp_path: Path) -> None:
    fixture = probe.build_fixture()
    truth = probe._truth_answer(fixture)

    def behavior(prompt: str) -> _FakeCompletion:
        return _FakeCompletion(str(truth), "stop")

    _FakePort.behavior = behavior
    outcome = probe.run_probe(tmp_path, "run-p", "test-key")
    assert outcome["sends"] == 2
    assert outcome["both_classes_completed"] is True
    assert "NOTHING is launched" in outcome["interpretation"]
    assert all(r["correct_informational"] for r in outcome["rows"])
    assert [c["max_tokens"] for c in _FakePort.calls] == [4096, 4096]
    assert {c["timeout"] for c in _FakePort.calls} == {300.0}


def test_probe_empty_answer_halts(fake_port, tmp_path: Path) -> None:
    _FakePort.behavior = lambda prompt: _FakeCompletion("", "length")
    outcome = probe.run_probe(tmp_path, "run-p2", "test-key")
    assert outcome["both_classes_completed"] is False
    assert all(r["classification"] == "length" for r in outcome["rows"])
    assert "halts" in outcome["interpretation"]


def test_probe_transport_failure_halts(fake_port, tmp_path: Path) -> None:
    def behavior(prompt: str) -> _FakeCompletion:
        raise RuntimeError("ProviderTransportRejected")

    _FakePort.behavior = behavior
    outcome = probe.run_probe(tmp_path, "run-p3", "test-key")
    assert outcome["both_classes_completed"] is False
    assert all(
        r["classification"] == "transport_error" for r in outcome["rows"]
    )


def test_probe_c_class_only_failure_halts(fake_port, tmp_path: Path) -> None:
    fixture = probe.build_fixture()
    truth = probe._truth_answer(fixture)
    seen = {"n": 0}

    def behavior(prompt: str) -> _FakeCompletion:
        seen["n"] += 1
        if "graded evidence" in prompt:
            return _FakeCompletion("", "stop")  # C-class empty
        return _FakeCompletion(str(truth), "stop")

    _FakePort.behavior = behavior
    outcome = probe.run_probe(tmp_path, "run-p4", "test-key")
    assert outcome["both_classes_completed"] is False
    classes = {r["request_class"]: r["classification"] for r in outcome["rows"]}
    assert classes["c_class_interpretation"] == "empty"
    assert classes["d_class_execution"] == "completed_parseable"


def test_wrong_answer_is_informational_not_failure(
    fake_port, tmp_path: Path
) -> None:
    _FakePort.behavior = lambda prompt: _FakeCompletion("1", "stop")
    outcome = probe.run_probe(tmp_path, "run-p5", "test-key")
    # parseable but wrong: the class still COMPLETED (probe measures
    # viability, not effect)
    assert outcome["both_classes_completed"] is True
    assert all(r["correct_informational"] is False for r in outcome["rows"])
