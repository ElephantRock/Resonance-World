"""Independent source-ledger accounting for offline multischema G1 v2."""

from __future__ import annotations

import copy
import json

import pytest

from resonance_world.c3r_g1_multischema import (
    LocalFixtureEvaluator,
    V2Design,
    V2Runner,
    run_offline_multischema_fixture,
)
from resonance_world.c3r_g1_multischema_audit import audit_multischema


def _fixture():
    spec = V2Design(units=2, development_per_family=3, qualification_per_family=2)
    cohort = spec.freeze()
    evaluator = LocalFixtureEvaluator(cohort, private_seed=1701)
    report = run_offline_multischema_fixture(spec).to_dict()
    return cohort, evaluator, report


def test_default_report_recomputed_without_model_or_provider() -> None:
    cohort = V2Design().freeze()
    report = run_offline_multischema_fixture().to_dict()
    plain = audit_multischema(report, cohort)
    graded = audit_multischema(
        report, cohort, fixture_evaluator=LocalFixtureEvaluator(
            cohort, private_seed=1701
        )
    )
    assert plain.verdict == graded.verdict == "structurally_consistent_unattested"
    assert plain.errors == graded.errors == ()
    assert plain.inspected_attempts == graded.inspected_attempts == 480
    assert graded.to_dict() == {
        "schema": "c3r-g1-multischema-audit-v0.1",
        "verdict": "structurally_consistent_unattested",
        "errors": [],
        "inspected_attempts": 480,
        "independent_grader_attested": False,
        "provider_activity_verified": False,
        "scientific_acceptance": False,
    }


@pytest.mark.parametrize(("path", "value", "expected_issue"), [
    (("public_cohort_digest",), "0" * 64, "public_cohort_lock_mismatch"),
    (("trial_digest",), "0" * 64, "attempt_digest_mismatch"),
    (("prescribed_logical_calls",), 1, "reported_logical_call_count_mismatch"),
    (("heldout_triplets_complete",), 1, "qualification_aggregate_mismatch"),
    (("qualification_actions_accepted",), 0, "qualification_aggregate_mismatch"),
    (("source_dev_accepted",), 0, "development_acceptance_mismatch"),
    (("source_exposure", 0, "placebo"), 99, "exposure_accounting_mismatch"),
    (("by_arm", "learned", "itt_successes"), 0, "arm_itt_mismatch"),
    (("by_family", "text", "fresh", "accepted"), 0, "family_itt_mismatch"),
    (("unit_effects", 0, "itt_learned_minus_fresh"), 1, "unit_itt_mismatch"),
    (("mean_unit_itt_learned_minus_fresh",), 1.0, "cluster_mean_fresh_mismatch"),
    (("technical_yield_gate", "passed_in_fixture"), False,
     "technical_gate_mismatch"),
    (("technical_yield_gate", "authorizes_live_campaign"), True,
     "technical_gate_mismatch"),
    (("provider_sends_verified",), True, "provider_sends_verified_must_be_false"),
    (("independent_evaluator_attested",), True,
     "independent_evaluator_attested_must_be_false"),
    (("scientific_acceptance",), True, "scientific_acceptance_must_be_false"),
    (("status",), "scientific_g1_proven", "unverified_port_status"),
    (("trial_records", 0, "family"), "fake", "record_task_mismatch"),
    (("trial_records", 0, "status"), "omitted", "invalid_record_outcome"),
])
def test_tampered_report_is_rejected(path, value, expected_issue) -> None:
    cohort, grader, report = _fixture()
    broken = copy.deepcopy(report)
    cursor = broken
    for part in path[:-1]:
        cursor = cursor[part]
    cursor[path[-1]] = value
    verdict = audit_multischema(broken, cohort, fixture_evaluator=grader)
    assert verdict.verdict == "rejected_inconsistent"
    assert expected_issue in verdict.errors
    assert verdict.to_dict()["scientific_acceptance"] is False


def test_duplicate_or_missing_heldout_attempt_is_never_silently_dropped() -> None:
    cohort, grader, source = _fixture()
    first = copy.deepcopy(source)
    first["trial_records"].pop()
    verdict = audit_multischema(first, cohort, fixture_evaluator=grader)
    assert verdict.verdict == "rejected_inconsistent"
    assert "attempt_denominator_mismatch" in verdict.errors
    assert "missing_prescribed_attempts" in verdict.errors

    duplicated = copy.deepcopy(source)
    duplicated["trial_records"][1] = copy.deepcopy(duplicated["trial_records"][0])
    verdict = audit_multischema(duplicated, cohort)
    assert "duplicate_observed_attempt" in verdict.errors
    assert "missing_prescribed_attempts" in verdict.errors


def test_forged_digest_cannot_hide_changed_private_fixture_grade() -> None:
    cohort, grader, source = _fixture()
    forged = copy.deepcopy(source)
    chosen = next(row for row in forged["trial_records"] if row["status"] == "accepted")
    chosen["success"] = not chosen["success"]
    import hashlib

    forged["trial_digest"] = hashlib.sha256(json.dumps(
        forged["trial_records"], sort_keys=True, separators=(",", ":")
    ).encode()).hexdigest()
    verdict = audit_multischema(forged, cohort, fixture_evaluator=grader)
    assert verdict.verdict == "rejected_inconsistent"
    assert "local_fixture_grade_mismatch" in verdict.errors


def test_report_never_qualifies_as_independent_evaluator_attestation() -> None:
    cohort, _grader, source = _fixture()
    no_external = audit_multischema(source, cohort)
    assert no_external.verdict == "structurally_consistent_unattested"
    assert no_external.to_dict()["independent_grader_attested"] is False
    source["trial_records"][0]["private_seed"] = 1701
    verdict = audit_multischema(source, cohort)
    assert "raw_or_private_field_present" in verdict.errors
    assert "invalid_record_schema" in verdict.errors
    assert "1701" not in json.dumps(verdict.to_dict())


def test_all_exception_attempts_remain_covered_by_full_denominator() -> None:
    class Exploding:
        def complete(self, _request):
            raise RuntimeError("SECRET_OR_RAW_PROVIDER_MESSAGE")

    spec = V2Design(units=2, development_per_family=3, qualification_per_family=2)
    cohort = spec.freeze()
    data = V2Runner(
        cohort, LocalFixtureEvaluator(cohort, private_seed=1701)
    ).run(port_factory=lambda _uid, _arm, _stage: Exploding()).to_dict()
    assert len(data["trial_records"]) == spec.logical_calls
    assert data["qualification_actions_accepted"] == 0
    assert data["technical_yield_gate"]["passed_in_fixture"] is False
    assert "SECRET_OR_RAW_PROVIDER_MESSAGE" not in json.dumps(data)
    verdict = audit_multischema(data, cohort)
    assert verdict.verdict == "structurally_consistent_unattested"
    assert verdict.inspected_attempts == spec.logical_calls


def test_malformed_top_level_does_not_return_success() -> None:
    cohort = V2Design(units=1).freeze()
    invalid = audit_multischema(None, cohort)
    assert invalid.verdict == "invalid_input"
    assert invalid.to_dict()["scientific_acceptance"] is False
    long_report = {"trial_records": [{}] * 481}
    verdict = audit_multischema(long_report, cohort)
    assert verdict.verdict == "rejected_inconsistent"
    assert "missing_or_overlong_trial_records" in verdict.errors
