"""G1 three-step real-model agent procedural memory transfer across processes.

The source model supplies blind A/B probe actions. An explicit, deterministic
agent-side reducer learns three binary procedure steps from the returned grade
bits. A second Python process loads an fsynced private 3-bit capsule and asks
GLM-5.3 to execute the procedure on a NEW operand, versus capacity-matched
untrained/random and unrelated-experience (shuffled) capsule controls.

No model weight learning, no external auditor, no retries, no science approval.
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
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from resonance_world.c3r_g1_model_boundary import ModelChoiceCompletion
from resonance_world.c3r_g1_zai_transport import PhysicalSendLedger, ZaiStandardModelPort

MODEL = "glm-5.3"
EFFORT = "low"
FAMILIES = ("arithmetic", "text")
ARMS = ("learned", "fresh", "neutral")
CODES = tuple(a + b + c for a in "AB" for b in "AB" for c in "AB")
SCHEMA = "c3r-g1-three-step-agent-memory-v0.1"
LIMIT = 256_000


def _digest(value: object) -> str:
    return hashlib.sha256(json.dumps(
        value, separators=(",", ":"), sort_keys=True,
    ).encode()).hexdigest()


def _run_dir(workspace: Path, run_id: str) -> Path:
    if (not isinstance(run_id, str)
            or re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.-]{7,63}", run_id) is None):
        raise ValueError("invalid experimental run identity")
    if (not workspace.is_absolute() or workspace.is_symlink()
            or workspace.stat().st_uid != os.geteuid()
            or workspace.stat().st_mode & 0o077):
        raise ValueError("private owner-only workspace required")
    return workspace / ("g1-procedure-" + hashlib.sha256(run_id.encode()).hexdigest())


def _write_once(root: Path, name: str, record: object) -> None:
    data = json.dumps(record, sort_keys=True, separators=(",", ":")).encode() + b"\n"
    if len(data) > LIMIT:
        raise ValueError("oversized private event")
    fd = os.open(root / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as out:
        out.write(data)
        out.flush()
        os.fsync(out.fileno())
    fd = os.open(root, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _read(root: Path, name: str) -> dict[str, object]:
    path = root / name
    if path.is_symlink() or path.stat().st_size > LIMIT:
        raise ValueError("private artifact redirected or oversized")
    record = json.loads(path.read_text(encoding="utf-8"))
    if type(record) is not dict:
        raise ValueError("malformed private record")
    return record


def _execute(family: str, payload: dict[str, object], program: str) -> str:
    if program not in CODES:
        raise ValueError("invalid three-step program")
    if family == "arithmetic":
        x = int(payload["value"])
        k1, k2, k3 = int(payload["k1"]), int(payload["k2"]), int(payload["k3"])
        x = x + k1 if program[0] == "A" else x - k1
        x *= k2 if program[1] == "A" else k2 + 1
        x = x + k3 if program[2] == "A" else x - k3
        return str(x)
    if family == "text":
        value = str(payload["value"])
        value = ("a" if program[0] == "A" else "b") + value
        value = value.upper() if program[1] == "A" else value.lower()
        return value + ("7" if program[2] == "A" else "9")
    raise ValueError("unsupported task family")


def _task(rng: random.SystemRandom, family: str) -> dict[str, object]:
    if family == "text":
        return {"value": "".join(rng.choices(string.ascii_lowercase, k=6))}
    for _ in range(1024):
        candidate = {
            "value": rng.randrange(30, 400), "k1": rng.randrange(2, 20),
            "k2": rng.randrange(2, 7), "k3": rng.randrange(2, 20),
        }
        if len({_execute(family, candidate, c) for c in CODES}) == 8:
            return candidate
    raise ValueError("could not generate unambiguous arithmetic task")


def _manifest(run_id: str) -> dict[str, object]:
    rng = random.SystemRandom()
    units = []
    for family in FAMILIES:
        # Balance each hidden instruction step within each 4-context family.
        steps = []
        for _ in range(3):
            choices = list("AABB")
            rng.shuffle(choices)
            steps.append(choices)
        for i in range(4):
            unit_id = f"proc-{family[:3]}-{i:02d}"
            private_program = "".join(part[i] for part in steps)
            units.append({
                "unit_id": unit_id, "family": family,
                "context_id": "ctx-" + os.urandom(12).hex(),
                "private_program": private_program,
                "fresh_random_program": rng.choice(CODES),
                "source_task_ids": [
                    "dev-" + os.urandom(8).hex() for _ in range(3)
                ],
                "holdout_task_id": "hold-" + os.urandom(8).hex(),
                "holdout_payload": _task(rng, family),
            })
    if (len({u["context_id"] for u in units}) != 8
            or len({u["holdout_task_id"] for u in units}) != 8):
        raise ValueError("duplicate private task identity")
    return {
        "schema": SCHEMA, "run_id": run_id,
        "source_slots": 24, "holdout_slots": 24,
        "model": MODEL, "reasoning_effort": EFFORT,
        "units": units, "scientific_acceptance": False,
    }


def _source_prompt(unit: dict[str, object], step: int) -> str:
    variants = (
        ("A: add k1, B: subtract k1", "A: prefix a, B: prefix b"),
        ("A: multiply by k2, B: multiply by k2+1", "A: uppercase, B: lowercase"),
        ("A: add k3, B: subtract k3", "A: append 7, B: append 9"),
    )
    return (
        "Internal agent development action. This context has an unobservable "
        "three-step procedure. At this stage you cannot infer the private "
        "correct step from the public ID; choose A as a deterministic trial "
        "and reply with exactly A or B, no reasoning or explanation. "
        "The local agent will receive correctness feedback AFTER this action. "
        f"Context: {unit['context_id']}. "
        f"Step {step + 1} of 3. "
        f"Two alternatives: {variants[step][0 if unit['family'] == 'arithmetic' else 1]}. "
        "Reply exactly A or B."
    )


def _holdout_prompt(unit: dict[str, object], policy: str) -> str:
    if policy not in CODES:
        raise ValueError("holdout requires a full equal-capacity 3-bit capsule")
    arithmetic = (
        "Step1 A: x += k1; B: x -= k1. "
        "Step2 A: x *= k2; B: x *= (k2+1). "
        "Step3 A: x += k3; B: x -= k3."
    )
    texts = (
        "Step1 A: prefix lowercase a; B: prefix lowercase b. "
        "Step2 A: uppercase all characters; B: lowercase all characters. "
        "Step3 A: append character 7; B: append character 9."
    )
    return (
        "You are in a NEW isolated agent session. "
        "Execute all THREE steps in order using the exact choices in the "
        "three-character procedure capsule. The capsule is the only policy "
        "available in this session; no historical grades or source transcript "
        "are available. Output ONLY the final result, without quotation marks, "
        "labels, reasoning or markdown.\n"
        f"Procedure capsule: {policy}\n"
        f"Program: {arithmetic if unit['family'] == 'arithmetic' else texts}\n"
        f"Public input: {json.dumps(unit['holdout_payload'], sort_keys=True)}\n"
        "Output only the final result."
    )


class SlotJournal:
    def __init__(self, root: Path, run_id: str, max_slots: int = 48):
        if type(max_slots) is not int or not 1 <= max_slots <= 256:
            raise ValueError("invalid prescribed slot count")
        self.root = root
        self.run_id = run_id
        self.max_slots = max_slots
        self._lock = threading.Lock()
        self._indices: set[int] = set()

    def reserve(self, index: int, prompt: str) -> None:
        if type(index) is not int or not 0 <= index < self.max_slots:
            raise ValueError("invalid physical attempt index")
        with self._lock:
            _write_once(self.root, f"send-{index:02d}.json", {
                "run_id": self.run_id, "index": index,
                "model": MODEL, "reasoning_effort": EFFORT,
                "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
                "reserved_no_retry": True,
            })
            self._indices.add(index)

    @property
    def count(self) -> int:
        return len(self._indices)


def _send(index: int, prompt: str, factory, journal: SlotJournal,
          *, mode: str) -> dict[str, object]:
    journal.reserve(index, prompt)
    start = time.monotonic()
    try:
        result = factory().complete_prompt(prompt)
        if not isinstance(result, ModelChoiceCompletion) or result.model_id != MODEL:
            raise ValueError("unexpected provider adapter return")
        answer = result.output.strip()
        accepted = (
            result.finish_reason == "stop"
            and (answer in ("A", "B") if mode == "source" else bool(
                re.fullmatch(r"(?:-?[0-9]{1,12}|[A-Za-z]{7}[79])", answer)
            ))
        )
        return {
            "status": "accepted" if accepted else "invalid_format",
            "answer": answer if accepted else None,
            "finish_reason": result.finish_reason,
            "latency_ms": round(1000 * (time.monotonic() - start), 1),
            "prompt_tokens": result.prompt_tokens_reported,
            "completion_tokens": result.completion_tokens_reported,
            "reasoning_tokens": result.reasoning_tokens_reported,
            "provider_failure_class": None,
        }
    except Exception as exc:
        return {
            "status": "provider_error", "answer": None, "finish_reason": None,
            "latency_ms": round(1000 * (time.monotonic() - start), 1),
            "prompt_tokens": None, "completion_tokens": None,
            "reasoning_tokens": None,
            "provider_failure_class": (
                type(exc).__name__ if type(exc).__name__ in (
                    "TimeoutError", "HTTPError", "URLError",
                    "RuntimeError", "ValueError", "OSError",
                ) else "OtherTransportError"
            ),
        }


def _infer(rows: list[dict[str, object]]) -> str | None:
    if len(rows) != 3 or {row["step"] for row in rows} != {0, 1, 2}:
        return None
    if any(row["status"] != "accepted" or row["choice"] not in ("A", "B")
           or type(row["correct"]) is not bool for row in rows):
        return None
    bits = [None, None, None]
    for row in rows:
        bit = row["choice"] if row["correct"] else (
            "A" if row["choice"] == "B" else "B"
        )
        bits[row["step"]] = bit
    result = "".join(bits)
    return result if result in CODES else None


def run_source(workspace: Path, run_id: str, factory, workers: int = 3) -> dict[str, object]:
    if type(workers) is not int or not 1 <= workers <= 4:
        raise ValueError("source workers must be 1..4")
    root = _run_dir(workspace, run_id)
    root.mkdir(mode=0o700, exist_ok=False)
    manifest = _manifest(run_id)
    _write_once(root, "manifest.json", manifest)
    journal = SlotJournal(root, run_id)

    def run_unit(i: int, unit: dict[str, object]):
        rows = []
        for step in range(3):
            index = i*3 + step
            send = _send(index, _source_prompt(unit, step), factory, journal,
                         mode="source")
            correct = send["answer"] == unit["private_program"][step] if (
                send["status"] == "accepted") else None
            rows.append({
                "slot_index": index, "unit_id": unit["unit_id"],
                "step": step, "status": send["status"],
                "choice": send["answer"], "correct": correct,
                "latency_ms": send["latency_ms"],
                "prompt_tokens": send["prompt_tokens"],
                "completion_tokens": send["completion_tokens"],
                "reasoning_tokens": send["reasoning_tokens"],
                "failure_class": send["provider_failure_class"],
            })
        return rows

    source = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(run_unit, i, unit)
                   for i, unit in enumerate(manifest["units"])]
        for future in as_completed(futures):
            source.extend(future.result())
    source.sort(key=lambda row: row["slot_index"])
    capsule = {
        "schema": SCHEMA, "run_id": run_id,
        "manifest_sha256": _digest(manifest),
        "procedure_capsules": [{
            "unit_id": unit["unit_id"],
            "policy": _infer([
                row for row in source if row["unit_id"] == unit["unit_id"]
            ]),
        } for unit in manifest["units"]],
        "scientific_acceptance": False,
    }
    _write_once(root, "capsules.json", capsule)
    frozen = {
        "schema": SCHEMA, "run_id": run_id,
        "manifest_sha256": _digest(manifest),
        "capsule_sha256": _digest(capsule),
        "source_rows": source,
        "scientific_acceptance": False,
    }
    _write_once(root, "source.json", frozen)
    return {
        "schema": SCHEMA, "run_id": run_id,
        "phase": "source_complete", "model": MODEL,
        "thinking_requested": "enabled", "reasoning_effort_requested": EFFORT,
        "prescribed_source": 24, "reserved_source": journal.count,
        "source_valid": sum(row["status"] == "accepted" for row in source),
        "source_contexts_eligible": sum(c["policy"] in CODES for c in capsule[
            "procedure_capsules"]),
        "manifest_sha256": _digest(manifest),
        "source_sha256": _digest(frozen),
        "scientific_acceptance": False,
    }


def run_holdout(workspace: Path, run_id: str, factory, workers: int = 3) -> dict[str, object]:
    if type(workers) is not int or not 1 <= workers <= 4:
        raise ValueError("holdout workers must be 1..4")
    root = _run_dir(workspace, run_id)
    if root.is_symlink() or root.stat().st_mode & 0o077:
        raise ValueError("holdout workspace not private")
    manifest = _read(root, "manifest.json")
    capsule = _read(root, "capsules.json")
    frozen = _read(root, "source.json")
    if (manifest.get("schema") != SCHEMA or capsule.get("schema") != SCHEMA
            or manifest.get("run_id") != run_id or capsule.get("run_id") != run_id
            or frozen.get("run_id") != run_id
            or frozen.get("manifest_sha256") != _digest(manifest)
            or frozen.get("capsule_sha256") != _digest(capsule)
            or capsule.get("manifest_sha256") != _digest(manifest)
            or len(manifest.get("units", [])) != 8
            or len(frozen.get("source_rows", [])) != 24
            or len(capsule.get("procedure_capsules", [])) != 8):
        raise ValueError("source/capsule integrity mismatch")
    units = manifest["units"]
    policies = {r["unit_id"]: r["policy"] for r in capsule["procedure_capsules"]}
    if len(policies) != 8 or set(policies) != {u["unit_id"] for u in units}:
        raise ValueError("missing or duplicated capsule")
    for unit in units:
        original = [r for r in frozen["source_rows"]
                    if r["unit_id"] == unit["unit_id"]]
        if policies[unit["unit_id"]] != _infer(original):
            raise ValueError("policy does not match committed graded feedback")

    # Pre-source shuffled donor schedule is fixed by the manifest unit order.
    donors = {}
    for family in FAMILIES:
        group = [unit for unit in units if unit["family"] == family]
        for j, unit in enumerate(group):
            donors[unit["unit_id"]] = group[(j+1) % len(group)]["unit_id"]

    # Fail-closed phase re-entry: no repeated physical sends, even after crash.
    _write_once(root, "holdout-start.json", {
        "schema": SCHEMA, "run_id": run_id,
        "source_sha256": _digest(frozen),
        "capsule_sha256": _digest(capsule),
        "started_no_retry": True,
    })
    journal = SlotJournal(root, run_id)

    def qualify(i: int, unit: dict[str, object], arm: str):
        index = 24 + i*3 + ARMS.index(arm)
        policy = policies[unit["unit_id"]]
        if policy not in CODES:
            return {
                "slot_index": index, "unit_id": unit["unit_id"],
                "family": unit["family"], "arm": arm,
                "status": "not_sent", "correct": None,
                "latency_ms": None, "prompt_tokens": None,
                "completion_tokens": None, "reasoning_tokens": None,
                "policy_source": "incomplete_source",
            }
        candidate = (
            policy if arm == "learned"
            else unit["fresh_random_program"] if arm == "fresh"
            else policies[donors[unit["unit_id"]]]
        )
        # If the unrelated donor did not finish, use the pre-frozen placebo
        # of identical length instead; preserve the fallback distinction.
        donor_fallback = arm == "neutral" and candidate not in CODES
        if donor_fallback:
            candidate = unit["fresh_random_program"]
        prompt = _holdout_prompt(unit, candidate)
        sent = _send(index, prompt, factory, journal, mode="holdout")
        correct = (sent["answer"] == _execute(
            unit["family"], unit["holdout_payload"], unit["private_program"]
        ) if sent["status"] == "accepted" else None)
        return {
            "slot_index": index, "unit_id": unit["unit_id"],
            "family": unit["family"], "arm": arm,
            "status": sent["status"], "correct": correct,
            "latency_ms": sent["latency_ms"],
            "prompt_tokens": sent["prompt_tokens"],
            "completion_tokens": sent["completion_tokens"],
            "reasoning_tokens": sent["reasoning_tokens"],
            "policy_source": (
                "persisted_relevant" if arm == "learned"
                else "fresh_untrained_random" if arm == "fresh"
                else "shuffled_other_agent_or_fallback"
            ),
            "failure_class": sent["provider_failure_class"],
        }

    rows = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(qualify, i, unit, arm)
                   for i, unit in enumerate(units) for arm in ARMS]
        for future in as_completed(futures):
            rows.append(future.result())
    rows.sort(key=lambda row: row["slot_index"])
    if len(rows) != 24 or [r["slot_index"] for r in rows] != list(range(24, 48)):
        raise ValueError("incomplete fixed denominator")
    _write_once(root, "terminal.json", {
        "schema": SCHEMA, "run_id": run_id, "source_sha256": _digest(frozen),
        "capsule_sha256": _digest(capsule), "holdout_rows": rows,
        "scientific_acceptance": False,
    })
    arms = {}
    for arm in ARMS:
        subset = [row for row in rows if row["arm"] == arm]
        accepted = [row for row in subset if row["status"] == "accepted"]
        arms[arm] = {
            "prescribed": 8,
            "accepted": len(accepted),
            "correct": sum(r["correct"] is True for r in subset),
            "by_family": {family: {
                "prescribed": 4,
                "accepted": sum(r["status"] == "accepted" for r in subset
                                if r["family"] == family),
                "correct": sum(r["correct"] is True for r in subset
                               if r["family"] == family),
            } for family in FAMILIES},
            "reported_completion_tokens": sum(
                r["completion_tokens"] or 0 for r in subset
            ),
            "median_latency_ms": (
                statistics.median(r["latency_ms"] for r in subset
                                  if r["latency_ms"] is not None)
                if any(r["latency_ms"] is not None for r in subset) else None
            ),
        }
    return {
        "schema": SCHEMA, "run_id": run_id, "phase": "holdout_closed",
        "model": MODEL, "reasoning_effort_requested": EFFORT,
        "thinking_requested": "enabled",
        "process_restart_required": True,
        "memory_capsule_steps": 3, "same_size_capsules_all_arms": True,
        "raw_source_grades_supplied_to_holdout_model": False,
        "new_context_ids_and_holdout_operands": True,
        "source_attempts_prescribed": 24,
        "qualification_attempts_prescribed": 24,
        "physical_holdout_reservations": journal.count,
        "eligible_contexts": sum(policy in CODES for policy in policies.values()),
        "qualification_by_arm": arms,
        "qualification_rows_redacted": rows,
        "qualification_status_counts": dict(Counter(r["status"] for r in rows)),
        "vendor_billing_independently_attested": False,
        "model_parameters_updated": False, "scientific_acceptance": False,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="GLM-5.3 real 3-step procedure agent memory")
    p.add_argument("--phase", required=True, choices=("source", "holdout"))
    p.add_argument("--run-id", required=True)
    p.add_argument("--workspace", type=Path)
    p.add_argument("--workers", type=int, default=3)
    p.add_argument("--live", action="store_true")
    p.add_argument("--timeout-seconds", type=float, default=120)
    p.add_argument("--max-tokens", type=int, default=4096)
    args = p.parse_args(argv)
    if not args.live:
        print(json.dumps({"status": "offline_no_sends", "phase": args.phase,
                          "scientific_acceptance": False}))
        return 0
    if (args.workspace is None or not args.workspace.is_absolute()
            or not 1 <= args.workers <= 4
            or not 30 <= args.timeout_seconds <= 300
            or not 256 <= args.max_tokens <= 16384):
        raise SystemExit("invalid live parameters")
    key = os.environ.get("C3R_ZAI_API_KEY", "").strip()
    if not key:
        raise SystemExit("C3R_ZAI_API_KEY missing, zero sends")
    def factory():
        return ZaiStandardModelPort(
            api_key=key, model_id=MODEL,
            ledger=PhysicalSendLedger(1), enabled=True,
            route="coding", reasoning_effort=EFFORT,
            timeout_seconds=args.timeout_seconds,
            max_tokens=args.max_tokens,
        )
    if args.phase == "source":
        result = run_source(args.workspace, args.run_id, factory, args.workers)
    else:
        result = run_holdout(args.workspace, args.run_id, factory, args.workers)
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
