"""Local C3R-G2 probe tests; no provider, no frozen scientific inference."""

import inspect
import json

import pytest

from resonance_world.c3r_g2 import PLANS, ProcedureCompiler
from resonance_world.c3r_g2_probe import (
    ARMS,
    FixtureOracle,
    apply_public_plan,
    make_development_index,
    make_holdout,
    main,
    make_task,
    propose,
    run_fixture_probe,
    select_compiled,
    select_raw_history,
)


def test_fixture_is_reproducible_and_explicitly_noninferential() -> None:
    first = run_fixture_probe()
    second = run_fixture_probe()
    assert first.canonical_bytes() == second.canonical_bytes()
    report = json.loads(first.canonical_bytes())
    assert report["status"] == "construction_only_no_inference"
    assert report["independent_organization_units"] == 1
    assert report["source_development"] == "scripted_exhaustive_plan_probe_not_individual_learning"
    assert set(report["outcome_counts"]) == set(ARMS)
    assert len(first.holdout_task_ids) == 48
    assert len(first.traces) == 48 * len(ARMS)
    assert report["source_lock"] != report["holdout_lock"]


def test_raw_history_is_not_handicapped_to_manufacture_compiler_uplift() -> None:
    result = run_fixture_probe()
    # The raw-history arm has the same data and aggregation rule as D.
    assert result.outcomes["C"] == result.outcomes["D"]
    assert all(result.outcomes["D"])
    assert sum(result.outcomes["B"]) == 24
    assert result.outcomes["D_MINUS"] == result.outcomes["B"]
    assert result.to_dict()["descriptive_D_minus_C"] == 0.0
    assert result.to_dict()["descriptive_D_minus_B"] == 0.5
    assert result.history_reads["C"] > 0
    assert result.history_reads["D"] == 0
    assert result.compilation_rows_inspected > 0


def test_all_arms_use_same_fresh_roster_and_public_proposal_budget() -> None:
    result = run_fixture_probe()
    for trace in result.traces:
        assert trace.proposer_ids == ("new-member-1", "new-member-2")
        assert trace.proposal_slots == 2
        assert trace.primitive_operations == 4
        assert trace.selected_plan == trace.proposals[0]
        assert trace.arm in ARMS
    assert not set(result.source_episode_ids) & set(result.holdout_task_ids)
    assert all(source_id.startswith("dev-") for source_id in result.source_episode_ids)
    assert all(target_id.startswith("holdout-") for target_id in result.holdout_task_ids)


def test_hidden_oracle_changes_outcomes_without_controller_truth_access() -> None:
    task = make_task(split="holdout", context="opaque-context-1", number=0)
    assert not hasattr(task, "expected_result")
    oracle_a = FixtureOracle({"opaque-context-1": PLANS[0]})
    oracle_b = FixtureOracle({"opaque-context-1": PLANS[1]})
    guess = apply_public_plan(task, PLANS[0])
    assert oracle_a.grade(task, guess)
    assert not oracle_b.grade(task, guess)
    assert set(inspect.signature(FixtureOracle.grade).parameters) == {
        "self", "task", "answer"
    }
    assert not (
        {"oracle", "expected_result", "truth", "outcome", "treatment"}
        & set(inspect.signature(propose).parameters)
    )


def test_source_evidence_is_graded_and_holdout_task_ids_are_new() -> None:
    oracle = FixtureOracle(
        {"opaque-context-1": PLANS[0], "opaque-context-2": PLANS[1]}
    )
    index = make_development_index(oracle)
    holdout = make_holdout()
    assert len(index.episodes) == 16
    assert len({row.source_agent_id for row in index.episodes}) == 16
    assert {row.episode_id for row in index.episodes}.isdisjoint(
        {task.task_id for task in holdout}
    )
    for context in ("opaque-context-1", "opaque-context-2"):
        candidate = ProcedureCompiler().compile(index, context=context)
        assert candidate is not None
        assert select_raw_history(index, context=context) == candidate.plan
        assert select_compiled(candidate, context=context) == candidate.plan
        assert candidate.status == "candidate"


def test_ablation_uses_fixed_nonlearned_policy() -> None:
    result = run_fixture_probe()
    baseline = [trace for trace in result.traces if trace.arm == "B"]
    removed = [trace for trace in result.traces if trace.arm == "D_MINUS"]
    assert len(baseline) == len(removed)
    for left, right in zip(baseline, removed, strict=True):
        assert left.task_id == right.task_id
        assert left.proposals == right.proposals
        assert left.submitted_answer == right.submitted_answer


def test_insufficient_exploration_does_not_produce_an_inferred_policy() -> None:
    oracle = FixtureOracle({"opaque-context-1": PLANS[0]})
    index = make_development_index(
        oracle, contexts=("opaque-context-1",), per_plan=1
    )
    assert ProcedureCompiler().compile(index, context="opaque-context-1") is None
    assert select_raw_history(index, context="opaque-context-1") == PLANS[0]


def test_unknown_context_and_invalid_oracle_plan_fail_closed() -> None:
    with pytest.raises(ValueError, match="valid hidden context"):
        FixtureOracle({"opaque-context-1": ("add", "add")})  # type: ignore[dict-item]
    with pytest.raises(KeyError):
        FixtureOracle({"opaque-context-1": PLANS[0]}).grade(
            make_task(split="holdout", context="opaque-context-2", number=0),
            answer=0,
        )


def test_noncommuting_task_inputs_and_public_plans() -> None:
    task = make_task(split="holdout", context="opaque-context-1", number=3)
    assert apply_public_plan(task, PLANS[0]) != apply_public_plan(task, PLANS[1])
    with pytest.raises(ValueError, match="noncommuting"):
        type(task)(task.task_id, task.context, task.value, offset=0, factor=1)


def test_compiler_does_not_magically_transfer_to_unseen_contexts() -> None:
    result = run_fixture_probe()
    assert len(result.candidate_digests) == 2
    assert all(digest is not None for digest in result.candidate_digests.values())
    assert "unseen-context" not in result.candidate_digests


def test_context_switch_reverses_compiled_preference_without_retuning() -> None:
    first = run_fixture_probe()
    swapped = run_fixture_probe(hidden_plans=(PLANS[1], PLANS[0]))
    assert first.candidate_digests != swapped.candidate_digests
    assert sum(swapped.outcomes["C"]) == len(swapped.holdout_task_ids)
    assert swapped.outcomes["C"] == swapped.outcomes["D"]


def test_cli_emits_canonical_noninferential_report(capsys: pytest.CaptureFixture[str]) -> None:
    assert main() == 0
    captured = capsys.readouterr().out
    assert json.loads(captured)["status"] == "construction_only_no_inference"
    assert captured.strip() == run_fixture_probe().canonical_bytes().decode("utf-8")


def test_payload_disjointness_catches_repeated_tasks_with_fresh_ids() -> None:
    # The fixture input generator cycles after 133 indices, regardless of ID.
    with pytest.raises(ValueError, match="task input overlap"):
        run_fixture_probe(tasks_per_context=34)
