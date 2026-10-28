"""G1 natural stepwise execution fidelity: live dispatch (96-send cap).

Owner GO (2026-10-28): test whether step-by-step execution of a correct
natural-language procedure with visible intermediate states raises final-
task success above the single-shot baseline (75% ITT), WITHOUT adding any
information about the hidden truth.

Frozen design (research/c3r_g2/G1_NATURAL_STEPWISE_EXECUTION_FIDELITY_
PROSPECTIVE_20261027.md): 8 public programs x 2 waves, 1 fresh
unambiguous input per (program, wave) = 16 tasks.
- Arm A (single-shot): 1 send per task — full NL procedure + input → final.
- Arm B (stepwise):    5 sends per task — one per step: current state +
  "apply Step N: <instruction>" → intermediate state. After step 5 the
  final state is the answer.

ITT: a task fails if any step's output is unparseable or the final value
is wrong. All failures preserved in the denominator. Hard cap 96
(16 A + 80 B) enforced by an O_EXCL slot ledger shared across sessions.

Sessions (one CLI process each, no retries anywhere):
- manifest: freeze programs, per-task inputs/truths and the full 96-slot
  plan; re-running verifies identity and refuses drift.
- send --arm a --wave W:        8 sends (slots for that wave).
- send --arm b --wave W --program P: 5 sends (that task's slot block).
- report: offline aggregation of all 18 summaries into the paired ITT
  verdict against the predeclared criterion. Sends nothing.
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

SCHEMA = "c3r-g1-stepwise-execution-v0.1"
MODEL = "glm-5.3"
EFFORT = "high"
MAX_TOKENS = 4096
ROUTE = "coding"
CAMPAIGN_SLOTS = 96
A_SLOTS = 16
B_SLOTS = 80
STEPS = 5


class StepwiseLedger:
    """Cross-process O_EXCL slot ledger enforcing the 96-send cap."""

    def __init__(self, root: Path, run_id: str) -> None:
        self.root = root
        self.run_id = run_id
        self._lock = threading.Lock()
        self.root.mkdir(parents=True, exist_ok=True)

    def _slot_path(self, index: int) -> Path:
        return self.root / f"stepwise-slot-{index:03d}.json"

    def reserve(self, index: int, session: str) -> None:
        with self._lock:
            path = self._slot_path(index)
            if path.exists():
                raise RuntimeError(f"slot {index} already reserved: double dispatch")
            if index >= CAMPAIGN_SLOTS:
                raise RuntimeError(f"slot {index} exceeds the 96-send cap")
            payload = json.dumps({
                "run_id": self.run_id, "session": session, "index": index,
                "reserved_no_retry": True,
            }, sort_keys=True).encode() + b"\n"
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "wb") as out:
                out.write(payload)
                out.flush()
                os.fsync(out.fileno())

    def reserve_block(self, indices: list[int], session: str) -> None:
        for index in indices:
            self.reserve(index, session)

    @property
    def consumed(self) -> int:
        return sum(1 for _ in self.root.glob("stepwise-slot-*.json"))


def _program_position(program_id: str) -> int:
    for position, program in enumerate(all_programs()):
        if program["program_id"] == program_id:
            return position
    raise ValueError(f"unknown program id: {program_id}")


def arm_a_slot(wave: str, position: int) -> int:
    """Arm A slots 0..15: one per (program, wave)."""

    return WAVES.index(wave) * 8 + position


def arm_b_slot(wave: str, position: int, step: int) -> int:
    """Arm B slots 16..95: five consecutive per (program, wave)."""

    return A_SLOTS + (WAVES.index(wave) * 8 + position) * STEPS + step


def arm_b_slot_block(wave: str, position: int) -> list[int]:
    return [arm_b_slot(wave, position, step) for step in range(STEPS)]


def slot_plan() -> list[dict[str, object]]:
    """The full frozen 96-slot campaign plan (deterministic)."""

    plan: list[dict[str, object]] = []
    for program in all_programs():
        position = _program_position(program["program_id"])
        for wave in WAVES:
            plan.append({
                "index": arm_a_slot(wave, position),
                "arm": "a", "wave": wave,
                "program_id": program["program_id"], "step": None,
            })
            for step in range(STEPS):
                plan.append({
                    "index": arm_b_slot(wave, position, step),
                    "arm": "b", "wave": wave,
                    "program_id": program["program_id"], "step": step,
                })
    return sorted(plan, key=lambda row: row["index"])  # type: ignore[return-value]


def _natural_step_instructions(family: str, code: str) -> list[str]:
    """The 5 step instruction lines, CORRECT w.r.t. the frozen evaluator.

    Apparatus defect found in offline pre-dispatch testing (2026-10-28):
    the frozen `_natural_instructions` renders the rotate step-5 B branch
    as "prepend '5'" while the frozen evaluator (`c3r_g1_novel_grammar_
    families._execute`) prepends '9' for that branch. The registered
    design requires a CORRECT procedure (intermediate states fully
    determined by (input, procedure)); this campaign therefore renders
    that one branch as '9', matching the evaluator. The published
    representation-comparison numbers (20261027) inherited the defect and
    are reported to the owner as a baseline caveat, not re-scored here.
    """
    from c3r_g1_procedure_representation import _natural_instructions

    text = _natural_instructions(family, code)
    lines = [
        line.strip() for line in text.splitlines()
        if line.strip().startswith("Step ")
    ]
    defective = "Step 5: prepend '5' to the beginning."
    corrected = "Step 5: prepend '9' to the beginning."
    if family == "rotate" and code[4] == "B":
        if lines[4] != defective:
            raise RuntimeError(
                "upstream rotate step-5 B text changed: re-audit the defect"
            )
        lines[4] = corrected
    return lines


def _bare_step_instruction(step_lines: list[str], step_number: int) -> str:
    """Strip the 'Step N:' prefix: the registered step prompt embeds the
    instruction text itself after 'Apply Step N:' (no doubled prefix)."""

    line = step_lines[step_number - 1]
    head, _, rest = line.partition(":")
    if not head.strip() == f"Step {step_number}" or not rest.strip():
        raise ValueError(f"malformed step line {step_number}: {line!r}")
    return rest.strip()


def _grammar_text(family: str) -> str:
    if family == "digits":
        return (
            "The input is a 4-digit decimal string. The five steps operate on "
            "the digits: swapping or reordering them, keeping a subset, "
            "transforming individual digit values, sorting, and prefixing or "
            "appending the count."
        )
    return (
        "The input is a 6-letter lowercase string. The five steps operate on "
        "the string: rotating, inserting separators, keeping a subset, "
        "swapping pairs, and appending or prepending a digit."
    )


def _build_single_shot_prompt(family: str, code: str, input_value: str) -> str:
    steps = _natural_step_instructions(family, code)
    grammar = _grammar_text(family)
    return (
        "This is a new isolated agent session. Execute the following "
        "five-step procedure IN ORDER on the new task below. Output ONLY "
        "the final value, without reasoning, markdown or labels.\n"
        f"{grammar}\n"
        "The procedure, as explicit steps:\n" + "\n".join(steps) + "\n"
        f'New task: {json.dumps({"value": input_value}, sort_keys=True)}\n'
        "Answer with only the final result."
    )


def _build_step_prompt(step_number: int, instruction: str,
                       current_state: str) -> str:
    return (
        "You have an intermediate state and must apply exactly ONE step "
        "to it. Do NOT skip ahead or combine steps.\n"
        f"Current state: {json.dumps(current_state)}\n"
        f"Apply Step {step_number}: {instruction}\n"
        "Answer with only the transformed value."
    )


def _task_input(family: str, program_id: str, wave: str) -> str:
    """Deterministic fresh unambiguous input: all 32 codes stay distinct."""
    from c3r_g1_novel_grammar_families import CODES, _execute as novel_execute

    for attempt in range(500):
        digest = hashlib.sha256(
            f"stepwise:{program_id}:{wave}:{attempt}".encode()
        ).digest()
        rng = random.Random(digest)
        if family == "rotate":
            value = "".join(rng.choices("abcdefghijklmnopqrstuvwxyz", k=6))
        else:
            value = "".join(rng.choices("0123456789", k=4))
        outputs = {
            novel_execute(family, {"value": value}, code) for code in CODES
        }
        if len(outputs) == 32:
            return value
    raise ValueError(f"unable to sample unambiguous input: {family}/{program_id}/{wave}")


def _execute(family: str, task: dict, code: str) -> str:
    from c3r_g1_novel_grammar_families import _execute as novel_execute

    return novel_execute(family, task, code)


def _write_json(path: Path, record: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _campaign_tasks() -> list[dict[str, object]]:
    """The 16 frozen (program, wave) tasks with inputs and truths."""

    tasks = []
    for program in all_programs():
        pid = program["program_id"]
        for wave in WAVES:
            input_value = _task_input(program["family"], pid, wave)
            tasks.append({
                "program_id": pid,
                "family": program["family"],
                "program_code": program["program"],
                "steps": _natural_step_instructions(
                    program["family"], program["program"]
                ),
                "wave": wave,
                "input": input_value,
                "truth": _execute(
                    program["family"], {"value": input_value}, program["program"]
                ),
            })
    return tasks


def run_manifest(workspace: Path, run_id: str) -> dict[str, object]:
    manifest = {
        "schema": SCHEMA,
        "run_id": run_id,
        "model": MODEL,
        "reasoning_effort": EFFORT,
        "max_tokens": MAX_TOKENS,
        "route": ROUTE,
        "programs": all_programs(),
        "tasks": _campaign_tasks(),
        "slots": slot_plan(),
        "campaign_slots": CAMPAIGN_SLOTS,
        "scientific_acceptance": False,
    }
    path = workspace / "stepwise-manifest.json"
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
    path = workspace / "stepwise-manifest.json"
    if not path.exists():
        raise FileNotFoundError(
            "frozen manifest missing: run the manifest session first"
        )
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if any(
        manifest[field] != expected
        for field, expected in (
            ("programs", all_programs()),
            ("tasks", _campaign_tasks()),
            ("slots", slot_plan()),
        )
    ):
        raise ValueError("manifest drift: frozen campaign changed")
    return manifest


def _dispatch(api_key: str, prompt: str):
    """One bounded send: fresh port + single-slot physical ledger."""

    return ZaiStandardModelPort(
        api_key=api_key,
        model_id=MODEL,
        ledger=PhysicalSendLedger(1),
        enabled=True,
        route=ROUTE,
        reasoning_effort=EFFORT,
        max_tokens=MAX_TOKENS,
    ).complete_prompt(prompt)


def _task_row_prefix(task: dict[str, object], arm: str) -> dict[str, object]:
    return {
        "program_id": task["program_id"],
        "family": task["family"],
        "wave": task["wave"],
        "arm": arm,
        "input": task["input"],
        "truth": task["truth"],
    }


def run_arm_a(workspace: Path, run_id: str, wave: str, api_key: str) -> dict[str, object]:
    """Single-shot session: 8 tasks x 1 send for one wave."""

    manifest = _load_manifest(workspace)
    ledger = StepwiseLedger(workspace / "stepwise-ledger", run_id)
    tasks = [t for t in manifest["tasks"] if t["wave"] == wave]
    rows: list[dict[str, object]] = []

    for task in tasks:
        position = _program_position(task["program_id"])
        slot = arm_a_slot(wave, position)
        prompt = _build_single_shot_prompt(
            task["family"], task["program_code"], task["input"]
        )
        ledger.reserve(slot, f"a-{task['program_id']}")
        started = time.monotonic()
        try:
            completion = _dispatch(api_key, prompt)
            answer = completion.output.strip()
            finish = completion.finish_reason
        except Exception as exc:
            rows.append({
                **_task_row_prefix(task, "a"),
                "status": "provider_error",
                "failure_class": type(exc).__name__[:40],
                "sends": 1, "slots": [slot],
                "steps": [{"slot": slot, "step": None,
                           "status": "provider_error",
                           "failure_class": type(exc).__name__[:40],
                           "answer": None, "finish_reason": None,
                           "latency_ms": round((time.monotonic() - started) * 1000, 1)}],
                "correct": None, "itt_success": False,
            })
            print(f"[a] {wave} {task['program_id']}: provider_error "
                  f"({type(exc).__name__})", flush=True)
            continue
        parseable = finish == "stop" and bool(answer)
        correct = (answer == task["truth"]) if parseable else None
        rows.append({
            **_task_row_prefix(task, "a"),
            "status": "evaluated" if parseable else "unscored",
            "sends": 1, "slots": [slot],
            "steps": [{"slot": slot, "step": None,
                       "status": "sent_ok" if parseable else "unscored",
                       "answer": answer, "finish_reason": finish,
                       "latency_ms": round((time.monotonic() - started) * 1000, 1)}],
            "correct": correct,
            "itt_success": correct is True,
        })
        print(f"[a] {wave} {task['program_id']}: answer={answer!r} "
              f"correct={correct}", flush=True)

    summary = _session_summary("a", f"a-{wave}", wave, None, rows)
    _write_json(workspace / f"summary-a-{wave}.json", summary)
    print(f"summary written: {workspace / f'summary-a-{wave}.json'}", flush=True)
    return summary


def run_arm_b(workspace: Path, run_id: str, wave: str, program_id: str,
             api_key: str) -> dict[str, object]:
    """Stepwise session: one task, 5 sends, state chained send-to-send."""

    manifest = _load_manifest(workspace)
    ledger = StepwiseLedger(workspace / "stepwise-ledger", run_id)
    task = next(
        t for t in manifest["tasks"]
        if t["wave"] == wave and t["program_id"] == program_id
    )
    position = _program_position(program_id)
    instructions = task["steps"] if "steps" in task else _natural_step_instructions(
        task["family"], task["program_code"]
    )
    if len(instructions) != STEPS:
        raise RuntimeError(
            f"procedure does not render as {STEPS} steps: {program_id}"
        )

    state = task["input"]
    step_records: list[dict[str, object]] = []
    used_slots: list[int] = []
    failure: dict[str, object] | None = None

    for step_idx in range(STEPS):
        slot = arm_b_slot(wave, position, step_idx)
        prompt = _build_step_prompt(
            step_idx + 1,
            _bare_step_instruction(instructions, step_idx + 1),
            state,
        )
        ledger.reserve(slot, f"b-{program_id}-{step_idx}")
        used_slots.append(slot)
        started = time.monotonic()
        try:
            completion = _dispatch(api_key, prompt)
            answer = completion.output.strip()
            finish = completion.finish_reason
        except Exception as exc:
            failure = {"status": "provider_error",
                       "failure_class": type(exc).__name__[:40]}
            step_records.append({
                "slot": slot, "step": step_idx + 1,
                "status": "provider_error",
                "failure_class": type(exc).__name__[:40],
                "answer": None, "finish_reason": None,
                "latency_ms": round((time.monotonic() - started) * 1000, 1),
            })
            break
        parseable = finish == "stop" and bool(answer)
        step_records.append({
            "slot": slot, "step": step_idx + 1,
            "status": "sent_ok" if parseable else "unscored",
            "answer": answer, "finish_reason": finish,
            "latency_ms": round((time.monotonic() - started) * 1000, 1),
        })
        if not parseable:
            failure = {"status": "unscored", "failure_class": None}
            break
        state = answer

    if failure is not None:
        status = failure["status"]
        correct: bool | None = None
        itt_success = False
    else:
        status = "evaluated"
        correct = state == task["truth"]
        itt_success = correct is True

    row = {
        **_task_row_prefix(task, "b"),
        "status": status,
        "failure_class": failure["failure_class"] if failure else None,
        "sends": len(used_slots), "slots": used_slots,
        "steps": step_records,
        "final_state": state if failure is None else None,
        "correct": correct,
        "itt_success": itt_success,
    }
    print(f"[b] {wave} {program_id}: status={status} correct={correct} "
          f"sends={len(used_slots)}", flush=True)

    summary = _session_summary("b", f"b-{wave}-{program_id}", wave, program_id, [row])
    _write_json(
        workspace / f"summary-b-{wave}-{program_id}.json", summary
    )
    print(f"summary written: {workspace / f'summary-b-{wave}-{program_id}.json'}",
          flush=True)
    return summary


def _session_summary(arm: str, session: str, wave: str,
                     program_id: str | None,
                     rows: list[dict[str, object]]) -> dict[str, object]:
    return {
        "schema": SCHEMA,
        "session": session,
        "arm": arm,
        "wave": wave,
        "program_id": program_id,
        "tasks": len(rows),
        "sends": sum(row["sends"] for row in rows),
        "itt_successes": sum(1 for row in rows if row["itt_success"] is True),
        "rows": rows,
    }


def run_report(workspace: Path) -> dict[str, object]:
    """Offline paired ITT aggregation against the predeclared criterion."""

    required = (
        [f"summary-a-{wave}.json" for wave in WAVES]
        + [f"summary-b-{wave}-{p['program_id']}.json"
           for p in all_programs() for wave in WAVES]
    )
    missing = [name for name in required if not (workspace / name).exists()]
    if missing:
        raise FileNotFoundError(f"campaign incomplete, missing summaries: {missing}")

    rows: list[dict[str, object]] = []
    sends = 0
    for name in required:
        summary = json.loads((workspace / name).read_text(encoding="utf-8"))
        sends += summary["sends"]
        rows.extend(summary["rows"])

    by_key: dict[tuple[str, str], dict[str, bool]] = {}
    for row in rows:
        key = (row["program_id"], row["wave"])
        by_key.setdefault(key, {})[row["arm"]] = row["itt_success"] is True

    a_itt = sum(1 for pair in by_key.values() if pair.get("a"))
    b_itt = sum(1 for pair in by_key.values() if pair.get("b"))
    b_only = sum(1 for pair in by_key.values() if pair.get("b") and not pair.get("a"))
    a_only = sum(1 for pair in by_key.values() if pair.get("a") and not pair.get("b"))
    paired_diff = b_itt - a_itt

    criterion_b = b_itt >= 14
    criterion_paired = paired_diff >= 3
    verdict = (
        "predeclared success criterion MET"
        if criterion_b and criterion_paired
        else "predeclared success criterion NOT MET"
    )

    step_failures: dict[str, int] = {}
    for row in rows:
        if row["arm"] != "b" or row["itt_success"]:
            continue
        for step in row["steps"]:
            if step["status"] != "sent_ok":
                step_failures[str(step["step"])] = (
                    step_failures.get(str(step["step"]), 0) + 1
                )
                break

    report = {
        "schema": SCHEMA,
        "campaign": "g1-natural-stepwise-execution-fidelity-20261028",
        "tasks": len(by_key),
        "sends_total": sends,
        "send_cap": CAMPAIGN_SLOTS,
        "a_itt_successes": a_itt,
        "b_itt_successes": b_itt,
        "paired_b_minus_a": paired_diff,
        "discordant_b_only": b_only,
        "discordant_a_only": a_only,
        "b_step_failure_positions": step_failures,
        "criterion_b_at_least_14_of_16": criterion_b,
        "criterion_paired_diff_at_least_3": criterion_paired,
        "verdict": verdict,
        "scientific_acceptance": False,
    }
    _write_json(workspace / "stepwise-report.json", report)
    print(json.dumps(report, indent=2, sort_keys=True), flush=True)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="G1 stepwise execution fidelity")
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--session", required=True,
                        choices=("manifest", "send", "report"))
    parser.add_argument("--arm", choices=("a", "b"))
    parser.add_argument("--wave", choices=WAVES)
    parser.add_argument("--program")
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
    if args.arm == "a":
        if args.program:
            parser.error("arm a is single-shot: no --program")
        run_arm_a(workspace, args.run_id, args.wave, args.api_key)
        return 0
    if not args.program:
        parser.error("arm b send sessions require --program (one task, 5 sends)")
    run_arm_b(workspace, args.run_id, args.wave, args.program, args.api_key)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
