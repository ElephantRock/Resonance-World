"""G1 novel grammar generalization: four-arm, three-session live dispatch.

Owner-mandated discriminating extension of the C3R-G1 track (2026-10-26,
preregistration G1_NOVEL_GRAMMAR_GENERALIZATION_PROSPECTIVE_20261026.md):
two NOVEL procedural grammar families, NEW holdout samples, four arms
(learned capsule / raw examples at execution / fresh capsule / neutral
capsule), three separate Python sessions (induction, wave1, wave2),
High/4096 fixed, no retries, every send in the denominator.

Default CLI makes zero provider calls. Linux/CI dispatch only (the
private-workspace validator is POSIX-specific by design).
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import os
import random
import re
import string
import threading
import time
from collections.abc import Callable
from pathlib import Path

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
SCHEMA = "c3r-g1-novel-grammar-generalization-v0.1"
FAMILIES = ("digits", "rotate")
UNITS_PER_FAMILY = 4
ARMS = ("learned", "raw", "fresh", "neutral")
WAVES = ("wave1", "wave2")
WAVE_SLOTS = 8  # one per unit
CAPSULE_FILE = "capsules.json"

_CODE_RE = re.compile(r"[AB]{5}")


# -- novel family 1: digits -------------------------------------------------


def _execute(family: str, task: dict[str, object], code: str) -> str:
    if not _CODE_RE.fullmatch(code):
        raise ValueError("invalid five-step procedure")
    if family == "digits":
        digits = list(str(task["value"]))
        if code[0] == "A":
            digits[1], digits[2] = digits[2], digits[1]
        digits = digits[:2] if code[1] == "A" else digits[-2:]
        digits = [str((int(d) + 1) % 10) if code[2] == "A" else str((int(d) + 9) % 10)
                  for d in digits]
        digits = sorted(digits, reverse=(code[3] == "A"))
        body = "".join(digits)
        return (str(len(body)) + body) if code[4] == "A" else (body + str(len(body)))
    if family == "rotate":
        value = str(task["value"])
        n = len(value)
        shift = 2 if code[0] == "A" else n - 2
        value = value[shift % n:] + value[: shift % n]
        if code[1] == "A":
            value = "-".join(value[i:i + 2] for i in range(0, len(value), 2))
        else:
            value = "_".join(
                value[i:i + 3] for i in range(0, len(value), 3)
            ) if len(value) > 3 else value
        value = value[:7] if code[2] == "A" else value[-7:]
        chars = list(value)
        if code[3] == "A":
            for i in range(0, len(chars) - 1, 2):
                chars[i], chars[i + 1] = chars[i + 1], chars[i]
            value = "".join(chars)
        return ("9" + value) if code[4] == "B" else (value + "9")
    raise ValueError("unknown novel procedure family")


def _task(rng: random.SystemRandom, family: str) -> dict[str, object]:
    if family == "rotate":
        for _ in range(500):
            value = "".join(rng.choices(string.ascii_lowercase, k=6))
            codes = ["".join(bits) for bits in itertools.product("AB", repeat=5)]
            outputs = {_execute(family, {"value": value}, code) for code in codes}
            if len(outputs) == 32:
                return {"value": value}
        raise ValueError("unable to sample unambiguous rotate task")
    for _ in range(500):
        value = "".join(rng.choices("0123456789", k=4))
        codes = ["".join(bits) for bits in itertools.product("AB", repeat=5)]
        outputs = {_execute(family, {"value": value}, code) for code in codes}
        if len(outputs) == 32:
            return {"value": value}
    raise ValueError("unable to sample unambiguous digits task")


def _grammar(family: str) -> str:
    if family == "digits":
        return (
            "The input is a 4-digit decimal string. "
            "Step1 A: swap the two middle digits B: leave unchanged; "
            "Step2 A: keep only the first two digits B: keep only the last two; "
            "Step3 A: replace each digit d with (d+1) mod 10 B: with (d+9) mod 10; "
            "Step4 A: arrange digits descending B: ascending; "
            "Step5 A: prefix the digit count B: append the digit count."
        )
    return (
        "The input is a 6-letter lowercase string. "
        "Step1 A: rotate left by 2 B: rotate right by 2; "
        "Step2 A: insert '-' after every second character B: insert '_' after "
        "every third character; Step3 A: keep the first 7 characters B: keep "
        "the last 7 characters; Step4 A: swap every adjacent character pair "
        "B: leave unchanged; Step5 A: append '9' B: prepend '5'."
    )


# -- manifest ----------------------------------------------------------------


def _manifest(run_id: str) -> dict[str, object]:
    rng = random.SystemRandom()
    units = []
    for family in FAMILIES:
        for pos in range(UNITS_PER_FAMILY):
            units.append({
                "unit_id": f"novel-{family}-{pos:02d}",
                "context_id": "ctx-" + os.urandom(12).hex(),
                "family": family,
                "private_program": "".join(rng.choice("AB") for _ in range(5)),
                "control_fresh": "".join(rng.choice("AB") for _ in range(5)),
                "control_neutral": "".join(rng.choice("AB") for _ in range(5)),
                "source_tasks": [_task(rng, family) for _ in range(2)],
                "holdouts": {wave: _task(rng, family) for wave in WAVES},
            })
    if len({u["context_id"] for u in units}) != len(units):
        raise ValueError("duplicate private context ID")
    return {
        "schema": SCHEMA,
        "run_id": run_id,
        "model": MODEL,
        "effort_requested": EFFORT,
        "max_tokens": MAX_TOKENS,
        "route": ROUTE,
        "families": list(FAMILIES),
        "units": units,
        "scientific_acceptance": False,
    }


# -- prompts -----------------------------------------------------------------


def _induce_prompt(unit: dict[str, object]) -> str:
    examples = [{
        "input": task,
        "correct_final_output": _execute(unit["family"], task, unit["private_program"]),
    } for task in unit["source_tasks"]]
    return (
        "Infer an unknown FIXED five-step A/B procedure from two corrected "
        "terminal input/output examples. Each choice is A or B. Return exactly "
        "FIVE letters consisting only of A/B, for example ABBAA. Do not include "
        "an explanation or markdown. The evaluator will not tell you the hidden "
        "code or any per-step labels, and there is no extra source feedback "
        f"after your inference.\nOperations: {_grammar(unit['family'])}\n"
        f"Correct training examples: {json.dumps(examples, sort_keys=True)}\n"
        "Answer only the five-letter procedure."
    )


def _exec_prompt(arm: str, unit: dict[str, object], capsule: str, wave: str) -> str:
    task = unit["holdouts"][wave]
    head = "This is a new isolated agent session. "
    tail = (
        f"\nOperations: {_grammar(unit['family'])}\n"
        f"New task: {json.dumps(task, sort_keys=True)}\n"
        "Answer with only the final result."
    )
    if arm == "learned":
        return (
            f"{head}Execute the five steps IN ORDER using the supplied "
            "five-letter procedure capsule. Do not infer a different policy. "
            f"\nProcedure capsule: {capsule}{tail}"
        )
    if arm == "raw":
        examples = [{
            "input": task_src,
            "correct_final_output": _execute(unit["family"], task_src, unit["private_program"]),
        } for task_src in unit["source_tasks"]]
        return (
            f"{head}A known five-step A/B procedure transforms inputs to "
            "outputs as shown by the corrected examples below. Derive the "
            "procedure yourself, then apply it to the new task. Do not ask "
            "for more information. There is no procedure capsule in this "
            f"session.\nOperations: {_grammar(unit['family'])}\n"
            f"Corrected training examples: {json.dumps(examples, sort_keys=True)}{tail}"
        )
    return (
        f"{head}Execute the five steps IN ORDER using the supplied five-letter "
        "procedure capsule. Do not infer a different policy. "
        f"\nProcedure capsule: {capsule}{tail}"
    )


def _holdout_correct(family: str, unit: dict[str, object], wave: str, answer: str) -> bool:
    truth = _execute(family, unit["holdouts"][wave], unit["private_program"])
    return answer == truth


# -- slots and dispatch --------------------------------------------------------


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
            raise ValueError("invalid physical attempt index")
        with self._lock:
            _write_once(self.root, f"send-{self.session}-{index:02d}.json", {
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
          guard: _SlotGuard, *, kind: str) -> dict[str, object]:
    guard.reserve(index, prompt)
    started = time.monotonic()
    try:
        result = port_factory().complete_prompt(prompt)
        if not isinstance(result, ModelChoiceCompletion) or result.model_id != MODEL:
            raise ValueError("invalid model result")
        answer = result.output.strip()
        if kind == "source":
            valid = result.finish_reason == "stop" and bool(_CODE_RE.fullmatch(answer))
        else:
            valid = result.finish_reason == "stop" and bool(answer)
        return {
            "status": "accepted" if valid else "invalid_format",
            "answer": answer,
            "latency_ms": round((time.monotonic() - started) * 1000, 1),
            "prompt_tokens": result.prompt_tokens_reported,
            "completion_tokens": result.completion_tokens_reported,
            "reasoning_tokens": result.reasoning_tokens_reported,
            "finish_reason": result.finish_reason,
        }
    except Exception as exc:
        return {
            "status": "provider_error",
            "answer": None,
            "latency_ms": round((time.monotonic() - started) * 1000, 1),
            "prompt_tokens": None,
            "completion_tokens": None,
            "reasoning_tokens": None,
            "finish_reason": None,
            "failure_class": type(exc).__name__[:40],
        }


def _port_factory(key: str):
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


# -- sessions ------------------------------------------------------------------


def run_induction(
    workspace: Path, run_id: str, api_key: str, workers: int = 2
) -> dict[str, object]:
    root = _run_dir(workspace, run_id)
    root.mkdir(mode=0o700, exist_ok=False)
    manifest = _manifest(run_id)
    _write_once(root, "manifest.json", manifest)
    guard = _SlotGuard(root, run_id, "induction", len(manifest["units"]))

    def induce(index: int, unit: dict[str, object]):
        response = _call(
            index, _induce_prompt(unit), _port_factory(api_key), guard, kind="source"
        )
        return {
            "index": index,
            "unit_id": unit["unit_id"],
            "family": unit["family"],
            "status": response["status"],
            "proposal": response["answer"] if response["status"] == "accepted" else None,
            "policy_correct": (
                response["answer"] == unit["private_program"]
                if response["status"] == "accepted" else None
            ),
            "latency_ms": response["latency_ms"],
            "failure_class": response.get("failure_class"),
        }

    from concurrent.futures import ThreadPoolExecutor, as_completed

    rows = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(induce, i, unit) for i, unit in enumerate(manifest["units"])]
        for future in as_completed(futures):
            rows.append(future.result())
    rows.sort(key=lambda row: row["index"])
    capsules = {
        row["unit_id"]: {"capsule": row["proposal"], "status": row["status"]}
        for row in rows
    }
    _write_once(root, CAPSULE_FILE, {"units": capsules})
    summary = {
        "session": "induction",
        "sends": guard.count,
        "accepted": sum(1 for row in rows if row["status"] == "accepted"),
        "source_correct": sum(1 for row in rows if row["policy_correct"] is True),
        "rows": rows,
    }
    _write_once(root, "induction-summary.json", summary)
    return summary


def run_wave(
    workspace: Path, run_id: str, arm: str, wave: str, api_key: str, workers: int = 2
) -> dict[str, object]:
    if arm not in ARMS:
        raise ValueError(f"unknown arm {arm!r}")
    if wave not in WAVES:
        raise ValueError(f"unknown wave {wave!r}")
    root = _run_dir(workspace, run_id)
    # The wave sessions MUST evaluate the SAME private programs and holdout
    # tasks the induction session registered: read the write-once manifest,
    # never regenerate it.
    manifest = _read(root, "manifest.json")
    capsules = _read(root, CAPSULE_FILE)["units"]
    guard = _SlotGuard(root, run_id, f"{wave}-{arm}", len(manifest["units"]))

    def execute(index: int, unit: dict[str, object]):
        capsule = unit["control_fresh"] if arm == "fresh" else (
            unit["control_neutral"] if arm == "neutral" else
            capsules[unit["unit_id"]]["capsule"]
        )
        if arm == "learned" and capsule is None:
            return {
                "index": index, "unit_id": unit["unit_id"], "status": "no_capsule",
                "answer": None, "correct": None, "latency_ms": None,
                "failure_class": None,
            }
        prompt = _exec_prompt(arm, unit, capsule or "", wave)
        response = _call(index, prompt, _port_factory(api_key), guard, kind="value")
        correct = (
            _holdout_correct(unit["family"], unit, wave, response["answer"])
            if response["status"] == "accepted" else None
        )
        return {
            "index": index,
            "unit_id": unit["unit_id"],
            "status": response["status"],
            "answer": response["answer"] if response["status"] == "accepted" else None,
            "correct": correct,
            "latency_ms": response["latency_ms"],
            "failure_class": response.get("failure_class"),
        }

    from concurrent.futures import ThreadPoolExecutor, as_completed

    rows = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(execute, i, unit) for i, unit in enumerate(manifest["units"])]
        for future in as_completed(futures):
            rows.append(future.result())
    rows.sort(key=lambda row: row["index"])
    analyzed = [row for row in rows if row["correct"] is not None]
    summary = {
        "session": f"{wave}-{arm}",
        "sends": guard.count,
        "correct": sum(1 for row in analyzed if row["correct"] is True),
        "wrong": sum(1 for row in analyzed if row["correct"] is False),
        "no_capsule": sum(1 for row in rows if row["status"] == "no_capsule"),
        "provider_error": sum(1 for row in rows if row["status"] == "provider_error"),
        "rows": rows,
    }
    _write_once(root, f"{wave}-{arm}-summary.json", summary)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="G1 novel grammar generalization")
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--session", required=True,
                        choices=("induce", "wave1", "wave2"))
    parser.add_argument("--arm", choices=ARMS)
    parser.add_argument("--api-key", default=os.environ.get("C3R_ZAI_API_KEY", ""))
    parser.add_argument("--workers", type=int, default=2)
    args = parser.parse_args()
    if not args.api_key:
        parser.error("C3R_ZAI_API_KEY (or --api-key) is required")
    if args.session == "induce":
        summary = run_induction(args.workspace, args.run_id, args.api_key, args.workers)
    else:
        if args.arm is None:
            parser.error("wave sessions require --arm")
        wave = "wave1" if args.session == "wave1" else "wave2"
        summary = run_wave(
            args.workspace, args.run_id, args.arm, wave, args.api_key, args.workers
        )
    print(json.dumps({k: v for k, v in summary.items() if k != "rows"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
