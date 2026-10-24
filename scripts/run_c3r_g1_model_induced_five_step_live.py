"""Prospective G1 five-step MODEL-INDUCED agent policy across three processes.

A model sees two terminal input/output examples and independently infers a
five-bit procedure. The controller does NOT reconstruct, repair or grade-feed
the model's proposal. A private owner-only capsule persists its verbatim valid
proposal, which is applied to NEW inputs in two later Python interpreters.
Two controls use independently uniform random five-bit capsules. All missing
and invalid calls remain in the prescribed denominator; there are no retries.

Internal-first operational pilot, NOT scientific proof of learning or
multi-day retention. Default CLI makes zero provider calls.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import re
import statistics
import string
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from itertools import product
from pathlib import Path

from resonance_world.c3r_g1_model_boundary import ModelChoiceCompletion
from resonance_world.c3r_g1_zai_transport import PhysicalSendLedger, ZaiStandardModelPort

from run_c3r_g1_three_step_procedure_live import (
    SlotJournal,
    _digest,
    _read,
    _run_dir,
    _write_once,
)

MODEL = "glm-5.3"
EFFORT = "low"
SCHEMA = "c3r-g1-five-step-model-induced-memory-v0.1"
ARMS = ("learned", "fresh", "neutral")
FAMILIES = ("arithmetic", "text")
WAVES = ("retention1", "retention2")
CODES = tuple("".join(bits) for bits in product("AB", repeat=5))
SOURCE_SLOTS = 8
WAVE_SLOTS = 24
TOTAL_SLOTS = 56


def _execute(family: str, task: dict[str, object], code: str) -> str:
    if code not in CODES:
        raise ValueError("invalid five-step procedure")
    if family == "arithmetic":
        x, a, b, c = (int(task[key]) for key in ("value", "a", "b", "c"))
        x = x + a if code[0] == "A" else x - a
        x *= 2 if code[1] == "A" else 3
        x = x + b if code[2] == "A" else x - b
        x *= 5 if code[3] == "A" else 7
        x = x + c if code[4] == "A" else x - c
        return str(x)
    if family == "text":
        value = str(task["value"])
        value = ("q" if code[0] == "A" else "r") + value
        value += "3" if code[1] == "A" else "7"
        value = value.upper() if code[2] == "A" else value.lower()
        value = value[::-1] if code[3] == "A" else value
        return ("!" if code[4] == "A" else "?") + value
    raise ValueError("unknown procedure family")


def _task(rng: random.SystemRandom, family: str) -> dict[str, object]:
    if family == "text":
        return {"value": "".join(rng.choices(string.ascii_lowercase, k=6))}
    # Reject task operands that produce ambiguous output across 32 policies.
    for _ in range(500):
        candidate = {
            "value": rng.randrange(40, 400),
            "a": rng.randrange(65, 180),
            "b": rng.randrange(9, 40),
            "c": rng.randrange(1, 9),
        }
        if len({_execute(family, candidate, code) for code in CODES}) == 32:
            return candidate
    raise ValueError("unable to sample unambiguous five-step task")


def _manifest(run_id: str) -> dict[str, object]:
    rng = random.SystemRandom()
    units = []
    for family in FAMILIES:
        columns = []
        for _ in range(5):
            bits = list("AABB")
            rng.shuffle(bits)
            columns.append(bits)
        for pos in range(4):
            unit = {
                "unit_id": f"induce-{family[:3]}-{pos:02d}",
                "context_id": "ctx-" + os.urandom(12).hex(),
                "family": family,
                "private_program": "".join(col[pos] for col in columns),
                "control_fresh": rng.choice(CODES),
                "control_neutral": rng.choice(CODES),
                "source_tasks": [_task(rng, family) for _ in range(2)],
                "holdouts": {wave: _task(rng, family) for wave in WAVES},
            }
            units.append(unit)
    if len({u["context_id"] for u in units}) != 8:
        raise ValueError("duplicate private context ID")
    return {
        "schema": SCHEMA, "run_id": run_id, "model": MODEL,
        "effort_requested": EFFORT, "source_slots": SOURCE_SLOTS,
        "holdout_slots_per_wave": WAVE_SLOTS,
        "units": units, "scientific_acceptance": False,
    }


def _grammar(family: str) -> str:
    if family == "arithmetic":
        return (
            "Step1 A:add a B:subtract a; Step2 A:multiply 2 B:multiply 3; "
            "Step3 A:add b B:subtract b; Step4 A:multiply 5 B:multiply 7; "
            "Step5 A:add c B:subtract c."
        )
    return (
        "Step1 A:prefix lowercase q B:prefix lowercase r; "
        "Step2 A:append 3 B:append 7; Step3 A:uppercase B:lowercase; "
        "Step4 A:reverse all characters B:leave unchanged; "
        "Step5 A:prefix ! B:prefix ?."
    )


def _induce_prompt(unit: dict[str, object]) -> str:
    examples = [{
        "input": task,
        "correct_final_output": _execute(
            unit["family"], task, unit["private_program"]
        ),
    } for task in unit["source_tasks"]]
    return (
        "Infer an unknown FIXED five-step A/B procedure from two corrected "
        "terminal input/output examples. Each choice is A or B. "
        "Return exactly FIVE letters consisting only of A/B, for example "
        "ABBAA. Do not include an explanation or markdown. "
        "The evaluator will not tell you the hidden code or any per-step "
        "labels, and there is no extra source feedback after your inference.\n"
        f"Operations: {_grammar(unit['family'])}\n"
        f"Correct training examples: {json.dumps(examples, sort_keys=True)}\n"
        "Answer only the five-letter procedure."
    )


def _holdout_prompt(unit: dict[str, object], code: str, wave: str) -> str:
    if code not in CODES or wave not in WAVES:
        raise ValueError("invalid capsule or wave")
    return (
        "This is a new isolated agent session. Execute the five steps IN "
        "ORDER using the supplied five-letter procedure capsule. "
        "Do not infer a different policy or ask for earlier examples. "
        "Output ONLY the final value, without reasoning, markdown or labels.\n"
        f"Operations: {_grammar(unit['family'])}\n"
        f"Procedure capsule: {code}\n"
        f"New task: {json.dumps(unit['holdouts'][wave], sort_keys=True)}\n"
        "Answer with only the final result."
    )


def _call(index: int, prompt: str, port_factory, journal: SlotJournal,
          *, source: bool) -> dict[str, object]:
    journal.reserve(index, prompt)
    started = time.monotonic()
    try:
        result = port_factory().complete_prompt(prompt)
        if not isinstance(result, ModelChoiceCompletion) or result.model_id != MODEL:
            raise ValueError("invalid model result")
        answer = result.output.strip()
        regex = r"[AB]{5}" if source else r"(?:-?[0-9]{1,16}|[!?][A-Za-z0-9]{8})"
        valid = bool(result.finish_reason == "stop" and re.fullmatch(regex, answer))
        return {
            "status": "accepted" if valid else "invalid_format",
            "answer": answer if valid else None,
            "latency_ms": round((time.monotonic() - started) * 1000, 1),
            "prompt_tokens": result.prompt_tokens_reported,
            "completion_tokens": result.completion_tokens_reported,
            "reasoning_tokens": result.reasoning_tokens_reported,
            "finish_reason": result.finish_reason,
        }
    except Exception as exc:
        return {
            "status": "provider_error", "answer": None,
            "latency_ms": round((time.monotonic() - started) * 1000, 1),
            "prompt_tokens": None, "completion_tokens": None,
            "reasoning_tokens": None, "finish_reason": None,
            "failure_class": type(exc).__name__[:40],
        }


def _port_factory(key: str, timeout_seconds: float, max_tokens: int):
    def factory():
        return ZaiStandardModelPort(
            api_key=key, model_id=MODEL, ledger=PhysicalSendLedger(1),
            enabled=True, route="coding", reasoning_effort=EFFORT,
            timeout_seconds=timeout_seconds, max_tokens=max_tokens,
        )
    return factory


def run_source(workspace: Path, run_id: str, port_factory,
               workers: int = 3) -> dict[str, object]:
    if type(workers) is not int or not 1 <= workers <= 4:
        raise ValueError("workers outside 1..4")
    root = _run_dir(workspace, run_id)
    root.mkdir(mode=0o700, exist_ok=False)
    manifest = _manifest(run_id)
    _write_once(root, "manifest.json", manifest)
    journal = SlotJournal(root, run_id, max_slots=TOTAL_SLOTS)

    def learn(i: int, unit: dict[str, object]):
        response = _call(i, _induce_prompt(unit), port_factory, journal, source=True)
        return {
            "index": i, "unit_id": unit["unit_id"],
            "status": response["status"],
            "proposal": response["answer"],
            "policy_correct": (
                response["answer"] == unit["private_program"]
                if response["status"] == "accepted" else None
            ),
            "latency_ms": response["latency_ms"],
            "prompt_tokens": response["prompt_tokens"],
            "completion_tokens": response["completion_tokens"],
            "reasoning_tokens": response["reasoning_tokens"],
        }

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(learn, i, unit)
                   for i, unit in enumerate(manifest["units"])]
        rows = [future.result() for future in as_completed(futures)]
    rows.sort(key=lambda row: row["index"])
    if len(rows) != SOURCE_SLOTS or [x["index"] for x in rows] != list(range(8)):
        raise ValueError("incomplete induction denominator")
    capsule = {
        "schema": SCHEMA, "run_id": run_id, "manifest_sha256": _digest(manifest),
        "policies": [{
            "unit_id": row["unit_id"], "code": row["proposal"],
        } for row in rows],
        "scientific_acceptance": False,
    }
    _write_once(root, "capsules.json", capsule)
    source = {
        "schema": SCHEMA, "run_id": run_id,
        "manifest_sha256": _digest(manifest),
        "capsule_sha256": _digest(capsule),
        "rows": rows, "scientific_acceptance": False,
    }
    _write_once(root, "source.json", source)
    return {
        "schema": SCHEMA, "run_id": run_id, "phase": "source",
        "model": MODEL, "thinking_requested": "enabled",
        "reasoning_effort_requested": EFFORT,
        "source_prescribed": SOURCE_SLOTS,
        "physical_source_reservations": journal.count,
        "valid_policy_proposals": sum(r["status"] == "accepted" for r in rows),
        "policy_match_to_hidden_target": sum(
            r["policy_correct"] is True for r in rows
        ),
        "source_status_counts": dict(Counter(r["status"] for r in rows)),
        "policy_authored_by_model_not_controller": True,
        "individual_step_grades_given_to_model": False,
        "scientific_acceptance": False,
    }


def _read_source(root: Path, run_id: str, wave: str):
    if root.is_symlink() or root.stat().st_mode & 0o077:
        raise ValueError("run root not owner-private")
    manifest = _read(root, "manifest.json")
    capsule = _read(root, "capsules.json")
    source = _read(root, "source.json")
    if (
        any(x.get("schema") != SCHEMA or x.get("run_id") != run_id
            for x in (manifest, capsule, source))
        or capsule.get("manifest_sha256") != _digest(manifest)
        or source.get("manifest_sha256") != _digest(manifest)
        or source.get("capsule_sha256") != _digest(capsule)
        or len(manifest.get("units", [])) != 8
        or len(source.get("rows", [])) != 8
        or len(capsule.get("policies", [])) != 8
    ):
        raise ValueError("frozen source/experience integrity check failed")
    codes = {p["unit_id"]: p["code"] for p in capsule["policies"]}
    if len(codes) != 8 or set(codes) != {
        u["unit_id"] for u in manifest["units"]
    }:
        raise ValueError("duplicate or missing context memory")
    for unit in manifest["units"]:
        row = next((r for r in source["rows"]
                    if r["unit_id"] == unit["unit_id"]), None)
        if row is None or codes[unit["unit_id"]] != row["proposal"]:
            raise ValueError("persisted model policy differs from original proposal")
        if row["policy_correct"] is not (
            row["proposal"] == unit["private_program"]
            if row["status"] == "accepted" else None
        ):
            raise ValueError("tampered source/hidden-target correctness ledger")
    if wave == "retention2":
        previous = _read(root, "retention1-terminal.json")
        if (
            previous.get("run_id") != run_id
            or previous.get("source_sha256") != _digest(source)
            or previous.get("capsule_sha256") != _digest(capsule)
            or len(previous.get("rows", [])) != 24
        ):
            raise ValueError("previous retention wave not closed")
    return manifest, capsule, source, codes


def run_retention(workspace: Path, run_id: str, wave: str,
                  port_factory, workers: int = 3) -> dict[str, object]:
    if wave not in WAVES or type(workers) is not int or not 1 <= workers <= 4:
        raise ValueError("invalid retention phase or worker bound")
    root = _run_dir(workspace, run_id)
    manifest, capsule, source, codes = _read_source(root, run_id, wave)
    _write_once(root, f"{wave}-start.json", {
        "schema": SCHEMA, "run_id": run_id, "wave": wave,
        "source_sha256": _digest(source), "capsule_sha256": _digest(capsule),
        "exclusive_no_replay": True,
    })
    journal = SlotJournal(root, run_id, max_slots=TOTAL_SLOTS)
    start = SOURCE_SLOTS + WAVES.index(wave) * WAVE_SLOTS

    def evaluate(i: int, unit: dict[str, object], arm: str):
        index = start + i * 3 + ARMS.index(arm)
        learned = codes[unit["unit_id"]]
        if learned not in CODES:
            return {
                "index": index, "unit_id": unit["unit_id"],
                "family": unit["family"], "arm": arm,
                "status": "not_sent", "correct": None,
                "latency_ms": None, "prompt_tokens": None,
                "completion_tokens": None, "reasoning_tokens": None,
            }
        candidate = (
            learned if arm == "learned"
            else unit["control_fresh"] if arm == "fresh"
            else unit["control_neutral"]
        )
        response = _call(
            index, _holdout_prompt(unit, candidate, wave),
            port_factory, journal, source=False,
        )
        correct_target = _execute(
            unit["family"], unit["holdouts"][wave], unit["private_program"]
        )
        return {
            "index": index, "unit_id": unit["unit_id"],
            "family": unit["family"], "arm": arm,
            "status": response["status"],
            "correct": (
                response["answer"] == correct_target
                if response["status"] == "accepted" else None
            ),
            "latency_ms": response["latency_ms"],
            "prompt_tokens": response["prompt_tokens"],
            "completion_tokens": response["completion_tokens"],
            "reasoning_tokens": response["reasoning_tokens"],
        }

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(evaluate, i, unit, arm)
                   for i, unit in enumerate(manifest["units"])
                   for arm in ARMS]
        rows = [future.result() for future in as_completed(futures)]
    rows.sort(key=lambda r: r["index"])
    if len(rows) != WAVE_SLOTS or [
        row["index"] for row in rows
    ] != list(range(start, start + WAVE_SLOTS)):
        raise ValueError("incomplete retention logical denominator")
    _write_once(root, f"{wave}-terminal.json", {
        "schema": SCHEMA, "run_id": run_id, "wave": wave,
        "source_sha256": _digest(source),
        "capsule_sha256": _digest(capsule),
        "rows": rows, "scientific_acceptance": False,
    })
    arms = {}
    for arm in ARMS:
        subset = [row for row in rows if row["arm"] == arm]
        latency = [r["latency_ms"] for r in subset
                   if r["latency_ms"] is not None]
        arms[arm] = {
            "prescribed": 8,
            "accepted": sum(r["status"] == "accepted" for r in subset),
            "correct": sum(r["correct"] is True for r in subset),
            "completion_tokens_reported": sum(
                r["completion_tokens"] or 0 for r in subset
            ),
            "median_latency_ms": statistics.median(latency) if latency else None,
        }
    return {
        "schema": SCHEMA, "run_id": run_id, "phase": wave,
        "model": MODEL, "thinking_requested": "enabled",
        "reasoning_effort_requested": EFFORT,
        "separate_interpreter_required": True,
        "true_elapsed_time_delay_tested": False,
        "unchanged_model_authored_capsule": True,
        "source_examples_withheld_from_holdout": True,
        "controls_prior_match_probability": 1/32,
        "qualification_prescribed": 24,
        "physical_holdout_reservations": journal.count,
        "qualification_by_arm": arms,
        "status_counts": dict(Counter(r["status"] for r in rows)),
        "qualification_rows_redacted": rows,
        "scientific_acceptance": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Five-step model-authored policy G1 pilot")
    parser.add_argument("--phase", choices=("source", *WAVES), required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--workspace", type=Path)
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--timeout-seconds", type=float, default=120)
    parser.add_argument("--max-tokens", type=int, default=4096)
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args(argv)
    if not args.live:
        print(json.dumps({
            "status": "offline_zero_sends", "phase": args.phase,
            "scientific_acceptance": False,
        }))
        return 0
    if (
        args.workspace is None or not args.workspace.is_absolute()
        or not 1 <= args.workers <= 4
        or not 30 <= args.timeout_seconds <= 300
        or not 256 <= args.max_tokens <= 16384
    ):
        raise SystemExit("invalid live experiment parameters")
    api_key = os.environ.get("C3R_ZAI_API_KEY", "").strip()
    if not api_key:
        raise SystemExit("missing provider credential; no sends")
    factory = _port_factory(api_key, args.timeout_seconds, args.max_tokens)
    outcome = (
        run_source(args.workspace, args.run_id, factory, args.workers)
        if args.phase == "source"
        else run_retention(
            args.workspace, args.run_id, args.phase, factory, args.workers
        )
    )
    print(json.dumps(outcome, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
