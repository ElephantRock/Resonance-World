#!/usr/bin/env python3
"""Credential-free verification of the prospectively frozen H8 apparatus."""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from h8_power import report as power_report
from h8_representation_core import ARMS, FORBIDDEN_IR_KEYS, canonical_bytes, compiled_state, digest, history_ir, prepare, strip_shell
from materialize_h8_fixtures import PRIVATE_SENTINEL, build


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def recursive_keys(value: object) -> set[str]:
    keys: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            keys.add(str(key)); keys.update(recursive_keys(child))
    elif isinstance(value, list):
        for child in value: keys.update(recursive_keys(child))
    return keys


def verify(fixture_dir: Path, output_dir: Path) -> dict[str, Any]:
    e_path = fixture_dir / "plane_e" / "evidence.json"
    k_path = fixture_dir / "plane_k" / "evaluator.json"
    d_path = fixture_dir / "development" / "development.json"
    m_path = fixture_dir / "meta" / "fixture-manifest.json"
    evidence, evaluator, development, manifest = load(e_path), load(k_path), load(d_path), load(m_path)

    expected_e, expected_k, expected_d, expected_m = build()
    if e_path.read_bytes() != canonical_bytes(expected_e): raise AssertionError("Plane E does not reproduce generator output")
    if k_path.read_bytes() != canonical_bytes(expected_k): raise AssertionError("Plane K does not reproduce generator output")
    if d_path.read_bytes() != canonical_bytes(expected_d): raise AssertionError("development fixture does not reproduce generator output")
    expected_m = {**expected_m, "plane_e_sha256": sha256_bytes(canonical_bytes(expected_e)),
                  "plane_k_sha256": sha256_bytes(canonical_bytes(expected_k)),
                  "development_sha256": sha256_bytes(canonical_bytes(expected_d))}
    if m_path.read_bytes() != canonical_bytes(expected_m): raise AssertionError("fixture manifest does not reproduce generator output")

    if manifest["confirmatory_unit_count"] != 384: raise AssertionError("H8 confirmatory unit count drift")
    if manifest["organization_cell_count"] != 1920: raise AssertionError("H8 cell count drift")
    if manifest["logical_model_call_count"] != 5760: raise AssertionError("H8 logical-call count drift")
    if manifest["correct_position_balance"] != {"first": 192, "second": 192}: raise AssertionError("H8 correct-action position balance drift")
    if evidence["production_historical_substrate_enabled"]: raise AssertionError("production Historical Substrate must remain OFF")

    confirm_ids = {unit["unit_id"] for unit in evidence["units"]}
    dev_ids = {unit["unit_id"] for unit in development["units"]}
    if confirm_ids & dev_ids: raise AssertionError("development/confirmatory unit overlap")
    confirm_record_ids = {row["record_id"] for rows in evidence["canonical_evidence_sets"].values() for row in rows}
    dev_record_ids = {row["record_id"] for rows in development["canonical_evidence_sets"].values() for row in rows}
    if confirm_record_ids & dev_record_ids: raise AssertionError("development/confirmatory evidence overlap")

    plan = prepare(evidence)
    if len(plan["cells"]) != 1920: raise AssertionError("H8 request-plan cell count drift")
    request_plan_bytes = canonical_bytes(plan)
    request_text = request_plan_bytes.decode()
    if PRIVATE_SENTINEL in request_text or '"correct_action"' in request_text:
        raise AssertionError("evaluator-private truth leaked into request plan")

    by_unit: dict[str, dict[str, dict[str, Any]]] = {}
    rotation_counts: Counter[int] = Counter(); arm_counts: Counter[str] = Counter(); audit_rows: list[dict[str, Any]] = []
    unit_map = {unit["unit_id"]: unit for unit in evidence["units"]}
    for cell in plan["cells"]:
        by_unit.setdefault(cell["unit_id"], {})[cell["arm"]] = cell
        if cell["arm"] == "raw_direct": rotation_counts[int(cell["arm_order_rotation"])] += 1
        arm_counts[cell["arm"]] += 1
        if cell["arm"] == "raw_direct":
            if cell["representation"] != cell["visible_raw_evidence"]: raise AssertionError("raw_direct representation drift")
            continue
        stripped = strip_shell(cell["representation"])
        if cell["arm"] in {"raw_shell", "raw_shell_roles"}:
            expected_payload = cell["visible_raw_evidence"]
        elif cell["arm"] == "history_ir_roles":
            expected_payload = history_ir(unit_map[cell["unit_id"]], cell["visible_raw_evidence"])
            forbidden = recursive_keys(stripped) & FORBIDDEN_IR_KEYS
            if forbidden: raise AssertionError(f"forbidden History IR keys: {sorted(forbidden)}")
        elif cell["arm"] == "compiled_state_roles":
            expected_payload = compiled_state(unit_map[cell["unit_id"]], cell["visible_raw_evidence"])
        else:
            raise AssertionError("unknown H8 arm")
        if stripped != expected_payload: raise AssertionError(f"shell changed payload in {cell['arm']}")
        audit_rows.append({"unit_id": cell["unit_id"], "arm": cell["arm"],
                           "source_sha256": digest(expected_payload), "stripped_sha256": digest(stripped),
                           "identity": digest(expected_payload) == digest(stripped)})

    if set(arm_counts) != set(ARMS) or any(arm_counts[arm] != 384 for arm in ARMS):
        raise AssertionError(f"H8 arm balance drift: {dict(arm_counts)}")
    if max(rotation_counts.values()) - min(rotation_counts.values()) > 1: raise AssertionError("arm-order rotation is not balanced")
    for unit_id, arms in by_unit.items():
        if set(arms) != set(ARMS): raise AssertionError(f"incomplete arm block: {unit_id}")
        if arms["raw_shell"]["representation"] != arms["raw_shell_roles"]["representation"]:
            raise AssertionError("B/C raw-shell representation mismatch")
        if strip_shell(arms["raw_shell"]["representation"]) != arms["raw_direct"]["representation"]:
            raise AssertionError("A/B shell identity invariant failed")

    p_report = power_report()
    if p_report["paired_n"] != 384 or not p_report["passes_target"]: raise AssertionError("H8 power contract drift")

    t0 = {
        "schema": "h8-t0-shell-audit-v0.1",
        "raw_shell_identity": "strip_shell(shell(raw_evidence)) == raw_evidence",
        "checked_shell_cells": len(audit_rows),
        "raw_shell_cells": sum(1 for row in audit_rows if row["arm"] in {"raw_shell", "raw_shell_roles"}),
        "history_ir_shell_cells": sum(1 for row in audit_rows if row["arm"] == "history_ir_roles"),
        "compiled_state_shell_cells": sum(1 for row in audit_rows if row["arm"] == "compiled_state_roles"),
        "all_identity_checks_passed": all(row["identity"] for row in audit_rows),
        "pairs": audit_rows,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    t0_path = output_dir / "h8-t0-shell-audit.json"; power_path = output_dir / "h8-power-report.json"
    t0_path.write_bytes(canonical_bytes(t0)); power_path.write_bytes(canonical_bytes(p_report))

    report = {
        "schema": "h8-lock-report-v0.1",
        "plane_e_sha256": sha256_bytes(e_path.read_bytes()), "plane_k_sha256": sha256_bytes(k_path.read_bytes()),
        "development_sha256": sha256_bytes(d_path.read_bytes()), "fixture_manifest_sha256": sha256_bytes(m_path.read_bytes()),
        "request_plan_sha256": sha256_bytes(request_plan_bytes), "t0_shell_audit_sha256": sha256_bytes(t0_path.read_bytes()),
        "power_report_sha256": sha256_bytes(power_path.read_bytes()),
        "power_implementation_sha256": sha256_bytes((Path(__file__).with_name("h8_power.py")).read_bytes()),
        "confirmatory_unit_count": 384, "organization_cell_count": 1920, "logical_model_call_count": 5760,
        "arm_counts": dict(arm_counts), "arm_rotation_counts": {str(key): value for key, value in sorted(rotation_counts.items())},
        "production_historical_substrate_enabled": False, "private_truth_absent_from_request_plan": True,
        "history_ir_forbidden_fields_absent": True, "development_confirmatory_disjoint": True,
        "power_target_passed": True, "t0_passed": True,
    }
    report_path = output_dir / "h8-lock-report.json"; report_path.write_bytes(canonical_bytes(report))
    return report


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--fixture-dir", type=Path, required=True); parser.add_argument("--output-dir", type=Path, required=True); args = parser.parse_args()
    value = verify(args.fixture_dir, args.output_dir); print(json.dumps(value, sort_keys=True)); return 0


if __name__ == "__main__":
    raise SystemExit(main())
