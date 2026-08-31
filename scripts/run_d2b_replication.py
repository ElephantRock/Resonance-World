#!/usr/bin/env python3
"""Run one frozen D2b replication provider shard without classifying it."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import threading
from pathlib import Path
from typing import Any

import run_d2_c2_confirmatory as parent
from d2_artifact_core import assert_export_safe, make_artifact
from d2_calibration_r2_core import (
    ACTIONS,
    CHANCE_SCORE,
    features_set,
    generate_balanced_cases,
    policy_for,
    sha256,
)

PAIR_COUNT = 360
SEED_BASE = 3_200_000
SEED_STEP = 100
SOURCE_DEV_COUNT = parent.SOURCE_DEV_COUNT
DEST_DEV_COUNT = parent.DEST_DEV_COUNT
EVAL_COUNT = parent.EVAL_COUNT
BATCH_SIZE = parent.BATCH_SIZE
EVAL_CHUNK_SIZE = parent.EVAL_CHUNK_SIZE
MODEL = parent.MODEL
TEMPERATURE = parent.TEMPERATURE
MAX_ATTEMPTS = parent.MAX_ATTEMPTS
MAX_TOKENS = parent.MAX_TOKENS
LOCAL_CONCURRENCY = parent.LOCAL_CONCURRENCY
MIN_REQUEST_INTERVAL_SECONDS = parent.MIN_REQUEST_INTERVAL_SECONDS
EXPECTED_COHORT_SHA256 = (
    "b4d8f39b9730de6869b6b3c3f9ceb4d16c76214b8eee9437c2bca62e85286b23"
)

BEHAVIORAL_OBJECTIVE = parent.BEHAVIORAL_OBJECTIVE
ECOLOGY_HINT = parent.ECOLOGY_HINT
DEVELOPMENT_PROTOCOL = parent.DEVELOPMENT_PROTOCOL


def canonical_bytes(value: Any) -> bytes:
    return parent.canonical_bytes(value)


def file_sha256(path: Path) -> str:
    return parent.file_sha256(path)


def case_bundle(pair_index: int) -> dict[str, Any]:
    pair_seed = SEED_BASE + pair_index * SEED_STEP
    source_seed = pair_seed + 1
    destination_seed = pair_seed + 2
    eval_seed = pair_seed + 3
    policy = policy_for(pair_seed)
    source_cases = generate_balanced_cases(
        rng_seed=source_seed,
        count=SOURCE_DEV_COUNT,
        prefix=f"d2b-source-p{pair_index:03d}",
        policy=policy,
    )
    source_features = features_set(source_cases)
    destination_cases = generate_balanced_cases(
        rng_seed=destination_seed,
        count=DEST_DEV_COUNT,
        prefix=f"d2b-destination-p{pair_index:03d}",
        policy=policy,
        exclude_features=source_features,
    )
    destination_features = features_set(destination_cases)
    eval_cases = generate_balanced_cases(
        rng_seed=eval_seed,
        count=EVAL_COUNT,
        prefix=f"d2b-eval-p{pair_index:03d}",
        policy=policy,
        exclude_features=source_features | destination_features,
    )
    eval_features = features_set(eval_cases)
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
        "policy_sha256": sha256(bundle["policy"].private_record()),
        "source_cases_sha256": sha256(bundle["source_cases"]),
        "destination_cases_sha256": sha256(bundle["destination_cases"]),
        "evaluation_holdout_sha256": sha256(bundle["eval_cases"]),
        "source_destination_overlap": len(
            bundle["source_features"] & bundle["destination_features"]
        ),
        "development_evaluation_overlap": len(
            (bundle["source_features"] | bundle["destination_features"])
            & bundle["eval_features"]
        ),
    }


def verify_cohort_lock(path: Path) -> dict[str, Any]:
    lock = json.loads(path.read_text())
    if lock.get("schema") != "d2b-replication-cohort-lock-v0.1":
        raise AssertionError("unexpected D2b cohort-lock schema")
    if lock["cohort_pairs_sha256"] != EXPECTED_COHORT_SHA256:
        raise AssertionError("committed D2b cohort hash constant mismatch")
    if lock["seed_series"]["base"] != SEED_BASE:
        raise AssertionError("D2b seed-base mismatch")
    records = [pair_lock_record(index) for index in range(PAIR_COUNT)]
    computed = sha256(records)
    if computed != EXPECTED_COHORT_SHA256:
        raise AssertionError(
            f"D2b cohort lock mismatch: {computed} != {EXPECTED_COHORT_SHA256}"
        )
    if any(
        row["source_destination_overlap"] != 0
        or row["development_evaluation_overlap"] != 0
        for row in records
    ):
        raise AssertionError("D2b cohort overlap integrity failure")
    return {
        "schema": lock["schema"],
        "pair_count": PAIR_COUNT,
        "cohort_pairs_sha256": computed,
        "all_source_destination_overlaps_zero": True,
        "all_development_evaluation_overlaps_zero": True,
    }


def load_shard_range(shard_id: int, path: Path) -> tuple[int, int]:
    data = json.loads(path.read_text())
    if data.get("schema") != "d2b-replication-shard-map-v0.1":
        raise AssertionError("unexpected D2b shard-map schema")
    if data.get("pair_count_attempted") != PAIR_COUNT:
        raise AssertionError("D2b shard-map pair-count mismatch")
    if data.get("provider_local_concurrency_per_shard") != LOCAL_CONCURRENCY:
        raise AssertionError("D2b local concurrency drift")
    shards = data.get("shards")
    if not isinstance(shards, list) or len(shards) != 18:
        raise AssertionError("D2b shard-map cardinality mismatch")
    expected_indices: list[int] = []
    selected: tuple[int, int] | None = None
    for row in shards:
        sid = int(row["shard"])
        start = int(row["start_pair"])
        end = int(row["end_pair"])
        if end < start:
            raise AssertionError("invalid D2b shard range")
        expected_indices.extend(range(start, end + 1))
        if sid == shard_id:
            selected = (start, end)
    if expected_indices != list(range(PAIR_COUNT)):
        raise AssertionError("D2b shard map does not cover 0..359 exactly once")
    if selected is None:
        raise AssertionError(f"unknown D2b shard id: {shard_id}")
    return selected


class Client(parent.Client):
    """Parent transport with D2b request-id provenance and identical counters."""

    def __init__(self, key: str) -> None:
        super().__init__(key)
        self.rng = random.Random(2026083101)
        self.counter_lock = threading.Lock()
        self.logical_calls_started = 0
        self.logical_calls_completed = 0
        self.successful_physical_attempts = 0
        self.logical_call_failures = 0

    def _request_id(self, phase: str, attempt: int) -> str:
        with self.rng_lock:
            nonce = self.rng.getrandbits(64)
        safe = phase.replace("/", "-")[-40:]
        return f"d2b-{safe}-{attempt}-{nonce:016x}"


def build_artifact(pair_index: int, source_public_score: float) -> dict[str, Any]:
    return make_artifact(
        artifact_id=f"d2b-replication-capability-{pair_index:03d}",
        behavioral_objective={
            "action_vocabulary": list(ACTIONS),
            "objective": BEHAVIORAL_OBJECTIVE,
        },
        source_public_evidence={
            "registered_source_development_completed": True,
            "heldout_score_band": (
                "at_or_above_chance"
                if source_public_score >= CHANCE_SCORE
                else "below_chance"
            ),
            "no_private_strategy_exported": True,
        },
        required_environment={
            "feature_names": ["f0", "f1", "f2", "f3"],
            "feature_domain": "integers 0..7",
            "local_hidden_policy_required": True,
        },
        required_task_ecology={
            "registered_family": (
                "two undisclosed controlling coordinates; each thresholded at 4; "
                "opaque one-to-one two-bit-to-action relabeling"
            ),
            "local_policy_parameters_are_not_exported": True,
        },
        development_protocol={
            "batch_size": BATCH_SIZE,
            "development_cases": DEST_DEV_COUNT,
            "procedure": DEVELOPMENT_PROTOCOL,
            "destination_local_examples_only": True,
        },
        feedback_contract={
            "development_feedback": ["correct", "correct_action"],
            "evaluation_feedback": "none",
        },
        memory_update_contract={
            "private_strategy_allowed": True,
            "strategy_is_local_and_nonexportable": True,
            "recommended_contents": (
                "candidate controlling coordinates and action-state mapping"
            ),
        },
        provider_contract={
            "provider": "Z.AI",
            "model": MODEL,
            "temperature": TEMPERATURE,
            "thinking": "disabled",
            "structured_output": "json_object",
        },
        resource_requirements={
            "development_batches": SOURCE_DEV_COUNT // BATCH_SIZE,
            "development_cases": DEST_DEV_COUNT,
            "heldout_evaluation_cases": EVAL_COUNT,
            "logical_calls": DEST_DEV_COUNT // BATCH_SIZE
            + EVAL_COUNT // EVAL_CHUNK_SIZE,
        },
        stopping_rule={
            "development_batches_are_fixed": True,
            "no_outcome_adaptive_stopping": True,
        },
        evaluation_contract={
            "heldout_evaluation_count": EVAL_COUNT,
            "no_evaluation_feedback": True,
            "confirmatory_cases_not_serialized": True,
        },
        known_dependencies=[
            "destination exposes four integer features with the registered policy family",
            "outcome-bearing feedback is available only during development",
        ],
        known_failure_conditions=[
            "insufficient labeled local development evidence",
            "provider fails structured action contract",
        ],
        permitted_use_modes=[
            "local_development",
            "fresh_destination_reproduction_confirmatory",
        ],
        provenance={
            "program_issue": 186,
            "parent_program_issue": 167,
            "parent_discovery_study": "D2-C2",
            "study": "D2b fresh replication",
            "production_historical_substrate_enabled": False,
        },
    )


def run_pair(client: Client, pair_index: int) -> dict[str, Any]:
    bundle = case_bundle(pair_index)
    policy = bundle["policy"]
    source_cases = bundle["source_cases"]
    destination_cases = bundle["destination_cases"]
    eval_cases = bundle["eval_cases"]

    source = parent.run_development_arm(
        client,
        arm=f"source-p{pair_index:03d}",
        dev_cases=source_cases,
        eval_cases=eval_cases,
        artifact=None,
        labeled=True,
    )
    artifact = build_artifact(pair_index, float(source["runner_final_score"]))
    source_agent_id = f"source-agent-d2b-p{pair_index:03d}-{bundle['source_seed']}"
    audit = assert_export_safe(
        artifact,
        source_agent_ids=[source_agent_id],
        source_seeds=[bundle["source_seed"], bundle["pair_seed"]],
        source_example_ids=[case["case_id"] for case in source_cases],
        hidden_truth_tokens=[policy.truth_token],
    )

    reproduced = parent.run_development_arm(
        client,
        arm=f"reproduced-p{pair_index:03d}",
        dev_cases=destination_cases,
        eval_cases=eval_cases,
        artifact=artifact,
        labeled=True,
    )
    description = parent.run_development_arm(
        client,
        arm=f"description-p{pair_index:03d}",
        dev_cases=destination_cases,
        eval_cases=eval_cases,
        artifact=None,
        labeled=False,
    )
    fresh = parent.run_fresh_arm(client, eval_cases=eval_cases)

    return {
        "status": "complete",
        "pair_index": pair_index,
        "pair_public_id": f"d2b-replication-pair-{pair_index:03d}",
        "pair_lock_record": pair_lock_record(pair_index),
        "artifact": artifact,
        "artifact_audit": audit.as_dict(),
        "evaluation_case_ids": [case["case_id"] for case in eval_cases],
        "evaluation_truth": [case["correct_action"] for case in eval_cases],
        "arms": {
            "fresh": fresh,
            "description_only": description,
            "reproduced": reproduced,
            "source_developed": source,
        },
    }


def run_pair_safe(client: Client, pair_index: int) -> dict[str, Any]:
    try:
        return run_pair(client, pair_index)
    except Exception as exc:
        fingerprint = hashlib.sha256(
            f"{type(exc).__name__}:{str(exc)[:500]}".encode()
        ).hexdigest()
        return {
            "status": "failed",
            "pair_index": pair_index,
            "pair_public_id": f"d2b-replication-pair-{pair_index:03d}",
            "failure_class": "provider_pair_failure",
            "error_type": type(exc).__name__,
            "error_sha256": fingerprint,
        }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--shard-id", type=int, required=True)
    parser.add_argument(
        "--output-dir", default="output/d2b-replication-provider-shard"
    )
    parser.add_argument(
        "--cohort-lock",
        default="research/d2b/d2b-replication-cohort-lock.json",
    )
    parser.add_argument("--shard-map", default="research/d2b/D2B_SHARD_MAP.json")
    parser.add_argument("--plan", default="research/d2b/PLAN.md")
    parser.add_argument(
        "--request-plan", default="research/d2b/D2B_REPLICATION_REQUEST_PLAN.json"
    )
    args = parser.parse_args()

    shard_map_path = Path(args.shard_map)
    start_pair, end_pair = load_shard_range(args.shard_id, shard_map_path)
    lock_summary = verify_cohort_lock(Path(args.cohort_lock))

    key = os.environ.get("ZAI_API_KEY", "")
    if not key:
        raise RuntimeError("ZAI_API_KEY is required for provider shard execution")
    client = Client(key)

    pair_records = [
        run_pair_safe(client, index) for index in range(start_pair, end_pair + 1)
    ]
    complete = [row for row in pair_records if row["status"] == "complete"]
    failed = [row for row in pair_records if row["status"] != "complete"]

    output = {
        "schema": "d2b-replication-provider-shard-v0.1",
        "status": "provider_shard_complete_unclassified",
        "classification": None,
        "shard_id": args.shard_id,
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
            "successful_physical_attempts": client.successful_physical_attempts,
        },
        "plan_sha256": file_sha256(Path(args.plan)),
        "request_plan_sha256": file_sha256(Path(args.request_plan)),
        "cohort_lock_file_sha256": file_sha256(Path(args.cohort_lock)),
        "shard_map_sha256": file_sha256(shard_map_path),
        "production_historical_substrate_enabled": False,
    }

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"d2b-replication-provider-shard-{args.shard_id:02d}.json"
    output_path.write_bytes(canonical_bytes(output))
    manifest = {
        "schema": "d2b-replication-provider-shard-manifest-v0.1",
        "shard_id": args.shard_id,
        "start_pair": start_pair,
        "end_pair": end_pair,
        "provider_shard_output_sha256": file_sha256(output_path),
        "attempted_pairs": len(pair_records),
        "complete_pairs": len(complete),
        "failed_pairs": len(failed),
        "cohort_pairs_sha256": EXPECTED_COHORT_SHA256,
        "model": MODEL,
        "temperature": TEMPERATURE,
        "classification": None,
        "production_historical_substrate_enabled": False,
    }
    manifest_path = output_dir / f"d2b-provider-shard-{args.shard_id:02d}-manifest.json"
    manifest_path.write_bytes(canonical_bytes(manifest))
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
