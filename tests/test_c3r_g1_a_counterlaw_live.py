"""Offline regressions for the SECOND real-data GLM G1 exploratory trial."""

import hashlib
import importlib.util
import json
from pathlib import Path

from resonance_world.c3r_g1_model_boundary import ModelChoiceCompletion
from resonance_world.c3r_g1_zai_transport import PhysicalSendLedger


def _load():
    filename = (
        Path(__file__).resolve().parents[1] / "scripts" /
        "run_c3r_g1_a_counterlaw_live.py"
    )
    spec = importlib.util.spec_from_file_location("c3r_real_a_counterlaw_cli", filename)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    # Local source defines a dataclass that requires registration.
    import sys

    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_plan_is_eight_calls_with_two_three_arm_holdouts() -> None:
    x = _load()
    planned = x.plan()
    assert len(planned) == 8
    assert [p.stage for p in planned] == [
        "development", "development", *["qualification"] * 6,
    ]
    assert [p.arm for p in planned] == [
        "learned", "learned", "learned", "fresh", "placebo",
        "learned", "fresh", "placebo",
    ]
    assert len({p.task.task_id for p in planned[:2]}) == 2
    assert len({p.task.task_id for p in planned[2:]}) == 2
    assert set(p.task.task_id for p in planned[:2]).isdisjoint(
        p.task.task_id for p in planned[2:]
    )
    assert all("A" not in p.task.context for p in planned)


def test_mock_provider_uses_real_feedback_only_for_learned_arm() -> None:
    x = _load()
    ledger = PhysicalSendLedger(8)

    class Fake:
        def __init__(self):
            self.calls = []

        def complete(self, req):
            self.calls.append(req)
            ordinal = ledger.reserve(
                request_digest=hashlib.sha256(req.prompt().encode()).hexdigest(),
            )
            ledger.finish(ordinal, http_status=200)
            if req.stage == "development":
                answer = "B" if len(req.feedback) == 0 else "A"
            elif req.feedback and any(
                f.success is False for f in req.feedback
            ):
                answer = "A"
            else:
                answer = "B"
            return ModelChoiceCompletion(answer, "glm-5.3", finish_reason="stop")

    port = Fake()
    report = x.run_trial(port, ledger)
    assert len(port.calls) == 8
    assert ledger.consumed == 8
    assert report["development_accepted"] == 2
    assert report["development_correct"] == 1
    assert report["qualification"]["learned"]["correct"] == 2
    assert report["qualification"]["fresh"]["correct"] == 0
    assert report["qualification"]["placebo"]["correct"] == 0
    assert report["fully_analyzable_triplets"] == 2
    assert report["scientific_acceptance"] is False
    assert [len(req.feedback) for req in port.calls] == [
        0, 1, 2, 0, 2, 2, 0, 2,
    ]
    assert all(
        all(f.plan == x.PLANS["B"] and f.success is True for f in req.feedback)
        for req in (port.calls[4], port.calls[7])
    )
    assert all(not req.feedback for req in (port.calls[3], port.calls[6]))
    assert "C3R_ZAI_API_KEY" not in json.dumps(report)


def test_first_failed_provider_call_preserves_all_eight_logical_rows() -> None:
    x = _load()
    ledger = PhysicalSendLedger(8)

    class Bad:
        count = 0

        def complete(self, _request):
            self.count += 1
            raise RuntimeError("private provider error")

    port = Bad()
    result = x.run_trial(port, ledger)
    assert port.count == 1
    assert len(result["observations"]) == 8
    assert result["observations"][0]["status"] == "adapter_exception"
    assert all(
        item["status"] == "not_sent_after_failure"
        for item in result["observations"][1:]
    )
    assert result["fully_analyzable_triplets"] == 0
    assert "private provider error" not in json.dumps(result)


def test_default_cli_dry_run_never_reads_provider_credentials(
    monkeypatch, capsys,
) -> None:
    x = _load()
    monkeypatch.delenv("C3R_ZAI_API_KEY", raising=False)
    assert x.main([]) == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["status"] == "offline_no_provider_sends"
    assert summary["expected_sends"] == 8
    assert summary["scientific_acceptance"] is False
