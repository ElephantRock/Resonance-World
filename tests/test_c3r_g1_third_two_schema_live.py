"""Offline regressions for third real two-schema, neutral-placebo G1 trial."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

from resonance_world.c3r_g1_model_boundary import ModelChoiceCompletion
from resonance_world.c3r_g1_zai_transport import PhysicalSendLedger


def _module():
    name = "third_g1_two_schema_trial"
    path = (
        Path(__file__).resolve().parents[1] / "scripts" /
        "run_c3r_g1_third_two_schema_live.py"
    )
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_lock_two_families_opposite_targets_and_eight_actions() -> None:
    x = _module()
    assert len(x.ORDER) == 8
    assert x.TARGETS == {"arithmetic": "B", "text": "A"}
    assert len({x.SOURCE[k].context for k in x.SOURCE}) == 2
    for family in x.SOURCE:
        assert x.SOURCE[family].task_id != x.HOLDOUT[family].task_id
        assert x.SOURCE[family].public_tuple() != x.HOLDOUT[family].public_tuple()
        assert x.apply_choice(x.HOLDOUT[family], "A") != x.apply_choice(
            x.HOLDOUT[family], "B"
        )
    assert x.experiment_lock() == x.experiment_lock()
    assert x.experiment_lock()["planned_provider_calls"] == 8
    assert x.experiment_lock()["scientific_acceptance"] is False


def test_neutral_placebo_does_not_leak_true_choice_or_grade() -> None:
    x = _module()
    task = x.HOLDOUT["arithmetic"]
    actual = x.Feedback(x.SOURCE["arithmetic"].task_id, task.context, "B", False)
    learned = x.prompt_for(task=task, arm="learned", recorded=actual)
    neutral = x.prompt_for(task=task, arm="placebo", recorded=actual)
    baseline = x.prompt_for(task=task, arm="fresh", recorded=actual)
    assert "choice=B; success=false" in learned
    assert "choice=?; success=?" in neutral
    assert "choice=B" not in neutral and "success=false" not in neutral
    assert len(learned) == len(neutral)
    assert baseline.endswith("(none)")
    changed = x.Feedback(x.SOURCE["arithmetic"].task_id, task.context, "A", True)
    other = x.prompt_for(task=task, arm="placebo", recorded=changed)
    assert "choice=?; success=?" in other
    assert "choice=A;" not in other and "success=true" not in other


def test_model_mock_keeps_denominator_and_never_claims_scientific_evidence() -> None:
    x = _module()
    ledger = PhysicalSendLedger(8)

    class Port:
        calls: list[str] = []

        def complete_prompt(self, prompt):
            self.calls.append(prompt)
            ordinal = ledger.reserve(request_digest="a" * 64)
            ledger.finish(ordinal, http_status=200)
            return ModelChoiceCompletion(
                "A", "glm-5.3", finish_reason="stop",
                completion_tokens_reported=5,
            )

    port = Port()
    result = x.run_trial(port, ledger)
    assert len(port.calls) == ledger.consumed == 8
    assert result["development_accepted"] == 2
    assert result["development_correct"] == 1
    assert result["complete_triplets"] == 2
    assert result["qualifications"]["arithmetic"]["learned"]["correct"] == 0
    assert result["qualifications"]["text"]["fresh"]["correct"] == 1
    assert result["qualifications"]["text"]["placebo"]["correct"] == 1
    assert result["scientific_acceptance"] is False
    assert result["matched_tokens_attested"] is False
    assert result["independent_learner_replication_attested"] is False
    assert "success=false" in port.calls[5]
    assert "choice=?; success=?" in port.calls[2]
    assert "choice=?; success=?" in port.calls[7]
    assert "choice=A;" not in port.calls[2]
    assert "success=true" in port.calls[4]
    assert port.calls[3].endswith("(none)")


def test_transport_failure_aborts_all_remaining_prescribed_actions() -> None:
    x = _module()
    ledger = PhysicalSendLedger(8)

    class Failure:
        count = 0

        def complete_prompt(self, _prompt):
            self.count += 1
            raise RuntimeError("provider private payload")

    failed = Failure()
    result = x.run_trial(failed, ledger)
    assert failed.count == 1
    assert result["observations"][0]["status"] == "adapter_exception"
    assert all(
        row["status"] == "not_sent_after_failure"
        for row in result["observations"][1:]
    )
    assert result["complete_triplets"] == 0
    assert result["prescribed_calls"] == 8
    assert "provider private payload" not in json.dumps(result)


def test_default_run_is_offline_and_credential_free(monkeypatch, capsys) -> None:
    x = _module()
    monkeypatch.delenv("C3R_ZAI_API_KEY", raising=False)
    assert x.main([]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "offline_no_provider_sends"
    assert report["lock"]["planned_provider_calls"] == 8
    assert report["scientific_acceptance"] is False
