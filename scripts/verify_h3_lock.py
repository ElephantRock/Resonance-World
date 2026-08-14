#!/usr/bin/env python3
"""Verify the frozen H3 pre-outcome fixture lock."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

BASE = "230f468a234bebaddbf2245f58327a84f959c00f"
CG = "b896891108fd954869a8cd0423f6e8440ab0cdc0"
FILES = {
    "meta/fixture-manifest.json": "871db12f6360d3ecd1ca778a51d537db270e2930029ed7ee72808a4cbb3dc0f2",
    "plane_e/evidence.json": "9dd3d4604ec25c890531b7fda9d5ba84aad1433c83ae383dacf4d8f20b66194f",
    "plane_k/evaluator.json": "65cad15fb3d8b8c5a51bf74f67e6cf1b3d38a357b0842d3f9d3c9869f054ccd3",
}


def obj(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain an object")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--materialization", required=True, type=Path)
    parser.add_argument("--corpus-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    materialization = obj(args.materialization)
    fixture = obj(args.corpus_root / "meta/fixture-manifest.json")
    plane_e = obj(args.corpus_root / "plane_e/evidence.json")
    plane_k = obj(args.corpus_root / "plane_k/evaluator.json")
    checks = {
        "base_revision": materialization.get("base_revision") == BASE,
        "contextgraph_release_commit": materialization.get("contextgraph_release_commit") == CG,
        "file_hashes": dict(materialization.get("files", {})) == FILES,
        "unit_count": fixture.get("unit_count") == 24,
        "organization_count": fixture.get("organization_count") == 8,
        "slots_per_organization": fixture.get("slots_per_organization") == 3,
        "generation_count": fixture.get("generation_count") == 5,
        "cell_count": fixture.get("cell_count") == 480,
        "family_counts": fixture.get("family_counts") == {"f1": 8, "f2": 8, "f3": 8},
        "complete_turnover": fixture.get("complete_turnover_per_generation")
        == {"g1": 24, "g2": 24, "g3": 24, "g4": 24, "g5": 24},
        "result_limit": fixture.get("result_limit") == 7,
        "default_balance": fixture.get("default_action_balance")
        == {"lexicographic_first": 12, "lexicographic_second": 12},
        "correct_balance": fixture.get("correct_action_balance")
        == {"lexicographic_first": 12, "lexicographic_second": 12},
        "record_counts": (
            fixture.get("legacy_record_count") == 48
            and fixture.get("collision_record_count") == 840
            and fixture.get("lesson_record_count") == 120
            and fixture.get("evidence_record_count") == 1008
        ),
        "plane_units": len(plane_e.get("units", [])) == 24 == len(plane_k.get("units", [])),
        "plane_e_no_evaluator_labels": all(
            "family" not in row and "correct_action" not in row and "private_sentinel" not in row
            for row in plane_e.get("units", [])
        ),
        "opaque_public_ids": all(
            str(row["unit_id"]).startswith("h3-")
            and str(row["organization_id"]).startswith("h3-")
            and str(row["slot_id"]).startswith("h3-")
            and str(row["predicate"]).startswith("h3-")
            and str(row["founder_id"]).startswith("h3-")
            and all(str(action).startswith("h3-") for action in row["actions"])
            and all(str(member).startswith("h3-") for member in row["members"].values())
            for row in plane_e.get("units", [])
        ),
    }
    result = {
        "schema": "h3-lock-verification-v0.1",
        "all_match": all(checks.values()),
        "checks": checks,
        "files": dict(materialization.get("files", {})),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n")
    return 0 if result["all_match"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
