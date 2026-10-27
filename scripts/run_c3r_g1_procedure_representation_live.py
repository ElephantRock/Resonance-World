"""G1 procedure representation comparison: live dispatch (cap 64, shared
cross-process campaign ledger).

Eight public programs (4 digits + 4 rotate) x 2 representations (code
capsule / numbered natural-language instructions) x 2 execution waves x
2 fresh holdout inputs per program per wave = exactly 64 sends.

Both representations see the SAME task in each paired comparison; send
order is deterministic (sorted program ids). The shared campaign ledger
(write-once O_EXCL slot files, indices 0..63) enforces the global cap
across all processes: a second dispatch attempting overlapping slots
fails visibly instead of silently sending. No retries; every send in
the denominator; results reported as paired (program, wave, input)
rows - never described as a measure of acquired-memory value.
"""

from __future__ import annotations

import argparse
import json
import os
import threading
import time
from pathlib import Path

from c3r_g1_procedure_representation import (
    REPRESENTATIONS,
    WAVES,
    all_programs,
    holdout_task,
    representation_prompt,
)

from resonance_world.c3r_g1_zai_transport import PhysicalSendLedger, ZaiStandardModelPort

SCHEMA = "c3r-g1-procedure-representation-v0.1"
CAMPAIGN_SLOTS = 64
MODEL = "glm-5.3"
EFFORT = "high"
MAX_TOKENS = 4096
ROUTE = "coding"
INPUTS_PER_PROGRAM_PER_WAVE = 2


class CampaignLedger:
    """Cross-process write-once slot ledger enforcing the 64-send cap.

    Each slot file is created with O_CREAT|O_EXCL; reserving an already-
    taken slot raises FileExistsError, so double dispatch or an
    over-budget campaign fails visibly instead of silently sending.
    """

    def __init__(self, root: Path, run_id: str) -> None:
        self.root = root
        self.run_id = run_id
        self._lock = threading.Lock()
        self.root.mkdir(parents=True, exist_ok=True)

    def slot_path(self, index: int) -> Path:
        return self.root / f"campaign-slot-{index:03d}.json"

    def reserve(self, index: int, session: str) -> None:
        with self._lock:
            if not 0 <= index < CAMPAIGN_SLOTS:
                raise RuntimeError(
                    f"campaign slot {index} outside the 64-send cap: "
                    "over-budget campaign"
                )
            path = self.slot_path(index)
            if path.exists():
                raise RuntimeError(
                    f"campaign slot {index} already reserved: double dispatch"
                )
            payload = json.dumps({
                "run_id": self.run_id,
                "session": session,
                "index": index,
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
        return sum(1 for _ in self.root.glob("campaign-slot-*.json"))


def slot_indices(representation: str, wave: str, half: str) -> list[int]:
    rep_index = REPRESENTATIONS.index(representation)
    wave_index = WAVES.index(wave)
    half_index = {"a": 0, "b": 1}[half]
    base = (wave_index * 2 + half_index) * 2 * 8
    return [base + rep_index * 8 + i for i in range(8)]


def _write_json(path: Path, record: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def run_manifest(workspace: Path, run_id: str) -> dict[str, object]:
    manifest = {
        "schema": SCHEMA,
        "run_id": run_id,
        "programs": all_programs(),
        "scientific_acceptance": False,
    }
    path = workspace / "representation-manifest.json"
    if path.exists():
        existing = json.loads(path.read_text(encoding="utf-8"))
        if existing["programs"] != manifest["programs"]:
            raise ValueError("manifest drift: frozen programs changed")
        print("manifest already frozen and identical", flush=True)
        return existing
    _write_json(path, manifest)
    print(f"manifest frozen: {path}", flush=True)
    return manifest


class _PortGuard:
    """Serial send guard: exactly one HTTP call in flight per process."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._busy = False

    def acquire(self) -> None:
        with self._lock:
            if self._busy:
                raise RuntimeError("a send is already in flight")
            self._busy = True

    def release(self) -> None:
        with self._lock:
            self._busy = False


def run_send(
    workspace: Path, run_id: str, representation: str, wave: str, half: str,
    api_key: str, workers: int,
) -> dict[str, object]:
    manifest = run_manifest(workspace, run_id)
    programs = manifest["programs"]
    ledger = CampaignLedger(workspace / "campaign-ledger", run_id)
    indices = slot_indices(representation, wave, half)
    ledger.reserve_block(indices, f"{representation}-{wave}-{half}")
    port_guard = _PortGuard()
    rows: list[dict[str, object]] = []

    for position, program in enumerate(programs):
        for input_index in (0, 1):
            slot = indices[position * 2 + input_index]
            task = holdout_task(
                program["family"], program["program"], wave, input_index
            )
            prompt = representation_prompt(
                representation, program["family"], program["program"], task
            )
            port_guard.acquire()
            started = time.monotonic()
            try:
                completion = ZaiStandardModelPort(
                    api_key=api_key,
                    model_id=MODEL,
                    ledger=PhysicalSendLedger(1),
                    enabled=True,
                    route="coding",
                    reasoning_effort=EFFORT,
                    max_tokens=MAX_TOKENS,
                ).complete_prompt(prompt)
                answer = completion.output.strip()
                finish = completion.finish_reason
            except Exception as exc:
                port_guard.release()
                rows.append({
                    "slot": slot,
                    "program_id": program["program_id"],
                    "representation": representation,
                    "wave": wave,
                    "input_index": input_index,
                    "status": "provider_error",
                    "failure_class": type(exc).__name__[:40],
                    "answer": None,
                    "correct": None,
                    "latency_ms": round((time.monotonic() - started) * 1000, 1),
                })
                print(
                    f"[reps] {representation}/{wave}/{half} "
                    f"{program['program_id']}#{input_index}: "
                    f"provider_error ({type(exc).__name__})",
                    flush=True,
                )
                continue
            port_guard.release()
            truth = _execute(program["family"], task, program["program"])
            correct = (answer == truth) if (finish == "stop" and answer) else None
            rows.append({
                "slot": slot,
                "program_id": program["program_id"],
                "representation": representation,
                "wave": wave,
                "input_index": input_index,
                "status": "evaluated" if correct is not None else "unscored",
                "answer": answer,
                "truth": truth,
                "correct": correct,
                "latency_ms": round((time.monotonic() - started) * 1000, 1),
            })
            print(
                f"[reps] {representation}/{wave}/{half} "
                f"{program['program_id']}#{input_index}: "
                f"answer={answer!r} correct={correct}",
                flush=True,
            )

    evaluated = [row for row in rows if row["correct"] is not None]
    summary = {
        "session": f"{representation}-{wave}-{half}",
        "representation": representation,
        "wave": wave,
        "half": half,
        "sends": len(rows),
        "evaluated": len(evaluated),
        "correct": sum(1 for row in evaluated if row["correct"] is True),
        "unscored": len(rows) - len(evaluated),
        "rows": rows,
    }
    out = workspace / f"summary-{representation}-{wave}-{half}.json"
    out.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    print(f"summary written: {out}", flush=True)
    return summary


def _execute(family: str, task: dict[str, object], code: str) -> str:
    from c3r_g1_novel_grammar_families import _execute as novel_execute

    return novel_execute(family, task, code)


def main() -> int:
    parser = argparse.ArgumentParser(description="G1 representation comparison")
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--session", required=True,
                        choices=("manifest", "send"))
    parser.add_argument("--representation", choices=REPRESENTATIONS)
    parser.add_argument("--wave", choices=WAVES)
    parser.add_argument("--half", choices=("a", "b"))
    parser.add_argument("--api-key", default=os.environ.get("C3R_ZAI_API_KEY", ""))
    parser.add_argument("--workers", type=int, default=2)
    args = parser.parse_args()
    workspace = args.workspace
    workspace.mkdir(parents=True, exist_ok=True)
    if args.session == "manifest":
        run_manifest(workspace, args.run_id)
        return 0
    if not args.api_key:
        parser.error("C3R_ZAI_API_KEY (or --api-key) is required")
    if not (args.representation and args.wave and args.half):
        parser.error("send sessions require --representation --wave --half")
    summary = run_send(
        workspace, args.run_id, args.representation, args.wave, args.half,
        args.api_key, args.workers,
    )
    print(json.dumps(
        {k: v for k, v in summary.items() if k != "rows"}, indent=2
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
