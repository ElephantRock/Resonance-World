"""Descriptive-only, zero-network auditing of a prescribed 40-attempt G1 cohort.

No target assignment, grade key, provider receipt or credentials enter this module.
Input correctness is *reported*, not independently verified. It never grants
scientific acceptance, provider execution status or permission to send.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from resonance_world.c3r_g1_crossed_plan import ARMS, FAMILIES, CrossedPlan, make_plan

Status = Literal["accepted", "invalid_format", "provider_error", "not_sent"]


@dataclass(frozen=True, slots=True)
class AttemptOutcome:
    unit_id: str
    task_id: str
    stage: str
    arm: str
    status: Status
    action: str | None = None
    correct: bool | None = None

    @property
    def key(self) -> tuple[str, str, str, str]:
        return (self.unit_id, self.task_id, self.stage, self.arm)


def _score(rows: list[AttemptOutcome]) -> dict[str, object]:
    """Conservative numerical bounds if unresolved attempts could be correct."""
    successes = sum(r.correct is True for r in rows)
    unknown = sum(r.status != "accepted" for r in rows)
    total = len(rows)
    if not total:
        raise ValueError("empty prespecified scoring set")
    return {
        "prescribed": total,
        "accepted": total - unknown,
        "reported_correct": successes,
        "reported_incorrect": total - unknown - successes,
        "unresolved": unknown,
        "rate_lower_if_unresolved_incorrect": successes / total,
        "rate_upper_if_unresolved_correct": (successes + unknown) / total,
    }


def _contrast(learned: dict[str, object], comparator: dict[str, object]) -> dict[str, object]:
    """Bounds on aggregate learned-minus-comparator, including missingness."""
    n = learned["prescribed"]
    if n != comparator["prescribed"] or not isinstance(n, int) or n < 1:
        raise ValueError("invalid paired denominators")
    l_success = learned["reported_correct"]
    c_success = comparator["reported_correct"]
    return {
        "unit": "learner_context_one_holdout_task",
        "paired_prescribed_units": n,
        "diff_lower": (l_success - c_success - comparator["unresolved"]) / n,
        "diff_upper": (l_success + learned["unresolved"] - c_success) / n,
        "requires_missingness_assumptions_for_point_estimate": (
            learned["unresolved"] != 0 or comparator["unresolved"] != 0
        ),
    }


def audit_outcomes(
    plan: CrossedPlan, *, outcomes: tuple[AttemptOutcome, ...],
) -> dict[str, object]:
    """Validate complete logical denominators; produce no individual labels.

    Exactly one outcome is required for every prescribed attempt. Unsent and
    errored attempts remain explicitly in the denominator, not silently
    dropped. All provider actions and correctness flags remain unattested.
    """
    plan.audit()
    if plan.public_digest != make_plan().public_digest:
        raise ValueError("unfrozen public plan")
    expected = [
        (s.unit_id, s.task_id, s.stage, s.arm) for s in plan.schedule
    ]
    observed = [row.key for row in outcomes]
    if (len(observed) != 40 or len(set(observed)) != 40
            or set(observed) != set(expected)):
        raise ValueError("exactly 40 unique prescribed attempt records are required")
    for row in outcomes:
        if row.status not in ("accepted", "invalid_format", "provider_error", "not_sent"):
            raise ValueError("invalid attempt status")
        if row.status == "accepted":
            if row.action not in ("A", "B") or type(row.correct) is not bool:
                raise ValueError("accepted attempts need exact A/B and binary score")
        elif row.action is not None or row.correct is not None:
            raise ValueError("unresolved attempts must not assert an action or score")
    by_key = {row.key: row for row in outcomes}
    cell_results: dict[str, dict[str, AttemptOutcome]] = {}
    family_by_unit = {cell.unit_id: cell.family for cell in plan.cells}
    for cell in plan.cells:
        holdout = cell.qualification[0]
        cell_results[cell.unit_id] = {
            arm: by_key[(cell.unit_id, holdout.task_id, "qualification", arm)]
            for arm in ARMS
        }
    accepted_source_units = 0
    for cell in plan.cells:
        dev = [by_key[(cell.unit_id, task.task_id, "development", "learned")]
               for task in cell.development]
        if all(row.status == "accepted" for row in dev):
            accepted_source_units += 1
    complete_triplets = sum(all(r.status == "accepted" for r in rows.values())
                            for rows in cell_results.values())
    family_summaries: dict[str, object] = {}
    for family in FAMILIES:
        family_units = [u for u in cell_results if family_by_unit[u] == family]
        arm_scores = {
            arm: _score([cell_results[u][arm] for u in family_units])
            for arm in ARMS
        }
        family_summaries[family] = {
            "prescribed_units": len(family_units),
            "arms": arm_scores,
            "learned_minus_fresh": _contrast(arm_scores["learned"], arm_scores["fresh"]),
            "learned_minus_neutral": _contrast(arm_scores["learned"], arm_scores["neutral"]),
        }
    overall = {
        arm: _score([cell_results[u][arm] for u in cell_results]) for arm in ARMS
    }
    status_counts = {
        status: sum(row.status == status for row in outcomes)
        for status in ("accepted", "invalid_format", "provider_error", "not_sent")
    }
    return {
        "schema": "c3r-g1-crossed-descriptive-audit-v0.1",
        "public_plan_digest": plan.public_digest,
        "prescribed_logical_attempts": 40,
        "development_attempts_prescribed": 16,
        "qualification_attempts_prescribed": 24,
        "logical_status_counts": status_counts,
        "source_units_with_two_accepted_development_actions": accepted_source_units,
        "complete_accepted_qualification_triplets": complete_triplets,
        "family": family_summaries,
        "overall": {
            "arms": overall,
            "learned_minus_fresh": _contrast(overall["learned"], overall["fresh"]),
            "learned_minus_neutral": _contrast(overall["learned"], overall["neutral"]),
        },
        "target_cell_stratification_available": False,
        "input_correctness_independently_attested": False,
        "actual_send_count_reconciled": False,
        "provider_execution_verified": False,
        "session_isolation_verified": False,
        "scientific_acceptance": False,
        "verdict": "unattested_descriptive_arithmetic_only",
    }
