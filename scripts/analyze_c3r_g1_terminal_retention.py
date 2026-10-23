"""Read-only closure audit for three terminal-grade two-wave GLM-5.3 cohorts.

Requires complete source, first retention and second retention reports for
each unique run. Never supplies missing data, silently drops invalid attempts,
or treats the same context tested in two waves as an independent unit.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

ARMS = ("learned", "fresh", "neutral")
WAVES = ("retention1", "retention2")
SCHEMA = "c3r-g1-terminal-grade-two-retentions-v0.1"
MAX_SIZE = 256_000


def _read(path: Path) -> dict[str, object]:
    if path.stat().st_size > MAX_SIZE:
        raise ValueError("oversized redacted evidence input")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("JSON evidence must be object")
    return data


def _arm_grade(rows: list[dict[str, object]], arm: str):
    return {row["unit_id"]: row["correct"] is True
            for row in rows if row["arm"] == arm}


def _pairs(rows: list[dict[str, object]], control: str) -> dict[str, int]:
    learned = _arm_grade(rows, "learned")
    other = _arm_grade(rows, control)
    if set(learned) != set(other) or len(learned) != 8:
        raise ValueError("unpaired context units")
    return {
        "learned_only": sum(learned[u] and not other[u] for u in learned),
        "control_only": sum(other[u] and not learned[u] for u in learned),
        "ties": sum(learned[u] == other[u] for u in learned),
    }


def analyze(triples: tuple[tuple[Path, Path, Path], ...]) -> dict[str, object]:
    if len(triples) != 3:
        raise ValueError("exactly three independent cohort evidence triples required")
    seen: set[str] = set()
    cohorts = []
    for paths in triples:
        src, first, second = map(_read, paths)
        run_id = src.get("run_id")
        if (not isinstance(run_id, str) or not run_id
                or run_id in seen
                or src.get("schema") != SCHEMA
                or src.get("phase") != "source"
                or src.get("scientific_acceptance") is not False
                or src.get("source_slots_prescribed") != 56
                or first.get("run_id") != run_id
                or second.get("run_id") != run_id
                or src.get("eligible_contexts") not in range(9)):
            raise ValueError("source cohort missing/duplicated or inconsistent")
        seen.add(run_id)
        source_count = src.get("source_sends_reserved")
        source_not_sent = src.get("source_not_sent")
        source_accepted = src.get("source_accepted")
        if (type(source_count) is not int or not 0 <= source_count <= 56
                or type(source_not_sent) is not int
                or source_not_sent != 56-source_count
                or type(source_accepted) is not int
                or not 0 <= source_accepted <= source_count):
            raise ValueError("source reservation and logical denominator invalid")
        wave_out = {}
        wave_rows = {}
        for wave, evidence in zip(WAVES, (first, second)):
            if (evidence.get("schema") != SCHEMA
                    or evidence.get("phase") != wave
                    or evidence.get("scientific_acceptance") is not False
                    or evidence.get("prescribed_holdout_slots") != 24
                    or evidence.get("separate_interpreter_required") is not True
                    or evidence.get("equal_capacity_and_independent_uniform_control_capsules") is not True
                    or evidence.get("learned_capsule_unmodified_between_waves") is not True
                    or evidence.get("source_transcript_reinserted_in_prompt") is not False
                    or evidence.get("eligible_contexts") != src["eligible_contexts"]):
                raise ValueError("retention evidence missing or incompatible")
            rows = evidence.get("qualification_rows_redacted")
            if not isinstance(rows, list) or len(rows) != 24:
                raise ValueError("all 24 retention slots must be present")
            offset = 56 if wave == "retention1" else 80
            if sorted(r["index"] for r in rows) != list(range(offset, offset+24)):
                raise ValueError("retention attempt index duplicated or missing")
            if any(type(r.get("correct")) not in (bool, type(None)) or
                   r.get("status") not in (
                       "accepted", "invalid_format", "provider_error", "not_sent"
                   ) for r in rows):
                raise ValueError("invalid row grade or attempt status")
            if (sum(r["status"] != "not_sent" for r in rows)
                    != evidence.get("physical_holdout_reservations")):
                raise ValueError("physical reservation count mismatch")
            cohort_units = {r["unit_id"] for r in rows}
            if len(cohort_units) != 8:
                raise ValueError("expected eight context units per wave")
            for unit_id in cohort_units:
                if {r["arm"] for r in rows if r["unit_id"] == unit_id} != set(ARMS):
                    raise ValueError("missing arm within context triplet")
            grades = {}
            for arm in ARMS:
                reported = evidence["qualification_by_arm"][arm]
                subset = [r for r in rows if r["arm"] == arm]
                valid = sum(r["status"] == "accepted" for r in subset)
                correct = sum(r["correct"] is True for r in subset)
                if (len(subset) != 8 or reported["prescribed"] != 8
                        or reported["accepted"] != valid
                        or reported["correct"] != correct):
                    raise ValueError("per-arm grade mismatch")
                grades[arm] = {"correct": correct, "valid": valid, "prescribed": 8}
            wave_rows[wave] = rows
            wave_out[wave] = {
                "source_contexts_eligible": evidence["eligible_contexts"],
                "physical_holdout_reservations": evidence["physical_holdout_reservations"],
                "status_counts": dict(Counter(r["status"] for r in rows)),
                "arms": grades,
                "paired": {
                    control: _pairs(rows, control)
                    for control in ("fresh", "neutral")
                },
            }
        earlier = _arm_grade(wave_rows["retention1"], "learned")
        later = _arm_grade(wave_rows["retention2"], "learned")
        if set(earlier) != set(later):
            raise ValueError("retention waves do not follow same context identities")
        changes = {
            "correct_both": sum(earlier[u] and later[u] for u in earlier),
            "lost_by_wave2": sum(earlier[u] and not later[u] for u in earlier),
            "recovered_by_wave2": sum(not earlier[u] and later[u] for u in earlier),
            "incorrect_both": sum(not earlier[u] and not later[u] for u in earlier),
        }
        cohorts.append({
            "run_id": run_id,
            "source_sends_reserved": source_count,
            "source_accepted": source_accepted,
            "source_not_sent": source_not_sent,
            "source_eligible_contexts": src["eligible_contexts"],
            "waves": wave_out,
            "same_context_learned_retention_changes": changes,
        })
    totals = {
        wave: {
            arm: {
                "correct": sum(c["waves"][wave]["arms"][arm]["correct"] for c in cohorts),
                "accepted": sum(c["waves"][wave]["arms"][arm]["valid"] for c in cohorts),
                "prescribed": 24,
            } for arm in ARMS
        } for wave in WAVES
    }
    return {
        "schema": "c3r-g1-terminal-two-wave-summary-v0.1",
        "cohorts": cohorts,
        "totals": totals,
        "planned_logical_attempts": 312,
        "source_physical_reservations": sum(c["source_sends_reserved"] for c in cohorts),
        "holdout_physical_reservations": sum(
            c["waves"][wave]["physical_holdout_reservations"]
            for c in cohorts for wave in WAVES
        ),
        "same_contexts_retested_across_waves": True,
        "chronological_elapsed_time_proven": False,
        "provider_billing_independently_attested": False,
        "demonstrates_autonomous_model_learning": False,
        "scientific_acceptance": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only two-retention cohort audit")
    parser.add_argument("--cohort", action="append", nargs=3, metavar=(
        "SOURCE_JSON", "RETENTION1_JSON", "RETENTION2_JSON"
    ), required=True)
    args = parser.parse_args(argv)
    try:
        triples = tuple(tuple(Path(p) for p in trio) for trio in args.cohort)
        result = analyze(triples)
    except (OSError, ValueError, KeyError, TypeError):
        print(json.dumps({
            "status": "incomplete_or_rejected",
            "scientific_acceptance": False,
        }))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
