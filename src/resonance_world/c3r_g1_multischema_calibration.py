"""Zero-network-by-default, eight-call G1 multischema *technical* calibration.

Prospective calibration-only public tasks: two source-format probes and six
matched qualification-format probes across two task algebras/three arms.
This NEVER grades answers, infers G1, opens an API connection, or retrieves a
credential by itself. An injected provider port is untrusted; physical send
and monetary caps must be enforced at that transport, not by this runner.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Protocol

from .c3r_g1_model_boundary import ModelChoiceCompletion
from .c3r_g1_multischema import ARMS, FAMILIES, Arm, Family, SchemaRequest, SchemaTask

LOGICAL_BUDGET = 8
TECHNICAL_MODEL = "glm-5.3"
STATES = frozenset({
    "accepted", "invalid_format", "wrong_model", "invalid_completion",
    "unfinished_output", "adapter_exception", "not_sent_after_failure",
})


def _hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


class CalibrationPort(Protocol):
    def complete_prompt(self, prompt: str) -> ModelChoiceCompletion: ...


@dataclass(frozen=True, slots=True)
class CalibrationProbe:
    stage: str
    family: Family
    arm: Arm
    task: SchemaTask

    def prompt(self) -> str:
        return SchemaRequest(
            "technical-calibration-only", self.arm, self.stage,
            self.task,
        ).prompt()


def make_calibration_plan() -> tuple[CalibrationProbe, ...]:
    """Never reuse G1 scientific/cohort task labels or hidden rule truth."""
    plan: list[CalibrationProbe] = []
    for family in FAMILIES:
        suffix = family.replace("arithmetic", "a").replace("text", "t")
        task = SchemaTask(
            task_id=f"cal-dev-{suffix}-0", context=f"technical-cal-{family}",
            family=family, **(
                {"value": 913, "offset": 4, "factor": 6}
                if family == "arithmetic" else {"text": "abnominalab"}
            ),
        )
        plan.append(CalibrationProbe("development", family, "learned", task))
    for family in FAMILIES:
        suffix = family.replace("arithmetic", "a").replace("text", "t")
        task = SchemaTask(
            task_id=f"cal-holdout-{suffix}-0", context=f"technical-cal-{family}",
            family=family, **(
                {"value": 1729, "offset": 3, "factor": 7}
                if family == "arithmetic" else {"text": "abtrialab"}
            ),
        )
        for arm in ARMS:
            plan.append(CalibrationProbe("qualification", family, arm, task))
    if len(plan) != LOGICAL_BUDGET:
        raise RuntimeError("calibration plan must prescribe exactly eight calls")
    return tuple(plan)


@dataclass(frozen=True, slots=True)
class CalibrationAttempt:
    stage: str
    family: Family
    arm: Arm
    task_id: str
    status: str
    answer_accepted: bool
    reported_completion_tokens: int | None
    reported_reasoning_tokens: int | None
    finish_reason: str | None

    def to_dict(self) -> dict[str, object]:
        return {
            "stage": self.stage,
            "family": self.family,
            "arm": self.arm,
            "task_id": self.task_id,
            "status": self.status,
            "answer_accepted": self.answer_accepted,
            "reported_completion_tokens": self.reported_completion_tokens,
            "reported_reasoning_tokens": self.reported_reasoning_tokens,
            "finish_reason": self.finish_reason,
        }


@dataclass(frozen=True, slots=True)
class CalibrationReport:
    expected_model_id: str
    plan_digest: str
    attempts: tuple[CalibrationAttempt, ...]

    def to_dict(self) -> dict[str, object]:
        rows = tuple(self.attempts)
        if len(rows) != LOGICAL_BUDGET:
            raise ValueError("calibration attempts do not match locked denominator")
        dev = [r for r in rows if r.stage == "development"]
        qual = [r for r in rows if r.stage == "qualification"]
        complete = sum(
            all(
                any(r.family == fam and r.arm == arm and r.answer_accepted
                    for r in qual)
                for arm in ARMS
            )
            for fam in FAMILIES
        )
        count = sum(r.answer_accepted for r in rows)
        quality = {
            fam: {
                "prescribed": sum(r.family == fam for r in rows),
                "parseable": sum(r.family == fam and r.answer_accepted for r in rows),
                "qualification_by_arm": {
                    arm: sum(r.family == fam and r.arm == arm and r.answer_accepted
                             for r in qual)
                    for arm in ARMS
                },
            }
            for fam in FAMILIES
        }
        return {
            "schema": "c3r-g1-multischema-calibration-v0.1",
            "classification": "technical_prompt_output_yield_only_no_G1_inference",
            "expected_model_id": self.expected_model_id,
            "public_plan_digest": self.plan_digest,
            "prescribed_logical_calls": LOGICAL_BUDGET,
            "answered_calls": count,
            "answer_yield": count / LOGICAL_BUDGET,
            "development_parseable": sum(r.answer_accepted for r in dev),
            "development_prescribed": len(dev),
            "qualification_complete_triplets": complete,
            "qualification_triplets_prescribed": len(FAMILIES),
            "per_family": quality,
            "attempt_records": [r.to_dict() for r in rows],
            "transport_records_not_authenticated": True,
            "provider_sends_verified": False,
            "provider_billing_verified": False,
            "technical_yield_gate": {
                "requires_all_eight": True,
                "requires_two_complete_triplets": True,
                "passed": count == LOGICAL_BUDGET and complete == len(FAMILIES),
                "authorizes_scientific_study": False,
                "authorizes_provider_sends": False,
            },
            "scientific_acceptance": False,
        }

    def canonical_bytes(self) -> bytes:
        return json.dumps(
            self.to_dict(), sort_keys=True, separators=(",", ":")
        ).encode("utf-8")


class CalibrationRunner:
    def __init__(self, model_id: str) -> None:
        if not isinstance(model_id, str) or not model_id.strip():
            raise ValueError("calibration requires an explicit model identity")
        self.model_id = model_id
        self.plan = make_calibration_plan()

    def run(self, port: CalibrationPort) -> CalibrationReport:
        records: list[CalibrationAttempt] = []
        stopped = False
        for probe in self.plan:
            reason = None
            completion_tokens = None
            reasoning_tokens = None
            if stopped:
                status = "not_sent_after_failure"
            else:
                try:
                    completion = port.complete_prompt(probe.prompt())
                except Exception:
                    status = "adapter_exception"
                else:
                    if not isinstance(completion, ModelChoiceCompletion):
                        status = "invalid_completion"
                    elif completion.model_id != self.model_id:
                        status = "wrong_model"
                    else:
                        reason = completion.finish_reason
                        completion_tokens = completion.completion_tokens_reported
                        reasoning_tokens = completion.reasoning_tokens_reported
                        if completion.finish_reason not in (None, "stop"):
                            status = "unfinished_output"
                        elif completion.output not in ("A", "B"):
                            status = "invalid_format"
                        else:
                            status = "accepted"
                if status != "accepted":
                    # No retries, best-of-N, self-repair or hidden extra sends.
                    stopped = True
            records.append(CalibrationAttempt(
                stage=probe.stage, family=probe.family, arm=probe.arm,
                task_id=probe.task.task_id, status=status,
                answer_accepted=status == "accepted",
                reported_completion_tokens=completion_tokens,
                reported_reasoning_tokens=reasoning_tokens,
                finish_reason=reason,
            ))
        return CalibrationReport(
            self.model_id,
            _hash([{
                "stage": x.stage, "family": x.family, "arm": x.arm,
                "task": x.task.public_tuple(), "prompt_sha256": hashlib.sha256(
                    x.prompt().encode("utf-8")
                ).hexdigest(),
            } for x in self.plan]),
            tuple(records),
        )


@dataclass(slots=True)
class _OfflineConstantPort:
    model_id: str

    def complete_prompt(self, _prompt: str) -> ModelChoiceCompletion:
        return ModelChoiceCompletion("A", self.model_id, finish_reason="stop")


def run_offline_calibration(model_id: str = TECHNICAL_MODEL) -> CalibrationReport:
    """Synthetic fixture; always zero external API calls."""
    return CalibrationRunner(model_id).run(_OfflineConstantPort(model_id))


def main() -> int:
    print(run_offline_calibration().canonical_bytes().decode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
