"""C3R G1 multischema pilot: null/positive, evaluator isolation, sham and ITT."""

from __future__ import annotations

import json
from dataclasses import dataclass, field, replace

import pytest

from resonance_world.c3r_g1_model_boundary import ModelChoiceCompletion
from resonance_world.c3r_g1_multischema import (
    ARMS,
    FAMILIES,
    LocalFixtureEvaluator,
    PublicCohort,
    SchemaRequest,
    SchemaTask,
    V2Design,
    V2Runner,
    apply_choice,
    run_offline_multischema_fixture,
)


def _small() -> V2Design:
    return V2Design(units=2, development_per_family=3, qualification_per_family=2)


def test_two_families_have_different_executable_algebras() -> None:
    arithmetic = SchemaTask(
        "arithmetic-test", "ctx-arithmetic", "arithmetic",
        value=3, offset=2, factor=5,
    )
    text = SchemaTask("text-test", "ctx-text", "text", text="abroadab")
    assert apply_choice(arithmetic, "A") == 25
    assert apply_choice(arithmetic, "B") == 17
    assert apply_choice(text, "A") == "ZROADZ"
    assert apply_choice(text, "B") == "ABROADAB"
    assert "return (value + offset)" in arithmetic.prompt()
    assert "text.replace('ab', 'z')" in text.prompt()
    assert "expected_answer" not in arithmetic.prompt()
    assert "expected_answer" not in text.prompt()
    with pytest.raises(ValueError, match="only exact"):
        apply_choice(text, "The answer is A")


@pytest.mark.parametrize(
    "task",
    [
        {"family": "arithmetic", "value": 2, "offset": 1, "factor": 1},
        {"family": "arithmetic", "value": 2, "offset": 1, "factor": 3,
         "text": "ab"},
        {"family": "text", "text": "HELLO"},
        {"family": "text", "text": "ab", "value": 1},
        {"family": "not-a-family", "text": "ab"},
    ],
)
def test_rejects_ambiguous_or_invalid_family_payload(task) -> None:
    with pytest.raises(ValueError):
        SchemaTask(task_id="bad", context="ctx", **task)


def test_default_lock_has_no_public_payload_collision_across_schemas() -> None:
    spec = V2Design()
    frozen = spec.freeze()
    assert spec.logical_calls == 480
    assert spec.heldout_triplets == 128
    assert frozen.digest == V2Design().freeze().digest
    assert len(frozen.digest) == 64
    tasks = [
        task for unit in frozen.units for group in unit.families
        for task in (*group.development, *group.qualification)
    ]
    assert len(tasks) == 8 * 2 * (6 + 8)
    assert len({task.task_id for task in tasks}) == len(tasks)
    assert len({task.public_tuple()[1:] for task in tasks}) == len(tasks)
    assert {task.family for task in tasks} == set(FAMILIES)
    for unit in frozen.units:
        assert tuple(group.family for group in unit.families) == FAMILIES


def test_private_evaluator_rule_flips_without_changing_public_cohort() -> None:
    cohort = _small().freeze()
    grader_one = LocalFixtureEvaluator(cohort, private_seed=1701)
    grader_two = LocalFixtureEvaluator(cohort, private_seed=1702)
    target = cohort.units[0].families[0].qualification[0]
    assert cohort.digest == _small().freeze().digest
    assert grader_one.grade("unit-000", target, "A") != grader_two.grade(
        "unit-000", target, "A"
    )
    assert grader_one.grade("unit-000", target, "A") != grader_one.grade(
        "unit-000", target, "B"
    )
    fake = replace(target, value=target.value + 1)
    with pytest.raises(ValueError, match="locked cohort"):
        grader_one.grade("unit-000", fake, "A")
    with pytest.raises(ValueError, match="locked cohort"):
        grader_one.grade("unit-001", target, "A")


def test_duplicate_public_ids_and_payloads_rejected_even_when_other_id_changes() -> None:
    cohort = _small().freeze()
    unit = cohort.units[0]
    group = unit.families[0]
    altered = replace(group, qualification=(group.development[0], *group.qualification[1:]))
    with pytest.raises(ValueError, match="reused"):
        PublicCohort(cohort.design, (
            replace(unit, families=(altered, unit.families[1])),
            *cohort.units[1:],
        ))
    altered2 = replace(
        group, qualification=(
            replace(group.development[0], task_id="another-public-id"),
            *group.qualification[1:],
        ),
    )
    with pytest.raises(ValueError, match="reused"):
        PublicCohort(cohort.design, (
            replace(unit, families=(altered2, unit.families[1])),
            *cohort.units[1:],
        ))


def test_null_fixture_has_all_480_entries_zero_effect_and_no_network_claim() -> None:
    report = run_offline_multischema_fixture()
    result = report.to_dict()
    assert result["status"] == "offline_fixture_no_model_learning_claim"
    assert result["prescribed_logical_calls"] == 480
    assert result["source_dev_prescribed"] == 96
    assert result["source_dev_accepted"] == 96
    assert result["heldout_triplets_prescribed"] == 128
    assert result["heldout_triplets_complete"] == 128
    assert result["qualification_actions_accepted"] == 384
    assert result["qualification_action_yield"] == 1.0
    assert result["triplet_yield"] == 1.0
    assert result["technical_yield_gate"]["passed_in_fixture"] is True
    assert result["technical_yield_gate"]["authorizes_live_campaign"] is False
    assert result["mean_unit_itt_learned_minus_fresh"] == 0.0
    assert result["mean_unit_itt_learned_minus_placebo"] == 0.0
    assert result["fixture_port_execution_only"] is True
    assert result["provider_sends_verified"] is False
    assert result["independent_evaluator_attested"] is False
    assert result["scientific_acceptance"] is False
    assert len(result["trial_records"]) == 480
    assert len(result["trial_digest"]) == 64
    assert result["by_arm"] == {
        arm: {"prescribed": 128, "accepted": 128, "itt_successes": 64}
        for arm in ARMS
    }
    assert all(result["by_family"][family][arm]["itt_successes"] == 32
               for family in FAMILIES for arm in ARMS)
    assert report.canonical_bytes() == run_offline_multischema_fixture().canonical_bytes()
    assert "private_seed" not in report.canonical_bytes().decode()
    assert "reasoning_content" not in report.canonical_bytes().decode()


@dataclass
class _CapturePort:
    model_id: str = "offline-schema-fixture"
    output: str = "A"
    seen: list[SchemaRequest] = field(default_factory=list)

    def complete(self, request: SchemaRequest) -> ModelChoiceCompletion:
        self.seen.append(request)
        return ModelChoiceCompletion(output=self.output, model_id=self.model_id)


def test_four_distinct_port_sessions_per_unit_and_no_holdout_feedback() -> None:
    created: dict[tuple[str, str, str], _CapturePort] = {}

    def factory(uid, arm, stage):
        port = _CapturePort()
        created[uid, arm, stage] = port
        return port

    result = V2Runner(
        _small().freeze(), LocalFixtureEvaluator(_small().freeze(), private_seed=1701)
    ).run(port_factory=factory)
    assert len(result.attempts) == _small().logical_calls
    assert len(created) == 2 * 4
    for uid in ("unit-000", "unit-001"):
        learned_dev = created[uid, "learned", "development"]
        learned_qual = created[uid, "learned", "qualification"]
        fresh = created[uid, "fresh", "qualification"]
        placebo = created[uid, "placebo", "qualification"]
        assert learned_dev is not learned_qual
        assert len(learned_dev.seen) == 2 * 3
        assert len(learned_qual.seen) == len(fresh.seen) == len(placebo.seen) == 4
        assert all(r.stage == "development" for r in learned_dev.seen)
        assert all(r.stage == "qualification" for r in learned_qual.seen)
        assert all(not r.feedback for r in fresh.seen)
        for port in (learned_dev, learned_qual, fresh, placebo):
            assert all(
                fb.task_id.startswith("dev-") and fb.context == req.task.context
                and fb.task_id != req.task.task_id
                for req in port.seen for fb in req.feedback
            )
        for trained_request in learned_qual.seen:
            placebo_request = next(
                r for r in placebo.seen if r.task.task_id == trained_request.task.task_id
            )
            assert len(trained_request.feedback) == len(placebo_request.feedback) == 3


def test_placebo_plan_and_label_trace_independent_of_real_development_choices() -> None:
    snapshots: list[tuple[tuple[str, str, str, bool], ...]] = []
    for learned_dev_choice in ("A", "B"):
        created = {}

        def factory(uid, arm, stage, _choice=learned_dev_choice, _seen=created):
            choice = _choice if arm == "learned" and stage == "development" else "A"
            port = _CapturePort(output=choice)
            _seen[uid, arm, stage] = port
            return port

        cohort = _small().freeze()
        V2Runner(cohort, LocalFixtureEvaluator(cohort, private_seed=1701)).run(
            port_factory=factory
        )
        requests = created["unit-000", "placebo", "qualification"].seen
        snapshots.append(tuple(
            (fb.task_id, fb.context, fb.choice, fb.success)
            for req in requests for fb in req.feedback
        ))
    assert snapshots[0] == snapshots[1]


def test_model_id_failures_and_malformed_formats_stay_in_itt_denominator() -> None:
    def factory(_uid, arm, _stage):
        if arm == "fresh":
            return _CapturePort(model_id="wrong-model")
        if arm == "placebo":
            return _CapturePort(output="Answer A")
        return _CapturePort()

    cohort = _small().freeze()
    report = V2Runner(
        cohort, LocalFixtureEvaluator(cohort, private_seed=1701)
    ).run(port_factory=factory)
    data = report.to_dict()
    assert data["prescribed_logical_calls"] == 36
    assert len(data["trial_records"]) == 36
    assert data["heldout_triplets_complete"] == 0
    assert data["qualification_actions_accepted"] == 8
    assert data["qualification_action_yield"] == 1 / 3
    assert data["by_arm"]["learned"]["accepted"] == 8
    assert data["by_arm"]["fresh"]["accepted"] == 0
    assert data["by_arm"]["placebo"]["accepted"] == 0
    assert data["technical_yield_gate"]["passed_in_fixture"] is False
    assert data["status"] == "unverified_injected_ports_no_inference"
    assert data["fixture_port_execution_only"] is False
    assert data["provider_sends_verified"] is False
    assert data["scientific_acceptance"] is False
    assert sum(row["status"] == "wrong_model" for row in data["trial_records"]) == 8
    assert sum(row["status"] == "invalid_format" for row in data["trial_records"]) == 8


def test_exceptions_are_failures_not_missing_records() -> None:
    class Failure:
        def complete(self, _request):
            raise TimeoutError("synthetic error containing arbitrary raw text")

    def factory(_uid, arm, _stage):
        return Failure() if arm == "fresh" else _CapturePort()

    cohort = _small().freeze()
    data = V2Runner(cohort, LocalFixtureEvaluator(cohort, private_seed=1701)).run(
        port_factory=factory
    ).to_dict()
    assert len(data["trial_records"]) == 36
    assert sum(row["status"] == "adapter_exception" for row in data["trial_records"]) == 8
    assert data["qualification_actions_accepted"] == 16
    assert data["heldout_triplets_complete"] == 0
    assert "synthetic error containing" not in json.dumps(data)


@dataclass(slots=True)
class _FeedbackLearner:
    model_id: str = "offline-schema-fixture"

    def complete(self, request: SchemaRequest) -> ModelChoiceCompletion:
        if not request.feedback:
            action = "A"
        else:
            last = request.feedback[-1]
            action = last.choice if last.success else (
                "B" if last.choice == "A" else "A"
            )
        return ModelChoiceCompletion(output=action, model_id=self.model_id)


def test_positive_control_feedback_acquisition_on_both_distinct_schemas() -> None:
    def factory(_uid, arm, _stage):
        return _FeedbackLearner() if arm == "learned" else _CapturePort()

    cohort = V2Design(units=4, qualification_per_family=3).freeze()
    data = V2Runner(
        cohort, LocalFixtureEvaluator(cohort, private_seed=1701)
    ).run(port_factory=factory).to_dict()
    assert data["mean_unit_itt_learned_minus_fresh"] > 0
    assert data["by_family"]["arithmetic"]["learned"]["itt_successes"] == 12
    assert data["by_family"]["text"]["learned"]["itt_successes"] == 12
    assert all(row["itt_learned_minus_fresh"] > 0 for row in data["unit_effects"])
    assert data["scientific_acceptance"] is False
    assert data["independent_evaluator_attested"] is False


def test_reuse_of_port_object_is_rejected_before_any_qualification() -> None:
    singleton = _CapturePort()
    cohort = _small().freeze()
    runner = V2Runner(cohort, LocalFixtureEvaluator(cohort, private_seed=1701))
    with pytest.raises(ValueError, match="distinct"):
        runner.run(port_factory=lambda _uid, _arm, _stage: singleton)

    ports = [_CapturePort() for _ in range(4)]
    counter = 0

    def reuse(_uid, _arm, _stage):
        nonlocal counter
        selected = ports[counter % 4]
        counter += 1
        return selected

    with pytest.raises(ValueError, match="distinct"):
        runner.run(port_factory=reuse)


@pytest.mark.parametrize("kwargs", [
    {"units": 0}, {"units": True}, {"units": 9},
    {"development_per_family": 0}, {"qualification_per_family": 0},
    {"public_seed": -1}, {"public_seed": 2**32},
    {"model_id": " "},
])
def test_invalid_or_overbudget_design_rejected(kwargs) -> None:
    with pytest.raises(ValueError):
        V2Design(**kwargs)


def test_fake_or_cross_context_feedback_rejected() -> None:
    cohort = _small().freeze()
    task = cohort.units[0].families[0].qualification[0]
    from resonance_world.c3r_g1_multischema import Feedback

    with pytest.raises(ValueError):
        SchemaRequest("unit-000", "fresh", "qualification", task, (
            Feedback("dev-x", task.context, "A", True),
        ))
    with pytest.raises(ValueError):
        SchemaRequest("unit-000", "learned", "qualification", task, (
            Feedback("dev-x", "wrong-context", "A", True),
        ))
    with pytest.raises(ValueError):
        SchemaRequest("unit-000", "learned", "qualification", task, (
            Feedback(task.task_id, task.context, "A", True),
        ))
    with pytest.raises(ValueError):
        Feedback("dev-x", task.context, "A", 1)


def test_all_fixture_outputs_are_deterministic_without_external_provider() -> None:
    one = run_offline_multischema_fixture(_small()).canonical_bytes()
    two = run_offline_multischema_fixture(_small()).canonical_bytes()
    assert one == two
    data = json.loads(one)
    assert data["technical_yield_gate"]["passed_in_fixture"] is True
    assert data["provider_sends_verified"] is False
    assert len(data["trial_records"]) == _small().logical_calls
