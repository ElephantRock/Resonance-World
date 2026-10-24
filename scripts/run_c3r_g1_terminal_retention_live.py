"""G1 terminal-feedback acquisition and two-session procedural retention experiment.

Each agent tests complete THREE-step programs and receives ONLY one binary
terminal success/failure grade per completed trial. The deterministic internal
learner eliminates candidate programs; unlike the earlier per-step experiment,
no individual hidden step's grade is ever revealed. Learned, Fresh and Neutral
each receive equal-length three-bit capsules. The two controls are sampled
INDEPENDENTLY of every target and of one another, preventing biased shuffled
donor assignments.

A source interpreter and two separate holdout interpreters communicate only
through owner-private, fsynced local files. No retries or independent auditor.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import statistics
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from run_c3r_g1_three_step_procedure_live import (
    ARMS,
    CODES,
    EFFORT,
    FAMILIES,
    MODEL,
    SlotJournal,
    _digest,
    _execute,
    _holdout_prompt,
    _read,
    _run_dir,
    _send,
    _task,
    _write_once,
)

from resonance_world.c3r_g1_zai_transport import PhysicalSendLedger, ZaiStandardModelPort

SCHEMA = "c3r-g1-terminal-grade-two-retentions-v0.1"
SOURCE_SLOTS = 56
WAVE_SLOTS = 24
TOTAL_SLOTS = 104
WAVES = ("retention1", "retention2")


def _manifest(run_id: str) -> dict[str, object]:
    rng = random.SystemRandom()
    units = []
    for family in FAMILIES:
        balanced = []
        for _ in range(3):
            bits = list("AABB")
            rng.shuffle(bits)
            balanced.append(bits)
        for index in range(4):
            target = "".join(bits[index] for bits in balanced)
            candidates = list(CODES)
            rng.shuffle(candidates)
            # Fresh and neutral have the same prior (uniform over 8 programs)
            # and equal exact capsule sizes, independent of target and grades.
            units.append({
                "unit_id": f"terminal-{family[:3]}-{index:02d}",
                "family": family,
                "context_id": "ctx-" + os.urandom(12).hex(),
                "private_target": target,
                "candidate_order": candidates,
                "fresh_policy": rng.choice(CODES),
                "neutral_policy": rng.choice(CODES),
                "probe_tasks": [_task(rng, family) for _ in range(7)],
                "holdout_tasks": {
                    wave: _task(rng, family) for wave in WAVES
                },
            })
    return {
        "schema": SCHEMA, "run_id": run_id,
        "model": MODEL, "requested_effort": EFFORT,
        "prescribed_source_slots": SOURCE_SLOTS,
        "prescribed_holdout_slots_per_wave": WAVE_SLOTS,
        "units": units, "scientific_acceptance": False,
    }


def _unit_decision(records: list[dict[str, object]],
                   candidate_order: list[str]) -> str | None:
    """Infer a complete procedure only from all-program terminal grade bits."""
    candidates = set(CODES)
    for row in records:
        if row["status"] == "not_sent":
            continue
        if (row["status"] != "accepted"
                or row["candidate"] not in CODES
                or type(row["correct"]) is not bool):
            continue
        if row["correct"]:
            return row["candidate"]
        candidates.discard(row["candidate"])
    if len(candidates) == 1 and (
        len([row for row in records if row["status"] == "accepted"]) == 7
    ):
        return next(iter(candidates))
    return None


def run_source(workspace: Path, run_id: str, port_factory,
               workers: int = 3) -> dict[str, object]:
    if type(workers) is not int or not 1 <= workers <= 4:
        raise ValueError("workers must be 1..4")
    folder = _run_dir(workspace, run_id)
    folder.mkdir(mode=0o700, exist_ok=False)
    manifest = _manifest(run_id)
    _write_once(folder, "manifest.json", manifest)
    journal = SlotJournal(folder, run_id, max_slots=TOTAL_SLOTS)

    def unit_source(index: int, unit: dict[str, object]):
        rows = []
        identified = None
        for offset in range(7):
            slot = index * 7 + offset
            candidate = unit["candidate_order"][offset]
            if identified is not None:
                rows.append({
                    "index": slot, "unit_id": unit["unit_id"],
                    "candidate": candidate, "status": "not_sent",
                    "correct": None, "latency_ms": None,
                    "prompt_tokens": None, "completion_tokens": None,
                    "reasoning_tokens": None,
                })
                continue
            task_unit = dict(unit)
            task_unit["holdout_payload"] = unit["probe_tasks"][offset]
            reply = _send(
                slot, _holdout_prompt(task_unit, candidate), port_factory,
                journal, mode="holdout",
            )
            grade = (
                reply["answer"] == _execute(
                    unit["family"], unit["probe_tasks"][offset],
                    unit["private_target"],
                ) if reply["status"] == "accepted" else None
            )
            rows.append({
                "index": slot, "unit_id": unit["unit_id"],
                "candidate": candidate, "status": reply["status"],
                "correct": grade, "latency_ms": reply["latency_ms"],
                "prompt_tokens": reply["prompt_tokens"],
                "completion_tokens": reply["completion_tokens"],
                "reasoning_tokens": reply["reasoning_tokens"],
            })
            identified = _unit_decision(rows, unit["candidate_order"])
        return rows

    source = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [
            pool.submit(unit_source, i, unit)
            for i, unit in enumerate(manifest["units"])
        ]
        for future in as_completed(futures):
            source.extend(future.result())
    source.sort(key=lambda row: row["index"])
    if len(source) != SOURCE_SLOTS or [
        row["index"] for row in source
    ] != list(range(SOURCE_SLOTS)):
        raise ValueError("source must preserve all 56 planned attempts")
    capsules = {
        "schema": SCHEMA, "run_id": run_id,
        "manifest_sha256": _digest(manifest),
        "learned_policies": [{
            "unit_id": unit["unit_id"],
            "policy": _unit_decision([
                row for row in source if row["unit_id"] == unit["unit_id"]
            ], unit["candidate_order"]),
        } for unit in manifest["units"]],
        "scientific_acceptance": False,
    }
    _write_once(folder, "capsules.json", capsules)
    freeze = {
        "schema": SCHEMA, "run_id": run_id,
        "manifest_sha256": _digest(manifest),
        "capsule_sha256": _digest(capsules),
        "source_rows": source,
        "scientific_acceptance": False,
    }
    _write_once(folder, "source.json", freeze)
    return {
        "schema": SCHEMA, "phase": "source", "run_id": run_id,
        "source_slots_prescribed": SOURCE_SLOTS,
        "source_sends_reserved": journal.count,
        "source_accepted": sum(row["status"] == "accepted" for row in source),
        "source_not_sent": sum(row["status"] == "not_sent" for row in source),
        "eligible_contexts": sum(
            item["policy"] in CODES for item in capsules["learned_policies"]
        ),
        "source_sha256": _digest(freeze), "capsule_sha256": _digest(capsules),
        "only_terminal_grades_used": True,
        "scientific_acceptance": False,
    }


def _validated_phase(folder: Path, run_id: str, wave: str):
    if wave not in WAVES:
        raise ValueError("unknown retention wave")
    if folder.is_symlink() or folder.stat().st_mode & 0o077:
        raise ValueError("retention directory is not private")
    manifest = _read(folder, "manifest.json")
    capsule = _read(folder, "capsules.json")
    source = _read(folder, "source.json")
    if (manifest.get("schema") != SCHEMA
            or capsule.get("schema") != SCHEMA
            or source.get("schema") != SCHEMA
            or any(x.get("run_id") != run_id for x in (
                manifest, capsule, source,
            ))
            or capsule.get("manifest_sha256") != _digest(manifest)
            or source.get("manifest_sha256") != _digest(manifest)
            or source.get("capsule_sha256") != _digest(capsule)
            or len(manifest.get("units", [])) != 8
            or len(capsule.get("learned_policies", [])) != 8
            or len(source.get("source_rows", [])) != SOURCE_SLOTS):
        raise ValueError("source/capsule integrity mismatch")
    policies = {row["unit_id"]: row["policy"]
                for row in capsule["learned_policies"]}
    if (len(policies) != 8
            or set(policies) != {u["unit_id"] for u in manifest["units"]}):
        raise ValueError("capsule identity mismatch")
    for unit in manifest["units"]:
        records = [r for r in source["source_rows"]
                   if r["unit_id"] == unit["unit_id"]]
        if policies[unit["unit_id"]] != _unit_decision(
            records, unit["candidate_order"]
        ):
            raise ValueError("capsule disagrees with terminal-grade evidence")
        if any(row["candidate"] not in unit["candidate_order"] for row in records):
            raise ValueError("unknown source candidate")
    if wave == "retention2":
        previous = _read(folder, "retention1-terminal.json")
        if (previous.get("run_id") != run_id
                or previous.get("source_sha256") != _digest(source)
                or previous.get("capsule_sha256") != _digest(capsule)
                or len(previous.get("rows", [])) != WAVE_SLOTS):
            raise ValueError("retention1 not closed or modified")
    return manifest, capsule, source, policies


def run_retention(workspace: Path, run_id: str, wave: str, port_factory,
                  workers: int = 3) -> dict[str, object]:
    if type(workers) is not int or not 1 <= workers <= 4:
        raise ValueError("workers must be 1..4")
    folder = _run_dir(workspace, run_id)
    manifest, capsule, source, policies = _validated_phase(folder, run_id, wave)
    _write_once(folder, f"{wave}-start.json", {
        "schema": SCHEMA, "run_id": run_id,
        "wave": wave,
        "source_sha256": _digest(source),
        "capsule_sha256": _digest(capsule),
        "exclusive_no_replay": True,
    })
    journal = SlotJournal(folder, run_id, max_slots=TOTAL_SLOTS)
    offset = SOURCE_SLOTS + WAVES.index(wave) * WAVE_SLOTS

    def one(i: int, unit: dict[str, object], arm: str):
        slot = offset + i * 3 + ARMS.index(arm)
        relevant = policies[unit["unit_id"]]
        if relevant not in CODES:
            return {
                "index": slot, "unit_id": unit["unit_id"],
                "family": unit["family"], "arm": arm,
                "status": "not_sent", "correct": None,
                "latency_ms": None,
                "prompt_tokens": None, "completion_tokens": None,
                "reasoning_tokens": None,
            }
        # Two independent uniform-prior policies of the same exact size
        # as the learned capsule; not a donor rotated in a balanced quartet.
        chosen = (relevant if arm == "learned" else
                  unit["fresh_policy"] if arm == "fresh"
                  else unit["neutral_policy"])
        prompt_unit = dict(unit)
        prompt_unit["holdout_payload"] = unit["holdout_tasks"][wave]
        reply = _send(
            slot, _holdout_prompt(prompt_unit, chosen),
            port_factory, journal, mode="holdout",
        )
        target = _execute(
            unit["family"], unit["holdout_tasks"][wave],
            unit["private_target"],
        )
        return {
            "index": slot, "unit_id": unit["unit_id"],
            "family": unit["family"], "arm": arm,
            "status": reply["status"],
            "correct": (
                reply["answer"] == target
                if reply["status"] == "accepted" else None
            ),
            "latency_ms": reply["latency_ms"],
            "prompt_tokens": reply["prompt_tokens"],
            "completion_tokens": reply["completion_tokens"],
            "reasoning_tokens": reply["reasoning_tokens"],
        }

    rows = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [
            pool.submit(one, i, unit, arm)
            for i, unit in enumerate(manifest["units"]) for arm in ARMS
        ]
        for future in as_completed(futures):
            rows.append(future.result())
    rows.sort(key=lambda r: r["index"])
    if len(rows) != WAVE_SLOTS or [
        row["index"] for row in rows
    ] != list(range(offset, offset + WAVE_SLOTS)):
        raise ValueError("retention denominator not closed")
    terminal = {
        "schema": SCHEMA, "run_id": run_id, "wave": wave,
        "source_sha256": _digest(source),
        "capsule_sha256": _digest(capsule),
        "rows": rows, "scientific_acceptance": False,
    }
    _write_once(folder, f"{wave}-terminal.json", terminal)
    summary = {}
    for arm in ARMS:
        sub = [r for r in rows if r["arm"] == arm]
        latencies = [r["latency_ms"] for r in sub if r["latency_ms"] is not None]
        summary[arm] = {
            "prescribed": 8,
            "accepted": sum(r["status"] == "accepted" for r in sub),
            "correct": sum(r["correct"] is True for r in sub),
            "completion_tokens_reported": sum(
                r["completion_tokens"] or 0 for r in sub
            ),
            "median_latency_ms": statistics.median(latencies) if latencies else None,
            "family": {
                family: {
                    "prescribed": 4,
                    "accepted": sum(r["status"] == "accepted" for r in sub
                                    if r["family"] == family),
                    "correct": sum(r["correct"] is True for r in sub
                                   if r["family"] == family),
                } for family in FAMILIES
            },
        }
    return {
        "schema": SCHEMA, "phase": wave, "run_id": run_id,
        "model": MODEL, "thinking_requested": "enabled",
        "reasoning_effort_requested": EFFORT,
        "wave_order": WAVES.index(wave) + 1,
        "separate_interpreter_required": True,
        "chronological_elapsed_time_proven": False,
        "source_transcript_reinserted_in_prompt": False,
        "learned_capsule_unmodified_between_waves": True,
        "equal_capacity_and_independent_uniform_control_capsules": True,
        "prescribed_holdout_slots": WAVE_SLOTS,
        "physical_holdout_reservations": journal.count,
        "eligible_contexts": sum(p in CODES for p in policies.values()),
        "qualification_by_arm": summary,
        "qualification_rows_redacted": rows,
        "status_counts": dict(Counter(r["status"] for r in rows)),
        "scientific_acceptance": False,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Terminal-only G1 learning and two restarts")
    p.add_argument("--phase", choices=("source", *WAVES), required=True)
    p.add_argument("--run-id", required=True)
    p.add_argument("--workspace", type=Path)
    p.add_argument("--workers", type=int, default=3)
    p.add_argument("--timeout-seconds", type=float, default=120)
    p.add_argument("--max-tokens", type=int, default=4096)
    p.add_argument("--live", action="store_true")
    args = p.parse_args(argv)
    if not args.live:
        print(json.dumps({
            "phase": args.phase, "status": "offline_zero_sends",
            "scientific_acceptance": False,
        }))
        return 0
    if (args.workspace is None or not args.workspace.is_absolute()
            or not 1 <= args.workers <= 4
            or not 30 <= args.timeout_seconds <= 300
            or not 256 <= args.max_tokens <= 16384):
        raise SystemExit("invalid real run parameters")
    key = os.environ.get("C3R_ZAI_API_KEY", "").strip()
    if not key:
        raise SystemExit("Z.AI credential unavailable; zero sends")
    def factory():
        return ZaiStandardModelPort(
            api_key=key, model_id=MODEL, ledger=PhysicalSendLedger(1),
            route="coding", enabled=True, reasoning_effort=EFFORT,
            timeout_seconds=args.timeout_seconds, max_tokens=args.max_tokens,
        )
    result = (run_source(args.workspace, args.run_id, factory, args.workers)
              if args.phase == "source" else
              run_retention(args.workspace, args.run_id, args.phase,
                            factory, args.workers))
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
