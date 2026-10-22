"""Second G1 REAL-model exploratory pilot: flip hidden law to A, include sham.

Only 8 logical/physical attempts: 2 graded development, then 2 matched
holdouts x learned/fresh/independent placebo. Zero sends unless --live.
This is NOT preregistered, blinded, powered, or proof of persistent agency.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from dataclasses import dataclass
from typing import Protocol

from resonance_world.c3r_g1_model_boundary import (
    ModelChoiceCompletion,
    ModelChoiceRequest,
    SourceFeedback,
)
from resonance_world.c3r_g1_zai_transport import (
    MAX_GENERATION_TOKENS,
    PhysicalSendLedger,
    ZaiStandardModelPort,
)
from resonance_world.c3r_g2_probe import FixtureOracle, PublicTask, apply_public_plan, make_task

CONTEXT = "c3r-k7-opaque-20261022"
MODEL = "glm-5.3"
EXPECTED_SENDS = 8
TARGET = ("add", "multiply")
PLANS = {"A": ("add", "multiply"), "B": ("multiply", "add")}


@dataclass(frozen=True, slots=True)
class Probe:
    stage: str
    arm: str
    task: PublicTask


def plan() -> tuple[Probe, ...]:
    tasks = (
        *(Probe("development", "learned", make_task(
            split="dev", context=CONTEXT, number=n
        )) for n in (20, 21)),
        *(Probe("qualification", arm, make_task(
            split="holdout", context=CONTEXT, number=n
        )) for n in (13, 14)
          for arm in ("learned", "fresh", "placebo")),
    )
    if len(tasks) != EXPECTED_SENDS:
        raise RuntimeError("locked eight-request denominator changed")
    return tasks


class Port(Protocol):
    def complete(self, request: ModelChoiceRequest) -> ModelChoiceCompletion: ...


def run_trial(port: Port, ledger: PhysicalSendLedger) -> dict[str, object]:
    oracle = FixtureOracle({CONTEXT: TARGET})
    source: list[SourceFeedback] = []
    sham = tuple(
        SourceFeedback(probe.task.task_id, CONTEXT, PLANS["B"], True)
        for probe in plan() if probe.stage == "development"
    )
    rows: list[dict[str, object]] = []
    aborted = False
    for probe in plan():
        feedback = (
            tuple(source) if probe.arm == "learned"
            else sham if probe.arm == "placebo" else ()
        )
        request = ModelChoiceRequest(
            owner_id="source-exploration-2",
            stage=probe.stage,
            task=probe.task,
            feedback=feedback,
        )
        record: dict[str, object] = {
            "stage": probe.stage,
            "arm": probe.arm,
            "task_id": probe.task.task_id,
            "status": "not_sent_after_failure" if aborted else "unknown",
            "choice_sha256": None,
            "success": None,
            "finish_reason": None,
            "completion_tokens_reported": None,
            "reasoning_tokens_reported": None,
            "prompt_tokens_reported": None,
        }
        if aborted:
            rows.append(record)
            continue
        try:
            completion = port.complete(request)
        except Exception:
            record["status"] = "adapter_exception"
        else:
            if not isinstance(completion, ModelChoiceCompletion):
                record["status"] = "invalid_completion"
            elif completion.model_id != MODEL:
                record["status"] = "wrong_model"
            else:
                record["choice_sha256"] = hashlib.sha256(
                    completion.output.encode("utf-8")
                ).hexdigest()
                record["finish_reason"] = completion.finish_reason
                record["completion_tokens_reported"] = completion.completion_tokens_reported
                record["reasoning_tokens_reported"] = completion.reasoning_tokens_reported
                record["prompt_tokens_reported"] = completion.prompt_tokens_reported
                if completion.finish_reason != "stop":
                    record["status"] = "unfinished_output"
                elif completion.output not in PLANS:
                    record["status"] = "invalid_format"
                else:
                    record["status"] = "accepted"
                    correct = oracle.grade(
                        probe.task, apply_public_plan(probe.task, PLANS[completion.output])
                    )
                    record["success"] = correct
                    if probe.stage == "development":
                        source.append(SourceFeedback(
                            probe.task.task_id, CONTEXT, PLANS[completion.output], correct
                        ))
        if record["status"] != "accepted":
            aborted = True
        rows.append(record)

    qualified = [x for x in rows if x["stage"] == "qualification"]
    result = {
        arm: {
            "prescribed": 2,
            "accepted": sum(
                x["arm"] == arm and x["status"] == "accepted" for x in qualified
            ),
            "correct": sum(x["arm"] == arm and x["success"] is True for x in qualified),
        }
        for arm in ("learned", "fresh", "placebo")
    }
    return {
        "schema": "c3r-g1-real-counterlaw-placebo-exploration-v0.1",
        "status": "exploratory_not_scientific_acceptance",
        "expected_model": MODEL,
        "public_context": CONTEXT,
        "true_target_is": "A",
        "planned_calls": EXPECTED_SENDS,
        "development_count": 2,
        "development_accepted": sum(
            x["stage"] == "development" and x["status"] == "accepted" for x in rows
        ),
        "development_correct": sum(
            x["stage"] == "development" and x["success"] is True for x in rows
        ),
        "placebo_rule": "independent_two_sham_B_success_labels_not_real_feedback",
        "qualification": result,
        "fully_analyzable_triplets": sum(
            all(
                any(x["arm"] == arm and x["task_id"] == task_id
                    and x["status"] == "accepted" for x in qualified)
                for arm in ("learned", "fresh", "placebo")
            ) for task_id in {x["task_id"] for x in qualified}
        ),
        "observations": rows,
        "send_ledger": ledger.to_dict(),
        "provider_billing_verified": False,
        "independent_evaluator_attested": False,
        "scientific_acceptance": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="One small G1 A-target sham-controlled probe")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--model", default=MODEL)
    parser.add_argument("--route", default="coding", choices=("coding",))
    parser.add_argument("--max-tokens", type=int, default=16384)
    args = parser.parse_args(argv)
    if args.model != MODEL or not 1 <= args.max_tokens <= MAX_GENERATION_TOKENS:
        raise SystemExit("model identity or generation budget rejected")
    if not args.live:
        print(json.dumps({
            "status": "offline_no_provider_sends",
            "expected_sends": EXPECTED_SENDS,
            "context": CONTEXT,
            "target": "A",
            "arms": ["learned", "fresh", "placebo"],
            "qualification_triplets": 2,
            "max_tokens": args.max_tokens,
            "scientific_acceptance": False,
        }, sort_keys=True))
        return 0

    key = os.environ.get("C3R_ZAI_API_KEY", "")
    if not key.strip():
        raise SystemExit("C3R_ZAI_API_KEY unavailable; no provider send")
    ledger = PhysicalSendLedger(EXPECTED_SENDS)
    port = ZaiStandardModelPort(
        api_key=key, model_id=args.model, ledger=ledger, enabled=True,
        route="coding", max_tokens=args.max_tokens, timeout_seconds=180,
    )
    print(json.dumps(run_trial(port, ledger), sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
