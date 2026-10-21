"""Credential-free, deterministic construction tests for C3R G2.

Passing these tests does NOT establish a causal organizational performance gain.
"""

import inspect

import pytest

from resonance_world.c3r_g2 import (
    EvaluatedExperience,
    ExperienceEvidenceIndex,
    HoldoutComparison,
    OrganizationalProcedure,
    ProcedureCompiler,
    ProcedureValidationGate,
    episode_digest,
)
from resonance_world.protocol import EvidenceRef

LOCK = "a" * 64
HOLDOUT_LOCK = "b" * 64
PLAN_A = ("add", "multiply")
PLAN_B = ("multiply", "add")


def _episode(number: int, plan: tuple[str, str], success: bool) -> EvaluatedExperience:
    episode_id = f"dev-{number}"
    agent_id = f"agent-{number}"
    context = "opaque-context-1"
    digest = episode_digest(
        episode_id=episode_id,
        source_agent_id=agent_id,
        context=context,
        plan=plan,
        success=success,
    )
    return EvaluatedExperience(
        episode_id=episode_id,
        source_agent_id=agent_id,
        context=context,
        plan=plan,
        success=success,
        evidence_ref=EvidenceRef(
            uri=f"evidence://external-evaluator/{episode_id}",
            sha256=digest,
            source_record_id=episode_id,
        ),
    )


def _index() -> ExperienceEvidenceIndex:
    return ExperienceEvidenceIndex(
        evaluator_id="independent-evaluator",
        development_lock_sha256=LOCK,
        episodes=(
            _episode(1, PLAN_A, False),
            _episode(2, PLAN_A, False),
            _episode(3, PLAN_B, True),
            _episode(4, PLAN_B, True),
        ),
    )


def _candidate() -> OrganizationalProcedure:
    candidate = ProcedureCompiler().compile(_index(), context="opaque-context-1")
    assert candidate is not None
    return candidate


def test_candidate_is_executable_but_never_self_validating() -> None:
    candidate = _candidate()
    assert candidate.plan == PLAN_B
    assert candidate.status == "candidate"
    assert candidate.execute(value=2, offset=3, factor=4) == 11
    assert len(candidate.source_evidence_refs) == 4
    assert candidate.digest == _candidate().digest


def test_compiler_abstains_on_missing_arm_samples() -> None:
    index = ExperienceEvidenceIndex(
        "independent-evaluator", LOCK, (_episode(1, PLAN_A, True),)
    )
    assert ProcedureCompiler().compile(index, context="opaque-context-1") is None


def test_compiler_abstains_on_ties_and_absent_context() -> None:
    items = (
        _episode(1, PLAN_A, True),
        _episode(2, PLAN_A, False),
        _episode(3, PLAN_B, True),
        _episode(4, PLAN_B, False),
    )
    index = ExperienceEvidenceIndex("independent-evaluator", LOCK, items)
    compiler = ProcedureCompiler()
    assert compiler.compile(index, context="opaque-context-1") is None
    assert compiler.compile(index, context="unseen-context") is None


def test_duplicate_episodes_are_rejected() -> None:
    with pytest.raises(ValueError, match="duplicate episode"):
        ExperienceEvidenceIndex(
            "evaluator", LOCK, (_episode(1, PLAN_A, True), _episode(1, PLAN_A, True))
        )


def test_digest_mismatch_is_rejected_before_compilation() -> None:
    episode = _episode(1, PLAN_A, True)
    with pytest.raises(ValueError, match="digest"):
        EvaluatedExperience(
            episode_id=episode.episode_id,
            source_agent_id=episode.source_agent_id,
            context=episode.context,
            plan=episode.plan,
            success=False,
            evidence_ref=episode.evidence_ref,
        )


def test_evidence_reference_must_bind_source_record() -> None:
    episode = _episode(1, PLAN_A, True)
    with pytest.raises(ValueError, match="identify the episode"):
        EvaluatedExperience(
            episode_id=episode.episode_id,
            source_agent_id=episode.source_agent_id,
            context=episode.context,
            plan=episode.plan,
            success=True,
            evidence_ref=EvidenceRef(
                uri=episode.evidence_ref.uri,
                sha256=episode.evidence_ref.sha256,
                source_record_id="another-episode",
            ),
        )


def test_compiler_rejects_invalid_sample_floor() -> None:
    with pytest.raises(ValueError, match="positive"):
        ProcedureCompiler(min_trials_per_plan=0)


def test_candidate_rejects_claimed_promotion() -> None:
    candidate = _candidate()
    with pytest.raises(ValueError, match="self-promote"):
        OrganizationalProcedure(
            context=candidate.context,
            plan=candidate.plan,
            source_episode_ids=candidate.source_episode_ids,
            source_evidence_refs=candidate.source_evidence_refs,
            development_lock_sha256=candidate.development_lock_sha256,
            status="validated",  # type: ignore[arg-type]
        )


def _holdout(candidate: OrganizationalProcedure) -> HoldoutComparison:
    return HoldoutComparison(
        candidate_digest=candidate.digest,
        evaluator_id="independent-holdout-evaluator",
        holdout_lock_sha256=HOLDOUT_LOCK,
        episode_ids=("holdout-1", "holdout-2"),
        treatment_success=(True, True),
        control_success=(False, True),
    )


def test_gate_returns_description_not_promotion() -> None:
    candidate = _candidate()
    assert ProcedureValidationGate.descriptive_difference(candidate, _holdout(candidate)) == 0.5
    assert candidate.status == "candidate"


def test_gate_rejects_development_holdout_overlap() -> None:
    candidate = _candidate()
    comparison = HoldoutComparison(
        candidate_digest=candidate.digest,
        evaluator_id="independent-holdout-evaluator",
        holdout_lock_sha256=HOLDOUT_LOCK,
        episode_ids=("dev-1",),
        treatment_success=(True,),
        control_success=(False,),
    )
    with pytest.raises(ValueError, match="disjoint"):
        ProcedureValidationGate.descriptive_difference(candidate, comparison)


def test_gate_rejects_reused_holdout_lock_and_wrong_candidate() -> None:
    candidate = _candidate()
    comparison = _holdout(candidate)
    with pytest.raises(ValueError, match="candidate"):
        ProcedureValidationGate.descriptive_difference(
            candidate,
            HoldoutComparison(
                candidate_digest="0" * 64,
                evaluator_id=comparison.evaluator_id,
                holdout_lock_sha256=comparison.holdout_lock_sha256,
                episode_ids=comparison.episode_ids,
                treatment_success=comparison.treatment_success,
                control_success=comparison.control_success,
            ),
        )
    with pytest.raises(ValueError, match="different frozen cohort"):
        ProcedureValidationGate.descriptive_difference(
            candidate,
            HoldoutComparison(
                candidate_digest=candidate.digest,
                evaluator_id=comparison.evaluator_id,
                holdout_lock_sha256=LOCK,
                episode_ids=comparison.episode_ids,
                treatment_success=comparison.treatment_success,
                control_success=comparison.control_success,
            ),
        )


def test_environment_truth_is_not_an_executor_or_compiler_input() -> None:
    execute_params = set(inspect.signature(OrganizationalProcedure.execute).parameters)
    compile_params = set(inspect.signature(ProcedureCompiler.compile).parameters)
    forbidden = {"expected_result", "truth", "evaluator", "world_outcome", "success"}
    assert not (execute_params & forbidden)
    assert not (compile_params & forbidden)
