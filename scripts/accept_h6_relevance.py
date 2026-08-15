#!/usr/bin/env python3
"""Evaluate frozen H6 output and emit registered result/manifest/audit."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from h6_evaluator_core import FAIL, PASS, evaluate


def cb(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError("expected JSON object")
    return value


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plane-e", type=Path, required=True)
    parser.add_argument("--plane-k", type=Path, required=True)
    parser.add_argument("--fixture-manifest", type=Path, required=True)
    parser.add_argument("--live-output", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--candidate-head", required=True)
    args = parser.parse_args()
    evidence, evaluator = load(args.plane_e), load(args.plane_k)
    fixture_manifest, live = load(args.fixture_manifest), load(args.live_output)
    hashes = {"plane_e_sha256": sha(args.plane_e), "plane_k_sha256": sha(args.plane_k),
              "fixture_manifest_sha256": sha(args.fixture_manifest), "live_output_sha256": sha(args.live_output)}
    first = evaluate(evidence, evaluator, fixture_manifest, live, candidate=args.candidate_head, hashes=hashes)
    second = evaluate(evidence, evaluator, fixture_manifest, live, candidate=args.candidate_head, hashes=hashes)
    if cb(first) != cb(second):
        raise SystemExit("H6 deterministic evaluator self-reproduction failed")
    result, manifest, audit = first
    result["gates"]["gate_15_frozen_output_evaluator_reproducibility"] = True
    result["classification"] = PASS if all(result["gates"].values()) else FAIL
    result_bytes = cb(result)
    manifest = {**manifest, "authoritative_result_sha256": hashlib.sha256(result_bytes).hexdigest()}
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "result.json").write_bytes(result_bytes)
    (args.output_dir / "manifest.json").write_bytes(cb(manifest))
    (args.output_dir / "audit.json").write_bytes(cb(audit))
    print(json.dumps(result, sort_keys=True))
    return 0 if result["classification"] == PASS else 3


if __name__ == "__main__":
    raise SystemExit(main())
