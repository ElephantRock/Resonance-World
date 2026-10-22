"""G1 two-schema three-arm pilot v2: OFFLINE construction, NOT scientific evidence.

Two genuinely different public action algebras (integer arithmetic and text
transforms), while the answer key is owned by a separate *local* evaluator.
No provider implementation, credential lookup, certified isolation or inference.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal, Protocol

from .c3r_g1_model_boundary import ModelChoiceCompletion

Family = Literal["arithmetic", "text"]
Arm = Literal["learned", "fresh", "placebo"]
Stage = Literal["development", "qualification"]
FAMILIES: tuple[Family, ...] = ("arithmetic", "text")
ARMS: tuple[Arm, ...] = ("learned", "fresh", "placebo")
STATUSES = ("accepted", "invalid_format", "adapter_exception", "invalid_completion",
            "wrong_model")


def _digest(value: object) -> str:
    data = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


@dataclass(frozen=True, slots=True)
class SchemaTask:
    task_id: str
    context: str
    family: Family
    value: int | None = None
    offset: int | None = None
    factor: int | None = None
    text: str | None = None

    def __post_init__(self) -> None:
        if not self.task_id or not self.context or self.family not in FAMILIES:
            raise ValueError("invalid public task identity or family")
        if self.family == "arithmetic":
            if (any(type(x) is not int for x in (self.value, self.offset, self.factor))
                    or self.offset < 1 or self.factor < 2 or self.text is not None):
                raise ValueError("arithmetic task requires only three valid operands")
        elif (not isinstance(self.text, str) or "ab" not in self.text
              or self.text.upper() == self.text
              or any(x is not None for x in (self.value, self.offset, self.factor))):
            raise ValueError("text task requires a noncommuting lowercase input")

    def public_tuple(self) -> tuple[object, ...]:
        return (self.task_id, self.context, self.family,
                self.value, self.offset, self.factor, self.text)

    def prompt(self) -> str:
        if self.family == "arithmetic":
            description = (
                "Choose a Python implementation for an integer expression.\n"
                "A: return (value + offset) * factor\n"
                "B: return value * factor + offset\n"
                f"value={self.value}; offset={self.offset}; factor={self.factor}"
            )
        else:
            description = (
                "Choose a Python implementation for a text transformation.\n"
                "A: return text.replace('ab', 'z').upper()\n"
                "B: return text.upper().replace('ab', 'z')\n"
                f"text={self.text!r}"
            )
        return (
            f"{description}\nContext: {self.context}\n"
            "A context has one fixed correct operation order, but the "
            "target ordering is private and may differ across contexts.\n"
            "Reply with exactly A or B."
        )


def apply_choice(task: SchemaTask, choice: str) -> int | str:
    """Public executable semantics; no access to evaluator targets."""
    if choice not in ("A", "B"):
        raise ValueError("only exact A/B are executable")
    if task.family == "arithmetic":
        assert task.value is not None
        assert task.offset is not None and task.factor is not None
        if choice == "A":
            return (task.value + task.offset) * task.factor
        return task.value * task.factor + task.offset
    assert task.text is not None
    if choice == "A":
        return task.text.replace("ab", "z").upper()
    return task.text.upper().replace("ab", "z")


@dataclass(frozen=True, slots=True)
class Feedback:
    task_id: str
    context: str
    choice: Literal["A", "B"]
    success: bool

    def __post_init__(self) -> None:
        if self.choice not in ("A", "B") or type(self.success) is not bool:
            raise ValueError("feedback requires a valid choice and Boolean grade")
        if not self.task_id or not self.context:
            raise ValueError("feedback identity required")


@dataclass(frozen=True, slots=True)
class SchemaRequest:
    unit_id: str
    arm: Arm
    stage: Stage
    task: SchemaTask
    feedback: tuple[Feedback, ...] = ()

    def __post_init__(self) -> None:
        if self.arm not in ARMS or self.stage not in ("development", "qualification"):
            raise ValueError("invalid arm or stage")
        if self.stage == "development" and self.arm != "learned":
            raise ValueError("only the learned arm trains")
        if self.arm == "fresh" and self.feedback:
            raise ValueError("fresh baseline cannot see source feedback")
        if self.stage == "development" and any(
            not item.task_id.startswith("dev-") for item in self.feedback
        ):
            raise ValueError("nondevelopment feedback leaked")
        if len({f.task_id for f in self.feedback}) != len(self.feedback):
            raise ValueError("duplicate feedback IDs")
        if any(f.context != self.task.context or f.task_id == self.task.task_id
               or not f.task_id.startswith("dev-") for f in self.feedback):
            raise ValueError("source/holdout feedback contamination")

    def prompt(self) -> str:
        prior = "\n".join(
            f"{item.task_id}: choice={item.choice}; success={str(item.success).lower()}"
            for item in self.feedback
        ) or "(none)"
        return f"{self.task.prompt()}\nPrior graded development attempts:\n{prior}"


class SchemaPort(Protocol):
    def complete(self, request: SchemaRequest) -> ModelChoiceCompletion: ...


@dataclass(frozen=True, slots=True)
class V2Design:
    units: int = 8
    development_per_family: int = 6
    qualification_per_family: int = 8
    public_seed: int = 20261022
    model_id: str = "offline-schema-fixture"

    def __post_init__(self) -> None:
        if any(type(x) is not int or not 1 <= x <= 16 for x in (
            self.units, self.development_per_family, self.qualification_per_family
        )):
            raise ValueError("design counts must be positive integers <=16")
        if type(self.public_seed) is not int or not 0 <= self.public_seed <= 2**32 - 1:
            raise ValueError("public seed must be a uint32")
        if not self.model_id.strip() or len(self.model_id) > 80:
            raise ValueError("model id must be explicit and bounded")
        if self.logical_calls > 480:
            raise ValueError("offline pilot logical call cap is 480")

    @property
    def heldout_triplets(self) -> int:
        return self.units * len(FAMILIES) * self.qualification_per_family

    @property
    def logical_calls(self) -> int:
        return self.units * len(FAMILIES) * (
            self.development_per_family + 3 * self.qualification_per_family
        )

    def freeze(self) -> PublicCohort:
        units: list[CohortUnit] = []
        for u in range(self.units):
            tasks_by_family: list[FamilyTasks] = []
            for family in FAMILIES:
                context = f"cohort-{u:03d}-{family}"
                rows: list[tuple[SchemaTask, ...]] = []
                for stage, count in (
                    ("dev", self.development_per_family),
                    ("holdout", self.qualification_per_family),
                ):
                    tasks: list[SchemaTask] = []
                    for i in range(count):
                        serial = (u * 1000 + (0 if family == "arithmetic" else 500)
                                  + (0 if stage == "dev" else 100) + i
                                  + self.public_seed % 31)
                        common = {
                            "task_id": f"{stage}-{u:03d}-{family}-{i:02d}",
                            "context": context,
                            "family": family,
                        }
                        if family == "arithmetic":
                            tasks.append(SchemaTask(
                                **common, value=100 + 17 * serial,
                                offset=1 + serial % 7,
                                factor=2 + (serial // 3) % 7,
                            ))
                        else:
                            tasks.append(SchemaTask(
                                **common, text=f"abq{serial}ab",
                            ))
                    rows.append(tuple(tasks))
                tasks_by_family.append(FamilyTasks(family, context, rows[0], rows[1]))
            units.append(CohortUnit(f"unit-{u:03d}", tuple(tasks_by_family)))
        return PublicCohort(self, tuple(units))


@dataclass(frozen=True, slots=True)
class FamilyTasks:
    family: Family
    context: str
    development: tuple[SchemaTask, ...]
    qualification: tuple[SchemaTask, ...]


@dataclass(frozen=True, slots=True)
class CohortUnit:
    unit_id: str
    families: tuple[FamilyTasks, ...]


@dataclass(frozen=True, slots=True)
class PublicCohort:
    design: V2Design
    units: tuple[CohortUnit, ...]

    def __post_init__(self) -> None:
        if len(self.units) != self.design.units or len({
            unit.unit_id for unit in self.units
        }) != len(self.units):
            raise ValueError("incorrect independent learner unit count")
        ids: set[str] = set()
        payloads: set[tuple[object, ...]] = set()
        for unit in self.units:
            if tuple(f.family for f in unit.families) != FAMILIES:
                raise ValueError("must include each different schema")
            for group in unit.families:
                if (len(group.development) != self.design.development_per_family
                        or len(group.qualification) != self.design.qualification_per_family):
                    raise ValueError("split size violated")
                for task in (*group.development, *group.qualification):
                    if task.context != group.context or task.family != group.family:
                        raise ValueError("schema or context collision")
                    payload = task.public_tuple()[1:]
                    if task.task_id in ids or payload in payloads:
                        raise ValueError("public cohort ID/payload reused")
                    ids.add(task.task_id)
                    payloads.add(payload)

    @property
    def digest(self) -> str:
        return _digest({
            "schema": "c3r-g1-multischema-public-lock-v0.1",
            "design": {
                "units": self.design.units,
                "development_per_family": self.design.development_per_family,
                "qualification_per_family": self.design.qualification_per_family,
                "public_seed": self.design.public_seed,
                "model_id": self.design.model_id,
            },
            "units": [
                [unit.unit_id, [
                    [group.family, group.context,
                     [task.public_tuple() for task in group.development],
                     [task.public_tuple() for task in group.qualification]]
                    for group in unit.families
                ]] for unit in self.units
            ],
        })


class LocalFixtureEvaluator:
    """Private-target local test double. NOT an isolated or attested grader."""

    def __init__(self, cohort: PublicCohort, *, private_seed: int) -> None:
        if type(private_seed) is not int or not 0 <= private_seed <= 2**32 - 1:
            raise ValueError("private fixture seed must be a uint32")
        self._targets: dict[tuple[str, str], str] = {}
        self._allowlisted_tasks: set[tuple[str, tuple[object, ...]]] = set()
        for index, unit in enumerate(cohort.units):
            for family_index, group in enumerate(unit.families):
                self._targets[unit.unit_id, group.context] = (
                    "A" if (private_seed + index + family_index) % 2 == 0 else "B"
                )
                for task in (*group.development, *group.qualification):
                    self._allowlisted_tasks.add((unit.unit_id, task.public_tuple()))

    def grade(self, unit_id: str, task: SchemaTask, choice: str) -> bool:
        if (unit_id, task.public_tuple()) not in self._allowlisted_tasks:
            raise ValueError("evaluator only accepts tasks from its locked cohort")
        # Grade executable outcomes, not just choice-string equality.
        target = self._targets[unit_id, task.context]
        return apply_choice(task, choice) == apply_choice(task, target)


@dataclass(frozen=True, slots=True)
class Attempt:
    unit_id: str
    arm: Arm
    stage: Stage
    task_id: str
    family: Family
    context: str
    status: str
    choice: str | None
    success: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "unit_id": self.unit_id, "arm": self.arm, "stage": self.stage,
            "task_id": self.task_id, "family": self.family, "context": self.context,
            "status": self.status, "choice": self.choice, "success": self.success,
        }


@dataclass(frozen=True, slots=True)
class V2Report:
    cohort_digest: str
    design: V2Design
    attempts: tuple[Attempt, ...]
    exposure: tuple[tuple[str, Family, int, int], ...]
    fixture_ports_only: bool = False

    def to_dict(self) -> dict[str, object]:
        rows = [r.to_dict() for r in self.attempts]
        qualification = [r for r in self.attempts if r.stage == "qualification"]
        counts: dict[str, dict[str, int]] = {
            arm: {
                "prescribed": sum(r.arm == arm for r in qualification),
                "accepted": sum(r.arm == arm and r.status == "accepted"
                                for r in qualification),
                "itt_successes": sum(r.arm == arm and r.success for r in qualification),
            }
            for arm in ARMS
        }
        by_unit: list[dict[str, object]] = []
        for unit in self.design.freeze().units:
            per_arm = {
                arm: sum(r.success for r in qualification
                         if r.unit_id == unit.unit_id and r.arm == arm)
                for arm in ARMS
            }
            denominator = len(FAMILIES) * self.design.qualification_per_family
            by_unit.append({
                "unit_id": unit.unit_id,
                "itt_learned_minus_fresh": (
                    per_arm["learned"] - per_arm["fresh"]
                ) / denominator,
                "itt_learned_minus_placebo": (
                    per_arm["learned"] - per_arm["placebo"]
                ) / denominator,
                "successes": per_arm,
            })
        by_family = {
            family: {
                arm: {
                    "prescribed": sum(r.family == family and r.arm == arm
                                      for r in qualification),
                    "accepted": sum(r.family == family and r.arm == arm
                                    and r.status == "accepted" for r in qualification),
                    "itt_successes": sum(r.family == family and r.arm == arm
                                         and r.success for r in qualification),
                }
                for arm in ARMS
            }
            for family in FAMILIES
        }
        matched: dict[tuple[str, str], list[Attempt]] = {}
        for row in qualification:
            matched.setdefault((row.unit_id, row.task_id), []).append(row)
        triplets = sum(
            len(group) == 3 and {item.arm for item in group} == set(ARMS)
            and all(item.status == "accepted" for item in group)
            for group in matched.values()
        )
        yield_actions = sum(r.status == "accepted" for r in qualification)
        dev = [r for r in self.attempts if r.stage == "development"]
        total = self.design.heldout_triplets
        if len(self.attempts) != self.design.logical_calls or len(matched) != total:
            raise ValueError("incomplete prescribed pilot ledger")
        output = {
            "schema": "c3r-g1-multischema-pilot-v0.1",
            "status": (
                "offline_fixture_no_model_learning_claim"
                if self.fixture_ports_only else "unverified_injected_ports_no_inference"
            ),
            "public_cohort_digest": self.cohort_digest,
            "families": list(FAMILIES),
            "independent_learner_units": self.design.units,
            "prescribed_logical_calls": self.design.logical_calls,
            "source_dev_prescribed": len(dev),
            "source_dev_accepted": sum(r.status == "accepted" for r in dev),
            "heldout_triplets_prescribed": total,
            "heldout_triplets_complete": triplets,
            "triplet_yield": triplets / total,
            "qualification_actions_accepted": yield_actions,
            "qualification_action_yield": yield_actions / (3 * total),
            "by_arm": counts,
            "by_family": by_family,
            "unit_effects": by_unit,
            "mean_unit_itt_learned_minus_fresh": sum(
                r["itt_learned_minus_fresh"] for r in by_unit
            ) / len(by_unit),
            "mean_unit_itt_learned_minus_placebo": sum(
                r["itt_learned_minus_placebo"] for r in by_unit
            ) / len(by_unit),
            "source_exposure": [
                {"unit_id": u, "family": f, "learned": n, "placebo": p}
                for u, f, n, p in self.exposure
            ],
            "trial_records": rows,
            "trial_digest": _digest(rows),
            "technical_yield_gate": {
                "min_action_yield": 0.95,
                "min_full_triplet_yield": 0.90,
                "all_development_actions_parseable": True,
                "passed_in_fixture": (
                    yield_actions / (3 * total) >= 0.95
                    and triplets / total >= 0.90
                    and all(row.status == "accepted" for row in dev)
                ),
                "authorizes_live_campaign": False,
            },
            "provider_sends_verified": False,
            "fixture_port_execution_only": self.fixture_ports_only,
            "independent_evaluator_attested": False,
            "scientific_acceptance": False,
            "warnings": [
                "two different public task schemas, but a local deterministic evaluator",
                "public lock excludes private target rule; no external commitment",
                "arm-specific Python ports do not certify real provider session independence",
                "sham histories are generated independently of graded source choices; "
                "match accepted-record counts, not exact token cost",
                "observed units and task counts do not establish power or replication",
                "all invalid outputs remain ITT failures; no G1/G2/G3/G4 promotion",
            ],
        }
        return output

    def canonical_bytes(self) -> bytes:
        return json.dumps(self.to_dict(), sort_keys=True,
                          separators=(",", ":")).encode("utf-8")


PortFactory = Callable[[str, Arm, Stage], SchemaPort]


class V2Runner:
    def __init__(self, cohort: PublicCohort, evaluator: LocalFixtureEvaluator) -> None:
        self.cohort = cohort
        self._evaluator = evaluator

    def _grade(
        self, unit_id: str, arm: Arm, stage: Stage, task: SchemaTask,
        feedback: tuple[Feedback, ...], port: SchemaPort,
    ) -> Attempt:
        req = SchemaRequest(unit_id, arm, stage, task, feedback)
        try:
            completion = port.complete(req)
        except Exception:
            status, choice = "adapter_exception", None
        else:
            if not isinstance(completion, ModelChoiceCompletion):
                status, choice = "invalid_completion", None
            elif completion.model_id != self.cohort.design.model_id:
                status, choice = "wrong_model", None
            elif completion.output not in ("A", "B"):
                status, choice = "invalid_format", None
            else:
                status, choice = "accepted", completion.output
        success = bool(
            status == "accepted" and choice is not None
            and self._evaluator.grade(unit_id, task, choice)
        )
        return Attempt(unit_id, arm, stage, task.task_id,
                       task.family, task.context, status, choice, success)

    def run(self, *, port_factory: PortFactory,
            fixture_ports_only: bool = False) -> V2Report:
        all_attempts: list[Attempt] = []
        exposure: list[tuple[str, Family, int, int]] = []
        used_ports: list[SchemaPort] = []
        for unit in self.cohort.units:
            development_port = port_factory(unit.unit_id, "learned", "development")
            qualifying = {
                arm: port_factory(unit.unit_id, arm, "qualification") for arm in ARMS
            }
            every_port = (development_port, *qualifying.values())
            if (any(not callable(getattr(p, "complete", None)) for p in every_port)
                    or len({id(p) for p in every_port}) != 4
                    or any(p is existing for p in every_port for existing in used_ports)):
                raise ValueError("ports must be distinct by arm, stage and learner unit")
            used_ports.extend(every_port)
            source: dict[str, tuple[tuple[Feedback, ...], tuple[Feedback, ...]]] = {}
            for group in unit.families:
                learned: list[Feedback] = []
                for task in group.development:
                    attempt = self._grade(
                        unit.unit_id, "learned", "development", task,
                        tuple(learned), development_port,
                    )
                    all_attempts.append(attempt)
                    if attempt.status == "accepted":
                        assert attempt.choice in ("A", "B")
                        learned.append(Feedback(
                            task.task_id, task.context, attempt.choice, attempt.success
                        ))
                # Placebo has independently constructed plan AND fake labels.
                # Neither real graded success nor the learned policy action
                # trajectory is used. Exposure count is held equal.
                sham: list[Feedback] = []
                for feedback in learned:
                    digest = _digest((
                        "placebo-independent-of-source-outcome-v2",
                        self.cohort.design.public_seed,
                        unit.unit_id, feedback.task_id,
                    ))
                    sham.append(Feedback(
                        feedback.task_id, feedback.context,
                        "A" if int(digest[:8], 16) % 2 == 0 else "B",
                        bool(int(digest[8:16], 16) % 2),
                    ))
                source[group.context] = (tuple(learned), tuple(sham))
                exposure.append((unit.unit_id, group.family,
                                 len(learned), len(sham)))
            for group in unit.families:
                learned, sham = source[group.context]
                for i, task in enumerate(group.qualification):
                    rotation = (i + int(unit.unit_id[-3:])) % len(ARMS)
                    for arm in (*ARMS[rotation:], *ARMS[:rotation]):
                        feedback = (
                            learned if arm == "learned"
                            else sham if arm == "placebo" else ()
                        )
                        all_attempts.append(self._grade(
                            unit.unit_id, arm, "qualification", task,
                            feedback, qualifying[arm],
                        ))
        if len(all_attempts) != self.cohort.design.logical_calls:
            raise RuntimeError("prescribed tasks were silently dropped")
        return V2Report(self.cohort.digest, self.cohort.design,
                        tuple(all_attempts), tuple(exposure), fixture_ports_only)


@dataclass(slots=True)
class _ConstantFixturePort:
    model_id: str

    def complete(self, request: SchemaRequest) -> ModelChoiceCompletion:
        return ModelChoiceCompletion(output="A", model_id=self.model_id)


def run_offline_multischema_fixture(design: V2Design | None = None) -> V2Report:
    """Null fixture. It never constructs or calls the Z.AI client."""
    spec = design or V2Design()
    cohort = spec.freeze()
    return V2Runner(
        cohort, LocalFixtureEvaluator(cohort, private_seed=1701)
    ).run(port_factory=lambda _uid, _arm, _stage: _ConstantFixturePort(spec.model_id),
          fixture_ports_only=True)


def main() -> int:
    print(run_offline_multischema_fixture().canonical_bytes().decode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
