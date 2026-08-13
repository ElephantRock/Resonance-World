#!/usr/bin/env python3
"""Run exact O2 evaluation after the pre-key researcher products are frozen."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

from resonance_world.o2_acceptance import CLASS_PASS, REPRO_CONTRACT, evaluate_o2
from resonance_world.o2_utility import canonical_bytes


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lock", required=True, type=Path)
    parser.add_argument("--lock-verification", required=True, type=Path)
    parser.add_argument("--corpus-root", required=True, type=Path)
    parser.add_argument("--research-output", required=True, type=Path)
    parser.add_argument("--pre-key-manifest", required=True, type=Path)
    parser.add_argument("--candidate-head", required=True)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()

    result, manifest = evaluate_o2(
        lock_path=args.lock,
        lock_verification_path=args.lock_verification,
        corpus_root=args.corpus_root,
        research_output=args.research_output,
        pre_key_manifest_path=args.pre_key_manifest,
        candidate_head=args.candidate_head,
        reproducibility_contract=REPRO_CONTRACT,
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    result_path = args.output_dir / "o2-result.json"
    result_path.write_bytes(canonical_bytes(result))
    manifest["authoritative_result_sha256"] = hashlib.sha256(result_path.read_bytes()).hexdigest()
    (args.output_dir / "o2-manifest.json").write_bytes(canonical_bytes(manifest))
    return 0 if result["classification"] == CLASS_PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())
