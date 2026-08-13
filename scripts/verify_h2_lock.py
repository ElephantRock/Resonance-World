#!/usr/bin/env python3
"""Verify the frozen H2 pre-outcome fixture lock."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

BASE = "839041f81ba9298f22544a939482f549ae6eefbb"
CG = "b896891108fd954869a8cd0423f6e8440ab0cdc0"
FILES = {
    "meta/fixture-manifest.json": "63487a40c373dab1f8b0958b8f2a46c863e107680c70d6e47d278f15770b93b9",
    "plane_e/evidence.json": "df4aa602b2e5d4b68e48d013f76acfa0b93d248806911c98b9ef1d1c6b1ac1c5",
    "plane_k/evaluator.json": "943b74b469d5b39de76b51234bc6af51430b482f2a536f74992519a94bfe05d9",
}


def obj(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain an object")
    return value


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--materialization", required=True, type=Path)
    p.add_argument("--corpus-root", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    a = p.parse_args()
    manifest = obj(a.materialization)
    fixture = obj(a.corpus_root / "meta/fixture-manifest.json")
    e = obj(a.corpus_root / "plane_e/evidence.json")
    k = obj(a.corpus_root / "plane_k/evaluator.json")
    checks = {
        "base_revision": manifest.get("base_revision") == BASE,
        "contextgraph_release_commit": manifest.get("contextgraph_release_commit") == CG,
        "file_hashes": dict(manifest.get("files", {})) == FILES,
        "unit_count": fixture.get("unit_count") == 48,
        "organization_count": fixture.get("organization_count") == 12,
        "slots_per_organization": fixture.get("slots_per_organization") == 4,
        "family_counts": fixture.get("family_counts") == {"f0": 16, "f1": 16, "f2": 16},
        "t50_family_balance": fixture.get("t50_replaced_by_family") == {"f0": 8, "f1": 8, "f2": 8},
        "turnover_counts": fixture.get("turnover_replaced_counts") == {"t0": 0, "t50": 24, "t100": 48},
        "result_limit": fixture.get("result_limit") == 2,
        "correct_action_balance": fixture.get("correct_action_balance") == {"lexicographic_first": 24, "lexicographic_second": 24},
        "record_counts": (
            fixture.get("evidence_record_count") == 208
            and fixture.get("future_record_count") == 48
            and fixture.get("collision_record_count") == 64
        ),
        "plane_units": len(e.get("units", [])) == 48 == len(k.get("units", [])),
        "plane_e_no_evaluator_labels": all(
            "family" not in row and "correct_action" not in row and "private_sentinel" not in row
            for row in e.get("units", [])
        ),
        "opaque_public_ids": all(
            str(row["unit_id"]).startswith("h2-")
            and str(row["organization_id"]).startswith("h2-")
            and str(row["slot_id"]).startswith("h2-")
            and str(row["predicate"]).startswith("h2-")
            and all(str(action).startswith("h2-") for action in row["actions"])
            for row in e.get("units", [])
        ),
    }
    result = {
        "schema": "h2-lock-verification-v0.1",
        "all_match": all(checks.values()),
        "checks": checks,
        "files": dict(manifest.get("files", {})),
    }
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n")
    return 0 if result["all_match"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
