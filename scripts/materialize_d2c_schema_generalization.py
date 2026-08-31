#!/usr/bin/env python3
"""Materialize the deterministic zero-provider D2c schema-generalization cohort."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import d2c_schema_core as core

SOURCE_DEV_COUNT = 40
DEST_DEV_COUNT = 40
EVAL_COUNT = 32
TOTAL_PAIRS = len(core.SCHEMA_ORDER) * core.PAIRS_PER_SCHEMA
SHARD_COUNT = 27
PAIRS_PER_SHARD = 20


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def case_bundle(global_pair_index: int) -> dict[str, Any]:
    schema_id, local_pair_index = core.schema_and_local_index(global_pair_index)
    pair_seed = core.pair_seed_for(schema_id, local_pair_index)
    source_seed = pair_seed + core.SOURCE_OFFSET
    destination_seed = pair_seed + core.DESTINATION_OFFSET
    eval_seed = pair_seed + core.EVALUATION_OFFSET
    policy = core.policy_for(schema_id, pair_seed)
    prefix = f"d2c-{schema_id}-p{local_pair_index:03d}"
    source_cases = core.generate_balanced_cases(
        rng_seed=source_seed,
        count=SOURCE_DEV_COUNT,
        prefix=f"{prefix}-source",
        policy=policy,
    )
    source_features = core.features_set(source_cases)
    destination_cases = core.generate_balanced_cases(
        rng_seed=destination_seed,
        count=DEST_DEV_COUNT,
        prefix=f"{prefix}-destination",
        policy=policy,
        exclude_features=source_features,
    )
    destination_features = core.features_set(destination_cases)
    eval_cases = core.generate_balanced_cases(
        rng_seed=eval_seed,
        count=EVAL_COUNT,
        prefix=f"{prefix}-eval",
        policy=policy,
        exclude_features=source_features | destination_features,
    )
    eval_features = core.features_set(eval_cases)
    return {
        "schema_id": schema_id,
        "local_pair_index": local_pair_index,
        "global_pair_index": global_pair_index,
        "pair_seed": pair_seed,
        "source_seed": source_seed,
        "destination_seed": destination_seed,
        "eval_seed": eval_seed,
        "policy": policy,
        "source_cases": source_cases,
        "destination_cases": destination_cases,
        "eval_cases": eval_cases,
        "source_features": source_features,
        "destination_features": destination_features,
        "eval_features": eval_features,
    }


def pair_lock_record(global_pair_index: int) -> dict[str, Any]:
    bundle = case_bundle(global_pair_index)
    schema_id = bundle["schema_id"]
    local_pair_index = bundle["local_pair_index"]
    return {
        "pair_index": global_pair_index,
        "schema_id": schema_id,
        "schema_pair_index": local_pair_index,
        "pair_public_id": f"d2c-{schema_id}-pair-{local_pair_index:03d}",
        "policy_sha256": core.sha256(bundle["policy"].private_record()),
        "source_cases_sha256": core.sha256(bundle["source_cases"]),
        "destination_cases_sha256": core.sha256(bundle["destination_cases"]),
        "evaluation_holdout_sha256": core.sha256(bundle["eval_cases"]),
        "source_destination_overlap": len(
            bundle["source_features"] & bundle["destination_features"]
        ),
        "development_evaluation_overlap": len(
            (bundle["source_features"] | bundle["destination_features"])
            & bundle["eval_features"]
        ),
    }


def seed_namespace(seed_base: int, pair_count: int) -> set[int]:
    return {
        seed_base + pair_index * core.SEED_STEP + offset
        for pair_index in range(pair_count)
        for offset in (core.SOURCE_OFFSET, core.DESTINATION_OFFSET, core.EVALUATION_OFFSET)
    }


def build_cohort_lock() -> dict[str, Any]:
    records = [pair_lock_record(index) for index in range(TOTAL_PAIRS)]
    if any(
        row["source_destination_overlap"] != 0
        or row["development_evaluation_overlap"] != 0
        for row in records
    ):
        raise AssertionError("D2c cohort overlap integrity failure")

    d2c_namespaces = {
        schema_id: seed_namespace(core.SCHEMA_SEED_BASES[schema_id], core.PAIRS_PER_SCHEMA)
        for schema_id in core.SCHEMA_ORDER
    }
    for i, left in enumerate(core.SCHEMA_ORDER):
        for right in core.SCHEMA_ORDER[i + 1 :]:
            if not d2c_namespaces[left].isdisjoint(d2c_namespaces[right]):
                raise AssertionError(f"D2c cross-schema seed overlap: {left}/{right}")

    predecessor_namespaces = {
        "D2-C1": seed_namespace(1_200_000, 360),
        "D2-C2": seed_namespace(2_200_000, 360),
        "D2b": seed_namespace(3_200_000, 360),
    }
    for schema_id, namespace in d2c_namespaces.items():
        for predecessor, previous in predecessor_namespaces.items():
            if not namespace.isdisjoint(previous):
                raise AssertionError(f"D2c {schema_id} overlaps {predecessor} seed namespace")

    schema_counts = {
        schema_id: sum(row["schema_id"] == schema_id for row in records)
        for schema_id in core.SCHEMA_ORDER
    }
    if any(count != core.PAIRS_PER_SCHEMA for count in schema_counts.values()):
        raise AssertionError("D2c schema pair-count mismatch")

    return {
        "schema": "d2c-schema-generalization-cohort-lock-v0.1",
        "preregistration_issue": 192,
        "pair_count": TOTAL_PAIRS,
        "pairs_per_schema": core.PAIRS_PER_SCHEMA,
        "schema_order": list(core.SCHEMA_ORDER),
        "schema_seed_bases": dict(core.SCHEMA_SEED_BASES),
        "seed_step": core.SEED_STEP,
        "source_offset": core.SOURCE_OFFSET,
        "destination_offset": core.DESTINATION_OFFSET,
        "evaluation_offset": core.EVALUATION_OFFSET,
        "cohort_pairs_sha256": core.sha256(records),
        "schema_pair_counts": schema_counts,
        "all_source_destination_overlaps_zero": True,
        "all_development_evaluation_overlaps_zero": True,
        "cross_schema_seed_overlap": 0,
        "predecessor_seed_namespace_overlap": {
            "D2-C1": 0,
            "D2-C2": 0,
            "D2b": 0
        },
        "pairs": records,
        "production_historical_substrate_enabled": False,
    }


def build_shard_map() -> dict[str, Any]:
    shards: list[dict[str, Any]] = []
    for shard_id in range(SHARD_COUNT):
        start_pair = shard_id * PAIRS_PER_SHARD
        end_pair = start_pair + PAIRS_PER_SHARD - 1
        schema_id, start_local = core.schema_and_local_index(start_pair)
        end_schema, end_local = core.schema_and_local_index(end_pair)
        if schema_id != end_schema:
            raise AssertionError("D2c shard crosses schema boundary")
        shards.append(
            {
                "shard": shard_id,
                "schema_id": schema_id,
                "start_pair": start_pair,
                "end_pair": end_pair,
                "start_schema_pair": start_local,
                "end_schema_pair": end_local,
            }
        )
    union = [index for row in shards for index in range(row["start_pair"], row["end_pair"] + 1)]
    if union != list(range(TOTAL_PAIRS)):
        raise AssertionError("D2c shard map does not cover all pairs exactly once")
    return {
        "schema": "d2c-schema-generalization-shard-map-v0.1",
        "pair_count_attempted": TOTAL_PAIRS,
        "pairs_per_schema": core.PAIRS_PER_SCHEMA,
        "shard_count": SHARD_COUNT,
        "shards_per_schema": 9,
        "pairs_per_shard": PAIRS_PER_SHARD,
        "provider_local_concurrency_per_shard": 1,
        "workflow_matrix_max_parallel": 4,
        "provider_shard_timeout_minutes": 240,
        "shards": shards,
        "production_historical_substrate_enabled": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default="output/d2c-materialized")
    args = parser.parse_args()
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    cohort = build_cohort_lock()
    shard_map = build_shard_map()
    (out / "d2c-schema-cohort-lock.json").write_bytes(canonical_bytes(cohort))
    (out / "D2C_SHARD_MAP.json").write_bytes(canonical_bytes(shard_map))
    summary = {
        "schema": "d2c-schema-generalization-materialization-summary-v0.1",
        "cohort_pairs_sha256": cohort["cohort_pairs_sha256"],
        "pair_count": cohort["pair_count"],
        "pairs_per_schema": cohort["pairs_per_schema"],
        "schema_pair_counts": cohort["schema_pair_counts"],
        "shard_count": shard_map["shard_count"],
        "all_source_destination_overlaps_zero": True,
        "all_development_evaluation_overlaps_zero": True,
        "cross_schema_seed_overlap": 0,
        "predecessor_seed_namespace_overlap": cohort["predecessor_seed_namespace_overlap"],
        "production_historical_substrate_enabled": False,
    }
    (out / "materialization-summary.json").write_bytes(canonical_bytes(summary))
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
