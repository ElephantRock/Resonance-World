from __future__ import annotations

import copy

import finalize_d2_vnext_q1_b_qualification as finalizer

PROVIDER_SHA = "a" * 64
EVALUATION_SHA = "b" * 64


def _result() -> dict:
    return {
        "schema": "d2-vnext-q1-acquisition-qualification-result-v0.1",
        "study_stream": "D2-vNext-Q1",
        "stage": "Q1-B",
        "classification": "D2-vNext-Q1-B2",
        "provider_output_sha256": PROVIDER_SHA,
        "exchangeability_review_required": True,
        "future_confirmatory_clearance_contract": {
            "resource_feasible": True,
            "required_attempted_pairs_total": 600,
        },
    }


def _review(verdict: str = "PASS") -> dict:
    return {
        "schema": "d2-vnext-q1-b-exchangeability-review-v0.1",
        "study_stream": "D2-vNext-Q1",
        "provider_output_sha256": PROVIDER_SHA,
        "q1_b_evaluation_result_sha256": EVALUATION_SHA,
        "reviewer": "independent-reviewer",
        "review_timestamp_utc": "2026-09-24T00:00:00Z",
        "reviewed_completion_by_schema": True,
        "reviewed_completion_by_shard": True,
        "reviewed_completion_by_execution_wave": True,
        "reviewed_transport_and_runtime_metadata": True,
        "scientific_effect_inputs_consulted": False,
        "verdict": verdict,
        "rationale": "Acquisition-only fixture review.",
    }


def test_pass_review_finalizes_q1_b_without_execution_authority() -> None:
    final = finalizer.finalize(_result(), _review("PASS"))
    assert final["classification"] == "D2-vNext-Q1-B-PASS"
    assert final["scientific_effect_gates_computed"] is False
    assert final["future_confirmatory_provider_execution_authorized"] is False
    assert final["registry_promotion_authorized"] is False
    assert final["production_historical_substrate_enabled"] is False


def test_nonexchangeable_review_is_inconclusive() -> None:
    final = finalizer.finalize(_result(), _review("INCONCLUSIVE_NONEXCHANGEABLE"))
    assert final["classification"] == "D2-vNext-Q1-B-INCONCLUSIVE_NONEXCHANGEABLE"


def test_review_cannot_consult_scientific_effect_inputs() -> None:
    review = _review()
    review["scientific_effect_inputs_consulted"] = True
    try:
        finalizer.finalize(_result(), review)
    except ValueError as exc:
        assert "must not consult scientific-effect inputs" in str(exc)
    else:
        raise AssertionError("scientific-effect-contaminated review was accepted")


def test_review_hash_must_match_provider_output() -> None:
    review = copy.deepcopy(_review())
    review["provider_output_sha256"] = "c" * 64
    try:
        finalizer.finalize(_result(), review)
    except ValueError as exc:
        assert "provider-output hash mismatch" in str(exc)
    else:
        raise AssertionError("mismatched review provider hash was accepted")
