#!/usr/bin/env python3
"""Verify the frozen H1 pre-outcome apparatus lock."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lock", required=True, type=Path)
    parser.add_argument("--materialization", required=True, type=Path)
    parser.add_argument("--corpus-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    lock = read_object(args.lock)
    manifest = read_object(args.materialization)
    fixture = read_object(args.corpus_root / "meta/fixture-manifest.json")
    plane_e = read_object(args.corpus_root / "plane_e/evidence.json")
    plane_k = read_object(args.corpus_root / "plane_k/evaluator.json")

    expected_files = dict(lock["files"])
    actual_files = dict(manifest["files"])
    checks = {
        "base_revision": manifest.get("base_revision") == lock.get("base_revision"),
        "contextgraph_release_commit": (
            manifest.get("contextgraph_release_commit")
            == lock.get("contextgraph_release_commit")
        ),
        "file_hashes": actual_files == expected_files,
        "unit_count": fixture.get("unit_count") == 30,
        "family_counts": fixture.get("family_counts")
        == {"f0": 10, "f1": 10, "f2": 10},
        "result_limit": fixture.get("result_limit") == 2,
        "correct_action_balance": fixture.get("correct_action_balance")
        == {"lexicographic_first": 15, "lexicographic_second": 15},
        "evidence_record_count": fixture.get("evidence_record_count") == 130,
        "future_record_count": fixture.get("future_record_count") == 30,
        "collision_record_count": fixture.get("collision_record_count") == 40,
        "plane_e_units": len(plane_e.get("units", [])) == 30,
        "plane_k_units": len(plane_k.get("units", [])) == 30,
        "plane_e_no_evaluator_labels": all(
            "family" not in row
            and "correct_action" not in row
            and "expected_flat_action" not in row
            for row in plane_e.get("units", [])
        ),
        "opaque_public_ids": all(
            str(row["unit_id"]).startswith("h1-")
            and str(row["organization_id"]).startswith("h1-")
            and str(row["predicate"]).startswith("h1-")
            and all(str(action).startswith("h1-") for action in row["actions"])
            for row in plane_e.get("units", [])
        ),
    }
    result = {
        "schema": "h1-lock-verification-v0.1",
        "all_match": all(checks.values()),
        "checks": checks,
        "files": actual_files,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    return 0 if result["all_match"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
