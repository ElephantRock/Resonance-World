"""G1 feedback-acquired procedural memory v2: operational rehabilitation.

Owner conditional GO (2026-10-28 evening): ONE re-calibrated attempt of
the closed v1 campaign. Changes vs v1 (and only these): per-call
timeout 300 s; induction requests (learning loop AND the Raw arm) at
max_tokens 16384 (Learned/Fresh stay at 4096); NEW units (v2 seed
codes/inputs over the same frozen binary/alpha families); independent
96-slot O_EXCL ledger; a bounded technical QUALIFICATION session that
gates the whole campaign — if the new operating point still cannot
produce a capsule or complete a Raw send, nothing else dispatches.

Frozen design: research/c3r_g2/G1_FEEDBACK_ACQUIRED_PROCEDURAL_MEMORY_
V2_PROSPECTIVE_20261028.md. Gate identical to v1: Learned >= 10/16 AND
Learned-Fresh >= +8 AND Learned-Raw >= +4. Owner decision table:
qualification fails -> operating point closed; gate fails -> the
acquisition mechanism closes; gate passes -> consider C3R-G2 via an
independent protocol. No Probe sends; no v1 request is re-sent.

Slot plan (96): qualification 88..95 (<= 6 sends); learning 10 slots
per program -> 0..39; Learned 40..55; Raw 56..71; Fresh 72..87.
The prompt templates are imported UNCHANGED from the v1 module.
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
    all_programs as v1_programs,
    all_programs_v2,
    derive_input,
    is_unambiguous,
    _execute as feedback_execute,
)
from resonance_world.c3r_g1_zai_transport import PhysicalSendLedger, ZaiStandardModelPort
from run_c3r_g1_feedback_memory_live import (
    EMPTY_GUARD_SUFFIX,
    _capsule_five_steps,
    _write_json,
    apply_prompt,
    draft_prompt,
    exec_fresh_prompt,
    exec_learned_prompt,
    exec_raw_prompt,
    revise_prompt,
    program_plan as v1_program_plan,
)

SCHEMA = "c3r-g1-feedback-memory2-v0.1"
MODEL = "glm-5.3"
EFFORT = "high"
EXEC_MAX_TOKENS = 4096          # Learned / Fresh arms (frozen)
INDUCTION_MAX_TOKENS = 16384    # learning loop + Raw arm (A2 calibration)
TIMEOUT_SECONDS = 300.0
ROUTE = "coding"
CAMPAIGN_SLOTS = 96
LEARNING_BLOCK = 10
EVIDENCE_PAIRS = 3
MAX_ROUNDS = 3
EVAL_INPUTS = 4
EXEC_BASES = {"learned": 40, "raw": 56, "fresh": 72}
EXEC_TASKS = 16
QUAL_BASE = 88
QUAL_BUDGET = 6


class Feedback2Ledger:
    """Independent cross-process O_EXCL ledger enforcing the 96-send cap."""

    def __init__(self, root: Path, run_id: str) -> None:
        self.root = root
        self.run_id = run_id
        self._lock = threading.Lock()
        self.root.mkdir(parents=True, exist_ok=True)

    def _slot_path(self, index: int) -> Path:
        return self.root / f"feedback2-slot-{index:03d}.json"

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

    @property
    def consumed(self) -> int:
        return sum(1 for _ in self.root.glob("feedback2-slot-*.json"))


def _program_position(program_id: str) -> int:
    for position, program in enumerate(all_programs_v2()):
        if program["program_id"] == program_id:
            return position
    raise ValueError(f"unknown v2 program id: {program_id}")


def _truth(family: str, input_value: str, code: str) -> str:
    return feedback_execute(family, {"value": input_value}, code)


def _v1_inputs() -> set[str]:
    used: set[str] = set()
    for program in v1_programs():
        v1_program_plan(program, used)
    return used


_V1_INPUTS_CACHE: set[str] | None = None


def _cached_v1_inputs() -> set[str]:
    global _V1_INPUTS_CACHE
    if _V1_INPUTS_CACHE is None:
        _V1_INPUTS_CACHE = _v1_inputs()
    return set(_V1_INPUTS_CACHE)


_QUAL_INPUTS_CACHE: set[str] | None = None


def _qual_input_values() -> set[str]:
    global _QUAL_INPUTS_CACHE
    if _QUAL_INPUTS_CACHE is None:
        qual = qualification_plan()
        _QUAL_INPUTS_CACHE = (
            {pair["input"] for pair in qual["evidence"]}
            | {qual["probe"], qual["raw_input"]}
        )
    return set(_QUAL_INPUTS_CACHE)


def program_plan_v2(program: dict[str, str],
                    used: set[str] | None = None) -> dict[str, object]:
    """v2 evidence/probes/eval inputs; v1 AND qualification inputs are
    pre-excluded, so every value in the whole v2 apparatus is unique."""

    pid = program["program_id"]
    family = program["family"]
    code = program["program"]
    used = used if used is not None else set()
    used |= _cached_v1_inputs()
    used |= _qual_input_values()
    used_before = len(used)

    def next_input(role: str, index: int) -> str:
        value = derive_input(family, pid, role, index,
                             exclude=frozenset(used), version=2)
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
        {"input_index": i, "input": next_input("eval", i), "truth": None}
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


def campaign_plan_v2() -> list[dict[str, object]]:
    used: set[str] = set()
    plans = []
    for program in all_programs_v2():
        plans.append(program_plan_v2(program, used))
    return plans


def campaign_tasks_v2() -> list[dict[str, object]]:
    tasks = []
    for plan in campaign_plan_v2():
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


def qualification_plan() -> dict[str, object]:
    """The dedicated qualification unit (never part of the evaluation)."""

    program = {
        "program_id": "prog-binary-qual",
        "family": "binary",
        "program": None,  # filled below
    }
    from c3r_g1_feedback_families import qualification_program

    code = qualification_program()["program"]
    program["program"] = code
    used = _cached_v1_inputs()

    def next_input(role: str, index: int) -> str:
        value = derive_input("binary", "prog-binary-qual", role, index,
                             exclude=frozenset(used), version=2)
        used.add(value)
        return value

    evidence = []
    for i in range(EVIDENCE_PAIRS):
        value = next_input("qual-evidence", i)
        evidence.append(
            {"input": value, "output": _truth("binary", value, code)}
        )
    probe = next_input("qual-probe", 0)
    raw_input = next_input("qual-raw", 0)
    return {
        "program_id": program["program_id"], "family": "binary",
        "program_code": code, "evidence": evidence,
        "probe": probe, "probe_truth": _truth("binary", probe, code),
        "raw_input": raw_input,
        "raw_truth": _truth("binary", raw_input, code),
    }


def learn_slot(position: int, offset: int) -> int:
    return position * LEARNING_BLOCK + offset


def exec_slot(arm: str, program_id: str, input_index: int) -> int:
    return (
        EXEC_BASES[arm] + _program_position(program_id) * EVAL_INPUTS
        + input_index
    )


def slot_plan_v2() -> list[dict[str, object]]:
    plan: list[dict[str, object]] = []
    for program in all_programs_v2():
        for offset in range(LEARNING_BLOCK):
            plan.append({
                "index": learn_slot(
                    _program_position(program["program_id"]), offset
                ),
                "kind": "learning", "program_id": program["program_id"],
            })
    for arm in ("learned", "raw", "fresh"):
        for task in campaign_tasks_v2():
            plan.append({
                "index": exec_slot(arm, task["program_id"],
                                   task["input_index"]),
                "kind": "exec", "arm": arm,
                "program_id": task["program_id"],
                "input_index": task["input_index"],
            })
    # the qualification BLOCK is 88..95 (8 slots); the runtime budget
    # still caps qualification at QUAL_BUDGET sends within it
    for offset in range(8):
        plan.append({"index": QUAL_BASE + offset, "kind": "qualification"})
    return sorted(plan, key=lambda row: row["index"])  # type: ignore[return-value]


def run_manifest(workspace: Path, run_id: str) -> dict[str, object]:
    manifest = {
        "schema": SCHEMA,
        "run_id": run_id,
        "model": MODEL,
        "reasoning_effort": EFFORT,
        "max_tokens_exec": EXEC_MAX_TOKENS,
        "max_tokens_induction": INDUCTION_MAX_TOKENS,
        "timeout_seconds": TIMEOUT_SECONDS,
        "route": ROUTE,
        "programs": all_programs_v2(),
        "plan": campaign_plan_v2(),
        "qualification": qualification_plan(),
        "slots": slot_plan_v2(),
        "campaign_slots": CAMPAIGN_SLOTS,
        "scientific_acceptance": False,
    }
    path = workspace / "feedback2-manifest.json"
    if path.exists():
        existing = json.loads(path.read_text(encoding="utf-8"))
        frozen_fields = ("programs", "plan", "qualification", "slots")
        if any(existing[field] != manifest[field]
               for field in frozen_fields):
            raise ValueError("manifest drift: frozen campaign changed")
        print("manifest already frozen and identical", flush=True)
        return existing
    _write_json(path, manifest)
    print(f"manifest frozen: {path}", flush=True)
    return manifest


def _load_manifest(workspace: Path) -> dict[str, object]:
    path = workspace / "feedback2-manifest.json"
    if not path.exists():
        raise FileNotFoundError(
            "frozen manifest missing: run the manifest session first"
        )
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if any(
        manifest[field] != expected
        for field, expected in (
            ("programs", all_programs_v2()),
            ("plan", campaign_plan_v2()),
            ("qualification", qualification_plan()),
            ("slots", slot_plan_v2()),
        )
    ):
        raise ValueError("manifest drift: frozen campaign changed")
    return manifest


def _dispatch(api_key: str, prompt: str, max_tokens: int):
    return ZaiStandardModelPort(
        api_key=api_key,
        model_id=MODEL,
        ledger=PhysicalSendLedger(1),
        enabled=True,
        route=ROUTE,
        reasoning_effort=EFFORT,
        max_tokens=max_tokens,
        timeout_seconds=TIMEOUT_SECONDS,
    ).complete_prompt(prompt)


class _TransportAbort(RuntimeError):
    pass


class _BudgetExhausted(RuntimeError):
    pass


def _guarded_send(api_key: str, prompt: str, role: str, session: str,
                  ledger: Feedback2Ledger, cursor: dict, base: int,
                  block: int, events: list[dict[str, object]],
                  max_tokens: int) -> str | None:
    """One send with the empty-output guard (guard = a new ledgered send)."""

    for guard in (False, True):
        index = cursor["next"]
        if index >= base + block:
            raise _BudgetExhausted(f"budget exhausted during {role}")
        cursor["next"] = index + 1
        ledger.reserve(index, f"{session}-{role}")
        text = prompt + (EMPTY_GUARD_SUFFIX if guard else "")
        started = time.monotonic()
        try:
            completion = _dispatch(api_key, text, max_tokens)
        except Exception as exc:
            events.append({
                "role": role, "slot": index, "guard": guard,
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
            "role": role, "slot": index, "guard": guard,
            "status": "sent_ok" if parseable else "empty_answer",
            "answer": answer, "finish_reason": finish,
            "latency_ms": round((time.monotonic() - started) * 1000, 1),
        })
        if parseable:
            return answer
    return None


def run_qualify(workspace: Path, run_id: str, api_key: str) -> dict[str, object]:
    """The owner's qualification gate; gates the whole campaign."""

    manifest = _load_manifest(workspace)
    ledger = Feedback2Ledger(workspace / "feedback2-ledger", run_id)
    plan = manifest["qualification"]
    evidence: list[dict[str, str]] = plan["evidence"]
    events: list[dict[str, object]] = []
    cursor = {"next": QUAL_BASE}

    capsule = None
    capsule_ok = False
    apply_completed = False
    apply_correct = None
    raw_completed = False
    raw_correct = None
    failure = None

    try:
        capsule = _guarded_send(
            api_key, draft_prompt(evidence), "qual-draft", "qualify",
            ledger, cursor, QUAL_BASE, QUAL_BUDGET, events,
            INDUCTION_MAX_TOKENS,
        )
        capsule_ok = _capsule_five_steps(capsule)
        if not capsule_ok:
            failure = "capsule_not_five_step"
        else:
            produced = _guarded_send(
                api_key, apply_prompt(capsule, plan["probe"]),
                "qual-apply", "qualify", ledger, cursor,
                QUAL_BASE, QUAL_BUDGET, events, INDUCTION_MAX_TOKENS,
            )
            apply_completed = produced is not None
            if not apply_completed:
                failure = "apply_not_completing"
            else:
                apply_correct = produced == plan["probe_truth"]
            raw_answer = _guarded_send(
                api_key, exec_raw_prompt(evidence, plan["raw_input"]),
                "qual-raw", "qualify", ledger, cursor,
                QUAL_BASE, QUAL_BUDGET, events, INDUCTION_MAX_TOKENS,
            )
            raw_completed = raw_answer is not None
            if not raw_completed:
                failure = "raw_not_completing"
            else:
                raw_correct = raw_answer == plan["raw_truth"]
    except _TransportAbort as exc:
        failure = f"transport:{exc}"
    except _BudgetExhausted as exc:
        failure = f"budget:{exc}"

    outcome = {
        "schema": SCHEMA,
        "qualified": failure is None,
        "failure": failure,
        "checks": {
            "capsule_five_step": capsule_ok,
            "apply_completed": apply_completed,
            "apply_correct_informational": apply_correct,
            "raw_completed": raw_completed,
            "raw_correct_informational": raw_correct,
        },
        "capsule": capsule,
        "sends_used": len(events),
        "events": events,
    }
    _write_json(workspace / "qualification.json", outcome)
    print(
        f"[qualify] qualified={outcome['qualified']} failure={failure} "
        f"sends={len(events)}", flush=True,
    )
    return outcome


def run_learn(workspace: Path, run_id: str, program_id: str,
              api_key: str) -> dict[str, object]:
    """The v2 feedback learning loop for ONE program (<= 10 sends)."""

    manifest = _load_manifest(workspace)
    ledger = Feedback2Ledger(workspace / "feedback2-ledger", run_id)
    plan = next(p for p in manifest["plan"] if p["program_id"] == program_id)
    evidence: list[dict[str, str]] = plan["evidence"]
    probes: list[str] = plan["probes"]
    family: str = plan["family"]
    code: str = plan["program_code"]

    base = _program_position(program_id) * LEARNING_BLOCK
    cursor = {"next": base}
    events: list[dict[str, object]] = []

    def send(prompt: str, role: str) -> str | None:
        return _guarded_send(
            api_key, prompt, role, f"learn-{program_id}", ledger,
            cursor, base, LEARNING_BLOCK, events, INDUCTION_MAX_TOKENS,
        )

    draft: str | None = None
    validated = False
    validation_round: int | None = None
    aborted: str | None = None
    budget_exhausted = False

    try:
        draft = send(draft_prompt(evidence), "draft0")
        for round_index in range(1, MAX_ROUNDS + 1):
            if draft is None:
                break
            probe = probes[round_index - 1]
            expected = _truth(family, probe, code)
            produced = send(apply_prompt(draft, probe),
                            f"apply{round_index}")
            if produced is not None and produced == expected:
                validated = True
                validation_round = round_index
                break
            revised = send(
                revise_prompt(draft, evidence, probe, produced, expected),
                f"revise{round_index}",
            )
            if revised is not None:
                draft = revised
    except _TransportAbort as exc:
        aborted = str(exc)
    except _BudgetExhausted:
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
        {"schema": SCHEMA, "program_id": program_id, "capsule": draft,
         "validated": validated},
    )
    print(
        f"[learn] {program_id}: validated={validated} "
        f"round={validation_round} sends={len(events)} "
        f"aborted={aborted} budget_exhausted={budget_exhausted}",
        flush=True,
    )
    return outcome


def run_exec(workspace: Path, run_id: str, arm: str,
             api_key: str) -> dict[str, object]:
    """One execution arm: 16 tasks, one send each."""

    manifest = _load_manifest(workspace)
    ledger = Feedback2Ledger(workspace / "feedback2-ledger", run_id)
    plan_by_pid = {p["program_id"]: p for p in manifest["plan"]}
    max_tokens = INDUCTION_MAX_TOKENS if arm == "raw" else EXEC_MAX_TOKENS
    capsules: dict[str, str | None] = {}
    if arm == "learned":
        for program in all_programs_v2():
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
    for task in campaign_tasks_v2():
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
            completion = _dispatch(api_key, prompt, max_tokens)
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
        print(f"[{arm}] {pid}#{task['input_index']}: correct={correct}",
              flush=True)

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
        "max_tokens": max_tokens,
        "sends": sum(1 for row in rows if row["slot"] is not None),
        "itt_successes": taxonomy["correct"],
        "taxonomy": taxonomy, "rows": rows,
    }
    _write_json(workspace / f"summary-{arm}.json", summary)
    print(f"summary written: {workspace / f'summary-{arm}.json'}", flush=True)
    return summary


def run_report(workspace: Path) -> dict[str, object]:
    """Qualification-aware aggregation with the owner's decision table."""

    qual_path = workspace / "qualification.json"
    if not qual_path.exists():
        raise FileNotFoundError("campaign incomplete: qualification.json missing")
    qualification = json.loads(qual_path.read_text(encoding="utf-8"))

    if not qualification["qualified"]:
        report = {
            "schema": SCHEMA,
            "campaign": "g1-feedback-memory-v2-20261028",
            "qualification": {
                "qualified": False, "failure": qualification["failure"],
                "sends_used": qualification["sends_used"],
            },
            "verdict": "OPERATING POINT CLOSED: qualification failed at "
                       "300 s / 16384 - no full campaign was dispatched",
            "scientific_acceptance": False,
        }
        _write_json(workspace / "feedback2-report.json", report)
        print(json.dumps(report, indent=2, sort_keys=True), flush=True)
        return report

    learn_files = [f"learn-{p['program_id']}.json" for p in all_programs_v2()]
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
    if g1 and g2:
        verdict = (
            "GATE PASSED: acquisition -> storage -> fresh-session execution "
            "demonstrated AND stored capsule beats raw re-derivation - "
            "consider C3R-G2 transition per an independent protocol"
        )
    else:
        verdict = (
            "GATE FAILED: the current acquisition mechanism closes WITH a "
            "scientific result - no chained rescues"
        )

    report = {
        "schema": SCHEMA,
        "campaign": "g1-feedback-memory-v2-20261028",
        "qualification": {
            "qualified": True, "failure": None,
            "sends_used": qualification["sends_used"],
            "checks": qualification["checks"],
        },
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
        },
        "execution": {
            arm: {
                "itt_successes": execs[arm]["itt_successes"],
                "sends": execs[arm]["sends"],
                "max_tokens": execs[arm]["max_tokens"],
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
    _write_json(workspace / "feedback2-report.json", report)
    print(json.dumps(report, indent=2, sort_keys=True), flush=True)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="G1 feedback-acquired procedural memory v2 "
                    "(operational rehabilitation)"
    )
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--session", required=True,
                        choices=("manifest", "qualify", "learn", "exec",
                                 "report"))
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
    if args.session == "qualify":
        outcome = run_qualify(workspace, args.run_id, args.api_key)
        return 0 if outcome["qualified"] else 1
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
