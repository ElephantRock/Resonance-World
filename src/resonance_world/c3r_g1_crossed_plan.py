"""G1 crossed A/B x arithmetic/text cohort: OFFLINE DESIGN ONLY.

This module does not call providers or grade model outputs. A private keyed
assignment is provided for a separately operated evaluator to adopt only
through an independently frozen, attested protocol. Nothing here authorizes
physical sends or grants scientific acceptance.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from typing import Literal

Family = Literal["arithmetic", "text"]
Arm = Literal["learned", "fresh", "neutral"]
Stage = Literal["development", "qualification"]
FAMILIES: tuple[Family, ...] = ("arithmetic", "text")
ARMS: tuple[Arm, ...] = ("learned", "fresh", "neutral")


def _hash(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True, slots=True)
class PublicTask:
    task_id: str
    context_id: str
    family: Family
    stage: Stage
    operands: tuple[int, int, int] | str

    def record(self) -> dict[str, object]:
        return {
            "task_id": self.task_id,
            "context_id": self.context_id,
            "family": self.family,
            "stage": self.stage,
            "operands": self.operands,
        }

    def action_value(self, choice: str) -> int | str:
        """Public executable algebra; this method cannot determine the truth target."""
        if choice not in ("A", "B"):
            raise ValueError("only exact A/B actions are executable")
        if self.family == "arithmetic":
            if not isinstance(self.operands, tuple):
                raise ValueError("invalid arithmetic operands")
            value, offset, factor = self.operands
            return ((value + offset) * factor if choice == "A"
                    else value * factor + offset)
        if not isinstance(self.operands, str):
            raise ValueError("invalid text operands")
        return (self.operands.replace("ab", "z").upper() if choice == "A"
                else self.operands.upper().replace("ab", "z"))


@dataclass(frozen=True, slots=True)
class PublicCell:
    unit_id: str
    family: Family
    context_id: str
    development: tuple[PublicTask, ...]
    qualification: tuple[PublicTask, ...]

    def record(self) -> dict[str, object]:
        return {
            "unit_id": self.unit_id,
            "family": self.family,
            "context_id": self.context_id,
            "development": [task.record() for task in self.development],
            "qualification": [task.record() for task in self.qualification],
        }


@dataclass(frozen=True, slots=True)
class AttemptSlot:
    unit_id: str
    task_id: str
    stage: Stage
    arm: Arm

    def record(self) -> dict[str, str]:
        return {
            "unit_id": self.unit_id, "task_id": self.task_id,
            "stage": self.stage, "arm": self.arm,
        }


@dataclass(frozen=True, slots=True)
class CrossedPlan:
    """Eight *independent proposed* context-level units, not a powered sample."""

    cells: tuple[PublicCell, ...]
    schedule: tuple[AttemptSlot, ...]
    development_per_cell: int
    qualification_per_cell: int

    def public_lock(self) -> dict[str, object]:
        return {
            "schema": "c3r-g1-crossed-offline-plan-v0.1",
            "evidence_class": "construction_only_no_provider_or_learning_evidence",
            "cells": [cell.record() for cell in self.cells],
            "schedule": [slot.record() for slot in self.schedule],
            "development_per_cell": self.development_per_cell,
            "qualification_per_cell": self.qualification_per_cell,
            "prescribed_logical_attempts": len(self.schedule),
            "planned_triplets": len(self.cells) * self.qualification_per_cell,
            "physical_send_authorized": False,
            "provider_token_parity_attested": False,
            "independent_evaluator_attested": False,
            "power_contract_frozen": False,
            "scientific_acceptance": False,
        }

    @property
    def public_digest(self) -> str:
        return _hash(self.public_lock())

    def audit(self) -> dict[str, object]:
        """Fail closed on altered denominators, duplication, order or split overlap."""
        if len(self.cells) != 8 or self.development_per_cell != 2 \
                or self.qualification_per_cell != 1:
            raise ValueError("crossed pilot must have 8 cells with 2+1 tasks")
        if {family: sum(c.family == family for c in self.cells)
                for family in FAMILIES} != {"arithmetic": 4, "text": 4}:
            raise ValueError("four disjoint contexts required per family")
        if len({c.unit_id for c in self.cells}) != len(self.cells) or len({
                c.context_id for c in self.cells}) != len(self.cells):
            raise ValueError("unit and context identities must be disjoint")
        ids: set[str] = set()
        inputs: set[tuple[object, ...]] = set()
        expected: set[tuple[str, str, Stage, Arm]] = set()
        for cell in self.cells:
            if (len(cell.development) != 2 or len(cell.qualification) != 1):
                raise ValueError("incorrect per-cell split")
            for task in (*cell.development, *cell.qualification):
                if (task.family != cell.family or task.context_id != cell.context_id
                        or (task in cell.development) != (task.stage == "development")):
                    raise ValueError("task context/stage mismatch")
                key = (cell.family, task.operands)
                if task.task_id in ids or key in inputs:
                    raise ValueError("reused task id or task operands")
                ids.add(task.task_id)
                inputs.add(key)
                if task.action_value("A") == task.action_value("B"):
                    raise ValueError("non-discriminating input")
                if task.stage == "development":
                    expected.add((cell.unit_id, task.task_id, task.stage, "learned"))
                else:
                    for arm in ARMS:
                        expected.add((cell.unit_id, task.task_id, task.stage, arm))
        rows = [(s.unit_id, s.task_id, s.stage, s.arm) for s in self.schedule]
        if len(rows) != 40 or len(set(rows)) != 40 or set(rows) != expected:
            raise ValueError("schedule must include every prescribed attempt exactly once")
        if any(slot.stage != "development" for slot in self.schedule[:16]) or any(
                slot.stage != "qualification" for slot in self.schedule[16:]):
            raise ValueError("all graded source actions must precede qualifications")
        # One independently reset model session is required per cell per phase/arm.
        # This is a plan-level requirement, NOT a certification of session isolation.
        return {
            "schema": "c3r-g1-crossed-plan-audit-v0.1",
            "verdict": "structurally_valid_unattested",
            "public_digest": self.public_digest,
            "distinct_contexts": len(self.cells),
            "development_attempts": 16,
            "qualification_attempts": 24,
            "heldout_triplets": 8,
            "physical_sends": 0,
            "independent_session_isolation_attested": False,
            "scientific_acceptance": False,
        }


def make_plan() -> CrossedPlan:
    """Public deterministic operands, opaque identities; no target labels."""
    cells: list[PublicCell] = []
    for family in FAMILIES:
        for index in range(4):
            unit_id = f"g1x-{family[:3]}-{index:02d}"
            context_id = "ctx-" + _hash(["g1x", family, index, 20261022])[:18]
            stages: list[tuple[PublicTask, ...]] = []
            for stage, count in (("development", 2), ("qualification", 1)):
                tasks: list[PublicTask] = []
                for j in range(count):
                    serial = 100 * index + 10 * (stage == "qualification") + j + (
                        2000 if family == "text" else 0
                    )
                    operands: tuple[int, int, int] | str
                    if family == "arithmetic":
                        operands = (19 + 11 * serial, 2 + serial % 5, 3 + serial % 7)
                    else:
                        operands = f"abflux{serial}ab"
                    tasks.append(PublicTask(
                        f"{stage[:3]}-{unit_id}-{j}", context_id,
                        family, stage, operands,
                    ))
                stages.append(tuple(tasks))
            cells.append(PublicCell(unit_id, family, context_id, stages[0], stages[1]))
    schedule: list[AttemptSlot] = []
    for cell in cells:
        schedule.extend(AttemptSlot(cell.unit_id, task.task_id,
                                    "development", "learned")
                        for task in cell.development)
    for cell_index, cell in enumerate(cells):
        for task in cell.qualification:
            rotation = cell_index % len(ARMS)
            for arm in (*ARMS[rotation:], *ARMS[:rotation]):
                schedule.append(AttemptSlot(cell.unit_id, task.task_id,
                                            "qualification", arm))
    plan = CrossedPlan(tuple(cells), tuple(schedule), 2, 1)
    plan.audit()
    return plan


def evaluator_private_assignment(
    plan: CrossedPlan, *, secret: bytes,
) -> dict[str, Literal["A", "B"]]:
    """Evaluator-side *local test* balance, not an attested independent oracle.

    Sort each family by HMAC with an evaluator-private 256-bit secret. Keep
    two contexts assigned to each target per family without putting the map
    in public lock, prompt or runner. Production needs separate custody.
    """
    plan.audit()
    if type(secret) is not bytes or len(secret) != 32:
        raise ValueError("private assignment requires exactly 32 secret bytes")
    mapping: dict[str, Literal["A", "B"]] = {}
    for family in FAMILIES:
        relevant = [c for c in plan.cells if c.family == family]
        ranked = sorted(relevant, key=lambda c: hmac.new(
            secret, ("g1x-v0.1:" + c.context_id).encode(), hashlib.sha256,
        ).digest())
        for i, cell in enumerate(ranked):
            mapping[cell.context_id] = "A" if i < 2 else "B"
    return mapping


def local_private_balance_audit(
    plan: CrossedPlan, assignment: dict[str, str],
) -> dict[str, object]:
    """Keep per-context labels in evaluator custody; expose only aggregate quotas."""
    if set(assignment) != {c.context_id for c in plan.cells}:
        raise ValueError("private assignment context set mismatch")
    quotas = {
        family: {target: sum(
            assignment[c.context_id] == target for c in plan.cells
            if c.family == family
        ) for target in ("A", "B")}
        for family in FAMILIES
    }
    if any(assignment[c.context_id] not in ("A", "B") for c in plan.cells):
        raise ValueError("invalid private target label")
    if any(quotas[family] != {"A": 2, "B": 2} for family in FAMILIES):
        raise ValueError("the two families must each contain 2 A and 2 B")
    return {
        "verdict": "local_private_balance_only_unattested",
        "family_target_quota": quotas,
        "private_keys_or_cell_labels_exported": False,
        "independent_evaluator_attested": False,
        "scientific_acceptance": False,
    }


def main() -> int:
    plan = make_plan()
    report = plan.audit()
    print(json.dumps(report, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
