#!/usr/bin/env python3
"""Deterministically evaluate frozen D2 confirmatory provider output."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import d2_confirmatory_stats as stats
import run_d2_confirmatory as runner
from d2_calibration_r2_core import ACTIONS, score_actions

EXPECTED_ATTEMPTED_PAIRS = 360
EXPECTED_MODEL = "glm-5-turbo"
EXPECTED_TEMPERATURE = 0.8
EXPECTED_COHORT_SHA256 = runner.EXPECTED_COHORT_SHA256
EXPECTED_DEVELOPED_CALLS = 9
EXPECTED_FRESH_CALLS = 4
EXPECTED_EVALUATION_ACTIONS = 32


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _global_integrity(
    provider: dict[str, Any],
    *,
    plan_path: Path,
    request_plan_path: Path,
    cohort_lock_path: Path,
) -> list[str]:
    defects: list[str] = []
    if provider.get("schema") != "d2-confirmatory-provider-output-v0.1":
        defects.append("provider_schema")
    if provider.get("status") != "provider_campaign_complete_unclassified":
        defects.append("provider_status")
    if provider.get("classification") is not None:
        defects.append("runner_must_not_classify")
    if provider.get("attempted_pairs") != EXPECTED_ATTEMPTED_PAIRS:
        defects.append("attempted_pair_count")
    if provider.get("model") != EXPECTED_MODEL:
        defects.append("model_drift")
    if float(provider.get("temperature", -1.0)) != EXPECTED_TEMPERATURE:
        defects.append("temperature_drift")
    if provider.get("production_historical_substrate_enabled") is not False:
        defects.append("historical_substrate_enabled")

    cohort = provider.get("cohort_lock", {})
    if cohort.get("pair_count") != EXPECTED_ATTEMPTED_PAIRS:
        defects.append("cohort_pair_count")
    if cohort.get("cohort_pairs_sha256") != EXPECTED_COHORT_SHA256:
        defects.append("cohort_hash")
    if cohort.get("all_source_destination_overlaps_zero") is not True:
        defects.append("cohort_source_destination_overlap")
    if cohort.get("all_development_evaluation_overlaps_zero") is not True:
        defects.append("cohort_development_evaluation_overlap")

    expected_hashes = {
        "plan_sha256": file_sha256(plan_path),
        "request_plan_sha256": file_sha256(request_plan_path),
        "cohort_lock_file_sha256": file_sha256(cohort_lock_path),
    }
    for key, expected in expected_hashes.items():
        if provider.get(key) != expected:
            defects.append(f"{key}_mismatch")

    records = provider.get("pair_records")
    if not isinstance(records, list) or len(records) != EXPECTED_ATTEMPTED_PAIRS:
        defects.append("pair_record_count")
    else:
        indexes = [row.get("pair_index") for row in records]
        if indexes != list(range(EXPECTED_ATTEMPTED_PAIRS)):
            defects.append("pair_record_order_or_identity")

    complete_count = sum(
        1 for row in records or [] if row.get("status") == "complete"
    )
    failed_count = sum(
        1 for row in records or [] if row.get("status") != "complete"
    )
    if provider.get("complete_pairs") != complete_count:
        defects.append("complete_pair_count")
    if provider.get("failed_pairs") != failed_count:
        defects.append("failed_pair_count")
    if complete_count + failed_count != EXPECTED_ATTEMPTED_PAIRS:
        defects.append("pair_count_partition")
    return defects


def _pair_integrity(row: dict[str, Any]) -> tuple[list[str], dict[str, float] | None]:
    defects: list[str] = []
    pair_index = int(row["pair_index"])
    bundle = runner.case_bundle(pair_index)
    expected_lock = runner.pair_lock_record(pair_index)
    if row.get("pair_lock_record") != expected_lock:
        defects.append("pair_lock_record")

    audit = row.get("artifact_audit", {})
    if audit.get("passed") is not True:
        defects.append("artifact_audit")

    eval_cases = bundle["eval_cases"]
    expected_ids = [case["case_id"] for case in eval_cases]
    expected_truth = [case["correct_action"] for case in eval_cases]
    if row.get("evaluation_case_ids") != expected_ids:
        defects.append("evaluation_case_ids")
    if row.get("evaluation_truth") != expected_truth:
        defects.append("evaluation_truth")

    arms = row.get("arms", {})
    expected_calls = {
        "source_developed": EXPECTED_DEVELOPED_CALLS,
        "reproduced": EXPECTED_DEVELOPED_CALLS,
        "description_only": EXPECTED_DEVELOPED_CALLS,
        "fresh": EXPECTED_FRESH_CALLS,
    }
    scores: dict[str, float] = {}
    for arm, call_count in expected_calls.items():
        record = arms.get(arm)
        if not isinstance(record, dict):
            defects.append(f"{arm}_missing")
            continue
        if record.get("logical_calls") != call_count:
            defects.append(f"{arm}_logical_calls")
        actions = record.get("evaluation_actions")
        if not isinstance(actions, list) or len(actions) != EXPECTED_EVALUATION_ACTIONS:
            defects.append(f"{arm}_evaluation_action_count")
            continue
        if any(action not in ACTIONS for action in actions):
            defects.append(f"{arm}_evaluation_action_vocabulary")
            continue
        score = score_actions(eval_cases, actions)
        runner_score = record.get("runner_final_score")
        if not isinstance(runner_score, (int, float)) or abs(score - float(runner_score)) > 1e-12:
            defects.append(f"{arm}_runner_score_mismatch")
        scores[arm] = score

    if (
        isinstance(arms.get("reproduced"), dict)
        and isinstance(arms.get("description_only"), dict)
        and arms["reproduced"].get("logical_calls")
        != arms["description_only"].get("logical_calls")
    ):
        defects.append("reproduced_description_call_inequality")

    if defects:
        return defects, None
    return defects, scores


def evaluate(
    provider_path: Path,
    *,
    plan_path: Path,
    request_plan_path: Path,
    cohort_lock_path: Path,
) -> dict[str, Any]:
    provider = json.loads(provider_path.read_text())
    global_defects = _global_integrity(
        provider,
        plan_path=plan_path,
        request_plan_path=request_plan_path,
        cohort_lock_path=cohort_lock_path,
    )

    pair_defects: list[dict[str, Any]] = []
    analyzable: list[tuple[int, dict[str, float]]] = []
    for row in provider.get("pair_records", []):
        if row.get("status") != "complete":
            continue
        defects, scores = _pair_integrity(row)
        if defects:
            pair_defects.append(
                {"pair_index": row.get("pair_index"), "defects": defects}
            )
        elif scores is not None:
            analyzable.append((int(row["pair_index"]), scores))

    integrity_ok = not global_defects and not pair_defects
    analyzable.sort(key=lambda item: item[0])
    analyzable_n = len(analyzable)

    statistical_result: dict[str, Any] | None = None
    if integrity_ok:
        fresh = [scores["fresh"] for _, scores in analyzable]
        description = [scores["description_only"] for _, scores in analyzable]
        reproduced = [scores["reproduced"] for _, scores in analyzable]
        source = [scores["source_developed"] for _, scores in analyzable]
        statistical_result = stats.evaluate_scores(
            fresh,
            description,
            reproduced,
            source,
        )
        classification = statistical_result["classification"]
        classification_label = statistical_result["classification_label"]
    else:
        classification = "D2-S4"
        classification_label = "scientifically_unclassifiable_integrity_failure"

    result = {
        "schema": "d2-confirmatory-result-v0.1",
        "provider_output_sha256": file_sha256(provider_path),
        "plan_sha256": file_sha256(plan_path),
        "request_plan_sha256": file_sha256(request_plan_path),
        "cohort_lock_file_sha256": file_sha256(cohort_lock_path),
        "cohort_pairs_sha256": EXPECTED_COHORT_SHA256,
        "attempted_pairs": provider.get("attempted_pairs"),
        "complete_pairs": provider.get("complete_pairs"),
        "failed_pairs": provider.get("failed_pairs"),
        "analyzable_pairs": analyzable_n,
        "minimum_analyzable_pairs": stats.MIN_ANALYZABLE,
        "integrity": {
            "passed": integrity_ok,
            "global_defects": global_defects,
            "pair_defects": pair_defects,
            "evaluated_complete_pairs": analyzable_n + len(pair_defects),
        },
        "statistics": statistical_result,
        "classification": classification,
        "classification_label": classification_label,
        "claim_ceiling": (
            "registered single-model synthetic individual-agent stochastic capability-reproduction "
            "mechanism only; no weight learning, cross-model/provider, naturalistic, team/swarm/"
            "institution, composition, market, environment-spawning, or production Historical "
            "Substrate claim"
        ),
        "registry_promotion_authorized": False,
        "production_historical_substrate_enabled": False,
    }
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("provider_output")
    parser.add_argument("--output-dir", default="output/d2-confirmatory-evaluation")
    parser.add_argument("--plan", default="research/d2/D2_CONFIRMATORY_PLAN.md")
    parser.add_argument(
        "--request-plan",
        default="research/d2/D2_CONFIRMATORY_REQUEST_PLAN.json",
    )
    parser.add_argument(
        "--cohort-lock",
        default="research/d2/d2-confirmatory-cohort-lock.json",
    )
    args = parser.parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    result = evaluate(
        Path(args.provider_output),
        plan_path=Path(args.plan),
        request_plan_path=Path(args.request_plan),
        cohort_lock_path=Path(args.cohort_lock),
    )
    result_path = output_dir / "d2-confirmatory-result.json"
    result_path.write_bytes(canonical_bytes(result))
    manifest = {
        "schema": "d2-confirmatory-evaluation-manifest-v0.1",
        "provider_output_sha256": result["provider_output_sha256"],
        "result_sha256": file_sha256(result_path),
        "classification": result["classification"],
        "analyzable_pairs": result["analyzable_pairs"],
        "registry_promotion_authorized": False,
        "production_historical_substrate_enabled": False,
    }
    manifest_path = output_dir / "evaluation-manifest.json"
    manifest_path.write_bytes(canonical_bytes(manifest))
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
