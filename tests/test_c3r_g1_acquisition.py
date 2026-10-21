"""Construction-only acquisition tests; do not assert scientific G1/G2 success."""

import inspect
import json

import pytest

from resonance_world.c3r_g1_acquisition import (
    FeedbackLearner,
    acquire_source,
    fresh_plan,
    main,
    run_feedback_acquisition_probe,
)
from resonance_world.c3r_g2 import PLANS, ProcedureCompiler
from resonance_world.c3r_g2_probe import FixtureOracle, make_task


def test_feedback_learner_requires_real_observed_feedback_to_adapt() -> None:
    learner = FeedbackLearner("source-one")
    observations = []
    for _ in range(8):
        plan = learner.choose(context="opaque")
        with pytest.raises(ValueError, match="pending"):
            learner.choose(context="opaque")
        success = plan == PLANS[1]
        learner.observe(context="opaque", plan=plan, success=success)
        observations.append(plan)

    assert learner.feedback_count == 8
    assert observations.count(PLANS[0]) >= 2
    assert observations.count(PLANS[1]) >= 2
    assert learner.learned_plan(context="opaque") == PLANS[1]
    assert learner.attempts["opaque"][PLANS[0]] >= 2
    assert learner.attempts["opaque"][PLANS[1]] >= 2


def test_feedback_rejects_mismatched_and_duplicate_responses() -> None:
    learner = FeedbackLearner("source-one")
    plan = learner.choose(context="opaque")
    other = PLANS[1] if plan == PLANS[0] else PLANS[0]
    with pytest.raises(ValueError, match="pending"):
        learner.observe(context="opaque", plan=other, success=True)
    with pytest.raises(ValueError, match="boolean"):
        learner.observe(context="opaque", plan=plan, success=1)  # type: ignore[arg-type]
    learner.observe(context="opaque", plan=plan, success=False)
    with pytest.raises(ValueError, match="pending"):
        learner.observe(context="opaque", plan=plan, success=True)
    with pytest.raises(ValueError, match="balanced acquisition"):
        learner.learned_plan(context="opaque")


def test_policy_does_not_accept_oracle_or_hidden_truth() -> None:
    forbidden = {"oracle", "grader", "expected_result", "truth", "answer", "treatment"}
    for method in (FeedbackLearner.choose, FeedbackLearner.learned_plan, fresh_plan):
        assert not (forbidden & set(inspect.signature(method).parameters))


def test_external_fixture_grades_actual_choices_not_all_possible_actions() -> None:
    oracle = FixtureOracle({"c": PLANS[1]})
    acquisition = acquire_source(oracle, contexts=("c",))
    assert len(acquisition.index.episodes) == 16
    assert all(agent.feedback_count == 8 for agent in acquisition.learners)
    assert len({record.episode_id for record in acquisition.index.episodes}) == 16
    for learner in acquisition.learners:
        assert learner.learned_plan(context="c") == PLANS[1]
    compiler = ProcedureCompiler()
    candidate = compiler.compile(acquisition.index, context="c")
    assert candidate is not None
    assert candidate.plan == PLANS[1]
    assert candidate.status == "candidate"


def test_feedback_evidence_and_candidate_are_deterministic() -> None:
    oracle = FixtureOracle({"c": PLANS[0]})
    first = acquire_source(oracle, contexts=("c",))
    second = acquire_source(oracle, contexts=("c",))
    assert first.index.development_lock_sha256 == second.index.development_lock_sha256
    assert first.index.episodes == second.index.episodes
    for row in first.index.episodes:
        assert row.source_agent_id.startswith("source-")
        assert row.evidence_ref.source_record_id == row.episode_id
        assert row.evidence_ref.uri.startswith("fixture-feedback://")


def test_qualification_is_disjoint_and_learned_is_not_worse_in_fixture() -> None:
    probe = run_feedback_acquisition_probe()
    assert probe.canonical_bytes() == run_feedback_acquisition_probe().canonical_bytes()
    report = json.loads(probe.canonical_bytes())
    assert report["status"] == "construction_only_not_scientific_evidence"
    assert report["source_learning_type"] == "deterministic_feedback_policy_not_model_learning"
    assert report["independent_organization_units"] == 1
    assert probe.source_feedback_count == 32
    assert len(probe.source_episode_ids) == 32
    assert len(probe.qualification_task_ids) == 16
    assert len(probe.destination_task_ids) == 48
    assert not (
        set(probe.source_episode_ids)
        & set(probe.qualification_task_ids + probe.destination_task_ids)
    )
    assert not set(probe.qualification_task_ids) & set(probe.destination_task_ids)
    assert all(all(results) for results in probe.qualification_learned.values())
    for owner, learned in probe.qualification_learned.items():
        assert sum(learned) >= sum(probe.qualification_fresh[owner])


def test_organizational_comparator_remains_fair_after_actual_feedback() -> None:
    report = run_feedback_acquisition_probe()
    assert report.destination_outcomes["D"] == report.destination_outcomes["C"]
    assert report.destination_outcomes["D_MINUS"] == report.destination_outcomes["B"]
    assert all(report.destination_outcomes["D"])
    assert report.history_reads > 0
    assert report.compiler_rows_scanned == 32
    assert report.to_dict()["descriptive_D_minus_C"] == 0.0
    assert set(report.compiled_candidate_digests) == {
        "opaque-context-1", "opaque-context-2"
    }
    assert all(report.compiled_candidate_digests.values())


def test_hidden_rule_can_be_swapped_without_telling_source_learner() -> None:
    probe = run_feedback_acquisition_probe(
        contexts=("private-a", "private-b"),
        hidden_plans=(PLANS[1], PLANS[0]),
    )
    assert all(all(values) for values in probe.qualification_learned.values())
    assert probe.destination_outcomes["C"] == probe.destination_outcomes["D"]
    assert all(probe.destination_outcomes["D"])


def test_payload_overlap_refused_despite_distinct_qualification_ids() -> None:
    # The fixture public operands repeat after 133 indices, even when IDs differ.
    with pytest.raises(ValueError, match="tasks overlap"):
        run_feedback_acquisition_probe(qualification_count=16)
    with pytest.raises(ValueError, match="tasks overlap"):
        run_feedback_acquisition_probe(destination_count=34)


def test_no_source_learning_when_observations_are_not_delivered() -> None:
    novice = FeedbackLearner("untaught")
    assert novice.choose(context="private-x") == fresh_plan(
        owner_id="untaught", context="private-x"
    )
    with pytest.raises(ValueError, match="balanced acquisition"):
        novice.learned_plan(context="private-x")


def test_unseen_schema_is_not_inferred_from_same_context_feedback() -> None:
    oracle = FixtureOracle({"trained-context": PLANS[1]})
    acquisition = acquire_source(oracle, contexts=("trained-context",))
    with pytest.raises(ValueError, match="balanced acquisition"):
        acquisition.learners[0].learned_plan(context="new-schema")
    assert make_task(
        split="holdout", context="new-schema", number=0
    ).context == "new-schema"


def test_cli_emits_canonical_report_without_running_a_provider(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main() == 0
    captured = capsys.readouterr().out.strip()
    assert captured == run_feedback_acquisition_probe().canonical_bytes().decode()
    assert json.loads(captured)["status"] == "construction_only_not_scientific_evidence"
