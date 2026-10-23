"""Credential-free complete crossed G1 live-runner contract tests."""

from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest

from resonance_world.c3r_g1_crossed_plan import make_plan
from resonance_world.c3r_g1_model_boundary import ModelChoiceCompletion


def _load():
    name = "c3r_g1_fourth_crossed_live_test_script"
    path = Path(__file__).resolve().parents[1] / "scripts" / "run_c3r_g1_fourth_crossed_live.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class FakePort:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail

    def complete_prompt(self, prompt: str) -> ModelChoiceCompletion:
        if self.fail:
            raise TimeoutError("do not echo secret provider failure")
        return ModelChoiceCompletion(
            output="A", model_id="glm-5.3", physical_sends_reported=1,
            prompt_tokens_reported=70, completion_tokens_reported=11,
            reasoning_tokens_reported=8, finish_reason="stop",
        )


def _workspace(tmp_path: Path) -> Path:
    root = tmp_path / "internal"
    root.mkdir(mode=0o700)
    return root


def test_full_crossed_mock_completes_16_then_24_without_grade_leaks(
    tmp_path: Path,
) -> None:
    x = _load()
    root = _workspace(tmp_path)
    report = x.run_crossed_live(
        run_id="g1-crossed-live-01", workspace=root,
        target_seed=os.urandom(32), port_factory=FakePort,
        max_workers=4,
    )
    assert report["plan_digest"] == make_plan().public_digest
    assert report["physical_sends_reserved"] == 40
    assert report["status_counts"] == {"accepted": 40}
    assert len(report["records"]) == 40
    assert sum(row["stage"] == "development" for row in report["records"]) == 16
    assert sum(row["stage"] == "qualification" for row in report["records"]) == 24
    assert sum(row["correct"] is True for row in report["records"][:16]) == 8
    assert report["qualification_by_arm"]["learned"]["prescribed"] == 8
    assert report["qualification_by_arm"]["fresh"]["prescribed"] == 8
    assert report["qualification_by_arm"]["neutral"]["prescribed"] == 8
    assert report["external_auditor_required"] is False
    assert report["scientific_acceptance"] is False
    for i in range(40):
        files = list(root.glob(f"g1-live-*/send-{i:02d}.json"))
        assert len(files) == 1
        assert files[0].stat().st_mode & 0o077 == 0
    serialized = json.dumps(report)
    assert "private_target_seed" not in serialized
    assert "signed_source_receipt" not in serialized
    assert "Past development evidence" not in serialized
    assert "secret provider failure" not in serialized


def test_neutral_history_exact_char_length_without_actual_grade_or_choice() -> None:
    x = _load()
    task = make_plan().cells[0].qualification[0]
    source = make_plan().cells[0].development
    rows = tuple({
        "task_id": item.task_id, "choice": "B" if i else "A",
        "correct": i == 0,
    } for i, item in enumerate(source))
    actual = x.prompt_for(task, source_history=rows, arm="learned")
    neutral = x.prompt_for(task, source_history=rows, arm="neutral")
    fresh = x.prompt_for(task, source_history=rows, arm="fresh")
    assert len(actual) == len(neutral)
    assert "success=true " in actual and "success=false" in actual
    assert "choice=A; success=true " not in neutral
    assert "choice=B; success=false" not in neutral
    assert "choice=?; success=?????" in neutral
    assert "choice=" not in fresh
    assert "success=" not in fresh
    assert x.prompt_for(task, source_history=(), arm="development").endswith(
        "Reply exactly A or B."
    )


def test_provider_errors_stay_in_denominator_with_no_automatic_retries(
    tmp_path: Path,
) -> None:
    x = _load()
    report = x.run_crossed_live(
        run_id="g1-crossed-failure-01", workspace=_workspace(tmp_path),
        target_seed=os.urandom(32),
        port_factory=lambda: FakePort(fail=True),
        max_workers=3,
    )
    assert report["physical_sends_reserved"] == 16
    assert report["source_gate_closed"] is True
    assert report["source_contexts_eligible"] == 0
    assert report["source_contexts_incomplete"] == 8
    assert report["status_counts"] == {
        "provider_error": 16, "not_sent": 24,
    }
    assert sum(row["correct"] is None for row in report["records"]) == 40
    assert sum(row["choice_sha256"] is None for row in report["records"]) == 40
    assert len([row for row in report["records"]
                if row["stage"] == "qualification"]) == 24
    assert report["scientific_acceptance"] is False
    assert "do not echo secret provider failure" not in json.dumps(report)


def test_same_run_id_rejected_before_any_additional_provider_attempt(
    tmp_path: Path,
) -> None:
    x = _load()
    path = _workspace(tmp_path)
    count = [0]

    class CountingPort:
        def complete_prompt(self, prompt):
            count[0] += 1
            return FakePort().complete_prompt(prompt)

    def invoke():
        return x.run_crossed_live(
            run_id="g1-crossed-replay-01", workspace=path,
            target_seed=os.urandom(32), port_factory=CountingPort,
            max_workers=2,
        )
    assert invoke()["physical_sends_reserved"] == 40
    assert count[0] == 40
    with pytest.raises(FileExistsError):
        invoke()
    assert count[0] == 40


def test_provider_credential_is_required_only_for_explicit_live(monkeypatch, capsys):
    x = _load()
    monkeypatch.delenv("C3R_ZAI_API_KEY", raising=False)
    assert x.main([]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "offline_plan_only"
    assert report["physical_sends"] == 0
    with pytest.raises(SystemExit, match="missing"):
        x.main(["--live", "--workspace", "/tmp/unused-credential-free"])


def test_duplicate_attempt_slot_fails_before_provider_dispatch(tmp_path: Path):
    x = _load()
    ledger = x.DurableAttemptJournal(
        _workspace(tmp_path), run_id="g1-crossed-reserve-01",
    )
    ledger.reserve(index=0, prompt="one", model=x.MODEL, route="coding")
    with pytest.raises(ValueError, match="duplicate"):
        ledger.reserve(index=0, prompt="other", model=x.MODEL, route="coding")
    assert ledger.count == 1
    assert not list(ledger.root.glob("send-01.json"))



def test_one_source_failed_context_does_not_block_seven_healthy_triplets(
    tmp_path: Path,
) -> None:
    x = _load()

    class FailsOnlyOneSource:
        def complete_prompt(self, prompt: str) -> ModelChoiceCompletion:
            if "dev-g1x-tex-00-0" in prompt:
                raise TimeoutError("private provider failure should never leak")
            return FakePort().complete_prompt(prompt)

    result = x.run_crossed_live(
        run_id="g1-crossed-partial-01",
        workspace=_workspace(tmp_path),
        target_seed=os.urandom(32),
        port_factory=FailsOnlyOneSource,
        max_workers=3,
    )
    assert result["source_contexts_eligible"] == 7
    assert result["source_contexts_incomplete"] == 1
    assert result["physical_sends_reserved"] == 37
    assert result["status_counts"] == {
        "accepted": 36, "provider_error": 1, "not_sent": 3,
    }
    affected = [
        row for row in result["records"]
        if row["unit_id"] == "g1x-tex-00"
        and row["stage"] == "qualification"
    ]
    assert len(affected) == 3
    assert all(row["not_sent_reason"] == "incomplete_source_for_context"
               for row in affected)
    assert all(row["correct"] is None for row in affected)
    assert result["qualification_by_arm"]["learned"]["prescribed"] == 8
    assert result["scientific_acceptance"] is False
