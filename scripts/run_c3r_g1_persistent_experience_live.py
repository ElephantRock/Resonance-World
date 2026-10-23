"""G1 real-model agent experience-transfer pilot; separated source/holdout processes.

A small deterministic *agent-side* reducer compiles model-attempt feedback into
a persisted, one-bit per-context policy. The qualification process is a new
process and never receives the source transcript. Fresh uses no policy and
Neutral receives a blinded independent placebo policy. Novel context IDs and
heldout operands are sampled before the first send.

This measures external agent experience-store transfer, NOT model-weight learning
or scientific G1 acceptance. Internal-only, no provider retries or auditors.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import re
import statistics
import threading
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from resonance_world.c3r_g1_crossed_plan import PublicTask
from resonance_world.c3r_g1_zai_transport import PhysicalSendLedger, ZaiStandardModelPort
from run_c3r_g1_fourth_crossed_live import _safe_send, prompt_for

MODEL = "glm-5.3"
EFFORT = "low"
ARMS = ("learned", "fresh", "neutral")
FAMILIES = ("arithmetic", "text")
MAX_FILE = 128_000


def _digest(obj: object) -> str:
    return hashlib.sha256(json.dumps(
        obj, separators=(",", ":"), sort_keys=True,
    ).encode()).hexdigest()


def _private_workspace(workspace: Path) -> None:
    if (not workspace.is_absolute() or workspace.is_symlink()
            or workspace.stat().st_uid != os.geteuid()
            or workspace.stat().st_mode & 0o077):
        raise ValueError("workspace must be private, owned, absolute and nonsymlink")


def _run_dir(workspace: Path, run_id: str) -> Path:
    if not isinstance(run_id, str) or re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9_.-]{7,63}", run_id,
    ) is None:
        raise ValueError("invalid unique experience transfer run ID")
    return workspace / ("g1-transfer-" + hashlib.sha256(run_id.encode()).hexdigest())


def _once(directory: Path, name: str, payload: object) -> None:
    path = directory / name
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode() + b"\n"
    if len(raw) > MAX_FILE:
        raise ValueError("private artifact too large")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    fd = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _read(directory: Path, name: str) -> dict[str, object]:
    path = directory / name
    if path.is_symlink() or path.stat().st_size > MAX_FILE:
        raise ValueError("missing/private artifact too large or redirected")
    obj = json.loads(path.read_text(encoding="utf-8"))
    if type(obj) is not dict:
        raise ValueError("private artifact must be object")
    return obj


def _public_task(task: dict[str, object]) -> PublicTask:
    ops = task["operands"]
    if task["family"] == "arithmetic":
        ops = tuple(ops)
    return PublicTask(task["task_id"], task["context_id"],
                      task["family"], task["stage"], ops)


def _new_manifest(run_id: str) -> dict[str, object]:
    randomizer = random.SystemRandom()
    units = []
    for family in FAMILIES:
        ranking = list(range(4))
        randomizer.shuffle(ranking)
        a_indices = set(ranking[:2])
        for i in range(4):
            name = f"mem-{family[:3]}-{i:02d}"
            context = "ctx-" + os.urandom(12).hex()
            tasks = []
            for j in range(3):
                if family == "arithmetic":
                    operand = [
                        randomizer.randrange(100_000, 2_000_000),
                        randomizer.randrange(2, 30),
                        randomizer.randrange(2, 12),
                    ]
                else:
                    nonce = os.urandom(8).hex()
                    operand = f"ab{nonce}ab"
                tasks.append({
                    "task_id": f"{name}-{j}-{os.urandom(6).hex()}",
                    "context_id": context,
                    "family": family,
                    "stage": "development" if j < 2 else "qualification",
                    "operands": operand,
                })
            units.append({
                "unit_id": name,
                "context_id": context,
                "family": family,
                "private_target": "A" if i in a_indices else "B",
                "tasks": tasks,
            })
    return {
        "schema": "c3r-g1-persistent-real-manifest-v0.1",
        "run_id": run_id,
        "model": MODEL, "reasoning_effort": EFFORT,
        "source_attempts": 16, "qualification_attempts": 24,
        "units": units, "scientific_acceptance": False,
    }


class FileJournal:
    def __init__(self, directory: Path, run_id: str) -> None:
        self.directory = directory
        self.run_id = run_id
        self._lock = threading.Lock()
        self._indices: set[int] = set()

    def reserve(self, *, index: int, prompt: str, model: str, route: str) -> None:
        if type(index) is not int or not 0 <= index < 40:
            raise ValueError("invalid reserved slot")
        with self._lock:
            _once(self.directory, f"send-{index:02d}.json", {
                "schema": "c3r-g1-persistent-attempt-reservation-v0.1",
                "run_id": self.run_id, "index": index,
                "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
                "model": model, "route": route,
                "status": "reserved_no_retry",
            })
            self._indices.add(index)

    @property
    def count(self) -> int:
        return len(self._indices)


def _policy(source: list[dict[str, object]]) -> str:
    """Infer the answer bit from observed actions and *binary* private feedback.

    The reducer receives no target labels. This is an explicit deterministic
    agent memory compiler, not a model autonomously acquiring a new capability.
    """
    if len(source) != 2 or any(
        row["status"] != "accepted"
        or row["choice"] not in ("A", "B")
        or type(row["correct"]) is not bool for row in source
    ):
        return "?"
    choices = {
        row["choice"] if row["correct"] else (
            "B" if row["choice"] == "A" else "A"
        ) for row in source
    }
    return next(iter(choices)) if len(choices) == 1 else "?"


def _holdout_prompt(task: PublicTask, policy: str) -> str:
    if policy not in ("A", "B", "?"):
        raise ValueError("capsule policy must be A/B/?")
    # Identical instructions for every arm; never insert graded transcript.
    arithmetic = "A: (value + offset) * factor; B: value * factor + offset."
    text = ("A: replace lowercase 'ab' with 'z', then uppercase; "
            "B: uppercase, then replace lowercase 'ab' with 'z'.")
    return (
        "You are an agent in a NEW session. A memory capsule may have been "
        "persisted from an earlier experience session. It is a proposal, "
        "not a hidden answer key. Choose the hidden context implementation "
        "A or B. If the policy is A or B, use it; if ?, choose A as the "
        "predeclared no-experience baseline. Reply exactly A or B.\n"
        f"Available implementations: {arithmetic if task.family == 'arithmetic' else text}\n"
        f"Public task: {json.dumps(task.record(), sort_keys=True)}\n"
        f"Memory capsule: policy={policy}\n"
        "Reply exactly A or B."
    )


def run_source(*, workspace: Path, run_id: str, port_factory,
               workers: int = 3) -> dict[str, object]:
    _private_workspace(workspace)
    if type(workers) is not int or not 1 <= workers <= 4:
        raise ValueError("source workers must be 1..4")
    folder = _run_dir(workspace, run_id)
    folder.mkdir(mode=0o700, exist_ok=False)
    manifest = _new_manifest(run_id)
    _once(folder, "manifest.json", manifest)  # frozen before first model send
    journal = FileJournal(folder, run_id)

    def source_unit(entry: dict[str, object]):
        outcomes = []
        for idx, task in enumerate(entry["tasks"][:2]):
            source_task = _public_task(task)
            # Never give model the evaluator's target or source feedback.
            prompt = prompt_for(source_task, source_history=(), arm="development")
            global_index = manifest["units"].index(entry) * 2 + idx
            response = _safe_send(
                global_index, prompt, journal=journal,
                port_factory=port_factory, model_id=MODEL,
            )
            correct = (response["choice"] == entry["private_target"]
                       if response["status"] == "accepted" else None)
            outcomes.append({
                "index": global_index, "unit_id": entry["unit_id"],
                "status": response["status"], "choice": response["choice"],
                "correct": correct, "latency_ms": response.get("latency_ms"),
                "prompt_tokens": response["prompt_tokens"],
                "completion_tokens": response["completion_tokens"],
                "reasoning_tokens": response["reasoning_tokens"],
            })
        return entry["unit_id"], outcomes

    source_rows = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(source_unit, e) for e in manifest["units"]]
        for future in as_completed(futures):
            _unit, results = future.result()
            source_rows.extend(results)
    source_rows.sort(key=lambda x: x["index"])
    capsules = []
    for unit in manifest["units"]:
        outcomes = [r for r in source_rows if r["unit_id"] == unit["unit_id"]]
        capsules.append({
            "unit_id": unit["unit_id"], "context_id": unit["context_id"],
            "policy": _policy(outcomes),
            "memory_format": "one_bit_inferred_from_binary_feedback",
        })
    capsule = {
        "schema": "c3r-g1-persisted-experience-capsules-v0.1",
        "run_id": run_id, "manifest_digest": _digest(manifest),
        "capsules": capsules, "scientific_acceptance": False,
    }
    _once(folder, "experience.json", capsule)
    _once(folder, "source.json", {
        "schema": "c3r-g1-experience-source-freeze-v0.1",
        "run_id": run_id, "manifest_digest": _digest(manifest),
        "capsule_digest": _digest(capsule),
        "source_attempts": source_rows, "source_count": 16,
        "scientific_acceptance": False,
    })
    return {
        "schema": "c3r-g1-persistent-source-summary-v0.1",
        "run_id": run_id, "source_attempts_prescribed": 16,
        "source_attempts_reserved": journal.count,
        "source_accepted": sum(r["status"] == "accepted" for r in source_rows),
        "experience_capsules_persisted": len(capsules),
        "eligible_contexts": sum(c["policy"] != "?" for c in capsules),
        "source_freeze_sha256": _digest(_read(folder, "source.json")),
        "provider_billing_attested": False,
        "scientific_acceptance": False,
    }


def run_holdout(*, workspace: Path, run_id: str, port_factory,
                workers: int = 3) -> dict[str, object]:
    _private_workspace(workspace)
    if type(workers) is not int or not 1 <= workers <= 4:
        raise ValueError("holdout workers must be 1..4")
    folder = _run_dir(workspace, run_id)
    if folder.is_symlink() or folder.stat().st_mode & 0o077:
        raise ValueError("holdout run directory is redirected or not private")
    manifest = _read(folder, "manifest.json")
    capsule = _read(folder, "experience.json")
    source = _read(folder, "source.json")
    if (manifest.get("run_id") != run_id or capsule.get("run_id") != run_id
            or source.get("run_id") != run_id
            or source.get("manifest_digest") != _digest(manifest)
            or capsule.get("manifest_digest") != _digest(manifest)
            or source.get("capsule_digest") != _digest(capsule)
            or source.get("source_count") != 16
            or len(manifest.get("units", [])) != 8
            or len(capsule.get("capsules", [])) != 8
            or len(source.get("source_attempts", [])) != 16):
        raise ValueError("source/experience frozen integrity check failed")
    stored = {c["unit_id"]: c for c in capsule["capsules"]}
    if set(stored) != {u["unit_id"] for u in manifest["units"]}:
        raise ValueError("capsule set is not identical to planned contexts")
    for u in manifest["units"]:
        expected = _policy([row for row in source["source_attempts"]
                            if row["unit_id"] == u["unit_id"]])
        if stored[u["unit_id"]]["policy"] != expected:
            raise ValueError("experience policy disagrees with frozen source feedback")
    journal = FileJournal(folder, run_id)
    schedule = [(i, unit, arm) for i, unit in enumerate(manifest["units"])
                for arm in ARMS]
    def act(i: int, unit: dict[str, object], arm: str):
        policy = stored[unit["unit_id"]]["policy"]
        if policy == "?":
            return {"slot_index": 16 + 3*i + ARMS.index(arm),
                    "unit_id": unit["unit_id"], "family": unit["family"],
                    "arm": arm, "status": "not_sent",
                    "correct": None, "latency_ms": None,
                    "prompt_tokens": None, "completion_tokens": None,
                    "reasoning_tokens": None}
        capsule_policy = (policy if arm == "learned" else "?"
                          if arm == "fresh" else
                          ("A" if int(hashlib.sha256(
                              (run_id + unit["context_id"] + "placebo").encode()
                          ).hexdigest(), 16) % 2 == 0 else "B"))
        task = _public_task(unit["tasks"][2])
        prompt = _holdout_prompt(task, capsule_policy)
        index = 16 + 3*i + ARMS.index(arm)
        answer = _safe_send(index, prompt, journal=journal,
                            port_factory=port_factory, model_id=MODEL)
        return {
            "slot_index": index, "unit_id": unit["unit_id"],
            "family": unit["family"], "arm": arm,
            "status": answer["status"],
            "correct": (answer["choice"] == unit["private_target"]
                        if answer["status"] == "accepted" else None),
            "latency_ms": answer.get("latency_ms"),
            "prompt_tokens": answer["prompt_tokens"],
            "completion_tokens": answer["completion_tokens"],
            "reasoning_tokens": answer["reasoning_tokens"],
        }
    holdout = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(act, i, unit, arm)
                   for i, unit, arm in schedule]
        for future in as_completed(futures):
            holdout.append(future.result())
    holdout.sort(key=lambda x: x["slot_index"])
    if len(holdout) != 24 or any(row["slot_index"] != 16+i
                                for i, row in enumerate(holdout)):
        raise ValueError("holdout did not close 24 prescribed slots")
    _once(folder, "terminal.json", {
        "schema": "c3r-g1-experience-holdout-private-v0.1",
        "run_id": run_id, "manifest_digest": _digest(manifest),
        "capsule_digest": _digest(capsule), "holdout": holdout,
        "scientific_acceptance": False,
    })
    public_arms = {}
    for arm in ARMS:
        rows = [row for row in holdout if row["arm"] == arm]
        public_arms[arm] = {
            "prescribed": 8,
            "accepted": sum(r["status"] == "accepted" for r in rows),
            "correct": sum(r["correct"] is True for r in rows),
            "reported_completion_tokens": sum(
                r["completion_tokens"] or 0 for r in rows
            ),
            "median_latency_ms": (
                statistics.median(r["latency_ms"] for r in rows
                                  if r["latency_ms"] is not None)
                if any(r["latency_ms"] is not None for r in rows) else None
            ),
        }
    return {
        "schema": "c3r-g1-persistent-cross-session-real-v0.1",
        "run_id": run_id, "model": MODEL,
        "reasoning_effort_requested": EFFORT,
        "model_session_restarted_between_phases": True,
        "agent_experience_read_from_private_file": True,
        "raw_development_feedback_in_holdout_prompts": False,
        "new_context_identities_and_holdout_operands": True,
        "source_attempts_prescribed": 16,
        "holdout_attempts_prescribed": 24,
        "source_attempts_reserved": 16,
        "holdout_attempts_reserved": journal.count,
        "memory_capsules": len(stored),
        "eligible_contexts": sum(c["policy"] != "?" for c in stored.values()),
        "source_digest": _digest(source), "capsule_digest": _digest(capsule),
        "qualification_by_arm": public_arms,
        "status_counts": dict(Counter(row["status"] for row in holdout)),
        "physical_provider_billing_attested": False,
        "proves_parametric_model_learning": False,
        "scientific_acceptance": False,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Real model, agent file-memory, separated sessions")
    p.add_argument("--phase", choices=("source", "holdout"), required=True)
    p.add_argument("--live", action="store_true")
    p.add_argument("--workspace", type=Path)
    p.add_argument("--run-id", required=True)
    p.add_argument("--workers", type=int, default=3)
    p.add_argument("--timeout-seconds", type=float, default=120)
    p.add_argument("--max-tokens", type=int, default=8192)
    args = p.parse_args(argv)
    if not args.live:
        print(json.dumps({
            "status": "offline_zero_sends", "phase": args.phase,
            "prescribed_model_attempts": 16 if args.phase == "source" else 24,
            "scientific_acceptance": False,
        }))
        return 0
    if (args.workspace is None or not args.workspace.is_absolute()
            or not 1 <= args.workers <= 4
            or not 30 <= args.timeout_seconds <= 300
            or not 512 <= args.max_tokens <= 16384):
        raise SystemExit("invalid live experiment parameters")
    credential = os.environ.get("C3R_ZAI_API_KEY", "").strip()
    if not credential:
        raise SystemExit("missing provider credential, zero sends")
    def factory():
        return ZaiStandardModelPort(
            api_key=credential, model_id=MODEL,
            ledger=PhysicalSendLedger(1), enabled=True, route="coding",
            reasoning_effort=EFFORT, timeout_seconds=args.timeout_seconds,
            max_tokens=args.max_tokens,
        )
    if args.phase == "source":
        result = run_source(
            workspace=args.workspace, run_id=args.run_id,
            port_factory=factory, workers=args.workers,
        )
    else:
        result = run_holdout(
            workspace=args.workspace, run_id=args.run_id,
            port_factory=factory, workers=args.workers,
        )
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
