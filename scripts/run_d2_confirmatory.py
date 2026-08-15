#!/usr/bin/env python3
"""Run the frozen D2 confirmatory provider campaign without classifying it."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import run_d2_calibration_r2 as r2
from d2_artifact_core import assert_export_safe, make_artifact
from d2_calibration_r2_core import (
    ACTIONS,
    CHANCE_SCORE,
    features_set,
    generate_balanced_cases,
    labeled_feedback,
    policy_for,
    score_actions,
    sha256,
    unlabeled_history,
)

PAIR_COUNT = 360
SEED_BASE = 1_200_000
SEED_STEP = 100
SOURCE_DEV_COUNT = 40
DEST_DEV_COUNT = 40
EVAL_COUNT = 32
BATCH_SIZE = 8
EVAL_CHUNK_SIZE = 8
MODEL = "glm-5-turbo"
TEMPERATURE = 0.8
MAX_ATTEMPTS = 8
MAX_TOKENS = 768
CONCURRENCY = 4
MIN_REQUEST_INTERVAL_SECONDS = 0.35
EXPECTED_COHORT_SHA256 = (
    "d8e2c82cd7c110bd3013b870e460218442d4d6819bb9cf06f537dcd670fd32a3"
)

BEHAVIORAL_OBJECTIVE = r2.BEHAVIORAL_OBJECTIVE
ECOLOGY_HINT = r2.ECOLOGY_HINT
DEVELOPMENT_PROTOCOL = r2.DEVELOPMENT_PROTOCOL

# The reused transport helpers read these globals from the calibration module.
r2.MODEL = MODEL
r2.TEMPERATURE = TEMPERATURE
r2.SOURCE_DEV_COUNT = SOURCE_DEV_COUNT
r2.DEST_DEV_COUNT = DEST_DEV_COUNT
r2.EVAL_COUNT = EVAL_COUNT
r2.BATCH_SIZE = BATCH_SIZE
r2.EVAL_CHUNK_SIZE = EVAL_CHUNK_SIZE
r2.MAX_ATTEMPTS = MAX_ATTEMPTS
r2.MAX_TOKENS = MAX_TOKENS
r2.CONCURRENCY = CONCURRENCY
r2.MIN_REQUEST_INTERVAL_SECONDS = MIN_REQUEST_INTERVAL_SECONDS


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def case_bundle(pair_index: int) -> dict[str, Any]:
    pair_seed = SEED_BASE + pair_index * SEED_STEP
    source_seed = pair_seed + 1
    destination_seed = pair_seed + 2
    eval_seed = pair_seed + 3
    policy = policy_for(pair_seed)
    source_cases = generate_balanced_cases(
        rng_seed=source_seed,
        count=SOURCE_DEV_COUNT,
        prefix=f"d2c-source-p{pair_index:03d}",
        policy=policy,
    )
    source_features = features_set(source_cases)
    destination_cases = generate_balanced_cases(
        rng_seed=destination_seed,
        count=DEST_DEV_COUNT,
        prefix=f"d2c-destination-p{pair_index:03d}",
        policy=policy,
        exclude_features=source_features,
    )
    destination_features = features_set(destination_cases)
    eval_cases = generate_balanced_cases(
        rng_seed=eval_seed,
        count=EVAL_COUNT,
        prefix=f"d2c-eval-p{pair_index:03d}",
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
    policy = bundle["policy"]
    return {
        "pair_index": pair_index,
        "pair_public_id": f"d2-confirmatory-pair-{pair_index:03d}",
        "policy_sha256": sha256(policy.private_record()),
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
    if lock["cohort_pairs_sha256"] != EXPECTED_COHORT_SHA256:
        raise AssertionError("committed cohort hash constant mismatch")
    records = [pair_lock_record(index) for index in range(PAIR_COUNT)]
    computed = sha256(records)
    if computed != EXPECTED_COHORT_SHA256:
        raise AssertionError(
            f"confirmatory cohort lock mismatch: {computed} != {EXPECTED_COHORT_SHA256}"
        )
    if any(
        row["source_destination_overlap"] != 0
        or row["development_evaluation_overlap"] != 0
        for row in records
    ):
        raise AssertionError("cohort overlap integrity failure")
    return {
        "schema": lock["schema"],
        "pair_count": PAIR_COUNT,
        "cohort_pairs_sha256": computed,
        "all_source_destination_overlaps_zero": True,
        "all_development_evaluation_overlaps_zero": True,
    }


class Client(r2.Client):
    """R2 transport with confirmatory request-id provenance and counters."""

    def __init__(self, key: str) -> None:
        super().__init__(key)
        self.rng = random.Random(2026081515)
        self.counter_lock = threading.Lock()
        self.logical_calls_started = 0
        self.logical_calls_completed = 0
        self.successful_physical_attempts = 0
        self.logical_call_failures = 0

    def _request_id(self, phase: str, attempt: int) -> str:
        with self.rng_lock:
            nonce = self.rng.getrandbits(64)
        safe = phase.replace("/", "-")[-40:]
        return f"d2c-{safe}-{attempt}-{nonce:016x}"

    def complete(self, **kwargs: Any) -> dict[str, Any]:
        with self.counter_lock:
            self.logical_calls_started += 1
        try:
            result = super().complete(**kwargs)
        except Exception:
            with self.counter_lock:
                self.logical_call_failures += 1
            raise
        with self.counter_lock:
            self.logical_calls_completed += 1
            self.successful_physical_attempts += len(result["attempts"])
        return result


def build_artifact(pair_index: int, source_public_score: float) -> dict[str, Any]:
    return make_artifact(
        artifact_id=f"d2-confirmatory-capability-{pair_index:03d}",
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
            "program_issue": 167,
            "study": "D2 confirmatory",
            "production_historical_substrate_enabled": False,
        },
    )


def run_development_arm(
    client: Client,
    *,
    arm: str,
    dev_cases: list[dict[str, Any]],
    eval_cases: list[dict[str, Any]],
    artifact: dict[str, Any] | None,
    labeled: bool,
) -> dict[str, Any]:
    calls: list[dict[str, Any]] = []
    batch_scores: list[float] = []
    strategy = ""
    prior_history: list[dict[str, Any]] | None = None

    for batch_index, batch in enumerate(
        r2.split_batches(dev_cases, BATCH_SIZE),
        start=1,
    ):
        result = client.complete(
            phase=f"{arm}/development{batch_index}",
            system=r2.system_prompt(len(batch)),
            user=r2.decision_user(
                cases=batch,
                prior_strategy=strategy,
                history=prior_history,
                labeled=labeled,
                artifact=artifact,
                phase=f"{arm}_development_{batch_index}",
            ),
            expected_actions=len(batch),
            temperature=TEMPERATURE,
        )
        actions = list(result["actions"])
        strategy = r2.resolved_strategy(result, strategy)
        calls.append(r2.call_record(result, strategy))
        batch_scores.append(score_actions(batch, actions))
        prior_history = (
            labeled_feedback(batch, actions)
            if labeled
            else unlabeled_history(batch, actions)
        )

    eval_actions: list[str] = []
    for chunk_index, chunk in enumerate(
        r2.split_batches(eval_cases, EVAL_CHUNK_SIZE),
        start=1,
    ):
        result = client.complete(
            phase=f"{arm}/evaluation{chunk_index}",
            system=r2.system_prompt(len(chunk)),
            user=r2.decision_user(
                cases=chunk,
                prior_strategy=strategy,
                history=prior_history if chunk_index == 1 else None,
                labeled=labeled,
                artifact=artifact,
                phase=f"{arm}_evaluation_{chunk_index}",
            ),
            expected_actions=len(chunk),
            temperature=TEMPERATURE,
        )
        eval_actions.extend(result["actions"])
        strategy = r2.resolved_strategy(result, strategy)
        calls.append(r2.call_record(result, strategy))

    return {
        "development_batch_scores": batch_scores,
        "runner_final_score": score_actions(eval_cases, eval_actions),
        "evaluation_actions": eval_actions,
        "logical_calls": len(calls),
        "physical_attempts": sum(call["physical_attempts"] for call in calls),
        "calls": calls,
    }


def run_fresh_arm(
    client: Client,
    *,
    eval_cases: list[dict[str, Any]],
) -> dict[str, Any]:
    calls: list[dict[str, Any]] = []
    strategy = ""
    eval_actions: list[str] = []
    for chunk_index, chunk in enumerate(
        r2.split_batches(eval_cases, EVAL_CHUNK_SIZE),
        start=1,
    ):
        result = client.complete(
            phase=f"fresh/evaluation{chunk_index}",
            system=r2.system_prompt(len(chunk)),
            user=r2.decision_user(
                cases=chunk,
                prior_strategy=strategy,
                history=None,
                labeled=False,
                artifact=None,
                phase=f"fresh_evaluation_{chunk_index}",
            ),
            expected_actions=len(chunk),
            temperature=TEMPERATURE,
        )
        eval_actions.extend(result["actions"])
        strategy = r2.resolved_strategy(result, strategy)
        calls.append(r2.call_record(result, strategy))
    return {
        "development_batch_scores": [],
        "runner_final_score": score_actions(eval_cases, eval_actions),
        "evaluation_actions": eval_actions,
        "logical_calls": len(calls),
        "physical_attempts": sum(call["physical_attempts"] for call in calls),
        "calls": calls,
    }


def run_pair(client: Client, pair_index: int) -> dict[str, Any]:
    bundle = case_bundle(pair_index)
    policy = bundle["policy"]
    source_cases = bundle["source_cases"]
    destination_cases = bundle["destination_cases"]
    eval_cases = bundle["eval_cases"]

    source = run_development_arm(
        client,
        arm=f"source-p{pair_index:03d}",
        dev_cases=source_cases,
        eval_cases=eval_cases,
        artifact=None,
        labeled=True,
    )
    artifact = build_artifact(pair_index, float(source["runner_final_score"]))
    source_agent_id = (
        f"source-agent-d2c-p{pair_index:03d}-{bundle['source_seed']}"
    )
    audit = assert_export_safe(
        artifact,
        source_agent_ids=[source_agent_id],
        source_seeds=[bundle["source_seed"], bundle["pair_seed"]],
        source_example_ids=[case["case_id"] for case in source_cases],
        hidden_truth_tokens=[policy.truth_token],
    )

    reproduced = run_development_arm(
        client,
        arm=f"reproduced-p{pair_index:03d}",
        dev_cases=destination_cases,
        eval_cases=eval_cases,
        artifact=artifact,
        labeled=True,
    )
    description = run_development_arm(
        client,
        arm=f"description-p{pair_index:03d}",
        dev_cases=destination_cases,
        eval_cases=eval_cases,
        artifact=None,
        labeled=False,
    )
    fresh = run_fresh_arm(client, eval_cases=eval_cases)

    lock_record = pair_lock_record(pair_index)
    return {
        "status": "complete",
        "pair_index": pair_index,
        "pair_public_id": f"d2-confirmatory-pair-{pair_index:03d}",
        "pair_lock_record": lock_record,
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
            "pair_public_id": f"d2-confirmatory-pair-{pair_index:03d}",
            "error_type": type(exc).__name__,
            "error_sha256": fingerprint,
        }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        default="output/d2-confirmatory-provider",
    )
    parser.add_argument(
        "--cohort-lock",
        default="research/d2/d2-confirmatory-cohort-lock.json",
    )
    args = parser.parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    lock_summary = verify_cohort_lock(Path(args.cohort_lock))
    client = Client(os.environ.get("ZAI_API_KEY", ""))

    pair_records: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
        futures = {
            pool.submit(run_pair_safe, client, index): index
            for index in range(PAIR_COUNT)
        }
        for future in as_completed(futures):
            pair_records.append(future.result())
    pair_records.sort(key=lambda row: row["pair_index"])

    complete = [row for row in pair_records if row["status"] == "complete"]
    failed = [row for row in pair_records if row["status"] != "complete"]
    output = {
        "schema": "d2-confirmatory-provider-output-v0.1",
        "status": "provider_campaign_complete_unclassified",
        "model": MODEL,
        "temperature": TEMPERATURE,
        "attempted_pairs": PAIR_COUNT,
        "complete_pairs": len(complete),
        "failed_pairs": len(failed),
        "cohort_lock": lock_summary,
        "pair_records": pair_records,
        "transport_accounting": {
            "logical_calls_started": client.logical_calls_started,
            "logical_calls_completed": client.logical_calls_completed,
            "logical_call_failures": client.logical_call_failures,
            "successful_physical_attempts": client.successful_physical_attempts,
        },
        "plan_sha256": file_sha256(
            Path("research/d2/D2_CONFIRMATORY_PLAN.md")
        ),
        "request_plan_sha256": file_sha256(
            Path("research/d2/D2_CONFIRMATORY_REQUEST_PLAN.json")
        ),
        "cohort_lock_file_sha256": file_sha256(Path(args.cohort_lock)),
        "production_historical_substrate_enabled": False,
        "classification": None,
    }
    output_path = output_dir / "d2-confirmatory-provider-output.json"
    output_path.write_bytes(canonical_bytes(output))
    manifest = {
        "schema": "d2-confirmatory-provider-manifest-v0.1",
        "provider_output_sha256": file_sha256(output_path),
        "attempted_pairs": PAIR_COUNT,
        "complete_pairs": len(complete),
        "failed_pairs": len(failed),
        "cohort_pairs_sha256": EXPECTED_COHORT_SHA256,
        "model": MODEL,
        "temperature": TEMPERATURE,
        "production_historical_substrate_enabled": False,
        "classification": None,
    }
    manifest_path = output_dir / "provider-manifest.json"
    manifest_path.write_bytes(canonical_bytes(manifest))
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
