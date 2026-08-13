#!/usr/bin/env python3
"""Add the D2 per-interval contribution query to frozen O2 researcher products."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

QUERY_ID = "contribution_vector_by_interval"
NOT_IDENTIFIABLE = "not_observationally_identifiable"


def canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        + "\n"
    ).encode()


def read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def contribution_answer(events: list[dict[str, Any]]) -> dict[str, Any] | None:
    member_rows = [row for row in events if isinstance(row.get("member_ids"), list)]
    members = sorted({str(member) for row in member_rows for member in row["member_ids"]})
    performance = [row for row in events if row.get("kind") == "performance"]
    if not members or not performance:
        return None
    max_interval = max(int(row["interval"]) for row in performance)
    vectors: list[dict[str, int]] = []
    for interval in range(1, max_interval + 1):
        vector = {member: 0 for member in members}
        for row in performance:
            if int(row["interval"]) != interval:
                continue
            member = str(row.get("subject_id"))
            if member in vector:
                vector[member] += int(row.get("successes", 0))
        vectors.append(vector)
    return {
        "value": vectors,
        "support_event_ids": sorted(str(row["event_id"]) for row in performance),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--r1-dir", required=True, type=Path)
    parser.add_argument("--research-output", required=True, type=Path)
    args = parser.parse_args()

    r1_logs = [read_object(path) for path in sorted(args.r1_dir.glob("*.json"))]
    r1_events = {str(row["history_id"]): list(row["events"]) for row in r1_logs}

    ledger_path = args.research_output / "r2-event-ledger.json"
    r2_answers_path = args.research_output / "r2-researcher-answers.json"
    r1_answers_path = args.research_output / "r1-researcher-answers.json"
    r0_answers_path = args.research_output / "r0-researcher-answers.json"

    ledger = read_object(ledger_path)
    r2_doc = read_object(r2_answers_path)
    r1_doc = read_object(r1_answers_path)
    r0_doc = read_object(r0_answers_path)

    r2_events = {
        str(row["history_id"]): list(row["events"]) for row in ledger["histories"]
    }

    for row in r2_doc["histories"]:
        history_id = str(row["history_id"])
        answer = contribution_answer(r2_events[history_id])
        if answer is not None:
            row["answers"][QUERY_ID] = answer

    for row in r1_doc["histories"]:
        history_id = str(row["history_id"])
        answer = contribution_answer(r1_events[history_id])
        if answer is not None:
            row["answers"][QUERY_ID] = answer

    for row in r0_doc["pairs"]:
        row["answers"][QUERY_ID] = NOT_IDENTIFIABLE

    r2_answers_path.write_bytes(canonical_bytes(r2_doc))
    r1_answers_path.write_bytes(canonical_bytes(r1_doc))
    r0_answers_path.write_bytes(canonical_bytes(r0_doc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
