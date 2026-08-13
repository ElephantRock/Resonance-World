#!/usr/bin/env python3
"""Materialize the preregistered H2 turnover benchmark fixtures."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

BASE_REVISION = "839041f81ba9298f22544a939482f549ae6eefbb"
CONTEXTGRAPH_RELEASE_COMMIT = "b896891108fd954869a8cd0423f6e8440ab0cdc0"


def cb(v: Any) -> bytes:
    return (json.dumps(v, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode()


def opaque(*parts: object) -> str:
    raw = "|".join(str(x) for x in parts)
    return "h2-" + hashlib.sha256(("resonance-h2-v1|" + raw).encode()).hexdigest()[:24]


def rec(i: int, role: str, org: str, pred: str, action: str, at: int) -> dict[str, Any]:
    return {
        "record_id": opaque("record", i, role),
        "organization_id": org,
        "subject_id": opaque("subject", i, role),
        "predicate": pred,
        "support_action": action,
        "source_id": opaque("source", i, role),
        "source_class": "direct-observation",
        "observed_by": opaque("observer", i),
        "observed_at": at,
        "confidence": 1.0,
        "direct": True,
    }


def materialize() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    units_e: list[dict[str, Any]] = []
    units_k: list[dict[str, Any]] = []
    records: list[dict[str, Any]] = []
    family_counts = {"f0": 0, "f1": 0, "f2": 0}
    t50_family = {"f0": 0, "f1": 0, "f2": 0}

    for i in range(48):
        o, s = divmod(i, 4)
        family = ("f0", "f1", "f2")[i % 3]
        family_counts[family] += 1
        org = opaque("org", o)
        other_org = opaque("org-decoy", i)
        pred = opaque("predicate", i)
        other_pred = opaque("predicate-decoy", i)
        actions = sorted([opaque("action", i, 0), opaque("action", i, 1)])
        correct = actions[i % 2]
        wrong = actions[1 - (i % 2)]
        base = 1000 + i * 20
        cutoff = base + 9

        relevant = [
            rec(i, "relevant-0", org, pred, correct, base + 1),
            rec(i, "relevant-1", org, pred, correct, base + 2),
        ]
        collisions: list[dict[str, Any]] = []
        if family == "f1":
            collisions = [
                rec(i, "collision-0", other_org, pred, wrong, base + 3),
                rec(i, "collision-1", other_org, pred, wrong, base + 4),
            ]
        elif family == "f2":
            collisions = [
                rec(i, "collision-0", org, other_pred, wrong, base + 3),
                rec(i, "collision-1", org, other_pred, wrong, base + 4),
            ]
        future = rec(i, "future", org, pred, wrong, base + 11)
        unit_records = relevant + collisions + [future]
        records.extend(unit_records)

        pre = sorted(
            [r for r in unit_records if int(r["observed_at"]) <= cutoff],
            key=lambda r: (int(r["observed_at"]), str(r["record_id"])),
        )
        flat_ids = [r["record_id"] for r in pre[-2:]]
        uid = opaque("unit", i)
        replaced_t50 = (o + s) % 2 == 0
        if replaced_t50:
            t50_family[family] += 1
        replace = {"t0": False, "t50": replaced_t50, "t100": True}

        units_e.append({
            "unit_id": uid,
            "organization_id": org,
            "slot_id": opaque("slot", o, s),
            "predicate": pred,
            "decision_cutoff": cutoff,
            "result_limit": 2,
            "actions": actions,
            "query_id": opaque("query", i),
            "incumbent_id": opaque("incumbent", o, s),
            "local_continuity_records": relevant,
            "replaced": replace,
        })
        units_k.append({
            "unit_id": uid,
            "family": family,
            "correct_action": correct,
            "wrong_action": wrong,
            "expected_relevant_record_ids": [r["record_id"] for r in relevant],
            "expected_flat_record_ids": flat_ids,
            "expected_structured_record_ids": [r["record_id"] for r in relevant],
            "expected_no_history_action": actions[0],
            "future_record_id": future["record_id"],
            "private_sentinel": opaque("private", i),
        })

    ordered_records = sorted(records, key=lambda r: (int(r["observed_at"]), str(r["record_id"])))
    plane_e = {
        "schema": "h2-plane-e-v0.1",
        "base_revision": BASE_REVISION,
        "contextgraph_release_commit": CONTEXTGRAPH_RELEASE_COMMIT,
        "result_limit": 2,
        "turnover_levels": ["t0", "t50", "t100"],
        "history_arms": ["no_history", "flat_history", "structured_history"],
        "units": units_e,
        "evidence_records": ordered_records,
    }
    plane_k = {"schema": "h2-plane-k-v0.1", "units": units_k}
    manifest = {
        "schema": "h2-fixture-manifest-v0.1",
        "base_revision": BASE_REVISION,
        "unit_count": 48,
        "organization_count": 12,
        "slots_per_organization": 4,
        "family_counts": family_counts,
        "t50_replaced_by_family": t50_family,
        "turnover_replaced_counts": {"t0": 0, "t50": 24, "t100": 48},
        "result_limit": 2,
        "correct_action_balance": {"lexicographic_first": 24, "lexicographic_second": 24},
        "evidence_record_count": len(ordered_records),
        "future_record_count": 48,
        "collision_record_count": 64,
    }
    return plane_e, plane_k, manifest


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--output-root", required=True, type=Path)
    a = p.parse_args()
    e, k, m = materialize()
    outputs = {
        "plane_e/evidence.json": e,
        "plane_k/evaluator.json": k,
        "meta/fixture-manifest.json": m,
    }
    hashes: dict[str, str] = {}
    for rel, value in outputs.items():
        path = a.output_root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = cb(value)
        path.write_bytes(payload)
        hashes[rel] = hashlib.sha256(payload).hexdigest()
    mm = {
        "schema": "h2-materialization-manifest-v0.1",
        "base_revision": BASE_REVISION,
        "contextgraph_release_commit": CONTEXTGRAPH_RELEASE_COMMIT,
        "files": hashes,
    }
    (a.output_root / "materialization-manifest.json").write_bytes(cb(mm))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
