#!/usr/bin/env python3
"""Materialize prospectively frozen H8 development and confirmatory fixtures."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

WORLD_BASE = "935e0463acc88f7f7756861d734eeba7b4efb034"
PROGRAM_BASE = "09da54404eca975c512137c70bb94d2a207e8178"
H5_RESULT_SHA256 = "c4d40f7df4a7f82d324e1cfa81c9a2d90a147a72f87b75e4bcee62a3c3d06029"
H6_RESULT_SHA256 = "fe24974c113f5960420d0c4c62902e471ad90ab7457c7b17e3472e479aed7691"
H7_RESULT_SHA256 = "67cab46e8ce2b33edf744e83743e6414f6adf2be1c642031770deca9197d5da5"
MODEL = "glm-5-turbo"
ENDPOINT = "https://api.z.ai/api/coding/paas/v4/chat/completions"
FAMILIES = (
    "temporal_supersession_under_condition",
    "multi_source_joint_constraint",
    "exception_scope_and_default",
    "contradiction_resolution_by_registered_reliability",
)
ARMS = ("raw_direct", "raw_shell", "raw_shell_roles", "history_ir_roles", "compiled_state_roles")
CONFIRMATORY_PER_FAMILY = 96
DEVELOPMENT_PER_FAMILY = 4
RECORD_BUDGET = 6
CALLS_PER_CELL = 3
PRIVATE_SENTINEL = "H8_PRIVATE_EVALUATOR_SENTINEL_F72C"


def canonical_bytes(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def token(namespace: str, prefix: str, *parts: object, n: int = 14) -> str:
    raw = "|".join([namespace, prefix, *[str(part) for part in parts]])
    return f"{prefix}-{hashlib.sha256(raw.encode()).hexdigest()[:n]}"


def bit(namespace: str, *parts: object) -> int:
    raw = "|".join([namespace, *[str(part) for part in parts]])
    return int(hashlib.sha256(raw.encode()).hexdigest(), 16) & 1


def record(*, record_id: str, kind: str, observed_at: int, source_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "record_id": record_id,
        "record_kind": kind,
        "observed_at": observed_at,
        "source_id": source_id,
        "source_class": "direct",
        "confidence": 1.0,
        "payload": payload,
    }


def common_unit(namespace: str, family: str, ordinal: int) -> dict[str, Any]:
    unit_id = f"{namespace}-u-{family[:4]}-{ordinal:03d}"
    organization_id = token(namespace, "org", family, ordinal)
    actions = sorted([token(namespace, "act", family, ordinal, "a"), token(namespace, "act", family, ordinal, "b")])
    notices = sorted([token(namespace, "notice", family, ordinal, "a"), token(namespace, "notice", family, ordinal, "b")])
    valid_position = bit(namespace, family, ordinal, "notice")
    authority_notices = [
        {"notice_id": notice, "world_verification": index == valid_position, "execution_capability": f"execute:{unit_id}"}
        for index, notice in enumerate(notices)
    ]
    members = {
        "call_1": token(namespace, "member", family, ordinal, 1),
        "call_2": token(namespace, "member", family, ordinal, 2),
        "call_3": token(namespace, "member", family, ordinal, 3),
    }
    return {
        "unit_id": unit_id,
        "family": family,
        "organization_id": organization_id,
        "actions": actions,
        "authority_notices": authority_notices,
        "members": members,
    }


def temporal_unit(namespace: str, ordinal: int) -> tuple[dict[str, Any], list[dict[str, Any]], str]:
    unit = common_unit(namespace, FAMILIES[0], ordinal)
    scopes = [token(namespace, "scope", ordinal, i) for i in range(2)]
    query_scope = scopes[bit(namespace, ordinal, "query-scope")]
    codes = [token(namespace, "code", ordinal, i) for i in range(4)]
    rows: list[dict[str, Any]] = []
    base = 100_000 + ordinal * 20
    latest_by_scope: dict[str, str] = {}
    for scope_index, scope in enumerate(scopes):
        first = codes[(scope_index + ordinal) % len(codes)]
        second = codes[(scope_index + ordinal + 1) % len(codes)]
        third = codes[(scope_index + ordinal + 2) % len(codes)]
        latest_by_scope[scope] = third
        for step, code in enumerate((first, second, third)):
            rows.append(
                record(
                    record_id=token(namespace, "evidence", ordinal, scope_index, step),
                    kind="conditional_observation",
                    observed_at=base + scope_index * 3 + step,
                    source_id=token(namespace, "source", ordinal, scope_index),
                    payload={"scope": scope, "decision_code": code},
                )
            )
    correct_code = latest_by_scope[query_scope]
    correct_position = ordinal % 2
    alternate = next(code for code in codes if code != correct_code)
    action_profiles = {
        unit["actions"][correct_position]: {"decision_code": correct_code},
        unit["actions"][1 - correct_position]: {"decision_code": alternate},
    }
    unit.update({
        "query": {"scope": query_scope},
        "action_profiles": action_profiles,
        "task_rule": (
            "For the queried scope, use the most recently observed decision_code for that same scope. "
            "Choose the offered action whose decision_code matches it. Observations for other scopes do not govern."
        ),
    })
    return unit, rows, unit["actions"][correct_position]


def joint_unit(namespace: str, ordinal: int) -> tuple[dict[str, Any], list[dict[str, Any]], str]:
    unit = common_unit(namespace, FAMILIES[1], ordinal)
    scopes = [token(namespace, "scope", ordinal, i) for i in range(2)]
    query_scope = scopes[bit(namespace, ordinal, "joint-query")]
    dimensions = [token(namespace, "dim", ordinal, i) for i in range(3)]
    rows: list[dict[str, Any]] = []
    base = 200_000 + ordinal * 20
    requirements: dict[str, dict[str, int]] = {}
    for scope_index, scope in enumerate(scopes):
        requirements[scope] = {}
        for dim_index, dimension in enumerate(dimensions):
            required_value = bit(namespace, ordinal, scope_index, dim_index, "required")
            requirements[scope][dimension] = required_value
            rows.append(
                record(
                    record_id=token(namespace, "evidence", ordinal, scope_index, dim_index),
                    kind="scope_requirement",
                    observed_at=base + scope_index * 3 + dim_index,
                    source_id=token(namespace, "source", ordinal, scope_index, dim_index),
                    payload={"scope": scope, "dimension": dimension, "required_value": required_value},
                )
            )
    correct_position = ordinal % 2
    correct_properties = requirements[query_scope]
    wrong_properties = dict(correct_properties)
    flip_dimension = dimensions[ordinal % len(dimensions)]
    wrong_properties[flip_dimension] = 1 - wrong_properties[flip_dimension]
    unit.update({
        "query": {"scope": query_scope},
        "action_profiles": {
            unit["actions"][correct_position]: {"properties": correct_properties},
            unit["actions"][1 - correct_position]: {"properties": wrong_properties},
        },
        "task_rule": (
            "All registered requirements for the queried scope must hold jointly. "
            "Choose the offered action whose properties satisfy every requirement for that scope."
        ),
    })
    return unit, rows, unit["actions"][correct_position]


def exception_unit(namespace: str, ordinal: int) -> tuple[dict[str, Any], list[dict[str, Any]], str]:
    unit = common_unit(namespace, FAMILIES[2], ordinal)
    scopes = [token(namespace, "scope", ordinal, i) for i in range(3)]
    modes = [token(namespace, "mode", ordinal, i) for i in range(5)]
    default_mode = modes[0]
    exception_modes = {scopes[0]: modes[1], scopes[1]: modes[2]}
    query_scope = scopes[ordinal % 3]
    base = 300_000 + ordinal * 20
    rows = [
        record(record_id=token(namespace, "evidence", ordinal, "old-default"), kind="default_rule", observed_at=base,
               source_id=token(namespace, "source", ordinal, "policy"), payload={"status": "superseded", "mode_code": modes[4]}),
        record(record_id=token(namespace, "evidence", ordinal, "default"), kind="default_rule", observed_at=base + 1,
               source_id=token(namespace, "source", ordinal, "policy"), payload={"status": "active", "mode_code": default_mode}),
        record(record_id=token(namespace, "evidence", ordinal, "exception-0"), kind="scope_exception", observed_at=base + 2,
               source_id=token(namespace, "source", ordinal, "exception-0"),
               payload={"status": "active", "scope": scopes[0], "mode_code": exception_modes[scopes[0]]}),
        record(record_id=token(namespace, "evidence", ordinal, "exception-1"), kind="scope_exception", observed_at=base + 3,
               source_id=token(namespace, "source", ordinal, "exception-1"),
               payload={"status": "active", "scope": scopes[1], "mode_code": exception_modes[scopes[1]]}),
        record(record_id=token(namespace, "evidence", ordinal, "expired"), kind="scope_exception", observed_at=base + 4,
               source_id=token(namespace, "source", ordinal, "expired"),
               payload={"status": "inactive", "scope": scopes[2], "mode_code": modes[3]}),
        record(record_id=token(namespace, "evidence", ordinal, "scope-note"), kind="scope_note", observed_at=base + 5,
               source_id=token(namespace, "source", ordinal, "audit"),
               payload={"scope": scopes[2], "note": "inactive exceptions do not override the active default"}),
    ]
    correct_mode = exception_modes.get(query_scope, default_mode)
    correct_position = ordinal % 2
    alternate = next(mode for mode in modes if mode != correct_mode)
    unit.update({
        "query": {"scope": query_scope},
        "action_profiles": {
            unit["actions"][correct_position]: {"mode_code": correct_mode},
            unit["actions"][1 - correct_position]: {"mode_code": alternate},
        },
        "task_rule": (
            "Use an active exception only when its scope exactly matches the queried scope. "
            "Otherwise use the active default. Superseded or inactive rules never govern."
        ),
    })
    return unit, rows, unit["actions"][correct_position]


def reliability_unit(namespace: str, ordinal: int) -> tuple[dict[str, Any], list[dict[str, Any]], str]:
    unit = common_unit(namespace, FAMILIES[3], ordinal)
    sources = [token(namespace, "source", ordinal, i) for i in range(2)]
    codes = [token(namespace, "code", ordinal, i) for i in range(4)]
    high_position = bit(namespace, ordinal, "reliable-source")
    rates = [(9, 10), (6, 10)]
    if high_position == 1:
        rates.reverse()
    current_codes = [codes[0], codes[1]]
    base = 400_000 + ordinal * 20
    rows = [
        record(record_id=token(namespace, "evidence", ordinal, "rate-0"), kind="source_reliability", observed_at=base,
               source_id=sources[0], payload={"successes": rates[0][0], "attempts": rates[0][1]}),
        record(record_id=token(namespace, "evidence", ordinal, "rate-1"), kind="source_reliability", observed_at=base + 1,
               source_id=sources[1], payload={"successes": rates[1][0], "attempts": rates[1][1]}),
        record(record_id=token(namespace, "evidence", ordinal, "old-0"), kind="historical_claim", observed_at=base + 2,
               source_id=sources[0], payload={"decision_code": codes[2]}),
        record(record_id=token(namespace, "evidence", ordinal, "old-1"), kind="historical_claim", observed_at=base + 3,
               source_id=sources[1], payload={"decision_code": codes[3]}),
        record(record_id=token(namespace, "evidence", ordinal, "current-0"), kind="current_claim", observed_at=base + 4,
               source_id=sources[0], payload={"decision_code": current_codes[0]}),
        record(record_id=token(namespace, "evidence", ordinal, "current-1"), kind="current_claim", observed_at=base + 5,
               source_id=sources[1], payload={"decision_code": current_codes[1]}),
    ]
    reliable_index = 0 if rates[0][0] / rates[0][1] > rates[1][0] / rates[1][1] else 1
    correct_code = current_codes[reliable_index]
    correct_position = ordinal % 2
    alternate = current_codes[1 - reliable_index]
    unit.update({
        "query": {"subject": token(namespace, "subject", ordinal)},
        "action_profiles": {
            unit["actions"][correct_position]: {"decision_code": correct_code},
            unit["actions"][1 - correct_position]: {"decision_code": alternate},
        },
        "task_rule": (
            "When the two current claims contradict, compute each source's registered reliability rate from "
            "successes/attempts and use the current decision_code reported by the uniquely more reliable source. "
            "Historical claims are not the current claim."
        ),
    })
    return unit, rows, unit["actions"][correct_position]


BUILDERS = {FAMILIES[0]: temporal_unit, FAMILIES[1]: joint_unit, FAMILIES[2]: exception_unit, FAMILIES[3]: reliability_unit}


def materialize_panel(namespace: str, per_family: int) -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]], list[dict[str, Any]], list[dict[str, Any]]]:
    units: list[dict[str, Any]] = []
    evidence: dict[str, list[dict[str, Any]]] = {}
    evaluator: list[dict[str, Any]] = []
    grants: list[dict[str, Any]] = []
    for family in FAMILIES:
        builder = BUILDERS[family]
        for ordinal in range(per_family):
            unit, rows, correct_action = builder(namespace, ordinal)
            if len(rows) != RECORD_BUDGET:
                raise AssertionError("H8 requires six canonical records per unit")
            rows = sorted(rows, key=lambda row: (int(row["observed_at"]), str(row["record_id"])))
            if len({row["record_id"] for row in rows}) != RECORD_BUDGET:
                raise AssertionError("duplicate H8 evidence id")
            valid_notice = next(notice["notice_id"] for notice in unit["authority_notices"] if notice["world_verification"])
            units.append(unit)
            evidence[unit["unit_id"]] = rows
            evaluator.append({"unit_id": unit["unit_id"], "family": family, "correct_action": correct_action, "valid_notice_id": valid_notice})
            grants.append({"organization_id": unit["organization_id"], "scenario_id": f"{unit['unit_id']}-h8",
                           "action": f"execute:{unit['unit_id']}", "notice_id": valid_notice})
    return units, evidence, evaluator, grants


def build() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    confirm_units, confirm_evidence, confirm_eval, confirm_grants = materialize_panel("h8-confirmatory", CONFIRMATORY_PER_FAMILY)
    dev_units, dev_evidence, _dev_eval, _dev_grants = materialize_panel("h8-development", DEVELOPMENT_PER_FAMILY)
    confirm_ids = {unit["unit_id"] for unit in confirm_units}
    dev_ids = {unit["unit_id"] for unit in dev_units}
    if confirm_ids & dev_ids:
        raise AssertionError("development/confirmatory identity overlap")
    confirm_record_ids = {row["record_id"] for rows in confirm_evidence.values() for row in rows}
    dev_record_ids = {row["record_id"] for rows in dev_evidence.values() for row in rows}
    if confirm_record_ids & dev_record_ids:
        raise AssertionError("development/confirmatory evidence overlap")
    plane_e = {
        "schema": "h8-plane-e-v0.1",
        "world_scientific_base": WORLD_BASE,
        "program_base": PROGRAM_BASE,
        "lineage_result_sha256": {"h5": H5_RESULT_SHA256, "h6": H6_RESULT_SHA256, "h7": H7_RESULT_SHA256},
        "generator": {"schema": "h8-generator-v0.1", "mode": "deterministic_frozen",
                      "development_namespace": "h8-development", "confirmatory_namespace": "h8-confirmatory",
                      "claim_ceiling": "G3_single_model"},
        "model_contract": {"provider": "zai-chat-completions", "model": MODEL, "endpoint": ENDPOINT,
                           "do_sample": True, "temperature": 0.8, "thinking": {"type": "disabled"},
                           "stream": False, "response_format": {"type": "json_object"}, "max_output_tokens": 128},
        "arms": list(ARMS), "families": list(FAMILIES), "record_budget": RECORD_BUDGET,
        "calls_per_cell": CALLS_PER_CELL, "units": confirm_units, "canonical_evidence_sets": confirm_evidence,
        "authority_grants": confirm_grants, "production_historical_substrate_enabled": False,
    }
    plane_k = {"schema": "h8-plane-k-v0.1", "private_evaluator_sentinel": PRIVATE_SENTINEL, "units": confirm_eval}
    development = {"schema": "h8-development-fixtures-v0.1", "generator": "h8-generator-v0.1",
                   "units": dev_units, "canonical_evidence_sets": dev_evidence,
                   "note": "structural development fixtures only; not part of the confirmatory provider panel"}
    by_id = {unit["unit_id"]: unit for unit in confirm_units}
    manifest = {
        "schema": "h8-fixture-manifest-v0.1", "confirmatory_unit_count": len(confirm_units),
        "development_unit_count": len(dev_units), "family_counts": {family: CONFIRMATORY_PER_FAMILY for family in FAMILIES},
        "arm_count": len(ARMS), "organization_cell_count": len(confirm_units) * len(ARMS),
        "logical_model_call_count": len(confirm_units) * len(ARMS) * CALLS_PER_CELL,
        "canonical_record_budget": RECORD_BUDGET,
        "correct_position_balance": {
            "first": sum(1 for row in confirm_eval if row["correct_action"] == by_id[row["unit_id"]]["actions"][0]),
            "second": sum(1 for row in confirm_eval if row["correct_action"] == by_id[row["unit_id"]]["actions"][1]),
        },
        "claim_ceiling": "G3_single_model",
    }
    return plane_e, plane_k, development, manifest


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--output-dir", type=Path, required=True); args = parser.parse_args()
    plane_e, plane_k, development, manifest = build()
    paths = {"plane_e": args.output_dir / "plane_e" / "evidence.json",
             "plane_k": args.output_dir / "plane_k" / "evaluator.json",
             "development": args.output_dir / "development" / "development.json",
             "manifest": args.output_dir / "meta" / "fixture-manifest.json"}
    for path in paths.values(): path.parent.mkdir(parents=True, exist_ok=True)
    e_bytes, k_bytes, d_bytes = canonical_bytes(plane_e), canonical_bytes(plane_k), canonical_bytes(development)
    manifest = {**manifest, "plane_e_sha256": hashlib.sha256(e_bytes).hexdigest(),
                "plane_k_sha256": hashlib.sha256(k_bytes).hexdigest(), "development_sha256": hashlib.sha256(d_bytes).hexdigest()}
    m_bytes = canonical_bytes(manifest)
    paths["plane_e"].write_bytes(e_bytes); paths["plane_k"].write_bytes(k_bytes); paths["development"].write_bytes(d_bytes); paths["manifest"].write_bytes(m_bytes)
    print(json.dumps({"plane_e_sha256": manifest["plane_e_sha256"], "plane_k_sha256": manifest["plane_k_sha256"],
                      "development_sha256": manifest["development_sha256"],
                      "fixture_manifest_sha256": hashlib.sha256(m_bytes).hexdigest(),
                      "confirmatory_unit_count": manifest["confirmatory_unit_count"],
                      "organization_cell_count": manifest["organization_cell_count"],
                      "logical_model_call_count": manifest["logical_model_call_count"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
