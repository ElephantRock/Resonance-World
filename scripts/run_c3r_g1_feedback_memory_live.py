"""G1 feedback-acquired natural procedural memory: live dispatch (80-send cap).

Owner GO (2026-10-28): can the agent acquire a new procedure from real
feedback, convert it itself into precise natural-language instructions,
store it, and execute it on new inputs in independent sessions — and
does the stored agent-owned procedure beat re-deriving from the same
raw evidence?

Frozen design (research/c3r_g2/G1_FEEDBACK_ACQUIRED_PROCEDURAL_MEMORY_
PROSPECTIVE_20261028.md): 4 programs from 2 NEW unburned families
(binary, alpha). Per program: 3 evidence pairs, a 3-round feedback
learning loop on distinct probes, then a verbatim capsule. Execution:
16 tasks (4 programs x 4 fresh inputs) x 3 arms (Learned capsule /
Raw evidence / Fresh nothing). The harness NEVER renders a procedure
for the agent; the capsule is the model's own text, stored verbatim.

Hard cap 80 (learning 0..31 lazily reserved, 8 per program; execution:
learned 32..47, raw 48..63, fresh 64..79) enforced by an O_EXCL ledger.
Gate (frozen): Learned ITT >= 10/16 AND Learned-Fresh >= +8 AND
Learned-Raw >= +4; otherwise the line closes — no rescue rounds.

Sessions: manifest | learn --program P | exec --arm learned|raw|fresh |
report. No transport retries anywhere. Empty model answers inside the
learning loop re-prompt once (a new ledgered send) and never terminate
the loop by themselves; empty answers at execution are ITT failures.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import threading
import time
from pathlib import Path

from c3r_g1_feedback_families import (
    all_programs as feedback_programs,
    derive_input,
    _execute as feedback_execute,
)
from resonance_world.c3r_g1_zai_transport import PhysicalSendLedger, ZaiStandardModelPort

SCHEMA = "c3r-g1-feedback-memory-v0.1"
MODEL = "glm-5.3"
EFFORT = "high"
MAX_TOKENS = 4096
ROUTE = "coding"
CAMPAIGN_SLOTS = 80
LEARNING_BLOCK = 8
EVIDENCE_PAIRS = 3
MAX_ROUNDS = 3
EVAL_INPUTS = 4
EXEC_BASES = {"learned": 32, "raw": 48, "fresh": 64}
EXEC_TASKS = 16

EMPTY_GUARD_SUFFIX = (
    "\nYour previous answer was empty or not a usable value. "
    "Respond with the required output only."
)


class FeedbackLedger:
    """Cross-process O_EXCL slot ledger enforcing the 80-send cap."""

    def __init__(self, root: Path, run_id: str) -> None:
        self.root = root
        self.run_id = run_id
        self._lock = threading.Lock()
        self.root.mkdir(parents=True, exist_ok=True)

    def _slot_path(self, index: int) -> Path:
        return self.root / f"feedback-slot-{index:03d}.json"

    def reserve(self, index: int, session: str) -> None:
        with self._lock:
            path = self._slot_path(index)
            if path.exists():
                raise RuntimeError(f"slot {index} already reserved: double dispatch")
            if index >= CAMPAIGN_SLOTS:
                raise RuntimeError(f"slot {index} exceeds the 80-send cap")
            payload = json.dumps({
                "run_id": self.run_id, "session": session, "index": index,
                "reserved_no_retry": True,
            }, sort_keys=True).encode() + b"\n"
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "wb") as out:
                out.write(payload)
                out.flush()
                os.fsync(out.fileno())

    @property
    def consumed(self) -> int:
        return sum(1 for _ in self.root.glob("feedback-slot-*.json"))


def _program_position(program_id: str) -> int:
    for position, program in enumerate(feedback_programs()):
        if program["program_id"] == program_id:
            return position
    raise ValueError(f"unknown feedback program id: {program_id}")


def _truth(family: str, input_value: str, code: str) -> str:
    return feedback_execute(family, {"value": input_value}, code)


def program_plan(program: dict[str, str],
                 used: set[str] | None = None) -> dict[str, object]:
    """Deterministic evidence pairs, probes and evaluation inputs.

    ``used`` accumulates across programs so every input in the whole
    campaign is GLOBALLY unique (no value appears under two hidden
    programs — a shared value would carry two different truths).
    """

    pid = program["program_id"]
    family = program["family"]
    code = program["program"]
    used = used if used is not None else set()
    used_before = len(used)

    def next_input(role: str, index: int) -> str:
        value = derive_input(family, pid, role, index,
                             exclude=frozenset(used))
        used.add(value)
        return value

    evidence = []
    for i in range(EVIDENCE_PAIRS):
        value = next_input("evidence", i)
        evidence.append(
            {"input": value, "output": _truth(family, value, code)}
        )
    probes = [next_input("probe", r) for r in range(MAX_ROUNDS)]
    eval_inputs = [
        {"input_index": i, "input": next_input("eval", i),
         "truth": None}
        for i in range(EVAL_INPUTS)
    ]
    for task in eval_inputs:
        task["truth"] = _truth(family, task["input"], code)
    assert len(used) - used_before == (
        EVIDENCE_PAIRS + MAX_ROUNDS + EVAL_INPUTS
    )
    return {
        "program_id": pid, "family": family, "program_code": code,
        "evidence": evidence, "probes": probes, "eval": eval_inputs,
    }


def campaign_plan() -> list[dict[str, object]]:
    used: set[str] = set()
    plans = []
    for program in feedback_programs():
        plans.append(program_plan(program, used))
    assert len(used) == 4 * (EVIDENCE_PAIRS + MAX_ROUNDS + EVAL_INPUTS)
    return plans


def campaign_tasks() -> list[dict[str, object]]:
    tasks = []
    for plan in campaign_plan():
        for task in plan["eval"]:
            tasks.append({
                "program_id": plan["program_id"],
                "family": plan["family"],
                "program_code": plan["program_code"],
                "input_index": task["input_index"],
                "input": task["input"],
                "truth": task["truth"],
            })
    return tasks


def exec_slot(arm: str, program_id: str, input_index: int) -> int:
    return (
        EXEC_BASES[arm] + _program_position(program_id) * EVAL_INPUTS
        + input_index
    )


def slot_plan() -> list[dict[str, object]]:
    plan: list[dict[str, object]] = []
    for program in feedback_programs():
        base = _program_position(program["program_id"]) * LEARNING_BLOCK
        for offset in range(LEARNING_BLOCK):
            plan.append({
                "index": base + offset, "kind": "learning",
                "program_id": program["program_id"],
            })
    for arm in ("learned", "raw", "fresh"):
        for task in campaign_tasks():
            plan.append({
                "index": exec_slot(arm, task["program_id"],
                                   task["input_index"]),
                "kind": "exec", "arm": arm,
                "program_id": task["program_id"],
                "input_index": task["input_index"],
            })
    return sorted(plan, key=lambda row: row["index"])  # type: ignore[return-value]


# --- frozen prompts ---


def _evidence_lines(evidence: list[dict[str, str]]) -> str:
    return "\n".join(
        f'in={pair["input"]} -> out={pair["output"]}' for pair in evidence
    )


def draft_prompt(evidence: list[dict[str, str]]) -> str:
    return (
        "You are given example input/output pairs of one fixed unknown "
        "five-step text transformation. Each step is one simple "
        "whole-string operation.\n"
        f"Examples:\n{_evidence_lines(evidence)}\n"
        "Write the exact procedure as five numbered steps "
        "(Step 1: ... Step 5: ...). Each step must be fully explicit "
        "about character positions, boundaries and indexing (use 1st, "
        "2nd, ... counting), and about where any count is placed. "
        "Output ONLY the five step lines."
    )


def apply_prompt(capsule: str, input_value: str) -> str:
    return (
        "Execute the following procedure strictly in order, applying "
        "exactly one step at a time:\n"
        f"{capsule}\n"
        f'New task: {json.dumps({"value": input_value}, sort_keys=True)}\n'
        "Answer with only the final value."
    )


def revise_prompt(capsule: str, evidence: list[dict[str, str]],
                  probe: str, produced: str | None, expected: str) -> str:
    observed = (
        f"Applying it to in={probe} produces {produced!r}, but the "
        f"correct output is out={expected}."
        if produced is not None
        else f"Applying it to in={probe} produced no usable answer, "
             f"but the correct output is out={expected}."
    )
    return (
        "You previously wrote this procedure:\n"
        f"{capsule}\n"
        f"{observed}\n"
        "Your procedure is wrong in at least one step. Revise it. Keep "
        "the steps that are right, fix what is wrong; every step must "
        "stay fully explicit. The original examples were:\n"
        f"{_evidence_lines(evidence)}\n"
        "Output ONLY the five step lines."
    )


def exec_learned_prompt(capsule: str, input_value: str) -> str:
    return (
        "This is a new isolated agent session. Execute the following "
        "procedure strictly in order, applying exactly one step at a "
        "time:\n"
        f"{capsule}\n"
        f'New task: {json.dumps({"value": input_value}, sort_keys=True)}\n'
        "Answer with only the final value."
    )


def exec_raw_prompt(evidence: list[dict[str, str]], input_value: str) -> str:
    return (
        "You are given example input/output pairs of one fixed unknown "
        "five-step text transformation. Work out the transformation from "
        "the examples, then apply it to the new task.\n"
        f"Examples:\n{_evidence_lines(evidence)}\n"
        f'New task: {json.dumps({"value": input_value}, sort_keys=True)}\n'
        "Answer with only the final value."
    )


def exec_fresh_prompt(input_value: str) -> str:
    return (
        "A fixed deterministic transformation is applied to text "
        "strings. Output only the transformed value.\n"
        f'New task: {json.dumps({"value": input_value}, sort_keys=True)}'
    )


def _capsule_five_steps(capsule: str | None) -> bool:
    if not capsule:
        return False
    lines = [line.strip() for line in capsule.splitlines() if line.strip()]
    if len(lines) != 5:
        return False
    return all(
        re.match(rf"^Step {index + 1}:", lines[index])
        for index in range(5)
    )


def _write_json(path: Path, record: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def run_manifest(workspace: Path, run_id: str) -> dict[str, object]:
    manifest = {
        "schema": SCHEMA,
        "run_id": run_id,
        "model": MODEL,
        "reasoning_effort": EFFORT,
        "max_tokens": MAX_TOKENS,
        "route": ROUTE,
        "programs": feedback_programs(),
        "plan": campaign_plan(),
        "slots": slot_plan(),
        "campaign_slots": CAMPAIGN_SLOTS,
        "scientific_acceptance": False,
    }
    path = workspace / "feedback-manifest.json"
    if path.exists():
        existing = json.loads(path.read_text(encoding="utf-8"))
        frozen_fields = ("programs", "plan", "slots")
        if any(existing[field] != manifest[field] for field in frozen_fields):
            raise ValueError("manifest drift: frozen campaign changed")
        print("manifest already frozen and identical", flush=True)
        return existing
    _write_json(path, manifest)
    print(f"manifest frozen: {path}", flush=True)
    return manifest


def _load_manifest(workspace: Path) -> dict[str, object]:
    path = workspace / "feedback-manifest.json"
    if not path.exists():
        raise FileNotFoundError(
            "frozen manifest missing: run the manifest session first"
        )
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if any(
        manifest[field] != expected
        for field, expected in (
            ("programs", feedback_programs()),
            ("plan", campaign_plan()),
            ("slots", slot_plan()),
        )
    ):
        raise ValueError("manifest drift: frozen campaign changed")
    return manifest


def _dispatch(api_key: str, prompt: str):
    return ZaiStandardModelPort(
        api_key=api_key,
        model_id=MODEL,
        ledger=PhysicalSendLedger(1),
        enabled=True,
        route=ROUTE,
        reasoning_effort=EFFORT,
        max_tokens=MAX_TOKENS,
    ).complete_prompt(prompt)


class _TransportAbort(RuntimeError):
    pass


class _LearningBudgetExhausted(RuntimeError):
    pass


def run_learn(workspace: Path, run_id: str, program_id: str,
              api_key: str) -> dict[str, object]:
    """The feedback learning loop for ONE program (<= 8 sends)."""

    manifest = _load_manifest(workspace)
    ledger = FeedbackLedger(workspace / "feedback-ledger", run_id)
    plan = next(
        p for p in manifest["plan"] if p["program_id"] == program_id
    )
    evidence: list[dict[str, str]] = plan["evidence"]
    probes: list[str] = plan["probes"]
    family: str = plan["family"]
    code: str = plan["program_code"]

    base = _program_position(program_id) * LEARNING_BLOCK
    cursor = {"next": base}
    events: list[dict[str, object]] = []

    def reserve_next(role: str) -> int:
        index = cursor["next"]
        if index >= base + LEARNING_BLOCK:
            raise _LearningBudgetExhausted(
                f"learning budget exhausted for {program_id}"
            )
        cursor["next"] = index + 1
        ledger.reserve(index, f"learn-{program_id}-{role}")
        return index

    def learn_send(prompt: str, role: str) -> str | None:
        """One send with the empty-output guard (guard = a new send)."""

        for guard in (False, True):
            slot = reserve_next(role)
            text = prompt + (EMPTY_GUARD_SUFFIX if guard else "")
            started = time.monotonic()
            try:
                completion = _dispatch(api_key, text)
            except Exception as exc:
                events.append({
                    "role": role, "slot": slot, "guard": guard,
                    "status": "transport_error",
                    "failure_class": type(exc).__name__[:40],
                    "answer": None, "finish_reason": None,
                    "latency_ms": round((time.monotonic() - started) * 1000, 1),
                })
                raise _TransportAbort(type(exc).__name__) from None
            answer = completion.output.strip()
            finish = completion.finish_reason
            parseable = finish == "stop" and bool(answer)
            events.append({
                "role": role, "slot": slot, "guard": guard,
                "status": "sent_ok" if parseable else "empty_answer",
                "answer": answer, "finish_reason": finish,
                "latency_ms": round((time.monotonic() - started) * 1000, 1),
            })
            if parseable:
                return answer
        return None

    draft: str | None = None
    validated = False
    validation_round: int | None = None
    aborted: str | None = None
    budget_exhausted = False

    try:
        draft = learn_send(draft_prompt(evidence), "draft0")
        for round_index in range(1, MAX_ROUNDS + 1):
            if draft is None:
                break
            probe = probes[round_index - 1]
            expected = _truth(family, probe, code)
            produced = learn_send(
                apply_prompt(draft, probe), f"apply{round_index}"
            )
            if produced is not None and produced == expected:
                validated = True
                validation_round = round_index
                break
            revised = learn_send(
                revise_prompt(draft, evidence, probe, produced, expected),
                f"revise{round_index}",
            )
            if revised is not None:
                draft = revised
    except _TransportAbort as exc:
        aborted = str(exc)
    except _LearningBudgetExhausted:
        budget_exhausted = True

    outcome = {
        "schema": SCHEMA,
        "program_id": program_id,
        "family": family,
        "program_code": code,
        "capsule": draft,
        "capsule_format_ok": _capsule_five_steps(draft),
        "validated": validated,
        "validation_round": validation_round,
        "sends_used": len(events),
        "aborted": aborted,
        "budget_exhausted": budget_exhausted,
        "events": events,
    }
    _write_json(workspace / f"learn-{program_id}.json", outcome)
    _write_json(
        workspace / f"capsule-{program_id}.json",
        {
            "schema": SCHEMA, "program_id": program_id,
            "capsule": draft, "validated": validated,
        },
    )
    print(
        f"[learn] {program_id}: validated={validated} "
        f"round={validation_round} sends={len(events)} "
        f"format_ok={outcome['capsule_format_ok']} "
        f"aborted={aborted} budget_exhausted={budget_exhausted}",
        flush=True,
    )
    return outcome


def run_exec(workspace: Path, run_id: str, arm: str,
             api_key: str) -> dict[str, object]:
    """One execution arm: 16 tasks, one send each."""

    manifest = _load_manifest(workspace)
    ledger = FeedbackLedger(workspace / "feedback-ledger", run_id)
    plan_by_pid = {p["program_id"]: p for p in manifest["plan"]}
    capsules: dict[str, str | None] = {}
    if arm == "learned":
        for program in feedback_programs():
            pid = program["program_id"]
            path = workspace / f"capsule-{pid}.json"
            if not path.exists():
                raise FileNotFoundError(
                    f"capsule missing for {pid}: run all learn sessions first"
                )
            capsules[pid] = json.loads(
                path.read_text(encoding="utf-8")
            )["capsule"]

    rows: list[dict[str, object]] = []
    for task in campaign_tasks():
        pid = task["program_id"]
        slot = exec_slot(arm, pid, task["input_index"])
        if arm == "learned":
            capsule = capsules[pid]
            if capsule is None:
                rows.append({
                    "program_id": pid, "input_index": task["input_index"],
                    "arm": arm, "input": task["input"],
                    "truth": task["truth"], "status": "no_capsule",
                    "answer": None, "correct": None, "itt_success": False,
                    "slot": None, "finish_reason": None, "latency_ms": None,
                })
                print(f"[{arm}] {pid}#{task['input_index']}: no_capsule",
                      flush=True)
                continue
            prompt = exec_learned_prompt(capsule, task["input"])
        elif arm == "raw":
            prompt = exec_raw_prompt(
                plan_by_pid[pid]["evidence"], task["input"]
            )
        else:
            prompt = exec_fresh_prompt(task["input"])

        ledger.reserve(slot, f"exec-{arm}-{pid}-{task['input_index']}")
        started = time.monotonic()
        try:
            completion = _dispatch(api_key, prompt)
            answer = completion.output.strip()
            finish = completion.finish_reason
        except Exception as exc:
            rows.append({
                "program_id": pid, "input_index": task["input_index"],
                "arm": arm, "input": task["input"], "truth": task["truth"],
                "status": "transport_error",
                "failure_class": type(exc).__name__[:40],
                "answer": None, "correct": None, "itt_success": False,
                "slot": slot, "finish_reason": None,
                "latency_ms": round((time.monotonic() - started) * 1000, 1),
            })
            print(f"[{arm}] {pid}#{task['input_index']}: transport_error "
                  f"({type(exc).__name__})", flush=True)
            continue
        parseable = finish == "stop" and bool(answer)
        correct = (answer == task["truth"]) if parseable else None
        rows.append({
            "program_id": pid, "input_index": task["input_index"],
            "arm": arm, "input": task["input"], "truth": task["truth"],
            "status": "evaluated" if parseable else "unparseable",
            "answer": answer, "correct": correct,
            "itt_success": correct is True, "slot": slot,
            "finish_reason": finish,
            "latency_ms": round((time.monotonic() - started) * 1000, 1),
        })
        print(f"[{arm}] {pid}#{task['input_index']}: "
              f"answer={answer!r} correct={correct}", flush=True)

    taxonomy = {
        "correct": sum(1 for row in rows if row["itt_success"]),
        "wrong_value": sum(1 for row in rows
                           if row["status"] == "evaluated"
                           and row["correct"] is False),
        "unparseable": sum(1 for row in rows
                           if row["status"] == "unparseable"),
        "transport": sum(1 for row in rows
                         if row["status"] == "transport_error"),
        "no_capsule": sum(1 for row in rows
                          if row["status"] == "no_capsule"),
    }
    summary = {
        "schema": SCHEMA, "session": f"exec-{arm}", "arm": arm,
        "information": {"learned": "stored capsule (verbatim)",
                        "raw": "the same 3 evidence pairs",
                        "fresh": "nothing"}[arm],
        "sends": sum(1 for row in rows if row["slot"] is not None),
        "itt_successes": taxonomy["correct"],
        "taxonomy": taxonomy,
        "rows": rows,
    }
    _write_json(workspace / f"summary-{arm}.json", summary)
    print(f"summary written: {workspace / f'summary-{arm}.json'}", flush=True)
    return summary


def run_report(workspace: Path) -> dict[str, object]:
    """Offline aggregation: learning outcomes, execution taxonomy, gate."""

    learn_files = [f"learn-{p['program_id']}.json"
                   for p in feedback_programs()]
    required = learn_files + [
        f"summary-{arm}.json" for arm in ("learned", "raw", "fresh")
    ]
    missing = [name for name in required if not (workspace / name).exists()]
    if missing:
        raise FileNotFoundError(f"campaign incomplete, missing: {missing}")

    learning = [
        json.loads((workspace / name).read_text(encoding="utf-8"))
        for name in learn_files
    ]
    execs = {
        arm: json.loads(
            (workspace / f"summary-{arm}.json").read_text(encoding="utf-8")
        )
        for arm in ("learned", "raw", "fresh")
    }

    by_key: dict[tuple[str, int], dict[str, bool]] = {}
    for arm, summary in execs.items():
        for row in summary["rows"]:
            key = (row["program_id"], row["input_index"])
            by_key.setdefault(key, {})[arm] = row["itt_success"] is True
    assert len(by_key) == EXEC_TASKS

    learned_itt = sum(1 for p in by_key.values() if p["learned"])
    raw_itt = sum(1 for p in by_key.values() if p["raw"])
    fresh_itt = sum(1 for p in by_key.values() if p["fresh"])

    def paired(arm_x: str, arm_y: str) -> dict[str, int]:
        return {
            "both": sum(1 for p in by_key.values() if p[arm_x] and p[arm_y]),
            "x_only": sum(1 for p in by_key.values()
                          if p[arm_x] and not p[arm_y]),
            "y_only": sum(1 for p in by_key.values()
                          if p[arm_y] and not p[arm_x]),
            "neither": sum(1 for p in by_key.values()
                           if not p[arm_x] and not p[arm_y]),
        }

    g1 = learned_itt >= 10 and (learned_itt - fresh_itt) >= 8
    g2 = (learned_itt - raw_itt) >= 4
    verdict = (
        "GATE PASSED: acquisition -> storage -> fresh-session execution "
        "demonstrated AND stored capsule beats raw re-derivation"
        if g1 and g2 else
        "GATE FAILED: the line closes — no rescue rounds, no threshold "
        "adjustment"
    )

    report = {
        "schema": SCHEMA,
        "campaign": "g1-feedback-acquired-procedural-memory-20261028",
        "learning": {
            "programs": len(learning),
            "validated": sum(1 for o in learning if o["validated"]),
            "capsule_format_ok": sum(
                1 for o in learning if o["capsule_format_ok"]
            ),
            "learning_sends": sum(o["sends_used"] for o in learning),
            "transport_aborted": sum(1 for o in learning if o["aborted"]),
            "budget_exhausted": sum(
                1 for o in learning if o["budget_exhausted"]
            ),
            "per_program": [
                {
                    "program_id": o["program_id"],
                    "validated": o["validated"],
                    "validation_round": o["validation_round"],
                    "capsule_format_ok": o["capsule_format_ok"],
                    "sends_used": o["sends_used"],
                }
                for o in learning
            ],
        },
        "execution": {
            arm: {
                "itt_successes": execs[arm]["itt_successes"],
                "sends": execs[arm]["sends"],
                "taxonomy": execs[arm]["taxonomy"],
            }
            for arm in ("learned", "raw", "fresh")
        },
        "learned_itt": learned_itt,
        "raw_itt": raw_itt,
        "fresh_itt": fresh_itt,
        "paired_learned_vs_raw": paired("learned", "raw"),
        "paired_learned_vs_fresh": paired("learned", "fresh"),
        "gate_g1_repeatable_value": g1,
        "gate_g2_beats_rederivation": g2,
        "verdict": verdict,
        "scientific_acceptance": False,
    }
    _write_json(workspace / "feedback-report.json", report)
    print(json.dumps(report, indent=2, sort_keys=True), flush=True)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="G1 feedback-acquired natural procedural memory"
    )
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--session", required=True,
                        choices=("manifest", "learn", "exec", "report"))
    parser.add_argument("--program")
    parser.add_argument("--arm", choices=("learned", "raw", "fresh"))
    parser.add_argument("--api-key", default=os.environ.get("C3R_ZAI_API_KEY", ""))
    args = parser.parse_args()
    workspace = args.workspace
    workspace.mkdir(parents=True, exist_ok=True)

    if args.session == "manifest":
        run_manifest(workspace, args.run_id)
        return 0
    if args.session == "report":
        run_report(workspace)
        return 0
    if not args.api_key:
        parser.error("C3R_ZAI_API_KEY (or --api-key) is required")
    if args.session == "learn":
        if not args.program:
            parser.error("learn sessions require --program")
        run_learn(workspace, args.run_id, args.program, args.api_key)
        return 0
    if not args.arm:
        parser.error("exec sessions require --arm")
    run_exec(workspace, args.run_id, args.arm, args.api_key)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
