#!/usr/bin/env python3
"""Evaluate one frozen H8 provider artifact and emit canonical classification files."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from h8_evaluator_core import evaluate
from h8_representation_core import canonical_bytes


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plane-e", type=Path, required=True)
    parser.add_argument("--plane-k", type=Path, required=True)
    parser.add_argument("--fixture-manifest", type=Path, required=True)
    parser.add_argument("--lock-report", type=Path, required=True)
    parser.add_argument("--live-output", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--candidate-head", required=True)
    args = parser.parse_args()

    result, audit = evaluate(
        evidence=load(args.plane_e),
        evaluator=load(args.plane_k),
        fixture_manifest=load(args.fixture_manifest),
        lock_report=load(args.lock_report),
        live=load(args.live_output),
        candidate_head=args.candidate_head,
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    result_path = args.output_dir / "result.json"
    audit_path = args.output_dir / "audit.json"
    result_path.write_bytes(canonical_bytes(result))
    audit_path.write_bytes(canonical_bytes(audit))
    manifest = {
        "schema": "h8-evaluation-manifest-v0.1",
        "candidate_head": args.candidate_head,
        "input_sha256": {
            "plane_e": sha256_file(args.plane_e),
            "plane_k": sha256_file(args.plane_k),
            "fixture_manifest": sha256_file(args.fixture_manifest),
            "lock_report": sha256_file(args.lock_report),
            "live_output": sha256_file(args.live_output),
        },
        "output_sha256": {"result": sha256_file(result_path), "audit": sha256_file(audit_path)},
        "classification": result["classification"],
    }
    manifest_path = args.output_dir / "manifest.json"
    manifest_path.write_bytes(canonical_bytes(manifest))
    print(json.dumps({
        "classification": result["classification"],
        "result_sha256": sha256_file(result_path),
        "audit_sha256": sha256_file(audit_path),
        "manifest_sha256": sha256_file(manifest_path),
        "gates": result["gates"],
    }, sort_keys=True))
    return 0 if result["classification"].endswith("_classified") else 3


if __name__ == "__main__":
    raise SystemExit(main())
