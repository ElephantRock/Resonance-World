"""Read-only recomputation of C3R G1 multischema fixture ledgers.

Structural consistency is NOT independent evaluator or provider attestation.
This module does not import clients, read secrets, mutate state or send network
requests. A local fixture grader is optional and not a scientific grader.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from .c3r_g1_multischema import (
    ARMS, FAMILIES, STATUSES, LocalFixtureEvaluator, PublicCohort,
)

RECORD_FIELDS = frozenset({
    "unit_id", "arm", "stage", "task_id", "family",
    "context", "status", "choice", "success",
})
FORBIDDEN = frozenset({
    "api_key", "authorization", "secret", "prompt", "raw_response",
    "raw_content", "reasoning_content", "answer_key", "private_seed",
})


def _sha(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _forbidden(value: object) -> bool:
    if isinstance(value, dict):
        return any(key in FORBIDDEN or _forbidden(child)
                   for key, child in value.items())
    if isinstance(value, list):
        return any(_forbidden(child) for child in value)
    return False


@dataclass(frozen=True, slots=True)
class MultischemaAudit:
    verdict: str
    errors: tuple[str, ...]
    inspected_attempts: int

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": "c3r-g1-multischema-audit-v0.1",
            "verdict": self.verdict,
            "errors": list(self.errors),
            "inspected_attempts": self.inspected_attempts,
            "independent_grader_attested": False,
            "provider_activity_verified": False,
            "scientific_acceptance": False,
        }


def audit_multischema(
    report: object, cohort: PublicCohort,
    *, fixture_evaluator: LocalFixtureEvaluator | None = None,
) -> MultischemaAudit:
    errors: list[str] = []
    if not isinstance(report, dict):
        return MultischemaAudit("invalid_input", ("not_an_object",), 0)
    if _forbidden(report):
        errors.append("raw_or_private_field_present")
    if report.get("schema") != "c3r-g1-multischema-pilot-v0.1":
        errors.append("schema_mismatch")
    if report.get("public_cohort_digest") != cohort.digest:
        errors.append("public_cohort_lock_mismatch")
    for name in ("scientific_acceptance", "independent_evaluator_attested",
                 "provider_sends_verified"):
        if report.get(name) is not False:
            errors.append(f"{name}_must_be_false")
    is_fixture = report.get("fixture_port_execution_only")
    if type(is_fixture) is not bool or report.get("status") != (
        "offline_fixture_no_model_learning_claim"
        if is_fixture else "unverified_injected_ports_no_inference"
    ):
        errors.append("unverified_port_status")

    expected = {}
    for unit in cohort.units:
        for family in unit.families:
            for task in family.development:
                expected[unit.unit_id, "learned", "development", task.task_id] = task
            for task in family.qualification:
                for arm in ARMS:
                    expected[unit.unit_id, arm, "qualification", task.task_id] = task

    rows = report.get("trial_records")
    if not isinstance(rows, list) or len(rows) > 480:
        return MultischemaAudit(
            "rejected_inconsistent", (*errors, "missing_or_overlong_trial_records"), 0
        )
    if len(rows) != len(expected):
        errors.append("attempt_denominator_mismatch")
    if report.get("prescribed_logical_calls") != len(expected):
        errors.append("reported_logical_call_count_mismatch")
    if report.get("trial_digest") != _sha(rows):
        errors.append("attempt_digest_mismatch")

    observed: dict[tuple[str, str, str, str], dict] = {}
    for record in rows:
        if not isinstance(record, dict) or set(record) != RECORD_FIELDS:
            errors.append("invalid_record_schema")
            continue
        if any(type(record[field]) is not str for field in (
            "unit_id", "arm", "stage", "task_id", "family", "context", "status"
        )):
            errors.append("invalid_record_types")
            continue
        key = (record["unit_id"], record["arm"],
               record["stage"], record["task_id"])
        if key in observed:
            errors.append("duplicate_observed_attempt")
            continue
        if key not in expected:
            errors.append("unexpected_task_or_treatment")
            continue
        task = expected[key]
        if record["family"] != task.family or record["context"] != task.context:
            errors.append("record_task_mismatch")
        if record["status"] not in STATUSES or type(record["success"]) is not bool:
            errors.append("invalid_record_outcome")
            continue
        accepted = record["status"] == "accepted"
        if accepted and record["choice"] not in ("A", "B"):
            errors.append("accepted_action_missing")
        if not accepted and (record["choice"] is not None or record["success"]):
            errors.append("failed_attempt_misclassified")
        if (fixture_evaluator is not None and accepted
                and record["choice"] in ("A", "B")
                and record["success"] != fixture_evaluator.grade(
                    record["unit_id"], task, record["choice"]
                )):
            errors.append("local_fixture_grade_mismatch")
        observed[key] = record

    if set(observed) != set(expected):
        errors.append("missing_prescribed_attempts")
    # Do not interpret aggregates built from an invalid attempt list.
    if errors:
        return MultischemaAudit(
            "rejected_inconsistent", tuple(dict.fromkeys(errors)), len(observed)
        )

    development = [r for r in observed.values() if r["stage"] == "development"]
    qualification = [r for r in observed.values() if r["stage"] == "qualification"]
    if report.get("source_dev_prescribed") != len(development):
        errors.append("development_denominator_mismatch")
    if report.get("source_dev_accepted") != sum(
        r["status"] == "accepted" for r in development
    ):
        errors.append("development_acceptance_mismatch")

    triplets = sum(
        all(observed[uid, arm, "qualification", task.task_id]["status"] == "accepted"
            for arm in ARMS)
        for unit in cohort.units for family in unit.families
        for task in family.qualification for uid in (unit.unit_id,)
    )
    total = cohort.design.heldout_triplets
    accepted = sum(r["status"] == "accepted" for r in qualification)
    metrics = {
        "heldout_triplets_prescribed": total,
        "heldout_triplets_complete": triplets,
        "triplet_yield": triplets / total,
        "qualification_actions_accepted": accepted,
        "qualification_action_yield": accepted / (3 * total),
    }
    if any(report.get(k) != v for k, v in metrics.items()):
        errors.append("qualification_aggregate_mismatch")

    per_arm = {
        arm: {
            "prescribed": sum(r["arm"] == arm for r in qualification),
            "accepted": sum(r["arm"] == arm and r["status"] == "accepted"
                            for r in qualification),
            "itt_successes": sum(r["arm"] == arm and r["success"]
                                 for r in qualification),
        }
        for arm in ARMS
    }
    if report.get("by_arm") != per_arm:
        errors.append("arm_itt_mismatch")
    per_family = {
        family: {
            arm: {
                "prescribed": sum(
                    r["family"] == family and r["arm"] == arm for r in qualification
                ),
                "accepted": sum(
                    r["family"] == family and r["arm"] == arm
                    and r["status"] == "accepted" for r in qualification
                ),
                "itt_successes": sum(
                    r["family"] == family and r["arm"] == arm and r["success"]
                    for r in qualification
                ),
            }
            for arm in ARMS
        }
        for family in FAMILIES
    }
    if report.get("by_family") != per_family:
        errors.append("family_itt_mismatch")

    unit_effects: list[dict[str, object]] = []
    for unit in cohort.units:
        score = {
            arm: sum(r["success"] for r in qualification
                     if r["unit_id"] == unit.unit_id and r["arm"] == arm)
            for arm in ARMS
        }
        n = len(FAMILIES) * cohort.design.qualification_per_family
        unit_effects.append({
            "unit_id": unit.unit_id,
            "itt_learned_minus_fresh": (score["learned"] - score["fresh"]) / n,
            "itt_learned_minus_placebo": (score["learned"] - score["placebo"]) / n,
            "successes": score,
        })
    if report.get("unit_effects") != unit_effects:
        errors.append("unit_itt_mismatch")
    if report.get("mean_unit_itt_learned_minus_fresh") != sum(
        row["itt_learned_minus_fresh"] for row in unit_effects
    ) / len(unit_effects):
        errors.append("cluster_mean_fresh_mismatch")
    if report.get("mean_unit_itt_learned_minus_placebo") != sum(
        row["itt_learned_minus_placebo"] for row in unit_effects
    ) / len(unit_effects):
        errors.append("cluster_mean_placebo_mismatch")

    counted_source = {
        (unit.unit_id, family.family): sum(
            observed[unit.unit_id, "learned", "development", task.task_id]["status"]
            == "accepted"
            for task in family.development
        )
        for unit in cohort.units for family in unit.families
    }
    exposure = report.get("source_exposure")
    if (not isinstance(exposure, list)
            or len(exposure) != len(counted_source)
            or any(
                not isinstance(entry, dict)
                or type(entry.get("unit_id")) is not str
                or type(entry.get("family")) is not str
                or type(entry.get("learned")) is not int
                or type(entry.get("placebo")) is not int
                or (entry["unit_id"], entry["family"]) not in counted_source
                or entry["learned"] != counted_source[entry["unit_id"], entry["family"]]
                or entry["placebo"] != entry["learned"]
                for entry in exposure
            )
            or len({(e["unit_id"], e["family"]) for e in exposure}) != len(exposure)):
        errors.append("exposure_accounting_mismatch")

    gate = report.get("technical_yield_gate")
    should_pass = (
        accepted / (3 * total) >= 0.95 and triplets / total >= 0.90
        and all(r["status"] == "accepted" for r in development)
    )
    if (
        not isinstance(gate, dict)
        or gate.get("min_action_yield") != 0.95
        or gate.get("min_full_triplet_yield") != 0.90
        or gate.get("all_development_actions_parseable") is not True
        or gate.get("passed_in_fixture") is not should_pass
        or gate.get("authorizes_live_campaign") is not False
    ):
        errors.append("technical_gate_mismatch")
    return MultischemaAudit(
        "rejected_inconsistent" if errors else "structurally_consistent_unattested",
        tuple(dict.fromkeys(errors)),
        len(observed),
    )
