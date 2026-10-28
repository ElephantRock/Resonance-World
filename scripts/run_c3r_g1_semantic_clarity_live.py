"""G1 semantic clarity of procedural instructions: live dispatch (32-send cap).

Owner limited GO (2026-10-28): does explicitly specifying separator
placement and forbidding the trailing separator improve procedure-
execution success, with the true program, model, resources and inputs
held fixed? Diagnostic study driven by the stepwise result — NOT an
independent confirmation of any earlier hypothesis.

Frozen design (research/c3r_g2/G1_SEMANTIC_CLARITY_INSTRUCTIONS_
PROSPECTIVE_20261028.md): the 4 frozen rotate programs only, 2 waves x
2 fresh unambiguous inputs = 16 tasks, identical across arms.
- Arm A (ambiguous): the original frozen step-2 wording.
- Arm B (precise):   exact-placement wording, no trailing separator.
The step-2 line is the ONLY difference. Single-shot execution
(1 send per task per arm). Hard cap 32 enforced by an O_EXCL slot
ledger. Predeclared criterion: B ITT >= 15/16 AND paired B-A >= +4.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import threading
import time
from pathlib import Path

from c3r_g1_procedure_representation import WAVES, all_programs
from resonance_world.c3r_g1_zai_transport import PhysicalSendLedger, ZaiStandardModelPort
from run_c3r_g1_stepwise_execution_live import (
    _grammar_text,
    _natural_step_instructions,
)

SCHEMA = "c3r-g1-semantic-clarity-v0.1"
MODEL = "glm-5.3"
EFFORT = "high"
MAX_TOKENS = 4096
ROUTE = "coding"
CAMPAIGN_SLOTS = 32
INPUTS_PER_PROGRAM_PER_WAVE = 2

AMBIGUOUS_STEP2 = {
    "A": "Step 2: insert '-' after every second character.",
    "B": "Step 2: insert '_' after every third character.",
}
PRECISE_STEP2 = {
    "A": "Step 2: insert '-' between consecutive pairs of two "
         "characters, with no separator at the end of the string.",
    "B": "Step 2: insert '_' between consecutive groups of three "
         "characters, with no separator at the end of the string.",
}


class ClarityLedger:
    """Cross-process O_EXCL slot ledger enforcing the 32-send cap."""

    def __init__(self, root: Path, run_id: str) -> None:
        self.root = root
        self.run_id = run_id
        self._lock = threading.Lock()
        self.root.mkdir(parents=True, exist_ok=True)

    def _slot_path(self, index: int) -> Path:
        return self.root / f"clarity-slot-{index:03d}.json"

    def reserve(self, index: int, session: str) -> None:
        with self._lock:
            path = self._slot_path(index)
            if path.exists():
                raise RuntimeError(f"slot {index} already reserved: double dispatch")
            if index >= CAMPAIGN_SLOTS:
                raise RuntimeError(f"slot {index} exceeds the 32-send cap")
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
        return sum(1 for _ in self.root.glob("clarity-slot-*.json"))


def rotate_programs() -> list[dict[str, str]]:
    programs = [p for p in all_programs() if p["family"] == "rotate"]
    if len(programs) != 4:
        raise RuntimeError("expected exactly 4 frozen rotate programs")
    return programs


def _rotate_position(program_id: str) -> int:
    for position, program in enumerate(rotate_programs()):
        if program["program_id"] == program_id:
            return position
    raise ValueError(f"unknown rotate program id: {program_id}")


def arm_slot(arm: str, wave: str, position: int, input_index: int) -> int:
    """Slots 0..15 = arm a, 16..31 = arm b; 8 per (arm, wave)."""

    return (
        (0 if arm == "a" else 16)
        + WAVES.index(wave) * 8
        + position * INPUTS_PER_PROGRAM_PER_WAVE
        + input_index
    )


def slot_plan() -> list[dict[str, object]]:
    plan: list[dict[str, object]] = []
    for arm in ("a", "b"):
        for wave in WAVES:
            for program in rotate_programs():
                position = _rotate_position(program["program_id"])
                for input_index in range(INPUTS_PER_PROGRAM_PER_WAVE):
                    plan.append({
                        "index": arm_slot(arm, wave, position, input_index),
                        "arm": arm, "wave": wave,
                        "program_id": program["program_id"],
                        "input_index": input_index,
                    })
    return sorted(plan, key=lambda row: row["index"])  # type: ignore[return-value]


def arm_steps(family: str, code: str, arm: str) -> list[str]:
    """The 5 procedure lines; arm b swaps ONLY the step-2 line."""

    if family != "rotate":
        raise ValueError("semantic-clarity campaign is rotate-only")
    lines = _natural_step_instructions(family, code)
    branch = code[1]
    if lines[1] != AMBIGUOUS_STEP2[branch]:
        raise RuntimeError(
            "upstream rotate step-2 text changed: re-audit the design"
        )
    if arm == "b":
        lines[1] = PRECISE_STEP2[branch]
    return lines


def _task_input(family: str, program_id: str, wave: str, input_index: int) -> str:
    """Deterministic fresh unambiguous input: all 32 codes stay distinct."""
    from c3r_g1_novel_grammar_families import CODES, _execute as novel_execute

    for attempt in range(500):
        digest = hashlib.sha256(
            f"semantic-clarity:v1:{program_id}:{wave}:{input_index}:{attempt}"
            .encode()
        ).digest()
        rng = random.Random(digest)
        value = "".join(rng.choices("abcdefghijklmnopqrstuvwxyz", k=6))
        outputs = {
            novel_execute(family, {"value": value}, code) for code in CODES
        }
        if len(outputs) == 32:
            return value
    raise ValueError(
        f"unable to sample unambiguous input: {program_id}/{wave}/{input_index}"
    )


def _truth(family: str, input_value: str, code: str) -> str:
    from c3r_g1_novel_grammar_families import _execute as novel_execute

    return novel_execute(family, {"value": input_value}, code)


def _build_prompt(family: str, steps: list[str], input_value: str) -> str:
    return (
        "This is a new isolated agent session. Execute the following "
        "five-step procedure IN ORDER on the new task below. Output ONLY "
        "the final value, without reasoning, markdown or labels.\n"
        f"{_grammar_text(family)}\n"
        "The procedure, as explicit steps:\n" + "\n".join(steps) + "\n"
        f'New task: {json.dumps({"value": input_value}, sort_keys=True)}\n'
        "Answer with only the final result."
    )


def _campaign_tasks() -> list[dict[str, object]]:
    tasks: list[dict[str, object]] = []
    for program in rotate_programs():
        pid = program["program_id"]
        for wave in WAVES:
            for input_index in range(INPUTS_PER_PROGRAM_PER_WAVE):
                input_value = _task_input(
                    program["family"], pid, wave, input_index
                )
                tasks.append({
                    "program_id": pid,
                    "family": program["family"],
                    "program_code": program["program"],
                    "wave": wave,
                    "input_index": input_index,
                    "input": input_value,
                    "truth": _truth(program["family"], input_value,
                                    program["program"]),
                    "steps_ambiguous": arm_steps(
                        program["family"], program["program"], "a"
                    ),
                    "steps_precise": arm_steps(
                        program["family"], program["program"], "b"
                    ),
                })
    return tasks


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
        "programs": rotate_programs(),
        "tasks": _campaign_tasks(),
        "slots": slot_plan(),
        "campaign_slots": CAMPAIGN_SLOTS,
        "scientific_acceptance": False,
    }
    path = workspace / "clarity-manifest.json"
    if path.exists():
        existing = json.loads(path.read_text(encoding="utf-8"))
        frozen_fields = ("programs", "tasks", "slots")
        if any(existing[field] != manifest[field] for field in frozen_fields):
            raise ValueError("manifest drift: frozen campaign changed")
        print("manifest already frozen and identical", flush=True)
        return existing
    _write_json(path, manifest)
    print(f"manifest frozen: {path}", flush=True)
    return manifest


def _load_manifest(workspace: Path) -> dict[str, object]:
    path = workspace / "clarity-manifest.json"
    if not path.exists():
        raise FileNotFoundError(
            "frozen manifest missing: run the manifest session first"
        )
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if any(
        manifest[field] != expected
        for field, expected in (
            ("programs", rotate_programs()),
            ("tasks", _campaign_tasks()),
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


def run_send(workspace: Path, run_id: str, arm: str, wave: str,
             api_key: str) -> dict[str, object]:
    """One (arm, wave) session: 8 single-shot sends."""

    manifest = _load_manifest(workspace)
    ledger = ClarityLedger(workspace / "clarity-ledger", run_id)
    steps_key = "steps_ambiguous" if arm == "a" else "steps_precise"
    tasks = [t for t in manifest["tasks"] if t["wave"] == wave]
    rows: list[dict[str, object]] = []

    for task in tasks:
        position = _rotate_position(task["program_id"])
        slot = arm_slot(arm, wave, position, task["input_index"])
        prompt = _build_prompt(
            task["family"], task[steps_key], task["input"]
        )
        ledger.reserve(slot, f"{arm}-{task['program_id']}-{task['input_index']}")
        started = time.monotonic()
        try:
            completion = _dispatch(api_key, prompt)
            answer = completion.output.strip()
            finish = completion.finish_reason
        except Exception as exc:
            rows.append({
                "program_id": task["program_id"], "wave": wave,
                "input_index": task["input_index"], "arm": arm,
                "input": task["input"], "truth": task["truth"],
                "status": "provider_error",
                "failure_class": type(exc).__name__[:40],
                "answer": None, "correct": None, "itt_success": False,
                "slot": slot,
                "latency_ms": round((time.monotonic() - started) * 1000, 1),
            })
            print(f"[{arm}] {wave} {task['program_id']}#"
                  f"{task['input_index']}: provider_error "
                  f"({type(exc).__name__})", flush=True)
            continue
        parseable = finish == "stop" and bool(answer)
        correct = (answer == task["truth"]) if parseable else None
        rows.append({
            "program_id": task["program_id"], "wave": wave,
            "input_index": task["input_index"], "arm": arm,
            "input": task["input"], "truth": task["truth"],
            "status": "evaluated" if parseable else "unscored",
            "answer": answer, "correct": correct,
            "itt_success": correct is True,
            "slot": slot,
            "latency_ms": round((time.monotonic() - started) * 1000, 1),
        })
        print(f"[{arm}] {wave} {task['program_id']}#{task['input_index']}: "
              f"answer={answer!r} correct={correct}", flush=True)

    summary = {
        "schema": SCHEMA,
        "session": f"{arm}-{wave}",
        "arm": arm,
        "wave": wave,
        "sends": len(rows),
        "itt_successes": sum(1 for row in rows if row["itt_success"] is True),
        "rows": rows,
    }
    out = workspace / f"summary-{arm}-{wave}.json"
    _write_json(out, summary)
    print(f"summary written: {out}", flush=True)
    return summary


def run_report(workspace: Path) -> dict[str, object]:
    """Offline paired ITT aggregation against the predeclared criterion."""

    required = [
        f"summary-{arm}-{wave}.json"
        for arm in ("a", "b") for wave in WAVES
    ]
    missing = [name for name in required if not (workspace / name).exists()]
    if missing:
        raise FileNotFoundError(f"campaign incomplete, missing summaries: {missing}")

    rows: list[dict[str, object]] = []
    sends = 0
    for name in required:
        summary = json.loads((workspace / name).read_text(encoding="utf-8"))
        sends += summary["sends"]
        rows.extend(summary["rows"])

    by_key: dict[tuple[str, str, int], dict[str, bool]] = {}
    for row in rows:
        key = (row["program_id"], row["wave"], row["input_index"])
        by_key.setdefault(key, {})[row["arm"]] = row["itt_success"] is True

    both = sum(1 for p in by_key.values() if p.get("a") and p.get("b"))
    b_only = sum(1 for p in by_key.values() if p.get("b") and not p.get("a"))
    a_only = sum(1 for p in by_key.values() if p.get("a") and not p.get("b"))
    neither = sum(1 for p in by_key.values()
                  if not p.get("a") and not p.get("b"))
    a_itt = sum(1 for p in by_key.values() if p.get("a"))
    b_itt = sum(1 for p in by_key.values() if p.get("b"))
    paired_diff = b_itt - a_itt

    criterion_b = b_itt >= 15
    criterion_paired = paired_diff >= 4
    verdict = (
        "predeclared success criterion MET: specification ambiguity is "
        "the dominant residual cause"
        if criterion_b and criterion_paired
        else "predeclared success criterion NOT MET: the wording-fix "
             "path is CLOSED"
    )

    report = {
        "schema": SCHEMA,
        "campaign": "g1-semantic-clarity-instructions-20261028",
        "tasks": len(by_key),
        "sends_total": sends,
        "send_cap": CAMPAIGN_SLOTS,
        "paired_table": {"both_correct": both, "b_only": b_only,
                         "a_only": a_only, "both_failed": neither},
        "a_itt_ambiguous": a_itt,
        "b_itt_precise": b_itt,
        "paired_b_minus_a": paired_diff,
        "criterion_b_at_least_15_of_16": criterion_b,
        "criterion_paired_diff_at_least_4": criterion_paired,
        "verdict": verdict,
        "scientific_acceptance": False,
    }
    _write_json(workspace / "clarity-report.json", report)
    print(json.dumps(report, indent=2, sort_keys=True), flush=True)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="G1 semantic clarity of procedural instructions"
    )
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--session", required=True,
                        choices=("manifest", "send", "report"))
    parser.add_argument("--arm", choices=("a", "b"))
    parser.add_argument("--wave", choices=WAVES)
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
    if not (args.arm and args.wave):
        parser.error("send sessions require --arm and --wave")
    run_send(workspace, args.run_id, args.arm, args.wave, args.api_key)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
