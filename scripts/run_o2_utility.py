#!/usr/bin/env python3
"""Produce frozen pre-key O2 R0/R1/R2 researcher outputs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from resonance_world.o2_utility import analyze_events, analyze_r0, canonical_bytes, ingest_history


def read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def load_histories(directory: Path, schema: str) -> list[dict[str, Any]]:
    histories = [read_object(path) for path in sorted(directory.glob("*.json"))]
    if len(histories) != 80:
        raise ValueError(f"O2 requires 80 histories, found {len(histories)}")
    if any(row.get("schema") != schema for row in histories):
        raise ValueError(f"unsupported O2 schema in {directory}")
    ids = [str(row["history_id"]) for row in histories]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate O2 history identity")
    return sorted(histories, key=lambda row: str(row["history_id"]))


def analyze_r0_pairs(directory: Path) -> list[dict[str, Any]]:
    rows = [read_object(path) for path in sorted(directory.glob("*.json"))]
    if len(rows) != 80:
        raise ValueError(f"O2 requires 80 R0 inputs, found {len(rows)}")
    by_pair: dict[str, list[bytes]] = {}
    for row in rows:
        if row.get("schema") != "o2-r0-endpoint-v0.1":
            raise ValueError("unsupported O2 R0 schema")
        pair_id = str(row["pair_id"])
        by_pair.setdefault(pair_id, []).append(canonical_bytes(row))
    if len(by_pair) != 40:
        raise ValueError(f"O2 requires 40 R0 collision pairs, found {len(by_pair)}")
    for pair_id, payloads in by_pair.items():
        if len(payloads) != 2 or payloads[0] != payloads[1]:
            raise ValueError(f"R0 aggregate collision broken for {pair_id}")
    return [analyze_r0(pair_id) for pair_id in sorted(by_pair)]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plane-e-dir", required=True, type=Path)
    parser.add_argument("--r0-dir", required=True, type=Path)
    parser.add_argument("--r1-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()

    plane_e = load_histories(args.plane_e_dir, "o2-plane-e-history-v0.1")
    flat_histories = load_histories(args.r1_dir, "o2-r1-flat-log-v0.1")
    flat_by_id = {str(row["history_id"]): row for row in flat_histories}

    all_claims: list[dict[str, Any]] = []
    ledgers: list[dict[str, Any]] = []
    r2_answers: list[dict[str, Any]] = []
    r1_answers: list[dict[str, Any]] = []

    for history in plane_e:
        history_id = str(history["history_id"])
        pair_id = str(history["pair_id"])
        claims, reconstructed = ingest_history(history)
        all_claims.extend(claims)
        ledgers.append({"history_id": history_id, "pair_id": pair_id, "events": reconstructed})
        r2_answers.append(
            {"history_id": history_id, "pair_id": pair_id, **analyze_events(reconstructed)}
        )

        flat = flat_by_id.get(history_id)
        if flat is None or str(flat.get("pair_id")) != pair_id:
            raise ValueError(f"R1 identity mismatch for {history_id}")
        events = flat.get("events")
        if not isinstance(events, list):
            raise ValueError(f"R1 history {history_id} has invalid events")
        r1_answers.append(
            {"history_id": history_id, "pair_id": pair_id, **analyze_events(events)}
        )

    if len({str(row["claim_id"]) for row in all_claims}) != len(all_claims):
        raise ValueError("O2 ContextGraph claim identities are not unique")
    if len({str(row["source_id"]) for row in all_claims}) != len(all_claims):
        raise ValueError("O2 ContextGraph source identities are not unique")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    products = {
        "contextgraph-evidence.json": {
            "schema": "o2-contextgraph-evidence-v0.1",
            "claims": all_claims,
        },
        "r2-event-ledger.json": {"schema": "o2-r2-event-ledger-v0.1", "histories": ledgers},
        "r2-researcher-answers.json": {
            "schema": "o2-r2-researcher-answers-v0.1",
            "histories": r2_answers,
        },
        "r1-researcher-answers.json": {
            "schema": "o2-r1-researcher-answers-v0.1",
            "histories": r1_answers,
        },
        "r0-researcher-answers.json": {
            "schema": "o2-r0-researcher-answers-v0.1",
            "pairs": analyze_r0_pairs(args.r0_dir),
        },
    }
    for filename, value in products.items():
        (args.output_dir / filename).write_bytes(canonical_bytes(value))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
