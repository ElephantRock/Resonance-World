"""G2 request-class qualification probe: exactly TWO live sends (frozen).

Frozen mini-protocol: research/c3r_g2/G2_REQUEST_CLASS_PROBE_PROTOCOL_20261028.md
Owner limited GO (2026-10-28 evening): one C-class interpretation
request + one D-class procedure-execution request; independent
permanent cap of exactly 2 sends via a dedicated O_EXCL ledger; the
two reserved Probe sends are untouched. Success of both permits
completing the statistical freeze and launches NOTHING; failure of
either class halts the campaign path.

Deterministic fixture: the S2-class organization from the offline
qualification harness (noisy-majority corpus, one holdout task, one
member per class, compiled procedure via the frozen floors).
"""

from __future__ import annotations

import argparse
import json
import os
import threading
import time
from pathlib import Path

from resonance_world.c3r_g2 import PLANS
from resonance_world.c3r_g2_causal_qualification import (
    Oracle,
    _apply,
    compile_procedure,
    member_reads,
    raw_interpretation,
    scenario_s2_noisy_majority,
)
from resonance_world.c3r_g1_zai_transport import PhysicalSendLedger, ZaiStandardModelPort

SCHEMA = "c3r-g2-request-class-probe-v0.1"
MODEL = "glm-5.3"
EFFORT = "high"
MAX_TOKENS = 4096
TIMEOUT_SECONDS = 300.0
ROUTE = "coding"
PROBE_SLOTS = 2


class ProbeLedger:
    """Dedicated O_EXCL ledger: exactly 2 sends, ever, per workspace."""

    def __init__(self, root: Path, run_id: str) -> None:
        self.root = root
        self.run_id = run_id
        self._lock = threading.Lock()
        self.root.mkdir(parents=True, exist_ok=True)

    def reserve(self, index: int, session: str) -> None:
        with self._lock:
            path = self.root / f"g2-probe-slot-{index:03d}.json"
            if path.exists():
                raise RuntimeError(
                    f"probe slot {index} already reserved: the permanent "
                    "2-send cap is exhausted"
                )
            if index >= PROBE_SLOTS:
                raise RuntimeError(
                    f"probe slot {index} exceeds the permanent 2-send cap"
                )
            payload = json.dumps({
                "run_id": self.run_id, "session": session, "index": index,
                "reserved_no_retry": True,
            }, sort_keys=True).encode() + b"\n"
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "wb") as out:
                out.write(payload)
                out.flush()
                os.fsync(out.fileno())


def build_fixture() -> dict[str, object]:
    """Deterministic S2-class organization, one task, one C sample."""

    spec = scenario_s2_noisy_majority()
    task = spec.tasks[0]
    member = "probe-member"
    sample = member_reads(spec.episodes, task, member)
    procedure, stats = compile_procedure(spec.episodes, task.context)
    oracle = Oracle(spec.truth)
    return {
        "spec": spec, "task": task, "member": member, "sample": sample,
        "procedure": procedure, "compile_stats": stats, "oracle": oracle,
    }


def c_class_prompt(fixture: dict[str, object]) -> str:
    records = "\n".join(
        f"record {e.episode_id}: context={e.context} variant={e.variant} "
        f"plan={e.plan} graded_success={e.graded_success}"
        for e in fixture["sample"]
    )
    task = fixture["task"]
    return (
        "You are a member of an organization. Using ONLY the graded "
        "evidence records below, decide which two-step plan succeeds in "
        "this context, apply it to the task, and output the final value.\n"
        f"Records:\n{records}\n"
        "The two plans are: add-then-multiply, or multiply-then-add.\n"
        f"Task: value={task.value}, offset={task.offset}, "
        f"factor={task.factor}\n"
        "Answer with only the final integer value."
    )


def d_class_prompt(fixture: dict[str, object]) -> str:
    task = fixture["task"]
    plan = fixture["procedure"]
    assert plan is not None
    order = "add, then multiply" if plan[0] == "add" else "multiply, then add"
    return (
        "This is a new isolated session. Execute the following "
        "organizational procedure exactly:\n"
        f"Step 1: {order}.\n"
        "Step 2: output the result.\n"
        f"Task: value={task.value}, offset={task.offset}, "
        f"factor={task.factor}\n"
        "Answer with only the final integer value."
    )


def _dispatch(api_key: str, prompt: str):
    return ZaiStandardModelPort(
        api_key=api_key,
        model_id=MODEL,
        ledger=PhysicalSendLedger(1),
        enabled=True,
        route=ROUTE,
        reasoning_effort=EFFORT,
        max_tokens=MAX_TOKENS,
        timeout_seconds=TIMEOUT_SECONDS,
    ).complete_prompt(prompt)


def _truth_answer(fixture: dict[str, object]) -> int:
    task = fixture["task"]
    return _apply(task, fixture["spec"].truth[(task.context, task.variant)])


def run_probe(workspace: Path, run_id: str, api_key: str) -> dict[str, object]:
    fixture = build_fixture()
    ledger = ProbeLedger(workspace / "g2-probe-ledger", run_id)
    requests: list[tuple[str, str]] = [
        ("c_class_interpretation", c_class_prompt(fixture)),
        ("d_class_execution", d_class_prompt(fixture)),
    ]
    truth = _truth_answer(fixture)
    rows: list[dict[str, object]] = []

    for index, (label, prompt) in enumerate(requests):
        ledger.reserve(index, label)
        started = time.monotonic()
        try:
            completion = _dispatch(api_key, prompt)
            answer = completion.output.strip()
            finish = completion.finish_reason
            row = {
                "request_class": label, "slot": index,
                "latency_ms": round((time.monotonic() - started) * 1000, 1),
                "finish_reason": finish,
                "answer": answer,
                "correct_informational": (
                    answer.isdigit() and int(answer) == truth
                ) if answer else False,
                "prompt_tokens_reported": completion.prompt_tokens_reported,
                "completion_tokens_reported": (
                    completion.completion_tokens_reported
                ),
            }
            if finish == "stop" and answer:
                row["classification"] = "completed_parseable"
            elif finish == "length":
                row["classification"] = "length"
            else:
                row["classification"] = "empty"
        except Exception as exc:
            row = {
                "request_class": label, "slot": index,
                "latency_ms": round((time.monotonic() - started) * 1000, 1),
                "classification": "transport_error",
                "failure_class": type(exc).__name__[:40],
                "answer": None, "correct_informational": False,
                "prompt_tokens_reported": None,
                "completion_tokens_reported": None,
            }
        rows.append(row)
        print(f"[probe] {label}: {row['classification']} "
              f"(latency {row['latency_ms']} ms)", flush=True)

    both_completed = all(
        row["classification"] == "completed_parseable" for row in rows
    )
    outcome = {
        "schema": SCHEMA,
        "run_id": run_id,
        "model": MODEL, "effort": EFFORT, "max_tokens": MAX_TOKENS,
        "timeout_seconds": TIMEOUT_SECONDS, "route": ROUTE,
        "protocol": "G2_REQUEST_CLASS_PROBE_PROTOCOL_20261028",
        "permanent_send_cap": PROBE_SLOTS,
        "sends": len(rows),
        "both_classes_completed": both_completed,
        "interpretation": (
            "both request classes technically usable at the registered "
            "operating point; statistical freeze may proceed; NOTHING "
            "is launched"
            if both_completed else
            "at least one request class failed; the campaign path halts "
            "and the operating point returns to the owner"
        ),
        "rows": rows,
    }
    path = workspace / "g2-request-class-probe.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(outcome, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")
    print(f"probe report written: {path}", flush=True)
    return outcome


def main() -> int:
    parser = argparse.ArgumentParser(
        description="G2 request-class qualification probe (exactly 2 sends)"
    )
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--api-key", default=os.environ.get("C3R_ZAI_API_KEY", ""))
    args = parser.parse_args()
    if not args.api_key:
        parser.error("C3R_ZAI_API_KEY (or --api-key) is required")
    args.workspace.mkdir(parents=True, exist_ok=True)
    outcome = run_probe(args.workspace, args.run_id, args.api_key)
    return 0 if outcome["both_classes_completed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
