#!/usr/bin/env python3
"""Materialize the zero-provider D2b replication cohort and shard locks."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import run_d2_c2_confirmatory as c2

PAIR_COUNT = 360
SEED_BASE = 3_200_000
SEED_STEP = 100
SOURCE_OFFSET = 1
DESTINATION_OFFSET = 2
EVALUATION_OFFSET = 3
SOURCE_DEV_COUNT = 40
DEST_DEV_COUNT = 40
EVAL_COUNT = 32
SHARD_COUNT = 18
PAIRS_PER_SHARD = 20


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def case_bundle(pair_index: int) -> dict[str, Any]:
    pair_seed = SEED_BASE + pair_index * SEED_STEP
    source_seed = pair_seed + SOURCE_OFFSET
    destination_seed = pair_seed + DESTINATION_OFFSET
    eval_seed = pair_seed + EVALUATION_OFFSET
    policy = c2.policy_for(pair_seed)
    source_cases = c2.generate_balanced_cases(
        rng_seed=source_seed,
        count=SOURCE_DEV_COUNT,
        prefix=f"d2b-source-p{pair_index:03d}",
        policy=policy,
    )
    source_features = c2.features_set(source_cases)
    destination_cases = c2.generate_balanced_cases(
        rng_seed=destination_seed,
        count=DEST_DEV_COUNT,
        prefix=f"d2b-destination-p{pair_index:03d}",
        policy=policy,
        exclude_features=source_features,
    )
    destination_features = c2.features_set(destination_cases)
    eval_cases = c2.generate_balanced_cases(
        rng_seed=eval_seed,
        count=EVAL_COUNT,
        prefix=f"d2b-eval-p{pair_index:03d}",
        policy=policy,
        exclude_features=source_features | destination_features,
    )
    eval_features = c2.features_set(eval_cases)
    return {
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


def pair_lock_record(pair_index: int) -> dict[str, Any]:
    bundle = case_bundle(pair_index)
    return {
        "pair_index": pair_index,
        "pair_public_id": f"d2b-replication-pair-{pair_index:03d}",
        "policy_sha256": c2.sha256(bundle["policy"].private_record()),
        "source_cases_sha256": c2.sha256(bundle["source_cases"]),
        "destination_cases_sha256": c2.sha256(bundle["destination_cases"]),
        "evaluation_holdout_sha256": c2.sha256(bundle["eval_cases"]),
        "source_destination_overlap": len(
            bundle["source_features"] & bundle["destination_features"]
        ),
        "development_evaluation_overlap": len(
            (bundle["source_features"] | bundle["destination_features"])
            & bundle["eval_features"]
        ),
    }


def seed_namespace(seed_base: int) -> set[int]:
    return {
        seed_base + pair_index * SEED_STEP + offset
        for pair_index in range(PAIR_COUNT)
        for offset in (SOURCE_OFFSET, DESTINATION_OFFSET, EVALUATION_OFFSET)
    }


def build_cohort_lock() -> dict[str, Any]:
    records = [pair_lock_record(index) for index in range(PAIR_COUNT)]
    if any(
        row["source_destination_overlap"] != 0
        or row["development_evaluation_overlap"] != 0
        for row in records
    ):
        raise AssertionError("D2b cohort overlap integrity failure")
    d2b = seed_namespace(SEED_BASE)
    if not d2b.isdisjoint(seed_namespace(1_200_000)):
        raise AssertionError("D2b seed namespace overlaps D2-C1")
    if not d2b.isdisjoint(seed_namespace(2_200_000)):
        raise AssertionError("D2b seed namespace overlaps D2-C2")
    return {
        "schema": "d2b-replication-cohort-lock-v0.1",
        "parent_study": "D2-C2",
        "preregistration_issue": 186,
        "pair_count": PAIR_COUNT,
        "seed_series": {
            "base": SEED_BASE,
            "step": SEED_STEP,
            "source_offset": SOURCE_OFFSET,
            "destination_offset": DESTINATION_OFFSET,
            "evaluation_offset": EVALUATION_OFFSET,
        },
        "case_prefixes": {
            "source": "d2b-source-p{pair_index:03d}",
            "destination": "d2b-destination-p{pair_index:03d}",
            "evaluation": "d2b-eval-p{pair_index:03d}",
        },
        "cohort_pairs_sha256": c2.sha256(records),
        "all_source_destination_overlaps_zero": True,
        "all_development_evaluation_overlaps_zero": True,
        "c1_seed_namespace_overlap": 0,
        "c2_seed_namespace_overlap": 0,
        "pairs": records,
        "production_historical_substrate_enabled": False,
    }


def build_shard_map() -> dict[str, Any]:
    shards = []
    for shard in range(SHARD_COUNT):
        start = shard * PAIRS_PER_SHARD
        end = start + PAIRS_PER_SHARD - 1
        shards.append({"shard": shard, "start_pair": start, "end_pair": end})
    union = [index for row in shards for index in range(row["start_pair"], row["end_pair"] + 1)]
    if union != list(range(PAIR_COUNT)):
        raise AssertionError("D2b shard map does not cover 0..359 exactly once")
    return {
        "schema": "d2b-replication-shard-map-v0.1",
        "pair_count_attempted": PAIR_COUNT,
        "shard_count": SHARD_COUNT,
        "pairs_per_shard": PAIRS_PER_SHARD,
        "provider_local_concurrency_per_shard": 1,
        "workflow_matrix_max_parallel": 4,
        "provider_shard_timeout_minutes": 240,
        "shards": shards,
        "production_historical_substrate_enabled": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default="output/d2b-materialized")
    args = parser.parse_args()
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    cohort = build_cohort_lock()
    shard_map = build_shard_map()
    (out / "d2b-replication-cohort-lock.json").write_bytes(canonical_bytes(cohort))
    (out / "D2B_SHARD_MAP.json").write_bytes(canonical_bytes(shard_map))
    summary = {
        "schema": "d2b-materialization-summary-v0.1",
        "cohort_pairs_sha256": cohort["cohort_pairs_sha256"],
        "pair_count": cohort["pair_count"],
        "shard_count": shard_map["shard_count"],
        "all_source_destination_overlaps_zero": True,
        "all_development_evaluation_overlaps_zero": True,
        "c1_seed_namespace_overlap": 0,
        "c2_seed_namespace_overlap": 0,
        "production_historical_substrate_enabled": False,
    }
    (out / "materialization-summary.json").write_bytes(canonical_bytes(summary))
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
