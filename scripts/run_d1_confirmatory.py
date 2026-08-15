#!/usr/bin/env python3
"""Execute a prospectively frozen deterministic D1 capability-reproduction panel."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from d1_capability_core import canonical_bytes, run_field_pair


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--candidate-head", required=True)
    args = parser.parse_args()

    plan = load(args.plan)
    if plan["schema"] != "d1-confirmatory-plan-v0.1":
        raise ValueError("D1 plan schema drift")
    seeds = [int(seed) for seed in plan["confirmatory_pair_seeds"]]
    if len(seeds) != 36 or len(set(seeds)) != 36:
        raise ValueError("D1 requires 36 unique confirmatory Field-pair seeds")

    rows = [run_field_pair(seed, dict(plan["config"])) for seed in seeds]
    output = {
        "schema": "d1-confirmatory-output-v0.1",
        "candidate_head": args.candidate_head,
        "plan_sha256": sha(args.plan),
        "pair_count": len(rows),
        "rows": rows,
        "execution_integrity": {
            "all_source_destination_identities_disjoint": all(
                row["source_destination_identity_disjoint"] for row in rows
            ),
            "all_forbidden_private_export_keys_absent": all(
                not row["forbidden_private_export_keys_found"] for row in rows
            ),
            "oracle_product_eligible": False,
            "production_historical_substrate_enabled": False,
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(canonical_bytes(output))
    print(
        json.dumps(
            {
                "pair_count": len(rows),
                "plan_sha256": output["plan_sha256"],
                "output_sha256": sha(args.output),
                "integrity": output["execution_integrity"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
