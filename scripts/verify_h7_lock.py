#!/usr/bin/env python3
"""Verify the prospective H7 fresh-fixture and selective-router lock."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from resonance_world.authority import AUTHORITY_VALIDATION_WORLD_REVISION
from resonance_world.historical_substrate import HISTORICAL_ACCESS_DEFAULT_ENABLED

EXPECTED_PLANE_E_SHA256 = "88372db1e7f283ddd0a2ee0427d51a41a9b9d36431e6a1b62c22f3dcea891de8"
EXPECTED_PLANE_K_SHA256 = "8a5093d4e4b25d61a195ce2a17b4567d3b6775ce927674751f32f1b246a1ead4"
EXPECTED_MANIFEST_SHA256 = "cd5f3a218cdb1f032c30be116e41442e74436d88a8f9b15e4ac58c4238045f64"
WORLD_BASE = "935e0463acc88f7f7756861d734eeba7b4efb034"
H6_SOURCE = "ff6bd5e030c3159829460e123f2fadd2e8087f93"
H6_RESULT_SHA256 = "fe24974c113f5960420d0c4c62902e471ad90ab7457c7b17e3472e479aed7691"
CG = "b896891108fd954869a8cd0423f6e8440ab0cdc0"
AUTHORITY_REVISION = "b2da04a1cd3ab5fb07dc781cd8b7bb93fab4b0d1"
PRIVATE_SENTINEL = "H7_PRIVATE_EVALUATOR_SENTINEL_91D4"
ARMS = ["no_state", "always_state", "selective_state"]
REPS = [f"r{i}" for i in range(1, 13)]


def sha(path: Path) -> str: return hashlib.sha256(path.read_bytes()).hexdigest()
def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict): raise ValueError("expected JSON object")
    return value


def main() -> int:
    p = argparse.ArgumentParser(); p.add_argument("--fixture-dir", type=Path, required=True); a = p.parse_args()
    e_path = a.fixture_dir / "plane_e" / "evidence.json"; k_path = a.fixture_dir / "plane_k" / "evaluator.json"; m_path = a.fixture_dir / "meta" / "fixture-manifest.json"
    hashes = {"plane_e": sha(e_path), "plane_k": sha(k_path), "manifest": sha(m_path)}
    if hashes != {"plane_e": EXPECTED_PLANE_E_SHA256, "plane_k": EXPECTED_PLANE_K_SHA256, "manifest": EXPECTED_MANIFEST_SHA256}:
        raise SystemExit(f"H7 fixture hash mismatch: {hashes!r}")
    e, k, m = load(e_path), load(k_path), load(m_path)
    if e.get("world_preregistered_base") != WORLD_BASE or e.get("h6_source_candidate") != H6_SOURCE or e.get("h6_result_sha256") != H6_RESULT_SHA256: raise SystemExit("H7 lineage mismatch")
    if e.get("contextgraph_release_commit") != CG: raise SystemExit("ContextGraph release mismatch")
    if e.get("arms") != ARMS or e.get("replicates") != REPS: raise SystemExit("H7 panel mismatch")
    contract = e.get("model_contract", {})
    for key, value in {"model": "glm-5-turbo", "do_sample": True, "temperature": 0.8, "thinking": {"type": "disabled"},
                       "stream": False, "response_format": {"type": "json_object"}, "max_output_tokens": 96}.items():
        if contract.get(key) != value: raise SystemExit(f"model contract mismatch: {key}")
    if m.get("unit_count") != 12 or m.get("organization_cell_count") != 432 or m.get("logical_model_call_count") != 1296 or m.get("canonical_record_budget") != 6: raise SystemExit("H7 count/budget mismatch")
    if m.get("family_counts") != {"cross_role_composition": 4, "authority_conflict": 4, "routine_transfer": 4}: raise SystemExit("family balance mismatch")
    if m.get("state_relevance_counts") != {"procedure_rate_comparison": 4, "none": 8}: raise SystemExit("state relevance balance mismatch")
    if m.get("correct_position_balance") != {"first": 6, "second": 6}: raise SystemExit("action balance mismatch")
    if PRIVATE_SENTINEL.encode() in e_path.read_bytes() or k.get("private_evaluator_sentinel") != PRIVATE_SENTINEL: raise SystemExit("private evaluator sentinel isolation failure")
    all_tokens = json.dumps(e, sort_keys=True)
    if "h5-u" in all_tokens or "h6-member-" in all_tokens: raise SystemExit("H7 fresh token namespace contaminated")
    units = {str(unit["unit_id"]): unit for unit in e["units"]}
    if set(units) != {f"h7-u{i:02d}" for i in range(12)}: raise SystemExit("fresh unit id mismatch")
    grants = {(g["organization_id"], g["scenario_id"]): g for g in e["authority_grants"]}
    if len(grants) != 12: raise SystemExit("authority grant count mismatch")
    member_ids: list[str] = []
    for uid, unit in units.items():
        rows = e["canonical_evidence_sets"][uid]
        if len(rows) != 6 or len({row["record_id"] for row in rows}) != 6: raise SystemExit("canonical record budget mismatch")
        if any(not str(row["observed_by"]).startswith("h7-") for row in rows): raise SystemExit("fresh record provenance mismatch")
        notices = [row for row in rows if row["record_kind"] == "authority_notice"]
        if len(notices) != 2 or sorted(bool(row["payload"]["world_verification"]) for row in notices) != [False, True]: raise SystemExit("authority notice mismatch")
        verified = [row for row in notices if row["payload"]["world_verification"]][0]
        grant = grants[(unit["organization_id"], f"{uid}-h7")]
        if grant["notice_id"] != verified["payload"]["notice_id"] or grant["action"] != f"execute:{uid}-h7": raise SystemExit("authority grant mismatch")
        for rep in REPS:
            values = list(unit["members"][rep].values())
            if len(values) != 3 or len(set(values)) != 3 or any(not str(value).startswith("h7-member-") for value in values): raise SystemExit("fresh member identity mismatch")
            member_ids.extend(values)
    if len(member_ids) != len(set(member_ids)): raise SystemExit("member identity reused")
    if HISTORICAL_ACCESS_DEFAULT_ENABLED: raise SystemExit("production Historical Substrate unexpectedly enabled")
    if AUTHORITY_VALIDATION_WORLD_REVISION != AUTHORITY_REVISION: raise SystemExit("authority primitive revision drift")
    report = {"schema": "h7-lock-verification-v0.1", "hashes": hashes, "unit_count": 12, "organization_cell_count": 432,
              "logical_model_call_count": 1296, "canonical_record_budget": 6, "production_historical_substrate_enabled": False,
              "authority_validation_world_revision": AUTHORITY_VALIDATION_WORLD_REVISION, "status": "pass"}
    encoded = (json.dumps(report, sort_keys=True, separators=(",", ":")) + "\n").encode()
    print(json.dumps({**report, "verification_sha256": hashlib.sha256(encoded).hexdigest()}, sort_keys=True)); return 0


if __name__ == "__main__": raise SystemExit(main())
