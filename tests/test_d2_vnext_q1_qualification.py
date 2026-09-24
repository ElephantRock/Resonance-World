from __future__ import annotations

import math

import d2_vnext_q1_acquisition_core as core
import d2_vnext_q1_hermes_client as client
import evaluate_d2_vnext_q1_acquisition as evaluator


def _attempt(*, parse_valid: bool, diagnostic: str, completed: bool = False) -> dict:
    return {
        "runtime_exception": False,
        "error_type": None,
        "error_sha256": None,
        "hermes_completed_flag_valid": True,
        "hermes_completed": completed,
        "hermes_failed": False,
        "hermes_partial": False,
        "hermes_interrupted": False,
        "hermes_error_present": False,
        "exact_structured_parse_valid": parse_valid,
        "parse_diagnostic": diagnostic,
        "physical_provider_sends_observed": 1,
        "exact_attributed_clean_transport": True,
        "logical_attribution_integrity": True,
        "effective_completed": completed and parse_valid,
        "terminal_iteration_override_used": False,
        "adapter_reason": "fixture",
    }


def test_terminal_failure_evidence_is_bounded_and_located() -> None:
    first = _attempt(parse_valid=False, diagnostic="json_decode_failure")
    second = _attempt(parse_valid=False, diagnostic="wrong_action_count")
    evidence = client.build_terminal_failure_evidence(
        phase="d160-pairwise_order-p007/development3",
        logical_index=19,
        first=first,
        retry_eligible=True,
        second=second,
    )
    assert evidence["arm"] == "d160-pairwise_order-p007"
    assert evidence["phase"] == "d160-pairwise_order-p007/development3"
    assert evidence["logical_call_index"] == 19
    assert evidence["retry_eligible"] is True
    assert evidence["retry_used"] is True
    assert evidence["accepted_exact_completion"] is False
    assert evidence["terminal_error_sha256"] == client.TERMINAL_FAILURE_SHA256
    client.assert_failure_evidence_has_no_raw_content(evidence)


def test_terminal_failure_validator_rejects_missing_location() -> None:
    first = _attempt(parse_valid=False, diagnostic="json_decode_failure")
    evidence = client.build_terminal_failure_evidence(
        phase="fresh/evaluation1",
        logical_index=0,
        first=first,
        retry_eligible=False,
        second=None,
    )
    record = {
        "pair_public_id": "d2-vnext-q1a-threshold_at_4-pair-000",
        "pair_index": 0,
        "schema_id": "threshold_at_4",
        "failure_class": "q1_logical_call_no_accepted_exact_completion",
        "error_sha256": client.TERMINAL_FAILURE_SHA256,
        "terminal_failure": {
            **evidence,
            "pair_public_id": "d2-vnext-q1a-threshold_at_4-pair-000",
            "pair_index": 0,
            "schema_id": "threshold_at_4",
        },
    }
    assert evaluator.validate_terminal_failure(record) == []
    del record["terminal_failure"]["phase"]
    assert "terminal_failure_shape" in evaluator.validate_terminal_failure(record)


def test_exact_clopper_pearson_lower_special_cases() -> None:
    assert evaluator.clopper_pearson_lower(0, 96) == 0.0
    all_success = evaluator.clopper_pearson_lower(96, 96)
    assert math.isclose(
        all_success,
        evaluator.PER_SCHEMA_ALPHA ** (1 / 96),
        rel_tol=1e-12,
    )
    assert 0.72 < evaluator.clopper_pearson_lower(80, 96) < 0.74


def test_future_attempt_rule_is_monotone() -> None:
    p70 = evaluator.clopper_pearson_lower(70, 96)
    p80 = evaluator.clopper_pearson_lower(80, 96)
    p90 = evaluator.clopper_pearson_lower(90, 96)
    r70 = evaluator.required_future_attempts(p70)
    r80 = evaluator.required_future_attempts(p80)
    r90 = evaluator.required_future_attempts(p90)
    assert r70 is not None and r80 is not None and r90 is not None
    assert r90 < r80 < r70
    assert evaluator.binomial_tail_at_least(88, r80, p80) >= 0.9875
    assert evaluator.binomial_tail_at_least(88, r80 - 1, p80) < 0.9875


def test_q1_stage_counts_remain_frozen() -> None:
    assert core.pairs_per_schema(core.STAGE_A) == 16
    assert core.pairs_per_schema(core.STAGE_B) == 96
    assert evaluator.A_MIN_COMPLETE_PER_SCHEMA == 12
    assert evaluator.FUTURE_MIN_ANALYZABLE == 88
    assert evaluator.JOINT_CLEARANCE_TARGET == 0.95
    assert evaluator.PER_SCHEMA_CLEARANCE_TARGET == 0.9875
    assert evaluator.PER_SCHEMA_ALPHA == 0.0125
    assert evaluator.MAX_FUTURE_TOTAL_ATTEMPTS == 640
