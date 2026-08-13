#!/usr/bin/env python3
"""Hash H0 researcher outputs before evaluator-only fixtures are restored."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    args = parser.parse_args()

    files = {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(args.output_dir.glob("*.json"))
    }
    manifest = {"schema": "h0-pre-key-manifest-v0.1", "files": files}
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(
        json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
