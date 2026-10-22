"""Default-off C3R model boundary and independently graded G1 construction runner.

This module contains no SDK, credential lookup, HTTP transport, or model
invocation entry point. A caller must explicitly inject a ModelChoicePort.
This is a deterministic integration contract, NOT authorized provider execution.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Literal, Protocol

from .c3r_g2 import EvaluatedExperience, ExperienceEvidenceIndex, Plan, episode_digest
from .c3r_g2_probe import FixtureOracle, PublicTask
from .protocol import EvidenceRef

Stage = Literal["development", "qualification"]
Status = Literal[
    "accepted", "invalid_format", "adapter_exception", "invalid_adapter_result",
    "reported_send_cap_exceeded",
]


def _digest(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _task_payload(task: PublicTask) -> tuple[str, int, int, int]:
    return (task.context, task.value, task.offset, task.factor)


@dataclass(frozen=True, slots=True)
class SourceFeedback:
    """Admissible *development only* feedback from earlier submitted actions."""

    task_id: str
    context: str
    plan: Plan
    success: bool


@dataclass(frozen=True, slots=True)
class ModelChoiceRequest:
    """Public information visible to a model, with no evaluator state."""

    owner_id: str
    stage: Stage
    task: PublicTask
    feedback: tuple[SourceFeedback, ...] = ()

    def __post_init__(self) -> None:
        if not self.owner_id.strip() or self.stage not in ("development", "qualification"):
            raise ValueError("invalid model request identity or stage")
        if not re.fullmatch(r"[a-zA-Z0-9_.-]{1,80}", self.task.context):
            raise ValueError("context must be an opaque non-instruction label")
        if len({item.task_id for item in self.feedback}) != len(self.feedback):
            raise ValueError("feedback cannot repeat task IDs")
        if any(item.task_id == self.task.task_id for item in self.feedback):
            raise ValueError("target feedback leakage")
        if any(item.context != self.task.context for item in self.feedback):
            raise ValueError("cross-context feedback is forbidden")

    def prompt(self) -> str:
        """Build a strict A/B choice prompt; never include expected answer."""
        prior = "\n".join(
            f"{item.task_id}: choice={'A' if item.plan == ('add', 'multiply') else 'B'};"
            f" success={str(item.success).lower()}"
            for item in self.feedback
        )
        return (
            "Software engineering task: select a Python implementation for a\n"
            "two-operation function. Reply with exactly A or B.\n"
            "A implements: return (value + offset) * factor\n"
            "B implements: return value * factor + offset\n"
            "Some contexts use one ordering and others use the other; learn from "
            "development feedback, not from task labels.\n"
            f"Context: {self.task.context}\n"
            f"Value: {self.task.value}; offset: {self.task.offset}; "
            f"factor: {self.task.factor}\n"
            f"Past graded development attempts:\n{prior if prior else '(none)'}\n"
            "Reply exactly A or B."
        )


@dataclass(frozen=True, slots=True)
class ModelChoiceCompletion:
    """Transport metadata supplied by the injected adapter, never trusted as proof."""

    output: str
    model_id: str
    physical_sends_reported: int = 0
    prompt_tokens_reported: int | None = None
    completion_tokens_reported: int | None = None
    finish_reason: str | None = None
    reasoning_present: bool | None = None
    reasoning_tokens_reported: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.output, str) or not self.model_id.strip():
            raise ValueError("model completion fields are invalid")
        numbers = (
            self.physical_sends_reported,
            self.prompt_tokens_reported,
            self.completion_tokens_reported,
            self.reasoning_tokens_reported,
        )
        if any(value is not None and (type(value) is not int or value < 0) for value in numbers):
            raise ValueError("reported usage must be nonnegative integers")
        if self.finish_reason is not None and (
            not isinstance(self.finish_reason, str) or len(self.finish_reason) > 48
        ):
            raise ValueError("finish reason metadata is invalid")
        if self.reasoning_present is not None and type(self.reasoning_present) is not bool:
            raise ValueError("reasoning presence must be boolean")


class ModelChoicePort(Protocol):
    """Inject a model outside this module; no production provider is implemented."""

    def complete(self, request: ModelChoiceRequest) -> ModelChoiceCompletion: ...


@dataclass(frozen=True, slots=True)
class ModelCohortLock:
    """Fixture-owned split freeze. For science an external party must attest it."""

    development: tuple[PublicTask, ...]
    qualification: tuple[PublicTask, ...]

    def __post_init__(self) -> None:
        if not self.development or not self.qualification:
            raise ValueError("both development and qualification splits are required")
        all_tasks = (*self.development, *self.qualification)
        if len({task.task_id for task in all_tasks}) != len(all_tasks):
            raise ValueError("duplicate task ids across splits")
        if len({_task_payload(task) for task in all_tasks}) != len(all_tasks):
            raise ValueError("duplicate task inputs across splits")

    @property
    def digest(self) -> str:
        return _digest(
            {
                "schema": "c3r-g1-fixture-cohort-v0.1",
                "development": [
                    (t.task_id, *_task_payload(t)) for t in self.development
                ],
                "qualification": [
                    (t.task_id, *_task_payload(t)) for t in self.qualification
                ],
            }
        )


@dataclass(frozen=True, slots=True)
class GradedAttempt:
    """Bounded observable outcome; never preserve raw model output or prompt."""

    stage: Stage
    owner_id: str
    task_id: str
    status: Status
    plan: Plan | None
    success: bool | None
    output_sha256: str | None
    model_id: str | None
    physical_sends_reported: int | None
    prompt_tokens_reported: int | None
    completion_tokens_reported: int | None
    error_class: str | None = None
    finish_reason: str | None = None
    reasoning_present: bool | None = None
    reasoning_tokens_reported: int | None = None

    def __post_init__(self) -> None:
        if (self.status == "accepted") != (self.plan is not None and self.success is not None):
            raise ValueError("accepted action must have a graded result, otherwise neither")


def _read_choice(raw: str) -> Plan | None:
    if raw == "A":
        return ("add", "multiply")
    if raw == "B":
        return ("multiply", "add")
    return None


class ModelG1Runner:
    """Runner owns the grader; injected ports receive only public requests.

    This is an in-process *API boundary*, not a secure process isolation or
    independently attested evaluation service.
    """

    def __init__(
        self, *,
        oracle: FixtureOracle,
        cohort: ModelCohortLock,
        max_reported_sends_per_call: int = 1,
    ) -> None:
        if max_reported_sends_per_call < 0:
            raise ValueError("reported send cap must be nonnegative")
        self._oracle = oracle
        self._cohort = cohort
        self._max_sends = max_reported_sends_per_call

    def _attempt(
        self,
        *,
        port: ModelChoicePort,
        request: ModelChoiceRequest,
    ) -> GradedAttempt:
        task = request.task
        try:
            completion = port.complete(request)
        except Exception as exc:
            return GradedAttempt(
                request.stage, request.owner_id, task.task_id, "adapter_exception",
                None, None, None, None, None, None, None, type(exc).__name__,
            )
        if not isinstance(completion, ModelChoiceCompletion):
            return GradedAttempt(
                request.stage, request.owner_id, task.task_id, "invalid_adapter_result",
                None, None, None, None, None, None, None, "WrongResultType",
            )
        output_sha = hashlib.sha256(completion.output.encode("utf-8")).hexdigest()
        base = {
            "output_sha256": output_sha,
            "model_id": completion.model_id,
            "physical_sends_reported": completion.physical_sends_reported,
            "prompt_tokens_reported": completion.prompt_tokens_reported,
            "completion_tokens_reported": completion.completion_tokens_reported,
            "finish_reason": completion.finish_reason,
            "reasoning_present": completion.reasoning_present,
            "reasoning_tokens_reported": completion.reasoning_tokens_reported,
        }
        if completion.physical_sends_reported > self._max_sends:
            return GradedAttempt(
                request.stage, request.owner_id, task.task_id, "reported_send_cap_exceeded",
                None, None, **base,
            )
        plan = _read_choice(completion.output)
        if plan is None:
            return GradedAttempt(
                request.stage, request.owner_id, task.task_id, "invalid_format",
                None, None, **base,
            )
        # Truth enters only after the action was committed and parsed.
        from .c3r_g2_probe import apply_public_plan

        grade = self._oracle.grade(task, apply_public_plan(task, plan))
        return GradedAttempt(
            request.stage, request.owner_id, task.task_id, "accepted",
            plan, grade, **base,
        )

    def execute(
        self, *,
        owner_id: str,
        learned_port: ModelChoicePort,
        fresh_port: ModelChoicePort,
    ) -> ModelG1Report:
        if not owner_id.strip():
            raise ValueError("source owner id required")
        development: list[GradedAttempt] = []
        feedback: list[SourceFeedback] = []
        evidence: list[EvaluatedExperience] = []
        for task in self._cohort.development:
            matching = tuple(item for item in feedback if item.context == task.context)
            attempt = self._attempt(
                port=learned_port,
                request=ModelChoiceRequest(owner_id, "development", task, matching),
            )
            development.append(attempt)
            if attempt.status == "accepted":
                assert attempt.plan is not None and attempt.success is not None
                feedback.append(
                    SourceFeedback(task.task_id, task.context, attempt.plan, attempt.success)
                )
                digest = episode_digest(
                    episode_id=task.task_id,
                    source_agent_id=owner_id,
                    context=task.context,
                    plan=attempt.plan,
                    success=attempt.success,
                )
                evidence.append(
                    EvaluatedExperience(
                        task.task_id,
                        owner_id,
                        task.context,
                        attempt.plan,
                        attempt.success,
                        EvidenceRef(
                            uri=f"fixture-model-grade://{self._cohort.digest}/{task.task_id}",
                            sha256=digest,
                            source_record_id=task.task_id,
                        ),
                    )
                )
        qualification_learned: list[GradedAttempt] = []
        qualification_fresh: list[GradedAttempt] = []
        for task in self._cohort.qualification:
            matching = tuple(item for item in feedback if item.context == task.context)
            qualification_learned.append(
                self._attempt(
                    port=learned_port,
                    request=ModelChoiceRequest(owner_id, "qualification", task, matching),
                )
            )
            # No feedback from *any* qualification attempt is delivered onward.
            qualification_fresh.append(
                self._attempt(
                    port=fresh_port,
                    request=ModelChoiceRequest(owner_id, "qualification", task),
                )
            )

        index = ExperienceEvidenceIndex(
            evaluator_id="unattested-local-fixture",
            development_lock_sha256=self._cohort.digest,
            episodes=tuple(evidence),
        )
        return ModelG1Report(
            cohort_digest=self._cohort.digest,
            development=tuple(development),
            learned=tuple(qualification_learned),
            fresh=tuple(qualification_fresh),
            evidence_index=index,
        )


@dataclass(frozen=True, slots=True)
class ModelG1Report:
    """Construction report. The supplied model port is not certified to be real."""

    cohort_digest: str
    development: tuple[GradedAttempt, ...]
    learned: tuple[GradedAttempt, ...]
    fresh: tuple[GradedAttempt, ...]
    evidence_index: ExperienceEvidenceIndex

    def to_dict(self) -> dict[str, object]:
        def tally(rows: tuple[GradedAttempt, ...]) -> dict[str, object]:
            statuses = sorted(set(row.status for row in rows))
            return {
                "attempts": len(rows),
                "accepted": sum(row.status == "accepted" for row in rows),
                "successes": sum(row.success is True for row in rows),
                "failures_by_status": {
                    status: sum(row.status == status for row in rows)
                    for status in statuses if status != "accepted"
                },
                "physical_sends_reported": sum(
                    row.physical_sends_reported or 0 for row in rows
                ),
                "prompt_tokens_reported": sum(
                    row.prompt_tokens_reported or 0 for row in rows
                ),
                "completion_tokens_reported": sum(
                    row.completion_tokens_reported or 0 for row in rows
                ),
                "reasoning_tokens_reported": sum(
                    row.reasoning_tokens_reported or 0 for row in rows
                ),
                "empty_output_count": sum(
                    row.output_sha256
                    == hashlib.sha256(b"").hexdigest() for row in rows
                ),
            }

        return {
            "schema": "c3r-g1-model-boundary-construction-v0.1",
            "status": "construction_only_not_scientific_evidence",
            "port_type": "injected_unverified_adapter",
            "cohort_digest": self.cohort_digest,
            "development": tally(self.development),
            "qualification_learned": tally(self.learned),
            "qualification_fresh": tally(self.fresh),
            "paired_analyzable": sum(
                a.status == b.status == "accepted"
                for a, b in zip(self.learned, self.fresh, strict=True)
            ),
            "source_evidence_count": len(self.evidence_index.episodes),
            "bounded_observations": [
                {
                    "stage": row.stage,
                    "task_id": row.task_id,
                    "owner_id": row.owner_id,
                    "status": row.status,
                    "model_id": row.model_id,
                    "output_sha256": row.output_sha256,
                    "error_class": row.error_class,
                    "physical_sends_reported": row.physical_sends_reported,
                    "finish_reason": row.finish_reason,
                    "reasoning_present": row.reasoning_present,
                    "reasoning_tokens_reported": row.reasoning_tokens_reported,
                    "completion_tokens_reported": row.completion_tokens_reported,
                }
                for row in (*self.development, *self.learned, *self.fresh)
            ],
            "warnings": [
                "no real model transport is implemented or authorized",
                "in-process evaluator separation is not independent attestation",
                "adapter-reported sends/tokens cannot enforce a provider-side cap",
                "all attempts count toward yield; missing completions are not successes",
                "qualification feedback is never returned to the model",
                "paired outcome summaries are descriptive, not inferential",
                "one source, no independent organizational units or G2 claim",
            ],
        }

    def canonical_bytes(self) -> bytes:
        return json.dumps(
            self.to_dict(), sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
