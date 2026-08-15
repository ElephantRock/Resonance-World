#!/usr/bin/env python3
"""Verify the prospective H5 fixture and apparatus lock."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from resonance_world.authority import AUTHORITY_VALIDATION_WORLD_REVISION
from resonance_world.historical_substrate import HISTORICAL_ACCESS_DEFAULT_ENABLED

EXPECTED_PLANE_E_SHA256 = "173b3e8a6461c38eb3bad6e3dd7ed6b38807f512b5ff64bfc0ead4f19ed4cbb9"
EXPECTED_PLANE_K_SHA256 = "f59804690f06782133881d648b0bcd1cb94c818a6e2747d8d2754b0a45dddb19"
EXPECTED_MANIFEST_SHA256 = "b86ee29bc9fa1c2fee5e7c03abbb8ea13590467e3efc8c675d67756f0f3784dd"
EXPECTED_WORLD_BASE = "935e0463acc88f7f7756861d734eeba7b4efb034"
EXPECTED_CONTEXTGRAPH = "b896891108fd954869a8cd0423f6e8440ab0cdc0"
EXPECTED_AUTHORITY_REVISION = "b2da04a1cd3ab5fb07dc781cd8b7bb93fab4b0d1"
PRIVATE_SENTINEL = "H5_PRIVATE_EVALUATOR_SENTINEL_41C7"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError("expected JSON object")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture-dir", type=Path, required=True)
    args = parser.parse_args()
    e_path = args.fixture_dir / "plane_e" / "evidence.json"
    k_path = args.fixture_dir / "plane_k" / "evaluator.json"
    m_path = args.fixture_dir / "meta" / "fixture-manifest.json"
    hashes = {"plane_e": sha(e_path), "plane_k": sha(k_path), "manifest": sha(m_path)}
    expected = {
        "plane_e": EXPECTED_PLANE_E_SHA256,
        "plane_k": EXPECTED_PLANE_K_SHA256,
        "manifest": EXPECTED_MANIFEST_SHA256,
    }
    if hashes != expected:
        raise SystemExit(f"H5 fixture hash mismatch: {hashes!r}")
    plane_e, plane_k, manifest = load(e_path), load(k_path), load(m_path)
    if plane_e["world_preregistered_base"] != EXPECTED_WORLD_BASE:
        raise SystemExit("World base mismatch")
    if plane_e["contextgraph_release_commit"] != EXPECTED_CONTEXTGRAPH:
        raise SystemExit("ContextGraph release mismatch")
    contract = plane_e["model_contract"]
    required_contract = {
        "model": "glm-5-turbo",
        "do_sample": True,
        "temperature": 0.8,
        "thinking": {"type": "disabled"},
        "stream": False,
        "response_format": {"type": "json_object"},
        "max_output_tokens": 96,
    }
    for key, value in required_contract.items():
        if contract.get(key) != value:
            raise SystemExit(f"model contract mismatch: {key}")
    if manifest["unit_count"] != 12 or manifest["organization_cell_count"] != 432:
        raise SystemExit("H5 count mismatch")
    if manifest["logical_model_call_count"] != 1296 or manifest["canonical_record_budget"] != 6:
        raise SystemExit("H5 budget mismatch")
    if manifest["family_counts"] != {
        "authority_conflict": 4,
        "cross_role_composition": 4,
        "routine_transfer": 4,
    }:
        raise SystemExit("family balance mismatch")
    if manifest["correct_position_balance"] != {"first": 6, "second": 6}:
        raise SystemExit("action balance mismatch")
    if PRIVATE_SENTINEL.encode() in e_path.read_bytes():
        raise SystemExit("private evaluator sentinel leaked into Plane E")
    if plane_k.get("private_evaluator_sentinel") != PRIVATE_SENTINEL:
        raise SystemExit("Plane K sentinel mismatch")
    units = {str(unit["unit_id"]): unit for unit in plane_e["units"]}
    grants = {(g["organization_id"], g["scenario_id"]): g for g in plane_e["authority_grants"]}
    if len(grants) != 36:
        raise SystemExit("authority grant count mismatch")
    for key, rows in plane_e["canonical_evidence_sets"].items():
        unit_id, generation = key.split(":")
        unit = units[unit_id]
        if len(rows) != 6 or len({row["record_id"] for row in rows}) != 6:
            raise SystemExit(f"canonical record budget mismatch: {key}")
        if any(row["organization_id"] != unit["organization_id"] or row["predicate"] != unit["predicate"] for row in rows):
            raise SystemExit(f"scope mismatch: {key}")
        if any(row["responsibility"] not in {"case", "steward"} for row in rows):
            raise SystemExit(f"responsibility mismatch: {key}")
        notices = [row for row in rows if row["record_kind"] == "authority_notice"]
        if len(notices) != 2 or sorted(bool(row["payload"]["world_verification"]) for row in notices) != [False, True]:
            raise SystemExit(f"authority notice mismatch: {key}")
        grant = grants[(unit["organization_id"], f"{unit_id}-{generation}")]
        verified = [row for row in notices if row["payload"]["world_verification"]]
        if grant["notice_id"] != verified[0]["payload"]["notice_id"]:
            raise SystemExit(f"authority grant/public verification mismatch: {key}")
        if grant["action"] != f"execute:{unit_id}-{generation}":
            raise SystemExit(f"authority capability mismatch: {key}")
        if unit["family"] == "routine_transfer":
            observed = sum(
                1 for row in rows
                if row["record_kind"] == "procedure_outcome" and row["payload"].get("status") == "observed"
            )
            expected_observed = {"g1": 0, "g2": 1, "g3": 2}[generation]
            if observed != expected_observed:
                raise SystemExit(f"routine temporal availability mismatch: {key}")
    member_ids: list[str] = []
    for unit in plane_e["units"]:
        for replicate in plane_e["replicates"]:
            for generation in plane_e["generations"]:
                values = list(unit["members"][replicate][generation].values())
                if len(values) != 3 or len(set(values)) != 3:
                    raise SystemExit("within-cell member identity collision")
                member_ids.extend(values)
    if len(member_ids) != len(set(member_ids)):
        raise SystemExit("turnover identity reused across H5 generations/replicates")
    if HISTORICAL_ACCESS_DEFAULT_ENABLED:
        raise SystemExit("production Historical Substrate unexpectedly enabled")
    if AUTHORITY_VALIDATION_WORLD_REVISION != EXPECTED_AUTHORITY_REVISION:
        raise SystemExit("authority primitive provenance drift")
    report = {
        "schema": "h5-lock-verification-v0.1",
        "hashes": hashes,
        "unit_count": 12,
        "organization_cell_count": 432,
        "logical_model_call_count": 1296,
        "canonical_record_budget": 6,
        "production_historical_substrate_enabled": False,
        "authority_validation_world_revision": AUTHORITY_VALIDATION_WORLD_REVISION,
        "status": "pass",
    }
    encoded = (json.dumps(report, sort_keys=True, separators=(",", ":")) + "\n").encode()
    print(json.dumps({**report, "verification_sha256": hashlib.sha256(encoded).hexdigest()}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
