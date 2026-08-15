#!/usr/bin/env python3
"""Execute D2-0 learnability revision 2 as development-only calibration."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from d2_artifact_core import assert_export_safe, make_artifact
from d2_calibration_r2_core import (
    ACTIONS,
    CHANCE_SCORE,
    descriptive_summary,
    development_readiness,
    features_set,
    generate_balanced_cases,
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
SOURCE_DEV_COUNT = 40
DEST_DEV_COUNT = 40
EVAL_COUNT = 32
BATCH_SIZE = 8
EVAL_CHUNK_SIZE = 8
MAX_ATTEMPTS = 8
MAX_TOKENS = 768
CONCURRENCY = 4
MIN_REQUEST_INTERVAL_SECONDS = 0.35
MAX_429_BACKOFF_SECONDS = 90.0

BEHAVIORAL_OBJECTIVE = (
    "Choose exactly one action from KAPPA, MICA, ORBIT, VELA for each four-feature integer case. "
    "Each Field owns a fixed hidden local policy."
)
ECOLOGY_HINT = (
    "The registered learnability-revision family has exactly two hidden controlling feature "
    "coordinates among f0..f3. Each controlling coordinate contributes one latent bit: 0 below 4 "
    "and 1 at or above 4. The two-bit state is mapped one-to-one to the four opaque action tokens. "
    "The controlling coordinates and action relabeling are local secrets and differ by Field."
)
DEVELOPMENT_PROTOCOL = (
    "Use local outcome-bearing feedback as evidence. Across batches, compare candidate controlling "
    "feature pairs, infer the four-state action relabeling, and maintain a concise private hypothesis. "
    "Prefer rules that explain all labeled examples; retain alternatives when evidence is ambiguous. "
    "Do not memorize case IDs as the policy."
)


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def payload_sha(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Client:
    def __init__(self, key: str) -> None:
        if not key.strip():
            raise ValueError("ZAI_API_KEY is empty")
        self.key = key
        self.rng = random.Random(2026081504)
        self.rng_lock = threading.Lock()
        self.rate_lock = threading.Lock()
        self.next_request_at = 0.0

    def _request_id(self, phase: str, attempt: int) -> str:
        with self.rng_lock:
            nonce = self.rng.getrandbits(64)
        safe = phase.replace("/", "-")[-40:]
        return f"d2r2-{safe}-{attempt}-{nonce:016x}"

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
                    "User-Agent": "resonance-world-d2-calibration-r2/0.1",
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
                    not isinstance(strategy, str) or len(strategy) > 6000
                ):
                    raise ValueError("strategy_shape")
                attempts.append(
                    {
                        "attempt": attempt,
                        "request_id": request_id,
                        "status": "ok",
                        "latency_ms": round((time.perf_counter() - started) * 1000, 3),
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
        "Return one JSON object with an actions array containing exactly "
        f"{case_count} entries, each one of {', '.join(ACTIONS)}. "
        "You may also include strategy as a concise private working string. "
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
        sections.append(f"Development protocol: {DEVELOPMENT_PROTOCOL}")
    elif phase.startswith("description"):
        sections.append(
            "This control receives unlabeled practice only. No correctness or correct-action "
            "feedback is available; do not treat prior choices as labels."
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
            "These are held-out development-calibration cases. Their correctness will not be "
            "returned to the agent."
        )
    else:
        sections.append(
            "Return choices and, if useful, an updated private strategy. Use feedback to revise "
            "the hypothesis rather than memorizing case IDs."
        )
    return "\n\n".join(sections)


def resolved_strategy(result: dict[str, Any], previous: str) -> str:
    strategy = result["strategy"]
    return previous if strategy is None else str(strategy)


def call_record(result: dict[str, Any], strategy: str) -> dict[str, Any]:
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


def split_batches(cases: list[dict[str, Any]], size: int) -> list[list[dict[str, Any]]]:
    if len(cases) % size:
        raise ValueError("case count not divisible by batch size")
    return [cases[i : i + size] for i in range(0, len(cases), size)]


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

    for batch_index, batch in enumerate(split_batches(dev_cases, BATCH_SIZE), start=1):
        result = client.complete(
            phase=f"{arm}/development{batch_index}",
            system=system_prompt(len(batch)),
            user=decision_user(
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
        strategy = resolved_strategy(result, strategy)
        calls.append(call_record(result, strategy))
        batch_scores.append(score_actions(batch, actions))
        prior_history = (
            labeled_feedback(batch, actions)
            if labeled
            else unlabeled_history(batch, actions)
        )

    eval_actions: list[str] = []
    for chunk_index, chunk in enumerate(split_batches(eval_cases, EVAL_CHUNK_SIZE), start=1):
        result = client.complete(
            phase=f"{arm}/evaluation{chunk_index}",
            system=system_prompt(len(chunk)),
            user=decision_user(
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
        strategy = resolved_strategy(result, strategy)
        calls.append(call_record(result, strategy))

    return {
        "development_batch_scores": batch_scores,
        "final_score": score_actions(eval_cases, eval_actions),
        "logical_calls": len(calls),
        "physical_attempts": sum(call["physical_attempts"] for call in calls),
        "calls": calls,
    }


def run_fresh_arm(client: Client, *, eval_cases: list[dict[str, Any]]) -> dict[str, Any]:
    calls: list[dict[str, Any]] = []
    strategy = ""
    eval_actions: list[str] = []
    for chunk_index, chunk in enumerate(split_batches(eval_cases, EVAL_CHUNK_SIZE), start=1):
        result = client.complete(
            phase=f"fresh/evaluation{chunk_index}",
            system=system_prompt(len(chunk)),
            user=decision_user(
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
        strategy = resolved_strategy(result, strategy)
        calls.append(call_record(result, strategy))
    return {
        "development_batch_scores": [],
        "final_score": score_actions(eval_cases, eval_actions),
        "logical_calls": len(calls),
        "physical_attempts": sum(call["physical_attempts"] for call in calls),
        "calls": calls,
    }


def build_artifact(pair_index: int, source_public_score: float) -> dict[str, Any]:
    return make_artifact(
        artifact_id=f"d2-r2-capability-{pair_index:02d}",
        behavioral_objective={
            "action_vocabulary": list(ACTIONS),
            "objective": BEHAVIORAL_OBJECTIVE,
        },
        source_public_evidence={
            "registered_source_development_completed": True,
            "heldout_development_calibration_score_band": (
                "at_or_above_chance" if source_public_score >= CHANCE_SCORE else "below_chance"
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
            "recommended_contents": "candidate controlling coordinates and action-state mapping",
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
            "evaluation_cases": EVAL_COUNT,
            "logical_calls": DEST_DEV_COUNT // BATCH_SIZE + EVAL_COUNT // EVAL_CHUNK_SIZE,
        },
        stopping_rule={
            "development_batches_are_fixed": True,
            "no_outcome_adaptive_stopping": True,
        },
        evaluation_contract={
            "heldout_development_calibration_cases": EVAL_COUNT,
            "no_evaluation_feedback": True,
            "confirmatory_holdout": "not_created_or_used",
        },
        known_dependencies=[
            "destination must expose four integer features with the registered local-policy family",
            "outcome-bearing feedback must be available only during development",
        ],
        known_failure_conditions=[
            "insufficient labeled local development evidence",
            "provider fails structured action contract",
        ],
        permitted_use_modes=["local_development", "fresh_destination_reproduction_calibration"],
        provenance={
            "program_issue": 167,
            "revision": "D2-0 learnability revision 2",
            "production_historical_substrate_enabled": False,
        },
    )


def run_pair(client: Client, pair_index: int) -> dict[str, Any]:
    pair_seed = 840000 + pair_index * 100
    source_seed = pair_seed + 1
    destination_seed = pair_seed + 2
    eval_seed = pair_seed + 3
    policy = policy_for(pair_seed)

    source_cases = generate_balanced_cases(
        rng_seed=source_seed,
        count=SOURCE_DEV_COUNT,
        prefix=f"r2-source-p{pair_index:02d}",
        policy=policy,
    )
    source_features = features_set(source_cases)
    destination_cases = generate_balanced_cases(
        rng_seed=destination_seed,
        count=DEST_DEV_COUNT,
        prefix=f"r2-destination-p{pair_index:02d}",
        policy=policy,
        exclude_features=source_features,
    )
    destination_features = features_set(destination_cases)
    eval_cases = generate_balanced_cases(
        rng_seed=eval_seed,
        count=EVAL_COUNT,
        prefix=f"r2-eval-p{pair_index:02d}",
        policy=policy,
        exclude_features=source_features | destination_features,
    )
    eval_features = features_set(eval_cases)

    source = run_development_arm(
        client,
        arm=f"source-p{pair_index:02d}",
        dev_cases=source_cases,
        eval_cases=eval_cases,
        artifact=None,
        labeled=True,
    )

    artifact = build_artifact(pair_index, float(source["final_score"]))
    source_agent_id = f"source-agent-r2-p{pair_index:02d}-{source_seed}"
    audit = assert_export_safe(
        artifact,
        source_agent_ids=[source_agent_id],
        source_seeds=[source_seed, pair_seed],
        source_example_ids=[case["case_id"] for case in source_cases],
        hidden_truth_tokens=[policy.truth_token],
    )

    reproduced = run_development_arm(
        client,
        arm=f"reproduced-p{pair_index:02d}",
        dev_cases=destination_cases,
        eval_cases=eval_cases,
        artifact=artifact,
        labeled=True,
    )
    description = run_development_arm(
        client,
        arm=f"description-p{pair_index:02d}",
        dev_cases=destination_cases,
        eval_cases=eval_cases,
        artifact=None,
        labeled=False,
    )
    fresh = run_fresh_arm(client, eval_cases=eval_cases)

    return {
        "pair_index": pair_index,
        "pair_public_id": f"d2-r2-pair-{pair_index:02d}",
        "private_policy_sha256": sha256(policy.private_record()),
        "source_destination_development_overlap": len(source_features & destination_features),
        "development_evaluation_overlap": len(
            (source_features | destination_features) & eval_features
        ),
        "artifact": artifact,
        "artifact_audit": audit.as_dict(),
        "arms": {
            "fresh": fresh,
            "description_only": description,
            "reproduced": reproduced,
            "source_developed": source,
        },
    }


def run_sampling_characterization(client: Client) -> list[dict[str, Any]]:
    policy = policy_for(999100)
    cases = generate_balanced_cases(
        rng_seed=999101,
        count=8,
        prefix="r2-sampling",
        policy=policy,
    )
    records: list[dict[str, Any]] = []
    for temperature in SAMPLING_TEMPERATURES:
        for replicate in range(SAMPLING_REPLICATES):
            result = client.complete(
                phase=f"sampling/t{temperature}/r{replicate}",
                system=system_prompt(len(cases)),
                user=decision_user(
                    cases=cases,
                    prior_strategy="",
                    history=None,
                    labeled=False,
                    artifact=None,
                    phase="sampling_characterization",
                ),
                expected_actions=len(cases),
                temperature=temperature,
            )
            records.append(
                {
                    "temperature": temperature,
                    "replicate": replicate,
                    "valid": True,
                    "actions": list(result["actions"]),
                    "score": score_actions(cases, result["actions"]),
                    "physical_attempts": len(result["attempts"]),
                }
            )
    return records


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default="output/d2-calibration-r2")
    args = parser.parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    client = Client(os.environ.get("ZAI_API_KEY", ""))
    sampling_records = run_sampling_characterization(client)

    pair_records: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
        futures = {pool.submit(run_pair, client, index): index for index in range(PAIR_COUNT)}
        for future in as_completed(futures):
            pair_records.append(future.result())
    pair_records.sort(key=lambda row: row["pair_index"])

    summary = descriptive_summary(pair_records)
    readiness = development_readiness(pair_records)
    sampling = sampling_summary(sampling_records)

    overlaps_sd = sum(int(row["source_destination_development_overlap"]) for row in pair_records)
    overlaps_eval = sum(int(row["development_evaluation_overlap"]) for row in pair_records)
    all_audits = all(bool(row["artifact_audit"]["passed"]) for row in pair_records)
    equal_calls = all(
        row["arms"]["description_only"]["logical_calls"]
        == row["arms"]["reproduced"]["logical_calls"]
        for row in pair_records
    )
    expected_developed_calls = SOURCE_DEV_COUNT // BATCH_SIZE + EVAL_COUNT // EVAL_CHUNK_SIZE
    expected_fresh_calls = EVAL_COUNT // EVAL_CHUNK_SIZE
    developed_call_gate = all(
        row["arms"][arm]["logical_calls"] == expected_developed_calls
        for row in pair_records
        for arm in ("source_developed", "reproduced", "description_only")
    )
    fresh_call_gate = all(
        row["arms"]["fresh"]["logical_calls"] == expected_fresh_calls
        for row in pair_records
    )
    pair_logical = sum(
        int(arm["logical_calls"])
        for row in pair_records
        for arm in row["arms"].values()
    )
    sampling_logical = len(sampling_records)
    logical_total = pair_logical + sampling_logical
    physical_total = sum(
        int(arm["physical_attempts"])
        for row in pair_records
        for arm in row["arms"].values()
    ) + sum(int(row["physical_attempts"]) for row in sampling_records)

    output = {
        "status": "completed_development_only_not_confirmatory",
        "revision": "D2-0 learnability revision 2",
        "model": MODEL,
        "temperature": TEMPERATURE,
        "pair_count": PAIR_COUNT,
        "source_development_cases": SOURCE_DEV_COUNT,
        "destination_development_cases": DEST_DEV_COUNT,
        "evaluation_cases": EVAL_COUNT,
        "batch_size": BATCH_SIZE,
        "evaluation_chunk_size": EVAL_CHUNK_SIZE,
        "pair_records": pair_records,
        "sampling_records": sampling_records,
        "production_historical_substrate_enabled": False,
        "confirmatory_holdout_created_or_used": False,
    }
    output_path = output_dir / "d2-0-r2-output.json"
    output_path.write_bytes(canonical_bytes(output))

    report = {
        "status": "completed_development_only_not_confirmatory",
        "revision": "D2-0 learnability revision 2",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "model": MODEL,
        "temperature": TEMPERATURE,
        "chance_score": CHANCE_SCORE,
        "pair_count": PAIR_COUNT,
        "descriptive_summary": summary,
        "development_readiness": readiness,
        "sampling_summary": sampling,
        "integrity": {
            "source_destination_development_overlap_total": overlaps_sd,
            "development_evaluation_overlap_total": overlaps_eval,
            "all_artifact_audits_pass": all_audits,
            "description_reproduced_logical_calls_equal": equal_calls,
            "all_developed_arm_logical_calls_expected": developed_call_gate,
            "all_fresh_logical_calls_expected": fresh_call_gate,
            "evaluation_feedback_returned": False,
            "confirmatory_holdout_created_or_used": False,
        },
        "call_accounting": {
            "paired_panel_logical_calls": pair_logical,
            "sampling_logical_calls": sampling_logical,
            "logical_calls_total": logical_total,
            "physical_attempts_total": physical_total,
        },
        "handoff": (
            "eligible_for_confirmatory_design_freeze"
            if readiness["all_gates_pass"]
            else "revise_development_substrate_again"
        ),
        "confirmatory_evidence": False,
        "production_historical_substrate_enabled": False,
    }
    expected_logical_total = PAIR_COUNT * (3 * expected_developed_calls + expected_fresh_calls)
    expected_logical_total += len(SAMPLING_TEMPERATURES) * SAMPLING_REPLICATES
    assert logical_total == expected_logical_total
    assert overlaps_sd == 0
    assert overlaps_eval == 0
    assert all_audits
    assert equal_calls
    assert developed_call_gate
    assert fresh_call_gate

    report_path = output_dir / "d2-0-r2-report.json"
    report_path.write_bytes(canonical_bytes(report))

    manifest = {
        "schema": "d2-0-r2-development-calibration-manifest-v0.1",
        "development_only": True,
        "confirmatory_evidence": False,
        "revision": "D2-0 learnability revision 2",
        "model": MODEL,
        "temperature": TEMPERATURE,
        "logical_calls_total": logical_total,
        "physical_attempts_total": physical_total,
        "output_sha256": file_sha256(output_path),
        "report_sha256": file_sha256(report_path),
        "production_historical_substrate_enabled": False,
    }
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_bytes(canonical_bytes(manifest))

    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
