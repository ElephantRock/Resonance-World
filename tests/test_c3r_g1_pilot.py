"""G1 pilot v1: null fixture, frozen splits, source isolation and ITT controls."""

from __future__ import annotations

import json
from dataclasses import dataclass, field

import pytest

from resonance_world.c3r_g1_model_boundary import (
    ModelChoiceCompletion,
    ModelChoiceRequest,
)
from resonance_world.c3r_g1_pilot import (
    PILOT_ARMS,
    PilotDesign,
    PilotLock,
    PilotRunner,
    run_offline_fixture,
)
from resonance_world.c3r_g2 import PLANS


def _small() -> PilotDesign:
    return PilotDesign(
        units=2, development_per_context=3, qualification_per_context=2,
    )


def test_default_pilot_budget_matches_prospective_480_call_design() -> None:
    design = PilotDesign()
    assert design.units == 8
    assert design.contexts_per_unit == 2
    assert design.qualification_triplets == 128
    assert design.required_calls == 480
    frozen = design.freeze()
    assert len(frozen.units) == 8
    assert len(frozen.digest) == 64
    assert frozen == design.freeze()


def test_nonoverlapping_ids_and_public_payloads_across_all_splits_and_units() -> None:
    frozen = PilotDesign().freeze()
    tasks = [
        task for unit in frozen.units for context in unit.contexts
        for task in (*context.development, *context.qualification)
    ]
    assert len(tasks) == 8 * 2 * (6 + 8)
    assert len({task.task_id for task in tasks}) == len(tasks)
    assert len({
        (task.context, task.value, task.offset, task.factor) for task in tasks
    }) == len(tasks)
    assert all("answer" not in task.__dict__ if hasattr(task, "__dict__") else True
               for task in tasks)


def test_rule_counterbalanced_and_invisible_in_public_lock_digest() -> None:
    frozen = PilotDesign().freeze()
    for unit in frozen.units:
        assert {context.hidden_plan for context in unit.contexts} == set(PLANS)
    assert frozen.digest == PilotDesign().freeze().digest
    reversed_lock = PilotLock(
        frozen.design,
        tuple(type(unit)(
            unit.unit_id,
            tuple(type(ctx)(
                ctx.context, PLANS[1] if ctx.hidden_plan == PLANS[0] else PLANS[0],
                ctx.development, ctx.qualification,
            ) for ctx in unit.contexts),
        ) for unit in frozen.units),
    )
    # The digest binds public inputs, NOT hidden evaluator ground truth:
    # an independently signed private evaluator commitment is still needed.
    assert reversed_lock.digest == frozen.digest


def test_null_policy_yields_zero_delta_with_full_triplet_denominator() -> None:
    report = run_offline_fixture()
    payload = report.to_dict()
    assert payload["schema"] == "c3r-g1-three-arm-pilot-v1"
    assert payload["status"] == "offline_fixture_only_no_scientific_inference"
    assert payload["planned_model_calls"] == 480
    assert len(payload["attempt_records"]) == 480
    assert len(payload["attempt_trace_sha256"]) == 64
    assert all(record["action"] in ("A", "B", None)
               for record in payload["attempt_records"])
    assert all(
        record["status"] == "accepted" and record["success"] in (True, False)
        for record in payload["attempt_records"]
    )
    assert payload["independent_learner_units"] == 8
    assert payload["heldout_triplets_prescribed"] == 128
    assert payload["heldout_triplets_accepted_all_arms"] == 128
    assert payload["qual_attempts_prescribed"] == 384
    assert payload["qual_actions_accepted"] == 384
    assert payload["mean_unit_itt_learned_minus_fresh"] == 0
    assert payload["mean_unit_itt_learned_minus_placebo"] == 0
    assert payload["technical_yield_gate"]["passed_in_fixture"] is True
    assert payload["technical_yield_gate"]["authority_to_start_live_campaign"] is False
    assert payload["development_accepted"] == 96
    assert {arm: payload["qualification_by_arm"][arm]["prescribed"]
            for arm in PILOT_ARMS} == {arm: 128 for arm in PILOT_ARMS}
    assert all(payload["qualification_by_arm"][arm]["itt_successes"] == 64
               for arm in PILOT_ARMS)
    assert payload["scientific_acceptance"] is False
    assert payload["statistical_test_performed"] is False
    assert payload["independent_evaluator_attested"] is False
    assert payload["actual_provider_sends_verified"] is False
    assert report.canonical_bytes() == run_offline_fixture().canonical_bytes()


def test_source_development_happens_only_in_learned_arm() -> None:
    report = run_offline_fixture(_small())
    assert sum(row.stage == "development" for row in report.rows) == 2 * 2 * 3
    assert all(row.arm == "learned" for row in report.rows
               if row.stage == "development")
    assert sum(row.stage == "qualification" for row in report.rows) == 2 * 2 * 2 * 3
    assert len(report.rows) == _small().required_calls
    assert all(trained == placebo == 3
               for _, _, trained, placebo in report.history_counts)
    assert all(row.status == "accepted" for row in report.rows)


@dataclass
class _CapturePort:
    model_id: str
    behavior: str = "A"
    seen: list[ModelChoiceRequest] = field(default_factory=list)

    def complete(self, request: ModelChoiceRequest) -> ModelChoiceCompletion:
        self.seen.append(request)
        return ModelChoiceCompletion(self.behavior, self.model_id)


def test_fresh_never_sees_feedback_and_placebo_receives_sham_of_same_length() -> None:
    created: dict[tuple[str, str], list[_CapturePort]] = {}

    def factory(unit_id, arm):
        port = _CapturePort("offline-fixture-model")
        created.setdefault((unit_id, arm), []).append(port)
        return port

    report = PilotRunner(_small().freeze()).run(port_factory=factory)
    assert report.to_dict()["scientific_acceptance"] is False
    for unit_index in range(2):
        unit_id = f"pilot-unit-{unit_index:03d}"
        learned_development, learned = created[unit_id, "learned"]
        (fresh,) = created[unit_id, "fresh"]
        (placebo,) = created[unit_id, "placebo"]
        assert len(learned_development.seen) == 2 * 3
        assert all(r.stage == "development" for r in learned_development.seen)
        assert all(r.stage == "qualification" for r in learned.seen)
        assert learned_development is not learned
        assert all(not request.feedback for request in fresh.seen)
        assert all(request.stage == "qualification" for request in fresh.seen)
        assert all(request.stage == "qualification" for request in placebo.seen)
        assert len(learned.seen) == 2 * 2
        assert len(fresh.seen) == len(placebo.seen) == 2 * 2
        for q_learned in (r for r in learned.seen if r.stage == "qualification"):
            sham = next(r for r in placebo.seen if r.task.task_id == q_learned.task.task_id)
            assert len(q_learned.feedback) == len(sham.feedback) == 3
            assert [(x.task_id, x.plan) for x in q_learned.feedback] == [
                (x.task_id, x.plan) for x in sham.feedback
            ]


def test_never_feedback_qualification_grades_to_any_subsequent_task() -> None:
    created = {}

    def factory(unit_id, arm):
        port = _CapturePort("offline-fixture-model")
        created.setdefault((unit_id, arm), []).append(port)
        return port

    PilotRunner(_small().freeze()).run(port_factory=factory)
    for ports in created.values():
        for port in ports:
            for request in port.seen:
                assert all("qualification" not in item.task_id for item in request.feedback)
                assert all(item.task_id != request.task.task_id for item in request.feedback)
                assert all(item.context == request.task.context for item in request.feedback)


def test_rejects_reused_port_across_arms_and_units() -> None:
    singleton = _CapturePort("offline-fixture-model")
    with pytest.raises(ValueError, match="must be distinct"):
        PilotRunner(_small().freeze()).run(port_factory=lambda _u, _a: singleton)
    shared = [_CapturePort("offline-fixture-model") for _ in range(4)]
    count = 0

    def cross_unit_reuse(_unit, _arm):
        nonlocal count
        port = shared[count % 4]
        count += 1
        return port

    with pytest.raises(ValueError, match="cannot reuse"):
        PilotRunner(_small().freeze()).run(port_factory=cross_unit_reuse)


def test_wrong_model_or_unparseable_answers_count_as_itt_failures() -> None:
    def factory(_unit, arm):
        if arm == "fresh":
            return _CapturePort("different-model")
        if arm == "placebo":
            return _CapturePort("offline-fixture-model", "The answer is A")
        return _CapturePort("offline-fixture-model", "A")

    result = PilotRunner(_small().freeze()).run(port_factory=factory)
    data = result.to_dict()
    assert data["heldout_triplets_prescribed"] == 8
    assert data["qual_actions_accepted"] == 8
    assert data["heldout_triplets_accepted_all_arms"] == 0
    assert data["heldout_triplet_yield"] == 0
    assert len(data["attempt_records"]) == _small().required_calls
    assert sum(
        row["stage"] == "qualification" and row["status"] == "wrong_model"
        for row in data["attempt_records"]
    ) == 8
    assert data["technical_yield_gate"]["passed_in_fixture"] is False
    assert data["qualification_by_arm"]["fresh"]["failures_by_status"]["wrong_model"] == 8
    assert data["qualification_by_arm"]["placebo"]["failures_by_status"]["invalid_format"] == 8
    assert all(row["accepted_by_arm"]["fresh"] == 0 for row in data["per_unit"])
    assert all(row["accepted_by_arm"]["placebo"] == 0 for row in data["per_unit"])
    assert data["scientific_acceptance"] is False


def test_provider_exception_retains_failed_tasks_in_denominator() -> None:
    class AlwaysRaises:
        def complete(self, _request):
            raise TimeoutError("synthetic transport error")

    def factory(_unit, arm):
        return AlwaysRaises() if arm == "fresh" else _CapturePort("offline-fixture-model")

    report = PilotRunner(_small().freeze()).run(port_factory=factory)
    data = report.to_dict()
    assert data["planned_model_calls"] == 36
    assert len(report.rows) == 36
    assert data["qual_attempts_prescribed"] == 24
    assert data["qual_actions_accepted"] == 16
    assert data["heldout_triplets_accepted_all_arms"] == 0
    assert sum(row.status == "adapter_exception" for row in report.rows) == 8


@dataclass
class _FeedbackPolicy:
    model_id: str

    def complete(self, request: ModelChoiceRequest) -> ModelChoiceCompletion:
        if not request.feedback:
            choice = "A"
        else:
            last = request.feedback[-1]
            choice = (
                "A" if last.plan == PLANS[0] else "B"
            ) if last.success else (
                "B" if last.plan == PLANS[0] else "A"
            )
        return ModelChoiceCompletion(choice, self.model_id)


def test_feedback_sensitive_fixture_exercises_positive_control_no_scientific_claim() -> None:
    def factory(_unit, arm):
        if arm == "learned":
            return _FeedbackPolicy("offline-fixture-model")
        return _CapturePort("offline-fixture-model")

    report = PilotRunner(PilotDesign(
        units=4, development_per_context=6, qualification_per_context=2
    ).freeze()).run(port_factory=factory)
    summary = report.to_dict()
    assert summary["mean_unit_itt_learned_minus_fresh"] > 0
    assert summary["heldout_triplets_accepted_all_arms"] == 16
    assert summary["scientific_acceptance"] is False
    assert summary["independent_evaluator_attested"] is False
    assert "offline_fixture" in summary["status"]


@pytest.mark.parametrize(
    "bad",
    [
        {"units": 0}, {"units": True},
        {"contexts_per_unit": 1},
        {"seed": -1}, {"seed": 2**32},
        {"development_per_context": 0},
        {"qualification_per_context": 0},
        {"model_id": " "},
        {"units": 9},
    ],
)
def test_rejects_invalid_or_unbounded_design(bad) -> None:
    with pytest.raises(ValueError):
        PilotDesign(**bad)


def test_report_serialization_contains_no_hidden_plans_or_task_answers() -> None:
    lock = PilotDesign().freeze()
    report = run_offline_fixture().canonical_bytes().decode()
    assert "hidden_plan" not in report
    assert "expected_answer" not in report
    assert "credential" not in report
    assert lock.digest in report
    assert json.loads(report)["scientific_acceptance"] is False
