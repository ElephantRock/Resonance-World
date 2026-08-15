#!/usr/bin/env python3
"""Materialize the prospective D1b replication plan from the frozen D1 plan."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

PARENT_D1_PLAN_SHA256 = "8223d441f8399d89901ecd7f704d8744c571a8035c7ebdc94150435f92ba8858"
D1_CONFIRMATORY_SEEDS = set(range(30_000, 30_036))
D1_CALIBRATION_SEEDS = set(range(10_000, 10_064))
D1B_SEEDS = tuple(range(50_000, 50_036))


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--parent-d1-plan", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    if file_sha256(args.parent_d1_plan) != PARENT_D1_PLAN_SHA256:
        raise ValueError("parent D1 plan identity drift")
    parent = load(args.parent_d1_plan)
    if parent["schema"] != "d1-confirmatory-plan-v0.1":
        raise ValueError("parent D1 plan schema drift")
    if int(parent["confirmatory_pair_count"]) != 36:
        raise ValueError("parent D1 pair-count drift")
    if float(parent["statistical_contract"]["P2"]["noninferiority_margin"]) != 0.05931396484374999:
        raise ValueError("parent D1 NI margin drift")
    if parent["statistical_contract"]["fixed_sequence"] != [
        "P0_source_development",
        "P1_destination_acquisition",
        "P2_reproduction_fidelity",
    ]:
        raise ValueError("parent D1 fixed-sequence drift")

    if set(D1B_SEEDS) & D1_CONFIRMATORY_SEEDS:
        raise ValueError("D1b seeds overlap D1 confirmatory seeds")
    if set(D1B_SEEDS) & D1_CALIBRATION_SEEDS:
        raise ValueError("D1b seeds overlap D1-0 calibration seeds")

    skill_balance = {"skill-a": 0, "skill-b": 0, "skill-c": 0}
    for seed in D1B_SEEDS:
        skill_balance[f"skill-{chr(ord('a') + seed % 3)}"] += 1
    if skill_balance != {"skill-a": 12, "skill-b": 12, "skill-c": 12}:
        raise ValueError("D1b skill-alias balance drift")

    plan = json.loads(json.dumps(parent))
    plan["status"] = "prospective_replication_locked_no_outcomes"
    plan["confirmatory_pair_seeds"] = list(D1B_SEEDS)
    plan["confirmatory_pair_count"] = 36
    plan["skill_alias_balance"] = skill_balance
    plan["development_confirmatory_seed_disjoint"] = True
    plan["d1_d1b_confirmatory_seed_disjoint"] = True
    plan["parent_d1_plan_sha256"] = PARENT_D1_PLAN_SHA256
    plan["replication_of_candidate"] = "46010232f9b73e481eaa6de4b60cc721f4ad2273"
    plan["replication_study"] = "D1b"
    plan["sample_size"]["n_rationale"] = (
        "exact D1 n=36 retained prospectively for fresh replication; three skill aliases remain balanced 12/12/12"
    )
    plan["replication_requirement"] = (
        "If D1b reproduces D1-S3 on this fresh cohort, D1+D1b become eligible for independent acceptance review toward internally_replicated status; the experiment cannot self-promote."
    )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    plan_path = args.output_dir / "d1b-confirmatory-plan.json"
    plan_path.write_bytes(canonical_bytes(plan))
    lock = {
        "schema": "d1b-lock-report-v0.1",
        "parent_d1_plan_sha256": PARENT_D1_PLAN_SHA256,
        "plan_sha256": file_sha256(plan_path),
        "confirmatory_pair_count": 36,
        "confirmatory_seed_min": min(D1B_SEEDS),
        "confirmatory_seed_max": max(D1B_SEEDS),
        "skill_alias_balance": skill_balance,
        "d1_calibration_seed_disjoint": True,
        "d1_confirmatory_seed_disjoint": True,
        "p2_noninferiority_margin": plan["statistical_contract"]["P2"]["noninferiority_margin"],
        "p2_margin_type": plan["statistical_contract"]["P2"]["margin_type"],
        "scientific_apparatus_unchanged_from_d1": True,
        "confirmatory_execution_authorized": False,
        "production_historical_substrate_enabled": False,
    }
    lock_path = args.output_dir / "d1b-lock-report.json"
    lock_path.write_bytes(canonical_bytes(lock))
    print(json.dumps(lock, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
