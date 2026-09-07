#!/usr/bin/env python3
"""Credential-free frozen evaluator for D2-vNext-S1 acquisition calibration."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import d2_vnext_s1_acquisition_core as core
import evaluate_d2d_source_acquisition as base
import materialize_d2_vnext_s1_source_acquisition as materializer

EXPECTED_COHORT_SHA256 = "5f650a4c0c8054942781698f77dc918c50c1f3f685f7b9f1e7f1ce7539d4be8c"
EXPECTED_MODEL = "glm-5.3"
EXPECTED_TEMPERATURE = 0.8
MAX_PHYSICAL_SENDS_PER_LOGICAL_CALL = 18
MAX_PHYSICAL_SENDS_CAMPAIGN = 24000
PRIMARY_ARMS = ("fresh", "developed_40", "developed_80", "developed_160")
BOOTSTRAP_SEEDS = {
    "threshold_at_4": 2026090701,
    "parity_pair": 2026090702,
    "interval_pair": 2026090703,
    "pairwise_order": 2026090704,
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
    base.EXPECTED_COHORT_SHA256 = EXPECTED_COHORT_SHA256
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


def _defect(pair_index: int, arm: str, call_index: int, defect: str) -> dict[str, Any]:
    return {
        "pair_index": pair_index,
        "arm": arm,
        "call": call_index,
        "defect": defect,
    }


def transport_defects(provider: dict[str, Any]) -> list[dict[str, Any]]:
    defects: list[dict[str, Any]] = []
    physical_total = provider.get("physical_provider_sends_observed_total")
    if type(physical_total) is not int or not 0 <= physical_total <= MAX_PHYSICAL_SENDS_CAMPAIGN:
        defects.append({"scope": "provider", "defect": "physical_campaign_count_invalid"})
    if provider.get("maximum_physical_provider_sends_campaign") != MAX_PHYSICAL_SENDS_CAMPAIGN:
        defects.append({"scope": "provider", "defect": "physical_campaign_ceiling_drift"})
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
            continue
        for arm in (*PRIMARY_ARMS, "oracle_instruction"):
            payload = arms.get(arm)
            if not isinstance(payload, dict) or payload.get("status") == "failed_diagnostic":
                continue
            calls = payload.get("calls")
            if not isinstance(calls, list):
                defects.append(
                    {"pair_index": pair_index, "arm": arm, "defect": "calls_missing"}
                )
                continue
            for call_index, call in enumerate(calls):
                if not isinstance(call, dict):
                    defects.append(_defect(pair_index, arm, call_index, "call_invalid"))
                    continue
                physical = call.get("physical_attempts")
                attempts = call.get("attempt_log")
                if (
                    type(physical) is not int
                    or not 1 <= physical <= MAX_PHYSICAL_SENDS_PER_LOGICAL_CALL
                    or not isinstance(attempts, list)
                    or len(attempts) != physical
                ):
                    defects.append(
                        _defect(pair_index, arm, call_index, "physical_attempt_count")
                    )
                    continue
                observed_from_complete_calls += physical
                for attempt_index, attempt in enumerate(attempts, start=1):
                    if not isinstance(attempt, dict) or attempt.get("attempt") != attempt_index:
                        defects.append(_defect(pair_index, arm, call_index, "attempt_shape"))
                        break
                else:
                    last = attempts[-1]
                    if last.get("http_status") != 200:
                        defects.append(
                            _defect(pair_index, arm, call_index, "terminal_http_status_not_200")
                        )
    if type(physical_total) is int and observed_from_complete_calls > physical_total:
        defects.append({"scope": "provider", "defect": "complete_call_sends_exceed_total"})
    return defects


def evaluate(provider: dict[str, Any]) -> dict[str, Any]:
    if provider.get("schema") != "d2-vnext-s1-source-acquisition-provider-output-v0.1":
        raise ValueError("D2-vNext-S1 provider schema mismatch")
    if provider.get("study_stream") != "D2-vNext-S1":
        raise ValueError("D2-vNext-S1 provider stream mismatch")
    normalized = copy.deepcopy(provider)
    normalized["schema"] = "d2d-source-acquisition-provider-output-v0.1"
    normalized["model"] = provider.get("requested_model")
    with _fresh_base_context():
        result = base.evaluate(normalized)
    transport = transport_defects(provider)
    result["schema"] = "d2-vnext-s1-source-acquisition-result-v0.1"
    result["study_stream"] = "D2-vNext-S1"
    result["requested_model"] = EXPECTED_MODEL
    result["effective_model_identity_observed"] = False
    result["effective_model_identity_claim"] = "unobserved_at_supported_product_boundary"
    result["historical_d2d_replacement_allowed"] = False
    result["historical_d2d_s2_replacement_allowed"] = False
    result["transport_integrity"] = {
        "contract": "pinned_hermes_coding_plan_fail_closed_physical_send_guard_v0.1",
        "passed": not transport,
        "defects": transport,
        "maximum_physical_provider_sends_per_logical_call": (
            MAX_PHYSICAL_SENDS_PER_LOGICAL_CALL
        ),
        "maximum_physical_provider_sends_campaign": MAX_PHYSICAL_SENDS_CAMPAIGN,
        "observed_physical_provider_sends": provider.get(
            "physical_provider_sends_observed_total"
        ),
    }
    if transport:
        result["classification"] = "D2-vNext-S1-A0"
        result["classification_label"] = "acquisition_envelope_transport_integrity_failure"
        result["common_confirmed_acquisition_budget"] = None
        result["integrity"]["passed"] = False
        result["integrity"]["global_defects"].append(
            "d2_vnext_s1_transport_integrity_failure"
        )
        result["positive_control"]["continuity_pass"] = False
    else:
        result["classification"] = result["classification"].replace(
            "D2d-A", "D2-vNext-S1-A"
        )
    result["claim_ceiling"] = (
        "single supported-product synthetic individual-agent source capability-acquisition "
        "calibration under four frozen D2-vNext-S1 schemas using pinned Hermes Agent, "
        "Z.AI GLM Coding Plan, and requested model glm-5.3 with effective upstream model "
        "identity unobserved; no capability-reproduction, schema-generalization, "
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
    parser.add_argument("--output-dir", default="output/d2-vnext-s1-evaluation")
    parser.add_argument("--plan", default="research/d2_vnext_s1/PLAN.md")
    parser.add_argument("--request-plan", default="research/d2_vnext_s1/D2_VNEXT_S1_REQUEST_PLAN.json")
    parser.add_argument("--schema-suite", default="research/d2_vnext_s1/D2_VNEXT_S1_SCHEMA_SUITE.json")
    parser.add_argument("--sample-size", default="research/d2_vnext_s1/D2_VNEXT_S1_SAMPLE_SIZE.json")
    parser.add_argument(
        "--cohort-lock",
        default="research/d2_vnext_s1/d2-vnext-s1-source-acquisition-cohort-lock.json",
    )
    parser.add_argument("--shard-map", default="research/d2_vnext_s1/D2_VNEXT_S1_SHARD_MAP.json")
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
    result_path = out / "d2-vnext-s1-source-acquisition-result.json"
    result_path.write_bytes(canonical_bytes(result))
    manifest = {
        "schema": "d2-vnext-s1-source-acquisition-evaluation-manifest-v0.1",
        "study_stream": "D2-vNext-S1",
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
