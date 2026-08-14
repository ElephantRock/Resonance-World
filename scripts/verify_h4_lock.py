#!/usr/bin/env python3
"""Verify prospectively frozen H4 fixture and apparatus identities."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

EXPECTED = {
    "plane_e/evidence.json": "e2c0a4735c38abff803d2eab2ab872ed296ca01d48165a28f6f5541a2b28191b",
    "plane_k/evaluator.json": "4800f93d01fd0a88abbe62140aa6e73160f0102720d7c946ac0d4e4d3d2e82f2",
    "meta/fixture-manifest.json": "9758f65f18bfd63de98b11a8d7b6334bdd6b66f196e904668518bb9571fb69a2",
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture-dir", required=True, type=Path)
    args = parser.parse_args()
    actual = {}
    for relative_path, expected in EXPECTED.items():
        path = args.fixture_dir / relative_path
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != expected:
            raise SystemExit(
                f"H4 lock mismatch {relative_path}: expected {expected}, got {digest}"
            )
        actual[relative_path] = digest
    manifest = json.loads(
        (args.fixture_dir / "meta" / "fixture-manifest.json").read_text()
    )
    assert manifest["unit_count"] == 12
    assert manifest["logical_cell_count"] == 432
    assert manifest["canonical_record_count"] == 264
    assert manifest["legacy_record_count"] == 84
    assert manifest["correct_position_balance"] == {"first": 6, "second": 6}
    assert manifest["family_counts"] == {
        "provenance_temporal": 4,
        "temporal_latest": 4,
        "two_key_composition": 4,
    }
    print(
        json.dumps(
            {"schema": "h4-lock-verification-v0.1", "hashes": actual},
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
