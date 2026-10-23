"""Two-send real-model control-readiness probe before a new G1 run.

No grading, no hidden labels, no retries or outside auditor. A technical
probe is *never* counted as a 40-slot scientific experiment observation.
Only redacted response metadata is printed.
"""

from __future__ import annotations

import argparse
import json
import os

from run_c3r_g1_fourth_crossed_live import prompt_for

from resonance_world.c3r_g1_crossed_plan import make_plan
from resonance_world.c3r_g1_model_boundary import ModelChoiceCompletion
from resonance_world.c3r_g1_zai_transport import PhysicalSendLedger, ZaiStandardModelPort


def run_control_probes(port_factory) -> dict[str, object]:
    cell = next(c for c in make_plan().cells if c.family == "text")
    task = cell.qualification[0]
    masked = tuple({
        "task_id": t.task_id,
        "choice": "A", "correct": False,
    } for t in cell.development)
    results = []
    for arm in ("fresh", "neutral"):
        prompt = prompt_for(
            task, source_history=() if arm == "fresh" else masked, arm=arm,
        )
        try:
            result = port_factory().complete_prompt(prompt)
            if not isinstance(result, ModelChoiceCompletion):
                raise ValueError("unrecognized provider completion object")
            tokens = result.completion_tokens_reported
            ready = (result.model_id == "glm-4.7"
                     and result.finish_reason == "stop"
                     and result.output in ("A", "B")
                     and (tokens is None or tokens <= 128))
            record = {
                "arm": arm,
                "status": "valid_short_answer" if ready else "incomplete_or_invalid",
                "finish_reason": result.finish_reason,
                "completion_tokens_reported": tokens,
                "reasoning_tokens_reported": result.reasoning_tokens_reported,
                "prompt_tokens_reported": result.prompt_tokens_reported,
            }
        except Exception as exc:
            record = {
                "arm": arm, "status": "transport_failure",
                "failure_class": type(exc).__name__,
                "completion_tokens_reported": None,
                "reasoning_tokens_reported": None,
                "prompt_tokens_reported": None,
            }
        results.append(record)
    return {
        "schema": "c3r-g1-internal-control-readiness-v0.1",
        "model": "glm-4.7",
        "requested_thinking_mode": "disabled",
        "control_prompt_policy": "default_A_if_no_actual_grades_v1",
        "technical_physical_send_reservations": 2,
        "readiness_passed": all(x["status"] == "valid_short_answer" for x in results),
        "observations": results,
        "source_task_grade_used": False,
        "counts_as_g1_experiment": False,
        "scientific_acceptance": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Two real control probes, zero retries")
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args(argv)
    if not args.live:
        print(json.dumps({"status": "offline_zero_sends", "scientific_acceptance": False}))
        return 0
    key = os.environ.get("C3R_ZAI_API_KEY", "").strip()
    if not key:
        raise SystemExit("provider credential absent, no send")
    def port_factory():
        return ZaiStandardModelPort(
            api_key=key, model_id="glm-4.7", ledger=PhysicalSendLedger(1),
            enabled=True, route="coding", thinking_mode="disabled",
            max_tokens=512, timeout_seconds=90,
        )
    report = run_control_probes(port_factory)
    print(json.dumps(report, sort_keys=True, separators=(",", ":")))
    return 0 if report["readiness_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
