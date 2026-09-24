#!/usr/bin/env python3
# ruff: noqa: E501
"""Deterministically materialize D2-vNext-Q1 Q1-A/Q1-B qualification cohorts."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import d2_vnext_q1_acquisition_core as core

PAIRS_PER_SHARD = 16
SCHEMAS_PER_SHARD = 4
PAIRS_PER_SCHEMA_PER_SHARD = 4
LOGICAL_CALLS_PER_COMPLETE_PAIR = 55
MAX_PHYSICAL_SENDS_PER_LOGICAL_CALL = 36
MAX_PHYSICAL_SENDS_PER_SHARD = 1152
WORKFLOW_MAX_PARALLEL = 4
EXPECTED_COHORT_SHA256: dict[str, str] = {
    core.STAGE_A: "21ae386da6fdba2883a331864fcaffc51f9fa8adb58aa43ee9d68519cadc3686",
    core.STAGE_B: "41124075eeda43439b392997b090ed7fe11275271b4bae86bc619371f86a750e",
}

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
}


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def case_bundle(stage: str, pair_index: int) -> dict[str, Any]:
    schema_id, local_index = core.schema_and_local_index(stage, pair_index)
    pair_seed = core.pair_seed_for(stage, schema_id, local_index)
    policy = core.policy_for(schema_id, pair_seed)
    development_seed = pair_seed + core.DEVELOPMENT_OFFSET
    evaluation_seed = pair_seed + core.EVALUATION_OFFSET
    slug = stage.lower().replace("-", "")
    development_cases = core.generate_balanced_cases(
        rng_seed=development_seed,
        count=core.DEVELOPMENT_MAX_COUNT,
        prefix=f"d2-vnext-{slug}-{schema_id}-p{local_index:03d}-dev",
        policy=policy,
    )
    development_features = core.features_set(development_cases)
    evaluation_cases = core.generate_balanced_cases(
        rng_seed=evaluation_seed,
        count=core.EVALUATION_COUNT,
        prefix=f"d2-vnext-{slug}-{schema_id}-p{local_index:03d}-eval",
        policy=policy,
        exclude_features=development_features,
    )
    if development_features & core.features_set(evaluation_cases):
        raise AssertionError("D2-vNext-Q1 development/evaluation feature overlap")
    return {
        "stage": stage,
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


def pair_lock_record(stage: str, pair_index: int) -> dict[str, Any]:
    bundle = case_bundle(stage, pair_index)
    policy: core.SchemaPolicy = bundle["policy"]
    return {
        "stage": stage,
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


def build_cohort_lock(stage: str) -> dict[str, Any]:
    records = [pair_lock_record(stage, i) for i in range(core.pair_count(stage))]
    seed_rows = [
        (str(row["schema_id"]), int(row[key]))
        for row in records
        for key in ("pair_seed", "development_seed", "evaluation_seed")
    ]
    seeds = [seed for _, seed in seed_rows]
    if len(seeds) != len(set(seeds)):
        raise AssertionError(f"D2-vNext-Q1 {stage} seed collision")
    by_schema = {schema: set() for schema in core.SCHEMA_ORDER}
    for schema, seed in seed_rows:
        by_schema[schema].add(seed)
    cross_schema_overlap = sum(
        len(by_schema[left] & by_schema[right])
        for i, left in enumerate(core.SCHEMA_ORDER)
        for right in core.SCHEMA_ORDER[i + 1 :]
    )
    predecessor = _predecessor_overlap(set(seeds))
    if any(predecessor.values()):
        raise AssertionError(f"D2-vNext-Q1 predecessor seed overlap: {predecessor}")
    cohort_hash = core.sha256(records)
    expected = EXPECTED_COHORT_SHA256[stage]
    if expected and cohort_hash != expected:
        raise AssertionError(f"D2-vNext-Q1 {stage} cohort drift: {cohort_hash}")
    return {
        "schema": "d2-vnext-q1-acquisition-cohort-lock-v0.1",
        "study_stream": "D2-vNext-Q1",
        "stage": stage,
        "fresh_namespace": core.NAMESPACE,
        "pair_count": core.pair_count(stage),
        "pairs_per_schema": core.pairs_per_schema(stage),
        "schema_order": list(core.SCHEMA_ORDER),
        "cohort_pairs_sha256": cohort_hash,
        "cross_schema_seed_overlap": cross_schema_overlap,
        "predecessor_seed_namespace_overlap": predecessor,
        "all_development_evaluation_overlaps_zero": all(r["development_evaluation_feature_overlap"] == 0 for r in records),
        "production_historical_substrate_enabled": False,
    }


def build_shard_map(stage: str) -> dict[str, Any]:
    pair_count = core.pair_count(stage)
    if pair_count % PAIRS_PER_SHARD:
        raise AssertionError("Q1 pair count must divide into 16-pair shards")
    shard_count = pair_count // PAIRS_PER_SHARD
    shards: list[dict[str, Any]] = []
    coverage: list[int] = []
    for shard_id in range(shard_count):
        start = shard_id * PAIRS_PER_SHARD
        indices = list(range(start, start + PAIRS_PER_SHARD))
        schema_counts = {schema: 0 for schema in core.SCHEMA_ORDER}
        for index in indices:
            schema, _ = core.schema_and_local_index(stage, index)
            schema_counts[schema] += 1
        if any(count != PAIRS_PER_SCHEMA_PER_SHARD for count in schema_counts.values()):
            raise AssertionError("Q1 mixed-schema shard balance drift")
        coverage.extend(indices)
        shards.append({
            "shard": shard_id,
            "pair_indices": indices,
            "schema_counts": schema_counts,
            "attempted_pairs": PAIRS_PER_SHARD,
            "maximum_physical_provider_sends": MAX_PHYSICAL_SENDS_PER_SHARD,
        })
    if coverage != list(range(pair_count)):
        raise AssertionError("Q1 shard coverage mismatch")
    return {
        "schema": "d2-vnext-q1-acquisition-shard-map-v0.1",
        "study_stream": "D2-vNext-Q1",
        "stage": stage,
        "fresh_namespace": core.NAMESPACE,
        "pair_count_attempted": pair_count,
        "pairs_per_schema": core.pairs_per_schema(stage),
        "shard_count": shard_count,
        "pairs_per_provider_shard": PAIRS_PER_SHARD,
        "pairs_per_schema_per_shard": PAIRS_PER_SCHEMA_PER_SHARD,
        "mixed_schema_shards": True,
        "provider_local_concurrency_per_shard": 1,
        "workflow_max_parallel": WORKFLOW_MAX_PARALLEL,
        "logical_calls_per_complete_pair": LOGICAL_CALLS_PER_COMPLETE_PAIR,
        "maximum_registered_logical_calls_per_shard": PAIRS_PER_SHARD * LOGICAL_CALLS_PER_COMPLETE_PAIR,
        "maximum_physical_provider_sends_per_logical_call": MAX_PHYSICAL_SENDS_PER_LOGICAL_CALL,
        "maximum_physical_provider_sends_per_shard": MAX_PHYSICAL_SENDS_PER_SHARD,
        "maximum_physical_provider_sends_campaign": shard_count * MAX_PHYSICAL_SENDS_PER_SHARD,
        "shards": shards,
        "production_historical_substrate_enabled": False,
    }


def validate_cross_stage_seed_separation() -> None:
    stage_seeds: dict[str, set[int]] = {}
    for stage in core.STAGES:
        values: set[int] = set()
        for index in range(core.pair_count(stage)):
            row = pair_lock_record(stage, index)
            values.update(int(row[k]) for k in ("pair_seed", "development_seed", "evaluation_seed"))
        stage_seeds[stage] = values
    if stage_seeds[core.STAGE_A] & stage_seeds[core.STAGE_B]:
        raise AssertionError("Q1-A/Q1-B seed overlap")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default="output/d2-vnext-q1-materialization")
    args = parser.parse_args()
    validate_cross_stage_seed_separation()
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    outputs: dict[str, dict[str, Any]] = {}
    for stage, slug in ((core.STAGE_A, "Q1_A"), (core.STAGE_B, "Q1_B")):
        lock = build_cohort_lock(stage)
        shard_map = build_shard_map(stage)
        outputs[f"D2_VNEXT_{slug}_COHORT_LOCK.json"] = lock
        outputs[f"D2_VNEXT_{slug}_SHARD_MAP.json"] = shard_map
    for name, payload in outputs.items():
        (out / name).write_bytes(canonical_bytes(payload))
    manifest = {
        "schema": "d2-vnext-q1-acquisition-materialization-manifest-v0.1",
        "study_stream": "D2-vNext-Q1",
        "fresh_namespace": core.NAMESPACE,
        "q1_a_cohort_pairs_sha256": outputs["D2_VNEXT_Q1_A_COHORT_LOCK.json"]["cohort_pairs_sha256"],
        "q1_b_cohort_pairs_sha256": outputs["D2_VNEXT_Q1_B_COHORT_LOCK.json"]["cohort_pairs_sha256"],
        "files": {name: file_sha256(out / name) for name in sorted(outputs)},
        "provider_calls": 0,
        "provider_execution_authorized": False,
        "production_historical_substrate_enabled": False,
    }
    (out / "materialization-manifest.json").write_bytes(canonical_bytes(manifest))
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
