#!/usr/bin/env python3
"""Frozen credential-free evaluator for D2c schema generalization."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import d2c_schema_core as core
import d2c_schema_stats as stats
import run_d2c_schema_generalization as runner

EXPECTED_ATTEMPTED_PAIRS = 540
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
    provider: dict[str, Any], *, plan_path: Path, request_plan_path: Path,
    schema_suite_path: Path, sample_size_path: Path, cohort_lock_path: Path, shard_map_path: Path
) -> list[str]:
    defects: list[str] = []
    if provider.get("schema") != "d2c-schema-generalization-provider-output-v0.1": defects.append("provider_schema")
    if provider.get("status") != "provider_campaign_complete_unclassified": defects.append("provider_status")
    if provider.get("classification") is not None: defects.append("provider_must_not_classify")
    if provider.get("attempted_pairs") != EXPECTED_ATTEMPTED_PAIRS: defects.append("attempted_pair_count")
    if provider.get("model") != EXPECTED_MODEL: defects.append("model_drift")
    if float(provider.get("temperature", -1)) != EXPECTED_TEMPERATURE: defects.append("temperature_drift")
    if provider.get("production_historical_substrate_enabled") is not False: defects.append("historical_substrate_enabled")
    if provider.get("aggregation_integrity", {}).get("passed") is not True: defects.append("aggregation_integrity")
    cohort = provider.get("cohort_lock", {})
    if cohort.get("pair_count") != EXPECTED_ATTEMPTED_PAIRS: defects.append("cohort_pair_count")
    if cohort.get("pairs_per_schema") != 180: defects.append("cohort_pairs_per_schema")
    if cohort.get("cohort_pairs_sha256") != EXPECTED_COHORT_SHA256: defects.append("cohort_hash")
    expected_hashes = {
        "plan_sha256": file_sha256(plan_path),
        "request_plan_sha256": file_sha256(request_plan_path),
        "schema_suite_sha256": file_sha256(schema_suite_path),
        "sample_size_sha256": file_sha256(sample_size_path),
        "cohort_lock_file_sha256": file_sha256(cohort_lock_path),
        "shard_map_sha256": file_sha256(shard_map_path),
    }
    for key, expected in expected_hashes.items():
        if provider.get(key) != expected: defects.append(f"{key}_mismatch")
    records = provider.get("pair_records")
    if not isinstance(records, list) or len(records) != EXPECTED_ATTEMPTED_PAIRS:
        defects.append("pair_record_count")
    elif [row.get("pair_index") for row in records] != list(range(EXPECTED_ATTEMPTED_PAIRS)):
        defects.append("pair_record_order_or_identity")
    return defects


def _pair_integrity(row: dict[str, Any]) -> tuple[list[str], dict[str, float] | None]:
    defects: list[str] = []
    pair_index = int(row["pair_index"])
    expected_schema, expected_local = core.schema_and_local_index(pair_index)
    if row.get("schema_id") != expected_schema: defects.append("schema_id")
    if row.get("schema_pair_index") != expected_local: defects.append("schema_pair_index")
    bundle = runner.case_bundle(pair_index)
    if row.get("pair_lock_record") != runner.pair_lock_record(pair_index): defects.append("pair_lock_record")
    audit = row.get("artifact_audit", {})
    if audit.get("passed") is not True: defects.append("artifact_audit")
    eval_cases = bundle["eval_cases"]
    expected_ids = [case["case_id"] for case in eval_cases]
    expected_truth = [case["correct_action"] for case in eval_cases]
    if row.get("evaluation_case_ids") != expected_ids: defects.append("evaluation_case_ids")
    if row.get("evaluation_truth") != expected_truth: defects.append("evaluation_truth")
    arms = row.get("arms", {})
    expected_calls = {"source_developed": EXPECTED_DEVELOPED_CALLS, "reproduced": EXPECTED_DEVELOPED_CALLS, "description_only": EXPECTED_DEVELOPED_CALLS, "fresh": EXPECTED_FRESH_CALLS}
    scores: dict[str, float] = {}
    for arm, expected_calls_n in expected_calls.items():
        record = arms.get(arm)
        if not isinstance(record, dict): defects.append(f"{arm}_missing"); continue
        if record.get("logical_calls") != expected_calls_n: defects.append(f"{arm}_logical_calls")
        actions = record.get("evaluation_actions")
        if not isinstance(actions, list) or len(actions) != EXPECTED_EVALUATION_ACTIONS:
            defects.append(f"{arm}_evaluation_action_count"); continue
        if any(action not in core.ACTIONS for action in actions):
            defects.append(f"{arm}_evaluation_action_vocabulary"); continue
        score = core.score_actions(eval_cases, actions)
        runner_score = record.get("runner_final_score")
        if not isinstance(runner_score, (int, float)) or abs(score - float(runner_score)) > 1e-12:
            defects.append(f"{arm}_runner_score_mismatch")
        scores[arm] = score
    if defects:
        return defects, None
    return defects, scores


def _classify(schema_results: dict[str, dict[str, Any]], integrity_ok: bool) -> tuple[str, str]:
    if not integrity_ok or any(not result["minimum_n_pass"] for result in schema_results.values()):
        return "D2c-S0", "scientifically_unclassifiable_integrity_or_minimum_n"
    if any(not result["P0"]["gate_pass"] for result in schema_results.values()):
        return "D2c-S1", "schema_generalization_source_development_not_established_all_schemas"
    if any(not result["P1"]["gate_pass"] for result in schema_results.values()):
        return "D2c-S2", "schema_generalization_reproduction_beyond_description_not_established_all_schemas"
    if any(not result["P2"]["gate_pass"] for result in schema_results.values()):
        return "D2c-S3", "schema_generalization_fidelity_not_established_all_schemas"
    return "D2c-S4", "single_model_g2_schema_generalization_supported"


def evaluate(
    provider_path: Path, *, plan_path: Path, request_plan_path: Path, schema_suite_path: Path,
    sample_size_path: Path, cohort_lock_path: Path, shard_map_path: Path
) -> dict[str, Any]:
    provider = json.loads(provider_path.read_text())
    global_defects = _global_integrity(provider, plan_path=plan_path, request_plan_path=request_plan_path, schema_suite_path=schema_suite_path, sample_size_path=sample_size_path, cohort_lock_path=cohort_lock_path, shard_map_path=shard_map_path)
    pair_defects: list[dict[str, Any]] = []
    analyzable: dict[str, list[tuple[int, dict[str, float]]]] = {schema_id: [] for schema_id in core.SCHEMA_ORDER}
    for row in provider.get("pair_records", []):
        if row.get("status") != "complete":
            continue
        defects, scores = _pair_integrity(row)
        if defects:
            pair_defects.append({"pair_index": row.get("pair_index"), "defects": defects})
        elif scores is not None:
            analyzable[str(row["schema_id"])].append((int(row["pair_index"]), scores))
    for rows in analyzable.values(): rows.sort(key=lambda item: item[0])
    integrity_ok = not global_defects and not pair_defects
    schema_results: dict[str, dict[str, Any]] = {}
    for schema_offset, schema_id in enumerate(core.SCHEMA_ORDER):
        rows = analyzable[schema_id]
        fresh = [s["fresh"] for _, s in rows]
        description = [s["description_only"] for _, s in rows]
        reproduced = [s["reproduced"] for _, s in rows]
        source = [s["source_developed"] for _, s in rows]
        schema_results[schema_id] = stats.evaluate_schema_scores(fresh, description, reproduced, source, bootstrap_seed_offset=schema_offset) if integrity_ok else {
            "minimum_n_pass": len(rows) >= stats.MIN_ANALYZABLE_PER_SCHEMA,
            "analyzable_pairs": len(rows),
            "minimum_analyzable_pairs": stats.MIN_ANALYZABLE_PER_SCHEMA,
            "P0": None, "P1": None, "P2": None, "all_gates_pass": False, "bootstrap_sensitivity": None,
        }
    classification, label = _classify(schema_results, integrity_ok)
    return {
        "schema": "d2c-schema-generalization-result-v0.1",
        "provider_output_sha256": file_sha256(provider_path),
        "plan_sha256": file_sha256(plan_path),
        "request_plan_sha256": file_sha256(request_plan_path),
        "schema_suite_sha256": file_sha256(schema_suite_path),
        "sample_size_sha256": file_sha256(sample_size_path),
        "cohort_lock_file_sha256": file_sha256(cohort_lock_path),
        "shard_map_sha256": file_sha256(shard_map_path),
        "cohort_pairs_sha256": EXPECTED_COHORT_SHA256,
        "attempted_pairs": provider.get("attempted_pairs"),
        "complete_pairs": provider.get("complete_pairs"),
        "failed_pairs": provider.get("failed_pairs"),
        "analyzable_pairs_by_schema": {schema_id: len(analyzable[schema_id]) for schema_id in core.SCHEMA_ORDER},
        "minimum_analyzable_pairs_per_schema": stats.MIN_ANALYZABLE_PER_SCHEMA,
        "integrity": {
            "passed": integrity_ok,
            "global_defects": global_defects,
            "pair_defects": pair_defects,
        },
        "schema_results": schema_results,
        "program_decision_rule": "all_three_schemas_must_independently_pass_minimum_n_P0_P1_P2_no_pooling_or_rescue",
        "classification": classification,
        "classification_label": label,
        "claim_ceiling": "registered single-model synthetic individual-agent G2 schema-generalization across the three frozen D2c schemas using Z.AI glm-5-turbo only; no G3 operator, cross-model/provider, naturalistic, team/swarm/institution, composition, market, environment-spawning, production-readiness, or production Historical Substrate claim",
        "registry_promotion_authorized": False,
        "production_historical_substrate_enabled": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("provider_output")
    parser.add_argument("--output-dir", default="output/d2c-evaluation")
    parser.add_argument("--plan", default="research/d2c/PLAN.md")
    parser.add_argument("--request-plan", default="research/d2c/D2C_REQUEST_PLAN.json")
    parser.add_argument("--schema-suite", default="research/d2c/D2C_SCHEMA_SUITE.json")
    parser.add_argument("--sample-size", default="research/d2c/D2C_SAMPLE_SIZE.json")
    parser.add_argument("--cohort-lock", default="research/d2c/d2c-schema-cohort-lock.json")
    parser.add_argument("--shard-map", default="research/d2c/D2C_SHARD_MAP.json")
    args = parser.parse_args()
    out = Path(args.output_dir); out.mkdir(parents=True, exist_ok=True)
    result = evaluate(Path(args.provider_output), plan_path=Path(args.plan), request_plan_path=Path(args.request_plan), schema_suite_path=Path(args.schema_suite), sample_size_path=Path(args.sample_size), cohort_lock_path=Path(args.cohort_lock), shard_map_path=Path(args.shard_map))
    result_path = out / "d2c-schema-generalization-result.json"
    result_path.write_bytes(canonical_bytes(result))
    manifest = {
        "schema": "d2c-schema-generalization-evaluation-manifest-v0.1",
        "provider_output_sha256": result["provider_output_sha256"],
        "result_sha256": file_sha256(result_path),
        "classification": result["classification"],
        "analyzable_pairs_by_schema": result["analyzable_pairs_by_schema"],
        "registry_promotion_authorized": False,
        "production_historical_substrate_enabled": False,
    }
    (out / "evaluation-manifest.json").write_bytes(canonical_bytes(manifest))
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
