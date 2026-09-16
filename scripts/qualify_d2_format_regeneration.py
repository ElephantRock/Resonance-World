#!/usr/bin/env python3
# ruff: noqa: I001,E501
"""CLI for #276 bounded format-regeneration structured-completion qualification."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from d2_format_regeneration_agent import preflight
from d2_format_regeneration_runtime import execute


def main() -> int:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--preflight", action="store_true")
    group.add_argument("--execute", action="store_true")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    payload = preflight() if args.preflight else execute()
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
