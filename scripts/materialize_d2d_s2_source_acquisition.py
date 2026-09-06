#!/usr/bin/env python3
"""Deterministically materialize the fresh D2d-S2 cohort and shard topology."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import d2d_s2_acquisition_core as core

PAIR_COUNT = len(core.SCHEMA_ORDER) * core.PAIRS_PER_SCHEMA
SHARD_COUNT = 24
PAIRS_PER_SHARD = 16
MINIMUM_ANALYZABLE_PER_SCHEMA = 88
EXPECTED_COHORT_SHA256 = "d74348dc2d15e2b1c1959726faa9ae473e01a3aeed46bcdc3b1c240e918b3d9f"

PREDECESSOR_NAMESPACES = {
    "D2-C1": [(1_200_000, 1_299_999)],
    "D2-C2": [(2_200_000, 2_299_999)],
    "D2b": [(3_200_000, 3_299_999)],
    "D2c": [(4_200_000, 4_299_999), (4_400_000, 4_499_999), (4_600_000, 4_699_999)],
    "D2d": [(5_000_000, 5_699_999)],
}


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def case_bundle(pair_index: int) -> dict[str, Any]:
    schema_id, local_index = core.schema_and_local_index(pair_index)
    pair_seed = core.pair_seed_for(schema_id, local_index)
    policy = core.policy_for(schema_id, pair_seed)
    development_seed = pair_seed + core.DEVELOPMENT_OFFSET
    evaluation_seed = pair_seed + core.EVALUATION_OFFSET
    development_cases = core.generate_balanced_cases(
        rng_seed=development_seed,
        count=core.DEVELOPMENT_MAX_COUNT,
        prefix=f"d2d-s2-{schema_id}-p{local_index:03d}-dev",
        policy=policy,
    )
    development_features = core.features_set(development_cases)
    evaluation_cases = core.generate_balanced_cases(
        rng_seed=evaluation_seed,
        count=core.EVALUATION_COUNT,
        prefix=f"d2d-s2-{schema_id}-p{local_index:03d}-eval",
        policy=policy,
        exclude_features=development_features,
    )
    if development_features & core.features_set(evaluation_cases):
        raise AssertionError("D2d-S2 development/evaluation feature overlap")
    return {
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
    development_cases = bundle["development_cases"]
    evaluation_cases = bundle["evaluation_cases"]
    return {
        "pair_index": pair_index,
        "schema_id": bundle["schema_id"],
        "schema_pair_index": bundle["local_pair_index"],
        "pair_seed": bundle["pair_seed"],
        "development_seed": bundle["development_seed"],
        "evaluation_seed": bundle["evaluation_seed"],
        "private_policy_commitment": core.sha256(policy.private_record()),
        "development_160_case_ids": [case["case_id"] for case in development_cases],
        "development_160_cases_sha256": core.sha256(development_cases),
        "evaluation_case_ids": [case["case_id"] for case in evaluation_cases],
        "evaluation_cases_sha256": core.sha256(evaluation_cases),
        "development_evaluation_feature_overlap": 0,
    }


def _predecessor_overlap(all_seeds: set[int]) -> dict[str, int]:
    return {
        name: sum(
            1 for seed in all_seeds if any(low <= seed <= high for low, high in ranges)
        )
        for name, ranges in PREDECESSOR_NAMESPACES.items()
    }


def build_cohort_lock() -> dict[str, Any]:
    records = [pair_lock_record(index) for index in range(PAIR_COUNT)]
    seed_rows: list[tuple[str, int]] = []
    for row in records:
        for key in ("pair_seed", "development_seed", "evaluation_seed"):
            seed_rows.append((str(row["schema_id"]), int(row[key])))
    values = [seed for _, seed in seed_rows]
    if len(values) != len(set(values)):
        raise AssertionError("D2d-S2 seed collision")
    by_schema: dict[str, set[int]] = {}
    for schema_id, seed in seed_rows:
        by_schema.setdefault(schema_id, set()).add(seed)
    cross_schema_overlap = 0
    for i, left in enumerate(core.SCHEMA_ORDER):
        for right in core.SCHEMA_ORDER[i + 1 :]:
            cross_schema_overlap += len(by_schema[left] & by_schema[right])
    predecessor = _predecessor_overlap(set(values))
    if any(predecessor.values()):
        raise AssertionError(f"D2d-S2 predecessor seed overlap: {predecessor}")
    cohort_hash = core.sha256(records)
    if cohort_hash != EXPECTED_COHORT_SHA256:
        raise AssertionError(f"D2d-S2 cohort drift: {cohort_hash}")
    return {
        "schema": "d2d-s2-source-acquisition-cohort-lock-v0.1",
        "study_stream": "D2d-S2",
        "pair_count": PAIR_COUNT,
        "pairs_per_schema": core.PAIRS_PER_SCHEMA,
        "schema_order": list(core.SCHEMA_ORDER),
        "cohort_pairs_sha256": cohort_hash,
        "all_development_prefixes_nested": True,
        "all_development_evaluation_overlaps_zero": all(
            row["development_evaluation_feature_overlap"] == 0 for row in records
        ),
        "cross_schema_seed_overlap": cross_schema_overlap,
        "predecessor_seed_namespace_overlap": predecessor,
        "production_historical_substrate_enabled": False,
    }


def build_shard_map() -> dict[str, Any]:
    shards: list[dict[str, Any]] = []
    coverage: list[int] = []
    for shard_id in range(SHARD_COUNT):
        start = shard_id * PAIRS_PER_SHARD
        end = start + PAIRS_PER_SHARD - 1
        schema_id, _ = core.schema_and_local_index(start)
        end_schema, _ = core.schema_and_local_index(end)
        if schema_id != end_schema:
            raise AssertionError("D2d-S2 provider shard crosses schema boundary")
        coverage.extend(range(start, end + 1))
        shards.append(
            {
                "shard": shard_id,
                "schema_id": schema_id,
                "start_pair": start,
                "end_pair": end,
                "attempted_pairs": PAIRS_PER_SHARD,
            }
        )
    if coverage != list(range(PAIR_COUNT)):
        raise AssertionError("D2d-S2 shard map coverage mismatch")
    return {
        "schema": "d2d-s2-source-acquisition-shard-map-v0.1",
        "study_stream": "D2d-S2",
        "pair_count_attempted": PAIR_COUNT,
        "pairs_per_schema": core.PAIRS_PER_SCHEMA,
        "shard_count": SHARD_COUNT,
        "pairs_per_provider_shard": PAIRS_PER_SHARD,
        "provider_local_concurrency_per_shard": 1,
        "workflow_max_parallel": 4,
        "logical_calls_per_complete_pair": 55,
        "logical_calls_before_failures": PAIR_COUNT * 55,
        "maximum_attempts_per_logical_call": 1,
        "minimum_request_interval_seconds": 0.35,
        "missing_whole_shard_max_analyzable_in_affected_schema": (
            core.PAIRS_PER_SCHEMA - PAIRS_PER_SHARD
        ),
        "minimum_analyzable_pairs_per_schema": MINIMUM_ANALYZABLE_PER_SCHEMA,
        "favorable_result_possible_with_missing_whole_shard": False,
        "shards": shards,
        "production_historical_substrate_enabled": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default="output/d2d-s2-materialization")
    args = parser.parse_args()
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    lock = build_cohort_lock()
    shard_map = build_shard_map()
    outputs = {
        "d2d-s2-source-acquisition-cohort-lock.json": lock,
        "D2D_S2_SHARD_MAP.json": shard_map,
    }
    for name, payload in outputs.items():
        (out / name).write_bytes(canonical_bytes(payload))
    manifest = {
        "schema": "d2d-s2-source-acquisition-materialization-manifest-v0.1",
        "study_stream": "D2d-S2",
        "cohort_pairs_sha256": lock["cohort_pairs_sha256"],
        "files": {name: file_sha256(out / name) for name in sorted(outputs)},
        "provider_calls": 0,
        "provider_execution_authorized": False,
        "production_historical_substrate_enabled": False,
    }
    (out / "materialization-manifest.json").write_bytes(canonical_bytes(manifest))
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
