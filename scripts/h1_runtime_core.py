"""Deterministic H1 bounded-history controller/runtime helpers."""
# ruff: noqa: E501
from __future__ import annotations

import hashlib
import json
from collections import Counter
from typing import Any

from resonance_contextgraph import EvidenceClaim, EvidenceStore
from resonance_world.historical_substrate import (
    HISTORICAL_FORBIDDEN_CONSUMERS,
    HistoricalAccessForbidden,
    require_historical_consumer,
)

CG = "b896891108fd954869a8cd0423f6e8440ab0cdc0"
REV = "h1-fixed-support-counter-v0.1"
NI = "not_observationally_identifiable"


def cb(v: Any) -> bytes:
    return (json.dumps(v, sort_keys=True, separators=(",", ":")) + "\n").encode()


def did(prefix: str, v: Any) -> str:
    return prefix + hashlib.sha256(cb(v)).hexdigest()[:24]


def ordered(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(rows, key=lambda r: (int(r["observed_at"]), str(r["record_id"])))


def cg_records(source: list[dict[str, Any]]) -> list[dict[str, Any]]:
    store = EvidenceStore()
    for row in source:
        store.ingest(EvidenceClaim(
            claim_id=did("h1-claim-", row["record_id"]), scope_id=str(row["organization_id"]),
            subject=str(row["record_id"]), predicate=str(row["predicate"]),
            object=json.dumps(row, sort_keys=True, separators=(",", ":")),
            observed_by=str(row["observed_by"]), source_id=str(row["source_id"]),
            source_class=str(row["source_class"]), observed_at=int(row["observed_at"]),
            confidence=float(row["confidence"]), direct=bool(row["direct"])))
    out = []
    for org in sorted({str(r["organization_id"]) for r in source}):
        for claim in store.claims(scope_id=org):
            out.append({"claim_id": claim.claim_id, **json.loads(claim.object)})
    return ordered(out)


def norm(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{k: v for k, v in r.items() if k != "claim_id"} for r in rows]


def decision(unit: dict[str, Any], input_id: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    actions = sorted(str(a) for a in unit["actions"])
    counts = Counter(str(r["support_action"]) for r in rows)
    if set(counts) - set(actions):
        raise ValueError("unsupported action")
    chosen = sorted(actions, key=lambda a: (-counts[a], a))[0]
    base = {"schema": "h1-controller-decision-v0.1", "controller_revision": REV,
            "unit_id": unit["unit_id"], "actions": actions, "history_input_id": input_id,
            "record_ids": [r["record_id"] for r in rows], "chosen_action": chosen}
    return {**base, "decision_id": did("h1-decision-", base)}


def path(unit: dict[str, Any], hist: dict[str, Any], input_id: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    dec = decision(unit, input_id, rows)
    accepted = dec["chosen_action"] in unit["actions"]
    con = {"schema": "h1-world-consequence-v0.1", "unit_id": unit["unit_id"],
           "decision_id": dec["decision_id"], "chosen_action": dec["chosen_action"],
           "action_accepted": accepted, "executed": accepted}
    con["consequence_id"] = did("h1-consequence-", con)
    ack = {"schema": "h1-execution-ack-v0.1", "decision_id": dec["decision_id"],
           "consequence_id": con["consequence_id"], "chosen_action": dec["chosen_action"],
           "executed": con["executed"]}
    ack["ack_id"] = did("h1-ack-", ack)
    return {"history": hist, "normalized_records": rows, "decision": dec,
            "consequence": con, "execution_acknowledgement": ack}


def flat(source: list[dict[str, Any]], unit: dict[str, Any]) -> dict[str, Any]:
    rows = ordered([r for r in source if int(r["observed_at"]) <= int(unit["decision_cutoff"])])
    rows = rows[-int(unit["result_limit"]):]
    base = {"schema": "h1-flat-history-window-v0.1", "unit_id": unit["unit_id"],
            "decision_cutoff": unit["decision_cutoff"], "result_limit": unit["result_limit"],
            "records": rows}
    return {**base, "window_id": did("h1-flat-window-", base)}


def sentinels() -> list[dict[str, str]]:
    out = []
    for consumer in sorted(HISTORICAL_FORBIDDEN_CONSUMERS):
        try:
            require_historical_consumer(consumer)
        except HistoricalAccessForbidden as exc:
            out.append({"consumer": consumer, "status": exc.code})
        else:
            out.append({"consumer": consumer, "status": "unexpectedly_allowed"})
    return out
