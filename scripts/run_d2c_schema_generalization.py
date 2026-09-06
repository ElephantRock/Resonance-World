#!/usr/bin/env python3
"""Run one frozen D2c schema-generalization provider shard without classifying it."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import threading
from pathlib import Path
from typing import Any

import d2c_schema_core as core
import materialize_d2c_schema_generalization as materializer
import run_d2_c2_confirmatory as parent
from d2_artifact_core import assert_export_safe, make_artifact

PAIR_COUNT = 540
PAIRS_PER_SCHEMA = 180
SHARD_COUNT = 27
SOURCE_DEV_COUNT = 40
DEST_DEV_COUNT = 40
EVAL_COUNT = 32
BATCH_SIZE = 8
EVAL_CHUNK_SIZE = 8
MODEL = "glm-5-turbo"
TEMPERATURE = 0.8
MAX_ATTEMPTS = 8
MAX_TOKENS = 768
LOCAL_CONCURRENCY = 1
MIN_REQUEST_INTERVAL_SECONDS = 0.35
EXPECTED_COHORT_SHA256 = "559a4420a1d592d85fa350d087a8d4b945f4bf882a683c660a77cf9fdb6b9c04"

BEHAVIORAL_OBJECTIVE = (
    "Choose exactly one action from KAPPA, MICA, ORBIT, VELA for each four-feature integer case. "
    "Each Field owns a fixed hidden local policy belonging to the registered D2c schema family."
)

# Reuse the validated D2 transport while pinning its transport globals to the D2c contract.
parent.r2.MODEL = MODEL
parent.r2.TEMPERATURE = TEMPERATURE
parent.r2.MAX_ATTEMPTS = MAX_ATTEMPTS
parent.r2.MAX_TOKENS = MAX_TOKENS
parent.r2.CONCURRENCY = LOCAL_CONCURRENCY
parent.r2.MIN_REQUEST_INTERVAL_SECONDS = MIN_REQUEST_INTERVAL_SECONDS


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def case_bundle(pair_index: int) -> dict[str, Any]:
    return materializer.case_bundle(pair_index)


def pair_lock_record(pair_index: int) -> dict[str, Any]:
    return materializer.pair_lock_record(pair_index)


def verify_cohort_lock(path: Path) -> dict[str, Any]:
    lock = json.loads(path.read_text())
    if lock.get("schema") != "d2c-schema-generalization-cohort-lock-v0.1":
        raise AssertionError("unexpected D2c cohort-lock schema")
    if lock.get("pair_count") != PAIR_COUNT:
        raise AssertionError("D2c cohort pair-count mismatch")
    if lock.get("pairs_per_schema") != PAIRS_PER_SCHEMA:
        raise AssertionError("D2c pairs-per-schema mismatch")
    if lock.get("cohort_pairs_sha256") != EXPECTED_COHORT_SHA256:
        raise AssertionError("D2c committed cohort hash mismatch")
    records = [pair_lock_record(index) for index in range(PAIR_COUNT)]
    computed = core.sha256(records)
    if computed != EXPECTED_COHORT_SHA256:
        raise AssertionError(f"D2c recomputed cohort mismatch: {computed}")
    if lock.get("all_source_destination_overlaps_zero") is not True:
        raise AssertionError("D2c source/destination overlap")
    if lock.get("all_development_evaluation_overlaps_zero") is not True:
        raise AssertionError("D2c development/evaluation overlap")
    if lock.get("cross_schema_seed_overlap") != 0:
        raise AssertionError("D2c cross-schema seed overlap")
    if lock.get("predecessor_seed_namespace_overlap") != {"D2-C1": 0, "D2-C2": 0, "D2b": 0}:
        raise AssertionError("D2c predecessor seed overlap")
    if lock.get("production_historical_substrate_enabled") is not False:
        raise AssertionError("Historical Substrate must be off")
    return {
        "schema": lock["schema"],
        "pair_count": PAIR_COUNT,
        "pairs_per_schema": PAIRS_PER_SCHEMA,
        "schema_order": list(core.SCHEMA_ORDER),
        "cohort_pairs_sha256": computed,
        "all_source_destination_overlaps_zero": True,
        "all_development_evaluation_overlaps_zero": True,
        "cross_schema_seed_overlap": 0,
        "predecessor_seed_namespace_overlap": {"D2-C1": 0, "D2-C2": 0, "D2b": 0},
    }


def load_shard_range(shard_id: int, path: Path) -> tuple[int, int, str]:
    data = json.loads(path.read_text())
    if data.get("schema") != "d2c-schema-generalization-shard-map-v0.1":
        raise AssertionError("unexpected D2c shard-map schema")
    if data.get("pair_count_attempted") != PAIR_COUNT or data.get("shard_count") != SHARD_COUNT:
        raise AssertionError("D2c shard-map cardinality mismatch")
    if data.get("provider_local_concurrency_per_shard") != LOCAL_CONCURRENCY:
        raise AssertionError("D2c local concurrency drift")
    shards = data.get("shards")
    if not isinstance(shards, list) or len(shards) != SHARD_COUNT:
        raise AssertionError("D2c shard rows mismatch")
    union: list[int] = []
    selected: tuple[int, int, str] | None = None
    for row in shards:
        sid = int(row["shard"])
        start = int(row["start_pair"])
        end = int(row["end_pair"])
        schema_id = str(row["schema_id"])
        union.extend(range(start, end + 1))
        if sid == shard_id:
            selected = (start, end, schema_id)
    if union != list(range(PAIR_COUNT)):
        raise AssertionError("D2c shard map does not cover 0..539 exactly once")
    if selected is None:
        raise AssertionError(f"unknown D2c shard: {shard_id}")
    return selected


class Client(parent.Client):
    """Validated D2 transport with D2c request-id provenance."""

    def __init__(self, key: str) -> None:
        super().__init__(key)
        self.rng = random.Random(2026090102)
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


def system_prompt(case_count: int) -> str:
    return (
        "Return one JSON object with an actions array containing exactly "
        f"{case_count} entries, each one of {', '.join(core.ACTIONS)}. "
        "You may also include strategy as a concise private working string. "
        "Other keys are ignored. "
        "Do not use markdown."
    )


def decision_user(
    *,
    schema_id: str,
    cases: list[dict[str, Any]],
    prior_strategy: str,
    history: list[dict[str, Any]] | None,
    labeled: bool,
    artifact: dict[str, Any] | None,
    phase: str,
) -> str:
    sections = [
        f"Objective: {BEHAVIORAL_OBJECTIVE}",
        f"Task ecology: {core.PUBLIC_ECOLOGY[schema_id]}",
        f"Phase: {phase}",
    ]
    if artifact is not None:
        sections.append(
            "Public Capability Artifact (production conditions only; no source-private state):\n"
            + json.dumps(artifact, sort_keys=True, separators=(",", ":"))
        )
    elif phase.startswith("source"):
        sections.append(f"Development protocol: {core.DEVELOPMENT_PROTOCOL[schema_id]}")
    elif phase.startswith("description"):
        sections.append(
            "This control receives unlabeled practice only. No correctness or "
            "correct-action feedback "
            "is available; do not treat prior choices as labels."
        )
    if prior_strategy:
        sections.append("Prior private strategy:\n" + prior_strategy)
    if history is not None:
        label = "Outcome-bearing local feedback" if labeled else "Unlabeled prior practice"
        sections.append(label + ":\n" + json.dumps(history, sort_keys=True, separators=(",", ":")))
    sections.append(
        "Cases to answer now:\n"
        + json.dumps(
            [core.public_case(case) for case in cases], sort_keys=True, separators=(",", ":")
        )
    )
    if "evaluation" in phase:
        sections.append(
            "These are held-out confirmatory cases. Their correctness will not be "
            "returned to the agent."
        )
    else:
        sections.append(
            "Return choices and, if useful, an updated private strategy. Use feedback "
            "to revise the "
            "hypothesis rather than memorizing case IDs."
        )
    return "\n\n".join(sections)


def _resolved_strategy(result: dict[str, Any], previous: str) -> str:
    strategy = result.get("strategy")
    return previous if strategy is None else str(strategy)


def _call_record(result: dict[str, Any], strategy: str) -> dict[str, Any]:
    return {
        "model": result["model"],
        "temperature": result["temperature"],
        "request_id": result["request_id"],
        "prompt_sha256": result["prompt_sha256"],
        "response_sha256": result["response_sha256"],
        "strategy_sha256": hashlib.sha256(strategy.encode()).hexdigest(),
        "strategy_present": result["strategy_present"],
        "extra_key_count": result["extra_key_count"],
        "physical_attempts": len(result["attempts"]),
        "attempt_log": result["attempts"],
        "usage": result["usage"],
        "total_latency_ms": result["total_latency_ms"],
    }


def _split(cases: list[dict[str, Any]], size: int) -> list[list[dict[str, Any]]]:
    if len(cases) % size:
        raise ValueError("case count not divisible by batch size")
    return [cases[i : i + size] for i in range(0, len(cases), size)]


def run_development_arm(
    client: Client,
    *,
    schema_id: str,
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
    for batch_index, batch in enumerate(_split(dev_cases, BATCH_SIZE), start=1):
        result = client.complete(
            phase=f"{arm}/development{batch_index}",
            system=system_prompt(len(batch)),
            user=decision_user(
                schema_id=schema_id,
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
        strategy = _resolved_strategy(result, strategy)
        calls.append(_call_record(result, strategy))
        batch_scores.append(core.score_actions(batch, actions))
        prior_history = (
            core.labeled_feedback(batch, actions)
            if labeled
            else core.unlabeled_history(batch, actions)
        )

    eval_actions: list[str] = []
    for chunk_index, chunk in enumerate(_split(eval_cases, EVAL_CHUNK_SIZE), start=1):
        result = client.complete(
            phase=f"{arm}/evaluation{chunk_index}",
            system=system_prompt(len(chunk)),
            user=decision_user(
                schema_id=schema_id,
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
        strategy = _resolved_strategy(result, strategy)
        calls.append(_call_record(result, strategy))
    return {
        "development_batch_scores": batch_scores,
        "runner_final_score": core.score_actions(eval_cases, eval_actions),
        "evaluation_actions": eval_actions,
        "logical_calls": len(calls),
        "physical_attempts": sum(call["physical_attempts"] for call in calls),
        "calls": calls,
    }


def run_fresh_arm(
    client: Client, *, schema_id: str, eval_cases: list[dict[str, Any]]
) -> dict[str, Any]:
    calls: list[dict[str, Any]] = []
    strategy = ""
    eval_actions: list[str] = []
    for chunk_index, chunk in enumerate(_split(eval_cases, EVAL_CHUNK_SIZE), start=1):
        result = client.complete(
            phase=f"fresh/evaluation{chunk_index}",
            system=system_prompt(len(chunk)),
            user=decision_user(
                schema_id=schema_id,
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
        strategy = _resolved_strategy(result, strategy)
        calls.append(_call_record(result, strategy))
    return {
        "development_batch_scores": [],
        "runner_final_score": core.score_actions(eval_cases, eval_actions),
        "evaluation_actions": eval_actions,
        "logical_calls": len(calls),
        "physical_attempts": sum(call["physical_attempts"] for call in calls),
        "calls": calls,
    }


def build_artifact(pair_index: int, schema_id: str, source_public_score: float) -> dict[str, Any]:
    return make_artifact(
        artifact_id=f"d2c-{schema_id}-capability-{pair_index:03d}",
        behavioral_objective={
            "action_vocabulary": list(core.ACTIONS),
            "objective": BEHAVIORAL_OBJECTIVE,
        },
        source_public_evidence={
            "registered_source_development_completed": True,
            "heldout_score_band": "at_or_above_chance"
            if source_public_score >= 0.25
            else "below_chance",
            "no_private_strategy_exported": True,
        },
        required_environment={
            "feature_names": list(core.FEATURE_NAMES),
            "feature_domain": "integers 0..7",
            "local_hidden_policy_required": True,
        },
        required_task_ecology={
            "schema_id": schema_id,
            "registered_family": core.PUBLIC_ECOLOGY[schema_id],
            "local_policy_parameters_are_not_exported": True,
        },
        development_protocol={
            "batch_size": BATCH_SIZE,
            "development_cases": DEST_DEV_COUNT,
            "procedure": core.DEVELOPMENT_PROTOCOL[schema_id],
            "destination_local_examples_only": True,
        },
        feedback_contract={
            "development_feedback": ["correct", "correct_action"],
            "evaluation_feedback": "none",
        },
        memory_update_contract={
            "private_strategy_allowed": True,
            "strategy_is_local_and_nonexportable": True,
            "recommended_contents": "candidate schema-local hidden policy and action-state mapping",
        },
        provider_contract={
            "provider": "Z.AI",
            "model": MODEL,
            "temperature": TEMPERATURE,
            "thinking": "disabled",
            "structured_output": "json_object",
        },
        resource_requirements={
            "development_batches": 5,
            "development_cases": DEST_DEV_COUNT,
            "heldout_evaluation_cases": EVAL_COUNT,
            "logical_calls": 9,
        },
        stopping_rule={"development_batches_are_fixed": True, "no_outcome_adaptive_stopping": True},
        evaluation_contract={
            "heldout_evaluation_count": EVAL_COUNT,
            "no_evaluation_feedback": True,
            "confirmatory_cases_not_serialized": True,
        },
        known_dependencies=[
            "destination exposes four integer features with the registered D2c schema family",
            "outcome-bearing feedback is available only during development",
        ],
        known_failure_conditions=[
            "insufficient labeled local development evidence",
            "provider fails structured action contract",
        ],
        permitted_use_modes=[
            "local_development",
            "fresh_destination_reproduction_schema_generalization",
        ],
        provenance={
            "program_issue": 192,
            "parent_registry_node": "d2_stochastic_capability_reproduction",
            "study": "D2c schema generalization",
            "schema_id": schema_id,
            "production_historical_substrate_enabled": False,
        },
    )


def run_pair(client: Client, pair_index: int) -> dict[str, Any]:
    bundle = case_bundle(pair_index)
    schema_id = str(bundle["schema_id"])
    policy = bundle["policy"]
    source_cases = bundle["source_cases"]
    destination_cases = bundle["destination_cases"]
    eval_cases = bundle["eval_cases"]
    source = run_development_arm(
        client,
        schema_id=schema_id,
        arm=f"source-{schema_id}-p{pair_index:03d}",
        dev_cases=source_cases,
        eval_cases=eval_cases,
        artifact=None,
        labeled=True,
    )
    artifact = build_artifact(pair_index, schema_id, float(source["runner_final_score"]))
    audit = assert_export_safe(
        artifact,
        source_agent_ids=[
            f"source-agent-d2c-{schema_id}-p{pair_index:03d}-{bundle['source_seed']}"
        ],
        source_seeds=[bundle["source_seed"], bundle["pair_seed"]],
        source_example_ids=[case["case_id"] for case in source_cases],
        hidden_truth_tokens=[policy.truth_token],
    )
    reproduced = run_development_arm(
        client,
        schema_id=schema_id,
        arm=f"reproduced-{schema_id}-p{pair_index:03d}",
        dev_cases=destination_cases,
        eval_cases=eval_cases,
        artifact=artifact,
        labeled=True,
    )
    description = run_development_arm(
        client,
        schema_id=schema_id,
        arm=f"description-{schema_id}-p{pair_index:03d}",
        dev_cases=destination_cases,
        eval_cases=eval_cases,
        artifact=None,
        labeled=False,
    )
    fresh = run_fresh_arm(client, schema_id=schema_id, eval_cases=eval_cases)
    return {
        "status": "complete",
        "pair_index": pair_index,
        "schema_id": schema_id,
        "schema_pair_index": bundle["local_pair_index"],
        "pair_public_id": f"d2c-{schema_id}-pair-{bundle['local_pair_index']:03d}",
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
    schema_id, local_index = core.schema_and_local_index(pair_index)
    try:
        return run_pair(client, pair_index)
    except Exception as exc:
        fingerprint = hashlib.sha256(f"{type(exc).__name__}:{str(exc)[:500]}".encode()).hexdigest()
        return {
            "status": "failed",
            "pair_index": pair_index,
            "schema_id": schema_id,
            "schema_pair_index": local_index,
            "pair_public_id": f"d2c-{schema_id}-pair-{local_index:03d}",
            "failure_class": "provider_pair_failure",
            "error_type": type(exc).__name__,
            "error_sha256": fingerprint,
        }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--shard-id", type=int, required=True)
    parser.add_argument("--output-dir", default="output/d2c-provider-shard")
    parser.add_argument("--cohort-lock", default="research/d2c/d2c-schema-cohort-lock.json")
    parser.add_argument("--shard-map", default="research/d2c/D2C_SHARD_MAP.json")
    parser.add_argument("--plan", default="research/d2c/PLAN.md")
    parser.add_argument("--request-plan", default="research/d2c/D2C_REQUEST_PLAN.json")
    parser.add_argument("--schema-suite", default="research/d2c/D2C_SCHEMA_SUITE.json")
    parser.add_argument("--sample-size", default="research/d2c/D2C_SAMPLE_SIZE.json")
    args = parser.parse_args()

    start_pair, end_pair, schema_id = load_shard_range(args.shard_id, Path(args.shard_map))
    lock_summary = verify_cohort_lock(Path(args.cohort_lock))
    key = os.environ.get("ZAI_API_KEY", "")
    if not key:
        raise RuntimeError("ZAI_API_KEY is required for D2c provider execution")
    client = Client(key)
    pair_records = [run_pair_safe(client, index) for index in range(start_pair, end_pair + 1)]
    complete = [row for row in pair_records if row["status"] == "complete"]
    failed = [row for row in pair_records if row["status"] != "complete"]
    output = {
        "schema": "d2c-schema-generalization-provider-shard-v0.1",
        "status": "provider_shard_complete_unclassified",
        "classification": None,
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
            "successful_physical_attempts": client.successful_physical_attempts,
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
    output_path = out / f"d2c-provider-shard-{args.shard_id:02d}.json"
    output_path.write_bytes(canonical_bytes(output))
    manifest = {
        "schema": "d2c-schema-generalization-provider-shard-manifest-v0.1",
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
    (out / f"d2c-provider-shard-{args.shard_id:02d}-manifest.json").write_bytes(
        canonical_bytes(manifest)
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
