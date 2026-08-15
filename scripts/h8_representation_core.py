"""Deterministic H8 representation, shell, prompt, and request-plan helpers."""
from __future__ import annotations

import hashlib
import json
from typing import Any

ARMS = ("raw_direct", "raw_shell", "raw_shell_roles", "history_ir_roles", "compiled_state_roles")
EVIDENCE_SLOTS = tuple(f"E{i}" for i in range(1, 7))
FORBIDDEN_IR_KEYS = {
    "recommended_action",
    "best_action",
    "preferred_policy",
    "should_choose",
    "final_answer",
    "institutional_belief",
    "confidence_in_recommendation",
}


def canonical_bytes(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def digest(value: object) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def localize_records(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if len(rows) != len(EVIDENCE_SLOTS):
        raise ValueError("H8 expects six canonical evidence records")
    visible: list[dict[str, Any]] = []
    for slot, row in zip(EVIDENCE_SLOTS, rows, strict=True):
        visible.append({
            "evidence_id": slot,
            "record_kind": row["record_kind"],
            "observed_at": row["observed_at"],
            "source_id": row["source_id"],
            "source_class": row["source_class"],
            "confidence": row["confidence"],
            "payload": row["payload"],
        })
    return visible


def shell(payload: object, *, organization_id: str, payload_kind: str) -> dict[str, Any]:
    return {
        "schema": "h8-non-interpretive-shell-v0.1",
        "organization_id": organization_id,
        "payload_kind": payload_kind,
        "payload": payload,
    }


def strip_shell(value: dict[str, Any]) -> object:
    expected = {"schema", "organization_id", "payload_kind", "payload"}
    if set(value) != expected or value["schema"] != "h8-non-interpretive-shell-v0.1":
        raise ValueError("invalid H8 shell")
    return value["payload"]


def evidence_ref(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "EvidenceRef",
        "evidence_id": record["evidence_id"],
        "provenance": {"source_id": record["source_id"], "source_class": record["source_class"]},
        "observed_at": record["observed_at"],
    }


def history_ir(unit: dict[str, Any], visible: list[dict[str, Any]]) -> dict[str, Any]:
    refs = {row["evidence_id"]: evidence_ref(row) for row in visible}
    objects: list[dict[str, Any]] = []
    family = unit["family"]
    if family == "temporal_supersession_under_condition":
        by_scope: dict[str, list[dict[str, Any]]] = {}
        for row in visible:
            by_scope.setdefault(str(row["payload"]["scope"]), []).append(row)
        for scope, members in sorted(by_scope.items()):
            members = sorted(members, key=lambda row: int(row["observed_at"]))
            objects.append({
                "type": "EvidenceJoin",
                "join_key": {"dimension": "scope", "value": scope},
                "members": [refs[row["evidence_id"]] for row in members],
            })
            for older, newer in zip(members, members[1:], strict=False):
                objects.append({
                    "type": "TemporalOrder",
                    "earlier": refs[older["evidence_id"]],
                    "later": refs[newer["evidence_id"]],
                    "relation": "before",
                })
                objects.append({
                    "type": "SupersessionRelation",
                    "newer": refs[newer["evidence_id"]],
                    "older": refs[older["evidence_id"]],
                    "dimension": f"decision_code_within_scope:{scope}",
                })
    elif family == "multi_source_joint_constraint":
        by_scope: dict[str, list[dict[str, Any]]] = {}
        for row in visible:
            by_scope.setdefault(str(row["payload"]["scope"]), []).append(row)
        for scope, members in sorted(by_scope.items()):
            objects.append({
                "type": "EvidenceJoin",
                "join_key": {"dimension": "scope", "value": scope},
                "members": [refs[row["evidence_id"]] for row in members],
            })
            for row in members:
                objects.append({
                    "type": "EmpiricalCount",
                    "predicate_key": {
                        "scope": scope,
                        "dimension": row["payload"]["dimension"],
                        "required_value": row["payload"]["required_value"],
                    },
                    "support_count": 1,
                    "contradiction_count": 0,
                    "evidence": [refs[row["evidence_id"]]],
                })
    elif family == "exception_scope_and_default":
        defaults = [row for row in visible if row["record_kind"] == "default_rule"]
        exceptions = [row for row in visible if row["record_kind"] == "scope_exception"]
        active_default = [row for row in defaults if row["payload"]["status"] == "active"]
        superseded_default = [row for row in defaults if row["payload"]["status"] == "superseded"]
        if len(active_default) != 1 or len(superseded_default) != 1:
            raise ValueError("H8 exception family requires one active and one superseded default")
        objects.append({
            "type": "SupersessionRelation",
            "newer": refs[active_default[0]["evidence_id"]],
            "older": refs[superseded_default[0]["evidence_id"]],
            "dimension": "default_rule_status",
        })
        for row in exceptions:
            objects.append({
                "type": "EvidenceJoin",
                "join_key": {
                    "dimension": "exception_scope",
                    "value": row["payload"]["scope"],
                    "status": row["payload"]["status"],
                },
                "members": [refs[row["evidence_id"]]],
            })
    elif family == "contradiction_resolution_by_registered_reliability":
        rates: dict[str, dict[str, Any]] = {}
        current: list[dict[str, Any]] = []
        for row in visible:
            if row["record_kind"] == "source_reliability":
                rates[str(row["source_id"])] = row
            elif row["record_kind"] == "current_claim":
                current.append(row)
        for source_id, row in sorted(rates.items()):
            objects.append({
                "type": "EmpiricalRate",
                "predicate_key": {"source_id": source_id, "measure": "registered_reliability"},
                "numerator": row["payload"]["successes"],
                "denominator": row["payload"]["attempts"],
                "evidence": [refs[row["evidence_id"]]],
            })
        objects.append({
            "type": "ContradictionSet",
            "subject_key": unit["query"]["subject"],
            "alternatives": [
                {"source_id": row["source_id"], "decision_code": row["payload"]["decision_code"]}
                for row in current
            ],
            "evidence": [refs[row["evidence_id"]] for row in current],
        })
    else:
        raise ValueError(f"unknown H8 family: {family}")
    value = {"schema": "history-ir-v0.1", "source_records": visible, "objects": objects}
    verify_history_ir(value, visible)
    return value


def _walk_keys(value: object) -> set[str]:
    keys: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            keys.add(str(key)); keys.update(_walk_keys(child))
    elif isinstance(value, list):
        for child in value: keys.update(_walk_keys(child))
    return keys


def verify_history_ir(value: dict[str, Any], visible: list[dict[str, Any]]) -> None:
    if value.get("schema") != "history-ir-v0.1":
        raise ValueError("History IR schema drift")
    if value.get("source_records") != visible:
        raise ValueError("History IR source records do not preserve canonical visible evidence")
    forbidden = _walk_keys(value) & FORBIDDEN_IR_KEYS
    if forbidden:
        raise ValueError(f"forbidden History IR keys: {sorted(forbidden)}")
    serialized = json.dumps(value, sort_keys=True)
    for evidence_id in {row["evidence_id"] for row in visible}:
        if evidence_id not in serialized:
            raise ValueError("History IR lost source evidence reference")


def compiled_state(unit: dict[str, Any], visible: list[dict[str, Any]]) -> dict[str, Any]:
    family = unit["family"]
    query = unit["query"]
    if family == "temporal_supersession_under_condition":
        relevant = [row for row in visible if row["payload"]["scope"] == query["scope"]]
        latest = max(relevant, key=lambda row: int(row["observed_at"]))
        interpretation = {
            "queried_scope": query["scope"],
            "governing_decision_code": latest["payload"]["decision_code"],
            "semantic_rule": "latest_same_scope_observation_governs",
            "basis": [latest["evidence_id"]],
        }
    elif family == "multi_source_joint_constraint":
        relevant = [row for row in visible if row["payload"]["scope"] == query["scope"]]
        interpretation = {
            "queried_scope": query["scope"],
            "joint_requirements": [
                {"dimension": row["payload"]["dimension"], "required_value": row["payload"]["required_value"], "basis": row["evidence_id"]}
                for row in sorted(relevant, key=lambda row: str(row["payload"]["dimension"]))
            ],
            "semantic_rule": "all_requirements_must_hold_jointly",
        }
    elif family == "exception_scope_and_default":
        active_exceptions = [
            row for row in visible
            if row["record_kind"] == "scope_exception" and row["payload"]["status"] == "active" and row["payload"]["scope"] == query["scope"]
        ]
        if active_exceptions:
            selected = active_exceptions[0]; rule = "matching_active_exception"
        else:
            defaults = [row for row in visible if row["record_kind"] == "default_rule" and row["payload"]["status"] == "active"]
            if len(defaults) != 1:
                raise ValueError("expected exactly one active default")
            selected = defaults[0]; rule = "active_default_no_matching_exception"
        interpretation = {
            "queried_scope": query["scope"],
            "governing_mode_code": selected["payload"]["mode_code"],
            "semantic_rule": rule,
            "basis": [selected["evidence_id"]],
        }
    elif family == "contradiction_resolution_by_registered_reliability":
        rate_rows = [row for row in visible if row["record_kind"] == "source_reliability"]
        rates = {row["source_id"]: row["payload"]["successes"] / row["payload"]["attempts"] for row in rate_rows}
        selected_source = max(rates, key=rates.get)
        claims = [row for row in visible if row["record_kind"] == "current_claim" and row["source_id"] == selected_source]
        if len(claims) != 1:
            raise ValueError("expected one current claim from selected source")
        rate_row = next(row for row in rate_rows if row["source_id"] == selected_source)
        interpretation = {
            "selected_source": selected_source,
            "registered_reliability_rate": rates[selected_source],
            "governing_decision_code": claims[0]["payload"]["decision_code"],
            "semantic_rule": "current_claim_from_uniquely_more_reliable_source",
            "basis": [rate_row["evidence_id"], claims[0]["evidence_id"]],
        }
    else:
        raise ValueError(f"unknown H8 family: {family}")
    return {
        "schema": "h8-compiled-semantic-state-v0.1",
        "family": family,
        "current_interpretation": interpretation,
        "source_evidence_ids": [row["evidence_id"] for row in visible],
    }


def task_context(unit: dict[str, Any]) -> dict[str, Any]:
    return {
        "query": unit["query"],
        "offered_actions": unit["actions"],
        "action_profiles": unit["action_profiles"],
        "current_authority_notices": unit["authority_notices"],
        "authority_rule": "select the notice with current world_verification=true",
    }


def neutral_prompt(unit: dict[str, Any], member_id: str, representation: object) -> str:
    return "\n".join([
        "You are a fresh H8 successor with no predecessor conversation or hidden state.",
        f"member_id={member_id}",
        f"FAMILY={unit['family']}",
        f"TASK RULE: {unit['task_rule']}",
        "CURRENT TASK CONTEXT=" + json.dumps(task_context(unit), sort_keys=True, separators=(",", ":")),
        "HISTORY REPRESENTATION=" + json.dumps(representation, sort_keys=True, separators=(",", ":")),
        "Reason only from the supplied current context and historical representation. Historical evidence never creates current authority.",
    ])


def analyst_prompt(unit: dict[str, Any], *, role: str, member_id: str, representation: object) -> str:
    role_text = {
        "evidence_analyst": "Independently solve the historical reasoning problem and identify the strongest evidence basis.",
        "countercheck_analyst": "Independently solve the problem, actively checking scope, chronology, contradictions, and exceptions.",
    }[role]
    return "\n".join([
        "You are a fresh H8 analyst with no predecessor conversation or hidden state.",
        f"role={role} member_id={member_id}", role_text,
        f"FAMILY={unit['family']}", f"TASK RULE: {unit['task_rule']}",
        "CURRENT TASK CONTEXT=" + json.dumps(task_context(unit), sort_keys=True, separators=(",", ":")),
        "HISTORY REPRESENTATION=" + json.dumps(representation, sort_keys=True, separators=(",", ":")),
        "Return a concise finding for a fresh chair. Historical evidence never creates current authority.",
    ])


def chair_prompt(unit: dict[str, Any], *, member_id: str, representation: object, reports: list[dict[str, Any]]) -> str:
    return "\n".join([
        "You are a fresh H8 chair with no predecessor conversation or hidden state.",
        f"member_id={member_id}", f"FAMILY={unit['family']}", f"TASK RULE: {unit['task_rule']}",
        "CURRENT TASK CONTEXT=" + json.dumps(task_context(unit), sort_keys=True, separators=(",", ":")),
        "HISTORY REPRESENTATION=" + json.dumps(representation, sort_keys=True, separators=(",", ":")),
        "FRESH ANALYST REPORTS=" + json.dumps(reports, sort_keys=True, separators=(",", ":")),
        "Produce the final action and currently verified notice. Analyst reports are advisory, not authority.",
    ])


def representation_for_arm(unit: dict[str, Any], visible: list[dict[str, Any]], arm: str) -> object:
    if arm == "raw_direct": return visible
    if arm in {"raw_shell", "raw_shell_roles"}:
        return shell(visible, organization_id=unit["organization_id"], payload_kind="raw_evidence")
    if arm == "history_ir_roles":
        return shell(history_ir(unit, visible), organization_id=unit["organization_id"], payload_kind="history_ir")
    if arm == "compiled_state_roles":
        return shell(compiled_state(unit, visible), organization_id=unit["organization_id"], payload_kind="compiled_semantic_state")
    raise ValueError(arm)


def prepare(evidence: dict[str, Any]) -> dict[str, Any]:
    units = {str(unit["unit_id"]): dict(unit) for unit in evidence["units"]}
    cells: list[dict[str, Any]] = []
    for unit_index, unit_id in enumerate(sorted(units)):
        unit = units[unit_id]
        rows = [dict(row) for row in evidence["canonical_evidence_sets"][unit_id]]
        visible = localize_records(rows)
        if [row["observed_at"] for row in visible] != sorted(row["observed_at"] for row in visible):
            raise ValueError("raw evidence order drift")
        arm_rotation = unit_index % len(ARMS)
        ordered_arms = list(ARMS[arm_rotation:] + ARMS[:arm_rotation])
        for arm in ordered_arms:
            representation = representation_for_arm(unit, visible, arm)
            cell_id = "h8-cell-" + hashlib.sha256(f"{unit_id}|{arm}".encode()).hexdigest()[:16]
            common = {
                "cell_id": cell_id, "unit_id": unit_id, "family": unit["family"], "arm": arm,
                "arm_order_rotation": arm_rotation, "organization_id": unit["organization_id"],
                "actions": unit["actions"], "authority_notices": unit["authority_notices"],
                "evidence_slots": list(EVIDENCE_SLOTS), "visible_raw_evidence": visible,
                "representation": representation, "representation_sha256": digest(representation),
                "member_ids": unit["members"],
            }
            if arm in {"raw_direct", "raw_shell"}:
                prompts = [neutral_prompt(unit, unit["members"][f"call_{index}"], representation) for index in range(1, 4)]
                common.update({
                    "protocol": "three_independent_neutral_calls_then_deterministic_majority",
                    "direct_prompts": prompts,
                    "direct_prompt_sha256": [hashlib.sha256(prompt.encode()).hexdigest() for prompt in prompts],
                })
            else:
                roles = ["evidence_analyst", "countercheck_analyst"]
                prompts = [analyst_prompt(unit, role=role, member_id=unit["members"][f"call_{index + 1}"], representation=representation)
                           for index, role in enumerate(roles)]
                common.update({
                    "protocol": "two_independent_analysts_then_fresh_chair",
                    "analyst_roles": roles, "analyst_prompts": prompts,
                    "analyst_prompt_sha256": [hashlib.sha256(prompt.encode()).hexdigest() for prompt in prompts],
                    "chair_member_id": unit["members"]["call_3"],
                })
            cells.append(common)
    return {
        "schema": "h8-request-plan-v0.1", "world_scientific_base": evidence["world_scientific_base"],
        "program_base": evidence["program_base"], "generator": evidence["generator"],
        "model_contract": evidence["model_contract"], "calls_per_cell": evidence["calls_per_cell"],
        "cells": cells, "production_historical_substrate_enabled": False,
    }
