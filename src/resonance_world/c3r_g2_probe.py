"""Credential-free C3R G2 *construction* probe with a grader-blind controller boundary.

All outcomes in this module are fixture-derived, not confirmatory scientific data.
A fair raw-history controller is intentionally allowed to recover the same
selection as the compiled procedure: representation alone may have zero uplift.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Literal

from .c3r_g2 import (
    PLANS,
    EvaluatedExperience,
    ExperienceEvidenceIndex,
    OrganizationalProcedure,
    Plan,
    ProcedureCompiler,
    episode_digest,
)
from .protocol import EvidenceRef

Arm = Literal["A", "B", "C", "D", "D_MINUS"]
ARMS: tuple[Arm, ...] = ("A", "B", "C", "D", "D_MINUS")
CONTEXTS = ("opaque-context-1", "opaque-context-2")


def _canonical(data: object) -> bytes:
    return json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha(data: object) -> str:
    return hashlib.sha256(_canonical(data)).hexdigest()


@dataclass(frozen=True, slots=True)
class PublicTask:
    """Only observable task inputs, intentionally excluding expected outcomes."""

    task_id: str
    context: str
    value: int
    offset: int
    factor: int

    def __post_init__(self) -> None:
        if not self.task_id or not self.context:
            raise ValueError("task identity and context are required")
        if self.offset < 1 or self.factor < 2:
            raise ValueError("require noncommuting public operations")


def apply_public_plan(task: PublicTask, plan: Plan) -> int:
    """No access to hidden task truth, evaluator, or treatment identifier."""
    if plan not in PLANS:
        raise ValueError("unknown plan")
    value = task.value
    for step in plan:
        value = value + task.offset if step == "add" else value * task.factor
    return value


class FixtureOracle:
    """Evaluator only. Never pass this object to a selector/controller.

    This is a local deterministic fixture, NOT a model or cryptographic isolation
    boundary. Source and destination fixtures share contexts, but not task IDs.
    """

    def __init__(self, context_plans: dict[str, Plan]) -> None:
        if not context_plans or any(plan not in PLANS for plan in context_plans.values()):
            raise ValueError("oracle requires valid hidden context plans")
        self._context_plans = dict(context_plans)

    def grade(self, task: PublicTask, answer: int) -> bool:
        """Outcome law reads only public operands and the *hidden* target plan."""
        return answer == apply_public_plan(task, self._context_plans[task.context])


def make_task(*, split: Literal["dev", "holdout"], context: str, number: int) -> PublicTask:
    """Deterministic distinct operands per split; IDs cannot collide."""
    if number < 0 or not context:
        raise ValueError("task index and context are required")
    offset_seed = number + (100 if split == "holdout" else 0)
    return PublicTask(
        task_id=f"{split}-{context}-{number}",
        context=context,
        value=1 + (7 * offset_seed) % 19,
        offset=1 + (3 * offset_seed) % 7,
        factor=2 + (5 * offset_seed) % 7,
    )


def make_development_index(
    oracle: FixtureOracle,
    *,
    contexts: tuple[str, ...] = CONTEXTS,
    per_plan: int = 4,
) -> ExperienceEvidenceIndex:
    """Scripted two-plan probes, not evidence of autonomous individual learning."""
    if per_plan < 1 or len(contexts) != len(set(contexts)):
        raise ValueError("positive development count and unique contexts required")
    rows: list[EvaluatedExperience] = []
    for context in contexts:
        for plan_index, plan in enumerate(PLANS):
            for index in range(per_plan):
                task = make_task(split="dev", context=context, number=per_plan * plan_index + index)
                agent_id = f"source-{context}-{plan_index}-{index}"
                success = oracle.grade(task, apply_public_plan(task, plan))
                digest = episode_digest(
                    episode_id=task.task_id,
                    source_agent_id=agent_id,
                    context=context,
                    plan=plan,
                    success=success,
                )
                rows.append(
                    EvaluatedExperience(
                        episode_id=task.task_id,
                        source_agent_id=agent_id,
                        context=context,
                        plan=plan,
                        success=success,
                        evidence_ref=EvidenceRef(
                            uri=f"fixture-evaluator://c3r/{task.task_id}",
                            sha256=digest,
                            source_record_id=task.task_id,
                        ),
                    )
                )
    lock = _sha(
        {
            "purpose": "fixture-development-only",
            "episode_digests": [row.evidence_ref.sha256 for row in rows],
            "ids": [row.episode_id for row in rows],
        }
    )
    return ExperienceEvidenceIndex("local-fixture-oracle", lock, tuple(rows))


def make_holdout(
    *, contexts: tuple[str, ...] = CONTEXTS, tasks_per_context: int = 24
) -> tuple[PublicTask, ...]:
    """Frozen-input-shape local fixture; NOT a fresh scientific sample."""
    if tasks_per_context < 1 or len(contexts) != len(set(contexts)):
        raise ValueError("positive holdout count and unique contexts required")
    return tuple(
        make_task(split="holdout", context=context, number=index)
        for context in contexts
        for index in range(tasks_per_context)
    )


def select_independent(task: PublicTask, *, agent_id: str) -> Plan:
    """No access to prior source history; first proposer wins blind ties."""
    bucket = int(_sha({"task": task.task_id, "agent": agent_id})[:8], 16) % len(PLANS)
    return PLANS[bucket]


def select_fixed(task: PublicTask) -> Plan:
    """Nonlearned role controller; identical policy for B and removal."""
    return PLANS[0]


def select_raw_history(index: ExperienceEvidenceIndex, *, context: str) -> Plan:
    """Competent C controller: same sufficient statistics as the compiled D arm.

    Unlike a handicapped raw-history baseline, C reads *all* admitted evidence
    for the requested context and matches D's per-plan support floors.
    """
    rows = [row for row in index.episodes if row.context == context]
    by_plan = {plan: [row for row in rows if row.plan == plan] for plan in PLANS}
    if any(len(group) < 2 or len({x.source_agent_id for x in group}) < 2
           for group in by_plan.values()):
        return PLANS[0]
    rates = {
        plan: sum(int(row.success) for row in group) / len(group)
        for plan, group in by_plan.items()
    }
    if rates[PLANS[0]] == rates[PLANS[1]]:
        return PLANS[0]
    return max(PLANS, key=lambda plan: rates[plan])


def select_compiled(
    candidate: OrganizationalProcedure | None, *, context: str
) -> Plan:
    """Candidate selection alters actions only; not the evaluator's success law."""
    if candidate is None or candidate.context != context:
        return PLANS[0]
    if candidate.status != "candidate":
        raise ValueError("scientific promotion is not a controller capability")
    return candidate.plan


@dataclass(frozen=True, slots=True)
class DecisionTrace:
    arm: Arm
    task_id: str
    proposer_ids: tuple[str, str]
    proposals: tuple[Plan, Plan]
    selected_plan: Plan
    submitted_answer: int
    proposal_slots: int = 2
    primitive_operations: int = 4

    def __post_init__(self) -> None:
        if len(set(self.proposer_ids)) != 2 or self.proposal_slots != 2:
            raise ValueError("exactly two distinct proposers are required")
        if self.selected_plan != self.proposals[0]:
            raise ValueError("selection must be blind and fixed to the first proposer")
        if self.primitive_operations != self.proposal_slots * len(PLANS[0]):
            raise ValueError("invalid primitive-operation count")


def propose(
    task: PublicTask,
    *,
    arm: Arm,
    members: tuple[str, str],
    index: ExperienceEvidenceIndex | None = None,
    candidate: OrganizationalProcedure | None = None,
) -> DecisionTrace:
    """Two complete proposals per arm; fixed blind slot-1 arbitration.

    The raw and compiled paths are separately injected. No grader or oracle is
    passed to this function. Evidence processing cost is *not* assumed equal.
    """
    if arm not in ARMS or len(members) != 2 or len(set(members)) != 2:
        raise ValueError("known arm and two distinct members required")
    if arm == "C" and index is None:
        raise ValueError("C requires development history")
    if arm == "D" and candidate is None:
        raise ValueError("D requires its compiled candidate")

    if arm == "A":
        plans = tuple(select_independent(task, agent_id=agent_id) for agent_id in members)
    elif arm == "C":
        plans = (select_raw_history(index, context=task.context),) * 2
    elif arm == "D":
        plans = (select_compiled(candidate, context=task.context),) * 2
    else:
        plans = (select_fixed(task),) * 2

    first, second = plans
    _ = apply_public_plan(task, second)  # Equal number of full public attempts per arm.
    return DecisionTrace(
        arm=arm,
        task_id=task.task_id,
        proposer_ids=members,
        proposals=(first, second),
        selected_plan=first,
        submitted_answer=apply_public_plan(task, first),
    )


def _as_trace_dict(trace: DecisionTrace) -> dict[str, object]:
    return {
        "arm": trace.arm,
        "task_id": trace.task_id,
        "proposer_ids": list(trace.proposer_ids),
        "proposals": [list(plan) for plan in trace.proposals],
        "selected_plan": list(trace.selected_plan),
        "submitted_answer": trace.submitted_answer,
        "proposal_slots": trace.proposal_slots,
        "primitive_operations": trace.primitive_operations,
    }


@dataclass(frozen=True, slots=True)
class ProbeReport:
    """Construction-only descriptive record; no inferential unit count or p-value."""

    development_lock: str
    holdout_lock: str
    candidate_digests: dict[str, str | None]
    source_episode_ids: tuple[str, ...]
    holdout_task_ids: tuple[str, ...]
    traces: tuple[DecisionTrace, ...]
    outcomes: dict[str, tuple[bool, ...]]
    history_reads: dict[str, int]
    compilation_rows_inspected: int

    def to_dict(self) -> dict[str, object]:
        counts = {
            arm: {"success": sum(self.outcomes[arm]), "tasks": len(self.outcomes[arm])}
            for arm in ARMS
        }
        return {
            "schema": "c3r-g2-fixture-probe-v0.1",
            "status": "construction_only_no_inference",
            "independent_organization_units": 1,
            "source_development": "scripted_exhaustive_plan_probe_not_individual_learning",
            "source_lock": self.development_lock,
            "holdout_lock": self.holdout_lock,
            "source_episode_ids": list(self.source_episode_ids),
            "holdout_task_ids": list(self.holdout_task_ids),
            "candidate_digests": self.candidate_digests,
            "outcome_counts": counts,
            "history_reads_by_arm": self.history_reads,
            "compilation_rows_inspected": self.compilation_rows_inspected,
            "trace_digest": _sha([_as_trace_dict(trace) for trace in self.traces]),
            "descriptive_D_minus_C": (
                sum(self.outcomes["D"]) - sum(self.outcomes["C"])
            ) / len(self.outcomes["D"]),
            "descriptive_D_minus_B": (
                sum(self.outcomes["D"]) - sum(self.outcomes["B"])
            ) / len(self.outcomes["D"]),
            "warnings": [
                "fixture data are synthetic and deterministic",
                "source acquisition is scripted rather than demonstrated agent learning",
                "one organization; tasks are not independent organizational units",
                "raw history recomputes the same sufficient statistic as compiled procedure",
                "selection slots match but evidence-read and compilation costs differ",
                "no holdout inferential test, independent replication, or authority",
            ],
        }

    def canonical_bytes(self) -> bytes:
        return _canonical(self.to_dict())


def run_fixture_probe(
    *,
    contexts: tuple[str, ...] = CONTEXTS,
    hidden_plans: tuple[Plan, ...] = (PLANS[0], PLANS[1]),
    tasks_per_context: int = 24,
) -> ProbeReport:
    """Full pipeline wired end to end, intentionally limited to local construction."""
    if len(contexts) != len(hidden_plans):
        raise ValueError("every context needs exactly one fixture plan")
    oracle = FixtureOracle(dict(zip(contexts, hidden_plans, strict=True)))
    source = make_development_index(oracle, contexts=contexts)
    holdout = make_holdout(contexts=contexts, tasks_per_context=tasks_per_context)
    if {task.task_id for task in holdout} & {row.episode_id for row in source.episodes}:
        raise ValueError("development/holdout task IDs must be disjoint")
    if len({task.task_id for task in holdout}) != len(holdout):
        raise ValueError("duplicate holdout task IDs")

    compiler = ProcedureCompiler()
    candidates = {context: compiler.compile(source, context=context) for context in contexts}
    traces: list[DecisionTrace] = []
    outcomes: dict[str, list[bool]] = {arm: [] for arm in ARMS}
    history_reads = {arm: 0 for arm in ARMS}
    for arm in ARMS:
        # New downstream member IDs; source agents do not join the target roster.
        members = (f"new-{arm}-member-1", f"new-{arm}-member-2")
        for task in holdout:
            trace = propose(
                task,
                arm=arm,
                members=members,
                index=source if arm == "C" else None,
                candidate=candidates[task.context] if arm == "D" else None,
            )
            traces.append(trace)
            outcomes[arm].append(oracle.grade(task, trace.submitted_answer))
            if arm == "C":
                history_reads[arm] += 2 * sum(
                    row.context == task.context for row in source.episodes
                )

    return ProbeReport(
        development_lock=source.development_lock_sha256,
        holdout_lock=_sha(
            {
                "purpose": "fixture-holdout-only",
                "tasks": [
                    (task.task_id, task.context, task.value, task.offset, task.factor)
                    for task in holdout
                ],
            }
        ),
        candidate_digests={
            context: None if candidate is None else candidate.digest
            for context, candidate in candidates.items()
        },
        source_episode_ids=tuple(row.episode_id for row in source.episodes),
        holdout_task_ids=tuple(task.task_id for task in holdout),
        traces=tuple(traces),
        outcomes={arm: tuple(rows) for arm, rows in outcomes.items()},
        history_reads=history_reads,
        compilation_rows_inspected=len(source.episodes),
    )
