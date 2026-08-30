#!/usr/bin/env python3
"""Deterministically aggregate D2-C2 provider shards without classifying them."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

PAIR_COUNT = 360
SHARD_COUNT = 18
EXPECTED_MODEL = "glm-5-turbo"
EXPECTED_TEMPERATURE = 0.8
EXPECTED_COHORT_SHA256 = (
    "8341d573da2d626858d25abfb381c499cc4d3c640749045b0141c985828fc676"
)


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_shard_map(path: Path) -> dict[int, tuple[int, int]]:
    data = json.loads(path.read_text())
    if data.get("schema") != "d2-c2-shard-map-v0.1":
        raise AssertionError("unexpected C2 shard-map schema")
    if data.get("pair_count_attempted") != PAIR_COUNT:
        raise AssertionError("C2 shard-map pair-count mismatch")
    rows = data.get("shards")
    if not isinstance(rows, list) or len(rows) != SHARD_COUNT:
        raise AssertionError("C2 shard-map cardinality mismatch")
    result: dict[int, tuple[int, int]] = {}
    union: list[int] = []
    for row in rows:
        shard_id = int(row["shard"])
        start = int(row["start_pair"])
        end = int(row["end_pair"])
        if shard_id in result:
            raise AssertionError("duplicate shard id in map")
        result[shard_id] = (start, end)
        union.extend(range(start, end + 1))
    if sorted(result) != list(range(SHARD_COUNT)):
        raise AssertionError("C2 shard ids must be 0..17")
    if union != list(range(PAIR_COUNT)):
        raise AssertionError("C2 shard map must cover 0..359 exactly once")
    return result


def _placeholder(pair_index: int, shard_id: int, failure_class: str) -> dict[str, Any]:
    return {
        "status": "failed",
        "pair_index": pair_index,
        "pair_public_id": f"d2-c2-confirmatory-pair-{pair_index:03d}",
        "shard_id": shard_id,
        "failure_class": failure_class,
    }


def _validate_shard(
    data: dict[str, Any],
    *,
    shard_id: int,
    start_pair: int,
    end_pair: int,
    expected_hashes: dict[str, str],
) -> list[str]:
    defects: list[str] = []
    if data.get("schema") != "d2-c2-confirmatory-provider-shard-v0.1":
        defects.append("schema")
    if data.get("status") != "provider_shard_complete_unclassified":
        defects.append("status")
    if data.get("classification") is not None:
        defects.append("shard_must_not_classify")
    if data.get("shard_id") != shard_id:
        defects.append("shard_id")
    if data.get("start_pair") != start_pair or data.get("end_pair") != end_pair:
        defects.append("registered_range")
    expected_n = end_pair - start_pair + 1
    if data.get("attempted_pairs") != expected_n:
        defects.append("attempted_pair_count")
    if data.get("model") != EXPECTED_MODEL:
        defects.append("model_drift")
    if float(data.get("temperature", -1.0)) != EXPECTED_TEMPERATURE:
        defects.append("temperature_drift")
    if data.get("production_historical_substrate_enabled") is not False:
        defects.append("historical_substrate_enabled")

    cohort = data.get("cohort_lock", {})
    if cohort.get("pair_count") != PAIR_COUNT:
        defects.append("cohort_pair_count")
    if cohort.get("cohort_pairs_sha256") != EXPECTED_COHORT_SHA256:
        defects.append("cohort_hash")
    if cohort.get("all_source_destination_overlaps_zero") is not True:
        defects.append("cohort_source_destination_overlap")
    if cohort.get("all_development_evaluation_overlaps_zero") is not True:
        defects.append("cohort_development_evaluation_overlap")

    for key, expected in expected_hashes.items():
        if data.get(key) != expected:
            defects.append(f"{key}_mismatch")

    records = data.get("pair_records")
    expected_indices = list(range(start_pair, end_pair + 1))
    if not isinstance(records, list) or len(records) != expected_n:
        defects.append("pair_record_count")
    else:
        indices = [row.get("pair_index") for row in records]
        if indices != expected_indices:
            defects.append("pair_record_order_or_identity")

    complete = sum(1 for row in records or [] if row.get("status") == "complete")
    failed = sum(1 for row in records or [] if row.get("status") != "complete")
    if data.get("complete_pairs") != complete:
        defects.append("complete_pair_count")
    if data.get("failed_pairs") != failed:
        defects.append("failed_pair_count")
    if complete + failed != expected_n:
        defects.append("pair_count_partition")
    return defects


def aggregate(
    input_dir: Path,
    *,
    plan_path: Path,
    request_plan_path: Path,
    cohort_lock_path: Path,
    shard_map_path: Path,
) -> dict[str, Any]:
    shard_map = load_shard_map(shard_map_path)
    expected_hashes = {
        "plan_sha256": file_sha256(plan_path),
        "request_plan_sha256": file_sha256(request_plan_path),
        "cohort_lock_file_sha256": file_sha256(cohort_lock_path),
        "shard_map_sha256": file_sha256(shard_map_path),
    }

    defects: list[str] = []
    candidates: dict[int, list[tuple[Path, dict[str, Any]]]] = {}
    for path in sorted(input_dir.rglob("d2-c2-confirmatory-provider-shard-*.json")):
        try:
            data = json.loads(path.read_text())
        except Exception:
            defects.append(f"unreadable_shard:{path.name}")
            continue
        shard_id = data.get("shard_id")
        if not isinstance(shard_id, int):
            defects.append(f"missing_shard_id:{path.name}")
            continue
        if shard_id not in shard_map:
            defects.append(f"foreign_shard_id:{shard_id}")
            continue
        candidates.setdefault(shard_id, []).append((path, data))

    pair_records: list[dict[str, Any]] = []
    missing_shards: list[int] = []
    invalid_shards: list[int] = []
    valid_shards: list[int] = []
    transport = {
        "logical_calls_started": 0,
        "logical_calls_completed": 0,
        "logical_call_failures": 0,
        "successful_physical_attempts": 0,
    }

    for shard_id in range(SHARD_COUNT):
        start_pair, end_pair = shard_map[shard_id]
        rows = candidates.get(shard_id, [])
        if not rows:
            missing_shards.append(shard_id)
            pair_records.extend(
                _placeholder(index, shard_id, "missing_shard_artifact")
                for index in range(start_pair, end_pair + 1)
            )
            continue
        if len(rows) != 1:
            defects.append(f"shard_{shard_id}_duplicate_artifacts")
            invalid_shards.append(shard_id)
            pair_records.extend(
                _placeholder(index, shard_id, "invalid_shard_artifact")
                for index in range(start_pair, end_pair + 1)
            )
            continue

        _path, data = rows[0]
        shard_defects = _validate_shard(
            data,
            shard_id=shard_id,
            start_pair=start_pair,
            end_pair=end_pair,
            expected_hashes=expected_hashes,
        )
        if shard_defects:
            defects.extend(
                f"shard_{shard_id}:{defect}" for defect in shard_defects
            )
            invalid_shards.append(shard_id)
            pair_records.extend(
                _placeholder(index, shard_id, "invalid_shard_artifact")
                for index in range(start_pair, end_pair + 1)
            )
            continue

        valid_shards.append(shard_id)
        pair_records.extend(data["pair_records"])
        accounting = data.get("transport_accounting", {})
        for key in transport:
            value = accounting.get(key, 0)
            if isinstance(value, int):
                transport[key] += value
            else:
                defects.append(f"shard_{shard_id}:transport_{key}")

    pair_records.sort(key=lambda row: int(row["pair_index"]))
    if [row["pair_index"] for row in pair_records] != list(range(PAIR_COUNT)):
        defects.append("canonical_pair_identity")

    complete = sum(1 for row in pair_records if row.get("status") == "complete")
    failed = PAIR_COUNT - complete
    defects = sorted(set(defects))
    integrity_passed = not defects

    cohort_lock = json.loads(cohort_lock_path.read_text())
    output = {
        "schema": "d2-c2-confirmatory-provider-output-v0.1",
        "status": "provider_campaign_complete_unclassified",
        "classification": None,
        "model": EXPECTED_MODEL,
        "temperature": EXPECTED_TEMPERATURE,
        "attempted_pairs": PAIR_COUNT,
        "complete_pairs": complete,
        "failed_pairs": failed,
        "cohort_lock": {
            "schema": cohort_lock["schema"],
            "pair_count": PAIR_COUNT,
            "cohort_pairs_sha256": EXPECTED_COHORT_SHA256,
            "all_source_destination_overlaps_zero": True,
            "all_development_evaluation_overlaps_zero": True,
        },
        "pair_records": pair_records,
        "aggregation_integrity": {
            "passed": integrity_passed,
            "defects": defects,
            "valid_shards": valid_shards,
            "missing_shards": missing_shards,
            "invalid_shards": invalid_shards,
        },
        "transport_accounting": transport,
        **expected_hashes,
        "production_historical_substrate_enabled": False,
    }
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input_dir")
    parser.add_argument(
        "--output-dir",
        default="output/d2-c2-confirmatory-aggregated",
    )
    parser.add_argument(
        "--plan",
        default="research/d2/D2_C2_CONFIRMATORY_PLAN.md",
    )
    parser.add_argument(
        "--request-plan",
        default="research/d2/D2_C2_CONFIRMATORY_REQUEST_PLAN.json",
    )
    parser.add_argument(
        "--cohort-lock",
        default="research/d2/d2-c2-confirmatory-cohort-lock.json",
    )
    parser.add_argument(
        "--shard-map",
        default="research/d2/D2_C2_SHARD_MAP.json",
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output = aggregate(
        Path(args.input_dir),
        plan_path=Path(args.plan),
        request_plan_path=Path(args.request_plan),
        cohort_lock_path=Path(args.cohort_lock),
        shard_map_path=Path(args.shard_map),
    )
    output_path = output_dir / "d2-c2-confirmatory-provider-output.json"
    output_path.write_bytes(canonical_bytes(output))
    manifest = {
        "schema": "d2-c2-confirmatory-aggregation-manifest-v0.1",
        "provider_output_sha256": file_sha256(output_path),
        "attempted_pairs": output["attempted_pairs"],
        "complete_pairs": output["complete_pairs"],
        "failed_pairs": output["failed_pairs"],
        "aggregation_integrity": output["aggregation_integrity"],
        "classification": None,
        "production_historical_substrate_enabled": False,
    }
    manifest_path = output_dir / "aggregation-manifest.json"
    manifest_path.write_bytes(canonical_bytes(manifest))
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
