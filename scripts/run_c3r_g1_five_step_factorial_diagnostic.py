"""G1 offline-first factorial diagnosis of model-authored five-step policies.

Four predeclared configurations (low/high x 4096/8192 output tokens) see
IDENTICAL two-example tasks per context. Each reserved attempt is independent:
no retry, no repair, no target or output text in public reports. This is a
source-induction DIAGNOSTIC, not agent-retention evidence.
"""

from __future__ import annotations

import argparse
import json
import hashlib
import os
import re
import statistics
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from run_c3r_g1_model_induced_five_step_live import (
    CODES,
    MODEL,
    _induce_prompt,
    _manifest,
)
from run_c3r_g1_three_step_procedure_live import (
    SlotJournal,
    _digest,
    _run_dir,
    _write_once,
)

from resonance_world.c3r_g1_model_boundary import ModelChoiceCompletion
from resonance_world.c3r_g1_zai_transport import PhysicalSendLedger, ZaiStandardModelPort

SCHEMA = "c3r-g1-five-step-factorial-diagnostics-v0.1"
CONDITIONS = (
    ("low", 4096),
    ("low", 8192),
    ("high", 4096),
    ("high", 8192),
)
MAX_CONTEXTS = 8
PRESCRIBED = MAX_CONTEXTS * len(CONDITIONS)
FAILURE_CLASSES = frozenset((
    "TimeoutError", "ProviderTransportRejected", "ProviderCircuitOpen",
    "ProviderBudgetExhausted", "ValueError", "TypeError", "RuntimeError",
    "OSError", "ConnectionError",
))


def _condition(effort: str, cap: int) -> str:
    return f"{effort}-{cap}"


def _attempt(prompt: str, target: str, effort: str, cap: int,
             factory) -> dict[str, object]:
    started = time.monotonic()
    try:
        response = factory(effort, cap).complete_prompt(prompt)
        if not isinstance(response, ModelChoiceCompletion) or response.model_id != MODEL:
            raise ValueError("unexpected model adapter result")
        answer = response.output.strip()
        finish = response.finish_reason
        usage = response.completion_tokens_reported
        if finish == "length" or (
            finish != "stop" and not answer and usage is not None and usage >= cap
        ):
            outcome = "length_exhausted"
        elif finish != "stop":
            outcome = "non_stop_finish"
        elif re.fullmatch(r"[AB]{5}", answer) is None:
            outcome = "invalid_format"
        elif answer == target:
            outcome = "valid_correct"
        else:
            outcome = "valid_wrong"
        return {
            "outcome": outcome,
            "finish_reason": finish if finish in (
                "stop", "length", "tool_calls", "content_filter", "other",
            ) else "not_reported",
            "output_length": len(answer),
            "prompt_tokens": response.prompt_tokens_reported,
            "completion_tokens": usage,
            "reasoning_tokens": response.reasoning_tokens_reported,
            "latency_ms": round((time.monotonic() - started) * 1000, 1),
            "failure_class": None,
        }
    except Exception as error:
        cls = type(error).__name__
        return {
            "outcome": "provider_error",
            "finish_reason": "not_reported",
            "output_length": None,
            "prompt_tokens": None,
            "completion_tokens": None,
            "reasoning_tokens": None,
            "latency_ms": round((time.monotonic() - started) * 1000, 1),
            "failure_class": cls if cls in FAILURE_CLASSES else "OtherProviderError",
        }


def _summary(rows: list[dict[str, object]]) -> dict[str, object]:
    latencies = [
        r["latency_ms"] for r in rows if type(r["latency_ms"]) in (int, float)
    ]
    tokens = {}
    for key in ("prompt_tokens", "completion_tokens", "reasoning_tokens"):
        values = [r[key] for r in rows if type(r.get(key)) is int and r[key] >= 0]
        tokens[key] = {
            "observed_sum": sum(values),
            "reported_attempts": len(values),
            "unreported_attempts": len(rows) - len(values),
        }
    return {
        "prescribed": len(rows),
        "reserved_physical_sends": len(rows),
        "outcome_counts": dict(Counter(r["outcome"] for r in rows)),
        "finish_reason_counts": dict(Counter(r["finish_reason"] for r in rows)),
        "valid_policy_count": sum(
            r["outcome"] in ("valid_correct", "valid_wrong") for r in rows
        ),
        "correct_policy_count": sum(r["outcome"] == "valid_correct" for r in rows),
        "median_latency_ms": statistics.median(latencies) if latencies else None,
        "provider_reported_tokens": tokens,
    }


def run_factorial(*, workspace: Path, run_id: str,
                  port_factory, workers: int = 3) -> dict[str, object]:
    if type(workers) is not int or not 1 <= workers <= 4:
        raise ValueError("workers must be 1..4")
    folder = _run_dir(workspace, run_id)
    # O_EXCL through directory creation ensures no second run, even on failure.
    folder.mkdir(mode=0o700, exist_ok=False)
    manifest = _manifest(run_id)
    plan = {
        "schema": SCHEMA, "run_id": run_id,
        "factorial_conditions": [
            {"reasoning_effort": e, "max_tokens": t} for e, t in CONDITIONS
        ],
        "prescribed": PRESCRIBED,
        "identical_examples_within_each_context": True,
        "model": MODEL,
        "source_manifest": manifest,
        "scientific_acceptance": False,
    }
    _write_once(folder, "manifest.json", plan)
    journal = SlotJournal(folder, run_id, max_slots=PRESCRIBED)

    def one(index: int, unit: dict[str, object], effort: str, cap: int):
        context_index = index // len(CONDITIONS)
        prompt = _induce_prompt(unit)
        # Reserve BEFORE touching any adapter or provider; no ambiguous resend.
        journal.reserve(index, prompt)
        evidence = _attempt(prompt, unit["private_program"], effort, cap, port_factory)
        return {
            "index": index,
            "unit_id": unit["unit_id"],
            "family": unit["family"],
            "context_index": context_index,
            "condition": _condition(effort, cap),
            "reasoning_effort_requested": effort,
            "max_tokens_requested": cap,
            "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
            **evidence,
        }

    with ThreadPoolExecutor(max_workers=workers) as executor:
        jobs = [
            executor.submit(one, 4 * i + j, unit, effort, cap)
            for i, unit in enumerate(manifest["units"])
            for j, (effort, cap) in enumerate(CONDITIONS)
        ]
        rows = [future.result() for future in as_completed(jobs)]
    rows.sort(key=lambda row: row["index"])
    if len(rows) != PRESCRIBED or [r["index"] for r in rows] != list(range(PRESCRIBED)):
        raise ValueError("invalid fixed 32-slot denominator")
    for index in range(MAX_CONTEXTS):
        same = {r["prompt_sha256"] for r in rows[4*index:4*(index+1)]}
        if len(same) != 1:
            raise ValueError("within-context provider prompts changed across conditions")
    terminal = {
        "schema": SCHEMA, "run_id": run_id,
        "manifest_sha256": _digest(plan),
        "rows": rows, "scientific_acceptance": False,
    }
    _write_once(folder, "terminal.json", terminal)
    summaries = {
        _condition(e, cap): _summary([
            r for r in rows if r["condition"] == _condition(e, cap)
        ]) for e, cap in CONDITIONS
    }
    # All grade indicators, including wrong answers and failures, remain.
    # Neither the private true programs nor the actual generated policies
    # can appear in the public report.
    return {
        "schema": SCHEMA, "run_id": run_id,
        "model": MODEL, "thinking_requested": "enabled",
        "conditions": summaries,
        "records": rows,
        "prescribed_logical_attempts": PRESCRIBED,
        "physical_sends_reserved": journal.count,
        "identical_examples_within_each_context": True,
        "manifest_sha256": _digest(plan),
        "source_only_no_holdout_or_memory_claim": True,
        "provider_token_sums_not_verified_billing": True,
        "scientific_acceptance": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Offline-first GLM-5.3 effort x token cap")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--workspace", type=Path)
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--timeout-seconds", type=float, default=120)
    args = parser.parse_args(argv)
    if not args.live:
        print(json.dumps({
            "status": "offline_zero_sends",
            "schema": SCHEMA,
            "prescribed_logical_attempts": PRESCRIBED,
            "scientific_acceptance": False,
        }))
        return 0
    if (args.workspace is None or not args.workspace.is_absolute()
            or type(args.workers) is not int or not 1 <= args.workers <= 4
            or not 30 <= args.timeout_seconds <= 300):
        raise SystemExit("invalid live experiment parameters")
    key = os.environ.get("C3R_ZAI_API_KEY", "").strip()
    if not key:
        raise SystemExit("missing ZAI credential: no sends")
    def factory(effort: str, cap: int):
        return ZaiStandardModelPort(
            api_key=key, model_id=MODEL, ledger=PhysicalSendLedger(1),
            enabled=True, route="coding", reasoning_effort=effort,
            max_tokens=cap, timeout_seconds=args.timeout_seconds,
        )
    report = run_factorial(
        workspace=args.workspace, run_id=args.run_id,
        port_factory=factory, workers=args.workers,
    )
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
