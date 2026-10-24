"""Offline checks for two genuine-control readiness probes (no API calls)."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

from resonance_world.c3r_g1_model_boundary import ModelChoiceCompletion


def _probe():
    scripts = Path(__file__).resolve().parents[1] / "scripts"
    sys.path.insert(0, str(scripts))
    spec = importlib.util.spec_from_file_location(
        "c3r_control_probe_fixture", scripts / "run_c3r_g1_control_readiness_probe.py",
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_control_probe_accepts_both_short_answers_without_private_grade():
    probe = _probe()

    class Port:
        def complete_prompt(self, prompt):
            assert "success=true" not in prompt
            assert "success=false" not in prompt
            return ModelChoiceCompletion(
                output="A", model_id="glm-5.3", physical_sends_reported=1,
                finish_reason="stop", prompt_tokens_reported=111,
                completion_tokens_reported=1, reasoning_tokens_reported=0,
            )

    report = probe.run_control_probes(Port)
    assert report["readiness_passed"] is True
    assert report["technical_physical_send_reservations"] == 2
    assert report["requested_thinking_mode"] == "enabled"
    assert report["reasoning_effort_requested"] == "low"
    assert report["source_task_grade_used"] is False
    assert report["counts_as_g1_experiment"] is False
    assert report["scientific_acceptance"] is False
    assert "Reply exactly" not in json.dumps(report)


def test_probe_rejects_invalid_answers_and_reasoning_length_exhaustion():
    probe = _probe()
    class LongAnswer:
        def complete_prompt(self, prompt):
            return ModelChoiceCompletion(
                output="A", model_id="glm-5.3",
                physical_sends_reported=1, finish_reason="length",
                completion_tokens_reported=512,
                reasoning_tokens_reported=509,
            )

    report = probe.run_control_probes(LongAnswer)
    assert report["readiness_passed"] is False
    assert all(x["status"] == "incomplete_or_invalid" for x in report["observations"])


def test_probe_redacts_transport_errors_and_attempts_both_arms():
    probe = _probe()
    calls = []
    class ErrorPort:
        def complete_prompt(self, prompt):
            calls.append(1)
            raise RuntimeError("secret provider body should never leak")

    report = probe.run_control_probes(ErrorPort)
    assert len(calls) == 2
    assert report["readiness_passed"] is False
    assert all(x["failure_class"] == "RuntimeError" for x in report["observations"])
    assert "secret provider body" not in json.dumps(report)
    assert probe.main([]) == 0
