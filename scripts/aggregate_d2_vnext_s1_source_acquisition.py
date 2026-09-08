#!/usr/bin/env python3
"""Aggregate D2-vNext-S1 provider shards without scientific classification."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import d2_vnext_s1_acquisition_core as core
import materialize_d2_vnext_s1_source_acquisition as materializer

PAIR_COUNT = 384
SHARD_COUNT = 24
EXPECTED_MODEL = "glm-5.3"
EXPECTED_TEMPERATURE = 0.8
EXPECTED_COHORT_SHA256 = "5f650a4c0c8054942781698f77dc918c50c1f3f685f7b9f1e7f1ce7539d4be8c"
MAX_PHYSICAL_SENDS_PER_SHARD = 1000
MAX_PHYSICAL_SENDS_CAMPAIGN = 24000


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _find_shard(root: Path, shard_id: int) -> Path | None:
    rows = sorted(root.glob(f"**/d2-vnext-s1-provider-shard-{shard_id:02d}.json"))
    if not rows:
        return None
    if len(rows) != 1:
        raise AssertionError(f"multiple D2-vNext-S1 outputs for shard {shard_id}")
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
                f"d2-vnext-s1-{schema_id}-pair-"
                f"{core.schema_and_local_index(pair_index)[1]:03d}"
            ),
            "failure_class": reason,
            "registered_shard_id": shard_id,
        }
        for pair_index in range(start, end + 1)
    ]


def aggregate(root: Path, *, shard_map_path: Path) -> dict[str, Any]:
    shard_map = json.loads(shard_map_path.read_text())
    if shard_map != materializer.build_shard_map():
        raise AssertionError("D2-vNext-S1 shard map drift")
    all_records: list[dict[str, Any]] = []
    shard_inputs: list[dict[str, Any]] = []
    physical_total = 0
    for shard_id, expected in enumerate(shard_map["shards"]):
        path = _find_shard(root, shard_id)
        if path is None:
            all_records.extend(_failure_rows(shard_id, expected, "missing_provider_shard"))
            shard_inputs.append({"shard_id": shard_id, "status": "missing", "sha256": None})
            continue
        try:
            payload = json.loads(path.read_text())
            if payload.get("schema") != "d2-vnext-s1-source-acquisition-provider-shard-v0.1":
                raise AssertionError("provider-shard schema mismatch")
            if payload.get("study_stream") != "D2-vNext-S1":
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
            if payload.get("requested_model") != EXPECTED_MODEL:
                raise AssertionError("provider shard requested-model mismatch")
            if payload.get("effective_model_identity_observed") is not False:
                raise AssertionError("unexpected effective-model identity claim")
            temperature = payload.get("temperature")
            if isinstance(temperature, bool) or not isinstance(temperature, (int, float)):
                raise AssertionError("provider shard temperature invalid")
            if abs(float(temperature) - EXPECTED_TEMPERATURE) > 1e-12:
                raise AssertionError("provider shard temperature mismatch")
            if payload.get("thinking") != "disabled":
                raise AssertionError("provider shard thinking contract mismatch")
            cohort = payload.get("cohort_lock", {})
            if cohort.get("cohort_pairs_sha256") != EXPECTED_COHORT_SHA256:
                raise AssertionError("provider shard cohort mismatch")
            accounting = payload.get("transport_accounting")
            if not isinstance(accounting, dict):
                raise AssertionError("provider shard transport accounting missing")
            sends = accounting.get("physical_provider_sends_observed")
            if type(sends) is not int or not 0 <= sends <= MAX_PHYSICAL_SENDS_PER_SHARD:
                raise AssertionError("provider shard physical-send count invalid")
            if accounting.get("unexpected_outbound_http_requests_blocked") != 0:
                raise AssertionError("provider shard attempted unregistered outbound HTTP")
            physical_total += sends
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
                {
                    "shard_id": shard_id,
                    "status": "loaded",
                    "sha256": file_sha256(path),
                    "physical_provider_sends_observed": sends,
                }
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
        raise AssertionError("canonical D2-vNext-S1 provider coverage mismatch")
    if physical_total > MAX_PHYSICAL_SENDS_CAMPAIGN:
        raise AssertionError("campaign physical-send topology ceiling exceeded")
    complete = [row for row in all_records if row.get("status") == "complete"]
    failed = [row for row in all_records if row.get("status") != "complete"]
    return {
        "schema": "d2-vnext-s1-source-acquisition-provider-output-v0.1",
        "study_stream": "D2-vNext-S1",
        "status": "provider_campaign_complete_unclassified",
        "classification": None,
        "attempted_pairs": PAIR_COUNT,
        "complete_pairs": len(complete),
        "failed_pairs": len(failed),
        "requested_model": EXPECTED_MODEL,
        "effective_model_identity_observed": False,
        "effective_model": None,
        "temperature": EXPECTED_TEMPERATURE,
        "thinking": "disabled",
        "cohort_pairs_sha256": EXPECTED_COHORT_SHA256,
        "physical_provider_sends_observed_total": physical_total,
        "maximum_physical_provider_sends_campaign": MAX_PHYSICAL_SENDS_CAMPAIGN,
        "pair_records": all_records,
        "shard_inputs": shard_inputs,
        "shard_map_sha256": file_sha256(shard_map_path),
        "registry_promotion_authorized": False,
        "acceptance_action_authorized": False,
        "production_historical_substrate_enabled": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("provider_shards")
    parser.add_argument("--shard-map", default="research/d2_vnext_s1/D2_VNEXT_S1_SHARD_MAP.json")
    parser.add_argument("--output-dir", default="output/d2-vnext-s1-canonical-provider")
    args = parser.parse_args()
    output = aggregate(Path(args.provider_shards), shard_map_path=Path(args.shard_map))
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    output_path = out / "d2-vnext-s1-provider-output.json"
    output_path.write_bytes(canonical_bytes(output))
    manifest = {
        "schema": "d2-vnext-s1-source-acquisition-provider-output-manifest-v0.1",
        "study_stream": "D2-vNext-S1",
        "provider_output_sha256": file_sha256(output_path),
        "attempted_pairs": PAIR_COUNT,
        "complete_pairs": output["complete_pairs"],
        "failed_pairs": output["failed_pairs"],
        "cohort_pairs_sha256": EXPECTED_COHORT_SHA256,
        "physical_provider_sends_observed_total": output[
            "physical_provider_sends_observed_total"
        ],
        "classification": None,
        "registry_promotion_authorized": False,
        "production_historical_substrate_enabled": False,
    }
    (out / "provider-output-manifest.json").write_bytes(canonical_bytes(manifest))
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
