from __future__ import annotations

import evaluate_d2_vnext_q3d3_diagnostic as evaluator
import materialize_d2_vnext_q3d3_diagnostic as materializer


def _base_payload() -> dict[str, object]:
    return {
        "integrity_defects": [],
        "attempted_pairs": 8,
        "complete_pairs": 0,
        "failed_pairs": 8,
        "physical_provider_sends_observed": 0,
        "cohort_pairs_sha256": materializer.EXPECTED_COHORT_SHA256,
        "pair_records": [],
    }


def test_evaluator_fails_closed_when_no_observability_records_exist() -> None:
    result = evaluator.evaluate_payload(_base_payload())
    assert result["classification"] == "Q3-D3-OBSERVABILITY-FAIL"
    assert result["classification_label"] == "observability_failure"
    assert result["observed_logical_call_records"] == 0
    assert result["scientific_effect_gates_computed"] is False
    assert result["acceptance_action_authorized"] is False
    assert result["registry_promotion_authorized"] is False


def test_evaluator_prioritizes_integrity_failure() -> None:
    payload = _base_payload()
    payload["physical_provider_sends_observed"] = 2305
    result = evaluator.evaluate_payload(payload)
    assert result["classification"] == "Q3-D3-INTEGRITY-FAIL"
    assert "campaign_send_cap_exceeded" in result["integrity_defects"]


def test_evaluator_rejects_wrong_cohort_commitment() -> None:
    payload = _base_payload()
    payload["cohort_pairs_sha256"] = "0" * 64
    result = evaluator.evaluate_payload(payload)
    assert result["classification"] == "Q3-D3-INTEGRITY-FAIL"
    assert "cohort_commitment_mismatch" in result["integrity_defects"]


def test_boundary_enum_excludes_unqualified_duplicate_sdk_layer() -> None:
    assert "http_body_content_absent" in evaluator.ALLOWED_Q3D3_BOUNDARIES
    assert "http_body_content_present_sdk_content_absent" in evaluator.ALLOWED_Q3D3_BOUNDARIES
    assert "sdk_content_present_q3d2_semantic_absent" not in evaluator.ALLOWED_Q3D3_BOUNDARIES
