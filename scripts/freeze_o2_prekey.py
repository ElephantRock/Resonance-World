#!/usr/bin/env python3
"""Cryptographically freeze O2 researcher outputs before evaluator Plane K appears."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

AUTHORITATIVE_PREKEY = (
    "contextgraph-evidence.json",
    "r0-researcher-answers.json",
    "r1-researcher-answers.json",
    "r2-event-ledger.json",
    "r2-researcher-answers.json",
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    args = parser.parse_args()

    files = {}
    for name in AUTHORITATIVE_PREKEY:
        path = args.output_dir / name
        if not path.is_file():
            raise ValueError(f"missing authoritative pre-key product: {name}")
        files[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest = {
        "schema": "o2-pre-key-freeze-v0.1",
        "files": files,
    }
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(
        json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
