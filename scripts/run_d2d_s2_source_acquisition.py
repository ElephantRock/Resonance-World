#!/usr/bin/env python3
"""Execute one authorized D2d-S2 provider shard without classifying it."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import d2d_s2_acquisition_core as core
import d2d_s2_general_api_client as transport
import materialize_d2d_s2_source_acquisition as materializer
import run_d2d_source_acquisition as base

ISSUE = 208
PAIR_COUNT = 384
SHARD_COUNT = 24
EXPECTED_COHORT_SHA256 = "d74348dc2d15e2b1c1959726faa9ae473e01a3aeed46bcdc3b1c240e918b3d9f"
MODEL = "glm-5-turbo"
TEMPERATURE = 0.8
MARKER_PATH = Path("research/d2d_s2/RUN_D2D_S2_SOURCE_ACQUISITION")
AUTH_ENV = "D2D_S2_PROVIDER_EXECUTION_AUTHORIZED"
AUTHORIZATION_STRING = "D2d_S2_provider_execution_explicitly_authorized"
BEHAVIORAL_OBJECTIVE = (
    "Choose exactly one action from KAPPA, MICA, ORBIT, VELA for each four-feature integer case. "
    "Each Field owns a fixed hidden local policy belonging to the registered D2d-S2 "
    "calibration schema."
)


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@contextmanager
def _fresh_base_context():
    """Bind the historical runner to D2d-S2 only while one shard is executing."""

    original = (
        base.core,
        base.materializer,
        base.EXPECTED_COHORT_SHA256,
        base.BEHAVIORAL_OBJECTIVE,
    )
    base.core = core
    base.materializer = materializer
    base.EXPECTED_COHORT_SHA256 = EXPECTED_COHORT_SHA256
    base.BEHAVIORAL_OBJECTIVE = BEHAVIORAL_OBJECTIVE
    try:
        yield
    finally:
        (
            base.core,
            base.materializer,
            base.EXPECTED_COHORT_SHA256,
            base.BEHAVIORAL_OBJECTIVE,
        ) = original


def marker_record() -> dict[str, str]:
    if not MARKER_PATH.exists():
        raise RuntimeError("D2d-S2 authorization marker is absent")
    lines = [line for line in MARKER_PATH.read_text().splitlines() if line]
    if len(lines) != 3 or any("=" not in line for line in lines):
        raise RuntimeError("D2d-S2 authorization marker is malformed")
    fields = dict(line.split("=", 1) for line in lines)
    if set(fields) != {"candidate_sha", "issue", "authorization"}:
        raise RuntimeError("D2d-S2 authorization marker fields are invalid")
    candidate = fields["candidate_sha"]
    if len(candidate) != 40 or any(ch not in "0123456789abcdef" for ch in candidate):
        raise RuntimeError("D2d-S2 candidate SHA is invalid")
    if fields["issue"] != str(ISSUE):
        raise RuntimeError("D2d-S2 authorization issue is invalid")
    if fields["authorization"] != AUTHORIZATION_STRING:
        raise RuntimeError("D2d-S2 authorization string is invalid")
    return fields


def assert_authorized() -> dict[str, str]:
    if os.environ.get(AUTH_ENV) != "1":
        raise RuntimeError("D2d-S2 provider execution is not authorized")
    return marker_record()


def verify_cohort_lock(path: Path) -> dict[str, Any]:
    committed = json.loads(path.read_text())
    expected = materializer.build_cohort_lock()
    if committed != expected:
        raise AssertionError("D2d-S2 committed cohort lock drift")
    return expected


def load_shard_range(shard_id: int, path: Path) -> tuple[int, int, str]:
    data = json.loads(path.read_text())
    if data != materializer.build_shard_map():
        raise AssertionError("D2d-S2 committed shard-map drift")
    if not 0 <= shard_id < SHARD_COUNT:
        raise AssertionError("unknown D2d-S2 shard")
    row = data["shards"][shard_id]
    return int(row["start_pair"]), int(row["end_pair"]), str(row["schema_id"])


def _rename_pair(record: dict[str, Any]) -> dict[str, Any]:
    record = dict(record)
    public_id = record.get("pair_public_id")
    if isinstance(public_id, str) and public_id.startswith("d2d-"):
        record["pair_public_id"] = "d2d-s2-" + public_id[len("d2d-"):]
    return record


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--shard-id", type=int, required=True)
    parser.add_argument("--output-dir", default="output/d2d-s2-provider-shard")
    parser.add_argument(
        "--cohort-lock",
        default="research/d2d_s2/d2d-s2-source-acquisition-cohort-lock.json",
    )
    parser.add_argument("--shard-map", default="research/d2d_s2/D2D_S2_SHARD_MAP.json")
    parser.add_argument("--plan", default="research/d2d_s2/PLAN.md")
    parser.add_argument("--request-plan", default="research/d2d_s2/D2D_S2_REQUEST_PLAN.json")
    parser.add_argument("--schema-suite", default="research/d2d_s2/D2D_S2_SCHEMA_SUITE.json")
    parser.add_argument("--sample-size", default="research/d2d_s2/D2D_S2_SAMPLE_SIZE.json")
    args = parser.parse_args()

    marker = assert_authorized()
    start_pair, end_pair, schema_id = load_shard_range(args.shard_id, Path(args.shard_map))
    lock_summary = verify_cohort_lock(Path(args.cohort_lock))
    key = os.environ.get("ZAI_API_KEY", "")
    if not key:
        raise RuntimeError("ZAI_API_KEY is required for authorized D2d-S2 execution")
    client = transport.Client(key)
    with _fresh_base_context():
        pair_records = [
            _rename_pair(base.run_pair_safe(client, index))
            for index in range(start_pair, end_pair + 1)
        ]
    complete = [row for row in pair_records if row["status"] == "complete"]
    failed = [row for row in pair_records if row["status"] != "complete"]
    output = {
        "schema": "d2d-s2-source-acquisition-provider-shard-v0.1",
        "study_stream": "D2d-S2",
        "status": "provider_shard_complete_unclassified",
        "classification": None,
        "authorized_candidate_sha": marker["candidate_sha"],
        "authorization_marker_sha256": file_sha256(MARKER_PATH),
        "shard_id": args.shard_id,
        "schema_id": schema_id,
        "start_pair": start_pair,
        "end_pair": end_pair,
        "attempted_pairs": len(pair_records),
        "complete_pairs": len(complete),
        "failed_pairs": len(failed),
        "model": MODEL,
        "temperature": TEMPERATURE,
        "cohort_lock": lock_summary,
        "pair_records": pair_records,
        "transport_accounting": {
            "logical_calls_started": client.logical_calls_started,
            "logical_calls_completed": client.logical_calls_completed,
            "logical_call_failures": client.logical_call_failures,
            "physical_attempts_started": client.physical_attempts_started,
            "max_attempts_per_logical_call": 1,
            "redirect_policy": "reject_do_not_follow",
        },
        "plan_sha256": file_sha256(Path(args.plan)),
        "request_plan_sha256": file_sha256(Path(args.request_plan)),
        "schema_suite_sha256": file_sha256(Path(args.schema_suite)),
        "sample_size_sha256": file_sha256(Path(args.sample_size)),
        "cohort_lock_file_sha256": file_sha256(Path(args.cohort_lock)),
        "shard_map_sha256": file_sha256(Path(args.shard_map)),
        "production_historical_substrate_enabled": False,
    }
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    output_path = out / f"d2d-s2-provider-shard-{args.shard_id:02d}.json"
    output_path.write_bytes(canonical_bytes(output))
    manifest = {
        "schema": "d2d-s2-source-acquisition-provider-shard-manifest-v0.1",
        "study_stream": "D2d-S2",
        "shard_id": args.shard_id,
        "schema_id": schema_id,
        "provider_shard_output_sha256": file_sha256(output_path),
        "attempted_pairs": len(pair_records),
        "complete_pairs": len(complete),
        "failed_pairs": len(failed),
        "cohort_pairs_sha256": EXPECTED_COHORT_SHA256,
        "classification": None,
        "production_historical_substrate_enabled": False,
    }
    (out / f"d2d-s2-provider-shard-{args.shard_id:02d}-manifest.json").write_bytes(
        canonical_bytes(manifest)
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
