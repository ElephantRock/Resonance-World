#!/usr/bin/env python3
"""Aggregate registered D2d provider shards without scientific classification."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import d2d_acquisition_core as core

PAIR_COUNT = 384
SHARD_COUNT = 24
EXPECTED_COHORT_SHA256 = "a9c2077d4e76825d9ef1f6b245caf0231f5a4a3b1dc00cc0032793add8f9ea19"


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_shard_map(path: Path) -> dict[int, tuple[int, int, str]]:
    shard_map = json.loads(path.read_text())
    if shard_map.get("schema") != "d2d-source-acquisition-shard-map-v0.1":
        raise AssertionError("unexpected D2d shard map")
    rows = shard_map.get("shards")
    if not isinstance(rows, list) or len(rows) != SHARD_COUNT:
        raise AssertionError("D2d shard-count mismatch")
    result: dict[int, tuple[int, int, str]] = {}
    coverage: list[int] = []
    for row in rows:
        shard_id = int(row["shard"])
        start = int(row["start_pair"])
        end = int(row["end_pair"])
        schema_id = str(row["schema_id"])
        result[shard_id] = (start, end, schema_id)
        coverage.extend(range(start, end + 1))
    if coverage != list(range(PAIR_COUNT)):
        raise AssertionError("D2d shard map coverage mismatch")
    return result


def _find_shard(root: Path, shard_id: int) -> Path | None:
    candidates = sorted(root.glob(f"**/d2d-provider-shard-{shard_id:02d}.json"))
    if not candidates:
        return None
    if len(candidates) != 1:
        raise AssertionError(f"multiple D2d shard outputs for shard {shard_id}")
    return candidates[0]


def _failure_rows(
    shard_id: int, start: int, end: int, schema_id: str, reason: str
) -> list[dict[str, Any]]:
    return [
        {
            "status": "failed",
            "pair_index": pair_index,
            "schema_id": schema_id,
            "schema_pair_index": core.schema_and_local_index(pair_index)[1],
            "pair_public_id": (
                f"d2d-{schema_id}-pair-"
                f"{core.schema_and_local_index(pair_index)[1]:03d}"
            ),
            "failure_class": reason,
            "registered_shard_id": shard_id,
        }
        for pair_index in range(start, end + 1)
    ]


def aggregate(root: Path, *, shard_map_path: Path) -> dict[str, Any]:
    mapping = load_shard_map(shard_map_path)
    all_records: list[dict[str, Any]] = []
    shard_inputs: list[dict[str, Any]] = []
    for shard_id in range(SHARD_COUNT):
        start, end, schema_id = mapping[shard_id]
        path = _find_shard(root, shard_id)
        if path is None:
            all_records.extend(
                _failure_rows(shard_id, start, end, schema_id, "missing_provider_shard")
            )
            shard_inputs.append({"shard_id": shard_id, "status": "missing", "sha256": None})
            continue
        try:
            payload = json.loads(path.read_text())
            if payload.get("schema") != "d2d-source-acquisition-provider-shard-v0.1":
                raise AssertionError("provider-shard schema mismatch")
            if payload.get("status") != "provider_shard_complete_unclassified":
                raise AssertionError("provider-shard status mismatch")
            if payload.get("classification") is not None:
                raise AssertionError("provider shard must be unclassified")
            if int(payload["shard_id"]) != shard_id:
                raise AssertionError("provider shard id mismatch")
            if int(payload["start_pair"]) != start or int(payload["end_pair"]) != end:
                raise AssertionError("provider shard range mismatch")
            if str(payload["schema_id"]) != schema_id:
                raise AssertionError("provider shard schema-id mismatch")
            cohort = payload.get("cohort_lock", {})
            if cohort.get("cohort_pairs_sha256") != EXPECTED_COHORT_SHA256:
                raise AssertionError("provider shard cohort hash mismatch")
            records = payload.get("pair_records")
            expected = list(range(start, end + 1))
            if not isinstance(records, list):
                raise AssertionError("provider shard pair records missing")
            if [int(record["pair_index"]) for record in records] != expected:
                raise AssertionError("provider shard pair coverage mismatch")
            if payload.get("production_historical_substrate_enabled") is not False:
                raise AssertionError("Historical Substrate drift")
            all_records.extend(records)
            shard_inputs.append(
                {"shard_id": shard_id, "status": "loaded", "sha256": file_sha256(path)}
            )
        except Exception as exc:
            fingerprint = hashlib.sha256(
                f"{type(exc).__name__}:{str(exc)[:500]}".encode()
            ).hexdigest()
            all_records.extend(
                _failure_rows(shard_id, start, end, schema_id, "invalid_provider_shard")
            )
            shard_inputs.append(
                {
                    "shard_id": shard_id,
                    "status": "invalid",
                    "sha256": file_sha256(path),
                    "error_sha256": fingerprint,
                }
            )
    all_records.sort(key=lambda row: int(row["pair_index"]))
    if [int(row["pair_index"]) for row in all_records] != list(range(PAIR_COUNT)):
        raise AssertionError("canonical D2d provider output coverage mismatch")
    complete = [row for row in all_records if row.get("status") == "complete"]
    failed = [row for row in all_records if row.get("status") != "complete"]
    return {
        "schema": "d2d-source-acquisition-provider-output-v0.1",
        "status": "provider_campaign_complete_unclassified",
        "classification": None,
        "attempted_pairs": PAIR_COUNT,
        "complete_pairs": len(complete),
        "failed_pairs": len(failed),
        "cohort_pairs_sha256": EXPECTED_COHORT_SHA256,
        "pair_records": all_records,
        "shard_inputs": shard_inputs,
        "shard_map_sha256": file_sha256(shard_map_path),
        "production_historical_substrate_enabled": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("provider_shards")
    parser.add_argument("--shard-map", default="research/d2d/D2D_SHARD_MAP.json")
    parser.add_argument("--output-dir", default="output/d2d-canonical-provider")
    args = parser.parse_args()
    output = aggregate(Path(args.provider_shards), shard_map_path=Path(args.shard_map))
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    output_path = out / "d2d-provider-output.json"
    output_path.write_bytes(canonical_bytes(output))
    manifest = {
        "schema": "d2d-source-acquisition-provider-output-manifest-v0.1",
        "provider_output_sha256": file_sha256(output_path),
        "attempted_pairs": PAIR_COUNT,
        "complete_pairs": output["complete_pairs"],
        "failed_pairs": output["failed_pairs"],
        "cohort_pairs_sha256": EXPECTED_COHORT_SHA256,
        "classification": None,
        "production_historical_substrate_enabled": False,
    }
    (out / "provider-output-manifest.json").write_bytes(canonical_bytes(manifest))
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
