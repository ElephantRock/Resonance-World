#!/usr/bin/env python3
"""Evaluate one frozen D1 confirmatory output under the preregistered contract."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from d1_evaluator_core import canonical_bytes, evaluate


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--lock", type=Path, required=True)
    parser.add_argument("--confirmatory-output", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--candidate-head", required=True)
    args = parser.parse_args()

    result, audit, manifest = evaluate(
        plan_path=args.plan,
        lock_path=args.lock,
        output_path=args.confirmatory_output,
        candidate_head=args.candidate_head,
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "result": args.output_dir / "result.json",
        "audit": args.output_dir / "audit.json",
        "manifest": args.output_dir / "manifest.json",
    }
    paths["result"].write_bytes(canonical_bytes(result))
    paths["audit"].write_bytes(canonical_bytes(audit))
    manifest["output_sha256"] = {
        "result": hashlib.sha256(paths["result"].read_bytes()).hexdigest(),
        "audit": hashlib.sha256(paths["audit"].read_bytes()).hexdigest(),
    }
    paths["manifest"].write_bytes(canonical_bytes(manifest))
    print(
        json.dumps(
            {
                "classification_code": result["classification_code"],
                "classification": result["classification"],
                "P0": result["P0_source_development"],
                "P1": result["P1_destination_acquisition"],
                "P2": result["P2_reproduction_fidelity"],
                "result_sha256": hashlib.sha256(paths["result"].read_bytes()).hexdigest(),
                "audit_sha256": hashlib.sha256(paths["audit"].read_bytes()).hexdigest(),
                "manifest_sha256": hashlib.sha256(paths["manifest"].read_bytes()).hexdigest(),
            },
            sort_keys=True,
        )
    )
    return 2 if result["classification_code"] == "D1-S4" else 0


if __name__ == "__main__":
    raise SystemExit(main())
