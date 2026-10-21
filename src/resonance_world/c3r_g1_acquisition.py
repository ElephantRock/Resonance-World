"""C3R local source-acquisition probe: decisions adapt to independent feedback.

Construction only. A deterministic two-plan learner receives public tasks and
post-action success bits, never the oracle's hidden context policy. The resulting
experience index may be fed to the existing G2 candidate compiler. This proves
apparatus feedback wiring, NOT autonomous model learning or causal G2 benefit.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field

from .c3r_g2 import (
    PLANS,
    EvaluatedExperience,
    ExperienceEvidenceIndex,
    Plan,
    ProcedureCompiler,
    episode_digest,
)
from .c3r_g2_probe import (
    ARMS,
    CONTEXTS,
    FixtureOracle,
    PublicTask,
    apply_public_plan,
    make_holdout,
    make_task,
    propose,
)
from .protocol import EvidenceRef


def _digest(payload: object) -> str:
    value = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(value).hexdigest()


@dataclass(slots=True)
class FeedbackLearner:
    """A tiny explicit policy learner, not an LLM or an institutional agent.

    Each context starts with balanced forced exploration. Subsequent choices
    follow observed per-plan success rates, with a stable owner-specific
    tie-break. The learner does not receive the evaluator or answer key.
    """

    owner_id: str
    attempts: dict[str, dict[Plan, int]] = field(default_factory=dict)
    successes: dict[str, dict[Plan, int]] = field(default_factory=dict)
    pending: tuple[str, Plan] | None = None
    feedback_count: int = 0

    def __post_init__(self) -> None:
        if not self.owner_id.strip():
            raise ValueError("learner requires an identity")

    def choose(self, *, context: str) -> Plan:
        if not context.strip():
            raise ValueError("context is required")
        if self.pending is not None:
            raise ValueError("ungraded decision is still pending")
        counts = self.attempts.get(context, {plan: 0 for plan in PLANS})
        observed = self.successes.get(context, {plan: 0 for plan in PLANS})
        tie_start = int(_digest([self.owner_id, context, "fresh-policy"])[:8], 16) % 2
        preference = (PLANS[tie_start], PLANS[1 - tie_start])
        if min(counts.values()) < 2:
            plan = min(preference, key=lambda item: counts[item])
        else:
            rates = {plan: observed[plan] / counts[plan] for plan in PLANS}
            plan = max(preference, key=lambda item: rates[item])
        self.pending = (context, plan)
        return plan

    def observe(self, *, context: str, plan: Plan, success: bool) -> None:
        """Consume a single post-action feedback bit for the outstanding choice."""
        if self.pending != (context, plan):
            raise ValueError("feedback does not match a pending decision")
        if type(success) is not bool:
            raise ValueError("feedback success must be boolean")
        self.attempts.setdefault(context, {item: 0 for item in PLANS})[plan] += 1
        if success:
            self.successes.setdefault(context, {item: 0 for item in PLANS})[plan] += 1
        else:
            self.successes.setdefault(context, {item: 0 for item in PLANS})
        self.feedback_count += 1
        self.pending = None

    def learned_plan(self, *, context: str) -> Plan:
        """Read frozen acquisition state without enrolling another episode."""
        counts = self.attempts.get(context, {plan: 0 for plan in PLANS})
        outcomes = self.successes.get(context, {plan: 0 for plan in PLANS})
        if min(counts.values()) < 2 or self.pending is not None:
            raise ValueError("source has not completed balanced acquisition")
        rates = {plan: outcomes[plan] / counts[plan] for plan in PLANS}
        fallback = int(_digest([self.owner_id, context, "fresh-policy"])[:8], 16) % 2
        preference = (PLANS[fallback], PLANS[1 - fallback])
        return max(preference, key=lambda item: rates[item])


def fresh_plan(*, owner_id: str, context: str) -> Plan:
    """Same learner before any feedback; avoids an intentionally weak baseline."""
    learner = FeedbackLearner(owner_id)
    return learner.choose(context=context)


@dataclass(frozen=True, slots=True)
class SourceAcquisition:
    index: ExperienceEvidenceIndex
    learners: tuple[FeedbackLearner, ...]
    context_by_agent: tuple[tuple[str, str], ...]

    def __post_init__(self) -> None:
        if len(self.learners) != len(self.context_by_agent):
            raise ValueError("source learner and context registries must align")
        if len({learner.owner_id for learner in self.learners}) != len(self.learners):
            raise ValueError("source agents must be independent identities")


def acquire_source(
    oracle: FixtureOracle,
    *,
    contexts: tuple[str, ...] = CONTEXTS,
    agents_per_context: int = 2,
    training_steps_per_agent: int = 8,
) -> SourceAcquisition:
    """Grade each actual learner choice, then deliver only its feedback bit.

    The oracle is owned by this fixture runner and never given to the learner.
    Experiments with model-mediated agents need an independently owned runner.
    """
    if agents_per_context < 2 or training_steps_per_agent < 4:
        raise ValueError("at least two sources and four feedback episodes required")
    if len(contexts) != len(set(contexts)):
        raise ValueError("context identities must be unique")

    rows: list[EvaluatedExperience] = []
    learners: list[FeedbackLearner] = []
    owners: list[tuple[str, str]] = []
    for context in contexts:
        for owner_index in range(agents_per_context):
            learner = FeedbackLearner(f"source-{context}-{owner_index}")
            learners.append(learner)
            owners.append((learner.owner_id, context))
            for step in range(training_steps_per_agent):
                number = owner_index * training_steps_per_agent + step
                task = make_task(split="dev", context=context, number=number)
                plan = learner.choose(context=task.context)
                success = oracle.grade(task, apply_public_plan(task, plan))
                learner.observe(context=task.context, plan=plan, success=success)
                digest = episode_digest(
                    episode_id=task.task_id,
                    source_agent_id=learner.owner_id,
                    context=task.context,
                    plan=plan,
                    success=success,
                )
                rows.append(
                    EvaluatedExperience(
                        episode_id=task.task_id,
                        source_agent_id=learner.owner_id,
                        context=task.context,
                        plan=plan,
                        success=success,
                        evidence_ref=EvidenceRef(
                            uri=f"fixture-feedback://c3r/{task.task_id}",
                            sha256=digest,
                            source_record_id=task.task_id,
                        ),
                    )
                )
    lock = _digest(
        {
            "scope": "c3r-feedback-development-fixture",
            "episodes": [(row.episode_id, row.evidence_ref.sha256) for row in rows],
        }
    )
    return SourceAcquisition(
        ExperienceEvidenceIndex("local-fixture-feedback-grader", lock, tuple(rows)),
        tuple(learners),
        tuple(owners),
    )


@dataclass(frozen=True, slots=True)
class AcquisitionProbeReport:
    """Explicitly noninferential summary; no promotion or p-values."""

    development_lock: str
    qualification_lock: str
    destination_lock: str
    source_ids: tuple[str, ...]
    source_episode_ids: tuple[str, ...]
    qualification_task_ids: tuple[str, ...]
    destination_task_ids: tuple[str, ...]
    source_feedback_count: int
    qualification_learned: dict[str, tuple[bool, ...]]
    qualification_fresh: dict[str, tuple[bool, ...]]
    compiled_candidate_digests: dict[str, str | None]
    destination_outcomes: dict[str, tuple[bool, ...]]
    history_reads: int
    compiler_rows_scanned: int

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": "c3r-source-acquisition-probe-v0.1",
            "status": "construction_only_not_scientific_evidence",
            "source_learning_type": "deterministic_feedback_policy_not_model_learning",
            "independent_organization_units": 1,
            "source_feedback_count": self.source_feedback_count,
            "source_ids": list(self.source_ids),
            "source_episode_ids": list(self.source_episode_ids),
            "qualification_task_ids": list(self.qualification_task_ids),
            "destination_task_ids": list(self.destination_task_ids),
            "development_lock": self.development_lock,
            "qualification_lock": self.qualification_lock,
            "destination_lock": self.destination_lock,
            "qualification_learned": {
                key: {"successes": sum(values), "tasks": len(values)}
                for key, values in sorted(self.qualification_learned.items())
            },
            "qualification_fresh": {
                key: {"successes": sum(values), "tasks": len(values)}
                for key, values in sorted(self.qualification_fresh.items())
            },
            "compiled_candidate_digests": self.compiled_candidate_digests,
            "destination_outcomes": {
                arm: {"successes": sum(self.destination_outcomes[arm]),
                      "tasks": len(self.destination_outcomes[arm])}
                for arm in ARMS
            },
            "descriptive_D_minus_C": (
                sum(self.destination_outcomes["D"]) - sum(self.destination_outcomes["C"])
            ) / len(self.destination_outcomes["D"]),
            "history_reads": self.history_reads,
            "compiler_rows_scanned": self.compiler_rows_scanned,
            "warnings": [
                "deterministic fixture and synthetic oracle, not model-mediated agents",
                "novel operands within the same schema are not cross-schema generalization",
                "source qualification is a probe diagnostic, not a powered G1 gate",
                "one independent organization unit, repeated missions are correlated",
                "C and D share sufficient statistics; no compiled effect is expected",
                "raw-history retrieval and one-time compilation have different costs",
                "digests are not independently authenticated evaluator authority",
            ],
        }

    def canonical_bytes(self) -> bytes:
        return json.dumps(
            self.to_dict(), sort_keys=True, separators=(",", ":")
        ).encode("utf-8")


def _task_key(task: PublicTask) -> tuple[str, int, int, int]:
    return (task.context, task.value, task.offset, task.factor)


def run_feedback_acquisition_probe(
    *,
    contexts: tuple[str, ...] = CONTEXTS,
    hidden_plans: tuple[Plan, ...] = (PLANS[0], PLANS[1]),
    qualification_count: int = 8,
    destination_count: int = 24,
) -> AcquisitionProbeReport:
    """Run one local demonstrator; all arms receive identical holdout tasks."""
    if len(contexts) != len(hidden_plans) or len(contexts) != len(set(contexts)):
        raise ValueError("context/oracle mapping must be unique and aligned")
    if qualification_count < 1 or destination_count < 1:
        raise ValueError("holdout sizes must be positive")

    oracle = FixtureOracle(dict(zip(contexts, hidden_plans, strict=True)))
    source = acquire_source(oracle, contexts=contexts)
    qualifier = tuple(
        make_task(split="holdout", context=context, number=destination_count + n)
        for context in contexts for n in range(qualification_count)
    )
    destination = make_holdout(contexts=contexts, tasks_per_context=destination_count)
    original = tuple(
        make_task(split="dev", context=context, number=number)
        for context in contexts for number in range(16)
    )
    if len(source.index.episodes) != len(original):
        raise ValueError("fixture development must have two agents and eight steps each")
    all_tasks = original + qualifier + destination
    if len({_task_key(task) for task in all_tasks}) != len(all_tasks):
        raise ValueError("development, qualification, and destination tasks overlap")
    if len({task.task_id for task in all_tasks}) != len(all_tasks):
        raise ValueError("split ids are duplicated")

    qualification_learned: dict[str, tuple[bool, ...]] = {}
    qualification_fresh: dict[str, tuple[bool, ...]] = {}
    for learner, (_, context) in zip(source.learners, source.context_by_agent, strict=True):
        tasks = tuple(task for task in qualifier if task.context == context)
        trained = learner.learned_plan(context=context)
        novice = fresh_plan(owner_id=learner.owner_id, context=context)
        qualification_learned[learner.owner_id] = tuple(
            oracle.grade(task, apply_public_plan(task, trained)) for task in tasks
        )
        qualification_fresh[learner.owner_id] = tuple(
            oracle.grade(task, apply_public_plan(task, novice)) for task in tasks
        )

    compiler = ProcedureCompiler()
    candidates = {
        context: compiler.compile(source.index, context=context) for context in contexts
    }
    dest_outcomes: dict[str, list[bool]] = {arm: [] for arm in ARMS}
    history_reads = 0
    for arm in ARMS:
        members = ("new-member-1", "new-member-2")
        for task in destination:
            trace = propose(
                task,
                arm=arm,
                members=members,
                index=source.index if arm == "C" else None,
                candidate=candidates[task.context] if arm == "D" else None,
            )
            dest_outcomes[arm].append(oracle.grade(task, trace.submitted_answer))
            if arm == "C":
                history_reads += 2 * sum(
                    row.context == task.context for row in source.index.episodes
                )
    return AcquisitionProbeReport(
        development_lock=source.index.development_lock_sha256,
        qualification_lock=_digest([_task_key(task) for task in qualifier]),
        destination_lock=_digest([_task_key(task) for task in destination]),
        source_ids=tuple(learner.owner_id for learner in source.learners),
        source_episode_ids=tuple(row.episode_id for row in source.index.episodes),
        qualification_task_ids=tuple(task.task_id for task in qualifier),
        destination_task_ids=tuple(task.task_id for task in destination),
        source_feedback_count=sum(learner.feedback_count for learner in source.learners),
        qualification_learned=qualification_learned,
        qualification_fresh=qualification_fresh,
        compiled_candidate_digests={
            context: None if candidate is None else candidate.digest
            for context, candidate in candidates.items()
        },
        destination_outcomes={arm: tuple(results) for arm, results in dest_outcomes.items()},
        history_reads=history_reads,
        compiler_rows_scanned=len(source.index.episodes),
    )


def main() -> int:
    """Explicitly noninferential deterministic JSON diagnostics to stdout."""
    print(run_feedback_acquisition_probe().canonical_bytes().decode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
