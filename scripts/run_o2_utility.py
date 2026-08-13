#!/usr/bin/env python3
"""Produce frozen pre-key O2 R0/R1/R2 researcher outputs."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from resonance_contextgraph import EvidenceStore

from resonance_world.context_graph_adapter import to_evidence_claim
from resonance_world.o2_utility import analyze_events, analyze_r0, canonical_bytes


@dataclass(frozen=True, slots=True)
class _ObservedClaim:
    field_id: str
    subject: str
    predicate: str
    object: str
    observed_by: str
    source_id: str
    source_class: str
    observed_at: int
    confidence: float
    direct: bool


def encoded(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def decoded(value: str) -> Any:
    return json.loads(value)


def ingest_history(history: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Round-trip one admissible O2 history through the accepted evidence store."""
    if history.get("schema") != "o2-plane-e-history-v0.1":
        raise ValueError("unsupported O2 Plane-E history schema")
    history_id = str(history["history_id"])
    events = history.get("events")
    if not isinstance(events, list) or not events:
        raise ValueError("O2 Plane-E history requires events")

    store = EvidenceStore()
    for event in events:
        if not isinstance(event, dict):
            raise ValueError("O2 event must be an object")
        event_id = str(event["event_id"])
        ordinal = int(event["ordinal"])
        for field, value in sorted(event.items()):
            source_id = f"o2:{history_id}:{event_id}:{field}"
            observed = _ObservedClaim(
                field_id=history_id,
                subject=event_id,
                predicate=f"o2.event.{field}",
                object=encoded(value),
                observed_by="resonance-world:o2-observer",
                source_id=source_id,
                source_class="world-observation",
                observed_at=ordinal,
                confidence=1.0,
                direct=True,
            )
            store.ingest(to_evidence_claim(observed, delivery=0))

    claims = [asdict(claim) for claim in store.claims(scope_id=history_id)]
    reconstructed: dict[str, dict[str, Any]] = defaultdict(dict)
    for claim in claims:
        predicate = str(claim["predicate"])
        if not predicate.startswith("o2.event."):
            raise ValueError("unexpected O2 evidence predicate")
        field = predicate.removeprefix("o2.event.")
        reconstructed[str(claim["subject"])][field] = decoded(str(claim["object"]))

    rows = list(reconstructed.values())
    rows.sort(key=lambda row: (int(row["ordinal"]), str(row["event_id"])))
    return claims, rows


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
