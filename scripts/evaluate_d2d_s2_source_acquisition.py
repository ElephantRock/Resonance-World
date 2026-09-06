#!/usr/bin/env python3
"""Credential-free frozen evaluator for D2d-S2 acquisition calibration."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import d2d_s2_acquisition_core as core
import evaluate_d2d_source_acquisition as base
import materialize_d2d_s2_source_acquisition as materializer

EXPECTED_COHORT_SHA256 = "d74348dc2d15e2b1c1959726faa9ae473e01a3aeed46bcdc3b1c240e918b3d9f"
PRIMARY_ARMS = ("fresh", "developed_40", "developed_80", "developed_160")
BOOTSTRAP_SEEDS = {
    "threshold_at_4": 2026090601,
    "parity_pair": 2026090602,
    "interval_pair": 2026090603,
    "pairwise_order": 2026090604,
}


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@contextmanager
def _fresh_base_context() -> Iterator[None]:
    """Bind the historical evaluator to D2d-S2 only for one evaluation call.

    The historical evaluator exposes its cohort dependencies as module globals. Keeping
    these substitutions scoped prevents importing this module from mutating historical
    D2d behavior elsewhere in the same test or analysis process.
    """

    original = (
        base.core,
        base.materializer,
        base.EXPECTED_COHORT_SHA256,
        base.BOOTSTRAP_SEEDS,
    )
    base.core = core
    base.materializer = materializer
    base.EXPECTED_COHORT_SHA256 = EXPECTED_COHORT_SHA256
    base.BOOTSTRAP_SEEDS = BOOTSTRAP_SEEDS
    try:
        yield
    finally:
        (
            base.core,
            base.materializer,
            base.EXPECTED_COHORT_SHA256,
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
    records = provider.get("pair_records")
    if not isinstance(records, list):
        return [{"scope": "provider", "defect": "pair_records_missing"}]
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
                attempts = call.get("attempt_log")
                call_shape_ok = (
                    call.get("physical_attempts") == 1
                    and isinstance(attempts, list)
                    and len(attempts) == 1
                )
                if not call_shape_ok:
                    defects.append(
                        _defect(pair_index, arm, call_index, "physical_attempt_count")
                    )
                    continue
                attempt = attempts[0]
                if (
                    attempt.get("physical_attempts_initiated") != 1
                    or attempt.get("redirects_followed") != 0
                    or attempt.get("redirect_history_verified") is not True
                    or attempt.get("http_status") != 200
                    or attempt.get("status") != "ok"
                ):
                    defects.append(
                        _defect(pair_index, arm, call_index, "hardened_transport_contract")
                    )
    return defects


def evaluate(provider: dict[str, Any]) -> dict[str, Any]:
    if provider.get("schema") != "d2d-s2-source-acquisition-provider-output-v0.1":
        raise ValueError("D2d-S2 provider schema mismatch")
    if provider.get("study_stream") != "D2d-S2":
        raise ValueError("D2d-S2 provider stream mismatch")
    normalized = copy.deepcopy(provider)
    normalized["schema"] = "d2d-source-acquisition-provider-output-v0.1"
    with _fresh_base_context():
        result = base.evaluate(normalized)
    transport = transport_defects(provider)
    result["schema"] = "d2d-s2-source-acquisition-result-v0.1"
    result["study_stream"] = "D2d-S2"
    result["historical_d2d_replacement_allowed"] = False
    result["transport_integrity"] = {
        "contract": "hardened_general_api_no_redirect_single_attempt_v0.1",
        "passed": not transport,
        "defects": transport,
    }
    if transport:
        result["classification"] = "D2d-S2-A0"
        result["classification_label"] = "acquisition_envelope_transport_integrity_failure"
        result["common_confirmed_acquisition_budget"] = None
        result["integrity"]["passed"] = False
        result["integrity"]["global_defects"].append("d2d_s2_transport_integrity_failure")
        result["positive_control"]["continuity_pass"] = False
    else:
        result["classification"] = result["classification"].replace("D2d-A", "D2d-S2-A")
    result["claim_ceiling"] = (
        "single-model synthetic individual-agent source capability-acquisition calibration "
        "under four frozen D2d-S2 schemas using Z.AI glm-5-turbo over the prospectively "
        "qualified hardened General API transport only; no capability-reproduction, "
        "schema-generalization, provider/model-generalization, naturalistic, team/swarm/"
        "institution, production-readiness, or Historical Substrate claim"
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("provider_output")
    parser.add_argument("--output-dir", default="output/d2d-s2-evaluation")
    parser.add_argument("--plan", default="research/d2d_s2/PLAN.md")
    parser.add_argument("--request-plan", default="research/d2d_s2/D2D_S2_REQUEST_PLAN.json")
    parser.add_argument("--schema-suite", default="research/d2d_s2/D2D_S2_SCHEMA_SUITE.json")
    parser.add_argument("--sample-size", default="research/d2d_s2/D2D_S2_SAMPLE_SIZE.json")
    parser.add_argument(
        "--cohort-lock",
        default="research/d2d_s2/d2d-s2-source-acquisition-cohort-lock.json",
    )
    parser.add_argument("--shard-map", default="research/d2d_s2/D2D_S2_SHARD_MAP.json")
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
    result_path = out / "d2d-s2-source-acquisition-result.json"
    result_path.write_bytes(canonical_bytes(result))
    manifest = {
        "schema": "d2d-s2-source-acquisition-evaluation-manifest-v0.1",
        "study_stream": "D2d-S2",
        "classification": result["classification"],
        "common_confirmed_acquisition_budget": result["common_confirmed_acquisition_budget"],
        "result_sha256": file_sha256(result_path),
        "provider_output_sha256": result["provider_output_sha256"],
        "analyzable_pairs_by_schema": result["analyzable_pairs_by_schema"],
        "transport_integrity_pass": result["transport_integrity"]["passed"],
        "registry_promotion_authorized": False,
        "production_historical_substrate_enabled": False,
    }
    (out / "evaluation-manifest.json").write_bytes(canonical_bytes(manifest))
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
