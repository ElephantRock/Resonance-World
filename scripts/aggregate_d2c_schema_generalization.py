#!/usr/bin/env python3
"""Aggregate D2c provider shards deterministically without scientific classification."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import d2c_schema_core as core

PAIR_COUNT = 540
SHARD_COUNT = 27
EXPECTED_MODEL = "glm-5-turbo"
EXPECTED_TEMPERATURE = 0.8
EXPECTED_COHORT_SHA256 = "559a4420a1d592d85fa350d087a8d4b945f4bf882a683c660a77cf9fdb6b9c04"


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_shard_map(path: Path) -> dict[int, tuple[int, int, str]]:
    data = json.loads(path.read_text())
    if data.get("schema") != "d2c-schema-generalization-shard-map-v0.1":
        raise AssertionError("unexpected D2c shard-map schema")
    rows = data.get("shards")
    if data.get("pair_count_attempted") != PAIR_COUNT or not isinstance(rows, list) or len(rows) != SHARD_COUNT:
        raise AssertionError("D2c shard-map cardinality mismatch")
    result: dict[int, tuple[int, int, str]] = {}
    union: list[int] = []
    for row in rows:
        shard_id = int(row["shard"])
        start = int(row["start_pair"])
        end = int(row["end_pair"])
        schema_id = str(row["schema_id"])
        if shard_id in result or schema_id not in core.SCHEMA_ORDER:
            raise AssertionError("invalid D2c shard row")
        if core.schema_and_local_index(start)[0] != schema_id or core.schema_and_local_index(end)[0] != schema_id:
            raise AssertionError("D2c shard crosses schema boundary")
        result[shard_id] = (start, end, schema_id)
        union.extend(range(start, end + 1))
    if sorted(result) != list(range(SHARD_COUNT)) or union != list(range(PAIR_COUNT)):
        raise AssertionError("D2c shard coverage mismatch")
    return result


def _placeholder(pair_index: int, shard_id: int, failure_class: str) -> dict[str, Any]:
    schema_id, local_index = core.schema_and_local_index(pair_index)
    return {
        "status": "failed",
        "pair_index": pair_index,
        "schema_id": schema_id,
        "schema_pair_index": local_index,
        "pair_public_id": f"d2c-{schema_id}-pair-{local_index:03d}",
        "shard_id": shard_id,
        "failure_class": failure_class,
    }


def _validate_shard(
    data: dict[str, Any], *, shard_id: int, start_pair: int, end_pair: int,
    schema_id: str, expected_hashes: dict[str, str]
) -> list[str]:
    defects: list[str] = []
    if data.get("schema") != "d2c-schema-generalization-provider-shard-v0.1": defects.append("schema")
    if data.get("status") != "provider_shard_complete_unclassified": defects.append("status")
    if data.get("classification") is not None: defects.append("shard_must_not_classify")
    if data.get("shard_id") != shard_id: defects.append("shard_id")
    if data.get("schema_id") != schema_id: defects.append("schema_id")
    if data.get("start_pair") != start_pair or data.get("end_pair") != end_pair: defects.append("range")
    expected_n = end_pair - start_pair + 1
    if data.get("attempted_pairs") != expected_n: defects.append("attempted_pairs")
    if data.get("model") != EXPECTED_MODEL: defects.append("model_drift")
    if float(data.get("temperature", -1)) != EXPECTED_TEMPERATURE: defects.append("temperature_drift")
    if data.get("production_historical_substrate_enabled") is not False: defects.append("historical_substrate")
    cohort = data.get("cohort_lock", {})
    if cohort.get("pair_count") != PAIR_COUNT: defects.append("cohort_pair_count")
    if cohort.get("cohort_pairs_sha256") != EXPECTED_COHORT_SHA256: defects.append("cohort_hash")
    if cohort.get("all_source_destination_overlaps_zero") is not True: defects.append("source_destination_overlap")
    if cohort.get("all_development_evaluation_overlaps_zero") is not True: defects.append("development_evaluation_overlap")
    for key, expected in expected_hashes.items():
        if data.get(key) != expected: defects.append(f"{key}_mismatch")
    records = data.get("pair_records")
    expected_indices = list(range(start_pair, end_pair + 1))
    if not isinstance(records, list) or len(records) != expected_n:
        defects.append("pair_record_count")
    else:
        if [row.get("pair_index") for row in records] != expected_indices: defects.append("pair_record_identity")
        if any(row.get("schema_id") != schema_id for row in records): defects.append("pair_record_schema")
    complete = sum(1 for row in records or [] if row.get("status") == "complete")
    failed = sum(1 for row in records or [] if row.get("status") != "complete")
    if data.get("complete_pairs") != complete: defects.append("complete_pair_count")
    if data.get("failed_pairs") != failed: defects.append("failed_pair_count")
    if complete + failed != expected_n: defects.append("pair_partition")
    return defects


def aggregate(
    input_dir: Path, *, plan_path: Path, request_plan_path: Path, schema_suite_path: Path,
    sample_size_path: Path, cohort_lock_path: Path, shard_map_path: Path
) -> dict[str, Any]:
    shard_map = load_shard_map(shard_map_path)
    expected_hashes = {
        "plan_sha256": file_sha256(plan_path),
        "request_plan_sha256": file_sha256(request_plan_path),
        "schema_suite_sha256": file_sha256(schema_suite_path),
        "sample_size_sha256": file_sha256(sample_size_path),
        "cohort_lock_file_sha256": file_sha256(cohort_lock_path),
        "shard_map_sha256": file_sha256(shard_map_path),
    }
    defects: list[str] = []
    candidates: dict[int, list[tuple[Path, dict[str, Any]]]] = {}
    for path in sorted(input_dir.rglob("d2c-provider-shard-*.json")):
        if path.name.endswith("-manifest.json"):
            continue
        try:
            data = json.loads(path.read_text())
        except Exception:
            defects.append(f"unreadable_shard:{path.name}")
            continue
        shard_id = data.get("shard_id")
        if not isinstance(shard_id, int) or shard_id not in shard_map:
            defects.append(f"foreign_or_missing_shard_id:{path.name}")
            continue
        candidates.setdefault(shard_id, []).append((path, data))

    pair_records: list[dict[str, Any]] = []
    missing_shards: list[int] = []
    invalid_shards: list[int] = []
    valid_shards: list[int] = []
    transport = {"logical_calls_started": 0, "logical_calls_completed": 0, "logical_call_failures": 0, "successful_physical_attempts": 0}
    for shard_id in range(SHARD_COUNT):
        start, end, schema_id = shard_map[shard_id]
        rows = candidates.get(shard_id, [])
        if not rows:
            missing_shards.append(shard_id)
            pair_records.extend(_placeholder(i, shard_id, "missing_shard_artifact") for i in range(start, end + 1))
            continue
        if len(rows) != 1:
            defects.append(f"shard_{shard_id}:duplicate_artifacts")
            invalid_shards.append(shard_id)
            pair_records.extend(_placeholder(i, shard_id, "invalid_shard_artifact") for i in range(start, end + 1))
            continue
        _path, data = rows[0]
        shard_defects = _validate_shard(data, shard_id=shard_id, start_pair=start, end_pair=end, schema_id=schema_id, expected_hashes=expected_hashes)
        if shard_defects:
            defects.extend(f"shard_{shard_id}:{d}" for d in shard_defects)
            invalid_shards.append(shard_id)
            pair_records.extend(_placeholder(i, shard_id, "invalid_shard_artifact") for i in range(start, end + 1))
            continue
        valid_shards.append(shard_id)
        pair_records.extend(data["pair_records"])
        accounting = data.get("transport_accounting", {})
        for key in transport:
            value = accounting.get(key, 0)
            if isinstance(value, int): transport[key] += value
            else: defects.append(f"shard_{shard_id}:transport_{key}")

    pair_records.sort(key=lambda row: int(row["pair_index"]))
    if [row.get("pair_index") for row in pair_records] != list(range(PAIR_COUNT)):
        defects.append("canonical_pair_identity")
    complete = sum(row.get("status") == "complete" for row in pair_records)
    schema_counts = {
        schema_id: {
            "attempted": sum(row.get("schema_id") == schema_id for row in pair_records),
            "complete": sum(row.get("schema_id") == schema_id and row.get("status") == "complete" for row in pair_records),
        }
        for schema_id in core.SCHEMA_ORDER
    }
    defects = sorted(set(defects))
    lock = json.loads(cohort_lock_path.read_text())
    return {
        "schema": "d2c-schema-generalization-provider-output-v0.1",
        "status": "provider_campaign_complete_unclassified",
        "classification": None,
        "model": EXPECTED_MODEL,
        "temperature": EXPECTED_TEMPERATURE,
        "attempted_pairs": PAIR_COUNT,
        "complete_pairs": complete,
        "failed_pairs": PAIR_COUNT - complete,
        "schema_counts": schema_counts,
        "cohort_lock": {
            "schema": lock["schema"],
            "pair_count": PAIR_COUNT,
            "pairs_per_schema": 180,
            "cohort_pairs_sha256": EXPECTED_COHORT_SHA256,
            "all_source_destination_overlaps_zero": True,
            "all_development_evaluation_overlaps_zero": True,
        },
        "pair_records": pair_records,
        "aggregation_integrity": {
            "passed": not defects,
            "defects": defects,
            "valid_shards": valid_shards,
            "missing_shards": missing_shards,
            "invalid_shards": invalid_shards,
        },
        "transport_accounting": transport,
        **expected_hashes,
        "production_historical_substrate_enabled": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input_dir")
    parser.add_argument("--output-dir", default="output/d2c-aggregated")
    parser.add_argument("--plan", default="research/d2c/PLAN.md")
    parser.add_argument("--request-plan", default="research/d2c/D2C_REQUEST_PLAN.json")
    parser.add_argument("--schema-suite", default="research/d2c/D2C_SCHEMA_SUITE.json")
    parser.add_argument("--sample-size", default="research/d2c/D2C_SAMPLE_SIZE.json")
    parser.add_argument("--cohort-lock", default="research/d2c/d2c-schema-cohort-lock.json")
    parser.add_argument("--shard-map", default="research/d2c/D2C_SHARD_MAP.json")
    args = parser.parse_args()
    out_dir = Path(args.output_dir); out_dir.mkdir(parents=True, exist_ok=True)
    output = aggregate(Path(args.input_dir), plan_path=Path(args.plan), request_plan_path=Path(args.request_plan), schema_suite_path=Path(args.schema_suite), sample_size_path=Path(args.sample_size), cohort_lock_path=Path(args.cohort_lock), shard_map_path=Path(args.shard_map))
    output_path = out_dir / "d2c-provider-output.json"
    output_path.write_bytes(canonical_bytes(output))
    manifest = {
        "schema": "d2c-schema-generalization-aggregation-manifest-v0.1",
        "provider_output_sha256": file_sha256(output_path),
        "attempted_pairs": output["attempted_pairs"],
        "complete_pairs": output["complete_pairs"],
        "failed_pairs": output["failed_pairs"],
        "schema_counts": output["schema_counts"],
        "aggregation_integrity": output["aggregation_integrity"],
        "classification": None,
        "production_historical_substrate_enabled": False,
    }
    (out_dir / "aggregation-manifest.json").write_bytes(canonical_bytes(manifest))
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
