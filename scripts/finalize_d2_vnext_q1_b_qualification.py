#!/usr/bin/env python3
# ruff: noqa: E501
"""Finalize Q1-B only after the frozen independent exchangeability review."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sha256(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(ch in "0123456789abcdef" for ch in value)


def finalize(result: dict[str, Any], review: dict[str, Any]) -> dict[str, Any]:
    if result.get("schema") != "d2-vnext-q1-acquisition-qualification-result-v0.1":
        raise ValueError("Q1-B evaluation schema mismatch")
    if result.get("stage") != "Q1-B":
        raise ValueError("finalizer accepts Q1-B only")
    if result.get("classification") != "D2-vNext-Q1-B2":
        raise ValueError("Q1-B finalization requires resource-feasible B2 evaluation")
    if result.get("exchangeability_review_required") is not True:
        raise ValueError("Q1-B evaluation did not require frozen review")
    if review.get("schema") != "d2-vnext-q1-b-exchangeability-review-v0.1":
        raise ValueError("Q1-B exchangeability review schema mismatch")
    required = {
        "schema",
        "study_stream",
        "provider_output_sha256",
        "q1_b_evaluation_result_sha256",
        "reviewer",
        "review_timestamp_utc",
        "reviewed_completion_by_schema",
        "reviewed_completion_by_shard",
        "reviewed_completion_by_execution_wave",
        "reviewed_transport_and_runtime_metadata",
        "scientific_effect_inputs_consulted",
        "verdict",
        "rationale",
    }
    if set(review) != required:
        raise ValueError("Q1-B exchangeability review field set mismatch")
    if review.get("study_stream") != "D2-vNext-Q1":
        raise ValueError("Q1-B exchangeability review stream mismatch")
    if not _sha256(review.get("provider_output_sha256")) or not _sha256(
        review.get("q1_b_evaluation_result_sha256")
    ):
        raise ValueError("Q1-B review hashes invalid")
    if review.get("provider_output_sha256") != result.get("provider_output_sha256"):
        raise ValueError("Q1-B review provider-output hash mismatch")
    for key in (
        "reviewed_completion_by_schema",
        "reviewed_completion_by_shard",
        "reviewed_completion_by_execution_wave",
        "reviewed_transport_and_runtime_metadata",
    ):
        if review.get(key) is not True:
            raise ValueError(f"Q1-B required review dimension missing: {key}")
    if review.get("scientific_effect_inputs_consulted") is not False:
        raise ValueError("Q1-B exchangeability review must not consult scientific-effect inputs")
    if not isinstance(review.get("reviewer"), str) or not review["reviewer"].strip():
        raise ValueError("Q1-B reviewer missing")
    if not isinstance(review.get("rationale"), str) or not review["rationale"].strip():
        raise ValueError("Q1-B review rationale missing")
    verdict = review.get("verdict")
    if verdict not in {"PASS", "INCONCLUSIVE_NONEXCHANGEABLE"}:
        raise ValueError("Q1-B exchangeability verdict invalid")
    final = {
        "schema": "d2-vnext-q1-b-final-qualification-v0.1",
        "study_stream": "D2-vNext-Q1",
        "stage": "Q1-B",
        "provider_output_sha256": result["provider_output_sha256"],
        "evaluation_classification": result["classification"],
        "future_confirmatory_clearance_contract": result[
            "future_confirmatory_clearance_contract"
        ],
        "exchangeability_review": review,
        "scientific_effect_gates_computed": False,
        "registry_promotion_authorized": False,
        "acceptance_action_authorized": False,
        "future_confirmatory_provider_execution_authorized": False,
        "production_historical_substrate_enabled": False,
    }
    if verdict == "PASS":
        final["classification"] = "D2-vNext-Q1-B-PASS"
        final["classification_label"] = "acquisition_envelope_resource_feasible_after_independent_exchangeability_review"
    else:
        final["classification"] = "D2-vNext-Q1-B-INCONCLUSIVE_NONEXCHANGEABLE"
        final["classification_label"] = "resource_feasibility_not_interpretable_under_frozen_binomial_exchangeability_model"
    return final


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("evaluation_result")
    parser.add_argument("exchangeability_review")
    parser.add_argument("--output-dir", default="output/d2-vnext-q1-b-final")
    args = parser.parse_args()
    result_path = Path(args.evaluation_result)
    review_path = Path(args.exchangeability_review)
    result = json.loads(result_path.read_text())
    review = json.loads(review_path.read_text())
    if review.get("q1_b_evaluation_result_sha256") != file_sha256(result_path):
        raise ValueError("Q1-B exchangeability review evaluation-result hash mismatch")
    final = finalize(result, review)
    final["q1_b_evaluation_result_sha256"] = file_sha256(result_path)
    final["exchangeability_review_sha256"] = file_sha256(review_path)
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / "D2_VNEXT_Q1_B_FINAL_QUALIFICATION.json"
    path.write_bytes(canonical_bytes(final))
    print(json.dumps({"classification": final["classification"], "result_sha256": file_sha256(path)}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
