#!/usr/bin/env python3
"""Reproduce D2-vNext-S2 post-hoc attrition ledger from frozen artifacts.

Diagnostic only. This script does not call a provider, modify the consumed stream,
or perform the frozen scientific hypothesis tests.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

EXPECTED_PROVIDER_SHA256 = "1419144f035ad1eafb3604f0a1859b134a2f9ddb280e1a04e4959d75e31042b2"
EXPECTED_RUN_ID = 35909017872
EXPECTED_ATTEMPTED = 384
EXPECTED_COMPLETE = 205
EXPECTED_FAILED = 179
EXPECTED_ANALYZABLE = {
    "threshold_at_4": 60,
    "parity_pair": 71,
    "interval_pair": 58,
    "pairwise_order": 16,
}
EXPECTED_FAILURE_SHA256 = "6c4a6ce59b69ad55cfd186ea90d43a07eb2f694cc17f54e284879eaa5304a6f9"
FAILURE_PREIMAGE = "RuntimeError:D2-vNext-S2 logical call has no accepted exact completion"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise AssertionError(f"expected JSON object: {path}")
    return value


def find_shard(root: Path, shard_id: int) -> Path:
    matches = sorted(root.glob(f"**/d2-vnext-s2-provider-shard-{shard_id:02d}.json"))
    matches = [path for path in matches if "manifest" not in path.name]
    if len(matches) != 1:
        raise AssertionError(f"expected exactly one shard {shard_id}, found {len(matches)}")
    return matches[0]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("provider_output", type=Path)
    parser.add_argument("shards_root", type=Path)
    parser.add_argument("artifact_index", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    if sha256_file(args.provider_output) != EXPECTED_PROVIDER_SHA256:
        raise AssertionError("canonical provider-output SHA-256 mismatch")
    provider = load_json(args.provider_output)
    if provider.get("attempted_pairs") != EXPECTED_ATTEMPTED:
        raise AssertionError("attempted-pair mismatch")
    if provider.get("complete_pairs") != EXPECTED_COMPLETE:
        raise AssertionError("complete-pair mismatch")
    if provider.get("failed_pairs") != EXPECTED_FAILED:
        raise AssertionError("failed-pair mismatch")

    index = load_json(args.artifact_index)
    if index.get("workflow_run_id") != EXPECTED_RUN_ID:
        raise AssertionError("artifact-index run mismatch")
    index_by_shard = {
        int(row["shard_id"]): row for row in index.get("provider_shards", [])
    }
    if set(index_by_shard) != set(range(24)):
        raise AssertionError("artifact-index shard coverage mismatch")

    canonical_inputs = {
        int(row["shard_id"]): row for row in provider.get("shard_inputs", [])
    }
    if set(canonical_inputs) != set(range(24)):
        raise AssertionError("canonical shard-input coverage mismatch")

    shards: dict[int, dict[str, Any]] = {}
    pair_to_shard: dict[int, int] = {}
    for shard_id in range(24):
        path = find_shard(args.shards_root, shard_id)
        actual_sha = sha256_file(path)
        expected_sha = str(index_by_shard[shard_id]["provider_shard_output_sha256"])
        if actual_sha != expected_sha:
            raise AssertionError(f"artifact-index SHA mismatch for shard {shard_id}")
        if actual_sha != canonical_inputs[shard_id]["sha256"]:
            raise AssertionError(f"canonical-input SHA mismatch for shard {shard_id}")
        shard = load_json(path)
        if int(shard["shard_id"]) != shard_id:
            raise AssertionError("shard id mismatch")
        if shard.get("status") != "provider_shard_complete_unclassified":
            raise AssertionError("unexpected shard status")
        accounting = shard.get("transport_accounting")
        if not isinstance(accounting, dict):
            raise AssertionError("transport accounting missing")
        for key in (
            "provider_sends_blocked_by_budget",
            "unexpected_outbound_http_requests_blocked",
            "logical_attribution_mismatch_blocks",
            "provider_workers_alive_after_drain",
        ):
            if accounting.get(key) != 0:
                raise AssertionError(f"transport/accounting defect in shard {shard_id}: {key}")
        if accounting.get("transport_hooks_restored_after_drain") is not True:
            raise AssertionError(f"transport hooks not restored in shard {shard_id}")
        shards[shard_id] = shard
        for pair_index in range(int(shard["start_pair"]), int(shard["end_pair"]) + 1):
            if pair_index in pair_to_shard:
                raise AssertionError("pair assigned to multiple shards")
            pair_to_shard[pair_index] = shard_id
    if set(pair_to_shard) != set(range(EXPECTED_ATTEMPTED)):
        raise AssertionError("shard pair coverage mismatch")

    records = provider.get("pair_records")
    if not isinstance(records, list) or len(records) != EXPECTED_ATTEMPTED:
        raise AssertionError("canonical pair-record coverage mismatch")
    records = sorted(records, key=lambda row: int(row["pair_index"]))
    if [int(row["pair_index"]) for row in records] != list(range(EXPECTED_ATTEMPTED)):
        raise AssertionError("canonical pair-index coverage mismatch")

    status_counts = Counter(str(row.get("status")) for row in records)
    if status_counts != Counter({"complete": EXPECTED_COMPLETE, "failed": EXPECTED_FAILED}):
        raise AssertionError(f"status reconciliation failed: {status_counts}")

    schema_complete: Counter[str] = Counter()
    schema_failed: Counter[str] = Counter()
    failed_fingerprints: Counter[tuple[str, str, str]] = Counter()
    ledger: list[dict[str, Any]] = []
    for row in records:
        pair_index = int(row["pair_index"])
        shard_id = pair_to_shard[pair_index]
        complete = row.get("status") == "complete"
        schema_id = str(row["schema_id"])
        if complete:
            schema_complete[schema_id] += 1
        else:
            schema_failed[schema_id] += 1
            key = (
                str(row.get("failure_class")),
                str(row.get("error_type")),
                str(row.get("error_sha256")),
            )
            failed_fingerprints[key] += 1
        shard_index = index_by_shard[shard_id]
        ledger.append(
            {
                "pair_index": pair_index,
                "pair_public_id": row["pair_public_id"],
                "schema_id": schema_id,
                "schema_pair_index": int(row["schema_pair_index"]),
                "provider_shard_id": shard_id,
                "pair_complete": str(complete).lower(),
                "registered_schema_analyzable": str(complete).lower(),
                "failure_class": "" if complete else row.get("failure_class", ""),
                "error_type": "" if complete else row.get("error_type", ""),
                "error_sha256": "" if complete else row.get("error_sha256", ""),
                "failure_fingerprint_preimage": "" if complete else FAILURE_PREIMAGE,
                "terminal_intra_pair_phase": (
                    "" if complete else "unknown_from_canonical_failed_pair_record"
                ),
                "source_provider_output_sha256": EXPECTED_PROVIDER_SHA256,
                "source_shard_output_sha256": canonical_inputs[shard_id]["sha256"],
                "source_shard_artifact_id": int(shard_index["artifact_id"]),
                "source_shard_artifact_digest": shard_index["artifact_digest"],
            }
        )

    if dict(schema_complete) != EXPECTED_ANALYZABLE:
        raise AssertionError(f"schema complete/analyzable mismatch: {schema_complete}")
    if sum(schema_failed.values()) != EXPECTED_FAILED:
        raise AssertionError("schema failure total mismatch")
    expected_failure_key = (
        "provider_pair_failure",
        "RuntimeError",
        EXPECTED_FAILURE_SHA256,
    )
    if failed_fingerprints != Counter({expected_failure_key: EXPECTED_FAILED}):
        raise AssertionError(f"unexpected pair-failure fingerprints: {failed_fingerprints}")

    shard_rows: list[dict[str, Any]] = []
    schema_totals: dict[str, dict[str, int]] = defaultdict(
        lambda: {
            "attempted_pairs": 0,
            "complete_pairs": 0,
            "failed_pairs": 0,
            "logical_calls_started": 0,
            "logical_calls_completed": 0,
            "logical_call_failures": 0,
            "format_regeneration_retries_used": 0,
            "terminal_iteration_overrides_used": 0,
            "physical_provider_sends_observed": 0,
        }
    )
    for shard_id in range(24):
        shard = shards[shard_id]
        accounting = shard["transport_accounting"]
        row = {
            "shard_id": shard_id,
            "schema_id": shard["schema_id"],
            "start_pair": int(shard["start_pair"]),
            "end_pair": int(shard["end_pair"]),
            "attempted_pairs": int(shard["attempted_pairs"]),
            "complete_pairs": int(shard["complete_pairs"]),
            "failed_pairs": int(shard["failed_pairs"]),
            "logical_calls_started": int(accounting["logical_calls_started"]),
            "logical_calls_completed": int(accounting["logical_calls_completed"]),
            "logical_call_failures": int(accounting["logical_call_failures"]),
            "format_regeneration_retries_used": int(
                accounting["format_regeneration_retries_used"]
            ),
            "terminal_iteration_overrides_used": int(
                accounting["terminal_iteration_overrides_used"]
            ),
            "physical_provider_sends_observed": int(
                accounting["physical_provider_sends_observed"]
            ),
            "provider_shard_output_sha256": canonical_inputs[shard_id]["sha256"],
            "workflow_artifact_id": int(index_by_shard[shard_id]["artifact_id"]),
            "workflow_artifact_digest": index_by_shard[shard_id]["artifact_digest"],
        }
        shard_rows.append(row)
        totals = schema_totals[str(shard["schema_id"])]
        for key in totals:
            totals[key] += row[key]

    if sum(row["physical_provider_sends_observed"] for row in shard_rows) != 14509:
        raise AssertionError("physical-send total mismatch")

    out = args.output_dir
    out.mkdir(parents=True, exist_ok=True)
    fieldnames = list(ledger[0])
    ledger_path = out / "D2_VNEXT_S2_PAIR_ATTRITION_LEDGER.csv"
    with ledger_path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(ledger)

    core = {
        "schema": "d2-vnext-s2-attrition-core-v0.1",
        "status": "posthoc_diagnostic_only",
        "source_run_id": EXPECTED_RUN_ID,
        "source_provider_output_sha256": EXPECTED_PROVIDER_SHA256,
        "pair_ledger_sha256": sha256_file(ledger_path),
        "attempted_pairs": EXPECTED_ATTEMPTED,
        "complete_pairs": EXPECTED_COMPLETE,
        "failed_pairs": EXPECTED_FAILED,
        "schema_totals": dict(schema_totals),
        "failure_fingerprint": {
            "failure_class": "provider_pair_failure",
            "error_type": "RuntimeError",
            "error_sha256": EXPECTED_FAILURE_SHA256,
            "preimage": FAILURE_PREIMAGE,
            "records": EXPECTED_FAILED,
        },
        "shards": shard_rows,
        "governance": {
            "provider_execution_authorized": False,
            "same_stream_rerun_authorized": False,
            "adaptive_n_rescue_authorized": False,
            "acceptance_authorized": False,
            "registry_promotion_authorized": False,
            "historical_substrate_enabled": False,
        },
    }
    (out / "D2_VNEXT_S2_ATTRITION_CORE.json").write_text(
        json.dumps(core, indent=2, sort_keys=True) + "\n"
    )
    print(json.dumps({
        "pair_ledger_sha256": core["pair_ledger_sha256"],
        "complete_pairs": EXPECTED_COMPLETE,
        "failed_pairs": EXPECTED_FAILED,
        "schema_complete_pairs": dict(schema_complete),
        "physical_provider_sends_observed": 14509,
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
