"""C3R G2 exploratory apparatus: bounded evidence to candidate organizational procedure.

This module deliberately does not evaluate World truth, issue authority, or
promote candidate procedures. The evaluator must supply independently graded
episode records; the compiler only sees admitted observations.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Literal

from .protocol import EvidenceRef

Step = Literal["add", "multiply"]
Plan = tuple[Step, Step]
PLANS: tuple[Plan, ...] = (("add", "multiply"), ("multiply", "add"))
SCHEMA = "c3r-g2-procedure-candidate-v0.1"


def _canonical(payload: dict[str, object]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _digest(payload: dict[str, object]) -> str:
    return hashlib.sha256(_canonical(payload)).hexdigest()


def episode_digest(
    *, episode_id: str, source_agent_id: str, context: str, plan: Plan, success: bool
) -> str:
    """Digest of the reported observation, not proof its outcome is true."""
    return _digest(
        {
            "episode_id": episode_id,
            "source_agent_id": source_agent_id,
            "context": context,
            "plan": list(plan),
            "success": success,
        }
    )


@dataclass(frozen=True, slots=True)
class EvaluatedExperience:
    """Evaluator-supplied outcome; source provenance is not a trust credential."""

    episode_id: str
    source_agent_id: str
    context: str
    plan: Plan
    success: bool
    evidence_ref: EvidenceRef

    def __post_init__(self) -> None:
        if not all((self.episode_id, self.source_agent_id, self.context)):
            raise ValueError("episode, source, and context ids are required")
        if self.plan not in PLANS:
            raise ValueError("unrecognized executable plan")
        if type(self.success) is not bool:
            raise ValueError("success must be a boolean evaluator outcome")
        if self.evidence_ref.source_record_id != self.episode_id:
            raise ValueError("evidence reference must identify the episode")
        if self.evidence_ref.sha256 != episode_digest(
            episode_id=self.episode_id,
            source_agent_id=self.source_agent_id,
            context=self.context,
            plan=self.plan,
            success=self.success,
        ):
            raise ValueError("evidence digest does not match reported outcome")


@dataclass(frozen=True, slots=True)
class ExperienceEvidenceIndex:
    """Immutable admission snapshot supplied by an independent evaluator.

    Digest consistency is checked, but the index cannot authenticate who graded
    an episode. Scientific admission requires an external evaluator-owned lock.
    """

    evaluator_id: str
    development_lock_sha256: str
    episodes: tuple[EvaluatedExperience, ...]

    def __post_init__(self) -> None:
        if not self.evaluator_id.strip():
            raise ValueError("evaluator id is required")
        if len(self.development_lock_sha256) != 64 or any(
            c not in "0123456789abcdef" for c in self.development_lock_sha256
        ):
            raise ValueError("development lock must be a sha256 digest")
        ids = [episode.episode_id for episode in self.episodes]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate episode ids are forbidden")


@dataclass(frozen=True, slots=True)
class OrganizationalProcedure:
    """An experimental executable candidate, never an approved policy."""

    context: str
    plan: Plan
    source_episode_ids: tuple[str, ...]
    source_evidence_refs: tuple[EvidenceRef, ...]
    development_lock_sha256: str
    status: Literal["candidate"] = "candidate"

    def __post_init__(self) -> None:
        if not self.context or self.plan not in PLANS:
            raise ValueError("procedure context and plan are required")
        if not self.source_episode_ids or len(self.source_episode_ids) != len(
            self.source_evidence_refs
        ):
            raise ValueError("procedure requires matching source evidence")
        if self.status != "candidate":
            raise ValueError("procedures cannot self-promote")

    @property
    def digest(self) -> str:
        return _digest(
            {
                "schema": SCHEMA,
                "context": self.context,
                "plan": list(self.plan),
                "development_lock_sha256": self.development_lock_sha256,
                "source_episode_ids": list(self.source_episode_ids),
                "source_evidence_sha256": [ref.sha256 for ref in self.source_evidence_refs],
                "status": self.status,
            }
        )

    def execute(self, *, value: int, offset: int, factor: int) -> int:
        """Act on explicit public task inputs; does not inspect evaluator truth."""
        current = value
        for step in self.plan:
            if step == "add":
                current += offset
            else:
                current *= factor
        return current


@dataclass(frozen=True, slots=True)
class ProcedureCompiler:
    """Abstaining two-plan hypothesis, not a validated learning mechanism."""

    min_trials_per_plan: int = 2
    min_sources_per_plan: int = 2

    def __post_init__(self) -> None:
        if self.min_trials_per_plan < 1 or self.min_sources_per_plan < 1:
            raise ValueError("positive trial and independent-source floors are required")

    def compile(
        self, index: ExperienceEvidenceIndex, *, context: str
    ) -> OrganizationalProcedure | None:
        grouped: dict[Plan, list[EvaluatedExperience]] = {plan: [] for plan in PLANS}
        for episode in index.episodes:
            if episode.context == context:
                grouped[episode.plan].append(episode)
        for rows in grouped.values():
            if len(rows) < self.min_trials_per_plan:
                return None
            if len({row.source_agent_id for row in rows}) < self.min_sources_per_plan:
                return None

        successes = {
            plan: sum(row.success for row in rows) / len(rows)
            for plan, rows in grouped.items()
        }
        if successes[PLANS[0]] == successes[PLANS[1]]:
            return None
        winning_plan = max(PLANS, key=lambda plan: successes[plan])
        source = tuple(sorted(index.episodes, key=lambda row: row.episode_id))
        source = tuple(row for row in source if row.context == context)
        return OrganizationalProcedure(
            context=context,
            plan=winning_plan,
            source_episode_ids=tuple(row.episode_id for row in source),
            source_evidence_refs=tuple(row.evidence_ref for row in source),
            development_lock_sha256=index.development_lock_sha256,
        )


@dataclass(frozen=True, slots=True)
class HoldoutComparison:
    """Descriptive paired outcome from a separately locked, independent grader."""

    candidate_digest: str
    evaluator_id: str
    holdout_lock_sha256: str
    episode_ids: tuple[str, ...]
    treatment_success: tuple[bool, ...]
    control_success: tuple[bool, ...]

    def __post_init__(self) -> None:
        if not self.evaluator_id or not self.episode_ids:
            raise ValueError("holdout requires evaluator and nonempty units")
        if (
            len(self.episode_ids) != len(set(self.episode_ids))
            or len(self.episode_ids) != len(self.treatment_success)
            or len(self.episode_ids) != len(self.control_success)
        ):
            raise ValueError("holdout paired units are missing or repeated")
        if any(type(x) is not bool for x in (*self.treatment_success, *self.control_success)):
            raise ValueError("holdout outcomes must be boolean")
        if len(self.holdout_lock_sha256) != 64:
            raise ValueError("holdout lock is required")


class ProcedureValidationGate:
    """Check provenance/disjointness only; cannot award scientific promotion."""

    @staticmethod
    def descriptive_difference(
        candidate: OrganizationalProcedure, comparison: HoldoutComparison
    ) -> float:
        if candidate.status != "candidate" or comparison.candidate_digest != candidate.digest:
            raise ValueError("comparison is not bound to this candidate")
        if comparison.holdout_lock_sha256 == candidate.development_lock_sha256:
            raise ValueError("holdout must have a different frozen cohort lock")
        if set(comparison.episode_ids) & set(candidate.source_episode_ids):
            raise ValueError("development and holdout episode ids must be disjoint")
        return (
            sum(comparison.treatment_success) - sum(comparison.control_success)
        ) / len(comparison.episode_ids)
