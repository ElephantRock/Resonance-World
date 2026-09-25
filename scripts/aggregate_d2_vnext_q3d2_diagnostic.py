#!/usr/bin/env python3
# ruff: noqa: E501
"""Aggregate two Q3-D2 provider shards into one canonical diagnostic payload."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import d2_vnext_q3d2_diagnostic_core as core
import materialize_d2_vnext_q3d2_diagnostic as materializer


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input_dir")
    parser.add_argument("--output-dir", default="output/d2-vnext-q3d2-canonical")
    args = parser.parse_args()
    root = Path(args.input_dir)
    paths = sorted(root.rglob("d2-vnext-q3d2-provider-shard-??.json"))
    defects: list[str] = []
    shards: list[dict[str, Any]] = []
    if len(paths) != materializer.SHARD_COUNT:
        defects.append(f"expected_{materializer.SHARD_COUNT}_shards_got_{len(paths)}")
    for path in paths:
        try:
            row = json.loads(path.read_text())
        except Exception as exc:
            defects.append(f"unreadable_shard:{path.name}:{type(exc).__name__}")
            continue
        shards.append(row)
    ids = [row.get("shard_id") for row in shards]
    if sorted(ids) != list(range(materializer.SHARD_COUNT)):
        defects.append("shard_id_coverage_mismatch")
    candidates = {row.get("authorized_candidate_sha") for row in shards}
    if len(candidates) != 1:
        defects.append("candidate_identity_mismatch")
    sends = sum(
        int(row.get("transport_accounting", {}).get("physical_provider_sends_observed", 0))
        for row in shards
    )
    if sends > materializer.MAX_PHYSICAL_SENDS_CAMPAIGN:
        defects.append("campaign_send_cap_exceeded")
    for row in shards:
        acct = row.get("transport_accounting", {})
        if int(acct.get("physical_provider_sends_observed", 0)) > materializer.MAX_PHYSICAL_SENDS_PER_SHARD:
            defects.append(f"shard_{row.get('shard_id')}_send_cap_exceeded")
        if any(
            int(acct.get(key, 0)) != 0
            for key in (
                "provider_sends_blocked_by_budget",
                "unexpected_outbound_http_requests_blocked",
                "logical_attribution_mismatch_blocks",
            )
        ):
            defects.append(f"shard_{row.get('shard_id')}_transport_integrity_defect")
        if (
            int(acct.get("provider_workers_alive_after_drain", 0)) != 0
            or acct.get("transport_hooks_restored_after_drain") is not True
        ):
            defects.append(f"shard_{row.get('shard_id')}_worker_or_hook_defect")
    pairs = sorted(
        (pair for row in shards for pair in row.get("pair_records", [])),
        key=lambda row: int(row.get("pair_index", -1)),
    )
    if [int(row.get("pair_index", -1)) for row in pairs] != list(range(core.PAIR_COUNT)):
        defects.append("pair_coverage_mismatch")
    canonical = {
        "schema": "d2-vnext-q3d2-canonical-provider-output-v0.1",
        "study_stream": "D2-vNext-Q3-D2",
        "stage": "Q3-D2",
        "fresh_namespace": core.NAMESPACE,
        "authorized_candidate_sha": next(iter(candidates)) if len(candidates) == 1 else None,
        "cohort_pairs_sha256": materializer.EXPECTED_COHORT_SHA256,
        "attempted_pairs": len(pairs),
        "complete_pairs": sum(1 for row in pairs if row.get("status") == "complete"),
        "failed_pairs": sum(1 for row in pairs if row.get("status") != "complete"),
        "physical_provider_sends_observed": sends,
        "maximum_physical_provider_sends_campaign": materializer.MAX_PHYSICAL_SENDS_CAMPAIGN,
        "integrity_defects": sorted(set(defects)),
        "pair_records": pairs,
        "shard_summaries": [
            {
                "shard_id": row.get("shard_id"),
                "attempted_pairs": row.get("attempted_pairs"),
                "complete_pairs": row.get("complete_pairs"),
                "failed_pairs": row.get("failed_pairs"),
                "physical_provider_sends_observed": row.get("transport_accounting", {}).get(
                    "physical_provider_sends_observed"
                ),
            }
            for row in sorted(shards, key=lambda item: int(item.get("shard_id", -1)))
        ],
        "scientific_effect_gates_authorized": False,
        "registry_promotion_authorized": False,
        "acceptance_action_authorized": False,
        "production_historical_substrate_enabled": False,
    }
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / "d2-vnext-q3d2-provider-output.json"
    path.write_bytes(canonical_bytes(canonical))
    manifest = {
        "schema": "d2-vnext-q3d2-canonical-provider-manifest-v0.1",
        "provider_output_sha256": file_sha256(path),
        "integrity_defects": canonical["integrity_defects"],
        "attempted_pairs": canonical["attempted_pairs"],
        "physical_provider_sends_observed": sends,
        "provider_execution_authorized": False,
        "scientific_effect_gates_authorized": False,
    }
    (out / "manifest.json").write_bytes(canonical_bytes(manifest))
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
