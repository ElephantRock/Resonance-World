#!/usr/bin/env python3
"""Execute D2-0 development-only calibration after transport repair 1."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from d2_artifact_core import assert_export_safe, make_artifact
from d2_calibration_core import (
    ACTIONS,
    descriptive_summary,
    features_set,
    generate_cases,
    labeled_feedback,
    policy_for,
    public_case,
    sampling_summary,
    score_actions,
    sha256,
    unlabeled_history,
)

MODEL = "glm-5-turbo"
ENDPOINT = "https://api.z.ai/api/coding/paas/v4/chat/completions"
TEMPERATURE = 0.8
SAMPLING_TEMPERATURES = (0.4, 0.8, 1.0)
SAMPLING_REPLICATES = 6
PAIR_COUNT = 8
SOURCE_DEV_COUNT = 16
DEST_DEV_COUNT = 16
EVAL_COUNT = 24
BATCH_SIZE = 8
EVAL_CHUNK_SIZE = 8
MAX_ATTEMPTS = 8
MAX_TOKENS = 512
CONCURRENCY = 4
MIN_REQUEST_INTERVAL_SECONDS = 0.35
MAX_429_BACKOFF_SECONDS = 90.0

BEHAVIORAL_OBJECTIVE = (
    "Choose exactly one action from KAPPA, MICA, ORBIT, VELA for each four-feature integer case. "
    "The environment owns a fixed hidden policy."
)
ECOLOGY_HINT = (
    "The hidden policy belongs to a fixed task family using simple parity and threshold relations "
    "over f0..f3, two latent bits, possible bit flips, and an opaque four-action relabeling. "
    "The actual family, flips, and relabeling are not disclosed."
)
SOURCE_PROTOCOL = (
    "Use local outcome-bearing feedback to test compact hypotheses. Maintain a concise private "
    "strategy that is updated between development batches. Do not memorize case IDs as a policy."
)


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def payload_sha(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


class Client:
    def __init__(self, key: str) -> None:
        if not key.strip():
            raise ValueError("ZAI_API_KEY is empty")
        self.key = key
        self.rng = random.Random(2026081503)
        self.rng_lock = threading.Lock()
        self.rate_lock = threading.Lock()
        self.next_request_at = 0.0

    def _request_id(self, phase: str, attempt: int) -> str:
        with self.rng_lock:
            nonce = self.rng.getrandbits(64)
        safe = phase.replace("/", "-")[-36:]
        return f"d2r1-{safe}-{attempt}-{nonce:016x}"

    def _wait(self) -> None:
        with self.rate_lock:
            now = time.monotonic()
            wait = max(0.0, self.next_request_at - now)
            if wait:
                time.sleep(wait)
            self.next_request_at = (
                max(time.monotonic(), self.next_request_at) + MIN_REQUEST_INTERVAL_SECONDS
            )

    def complete(
        self,
        *,
        phase: str,
        system: str,
        user: str,
        expected_actions: int,
        temperature: float,
    ) -> dict[str, Any]:
        attempts: list[dict[str, Any]] = []
        started_all = time.perf_counter()
        for attempt in range(1, MAX_ATTEMPTS + 1):
            request_id = self._request_id(phase, attempt)
            body = {
                "model": MODEL,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "thinking": {"type": "disabled"},
                "do_sample": True,
                "temperature": temperature,
                "max_tokens": MAX_TOKENS,
                "stream": False,
                "response_format": {"type": "json_object"},
                "request_id": request_id,
            }
            request = Request(
                ENDPOINT,
                data=json.dumps(body, separators=(",", ":")).encode(),
                method="POST",
                headers={
                    "Authorization": f"Bearer {self.key}",
                    "Content-Type": "application/json",
                    "Accept-Language": "en-US,en",
                    "User-Agent": "resonance-world-d2-calibration-r1/0.1",
                },
            )
            self._wait()
            started = time.perf_counter()
            retry_delay = min(8.0, 2.0 ** (attempt - 1))
            try:
                with urlopen(request, timeout=90.0) as response:
                    outer = json.loads(response.read().decode())
                if outer.get("model") != MODEL:
                    raise ValueError(f"model_drift:{outer.get('model')}")
                choices = outer.get("choices")
                if not isinstance(choices, list) or len(choices) != 1:
                    raise ValueError("choice_shape")
                text = choices[0].get("message", {}).get("content")
                payload = json.loads(text)
                if not isinstance(payload, dict) or "actions" not in payload:
                    raise ValueError("actions_missing")
                actions = payload["actions"]
                if not isinstance(actions, list) or len(actions) != expected_actions:
                    raise ValueError("action_count")
                if not all(action in ACTIONS for action in actions):
                    raise ValueError("action_vocabulary")
                strategy = payload.get("strategy")
                if strategy is not None and (
                    not isinstance(strategy, str) or len(strategy) > 4000
                ):
                    raise ValueError("strategy_shape")
                latency_ms = round((time.perf_counter() - started) * 1000, 3)
                attempts.append(
                    {
                        "attempt": attempt,
                        "request_id": request_id,
                        "status": "ok",
                        "latency_ms": latency_ms,
                    }
                )
                usage = outer.get("usage", {})
                return {
                    "actions": list(actions),
                    "strategy": strategy,
                    "attempts": attempts,
                    "usage": {
                        "input_tokens": int(usage.get("prompt_tokens", 0)),
                        "output_tokens": int(usage.get("completion_tokens", 0)),
                    },
                    "model": outer.get("model"),
                    "temperature": temperature,
                    "request_id": request_id,
                    "prompt_sha256": hashlib.sha256((system + "\n" + user).encode()).hexdigest(),
                    "response_sha256": payload_sha(payload),
                    "extra_key_count": len(set(payload) - {"actions", "strategy"}),
                    "strategy_present": strategy is not None,
                    "total_latency_ms": round((time.perf_counter() - started_all) * 1000, 3),
                }
            except HTTPError as exc:
                detail = exc.read().decode(errors="replace")[:500]
                attempts.append(
                    {
                        "attempt": attempt,
                        "request_id": request_id,
                        "status": f"http_{exc.code}",
                        "detail_sha256": hashlib.sha256(detail.encode()).hexdigest(),
                        "latency_ms": round((time.perf_counter() - started) * 1000, 3),
                    }
                )
                if (exc.code != 429 and exc.code < 500) or attempt == MAX_ATTEMPTS:
                    raise RuntimeError(f"Z.AI HTTP {exc.code}") from exc
                if exc.code == 429:
                    retry_delay = min(MAX_429_BACKOFF_SECONDS, 10.0 * (2.0 ** (attempt - 1)))
                    retry_after = exc.headers.get("Retry-After")
                    if retry_after:
                        try:
                            retry_delay = max(retry_delay, float(retry_after))
                        except ValueError:
                            pass
            except (URLError, TimeoutError, json.JSONDecodeError, ValueError) as exc:
                attempts.append(
                    {
                        "attempt": attempt,
                        "request_id": request_id,
                        "status": type(exc).__name__,
                        "detail": str(exc)[:160],
                        "latency_ms": round((time.perf_counter() - started) * 1000, 3),
                    }
                )
                if attempt == MAX_ATTEMPTS:
                    raise RuntimeError(f"provider call failed: {phase}: {attempts}") from exc
            time.sleep(retry_delay)
        raise AssertionError("unreachable")


def system_prompt(case_count: int) -> str:
    return (
        "Return one JSON object. It must contain an actions array with exactly "
        f"{case_count} entries, each one of {', '.join(ACTIONS)}. "
        "It may also contain strategy as a concise private working string. "
        "Other keys are ignored. Do not use markdown."
    )


def decision_user(
    *,
    cases: list[dict[str, Any]],
    prior_strategy: str,
    history: list[dict[str, Any]] | None,
    labeled: bool,
    artifact: dict[str, Any] | None,
    phase: str,
) -> str:
    sections = [
        f"Objective: {BEHAVIORAL_OBJECTIVE}",
        f"Task ecology: {ECOLOGY_HINT}",
        f"Phase: {phase}",
    ]
    if artifact is not None:
        sections.append(
            "Public Capability Artifact (production conditions only; no source-private state):\n"
            + json.dumps(artifact, sort_keys=True, separators=(",", ":"))
        )
    elif phase.startswith("source"):
        sections.append(f"Development protocol: {SOURCE_PROTOCOL}")
    elif phase.startswith("description"):
        sections.append(
            "This arm has only unlabeled/sham practice. No outcome-bearing feedback is available. "
            "Do not assume a prior chosen action was correct."
        )
    if prior_strategy:
        sections.append("Prior private strategy:\n" + prior_strategy)
    if history is not None:
        label = "Outcome-bearing local feedback" if labeled else "Unlabeled prior practice"
        sections.append(label + ":\n" + json.dumps(history, sort_keys=True, separators=(",", ":")))
    sections.append(
        "Cases to answer now:\n"
        + json.dumps([public_case(case) for case in cases], sort_keys=True, separators=(",", ":"))
    )
    if "evaluation" in phase:
        sections.append(
            "These are held-out calibration cases. No correctness feedback from evaluation will be returned."
        )
    else:
        sections.append("Return choices and, if useful, an updated private strategy.")
    return "\n\n".join(sections)


def resolved_strategy(result: dict[str, Any], previous: str) -> str:
    strategy = result["strategy"]
    return previous if strategy is None else str(strategy)


def call_record(result: dict[str, Any], resolved: str) -> dict[str, Any]:
    return {
        "model": result["model"],
        "temperature": result["temperature"],
        "request_id": result["request_id"],
        "prompt_sha256": result["prompt_sha256"],
        "response_sha256": result["response_sha256"],
        "strategy_sha256": hashlib.sha256(resolved.encode()).hexdigest(),
        "strategy_present": result["strategy_present"],
        "extra_key_count": result["extra_key_count"],
        "physical_attempts": len(result["attempts"]),
        "attempt_log": result["attempts"],
        "usage": result["usage"],
        "total_latency_ms": result["total_latency_ms"],
    }


def chunks(cases: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    return [cases[index : index + EVAL_CHUNK_SIZE] for index in range(0, len(cases), EVAL_CHUNK_SIZE)]


def run_development_arm(
    client: Client,
    *,
    arm: str,
    dev_cases: list[dict[str, Any]],
    eval_cases: list[dict[str, Any]],
    artifact: dict[str, Any] | None,
    labeled: bool,
) -> dict[str, Any]:
    first = dev_cases[:BATCH_SIZE]
    second = dev_cases[BATCH_SIZE:]
    calls: list[dict[str, Any]] = []

    r1 = client.complete(
        phase=f"{arm}/round1",
        system=system_prompt(len(first)),
        user=decision_user(
            cases=first,
            prior_strategy="",
            history=None,
            labeled=labeled,
            artifact=artifact,
            phase=f"{arm}_development_round1",
        ),
        expected_actions=len(first),
        temperature=TEMPERATURE,
    )
    a1 = list(r1["actions"])
    strategy = resolved_strategy(r1, "")
    calls.append(call_record(r1, strategy))

    history1 = labeled_feedback(first, a1) if labeled else unlabeled_history(first, a1)
    r2 = client.complete(
        phase=f"{arm}/round2",
        system=system_prompt(len(second)),
        user=decision_user(
            cases=second,
            prior_strategy=strategy,
            history=history1,
            labeled=labeled,
            artifact=artifact,
            phase=f"{arm}_development_round2",
        ),
        expected_actions=len(second),
        temperature=TEMPERATURE,
    )
    a2 = list(r2["actions"])
    strategy = resolved_strategy(r2, strategy)
    calls.append(call_record(r2, strategy))

    history2 = labeled_feedback(second, a2) if labeled else unlabeled_history(second, a2)
    eval_actions: list[str] = []
    for chunk_index, eval_chunk in enumerate(chunks(eval_cases), start=1):
        result = client.complete(
            phase=f"{arm}/evaluation{chunk_index}",
            system=system_prompt(len(eval_chunk)),
            user=decision_user(
                cases=eval_chunk,
                prior_strategy=strategy,
                history=history2 if chunk_index == 1 else None,
                labeled=labeled,
                artifact=artifact,
                phase=f"{arm}_evaluation_{chunk_index}",
            ),
            expected_actions=len(eval_chunk),
            temperature=TEMPERATURE,
        )
        eval_actions.extend(result["actions"])
        strategy = resolved_strategy(result, strategy)
        calls.append(call_record(result, strategy))

    return {
        "development_batch_scores": [score_actions(first, a1), score_actions(second, a2)],
        "final_score": score_actions(eval_cases, eval_actions),
        "logical_calls": len(calls),
        "physical_attempts": sum(call["physical_attempts"] for call in calls),
        "calls": calls,
    }


def run_fresh_arm(client: Client, *, eval_cases: list[dict[str, Any]]) -> dict[str, Any]:
    calls: list[dict[str, Any]] = []
    strategy = ""
    eval_actions: list[str] = []
    for chunk_index, eval_chunk in enumerate(chunks(eval_cases), start=1):
        result = client.complete(
            phase=f"fresh/evaluation{chunk_index}",
            system=system_prompt(len(eval_chunk)),
            user=decision_user(
                cases=eval_chunk,
                prior_strategy=strategy,
                history=None,
                labeled=False,
                artifact=None,
                phase=f"fresh_evaluation_{chunk_index}",
            ),
            expected_actions=len(eval_chunk),
            temperature=TEMPERATURE,
        )
        eval_actions.extend(result["actions"])
        strategy = resolved_strategy(result, strategy)
        calls.append(call_record(result, strategy))
    return {
        "development_batch_scores": [],
        "final_score": score_actions(eval_cases, eval_actions),
        "logical_calls": len(calls),
        "physical_attempts": sum(call["physical_attempts"] for call in calls),
        "calls": calls,
    }


def make_capability_artifact(*, pair_index: int, source_record: dict[str, Any]) -> dict[str, Any]:
    return make_artifact(
        artifact_id=f"d2c-r1-artifact-{pair_index:03d}",
        behavioral_objective={"text": BEHAVIORAL_OBJECTIVE, "actions": list(ACTIONS)},
        source_public_evidence={
            "calibration_only": True,
            "development_episode_count": SOURCE_DEV_COUNT,
            "development_batch_accuracy": source_record["development_batch_scores"],
            "heldout_calibration_accuracy": source_record["final_score"],
            "claim": "source capability observed under local outcome-bearing development",
        },
        required_environment={
            "feature_names": ["f0", "f1", "f2", "f3"],
            "feature_domain": "integer_0_through_7",
            "action_vocabulary": list(ACTIONS),
            "hidden_policy_owned_by_environment": True,
        },
        required_task_ecology={
            "public_family_description": ECOLOGY_HINT,
            "source_and_destination_examples_must_be_disjoint": True,
        },
        development_protocol={
            "protocol": SOURCE_PROTOCOL,
            "rounds": 2,
            "cases_per_round": BATCH_SIZE,
            "destination_local_examples_only": True,
        },
        feedback_contract={
            "type": "objective_outcome_bearing",
            "after_each_development_batch": True,
            "fields": ["chosen_action", "correct", "correct_action"],
        },
        memory_update_contract={
            "private_strategy": True,
            "updated_between_batches": True,
            "exportable": False,
        },
        provider_contract={
            "provider": "Z.AI",
            "calibration_model": MODEL,
            "calibration_temperature": TEMPERATURE,
            "evaluation_chunk_size": EVAL_CHUNK_SIZE,
            "confirmatory_settings_frozen": False,
        },
        resource_requirements={
            "development_episodes": DEST_DEV_COUNT,
            "development_logical_calls": 2,
            "calibration_evaluation_logical_calls": 3,
        },
        stopping_rule={"stop_after_development_episodes": DEST_DEV_COUNT},
        evaluation_contract={
            "calibration_holdout_case_count": EVAL_COUNT,
            "evaluation_chunk_size": EVAL_CHUNK_SIZE,
            "development_cases_excluded": True,
            "confirmatory_holdout_not_created_or_used": True,
        },
        known_dependencies=["structured_json_provider_output", "objective_local_feedback"],
        known_failure_conditions=[
            "provider_contract_instability",
            "artifact_export_boundary_failure",
            "source_development_at_floor",
        ],
        permitted_use_modes=["destination_local_development", "calibration_only"],
        provenance={
            "study": "D2-0-transport-repair-1",
            "pair_index": pair_index,
            "source_evidence_is_aggregate_only": True,
            "production_historical_substrate_enabled": False,
        },
    )


def run_pair(client: Client, pair_index: int) -> dict[str, Any]:
    pair_seed = 720000 + pair_index * 10
    source_seed = pair_seed + 1
    dest_seed = pair_seed + 2
    eval_seed = pair_seed + 3
    policy = policy_for(pair_seed)

    source_agent_id = f"d2c-source-agent-{pair_index:03d}"
    destination_agent_ids = {
        "fresh": f"d2c-dest-fresh-{pair_index:03d}",
        "description_only": f"d2c-dest-description-{pair_index:03d}",
        "reproduced": f"d2c-dest-reproduced-{pair_index:03d}",
    }

    source_dev = generate_cases(
        rng_seed=source_seed,
        count=SOURCE_DEV_COUNT,
        prefix=f"src-{pair_index:03d}",
        policy=policy,
    )
    source_features = features_set(source_dev)
    dest_dev = generate_cases(
        rng_seed=dest_seed,
        count=DEST_DEV_COUNT,
        prefix=f"dst-{pair_index:03d}",
        policy=policy,
        exclude_features=source_features,
    )
    all_dev_features = source_features | features_set(dest_dev)
    eval_cases = generate_cases(
        rng_seed=eval_seed,
        count=EVAL_COUNT,
        prefix=f"eval-{pair_index:03d}",
        policy=policy,
        exclude_features=all_dev_features,
    )

    source = run_development_arm(
        client,
        arm="source_developed",
        dev_cases=source_dev,
        eval_cases=eval_cases,
        artifact=None,
        labeled=True,
    )
    artifact = make_capability_artifact(pair_index=pair_index, source_record=source)
    audit = assert_export_safe(
        artifact,
        source_agent_ids=[source_agent_id],
        source_seeds=[pair_seed, source_seed, eval_seed],
        source_example_ids=[case["case_id"] for case in source_dev],
        hidden_truth_tokens=[policy.truth_token],
    )

    reproduced = run_development_arm(
        client,
        arm="reproduced",
        dev_cases=dest_dev,
        eval_cases=eval_cases,
        artifact=artifact,
        labeled=True,
    )
    description = run_development_arm(
        client,
        arm="description_only",
        dev_cases=dest_dev,
        eval_cases=eval_cases,
        artifact=None,
        labeled=False,
    )
    fresh = run_fresh_arm(client, eval_cases=eval_cases)

    assert reproduced["logical_calls"] == description["logical_calls"] == source["logical_calls"] == 5
    assert fresh["logical_calls"] == 3
    assert source_features.isdisjoint(features_set(dest_dev))
    assert all_dev_features.isdisjoint(features_set(eval_cases))

    return {
        "pair_index": pair_index,
        "pair_seed_public_hash": hashlib.sha256(str(pair_seed).encode()).hexdigest(),
        "source_identity_sha256": hashlib.sha256(source_agent_id.encode()).hexdigest(),
        "destination_identity_sha256": {
            key: hashlib.sha256(value.encode()).hexdigest()
            for key, value in destination_agent_ids.items()
        },
        "policy_private_sha256": sha256(policy.private_record()),
        "development_example_overlap_count": len(source_features & features_set(dest_dev)),
        "evaluation_development_overlap_count": len(all_dev_features & features_set(eval_cases)),
        "artifact": artifact,
        "artifact_audit": audit.as_dict(),
        "arms": {
            "fresh": fresh,
            "description_only": description,
            "reproduced": reproduced,
            "source_developed": source,
        },
    }


def run_sampling_characterization(client: Client) -> dict[str, Any]:
    policy = policy_for(719900)
    cases = generate_cases(rng_seed=719901, count=8, prefix="sampling", policy=policy)
    system = system_prompt(len(cases))
    user = decision_user(
        cases=cases,
        prior_strategy="",
        history=None,
        labeled=False,
        artifact=None,
        phase="sampling_characterization",
    )
    raw: list[dict[str, Any]] = []
    retry_reasons: dict[str, int] = {}
    extra_key_total = 0
    strategy_omission_total = 0
    for temperature in SAMPLING_TEMPERATURES:
        for replicate in range(SAMPLING_REPLICATES):
            result = client.complete(
                phase=f"sampling/{temperature}/{replicate}",
                system=system,
                user=user,
                expected_actions=len(cases),
                temperature=temperature,
            )
            for attempt in result["attempts"][:-1]:
                status = str(attempt["status"])
                retry_reasons[status] = retry_reasons.get(status, 0) + 1
            extra_key_total += int(result["extra_key_count"])
            strategy_omission_total += int(not result["strategy_present"])
            raw.append(
                {
                    "temperature": temperature,
                    "replicate": replicate,
                    "valid": True,
                    "actions": list(result["actions"]),
                    "score": score_actions(cases, result["actions"]),
                    "physical_attempts": len(result["attempts"]),
                }
            )
    summary = sampling_summary(raw)
    total_logical = len(SAMPLING_TEMPERATURES) * SAMPLING_REPLICATES
    total_physical = sum(int(item["physical_attempts"]) for item in summary.values())
    return {
        "suite_schema": "d2-0-sampling-characterization-r1-v0.1",
        "model": MODEL,
        "temperatures": list(SAMPLING_TEMPERATURES),
        "replicates_per_temperature": SAMPLING_REPLICATES,
        "case_count": len(cases),
        "public_case_batch_sha256": payload_sha([public_case(case) for case in cases]),
        "summary": summary,
        "logical_calls": total_logical,
        "physical_attempts": total_physical,
        "retry_frequency": (total_physical - total_logical) / total_physical,
        "retry_reasons": retry_reasons,
        "extra_key_total": extra_key_total,
        "strategy_omission_total": strategy_omission_total,
        "confirmatory_setting_selected": False,
    }


def aggregate(pair_records: list[dict[str, Any]], sampling: dict[str, Any]) -> dict[str, Any]:
    descriptive = descriptive_summary(pair_records)
    development_logical = sum(
        int(arm["logical_calls"])
        for pair in pair_records
        for arm in pair["arms"].values()
    )
    development_physical = sum(
        int(arm["physical_attempts"])
        for pair in pair_records
        for arm in pair["arms"].values()
    )
    total_logical = development_logical + int(sampling["logical_calls"])
    total_physical = development_physical + int(sampling["physical_attempts"])
    retry_reasons: dict[str, int] = dict(sampling["retry_reasons"])
    extra_key_total = int(sampling["extra_key_total"])
    strategy_omission_total = int(sampling["strategy_omission_total"])
    for pair in pair_records:
        for arm in pair["arms"].values():
            for call in arm["calls"]:
                extra_key_total += int(call["extra_key_count"])
                strategy_omission_total += int(not call["strategy_present"])
                for attempt in call["attempt_log"][:-1]:
                    status = str(attempt["status"])
                    retry_reasons[status] = retry_reasons.get(status, 0) + 1
    return {
        "schema": "d2-0-calibration-report-r1-v0.1",
        "status": "completed_development_only_not_confirmatory",
        "transport_repair": 1,
        "prior_incomplete_workflow": 31889041385,
        "model": MODEL,
        "development_temperature": TEMPERATURE,
        "pair_count": PAIR_COUNT,
        "development_episodes_per_developed_arm": SOURCE_DEV_COUNT,
        "evaluation_cases_per_pair": EVAL_COUNT,
        "evaluation_chunk_size": EVAL_CHUNK_SIZE,
        "descriptive": descriptive,
        "source_learning_curves": [
            pair["arms"]["source_developed"]["development_batch_scores"]
            + [pair["arms"]["source_developed"]["final_score"]]
            for pair in pair_records
        ],
        "reproduced_learning_curves": [
            pair["arms"]["reproduced"]["development_batch_scores"]
            + [pair["arms"]["reproduced"]["final_score"]]
            for pair in pair_records
        ],
        "description_only_learning_curves": [
            pair["arms"]["description_only"]["development_batch_scores"]
            + [pair["arms"]["description_only"]["final_score"]]
            for pair in pair_records
        ],
        "sampling_characterization": sampling,
        "integrity": {
            "source_destination_development_overlap_total": sum(
                pair["development_example_overlap_count"] for pair in pair_records
            ),
            "development_evaluation_overlap_total": sum(
                pair["evaluation_development_overlap_count"] for pair in pair_records
            ),
            "all_artifact_audits_pass": all(pair["artifact_audit"]["passed"] for pair in pair_records),
            "description_reproduced_logical_calls_equal": all(
                pair["arms"]["description_only"]["logical_calls"]
                == pair["arms"]["reproduced"]["logical_calls"]
                for pair in pair_records
            ),
            "all_developed_arm_logical_calls_five": all(
                pair["arms"][arm]["logical_calls"] == 5
                for pair in pair_records
                for arm in ("source_developed", "reproduced", "description_only")
            ),
            "all_fresh_logical_calls_three": all(
                pair["arms"]["fresh"]["logical_calls"] == 3 for pair in pair_records
            ),
            "evaluation_feedback_returned": False,
            "production_historical_substrate_enabled": False,
        },
        "call_accounting": {
            "logical_calls_total": total_logical,
            "physical_attempts_total": total_physical,
            "retry_frequency": (total_physical - total_logical) / total_physical,
            "retry_reasons": retry_reasons,
            "extra_key_total": extra_key_total,
            "strategy_omission_total": strategy_omission_total,
        },
        "power_inputs": {
            "paired_difference_sd_p0": descriptive["paired_contrasts"]["p0_source_minus_fresh"]["sample_sd"],
            "paired_difference_sd_p1": descriptive["paired_contrasts"][
                "p1_reproduced_minus_description"
            ]["sample_sd"],
            "paired_difference_sd_p2": descriptive["paired_contrasts"][
                "p2_reproduced_minus_source"
            ]["sample_sd"],
            "note": "Development-only empirical variance inputs; not confirmatory thresholds or final N.",
        },
        "confirmatory_outcomes_included": False,
        "confirmatory_holdout_created_or_used": False,
        "production_historical_substrate_enabled": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    key = os.environ.get("ZAI_API_KEY", "")
    if not key:
        raise SystemExit("ZAI_API_KEY required for D2-0 calibration")
    args.output_dir.mkdir(parents=True, exist_ok=True)

    client = Client(key)
    sampling = run_sampling_characterization(client)
    completed: dict[int, dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
        futures = {pool.submit(run_pair, client, index): index for index in range(PAIR_COUNT)}
        for future in as_completed(futures):
            index = futures[future]
            completed[index] = future.result()
            print(f"D2_CALIBRATION_R1_PROGRESS {len(completed)}/{PAIR_COUNT} pair={index}", flush=True)
    pairs = [completed[index] for index in range(PAIR_COUNT)]
    report = aggregate(pairs, sampling)
    assert report["call_accounting"]["logical_calls_total"] == 162

    output = {
        "schema": "d2-0-calibration-output-r1-v0.1",
        "report": report,
        "pairs": pairs,
        "production_historical_substrate_enabled": False,
    }
    output_path = args.output_dir / "d2-0-calibration-output.json"
    output_path.write_bytes(canonical_bytes(output))
    report_path = args.output_dir / "d2-0-calibration-report.json"
    report_path.write_bytes(canonical_bytes(report))
    manifest = {
        "schema": "d2-0-calibration-manifest-r1-v0.1",
        "output_sha256": hashlib.sha256(output_path.read_bytes()).hexdigest(),
        "report_sha256": hashlib.sha256(report_path.read_bytes()).hexdigest(),
        "model": MODEL,
        "development_temperature": TEMPERATURE,
        "pair_count": PAIR_COUNT,
        "evaluation_chunk_size": EVAL_CHUNK_SIZE,
        "transport_repair": 1,
        "prior_incomplete_workflow": 31889041385,
        "logical_calls_total": 162,
        "development_only": True,
        "confirmatory_evidence": False,
        "production_historical_substrate_enabled": False,
    }
    (args.output_dir / "manifest.json").write_bytes(canonical_bytes(manifest))
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
