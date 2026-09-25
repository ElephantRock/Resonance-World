#!/usr/bin/env python3
# ruff: noqa: E501
"""Deterministically materialize the fresh Q3-D3 upstream-boundary cohort."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import d2_vnext_q3d3_diagnostic_core as core

PAIRS_PER_SHARD = 4
SHARD_COUNT = 2
LOGICAL_CALLS_PER_COMPLETE_PAIR = 55
MAX_PHYSICAL_SENDS_PER_LOGICAL_CALL = 36
MAX_PHYSICAL_SENDS_PER_SHARD = 1152
MAX_PHYSICAL_SENDS_CAMPAIGN = SHARD_COUNT * MAX_PHYSICAL_SENDS_PER_SHARD
WORKFLOW_MAX_PARALLEL = 2
EXPECTED_COHORT_SHA256 = "648884eaaf39dda5f37ee03a75ba030308e631ba8b51e536255418efa48af661"

PREDECESSOR_NAMESPACES = {
    "D2-C1": [(1_200_000, 1_299_999)],
    "D2-C2": [(2_200_000, 2_299_999)],
    "D2b": [(3_200_000, 3_299_999)],
    "D2c": [(4_200_000, 4_299_999), (4_400_000, 4_499_999), (4_600_000, 4_699_999)],
    "D2-engineering": [(4_300_000, 4_399_999), (4_500_000, 4_599_999)],
    "D2d": [(5_000_000, 5_699_999)],
    "D2d-S2": [(6_000_000, 6_699_999)],
    "D2-vNext-S1": [(9_000_000, 9_099_999), (9_200_000, 9_299_999), (9_400_000, 9_499_999), (9_600_000, 9_699_999)],
    "D2-vNext-S2": [(10_000_000, 10_099_999), (10_200_000, 10_299_999), (10_400_000, 10_499_999), (10_600_000, 10_699_999)],
    "D2-vNext-Q1": [(11_000_000, 12_699_999)],
    "D2-vNext-Q2": [(13_000_000, 14_699_999)],
    "D2-vNext-Q3-D": [(15_000_000, 15_699_999)],
    "D2-vNext-Q3-D2": [(16_000_000, 16_699_999)],
}


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def case_bundle(pair_index: int) -> dict[str, Any]:
    schema_id, local_index = core.schema_and_local_index(pair_index)
    pair_seed = core.pair_seed_for(local_index)
    policy = core.policy_for(schema_id, pair_seed)
    development_seed = pair_seed + core.DEVELOPMENT_OFFSET
    evaluation_seed = pair_seed + core.EVALUATION_OFFSET
    development_cases = core.generate_balanced_cases(
        rng_seed=development_seed,
        count=core.DEVELOPMENT_MAX_COUNT,
        prefix=f"d2-vnext-q3d3-{schema_id}-p{local_index:03d}-dev",
        policy=policy,
    )
    development_features = core.features_set(development_cases)
    evaluation_cases = core.generate_balanced_cases(
        rng_seed=evaluation_seed,
        count=core.EVALUATION_COUNT,
        prefix=f"d2-vnext-q3d3-{schema_id}-p{local_index:03d}-eval",
        policy=policy,
        exclude_features=development_features,
    )
    if development_features & core.features_set(evaluation_cases):
        raise AssertionError("D2-vNext-Q3-D3 development/evaluation feature overlap")
    return {
        "stage": core.STAGE,
        "pair_index": pair_index,
        "schema_id": schema_id,
        "local_pair_index": local_index,
        "pair_seed": pair_seed,
        "development_seed": development_seed,
        "evaluation_seed": evaluation_seed,
        "policy": policy,
        "development_cases": development_cases,
        "evaluation_cases": evaluation_cases,
    }


def pair_lock_record(pair_index: int) -> dict[str, Any]:
    bundle = case_bundle(pair_index)
    policy: core.SchemaPolicy = bundle["policy"]
    return {
        "stage": core.STAGE,
        "pair_index": pair_index,
        "schema_id": bundle["schema_id"],
        "schema_pair_index": bundle["local_pair_index"],
        "pair_seed": bundle["pair_seed"],
        "development_seed": bundle["development_seed"],
        "evaluation_seed": bundle["evaluation_seed"],
        "private_policy_commitment": core.sha256(policy.private_record()),
        "development_160_case_ids": [c["case_id"] for c in bundle["development_cases"]],
        "development_160_cases_sha256": core.sha256(bundle["development_cases"]),
        "evaluation_case_ids": [c["case_id"] for c in bundle["evaluation_cases"]],
        "evaluation_cases_sha256": core.sha256(bundle["evaluation_cases"]),
        "development_evaluation_feature_overlap": 0,
    }


def _predecessor_overlap(seeds: set[int]) -> dict[str, int]:
    return {
        name: sum(1 for seed in seeds if any(low <= seed <= high for low, high in ranges))
        for name, ranges in PREDECESSOR_NAMESPACES.items()
    }


def build_cohort_lock() -> dict[str, Any]:
    records = [pair_lock_record(i) for i in range(core.PAIR_COUNT)]
    seeds = {
        int(row[key])
        for row in records
        for key in ("pair_seed", "development_seed", "evaluation_seed")
    }
    if len(seeds) != core.PAIR_COUNT * 3:
        raise AssertionError("D2-vNext-Q3-D3 seed collision")
    predecessor = _predecessor_overlap(seeds)
    if any(predecessor.values()):
        raise AssertionError(f"D2-vNext-Q3-D3 predecessor seed overlap: {predecessor}")
    cohort_hash = core.sha256(records)
    if cohort_hash != EXPECTED_COHORT_SHA256:
        raise AssertionError(f"D2-vNext-Q3-D3 cohort drift: {cohort_hash}")
    return {
        "schema": "d2-vnext-q3d3-diagnostic-cohort-lock-v0.1",
        "study_stream": "D2-vNext-Q3-D3",
        "stage": core.STAGE,
        "fresh_namespace": core.NAMESPACE,
        "pair_count": core.PAIR_COUNT,
        "pairs_per_schema": core.PAIR_COUNT,
        "schema_order": list(core.SCHEMA_ORDER),
        "cohort_pairs_sha256": cohort_hash,
        "predecessor_seed_namespace_overlap": predecessor,
        "all_development_evaluation_overlaps_zero": all(
            r["development_evaluation_feature_overlap"] == 0 for r in records
        ),
        "diagnostic_only": True,
        "scientific_effect_sample": False,
        "production_historical_substrate_enabled": False,
    }


def build_shard_map() -> dict[str, Any]:
    shards = []
    coverage = []
    for shard_id in range(SHARD_COUNT):
        start = shard_id * PAIRS_PER_SHARD
        indices = list(range(start, start + PAIRS_PER_SHARD))
        coverage.extend(indices)
        shards.append(
            {
                "shard": shard_id,
                "pair_indices": indices,
                "schema_counts": {core.SCHEMA_ID: PAIRS_PER_SHARD},
                "attempted_pairs": PAIRS_PER_SHARD,
                "maximum_physical_provider_sends": MAX_PHYSICAL_SENDS_PER_SHARD,
            }
        )
    if coverage != list(range(core.PAIR_COUNT)):
        raise AssertionError("D2-vNext-Q3-D3 shard coverage mismatch")
    return {
        "schema": "d2-vnext-q3d3-diagnostic-shard-map-v0.1",
        "study_stream": "D2-vNext-Q3-D3",
        "stage": core.STAGE,
        "fresh_namespace": core.NAMESPACE,
        "pair_count_attempted": core.PAIR_COUNT,
        "pairs_per_schema": core.PAIR_COUNT,
        "schema_id": core.SCHEMA_ID,
        "shard_count": SHARD_COUNT,
        "pairs_per_provider_shard": PAIRS_PER_SHARD,
        "provider_local_concurrency_per_shard": 1,
        "workflow_max_parallel": WORKFLOW_MAX_PARALLEL,
        "logical_calls_per_complete_pair": LOGICAL_CALLS_PER_COMPLETE_PAIR,
        "maximum_registered_logical_calls_per_shard": PAIRS_PER_SHARD * LOGICAL_CALLS_PER_COMPLETE_PAIR,
        "maximum_physical_provider_sends_per_logical_call": MAX_PHYSICAL_SENDS_PER_LOGICAL_CALL,
        "maximum_physical_provider_sends_per_shard": MAX_PHYSICAL_SENDS_PER_SHARD,
        "maximum_physical_provider_sends_campaign": MAX_PHYSICAL_SENDS_CAMPAIGN,
        "budget_borrowing_allowed": False,
        "adaptive_n_allowed": False,
        "failed_pair_replacement_allowed": False,
        "same_stream_rerun_allowed": False,
        "shards": shards,
        "diagnostic_only": True,
        "scientific_effect_sample": False,
        "production_historical_substrate_enabled": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default="output/d2-vnext-q3d3-materialization")
    args = parser.parse_args()
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    cohort = build_cohort_lock()
    shard_map = build_shard_map()
    files = {
        "D2_VNEXT_Q3D3_COHORT_LOCK.json": cohort,
        "D2_VNEXT_Q3D3_SHARD_MAP.json": shard_map,
    }
    for name, payload in files.items():
        (out / name).write_bytes(canonical_bytes(payload))
    manifest = {
        "schema": "d2-vnext-q3d3-materialization-manifest-v0.1",
        "study_stream": "D2-vNext-Q3-D3",
        "fresh_namespace": core.NAMESPACE,
        "cohort_pairs_sha256": cohort["cohort_pairs_sha256"],
        "maximum_physical_provider_sends_campaign": MAX_PHYSICAL_SENDS_CAMPAIGN,
        "files": {name: file_sha256(out / name) for name in sorted(files)},
        "provider_calls": 0,
        "provider_execution_authorized": False,
        "scientific_effect_gates_authorized": False,
        "production_historical_substrate_enabled": False,
    }
    (out / "materialization-manifest.json").write_bytes(canonical_bytes(manifest))
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
