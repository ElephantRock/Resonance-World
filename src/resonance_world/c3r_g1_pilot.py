"""G1 three-arm acquisition pilot: deterministic, credential-free apparatus only.

The experimental unit is one independently reset learner, NOT one heldout
question. No provider client, network call, evaluator attestation, causal
estimate, confidence interval or scientific admission is implemented here.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from .c3r_g1_model_boundary import (
    ModelChoiceCompletion,
    ModelChoicePort,
    ModelChoiceRequest,
    SourceFeedback,
)
from .c3r_g2 import PLANS, Plan
from .c3r_g2_probe import FixtureOracle, PublicTask, apply_public_plan

PilotArm = Literal["learned", "fresh", "placebo"]
PILOT_ARMS: tuple[PilotArm, ...] = ("learned", "fresh", "placebo")
Status = Literal[
    "accepted", "invalid_format", "adapter_exception",
    "invalid_adapter_result", "wrong_model",
]


def _hash(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


@dataclass(frozen=True, slots=True)
class PilotDesign:
    """Prospective *fixture* sizes; not a power calculation or live budget."""

    units: int = 8
    contexts_per_unit: int = 2
    development_per_context: int = 6
    qualification_per_context: int = 8
    seed: int = 20261022
    model_id: str = "offline-fixture-model"

    def __post_init__(self) -> None:
        values = (
            self.units,
            self.contexts_per_unit,
            self.development_per_context,
            self.qualification_per_context,
        )
        if any(type(value) is not int or not 1 <= value <= 16 for value in values):
            raise ValueError("pilot sizes must be bounded positive integers")
        if type(self.seed) is not int or self.seed < 0 or self.seed > 2**32 - 1:
            raise ValueError("pilot seed must be a nonnegative uint32")
        if not self.model_id.strip() or len(self.model_id) > 80:
            raise ValueError("explicit bounded model id required")
        if self.contexts_per_unit != 2:
            raise ValueError("pilot v1 uses two balanced fixture contexts per unit")
        if self.required_calls > 480:
            raise ValueError("pilot v1 cannot prescribe more than 480 logical calls")

    @property
    def qualification_triplets(self) -> int:
        return self.units * self.contexts_per_unit * self.qualification_per_context

    @property
    def required_calls(self) -> int:
        training = self.units * self.contexts_per_unit * self.development_per_context
        qualification = 3 * self.qualification_triplets
        return training + qualification

    def freeze(self) -> PilotLock:
        units: list[PilotUnit] = []
        for index in range(self.units):
            contexts: list[PilotContext] = []
            for family in range(self.contexts_per_unit):
                context = f"pilot-u{index:03d}-family-{family}"
                # Counterbalanced across units, not encoded in the public task.
                hidden = PLANS[(self.seed + index + family) % len(PLANS)]
                dev: list[PublicTask] = []
                qual: list[PublicTask] = []
                for stage, count, offset in (
                    ("development", self.development_per_context, 0),
                    ("qualification", self.qualification_per_context, 16),
                ):
                    for number in range(count):
                        serial = ((index * 2 + family) * 100) + offset + number
                        task = PublicTask(
                            task_id=f"{stage}-u{index:03d}-f{family}-{number}",
                            context=context,
                            value=1000 + serial * 17,
                            offset=1 + serial % 7,
                            factor=2 + (serial // 3) % 7,
                        )
                        (dev if stage == "development" else qual).append(task)
                contexts.append(PilotContext(context, hidden, tuple(dev), tuple(qual)))
            units.append(PilotUnit(f"pilot-unit-{index:03d}", tuple(contexts)))
        return PilotLock(self, tuple(units))


@dataclass(frozen=True, slots=True)
class PilotContext:
    context: str
    hidden_plan: Plan  # private fixture truth; never serialized or supplied to a port
    development: tuple[PublicTask, ...]
    qualification: tuple[PublicTask, ...]


@dataclass(frozen=True, slots=True)
class PilotUnit:
    unit_id: str
    contexts: tuple[PilotContext, ...]


@dataclass(frozen=True, slots=True)
class PilotLock:
    design: PilotDesign
    units: tuple[PilotUnit, ...]

    def __post_init__(self) -> None:
        seen_ids: set[str] = set()
        seen_payloads: set[tuple[str, int, int, int]] = set()
        for unit in self.units:
            if len(unit.contexts) != self.design.contexts_per_unit:
                raise ValueError("unit context count violates design lock")
            for context in unit.contexts:
                if len(context.development) != self.design.development_per_context:
                    raise ValueError("development count violates design lock")
                if len(context.qualification) != self.design.qualification_per_context:
                    raise ValueError("qualification count violates design lock")
                if context.hidden_plan not in PLANS:
                    raise ValueError("unknown fixture evaluator target")
                for task in (*context.development, *context.qualification):
                    if task.context != context.context or task.task_id in seen_ids:
                        raise ValueError("task context or identifier collision")
                    payload = (task.context, task.value, task.offset, task.factor)
                    if payload in seen_payloads:
                        raise ValueError("public payload collision across all splits")
                    seen_ids.add(task.task_id)
                    seen_payloads.add(payload)
        if len({unit.unit_id for unit in self.units}) != len(self.units):
            raise ValueError("independent learner IDs must be distinct")
        if len(self.units) != self.design.units:
            raise ValueError("unit count violates design lock")

    @property
    def digest(self) -> str:
        return _hash({
            "schema": "c3r-g1-pilot-lock-v1",
            "design": {
                "seed": self.design.seed,
                "units": self.design.units,
                "contexts": self.design.contexts_per_unit,
                "development": self.design.development_per_context,
                "qualification": self.design.qualification_per_context,
                "model_id": self.design.model_id,
            },
            "units": [
                {
                    "unit_id": unit.unit_id,
                    "tasks": [
                        [stage, task.task_id, task.context, task.value, task.offset,
                         task.factor]
                        for ctx in unit.contexts
                        for stage, tasks in (
                            ("development", ctx.development),
                            ("qualification", ctx.qualification),
                        )
                        for task in tasks
                    ],
                }
                for unit in self.units
            ],
        })


@dataclass(frozen=True, slots=True)
class PilotAttempt:
    unit_id: str
    arm: PilotArm
    stage: Literal["development", "qualification"]
    task_id: str
    status: Status
    success: bool  # ITT: invalid/failed attempts are failures, never discarded
    plan: Plan | None
    context: str


@dataclass(frozen=True, slots=True)
class PilotReport:
    lock_digest: str
    design: PilotDesign
    rows: tuple[PilotAttempt, ...]
    history_counts: tuple[tuple[str, str, int, int], ...]

    def to_dict(self) -> dict[str, object]:
        trials = [row for row in self.rows if row.stage == "qualification"]
        per_unit: list[dict[str, object]] = []
        complete_triplets = 0
        for unit_index in range(self.design.units):
            unit_id = f"pilot-unit-{unit_index:03d}"
            by_arm = {arm: [row for row in trials if row.unit_id == unit_id
                             and row.arm == arm] for arm in PILOT_ARMS}
            expected = self.design.contexts_per_unit * self.design.qualification_per_context
            if any(len(rows) != expected for rows in by_arm.values()):
                raise ValueError("missing arm or qualification attempt")
            success = {arm: sum(row.success for row in rows)
                       for arm, rows in by_arm.items()}
            accepted = {arm: sum(row.status == "accepted" for row in rows)
                        for arm, rows in by_arm.items()}
            per_unit.append({
                "unit_id": unit_id,
                "prescribed_per_arm": expected,
                "success_by_arm": success,
                "accepted_by_arm": accepted,
                "itt_learned_minus_fresh": (success["learned"] - success["fresh"]) / expected,
                "itt_learned_minus_placebo": (
                    success["learned"] - success["placebo"]
                ) / expected,
            })
        task_ids = sorted({row.task_id for row in trials})
        for unit_index in range(self.design.units):
            unit_id = f"pilot-unit-{unit_index:03d}"
            for task_id in task_ids:
                matched = [row for row in trials if row.unit_id == unit_id
                           and row.task_id == task_id]
                if matched and len(matched) == 3 and all(
                    row.status == "accepted" for row in matched
                ):
                    complete_triplets += 1
        denominator = self.design.qualification_triplets
        observed = sum(row.status == "accepted" for row in trials)
        development = [row for row in self.rows if row.stage == "development"]
        per_arm = {
            arm: {
                "prescribed": sum(row.arm == arm for row in trials),
                "accepted": sum(
                    row.status == "accepted" for row in trials if row.arm == arm
                ),
                "itt_successes": sum(
                    row.success for row in trials if row.arm == arm
                ),
                "failures_by_status": {
                    status: sum(
                        row.status == status for row in trials if row.arm == arm
                    )
                    for status in (
                        "invalid_format", "adapter_exception",
                        "invalid_adapter_result", "wrong_model",
                    )
                },
            }
            for arm in PILOT_ARMS
        }
        action_yield = observed / (3 * denominator)
        triplet_yield = complete_triplets / denominator
        # These are proposed *engineering* gates, not scientific G1 gates.
        engineering_ready = (
            action_yield >= 0.95
            and triplet_yield >= 0.90
            and all(row.status == "accepted" for row in development)
        )
        result: dict[str, object] = {
            "schema": "c3r-g1-three-arm-pilot-v1",
            "status": "offline_fixture_only_no_scientific_inference",
            "pilot_lock": self.lock_digest,
            "planned_model_calls": self.design.required_calls,
            "independent_learner_units": self.design.units,
            "heldout_triplets_prescribed": denominator,
            "heldout_triplets_accepted_all_arms": complete_triplets,
            "heldout_triplet_yield": triplet_yield,
            "qual_attempts_prescribed": 3 * denominator,
            "qual_actions_accepted": observed,
            "qual_action_yield": action_yield,
            "qualification_by_arm": per_arm,
            "development_prescribed": len(development),
            "development_accepted": sum(
                row.status == "accepted" for row in development
            ),
            "technical_yield_gate": {
                "min_qualification_action_yield": 0.95,
                "min_complete_triplet_yield": 0.90,
                "requires_all_development_actions_parseable": True,
                "passed_in_fixture": engineering_ready,
                "authority_to_start_live_campaign": False,
            },
            "per_unit": per_unit,
            "mean_unit_itt_learned_minus_fresh": sum(
                row["itt_learned_minus_fresh"] for row in per_unit
            ) / self.design.units,
            "mean_unit_itt_learned_minus_placebo": sum(
                row["itt_learned_minus_placebo"] for row in per_unit
            ) / self.design.units,
            "history_exposure_counts": [
                {"unit_id": uid, "context": ctx,
                 "learned": learned, "placebo": sham}
                for uid, ctx, learned, sham in self.history_counts
            ],
            "evaluated_successes_from_all_prescribed_tasks": True,
            "statistical_test_performed": False,
            "independent_evaluator_attested": False,
            "actual_provider_sends_verified": False,
            "scientific_acceptance": False,
            "warnings": [
                "synthetic fixture; not a real model-mediated acquisition result",
                "two opaque contexts within ONE arithmetic task schema, not two "
                "independent task families or out-of-schema generalization",
                "placebo has same observed plan/task history but synthetic "
                "non-outcome labels; not a token-equal or perfectly blind control",
                "fresh is a distinct port with no development/feedback; "
                "provider session equality and isolation are unverified",
                "separate learner units, not holdout questions, are inferential units",
                "no p-values, confidence intervals, power or G1/G2 promotion",
            ],
        }
        return result

    def canonical_bytes(self) -> bytes:
        return json.dumps(self.to_dict(), sort_keys=True,
                          separators=(",", ":")).encode("utf-8")


PortFactory = Callable[[str, PilotArm], ModelChoicePort]


class PilotRunner:
    """Uses fixture oracle internally; injected ports receive public requests only."""

    def __init__(self, lock: PilotLock) -> None:
        self.lock = lock

    def _attempt(
        self, *, unit_id: str, arm: PilotArm, stage: Literal["development", "qualification"],
        task: PublicTask, feedback: tuple[SourceFeedback, ...],
        port: ModelChoicePort, oracle: FixtureOracle,
    ) -> PilotAttempt:
        request = ModelChoiceRequest(
            owner_id=f"{unit_id}-{arm}", stage=stage, task=task, feedback=feedback
        )
        try:
            completion = port.complete(request)
        except Exception:
            return PilotAttempt(unit_id, arm, stage, task.task_id,
                                "adapter_exception", False, None, task.context)
        if not isinstance(completion, ModelChoiceCompletion):
            return PilotAttempt(unit_id, arm, stage, task.task_id,
                                "invalid_adapter_result", False, None, task.context)
        if completion.model_id != self.lock.design.model_id:
            return PilotAttempt(unit_id, arm, stage, task.task_id,
                                "wrong_model", False, None, task.context)
        if completion.output == "A":
            plan = PLANS[0]
        elif completion.output == "B":
            plan = PLANS[1]
        else:
            return PilotAttempt(unit_id, arm, stage, task.task_id,
                                "invalid_format", False, None, task.context)
        grade = oracle.grade(task, apply_public_plan(task, plan))
        return PilotAttempt(unit_id, arm, stage, task.task_id,
                            "accepted", grade, plan, task.context)

    def run(self, *, port_factory: PortFactory) -> PilotReport:
        rows: list[PilotAttempt] = []
        exposure: list[tuple[str, str, int, int]] = []
        used_ports: list[ModelChoicePort] = []
        for unit in self.lock.units:
            ports = {arm: port_factory(unit.unit_id, arm) for arm in PILOT_ARMS}
            if any(port is None or not callable(getattr(port, "complete", None))
                   for port in ports.values()):
                raise ValueError("each arm must provide a callable model port")
            if any(port is seen for port in ports.values() for seen in used_ports):
                raise ValueError("learner units cannot reuse model-port objects")
            if len({id(port) for port in ports.values()}) != 3:
                raise ValueError("learned, fresh and placebo ports must be distinct")
            used_ports.extend(ports.values())
            oracle = FixtureOracle({
                context.context: context.hidden_plan for context in unit.contexts
            })
            context_history: dict[str, tuple[tuple[SourceFeedback, ...],
                                             tuple[SourceFeedback, ...]]] = {}
            # Only the learned arm performs development; fresh receives none,
            # placebo receives a fake-label *copy* of accepted source history.
            for ctx in unit.contexts:
                acquired: list[SourceFeedback] = []
                for task in ctx.development:
                    attempt = self._attempt(
                        unit_id=unit.unit_id, arm="learned", stage="development",
                        task=task, feedback=tuple(acquired),
                        port=ports["learned"], oracle=oracle,
                    )
                    rows.append(attempt)
                    if attempt.status == "accepted":
                        assert attempt.plan is not None
                        acquired.append(SourceFeedback(
                            task.task_id, task.context, attempt.plan, attempt.success,
                        ))
                sham: list[SourceFeedback] = []
                for original in acquired:
                    # Independent pseudorandom sham labels: NOT oracle outcomes.
                    bit = int(_hash([
                        "independent-sham-v1", self.lock.design.seed,
                        unit.unit_id, original.task_id,
                    ])[:8], 16) % 2
                    sham.append(SourceFeedback(
                        original.task_id, original.context, original.plan, bool(bit),
                    ))
                context_history[ctx.context] = (tuple(acquired), tuple(sham))
                exposure.append((unit.unit_id, ctx.context, len(acquired), len(sham)))

            for ctx in unit.contexts:
                learned, sham = context_history[ctx.context]
                for index, task in enumerate(ctx.qualification):
                    # Rotation mitigates fixed order; within each task all arms
                    # see the exact same public task, but no qualification grade.
                    offset = (index + int(unit.unit_id[-3:])) % 3
                    for arm in (*PILOT_ARMS[offset:], *PILOT_ARMS[:offset]):
                        feedback = (learned if arm == "learned"
                                    else sham if arm == "placebo" else ())
                        rows.append(self._attempt(
                            unit_id=unit.unit_id, arm=arm,
                            stage="qualification", task=task, feedback=feedback,
                            port=ports[arm], oracle=oracle,
                        ))
        if len(rows) != self.lock.design.required_calls:
            raise RuntimeError("failed to account for all prescribed calls")
        return PilotReport(self.lock.digest, self.lock.design, tuple(rows),
                           tuple(exposure))


@dataclass(slots=True)
class _ConstantOfflinePort:
    """Synthetic exact-A policy. Never uses the grader or external provider."""

    model_id: str

    def complete(self, request: ModelChoiceRequest) -> ModelChoiceCompletion:
        return ModelChoiceCompletion(output="A", model_id=self.model_id)


def run_offline_fixture(design: PilotDesign | None = None) -> PilotReport:
    """Null-control smoke: all arms choose A; causal deltas must remain zero."""
    design = design or PilotDesign()
    return PilotRunner(design.freeze()).run(
        port_factory=lambda _unit, _arm: _ConstantOfflinePort(design.model_id)
    )


def main() -> int:
    print(run_offline_fixture().canonical_bytes().decode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
