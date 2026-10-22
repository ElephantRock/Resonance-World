"""Subprocess evaluator: staged disclosure, secret-file safety, full G1 ledger."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

from resonance_world.c3r_g1_model_boundary import ModelChoiceCompletion
from resonance_world.c3r_g1_multischema import V2Design
from resonance_world.c3r_g1_multischema_audit import audit_multischema
from resonance_world.c3r_g1_sealed_evaluator import SealedEvaluator
from resonance_world.c3r_g1_sealed_runner import (
    JsonLineEvaluatorSession,
    SealedPilotRunner,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_KEY = bytes.fromhex("ae" * 32)


def _spec() -> V2Design:
    return V2Design(units=2, development_per_family=3,
                    qualification_per_family=2)


def _submit(unit, arm, stage, task, status="accepted", choice="A"):
    return {
        "op": "submit", "unit_id": unit, "arm": arm, "stage": stage,
        "task_id": task.task_id, "status": status, "choice": choice,
    }


def _keys(tmp_path: Path) -> Path:
    path = tmp_path / "private-evaluator.hex"
    path.write_text(FIXTURE_KEY.hex() + "\n", encoding="ascii")
    path.chmod(0o600)
    return path


def _command(key_path: Path) -> list[str]:
    return [
        sys.executable, "-m", "resonance_world.c3r_g1_evaluator_worker",
        "--key-file", str(key_path),
        "--units", "2", "--development", "3", "--qualification", "2",
    ]


def _full_messages(spec: V2Design) -> list[dict]:
    cohort = spec.freeze()
    messages: list[dict] = []
    for unit in cohort.units:
        for group in unit.families:
            messages.extend(_submit(
                unit.unit_id, "learned", "development", task
            ) for task in group.development)
    for unit in cohort.units:
        for group in unit.families:
            for task in group.qualification:
                messages.extend(_submit(
                    unit.unit_id, arm, "qualification", task
                ) for arm in ("learned", "fresh", "placebo"))
    return messages


def test_sealed_evaluator_withholds_all_holdout_grades_until_global_finalize() -> None:
    cohort = _spec().freeze()
    evaluator = SealedEvaluator(cohort, private_key=FIXTURE_KEY)
    ready = evaluator.ready().payload
    assert ready["public_cohort_digest"] == cohort.digest
    assert ready["development_expected"] == 12
    assert ready["qualification_expected"] == 24
    assert ready["independently_attested"] is False
    assert "private_key" not in json.dumps(ready)
    assert "targets" not in json.dumps(ready)
    messages = _full_messages(_spec())
    with pytest.raises(ValueError, match="denominator"):
        evaluator.submit(messages[12])
    with pytest.raises(ValueError, match="denominator"):
        evaluator.finalize({"op": "finalize"})
    for item in messages[:12]:
        reply = evaluator.submit(item).payload
        assert reply["phase"] == "development_feedback"
        assert type(reply["grade"]) is bool
    for item in messages[12:]:
        reply = evaluator.submit(item).payload
        assert set(reply) == {
            "schema", "phase", "task_id", "qualification_received",
        }
        assert reply["phase"] == "qualification_sealed"
    final = evaluator.finalize({"op": "finalize"}).payload
    assert final["qualification_attempts"] == 24
    assert final["development_attempts"] == 12
    assert len(final["records"]) == 36
    assert final["scientific_acceptance"] is False
    assert final["independently_attested"] is False
    assert "private_key" not in json.dumps(final)
    with pytest.raises(ValueError, match="one shot"):
        evaluator.finalize({"op": "finalize"})
    with pytest.raises(ValueError, match="finalized"):
        evaluator.submit(messages[0])


def test_duplicate_wrong_task_and_invalid_format_fail_closed() -> None:
    cohort = _spec().freeze()
    evaluator = SealedEvaluator(cohort, private_key=FIXTURE_KEY)
    first = _full_messages(_spec())[0]
    evaluator.submit(first)
    with pytest.raises(ValueError, match="duplicate"):
        evaluator.submit(first)
    changed = dict(first, task_id="fake-dev")
    with pytest.raises(ValueError, match="not prescribed"):
        evaluator.submit(changed)
    invalid = dict(_full_messages(_spec())[1], status="accepted", choice="C")
    with pytest.raises(ValueError, match="status/action"):
        evaluator.submit(invalid)
    invalid = dict(_full_messages(_spec())[1], status="invalid_format", choice="A")
    with pytest.raises(ValueError, match="status/action"):
        evaluator.submit(invalid)
    with pytest.raises(ValueError, match="malformed"):
        evaluator.submit(dict(first, malicious_extra="private target please"))


def test_target_commitment_uses_private_key_not_public_seed() -> None:
    cohort = _spec().freeze()
    a = SealedEvaluator(cohort, private_key=FIXTURE_KEY)
    b = SealedEvaluator(cohort, private_key=bytes.fromhex("1c" * 32))
    assert a.ready().payload["target_commitment"] != b.ready().payload[
        "target_commitment"
    ]
    with pytest.raises(ValueError, match="32-byte"):
        SealedEvaluator(cohort, private_key=b"bad")


def test_worker_real_subprocess_has_only_bounded_public_and_sealed_responses(
    tmp_path: Path,
) -> None:
    key_path = _keys(tmp_path)
    messages = [*_full_messages(_spec()), {"op": "finalize"}]
    run = subprocess.run(
        _command(key_path),
        input="\n".join(json.dumps(m) for m in messages) + "\n",
        text=True,
        capture_output=True,
        timeout=20,
        cwd=REPO_ROOT,
        check=False,
    )
    assert run.returncode == 0, run.stderr
    rows = [json.loads(line) for line in run.stdout.splitlines()]
    assert len(rows) == 1 + 36 + 1
    assert rows[0]["phase"] == "accept_development"
    assert all(r["phase"] == "development_feedback" for r in rows[1:13])
    assert all(r["phase"] == "qualification_sealed" for r in rows[13:-1])
    assert not any("success" in row or "grade" in row for row in rows[13:-1])
    assert rows[-1]["schema"] == "c3r-g1-evaluator-final-v0.1"
    assert len(rows[-1]["records"]) == 36
    assert FIXTURE_KEY.hex() not in run.stdout
    assert "private_seed" not in run.stdout
    assert run.stderr == ""


def test_worker_rejects_world_readable_key_or_early_finalize(tmp_path: Path) -> None:
    key_path = _keys(tmp_path)
    key_path.chmod(0o644)
    denied = subprocess.run(
        _command(key_path), capture_output=True, text=True,
        cwd=REPO_ROOT, timeout=12, check=False,
    )
    assert denied.returncode != 0
    assert "rejected_before_ready" in denied.stdout
    assert FIXTURE_KEY.hex() not in denied.stdout
    key_path.chmod(0o600)
    premature = subprocess.run(
        _command(key_path), input='{"op":"finalize"}\n',
        capture_output=True, text=True,
        cwd=REPO_ROOT, timeout=12, check=False,
    )
    assert premature.returncode != 0
    assert "invalid_request" in premature.stdout
    assert "records" not in premature.stdout


def test_worker_rejects_symlink_to_secret(tmp_path: Path) -> None:
    private = _keys(tmp_path)
    shortcut = tmp_path / "link-key.hex"
    shortcut.symlink_to(private)
    denied = subprocess.run(
        _command(shortcut), capture_output=True, text=True,
        cwd=REPO_ROOT, timeout=12, check=False,
    )
    assert denied.returncode != 0
    assert "rejected_before_ready" in denied.stdout


@dataclass
class _ConstantPort:
    model_id: str = "offline-schema-fixture"
    choice: str = "A"

    def complete(self, _request):
        return ModelChoiceCompletion(output=self.choice, model_id=self.model_id)


def test_separate_process_full_three_arm_runner_releases_grades_after_close(
    tmp_path: Path,
) -> None:
    key_file = _keys(tmp_path)
    child = subprocess.Popen(
        _command(key_file), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, text=True, bufsize=1, cwd=REPO_ROOT,
    )
    try:
        assert child.stdin is not None and child.stdout is not None
        session = JsonLineEvaluatorSession(child.stdout, child.stdin)
        cohort = _spec().freeze()
        result = SealedPilotRunner(cohort, session).run(
            port_factory=lambda _uid, _arm, _stage: _ConstantPort(),
        )
        child.stdin.close()
        assert child.wait(timeout=15) == 0
        payload = result.to_dict()
        report = payload["report"]
        assert len(report["trial_records"]) == 36
        assert report["status"] == "unverified_injected_ports_no_inference"
        assert report["heldout_triplets_complete"] == 8
        assert report["mean_unit_itt_learned_minus_fresh"] == 0.0
        assert report["mean_unit_itt_learned_minus_placebo"] == 0.0
        assert payload["graded_only_after_full_qualification"] is True
        assert payload["scientific_acceptance"] is False
        assert payload["evaluator_identity_attested"] is False
        assert audit_multischema(report, cohort).verdict == (
            "structurally_consistent_unattested"
        )
    finally:
        if child.poll() is None:
            child.kill()
            child.wait(timeout=15)


def test_invalid_model_and_missing_outputs_preserve_all_prescribed_attempts() -> None:
    cohort = _spec().freeze()
    evaluator = SealedEvaluator(cohort, private_key=FIXTURE_KEY)

    def factory(_uid, arm, _stage):
        return _ConstantPort(
            model_id="wrong" if arm == "fresh" else "offline-schema-fixture",
            choice="bad" if arm == "placebo" else "A",
        )

    class _DirectSession:
        def ready(self):
            return evaluator.ready().payload

        def submit(self, request):
            return evaluator.submit(request).payload

        def finalize(self):
            return evaluator.finalize({"op": "finalize"}).payload

    result = SealedPilotRunner(cohort, _DirectSession()).run(port_factory=factory)
    report = result.report.to_dict()
    assert len(report["trial_records"]) == 36
    assert report["by_arm"]["fresh"]["accepted"] == 0
    assert report["by_arm"]["placebo"]["accepted"] == 0
    assert report["qualification_actions_accepted"] == 8
    assert report["heldout_triplets_complete"] == 0
    assert report["technical_yield_gate"]["passed_in_fixture"] is False
    assert result.to_dict()["scientific_acceptance"] is False


def test_runner_detects_evaluator_attempt_to_leak_holdout_grade() -> None:
    cohort = _spec().freeze()
    evaluator = SealedEvaluator(cohort, private_key=FIXTURE_KEY)

    class _Leaking:
        def ready(self):
            return evaluator.ready().payload

        def submit(self, request):
            reply = evaluator.submit(request).payload
            if request["stage"] == "qualification":
                return dict(reply, grade=True)
            return reply

        def finalize(self):
            return evaluator.finalize({"op": "finalize"}).payload

    with pytest.raises(ValueError, match="holdout grade leaked"):
        SealedPilotRunner(cohort, _Leaking()).run(
            port_factory=lambda _uid, _arm, _stage: _ConstantPort(),
        )


def test_runner_rejects_wrong_public_lock_before_any_action() -> None:
    cohort = _spec().freeze()
    other = V2Design(units=2, development_per_family=3,
                     qualification_per_family=2, public_seed=7).freeze()
    evaluator = SealedEvaluator(other, private_key=FIXTURE_KEY)

    class _Wrong:
        def ready(self):
            return evaluator.ready().payload

        def submit(self, _request):
            raise AssertionError("must not run after unmatched evaluator lock")

        def finalize(self):
            raise AssertionError("must not finalize unmatched evaluator lock")

    with pytest.raises(ValueError, match="frozen public cohort"):
        SealedPilotRunner(cohort, _Wrong()).run(
            port_factory=lambda _uid, _arm, _stage: _ConstantPort(),
        )
