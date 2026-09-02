#!/usr/bin/env python3
"""Frozen credential-free evaluator for D2d source capability acquisition."""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
from pathlib import Path
from typing import Any

import d2d_acquisition_core as core
import d2d_acquisition_stats as stats
import materialize_d2d_source_acquisition as materializer

PAIR_COUNT = 384
MINIMUM_ANALYZABLE_PER_SCHEMA = 88
THRESHOLD = 0.10
PRIMARY_ARMS = ("fresh", "developed_40", "developed_80", "developed_160")
BUDGETS = (160, 80, 40)
EXPECTED_COHORT_SHA256 = "a9c2077d4e76825d9ef1f6b245caf0231f5a4a3b1dc00cc0032793add8f9ea19"
BOOTSTRAP_SEEDS = {
    "threshold_at_4": 2026090201,
    "parity_pair": 2026090202,
    "interval_pair": 2026090203,
    "pairwise_order": 2026090204,
}


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _invalid_test(n: int) -> dict[str, Any]:
    return {
        "n": float(n),
        "mean": None,
        "sample_sd": None,
        "standard_error": None,
        "threshold": THRESHOLD,
        "z": None,
        "one_sided_p": None,
        "one_sided_95_lower": None,
        "gate_pass": False,
    }


def _score(truth: list[str], actions: list[str]) -> float:
    if len(truth) != core.EVALUATION_COUNT or len(actions) != core.EVALUATION_COUNT:
        raise ValueError("D2d evaluation vector length mismatch")
    if any(action not in core.ACTIONS for action in actions):
        raise ValueError("D2d unknown action token")
    return sum(a == b for a, b in zip(truth, actions, strict=True)) / len(truth)


def _validate_complete_pair(
    record: dict[str, Any],
) -> tuple[dict[str, float] | None, float | None, list[str], list[str]]:
    pair_index = int(record["pair_index"])
    defects: list[str] = []
    diagnostic_defects: list[str] = []
    expected_bundle = materializer.case_bundle(pair_index)
    expected_schema = expected_bundle["schema_id"]
    expected_local = expected_bundle["local_pair_index"]
    if record.get("schema_id") != expected_schema:
        defects.append("schema_id_mismatch")
    if int(record.get("schema_pair_index", -1)) != expected_local:
        defects.append("schema_pair_index_mismatch")
    if record.get("pair_lock_record") != materializer.pair_lock_record(pair_index):
        defects.append("pair_lock_record_mismatch")
    expected_eval_ids = [case["case_id"] for case in expected_bundle["evaluation_cases"]]
    expected_truth = [case["correct_action"] for case in expected_bundle["evaluation_cases"]]
    if record.get("evaluation_case_ids") != expected_eval_ids:
        defects.append("evaluation_case_ids_mismatch")
    if record.get("evaluation_truth") != expected_truth:
        defects.append("evaluation_truth_mismatch")
    development_cases = expected_bundle["development_cases"]
    expected_prefixes = {
        "developed_40": [case["case_id"] for case in development_cases[:40]],
        "developed_80": [case["case_id"] for case in development_cases[:80]],
        "developed_160": [case["case_id"] for case in development_cases],
    }
    if record.get("development_prefix_case_ids") != expected_prefixes:
        defects.append("development_prefix_case_ids_mismatch")
    arms = record.get("arms")
    if not isinstance(arms, dict):
        return None, None, defects + ["arms_missing"], diagnostic_defects
    scores: dict[str, float] = {}
    for arm in PRIMARY_ARMS:
        payload = arms.get(arm)
        if not isinstance(payload, dict):
            defects.append(f"{arm}_missing")
            continue
        actions = payload.get("evaluation_actions")
        if not isinstance(actions, list):
            defects.append(f"{arm}_actions_missing")
            continue
        try:
            score = _score(expected_truth, [str(value) for value in actions])
        except Exception:
            defects.append(f"{arm}_actions_invalid")
            continue
        runner_score = payload.get("runner_final_score")
        if not isinstance(runner_score, (int, float)) or abs(
            float(runner_score) - score
        ) > 1e-12:
            defects.append(f"{arm}_runner_score_mismatch")
            continue
        scores[arm] = score
    oracle_score: float | None = None
    oracle = arms.get("oracle_instruction")
    if isinstance(oracle, dict) and oracle.get("status") == "complete_diagnostic":
        actions = oracle.get("evaluation_actions")
        if isinstance(actions, list):
            try:
                oracle_score = _score(expected_truth, [str(value) for value in actions])
                runner_score = oracle.get("runner_final_score")
                if not isinstance(runner_score, (int, float)) or abs(
                    float(runner_score) - oracle_score
                ) > 1e-12:
                    diagnostic_defects.append("oracle_runner_score_mismatch")
                    oracle_score = None
            except Exception:
                diagnostic_defects.append("oracle_actions_invalid")
        else:
            diagnostic_defects.append("oracle_actions_missing")
    elif isinstance(oracle, dict) and oracle.get("status") == "failed_diagnostic":
        oracle_score = None
    else:
        diagnostic_defects.append("oracle_status_invalid")
    if defects or set(scores) != set(PRIMARY_ARMS):
        return None, oracle_score, defects, diagnostic_defects
    return scores, oracle_score, defects, diagnostic_defects


def _schema_result(
    schema_id: str,
    score_rows: list[dict[str, float]],
    oracle_scores: list[float],
) -> dict[str, Any]:
    n = len(score_rows)
    differences = {
        budget: [row[f"developed_{budget}"] - row["fresh"] for row in score_rows]
        for budget in BUDGETS
    }
    tests: dict[int, dict[str, Any]] = {}
    prior_pass = n >= MINIMUM_ANALYZABLE_PER_SCHEMA
    for budget in BUDGETS:
        entered = bool(prior_pass)
        test = (
            stats.paired_margin_test(differences[budget], threshold=THRESHOLD)
            if n >= 2
            else _invalid_test(n)
        )
        test["gate_entered"] = entered
        test["gate_pass"] = bool(entered and test["gate_pass"])
        tests[budget] = test
        prior_pass = bool(test["gate_pass"])
    arm_means: dict[str, float | None] = {}
    for arm in PRIMARY_ARMS:
        arm_means[arm] = (
            statistics.fmean(row[arm] for row in score_rows) if score_rows else None
        )
    arm_means["oracle_instruction"] = (
        statistics.fmean(oracle_scores) if oracle_scores else None
    )
    return {
        "minimum_analyzable_pairs": MINIMUM_ANALYZABLE_PER_SCHEMA,
        "analyzable_pairs": n,
        "minimum_n_pass": n >= MINIMUM_ANALYZABLE_PER_SCHEMA,
        "gatekeeping_order": [
            "developed_160_minus_fresh",
            "developed_80_minus_fresh",
            "developed_40_minus_fresh",
        ],
        "alpha_one_sided": 0.05,
        "arm_means": arm_means,
        "oracle_analyzable_pairs": len(oracle_scores),
        "A160": tests[160],
        "A80": tests[80],
        "A40": tests[40],
        "lowest_confirmed_budget": (
            40
            if tests[40]["gate_pass"]
            else 80
            if tests[80]["gate_pass"]
            else 160
            if tests[160]["gate_pass"]
            else None
        ),
        "bootstrap_sensitivity": stats.paired_bootstrap(
            differences,
            seed=BOOTSTRAP_SEEDS[schema_id],
        ),
    }


def evaluate(provider: dict[str, Any]) -> dict[str, Any]:
    global_defects: list[str] = []
    pair_defects: list[dict[str, Any]] = []
    diagnostic_defects: list[dict[str, Any]] = []
    if provider.get("schema") != "d2d-source-acquisition-provider-output-v0.1":
        global_defects.append("provider_schema_mismatch")
    if provider.get("status") != "provider_campaign_complete_unclassified":
        global_defects.append("provider_status_mismatch")
    if provider.get("classification") is not None:
        global_defects.append("provider_must_be_unclassified")
    if provider.get("attempted_pairs") != PAIR_COUNT:
        global_defects.append("attempted_pair_count_mismatch")
    if provider.get("cohort_pairs_sha256") != EXPECTED_COHORT_SHA256:
        global_defects.append("cohort_hash_mismatch")
    if provider.get("production_historical_substrate_enabled") is not False:
        global_defects.append("historical_substrate_drift")
    records = provider.get("pair_records")
    if not isinstance(records, list) or len(records) != PAIR_COUNT:
        global_defects.append("pair_record_count_mismatch")
        records = records if isinstance(records, list) else []
    indices: list[int] = []
    for record in records:
        try:
            indices.append(int(record["pair_index"]))
        except Exception:
            global_defects.append("pair_index_invalid")
            break
    if indices != list(range(PAIR_COUNT)):
        global_defects.append("pair_index_coverage_mismatch")

    scores_by_schema: dict[str, list[dict[str, float]]] = {
        schema_id: [] for schema_id in core.SCHEMA_ORDER
    }
    oracle_by_schema: dict[str, list[float]] = {
        schema_id: [] for schema_id in core.SCHEMA_ORDER
    }
    failed_pairs = 0
    complete_pairs = 0
    for record in records:
        if not isinstance(record, dict):
            continue
        if record.get("status") != "complete":
            failed_pairs += 1
            continue
        complete_pairs += 1
        pair_index = int(record["pair_index"])
        schema_id, _ = core.schema_and_local_index(pair_index)
        scores, oracle_score, defects, diag = _validate_complete_pair(record)
        if defects:
            pair_defects.append({"pair_index": pair_index, "defects": defects})
        elif scores is not None:
            scores_by_schema[schema_id].append(scores)
        if diag:
            diagnostic_defects.append({"pair_index": pair_index, "defects": diag})
        if oracle_score is not None:
            oracle_by_schema[schema_id].append(oracle_score)

    if provider.get("complete_pairs") != complete_pairs:
        global_defects.append("provider_complete_accounting_mismatch")
    if provider.get("failed_pairs") != failed_pairs:
        global_defects.append("provider_failed_accounting_mismatch")
    if complete_pairs + failed_pairs != PAIR_COUNT:
        global_defects.append("complete_failed_total_mismatch")

    schema_results = {
        schema_id: _schema_result(
            schema_id,
            scores_by_schema[schema_id],
            oracle_by_schema[schema_id],
        )
        for schema_id in core.SCHEMA_ORDER
    }
    integrity_pass = not global_defects and not pair_defects
    minimum_n_all = all(result["minimum_n_pass"] for result in schema_results.values())
    positive_control = schema_results["threshold_at_4"]
    continuity_pass = bool(
        integrity_pass and minimum_n_all and positive_control["A40"]["gate_pass"]
    )

    common_budget: int | None = None
    if not integrity_pass or not minimum_n_all:
        classification = "D2d-A0"
        label = "acquisition_envelope_integrity_or_minimum_n_failure"
    elif not continuity_pass:
        classification = "D2d-A1"
        label = "positive_control_continuity_not_established"
    else:
        non_control = [
            schema_results[schema_id]
            for schema_id in ("parity_pair", "interval_pair", "pairwise_order")
        ]
        if not all(result["A160"]["gate_pass"] for result in non_control):
            classification = "D2d-A2"
            label = "no_common_acquisition_protocol_through_160"
        elif not all(result["A80"]["gate_pass"] for result in non_control):
            classification = "D2d-A3"
            label = "common_acquisition_budget_160"
            common_budget = 160
        elif not all(result["A40"]["gate_pass"] for result in non_control):
            classification = "D2d-A4"
            label = "common_acquisition_budget_80"
            common_budget = 80
        else:
            classification = "D2d-A5"
            label = "common_acquisition_budget_40"
            common_budget = 40

    return {
        "schema": "d2d-source-acquisition-result-v0.1",
        "classification": classification,
        "classification_label": label,
        "common_confirmed_acquisition_budget": common_budget,
        "attempted_pairs": PAIR_COUNT,
        "complete_pairs": complete_pairs,
        "failed_pairs": failed_pairs,
        "minimum_analyzable_pairs_per_schema": MINIMUM_ANALYZABLE_PER_SCHEMA,
        "analyzable_pairs_by_schema": {
            schema_id: len(scores_by_schema[schema_id])
            for schema_id in core.SCHEMA_ORDER
        },
        "integrity": {
            "passed": integrity_pass,
            "global_defects": global_defects,
            "pair_defects": pair_defects,
            "diagnostic_defects": diagnostic_defects,
        },
        "positive_control": {
            "schema_id": "threshold_at_4",
            "continuity_requirement": "developed_40_minus_fresh_primary_gate_pass",
            "continuity_pass": continuity_pass,
        },
        "schema_results": schema_results,
        "program_decision_rule": (
            "after integrity/minimum-N and threshold_at_4 40-case continuity, "
            "all three non-control calibration schemas must pass a budget before "
            "that budget can be selected as common"
        ),
        "calibration_only": True,
        "d2e_reuse_of_calibration_schemas_allowed": False,
        "registry_promotion_authorized": False,
        "production_historical_substrate_enabled": False,
        "claim_ceiling": (
            "single-model synthetic individual-agent source capability-acquisition "
            "calibration under the four frozen D2d schemas using Z.AI glm-5-turbo only; "
            "no capability-reproduction, schema-generalization, model/provider-generalization, "
            "naturalistic, team/swarm/institution, production-readiness, or Historical "
            "Substrate claim"
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("provider_output")
    parser.add_argument("--output-dir", default="output/d2d-evaluation")
    parser.add_argument("--plan", default="research/d2d/PLAN.md")
    parser.add_argument("--request-plan", default="research/d2d/D2D_REQUEST_PLAN.json")
    parser.add_argument("--schema-suite", default="research/d2d/D2D_SCHEMA_SUITE.json")
    parser.add_argument("--sample-size", default="research/d2d/D2D_SAMPLE_SIZE.json")
    parser.add_argument(
        "--cohort-lock", default="research/d2d/d2d-source-acquisition-cohort-lock.json"
    )
    parser.add_argument("--shard-map", default="research/d2d/D2D_SHARD_MAP.json")
    args = parser.parse_args()

    provider_path = Path(args.provider_output)
    provider = json.loads(provider_path.read_text())
    result = evaluate(provider)
    result.update(
        {
            "provider_output_sha256": file_sha256(provider_path),
            "plan_sha256": file_sha256(Path(args.plan)),
            "request_plan_sha256": file_sha256(Path(args.request_plan)),
            "schema_suite_sha256": file_sha256(Path(args.schema_suite)),
            "sample_size_sha256": file_sha256(Path(args.sample_size)),
            "cohort_lock_file_sha256": file_sha256(Path(args.cohort_lock)),
            "shard_map_sha256": file_sha256(Path(args.shard_map)),
            "cohort_pairs_sha256": EXPECTED_COHORT_SHA256,
        }
    )
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    result_path = out / "d2d-source-acquisition-result.json"
    result_path.write_bytes(canonical_bytes(result))
    manifest = {
        "schema": "d2d-source-acquisition-evaluation-manifest-v0.1",
        "classification": result["classification"],
        "common_confirmed_acquisition_budget": result[
            "common_confirmed_acquisition_budget"
        ],
        "result_sha256": file_sha256(result_path),
        "provider_output_sha256": result["provider_output_sha256"],
        "analyzable_pairs_by_schema": result["analyzable_pairs_by_schema"],
        "registry_promotion_authorized": False,
        "production_historical_substrate_enabled": False,
    }
    (out / "evaluation-manifest.json").write_bytes(canonical_bytes(manifest))
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
