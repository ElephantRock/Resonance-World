#!/usr/bin/env python3
"""Verify a fresh O2 materialization against the applicable frozen apparatus lock."""

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


def resolve_amended_lock(lock_path: Path, materialization_path: Path) -> Path:
    """Apply the frozen #126 D2 amendment when its v0.2 lock is present."""
    amended_lock = lock_path.with_name("apparatus-lock-v0.2.json")
    if lock_path.name != "apparatus-lock.json" or not amended_lock.exists():
        return lock_path

    from materialize_o2_amended_benchmarks import amend

    amend(materialization_path.parent, lock_path)
    return amended_lock


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lock", required=True, type=Path)
    parser.add_argument("--materialization", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    effective_lock = resolve_amended_lock(args.lock, args.materialization)
    lock = read_object(effective_lock)
    materialized = read_object(args.materialization)
    expected = lock["roots"]
    actual = materialized["roots"]
    checks = {}
    for name in ("plane_e", "plane_k", "r0", "r1", "meta"):
        checks[name] = (
            int(actual[name]["file_count"]) == int(expected[name]["file_count"])
            and str(actual[name]["manifest_root_sha256"])
            == str(expected[name]["manifest_root_sha256"])
        )
    result = {
        "schema": "o2-apparatus-lock-verification-v0.2",
        "effective_lock": effective_lock.name,
        "frozen_base_revision": lock["frozen_base_revision"],
        "generator_revision": lock["generator_revision"],
        "checks": checks,
        "all_match": all(checks.values()),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    if not result["all_match"]:
        raise SystemExit("fresh O2 materialization differs from the frozen apparatus lock")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
