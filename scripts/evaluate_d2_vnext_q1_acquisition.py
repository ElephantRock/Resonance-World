#!/usr/bin/env python3
# ruff: noqa: E501
"""Credential-free D2-vNext-Q1 acquisition qualification evaluator.

This evaluator validates acquisition completeness and bounded failure evidence. It
never computes developed-vs-fresh effect tests or capability-acquisition gates.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import aggregate_d2_vnext_q1_acquisition as aggregator
import d2_vnext_q1_acquisition_core as core
import materialize_d2_vnext_q1_acquisition as materializer

EXPECTED_MODEL = "glm-5.3"
EXPECTED_TEMPERATURE = 0.8
PRIMARY_ARMS = ("fresh", "developed_40", "developed_80", "developed_160")
EXPECTED_CALLS = {"fresh": 4, "developed_40": 9, "developed_80": 14, "developed_160": 24}
EXPECTED_DEVELOPMENT_CASES = {"fresh": 0, "developed_40": 40, "developed_80": 80, "developed_160": 160}
ORACLE_CALLS = 4
A_MIN_COMPLETE_PER_SCHEMA = 12
FUTURE_MIN_ANALYZABLE = 88
JOINT_CLEARANCE_TARGET = 0.95
PER_SCHEMA_CLEARANCE_TARGET = 0.9875
PER_SCHEMA_ALPHA = 0.0125
MAX_FUTURE_TOTAL_ATTEMPTS = 640


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def score(truth: list[str], actions: list[str]) -> float:
    if len(truth) != core.EVALUATION_COUNT or len(actions) != core.EVALUATION_COUNT:
        raise ValueError("Q1 evaluation vector length mismatch")
    if any(action not in core.ACTIONS for action in actions):
        raise ValueError("Q1 unknown action token")
    return sum(a == b for a, b in zip(truth, actions, strict=True)) / len(truth)


def validate_complete_pair(stage: str, record: dict[str, Any]) -> list[str]:
    defects: list[str] = []
    pair_index = int(record["pair_index"])
    bundle = materializer.case_bundle(stage, pair_index)
    schema_id = str(bundle["schema_id"])
    local_index = int(bundle["local_pair_index"])
    if record.get("stage") != stage:
        defects.append("stage_mismatch")
    if record.get("schema_id") != schema_id:
        defects.append("schema_id_mismatch")
    if int(record.get("schema_pair_index", -1)) != local_index:
        defects.append("schema_pair_index_mismatch")
    if record.get("pair_lock_record") != materializer.pair_lock_record(stage, pair_index):
        defects.append("pair_lock_record_mismatch")
    expected_eval_ids = [case["case_id"] for case in bundle["evaluation_cases"]]
    expected_truth = [case["correct_action"] for case in bundle["evaluation_cases"]]
    if record.get("evaluation_case_ids") != expected_eval_ids:
        defects.append("evaluation_case_ids_mismatch")
    if record.get("evaluation_truth") != expected_truth:
        defects.append("evaluation_truth_mismatch")
    development_cases = bundle["development_cases"]
    expected_prefixes = {
        "developed_40": [case["case_id"] for case in development_cases[:40]],
        "developed_80": [case["case_id"] for case in development_cases[:80]],
        "developed_160": [case["case_id"] for case in development_cases],
    }
    if record.get("development_prefix_case_ids") != expected_prefixes:
        defects.append("development_prefix_case_ids_mismatch")
    arms = record.get("arms")
    if not isinstance(arms, dict):
        return defects + ["arms_missing"]
    for arm in PRIMARY_ARMS:
        payload = arms.get(arm)
        if not isinstance(payload, dict):
            defects.append(f"{arm}_missing")
            continue
        if payload.get("development_cases") != EXPECTED_DEVELOPMENT_CASES[arm]:
            defects.append(f"{arm}_development_cases_mismatch")
        calls = payload.get("calls")
        if not isinstance(calls, list) or len(calls) != EXPECTED_CALLS[arm]:
            defects.append(f"{arm}_call_records_mismatch")
        else:
            for call_index, call in enumerate(calls):
                try:
                    if not isinstance(call, dict):
                        raise AssertionError("call_not_object")
                    aggregator._validate_complete_call(call)
                except Exception as exc:
                    defects.append(f"{arm}_call_{call_index}_{type(exc).__name__}")
        actions = payload.get("evaluation_actions")
        if not isinstance(actions, list):
            defects.append(f"{arm}_actions_missing")
            continue
        try:
            computed = score(expected_truth, [str(value) for value in actions])
        except Exception:
            defects.append(f"{arm}_actions_invalid")
            continue
        runner_score = payload.get("runner_final_score")
        if not isinstance(runner_score, (int, float)) or abs(float(runner_score) - computed) > 1e-12:
            defects.append(f"{arm}_runner_score_mismatch")
    oracle = arms.get("oracle_instruction")
    if isinstance(oracle, dict) and oracle.get("status") == "complete_diagnostic":
        calls = oracle.get("calls")
        if not isinstance(calls, list) or len(calls) != ORACLE_CALLS:
            defects.append("oracle_call_records_mismatch")
        else:
            for call_index, call in enumerate(calls):
                try:
                    if not isinstance(call, dict):
                        raise AssertionError("call_not_object")
                    aggregator._validate_complete_call(call)
                except Exception as exc:
                    defects.append(f"oracle_call_{call_index}_{type(exc).__name__}")
    elif not (isinstance(oracle, dict) and oracle.get("status") == "failed_diagnostic"):
        defects.append("oracle_status_invalid")
    return defects


def _validate_attempt_view(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    required = {
        "runtime_exception",
        "error_type",
        "error_sha256",
        "hermes_completed_flag_valid",
        "hermes_completed",
        "hermes_failed",
        "hermes_partial",
        "hermes_interrupted",
        "hermes_error_present",
        "exact_structured_parse_valid",
        "parse_diagnostic",
        "physical_provider_sends_observed",
        "exact_attributed_clean_transport",
        "logical_attribution_integrity",
        "effective_completed",
        "terminal_iteration_override_used",
        "adapter_reason",
    }
    return set(value) == required


def validate_terminal_failure(record: dict[str, Any]) -> list[str]:
    if record.get("failure_class") != "q1_logical_call_no_accepted_exact_completion":
        return ["failure_not_bounded_logical_call_class"]
    terminal = record.get("terminal_failure")
    if not isinstance(terminal, dict):
        return ["terminal_failure_missing"]
    defects: list[str] = []
    required = {
        "pair_public_id",
        "pair_index",
        "schema_id",
        "arm",
        "phase",
        "logical_call_index",
        "first_attempt",
        "retry_eligible",
        "retry_used",
        "second_attempt",
        "accepted_exact_completion",
        "terminal_error_type",
        "terminal_error_sha256",
    }
    if set(terminal) != required:
        defects.append("terminal_failure_shape")
    if terminal.get("pair_public_id") != record.get("pair_public_id"):
        defects.append("terminal_pair_public_id_mismatch")
    if terminal.get("pair_index") != record.get("pair_index"):
        defects.append("terminal_pair_index_mismatch")
    if terminal.get("schema_id") != record.get("schema_id"):
        defects.append("terminal_schema_id_mismatch")
    if not _validate_attempt_view(terminal.get("first_attempt")):
        defects.append("terminal_first_attempt_shape")
    retry_used = terminal.get("retry_used")
    second = terminal.get("second_attempt")
    if retry_used is True and not _validate_attempt_view(second):
        defects.append("terminal_second_attempt_shape")
    if retry_used is False and second is not None:
        defects.append("terminal_second_attempt_without_retry")
    if terminal.get("accepted_exact_completion") is not False:
        defects.append("terminal_failure_marked_accepted")
    if terminal.get("terminal_error_type") != "RuntimeError":
        defects.append("terminal_error_type")
    if terminal.get("terminal_error_sha256") != record.get("error_sha256"):
        defects.append("terminal_error_hash_mismatch")
    try:
        import d2_vnext_q1_hermes_client as client

        client.assert_failure_evidence_has_no_raw_content(terminal)
    except Exception:
        defects.append("terminal_raw_content_or_schema_violation")
    return defects


def binomial_tail_at_least(k: int, n: int, p: float) -> float:
    if k <= 0:
        return 1.0
    if k > n:
        return 0.0
    if p <= 0.0:
        return 0.0
    if p >= 1.0:
        return 1.0
    total = 0.0
    for j in range(k, n + 1):
        total += math.comb(n, j) * (p**j) * ((1.0 - p) ** (n - j))
    return min(1.0, max(0.0, total))


def clopper_pearson_lower(successes: int, trials: int, alpha: float = PER_SCHEMA_ALPHA) -> float:
    if not 0 <= successes <= trials or trials <= 0:
        raise ValueError("invalid binomial counts")
    if successes == 0:
        return 0.0
    lo = 0.0
    hi = successes / trials
    for _ in range(100):
        mid = (lo + hi) / 2.0
        if binomial_tail_at_least(successes, trials, mid) < alpha:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


def required_future_attempts(p_lower: float) -> int | None:
    if p_lower <= 0.0:
        return None
    for n in range(FUTURE_MIN_ANALYZABLE, MAX_FUTURE_TOTAL_ATTEMPTS + 1):
        if binomial_tail_at_least(FUTURE_MIN_ANALYZABLE, n, p_lower) >= PER_SCHEMA_CLEARANCE_TARGET:
            return n
    return None


def evaluate(provider: dict[str, Any]) -> dict[str, Any]:
    global_defects: list[str] = []
    pair_defects: list[dict[str, Any]] = []
    observability_defects: list[dict[str, Any]] = []
    if provider.get("schema") != "d2-vnext-q1-acquisition-provider-output-v0.1":
        global_defects.append("provider_schema_mismatch")
    if provider.get("study_stream") != "D2-vNext-Q1":
        global_defects.append("provider_stream_mismatch")
    stage = provider.get("stage")
    if stage not in core.STAGES:
        raise ValueError("unknown Q1 stage")
    if provider.get("status") != "provider_campaign_complete_unclassified":
        global_defects.append("provider_status_mismatch")
    if provider.get("classification") is not None:
        global_defects.append("provider_must_be_unclassified")
    if provider.get("fresh_namespace") != core.NAMESPACE:
        global_defects.append("fresh_namespace_mismatch")
    if provider.get("cohort_pairs_sha256") != materializer.EXPECTED_COHORT_SHA256[stage]:
        global_defects.append("cohort_hash_mismatch")
    if provider.get("requested_model") != EXPECTED_MODEL:
        global_defects.append("requested_model_mismatch")
    if provider.get("production_historical_substrate_enabled") is not False:
        global_defects.append("historical_substrate_drift")
    transport = provider.get("transport_integrity")
    if not isinstance(transport, dict) or transport.get("passed") is not True:
        global_defects.append("transport_integrity_failure")
    expected_count = core.pair_count(stage)
    if provider.get("attempted_pairs") != expected_count:
        global_defects.append("attempted_pair_count_mismatch")
    shard_inputs = provider.get("shard_inputs")
    expected_shards = 4 if stage == core.STAGE_A else 24
    if not isinstance(shard_inputs, list) or len(shard_inputs) != expected_shards:
        global_defects.append("shard_input_count_mismatch")
    elif any(row.get("status") != "loaded" for row in shard_inputs if isinstance(row, dict)):
        global_defects.append("not_all_provider_shards_loaded")
    records = provider.get("pair_records")
    if not isinstance(records, list) or len(records) != expected_count:
        global_defects.append("pair_record_count_mismatch")
        records = records if isinstance(records, list) else []
    indices: list[int] = []
    for record in records:
        try:
            indices.append(int(record["pair_index"]))
        except Exception:
            global_defects.append("pair_index_invalid")
            break
    if indices != list(range(expected_count)):
        global_defects.append("pair_index_coverage_mismatch")

    complete_by_schema: Counter[str] = Counter()
    failed_by_schema: Counter[str] = Counter()
    for record in records:
        if not isinstance(record, dict):
            continue
        pair_index = int(record["pair_index"])
        schema_id, _ = core.schema_and_local_index(stage, pair_index)
        if record.get("status") == "complete":
            defects = validate_complete_pair(stage, record)
            if defects:
                pair_defects.append({"pair_index": pair_index, "defects": defects})
            else:
                complete_by_schema[schema_id] += 1
        else:
            failed_by_schema[schema_id] += 1
            defects = validate_terminal_failure(record)
            if defects:
                observability_defects.append({"pair_index": pair_index, "defects": defects})

    expected_per_schema = core.pairs_per_schema(stage)
    schema_rows: dict[str, dict[str, Any]] = {}
    for schema_id in core.SCHEMA_ORDER:
        complete = complete_by_schema[schema_id]
        failed = failed_by_schema[schema_id]
        invalid_complete = sum(
            1
            for row in pair_defects
            if core.schema_and_local_index(stage, int(row["pair_index"]))[0] == schema_id
        )
        if complete + failed + invalid_complete != expected_per_schema:
            global_defects.append(f"{schema_id}_accounting_mismatch")
        schema_rows[schema_id] = {
            "attempted_pairs": expected_per_schema,
            "complete_evaluator_analyzable_pairs": complete,
            "failed_pairs": failed,
            "invalid_complete_pairs": invalid_complete,
            "completion_rate": complete / expected_per_schema,
        }

    integrity_pass = not global_defects and not pair_defects and not observability_defects
    result: dict[str, Any] = {
        "schema": "d2-vnext-q1-acquisition-qualification-result-v0.1",
        "study_stream": "D2-vNext-Q1",
        "stage": stage,
        "status": "qualification_evaluated",
        "integrity": {
            "passed": integrity_pass,
            "global_defects": global_defects,
            "pair_defects": pair_defects,
            "terminal_failure_observability_defects": observability_defects,
        },
        "schema_results": schema_rows,
        "scientific_effect_gates_computed": False,
        "s2_data_pooled": False,
        "registry_promotion_authorized": False,
        "acceptance_action_authorized": False,
        "production_historical_substrate_enabled": False,
    }
    if stage == core.STAGE_A:
        minimum_screen_pass = all(
            row["complete_evaluator_analyzable_pairs"] >= A_MIN_COMPLETE_PER_SCHEMA
            for row in schema_rows.values()
        )
        result["q1_a_continuation_gate"] = {
            "minimum_complete_analyzable_pairs_per_schema": A_MIN_COMPLETE_PER_SCHEMA,
            "minimum_screen_pass": minimum_screen_pass,
            "terminal_failure_observability_complete": not observability_defects,
            "all_provider_shards_loaded": "not_all_provider_shards_loaded" not in global_defects,
            "transport_integrity_pass": isinstance(transport, dict) and transport.get("passed") is True,
            "pass": bool(integrity_pass and minimum_screen_pass),
        }
        if not integrity_pass:
            result["classification"] = "D2-vNext-Q1-A0"
            result["classification_label"] = "integrity_or_terminal_failure_observability_failure"
        elif not minimum_screen_pass:
            result["classification"] = "D2-vNext-Q1-A1"
            result["classification_label"] = "minimum_screen_completion_failure"
        else:
            result["classification"] = "D2-vNext-Q1-A-PASS"
            result["classification_label"] = "bounded_screen_pass_for_independent_q1_b_authorization_review"
        result["q1_b_provider_execution_authorized"] = False
        return result

    lower_bounds: dict[str, float] = {}
    required_n: dict[str, int | None] = {}
    for schema_id, row in schema_rows.items():
        successes = int(row["complete_evaluator_analyzable_pairs"])
        trials = int(row["attempted_pairs"])
        lower = clopper_pearson_lower(successes, trials)
        lower_bounds[schema_id] = lower
        required_n[schema_id] = required_future_attempts(lower)
        row["one_sided_exact_completion_lower_bound"] = lower
        row["lower_bound_alpha"] = PER_SCHEMA_ALPHA
        row["future_attempts_required_for_88_at_q_0_9875"] = required_n[schema_id]
    finite = all(value is not None for value in required_n.values())
    total_required = sum(int(value) for value in required_n.values() if value is not None) if finite else None
    resource_feasible = bool(
        integrity_pass
        and finite
        and total_required is not None
        and total_required <= MAX_FUTURE_TOTAL_ATTEMPTS
    )
    result["future_confirmatory_clearance_contract"] = {
        "minimum_analyzable_pairs_per_schema": FUTURE_MIN_ANALYZABLE,
        "joint_all_schema_clearance_target": JOINT_CLEARANCE_TARGET,
        "per_schema_clearance_target": PER_SCHEMA_CLEARANCE_TARGET,
        "per_schema_lower_bound_alpha": PER_SCHEMA_ALPHA,
        "per_schema_lower_bounds": lower_bounds,
        "required_attempted_pairs_by_schema": required_n,
        "required_attempted_pairs_total": total_required,
        "maximum_allowed_attempted_pairs_total": MAX_FUTURE_TOTAL_ATTEMPTS,
        "resource_feasible": resource_feasible,
    }
    result["exchangeability_review_required"] = True
    result["exchangeability_review_status"] = "pending_independent_review"
    if not integrity_pass:
        result["classification"] = "D2-vNext-Q1-B0"
        result["classification_label"] = "integrity_or_terminal_failure_observability_failure"
    elif not resource_feasible:
        result["classification"] = "D2-vNext-Q1-B1"
        result["classification_label"] = "future_confirmatory_resource_feasibility_failure"
    else:
        result["classification"] = "D2-vNext-Q1-B2"
        result["classification_label"] = "resource_feasible_pending_independent_exchangeability_review"
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("provider_output")
    parser.add_argument("--output-dir", default="output/d2-vnext-q1-evaluation")
    args = parser.parse_args()
    provider_path = Path(args.provider_output)
    provider = json.loads(provider_path.read_text())
    result = evaluate(provider)
    result["provider_output_sha256"] = file_sha256(provider_path)
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    stage = str(result["stage"])
    slug = stage.lower().replace("-", "")
    result_path = out / f"d2-vnext-{slug}-qualification-result.json"
    result_path.write_bytes(canonical_bytes(result))
    manifest = {
        "schema": "d2-vnext-q1-acquisition-qualification-manifest-v0.1",
        "study_stream": "D2-vNext-Q1",
        "stage": stage,
        "classification": result["classification"],
        "classification_label": result["classification_label"],
        "result_sha256": file_sha256(result_path),
        "provider_output_sha256": result["provider_output_sha256"],
        "scientific_effect_gates_computed": False,
        "provider_execution_authorized": False,
        "registry_promotion_authorized": False,
        "acceptance_action_authorized": False,
        "production_historical_substrate_enabled": False,
    }
    (out / "evaluation-manifest.json").write_bytes(canonical_bytes(manifest))
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
