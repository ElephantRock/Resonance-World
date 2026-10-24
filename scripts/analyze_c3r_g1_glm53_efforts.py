"""Read-only aggregation of finished GLM-5.3 low/high/max G1 cohorts.

Only closes observed outcomes; never calls the provider or reconstructs
unknown sends. Validates the separate fixed 40-attempt denominators and
returns public descriptive metrics without revealing private row choices.
"""

from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter
from pathlib import Path

EFFORTS = ("low", "high", "max")
ARMS = ("learned", "fresh", "neutral")
STAGES = ("development", "qualification")
FAMILIES = ("arithmetic", "text")
MAX_BYTES = 1_048_576


def _read(path: Path) -> dict[str, object]:
    if path.stat().st_size > MAX_BYTES:
        raise ValueError("oversized completed cohort report")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("cohort JSON must be an object")
    return data


def _totals(rows: list[dict[str, object]]) -> dict[str, object]:
    latency = [
        float(r["latency_ms"]) for r in rows
        if isinstance(r.get("latency_ms"), (int, float))
        and not isinstance(r["latency_ms"], bool)
        and 0 <= r["latency_ms"] <= 300_000
    ]
    keys = (
        "prompt_tokens_reported",
        "completion_tokens_reported",
        "reasoning_tokens_reported",
    )
    tokens = {}
    for key in keys:
        observed = [
            r[key] for r in rows if type(r.get(key)) is int and r[key] >= 0
        ]
        tokens[key] = {
            "observed_sum": sum(observed),
            "reporting_rows": len(observed),
            "missing_rows": len(rows) - len(observed),
        }
    return {
        "attempts": len(rows),
        "statuses": dict(Counter(str(r["status"]) for r in rows)),
        "valid_answer_count": sum(r["status"] == "accepted" for r in rows),
        "median_latency_ms": statistics.median(latency) if latency else None,
        "latency_reporting_rows": len(latency),
        "reported_usage": tokens,
    }


def analyze(paths: tuple[Path, ...]) -> dict[str, object]:
    if len(paths) != 3:
        raise ValueError("provide exactly one finalized cohort for each effort")
    runs: dict[str, dict[str, object]] = {}
    seen_ids = set()
    public_plan_digest = None
    for path in paths:
        cohort = _read(path)
        effort = cohort.get("reasoning_effort_requested")
        run_id = cohort.get("run_id")
        if (effort not in EFFORTS or effort in runs
                or not isinstance(run_id, str) or run_id in seen_ids
                or cohort.get("model") != "glm-5.3"
                or cohort.get("thinking_mode") != "enabled_requested"
                or cohort.get("scientific_acceptance") is not False
                or cohort.get("prescribed_attempts") != 40
                or cohort.get("source_attempts") != 16
                or cohort.get("holdout_attempts") != 24
                or cohort.get("external_auditor_required") is not False
                or cohort.get("control_fallback_policy")
                != "default_A_if_no_actual_grades_v1"):
            raise ValueError("cohort metadata does not match prospective design")
        digest = cohort.get("plan_digest")
        if not isinstance(digest, str) or len(digest) != 64:
            raise ValueError("missing frozen public design digest")
        if public_plan_digest is None:
            public_plan_digest = digest
        if public_plan_digest != digest:
            raise ValueError("cohorts used different public task plans")
        seen_ids.add(run_id)
        rows = cohort.get("records")
        if not isinstance(rows, list) or len(rows) != 40:
            raise ValueError("40 retained logical attempts required")
        if sorted(r.get("index") for r in rows if isinstance(r, dict)) != list(range(40)):
            raise ValueError("missing/duplicate logical attempt indices")
        if (sum(r["stage"] == "development" for r in rows) != 16
                or sum(r["stage"] == "qualification" for r in rows) != 24):
            raise ValueError("16 source and 24 holdout attempt split required")
        qual = [r for r in rows if r["stage"] == "qualification"]
        if (any(sum(r["arm"] == arm for r in qual) != 8 for arm in ARMS)
                or any(sum(r["family"] == family for r in qual) != 12
                       for family in FAMILIES)):
            raise ValueError("holdout arms or families not balanced")
        for arm in ARMS:
            arm_rows = [r for r in qual if r["arm"] == arm]
            reported = cohort["qualification_by_arm"][arm]
            if (reported["correct"] != sum(r["correct"] is True for r in arm_rows)
                    or reported["accepted"] != sum(
                        r["status"] == "accepted" for r in arm_rows
                    )
                    or reported["prescribed"] != 8):
                raise ValueError("reported arm grade does not match 40 attempt rows")
        send_count = cohort.get("physical_sends_reserved")
        if type(send_count) is not int or not 0 <= send_count <= 40:
            raise ValueError("invalid physical request reservation count")
        if send_count != sum(r["status"] != "not_sent" for r in rows):
            raise ValueError("physical reservations do not reconcile to statuses")
        summary = {
            "run_id": run_id,
            "effort_requested": effort,
            "physical_sends_reserved": send_count,
            "source_contexts_eligible": cohort.get("source_contexts_eligible"),
            "source": _totals([r for r in rows if r["stage"] == "development"]),
            "qualification": _totals(qual),
            "qualification_by_arm": {
                arm: {
                    "correct": sum(r["correct"] is True for r in qual if r["arm"] == arm),
                    "accepted": sum(r["status"] == "accepted" for r in qual if r["arm"] == arm),
                    "prescribed": 8,
                    **_totals([r for r in qual if r["arm"] == arm]),
                }
                for arm in ARMS
            },
            "scientific_acceptance": False,
        }
        runs[effort] = summary
    if set(runs) != set(EFFORTS):
        raise ValueError("missing low/high/max model effort cohort")
    return {
        "schema": "c3r-g1-glm53-three-effort-descriptive-v0.1",
        "same_public_tasks_reused": True,
        "private_target_assignments_paired_across_efforts": False,
        "public_plan_digest": public_plan_digest,
        "planned_logical_attempts": 120,
        "physical_sends_reserved": sum(
            runs[e]["physical_sends_reserved"] for e in EFFORTS
        ),
        "models": {e: runs[e] for e in EFFORTS},
        "provider_reported_tokens_are_not_vendor_invoice": True,
        "proves_persistent_agent_memory": False,
        "scientific_acceptance": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Offline postclosure G1 effort comparison")
    parser.add_argument("--cohort", type=Path, action="append", required=True)
    args = parser.parse_args(argv)
    try:
        report = analyze(tuple(args.cohort))
    except (OSError, ValueError, TypeError, KeyError):
        print(json.dumps({
            "schema": "c3r-g1-glm53-three-effort-descriptive-v0.1",
            "status": "incomplete_or_rejected",
            "scientific_acceptance": False,
        }))
        return 2
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
