#!/usr/bin/env python3
"""Evaluate frozen H5 output and emit the registered result/manifest/audit."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from h5_evaluator_core import PASS, evaluate


def cb(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict): raise ValueError("expected JSON object")
    return value


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--plane-e", type=Path, required=True); p.add_argument("--plane-k", type=Path, required=True)
    p.add_argument("--fixture-manifest", type=Path, required=True); p.add_argument("--live-output", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True); p.add_argument("--candidate-head", required=True)
    a = p.parse_args()
    e, k, fm, live = load(a.plane_e), load(a.plane_k), load(a.fixture_manifest), load(a.live_output)
    hashes = {"plane_e_sha256": sha(a.plane_e), "plane_k_sha256": sha(a.plane_k), "fixture_manifest_sha256": sha(a.fixture_manifest), "live_output_sha256": sha(a.live_output)}
    first = evaluate(e, k, fm, live, candidate=a.candidate_head, hashes=hashes)
    second = evaluate(e, k, fm, live, candidate=a.candidate_head, hashes=hashes)
    if cb(first) != cb(second): raise SystemExit("H5 deterministic evaluator self-reproduction failed")
    result, manifest, audit = first
    result["gates"]["gate_15_frozen_output_evaluator_reproducibility"] = True
    result["classification"] = PASS if all(result["gates"].values()) else "historical_substrate_institutional_mediation_failed"
    result_bytes = cb(result); manifest = {**manifest, "authoritative_result_sha256": hashlib.sha256(result_bytes).hexdigest()}
    a.output_dir.mkdir(parents=True, exist_ok=True)
    (a.output_dir / "result.json").write_bytes(result_bytes); (a.output_dir / "manifest.json").write_bytes(cb(manifest)); (a.output_dir / "audit.json").write_bytes(cb(audit))
    print(json.dumps(result, sort_keys=True))
    return 0 if result["classification"] == PASS else 3


if __name__ == "__main__": raise SystemExit(main())
