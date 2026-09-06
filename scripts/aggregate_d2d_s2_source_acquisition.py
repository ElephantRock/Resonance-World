#!/usr/bin/env python3
"""Aggregate D2d-S2 provider shards without scientific classification."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import d2d_s2_acquisition_core as core
import materialize_d2d_s2_source_acquisition as materializer

PAIR_COUNT = 384
SHARD_COUNT = 24
EXPECTED_MODEL = "glm-5-turbo"
EXPECTED_TEMPERATURE = 0.8
EXPECTED_COHORT_SHA256 = "d74348dc2d15e2b1c1959726faa9ae473e01a3aeed46bcdc3b1c240e918b3d9f"


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _find_shard(root: Path, shard_id: int) -> Path | None:
    rows = sorted(root.glob(f"**/d2d-s2-provider-shard-{shard_id:02d}.json"))
    if not rows:
        return None
    if len(rows) != 1:
        raise AssertionError(f"multiple D2d-S2 shard outputs for shard {shard_id}")
    return rows[0]


def _failure_rows(shard_id: int, row: dict[str, Any], reason: str) -> list[dict[str, Any]]:
    schema_id = str(row["schema_id"])
    start = int(row["start_pair"])
    end = int(row["end_pair"])
    return [
        {
            "status": "failed",
            "pair_index": pair_index,
            "schema_id": schema_id,
            "schema_pair_index": core.schema_and_local_index(pair_index)[1],
            "pair_public_id": (
                f"d2d-s2-{schema_id}-pair-{core.schema_and_local_index(pair_index)[1]:03d}"
            ),
            "failure_class": reason,
            "registered_shard_id": shard_id,
        }
        for pair_index in range(start, end + 1)
    ]


def aggregate(root: Path, *, shard_map_path: Path) -> dict[str, Any]:
    shard_map = json.loads(shard_map_path.read_text())
    if shard_map != materializer.build_shard_map():
        raise AssertionError("D2d-S2 shard map drift")
    all_records: list[dict[str, Any]] = []
    shard_inputs: list[dict[str, Any]] = []
    for shard_id, expected in enumerate(shard_map["shards"]):
        path = _find_shard(root, shard_id)
        if path is None:
            all_records.extend(_failure_rows(shard_id, expected, "missing_provider_shard"))
            shard_inputs.append({"shard_id": shard_id, "status": "missing", "sha256": None})
            continue
        try:
            payload = json.loads(path.read_text())
            if payload.get("schema") != "d2d-s2-source-acquisition-provider-shard-v0.1":
                raise AssertionError("provider-shard schema mismatch")
            if payload.get("study_stream") != "D2d-S2":
                raise AssertionError("provider-shard stream mismatch")
            if payload.get("status") != "provider_shard_complete_unclassified":
                raise AssertionError("provider-shard status mismatch")
            if payload.get("classification") is not None:
                raise AssertionError("provider shard must be unclassified")
            if int(payload["shard_id"]) != shard_id:
                raise AssertionError("provider shard id mismatch")
            if int(payload["start_pair"]) != int(expected["start_pair"]):
                raise AssertionError("provider shard start mismatch")
            if int(payload["end_pair"]) != int(expected["end_pair"]):
                raise AssertionError("provider shard end mismatch")
            if str(payload["schema_id"]) != str(expected["schema_id"]):
                raise AssertionError("provider shard schema-id mismatch")
            if payload.get("model") != EXPECTED_MODEL:
                raise AssertionError("provider shard model mismatch")
            temperature = payload.get("temperature")
            if isinstance(temperature, bool) or not isinstance(temperature, (int, float)):
                raise AssertionError("provider shard temperature invalid")
            if abs(float(temperature) - EXPECTED_TEMPERATURE) > 1e-12:
                raise AssertionError("provider shard temperature mismatch")
            cohort = payload.get("cohort_lock", {})
            if cohort.get("cohort_pairs_sha256") != EXPECTED_COHORT_SHA256:
                raise AssertionError("provider shard cohort mismatch")
            records = payload.get("pair_records")
            expected_indices = list(
                range(int(expected["start_pair"]), int(expected["end_pair"]) + 1)
            )
            if not isinstance(records, list):
                raise AssertionError("provider shard records missing")
            if [int(record["pair_index"]) for record in records] != expected_indices:
                raise AssertionError("provider shard coverage mismatch")
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
            all_records.extend(_failure_rows(shard_id, expected, "invalid_provider_shard"))
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
        raise AssertionError("canonical D2d-S2 provider coverage mismatch")
    complete = [row for row in all_records if row.get("status") == "complete"]
    failed = [row for row in all_records if row.get("status") != "complete"]
    return {
        "schema": "d2d-s2-source-acquisition-provider-output-v0.1",
        "study_stream": "D2d-S2",
        "status": "provider_campaign_complete_unclassified",
        "classification": None,
        "attempted_pairs": PAIR_COUNT,
        "complete_pairs": len(complete),
        "failed_pairs": len(failed),
        "model": EXPECTED_MODEL,
        "temperature": EXPECTED_TEMPERATURE,
        "cohort_pairs_sha256": EXPECTED_COHORT_SHA256,
        "pair_records": all_records,
        "shard_inputs": shard_inputs,
        "shard_map_sha256": file_sha256(shard_map_path),
        "production_historical_substrate_enabled": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("provider_shards")
    parser.add_argument("--shard-map", default="research/d2d_s2/D2D_S2_SHARD_MAP.json")
    parser.add_argument("--output-dir", default="output/d2d-s2-canonical-provider")
    args = parser.parse_args()
    output = aggregate(Path(args.provider_shards), shard_map_path=Path(args.shard_map))
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    output_path = out / "d2d-s2-provider-output.json"
    output_path.write_bytes(canonical_bytes(output))
    manifest = {
        "schema": "d2d-s2-source-acquisition-provider-output-manifest-v0.1",
        "study_stream": "D2d-S2",
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
