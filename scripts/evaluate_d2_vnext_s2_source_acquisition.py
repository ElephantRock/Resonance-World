#!/usr/bin/env python3
# ruff: noqa: E501
"""Credential-free frozen evaluator for D2-vNext-S2 acquisition calibration."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import d2_vnext_s2_acquisition_core as core
import evaluate_d2d_source_acquisition as base
import materialize_d2_vnext_s2_source_acquisition as materializer

EXPECTED_MODEL = "glm-5.3"
EXPECTED_TEMPERATURE = 0.8
MAX_PHYSICAL_SENDS_PER_LOGICAL_CALL = 36
MAX_PHYSICAL_SENDS_PER_SHARD = 2000
MAX_PHYSICAL_SENDS_CAMPAIGN = 48000
PRIMARY_ARMS = ("fresh", "developed_40", "developed_80", "developed_160")
BOOTSTRAP_SEEDS = {
    "threshold_at_4": 2026091901,
    "parity_pair": 2026091902,
    "interval_pair": 2026091903,
    "pairwise_order": 2026091904,
}


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@contextmanager
def _fresh_base_context() -> Iterator[None]:
    """Bind the historical statistical evaluator to this frozen fresh stratum."""
    original = (
        base.core,
        base.materializer,
        base.EXPECTED_COHORT_SHA256,
        base.EXPECTED_MODEL,
        base.EXPECTED_TEMPERATURE,
        base.BOOTSTRAP_SEEDS,
    )
    base.core = core
    base.materializer = materializer
    base.EXPECTED_COHORT_SHA256 = materializer.EXPECTED_COHORT_SHA256
    base.EXPECTED_MODEL = EXPECTED_MODEL
    base.EXPECTED_TEMPERATURE = EXPECTED_TEMPERATURE
    base.BOOTSTRAP_SEEDS = BOOTSTRAP_SEEDS
    try:
        yield
    finally:
        (
            base.core,
            base.materializer,
            base.EXPECTED_COHORT_SHA256,
            base.EXPECTED_MODEL,
            base.EXPECTED_TEMPERATURE,
            base.BOOTSTRAP_SEEDS,
        ) = original


def transport_defects(provider: dict[str, Any]) -> list[dict[str, Any]]:
    defects: list[dict[str, Any]] = []
    if provider.get("fresh_namespace") != core.NAMESPACE:
        defects.append({"scope": "provider", "defect": "fresh_namespace_drift"})
    if provider.get("response_format") != {"type": "json_object"}:
        defects.append({"scope": "provider", "defect": "json_mode_drift"})
    physical_total = provider.get("physical_provider_sends_observed_total")
    if type(physical_total) is not int or not 0 <= physical_total <= MAX_PHYSICAL_SENDS_CAMPAIGN:
        defects.append({"scope": "provider", "defect": "physical_campaign_count_invalid"})
    if provider.get("maximum_physical_provider_sends_campaign") != MAX_PHYSICAL_SENDS_CAMPAIGN:
        defects.append({"scope": "provider", "defect": "physical_campaign_ceiling_drift"})
    if provider.get("maximum_physical_provider_sends_per_shard") != MAX_PHYSICAL_SENDS_PER_SHARD:
        defects.append({"scope": "provider", "defect": "physical_shard_ceiling_drift"})
    if provider.get("maximum_physical_provider_sends_per_logical_call") != MAX_PHYSICAL_SENDS_PER_LOGICAL_CALL:
        defects.append({"scope": "provider", "defect": "physical_logical_ceiling_drift"})
    if not materializer.EXPECTED_COHORT_SHA256:
        defects.append({"scope": "provider", "defect": "cohort_hash_unpinned"})
    elif provider.get("cohort_pairs_sha256") != materializer.EXPECTED_COHORT_SHA256:
        defects.append({"scope": "provider", "defect": "cohort_hash_drift"})
    records = provider.get("pair_records")
    if not isinstance(records, list):
        return defects + [{"scope": "provider", "defect": "pair_records_missing"}]
    observed_from_complete_calls = 0
    for record in records:
        if not isinstance(record, dict) or record.get("status") != "complete":
            continue
        pair_index = int(record["pair_index"])
        arms = record.get("arms")
        if not isinstance(arms, dict):
            defects.append({"pair_index": pair_index, "defect": "arms_missing"})
            continue
        for arm in (*PRIMARY_ARMS, "oracle_instruction"):
            payload = arms.get(arm)
            if not isinstance(payload, dict) or payload.get("status") == "failed_diagnostic":
                continue
            calls = payload.get("calls")
            if not isinstance(calls, list):
                defects.append({"pair_index": pair_index, "arm": arm, "defect": "calls_missing"})
                continue
            for call_index, call in enumerate(calls):
                if not isinstance(call, dict):
                    defects.append({"pair_index": pair_index, "arm": arm, "call": call_index, "defect": "call_invalid"})
                    continue
                physical = call.get("physical_attempts")
                attempts = call.get("attempt_log")
                if (
                    type(physical) is not int
                    or not 1 <= physical <= MAX_PHYSICAL_SENDS_PER_LOGICAL_CALL
                    or not isinstance(attempts, list)
                    or len(attempts) != physical
                ):
                    defects.append({"pair_index": pair_index, "arm": arm, "call": call_index, "defect": "physical_attempt_count"})
                    continue
                observed_from_complete_calls += physical
                if call.get("retry_raw_first_response_content_included") is not False:
                    defects.append({"pair_index": pair_index, "arm": arm, "call": call_index, "defect": "raw_first_response_propagated"})
                used = call.get("retry_used")
                if used is True:
                    if call.get("retry_eligible_after_first") is not True:
                        defects.append({"pair_index": pair_index, "arm": arm, "call": call_index, "defect": "ineligible_retry"})
                    if call.get("agent_invocation_count") != 2:
                        defects.append({"pair_index": pair_index, "arm": arm, "call": call_index, "defect": "retry_invocation_count"})
                    if call.get("first_attempt_parse_valid") is True:
                        defects.append({"pair_index": pair_index, "arm": arm, "call": call_index, "defect": "valid_first_retried"})
                elif used is False and call.get("agent_invocation_count") != 1:
                    defects.append({"pair_index": pair_index, "arm": arm, "call": call_index, "defect": "primary_invocation_count"})
                if call.get("accepted_attempt_index") not in {1, 2}:
                    defects.append({"pair_index": pair_index, "arm": arm, "call": call_index, "defect": "accepted_attempt_invalid"})
                if call.get("json_mode_compatibility_failure") is not False:
                    defects.append({"pair_index": pair_index, "arm": arm, "call": call_index, "defect": "json_mode_compatibility_failure"})
                for attempt_index, attempt in enumerate(attempts, start=1):
                    if not isinstance(attempt, dict):
                        defects.append({"pair_index": pair_index, "arm": arm, "call": call_index, "defect": "attempt_shape"})
                        break
                    if attempt.get("logical_send_index") != attempt_index:
                        defects.append({"pair_index": pair_index, "arm": arm, "call": call_index, "defect": "logical_send_index"})
                        break
                    if attempt.get("http_status") != 200 or attempt.get("transport_error_type") is not None:
                        defects.append({"pair_index": pair_index, "arm": arm, "call": call_index, "defect": "transport_not_clean"})
                        break
    if type(physical_total) is int and observed_from_complete_calls > physical_total:
        defects.append({"scope": "provider", "defect": "complete_call_sends_exceed_total"})
    return defects


def evaluate(provider: dict[str, Any]) -> dict[str, Any]:
    if provider.get("schema") != "d2-vnext-s2-source-acquisition-provider-output-v0.1":
        raise ValueError("D2-vNext-S2 provider schema mismatch")
    if provider.get("study_stream") != "D2-vNext-S2":
        raise ValueError("D2-vNext-S2 provider stream mismatch")
    normalized = copy.deepcopy(provider)
    normalized["schema"] = "d2d-source-acquisition-provider-output-v0.1"
    normalized["model"] = provider.get("requested_model")
    with _fresh_base_context():
        result = base.evaluate(normalized)
    transport = transport_defects(provider)
    result["schema"] = "d2-vnext-s2-source-acquisition-result-v0.1"
    result["study_stream"] = "D2-vNext-S2"
    result["fresh_namespace"] = core.NAMESPACE
    result["requested_model"] = EXPECTED_MODEL
    result["effective_model_identity_observed"] = False
    result["effective_model_identity_claim"] = "unobserved_at_supported_product_boundary"
    result["historical_d2_vnext_s1_replacement_allowed"] = False
    result["historical_d2d_replacement_allowed"] = False
    result["historical_d2d_s2_replacement_allowed"] = False
    result["transport_integrity"] = {
        "contract": "qualified_terminal_completion_plus_bounded_format_regeneration_v0.1",
        "passed": not transport,
        "defects": transport,
        "maximum_physical_provider_sends_per_logical_call": MAX_PHYSICAL_SENDS_PER_LOGICAL_CALL,
        "maximum_physical_provider_sends_per_shard": MAX_PHYSICAL_SENDS_PER_SHARD,
        "maximum_physical_provider_sends_campaign": MAX_PHYSICAL_SENDS_CAMPAIGN,
        "observed_physical_provider_sends": provider.get("physical_provider_sends_observed_total"),
    }
    if transport:
        result["classification"] = "D2-vNext-S2-A0"
        result["classification_label"] = "acquisition_envelope_transport_or_retry_integrity_failure"
        result["common_confirmed_acquisition_budget"] = None
        result["integrity"]["passed"] = False
        result["integrity"]["global_defects"].append(
            "d2_vnext_s2_transport_or_retry_integrity_failure"
        )
        result["positive_control"]["continuity_pass"] = False
    else:
        result["classification"] = result["classification"].replace(
            "D2d-A", "D2-vNext-S2-A"
        )
    result["claim_ceiling"] = (
        "single supported-product synthetic individual-agent source capability-acquisition "
        "calibration under four frozen D2-vNext-S2 schemas using pinned Hermes Agent, "
        "Z.AI GLM Coding Plan, requested model glm-5.3, exact structured completion, and "
        "the prospectively qualified bounded format-regeneration rule; effective upstream "
        "model identity remains unobserved; no capability-reproduction, schema-generalization, "
        "provider/model-generalization, naturalistic, team/swarm/institution, registry, "
        "Acceptance, production-readiness, or Historical Substrate claim"
    )
    result["registry_promotion_authorized"] = False
    result["acceptance_action_authorized"] = False
    result["production_historical_substrate_enabled"] = False
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("provider_output")
    parser.add_argument("--output-dir", default="output/d2-vnext-s2-evaluation")
    parser.add_argument("--plan", default="research/d2_vnext_s2/PLAN.md")
    parser.add_argument("--request-plan", default="research/d2_vnext_s2/D2_VNEXT_S2_REQUEST_PLAN.json")
    parser.add_argument("--schema-suite", default="research/d2_vnext_s2/D2_VNEXT_S2_SCHEMA_SUITE.json")
    parser.add_argument("--sample-size", default="research/d2_vnext_s2/D2_VNEXT_S2_SAMPLE_SIZE.json")
    parser.add_argument(
        "--cohort-lock",
        default="research/d2_vnext_s2/d2-vnext-s2-source-acquisition-cohort-lock.json",
    )
    parser.add_argument("--shard-map", default="research/d2_vnext_s2/D2_VNEXT_S2_SHARD_MAP.json")
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
            "cohort_pairs_sha256": materializer.EXPECTED_COHORT_SHA256,
        }
    )
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    result_path = out / "d2-vnext-s2-source-acquisition-result.json"
    result_path.write_bytes(canonical_bytes(result))
    manifest = {
        "schema": "d2-vnext-s2-source-acquisition-evaluation-manifest-v0.1",
        "study_stream": "D2-vNext-S2",
        "classification": result["classification"],
        "common_confirmed_acquisition_budget": result[
            "common_confirmed_acquisition_budget"
        ],
        "result_sha256": file_sha256(result_path),
        "provider_output_sha256": result["provider_output_sha256"],
        "analyzable_pairs_by_schema": result["analyzable_pairs_by_schema"],
        "transport_integrity_pass": result["transport_integrity"]["passed"],
        "registry_promotion_authorized": False,
        "acceptance_action_authorized": False,
        "production_historical_substrate_enabled": False,
    }
    (out / "evaluation-manifest.json").write_bytes(canonical_bytes(manifest))
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
