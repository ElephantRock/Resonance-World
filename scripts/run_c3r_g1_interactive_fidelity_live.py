"""G1 interactive acquisition & execution fidelity: four-comparison live dispatch.

Preregistration:
research/c3r_g2/G1_INTERACTIVE_ACQUISITION_EXECUTION_FIDELITY_PROSPECTIVE_
20261026.md (frozen 2026-10-26, cap 64 sends, ITT accounting).

Sessions (separate processes, per the frozen budget):
- c1:              8 sends  - blind two-shot induction per unit (baseline).
- c2 --group 0..3: <=6 each - bounded interactive-feedback induction for a
                              pair of units (<=3 proposal rounds per unit;
                              per-example pass/fail feedback only).
- c3 --wave W:     8 sends  - execute the EVALUATOR-SUPPLIED correct capsule
                              (execution fidelity alone).
- c4 --wave W:     8 sends  - re-induce from raw examples at execution time.

C3 minus C4 is NOT a measure of acquired-memory value (the owner's
predeclared caveat). The two predeclared G2 gates: C2 final-capsule
correctness >= 6/8 AND C3 execution fidelity >= 15/16.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import threading
import time
from collections.abc import Callable
from pathlib import Path

from c3r_g1_interactive_fidelity_families import (
    FAMILIES,
    _execute,
    _grammar,
    _is_code,
    _task,
)
from run_c3r_g1_three_step_procedure_live import (
    _read,
    _run_dir,
    _write_once,
)

from resonance_world.c3r_g1_model_boundary import ModelChoiceCompletion
from resonance_world.c3r_g1_zai_transport import PhysicalSendLedger, ZaiStandardModelPort

MODEL = "glm-5.3"
EFFORT = "high"
MAX_TOKENS = 4096
ROUTE = "coding"
SCHEMA = "c3r-g1-interactive-fidelity-v0.1"
C2_MAX_ROUNDS = 3
UNITS_PER_GROUP = 2
C2_GROUPS = 4


class BudgetExhausted(RuntimeError):
    """The session's physical send budget is exhausted."""


class _SlotGuard:
    """Write-once slot journal over the private run directory."""

    def __init__(self, root: Path, run_id: str, session: str, max_slots: int) -> None:
        self.root = root
        self.run_id = run_id
        self.session = session
        self.max_slots = max_slots
        self._lock = threading.Lock()
        self._indices: set[int] = set()

    def reserve(self, index: int, prompt: str) -> None:
        if type(index) is not int or not 0 <= index < self.max_slots:
            raise BudgetExhausted("session send budget exhausted")
        with self._lock:
            _write_once(self.root, f"send-{self.session}-{index:03d}.json", {
                "run_id": self.run_id,
                "session": self.session,
                "index": index,
                "model": MODEL,
                "reasoning_effort": EFFORT,
                "max_tokens": MAX_TOKENS,
                "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
                "reserved_no_retry": True,
            })
            self._indices.add(index)

    @property
    def count(self) -> int:
        return len(self._indices)


def _call(index: int, prompt: str, port_factory: Callable[[], ZaiStandardModelPort],
          guard: _SlotGuard) -> dict[str, object]:
    guard.reserve(index, prompt)
    started = time.monotonic()
    try:
        result = port_factory().complete_prompt(prompt)
        if not isinstance(result, ModelChoiceCompletion) or result.model_id != MODEL:
            raise ValueError("invalid model result")
        answer = result.output.strip()
        valid = result.finish_reason == "stop" and bool(answer)
        return {
            "status": "accepted" if valid else "invalid_format",
            "answer": answer,
            "latency_ms": round((time.monotonic() - started) * 1000, 1),
            "finish_reason": result.finish_reason,
        }
    except Exception as exc:
        return {
            "status": "provider_error",
            "answer": None,
            "latency_ms": round((time.monotonic() - started) * 1000, 1),
            "finish_reason": None,
            "failure_class": type(exc).__name__[:40],
        }


def _port_factory(key: str) -> Callable[[], ZaiStandardModelPort]:
    def factory():
        return ZaiStandardModelPort(
            api_key=key,
            model_id=MODEL,
            ledger=PhysicalSendLedger(1),
            enabled=True,
            route=ROUTE,
            reasoning_effort=EFFORT,
            max_tokens=MAX_TOKENS,
        )
    return factory


def _source_examples(unit: dict[str, object]) -> list[dict[str, object]]:
    return [{
        "input": task,
        "correct_final_output": _execute(unit["family"], task, unit["private_program"]),
    } for task in unit["source_tasks"]]


def _induce_prompt(unit: dict[str, object]) -> str:
    examples = _source_examples(unit)
    return (
        "Infer an unknown FIXED five-step A/B procedure from two corrected "
        "terminal input/output examples. Each choice is A or B. Return exactly "
        "FIVE letters consisting only of A/B, for example ABBAA. Do not include "
        "an explanation or markdown.\n"
        f"Operations: {_grammar(unit['family'])}\n"
        f"Correct training examples: {json.dumps(examples, sort_keys=True)}\n"
        "Answer only the five-letter procedure."
    )


def _revise_prompt(unit: dict[str, object], proposal: str,
                   outcomes: list[dict[str, object]]) -> str:
    report = json.dumps(outcomes, sort_keys=True)
    return (
        "Your previously proposed five-step A/B procedure did NOT reproduce "
        "the corrected training examples. Per-example feedback on YOUR "
        f"proposal {proposal}:\n{report}\n"
        "At least one of the five steps is wrong. Propose a CORRECTED "
        "five-letter procedure. Answer only the five letters, no explanation."
    )


def _execute_prompt(unit: dict[str, object], capsule: str, wave: str) -> str:
    return (
        "This is a new isolated agent session. Execute the five steps IN "
        "ORDER using the supplied five-letter procedure capsule. Do not "
        "infer a different policy or ask for earlier examples. Output ONLY "
        "the final value, without reasoning, markdown or labels.\n"
        f"Operations: {_grammar(unit['family'])}\n"
        f"Procedure capsule: {capsule}\n"
        f"New task: {json.dumps(unit['holdouts'][wave], sort_keys=True)}\n"
        "Answer with only the final result."
    )


def _raw_prompt(unit: dict[str, object], wave: str) -> str:
    examples = _source_examples(unit)
    return (
        "This is a new isolated agent session. A known five-step A/B "
        "procedure transforms inputs to outputs as shown by the corrected "
        "examples below. Derive the procedure yourself, then apply it to the "
        "new task. Do not ask for more information.\n"
        f"Operations: {_grammar(unit['family'])}\n"
        f"Corrected training examples: {json.dumps(examples, sort_keys=True)}\n"
        f"New task: {json.dumps(unit['holdouts'][wave], sort_keys=True)}\n"
        "Answer with only the final result."
    )


def _manifest(run_id: str, feedback_rounds: int) -> dict[str, object]:
    """Owner-only manifest: private programs, source tasks, fresh holdouts.

    Written ONCE by the c1 session; every later session reads this exact
    file so all sessions evaluate identical programs and tasks.
    """

    rng = random.SystemRandom()
    units: list[dict[str, object]] = []
    for family in FAMILIES:
        for position in range(4):
            units.append({
                "unit_id": f"fidelity-{family}-{position:02d}",
                "context_id": "ctx-" + os.urandom(12).hex(),
                "family": family,
                "group": len(units) // UNITS_PER_GROUP,
                "private_program": "".join(rng.choice("AB") for _ in range(5)),
                "source_tasks": [_task(rng, family) for _ in range(2)],
                "holdouts": {
                    wave: _task(rng, family) for wave in ("wave1", "wave2")
                },
            })
    if len({str(unit["context_id"]) for unit in units}) != len(units):
        raise ValueError("duplicate private context ID")
    return {
        "schema": SCHEMA,
        "run_id": run_id,
        "model": MODEL,
        "effort_requested": EFFORT,
        "max_tokens": MAX_TOKENS,
        "route": ROUTE,
        "feedback_rounds": feedback_rounds,
        "units": units,
        "scientific_acceptance": False,
    }


def run_c1(workspace: Path, run_id: str, api_key: str, workers: int,
           feedback_rounds: int,
           port_factory: Callable[[], ZaiStandardModelPort] | None = None,
) -> dict[str, object]:
    root = _run_dir(workspace, run_id)
    root.mkdir(mode=0o700, exist_ok=False)
    manifest = _manifest(run_id, feedback_rounds)
    _write_once(root, "manifest.json", manifest)
    guard = _SlotGuard(root, run_id, "c1", len(manifest["units"]))
    rows = []

    def one(index: int, unit: dict[str, object]):
        factory = port_factory or _port_factory(api_key)
        response = _call(index, _induce_prompt(unit), factory, guard)
        capsule = response["answer"] if response["status"] == "accepted" else None
        return {
            "index": index,
            "unit_id": unit["unit_id"],
            "family": unit["family"],
            "comparison": "C1",
            "status": response["status"],
            "capsule": capsule,
            "policy_correct": (capsule == unit["private_program"]) if capsule else None,
            "latency_ms": response["latency_ms"],
            "failure_class": response.get("failure_class"),
        }

    from concurrent.futures import ThreadPoolExecutor, as_completed

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(one, i, unit) for i, unit in enumerate(manifest["units"])]
        for future in as_completed(futures):
            rows.append(future.result())
    rows.sort(key=lambda row: row["index"])
    summary = {
        "session": "c1-static-induction",
        "sends": guard.count,
        "accepted": sum(1 for row in rows if row["status"] == "accepted"),
        "source_correct": sum(1 for row in rows if row["policy_correct"] is True),
        "rows": rows,
    }
    _write_once(root, "c1-summary.json", summary)
    return summary


def run_c2_group(workspace: Path, run_id: str, group: int, api_key: str,
                 workers: int, feedback_rounds: int,
                 port_factory: Callable[[], ZaiStandardModelPort] | None = None,
) -> dict[str, object]:
    root = _run_dir(workspace, run_id)
    manifest = _read(root, "manifest.json")
    units = manifest["units"][group * UNITS_PER_GROUP:(group + 1) * UNITS_PER_GROUP]
    max_sends = len(units) * feedback_rounds
    guard = _SlotGuard(root, run_id, f"c2-g{group}", max_sends)

    def acquire(position: int, unit: dict[str, object]) -> dict[str, object]:
        history: list[dict[str, object]] = []
        prompt = _induce_prompt(unit)
        capsule = None
        for round_index in range(1, feedback_rounds + 1):
            slot_index = position * feedback_rounds + round_index - 1
            response = _call(slot_index, prompt, (port_factory or _port_factory(api_key)), guard)
            proposal = None
            if response["status"] == "accepted" and _is_code(response["answer"]):
                proposal = response["answer"]
            outcomes = []
            if proposal is not None:
                capsule = proposal
                for task in unit["source_tasks"]:
                    produced = _execute(unit["family"], task, proposal)
                    truth = _execute(unit["family"], task, unit["private_program"])
                    outcomes.append({
                        "task_input": task,
                        "produced": produced,
                        "correct": produced == truth,
                    })
            history.append({
                "round": round_index,
                "prompt_kind": "initial" if round_index == 1 else "revision",
                "proposal": proposal,
                "outcomes": outcomes,
            })
            if all(item["correct"] for item in outcomes):
                break
            prompt = _revise_prompt(unit, proposal or "(invalid answer)", outcomes)
        final_correct = capsule == unit["private_program"] if capsule else None
        return {
            "unit_id": unit["unit_id"],
            "family": unit["family"],
            "comparison": "C2",
            "capsule": capsule,
            "final_correct": final_correct,
            "rounds_used": len(history),
            "history": history,
        }

    from concurrent.futures import ThreadPoolExecutor, as_completed

    rows = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [
            pool.submit(acquire, position, unit)
            for position, unit in enumerate(units)
        ]
        for future in as_completed(futures):
            rows.append(future.result())
    rows.sort(key=lambda row: row["unit_id"])
    summary = {
        "session": f"c2-interactive-group{group}",
        "sends": guard.count,
        "final_correct": sum(1 for row in rows if row["final_correct"] is True),
        "rows": rows,
    }
    _write_once(root, f"c2-summary-group{group}.json", summary)
    return summary


def run_execute(
    workspace: Path, run_id: str, comparison: str, wave: str,
    api_key: str, workers: int,
    port_factory: Callable[[], ZaiStandardModelPort] | None = None,
) -> dict[str, object]:
    root = _run_dir(workspace, run_id)
    manifest = _read(root, "manifest.json")
    guard = _SlotGuard(root, run_id, f"{comparison}-{wave}", len(manifest["units"]))
    rows = []

    def one(index: int, unit: dict[str, object]):
        capsule = (
            unit["private_program"] if comparison == "C3" else None
        )
        prompt = (
            _execute_prompt(unit, capsule, wave)
            if comparison == "C3"
            else _raw_prompt(unit, wave)
        )
        response = _call(index, prompt, (port_factory or _port_factory(api_key)), guard)
        answer = response["answer"] if response["status"] == "accepted" else None
        truth = _execute(unit["family"], unit["holdouts"][wave], unit["private_program"])
        correct = (answer == truth) if answer is not None else None
        return {
            "index": index,
            "unit_id": unit["unit_id"],
            "family": unit["family"],
            "comparison": comparison,
            "wave": wave,
            "status": response["status"],
            "answer": answer,
            "truth": truth,
            "correct": correct,
            "latency_ms": response["latency_ms"],
            "failure_class": response.get("failure_class"),
        }

    from concurrent.futures import ThreadPoolExecutor, as_completed

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(one, i, unit) for i, unit in enumerate(manifest["units"])]
        for future in as_completed(futures):
            rows.append(future.result())
    rows.sort(key=lambda row: row["index"])
    scored = [row for row in rows if row["correct"] is not None]
    summary = {
        "session": f"{comparison}-{wave}",
        "comparison": comparison,
        "wave": wave,
        "sends": guard.count,
        "evaluated": len(scored),
        "correct": sum(1 for row in scored if row["correct"] is True),
        "unscored": len(rows) - len(scored),
        "rows": rows,
    }
    _write_once(root, f"{comparison}-{wave}-summary.json", summary)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="G1 interactive fidelity dispatch")
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--session", required=True,
                        choices=("c1", "c2", "c3", "c4"))
    parser.add_argument("--group", type=int, default=0)
    parser.add_argument("--wave", default="wave1", choices=("wave1", "wave2"))
    parser.add_argument("--feedback-rounds", type=int, default=3)
    parser.add_argument("--api-key", default=os.environ.get("C3R_ZAI_API_KEY", ""))
    parser.add_argument("--workers", type=int, default=2)
    args = parser.parse_args()
    if not args.api_key:
        parser.error("C3R_ZAI_API_KEY (or --api-key) is required")
    if args.session == "c1":
        summary = run_c1(
            args.workspace, args.run_id, args.api_key, args.workers,
            args.feedback_rounds,
        )
    elif args.session == "c2":
        if not 0 <= args.group < C2_GROUPS:
            parser.error("--group outside the preregistered range")
        summary = run_c2_group(
            args.workspace, args.run_id, args.group, args.api_key,
            args.workers, args.feedback_rounds,
        )
    else:
        summary = run_execute(
            args.workspace, args.run_id, args.session.upper(), args.wave,
            args.api_key, args.workers,
        )
    print(json.dumps({k: v for k, v in summary.items() if k != "rows"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
