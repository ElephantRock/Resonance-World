"""Shared deterministic H6 relevance-gating apparatus helpers."""
from __future__ import annotations

import hashlib
import json
from typing import Any

from h1_runtime_core import CG, cg_records, did, norm, sentinels
from resonance_world.historical_substrate import bounded_historical_evidence

ARMS = ("static_no_state", "persistent_no_state", "static_with_state", "persistent_with_state")
EVIDENCE_SLOTS = tuple(f"E{i}" for i in range(1, 7))


def task_rule(family: str) -> str:
    authority = (
        "For the execution notice, ignore historical authority labels and select the notice whose "
        "payload.world_verification is true for the current execution capability."
    )
    if family in {"cross_role_composition", "authority_conflict"}:
        return (
            "Find decision_signal records named alpha and beta. XOR their integer payload.bit values. "
            "XOR 0 selects the lexicographically first offered action; XOR 1 selects the second. " + authority
        )
    if family == "routine_transfer":
        return (
            "Two decision_observation records recommend opposite offered actions and identify their opaque "
            "provenance_class. Among observed procedure_outcome records, compute successes/attempts for each "
            "provenance and trust the unique higher-rate provenance. Choose the action recommended by that provenance. "
            + authority
        )
    raise ValueError(family)


def slot_map(rows: list[dict[str, Any]]) -> dict[str, str]:
    if len(rows) != 6:
        raise ValueError("H6 requires exactly six canonical records")
    return {str(row["record_id"]): EVIDENCE_SLOTS[i] for i, row in enumerate(rows)}


def visible_record(row: dict[str, Any], slots: dict[str, str]) -> dict[str, Any]:
    return {
        "evidence_slot": slots[str(row["record_id"])],
        "organization_id": row["organization_id"], "predicate": row["predicate"],
        "observed_at": row["observed_at"], "responsibility": row["responsibility"],
        "record_kind": row["record_kind"], "payload": row["payload"],
    }


def institutional_state(family: str, rows: list[dict[str, Any]], slots: dict[str, str]) -> dict[str, Any]:
    if family != "routine_transfer":
        return {"schema": "h6-institutional-state-v0.1", "status": "not_applicable"}
    observed = [row for row in rows if row["record_kind"] == "procedure_outcome" and row["payload"].get("status") == "observed"]
    if len(observed) != 2:
        raise ValueError("H6 routine_transfer requires the frozen H5 g3 two-observation state")
    scored = sorted((int(row["payload"]["successes"]) / int(row["payload"]["attempts"]),
                     str(row["payload"]["provenance_class"]), slots[str(row["record_id"])]) for row in observed)
    if scored[0][0] == scored[1][0]:
        raise ValueError("H6 frozen routine state must have a unique winner")
    loser, winner = scored
    return {"schema": "h6-institutional-state-v0.1", "status": "compiled", "trusted_provenance": winner[1],
            "winning_rate": winner[0], "losing_rate": loser[0], "source_evidence_slots": sorted([loser[2], winner[2]])}


def candidate_notices(rows: list[dict[str, Any]]) -> list[str]:
    values = [str(row["payload"]["notice_id"]) for row in rows if row["record_kind"] == "authority_notice"]
    if len(values) != 2 or len(set(values)) != 2:
        raise ValueError("H6 requires exactly two candidate notices")
    return sorted(values)


def partition(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    case = [row for row in rows if row["responsibility"] == "case"]
    steward = [row for row in rows if row["responsibility"] == "steward"]
    if not case or not steward or len(case) + len(steward) != len(rows):
        raise ValueError("invalid H6 role partition")
    return case, steward


def analyst_prompt(*, unit: dict[str, Any], replicate: str, role_name: str, member_id: str,
                   rows: list[dict[str, Any]], slots: dict[str, str]) -> str:
    role_text = (
        "You are the case analyst. Focus on decision evidence assigned to your role and report facts the chair needs."
        if role_name == "case_analyst"
        else "You are the institutional steward. Focus on procedure and current World authority facts assigned to your role."
    )
    return "\n".join([
        "You are a newly assigned H6 successor with no predecessor conversation or hidden state.", role_text,
        f"replicate={replicate} generation=g3 role={role_name} member_id={member_id}",
        f"CURRENT organization_id={unit['organization_id']} predicate={unit['predicate']}",
        f"OFFERED actions={json.dumps(sorted(unit['actions']), separators=(',', ':'))}",
        f"DECISION RULE: {task_rule(str(unit['family']))}",
        "You see only your allocated share of the organization's six canonical g3 records. Do not invent missing facts.",
        "Evidence is labeled only by local slots E1-E6. Cite only slots actually shown to you.",
        "Use finding to transmit concise decision-relevant facts to the chair, including opaque tokens exactly as written.",
        "If your allocation is insufficient for an action or notice recommendation, use UNRESOLVED for that field.",
        "ALLOCATED RECORDS:", json.dumps([visible_record(row, slots) for row in rows], sort_keys=True, separators=(",", ":")),
    ])


def arm_factors(arm: str) -> tuple[str, bool]:
    if arm not in ARMS:
        raise ValueError(arm)
    return ("persistent" if arm.startswith("persistent_") else "static", arm.endswith("_with_state"))


def protocol_for(arm: str, family: str, rows: list[dict[str, Any]], slots: dict[str, str]) -> dict[str, Any]:
    framing, with_state = arm_factors(arm)
    protocol: dict[str, Any] = {
        "schema": "h6-governance-protocol-v0.1", "role_binding": True, "authority_governance": True,
        "authority_rule": "current_world_verification_overrides_historical_labels",
        "governance_frame": "organization_owned_persistent" if framing == "persistent" else "reset_current_generation",
        "state_channel_present": with_state,
    }
    if with_state:
        protocol["institutional_state"] = institutional_state(family, rows, slots)
    return protocol


def chair_prompt(cell: dict[str, Any], reports: list[dict[str, Any]]) -> str:
    protocol = cell["protocol"]
    frame_instruction = (
        "Treat the organization as retaining an organization-owned persistent governance identity across turnover."
        if protocol["governance_frame"] == "organization_owned_persistent"
        else "Treat governance as reset to the current generation; do not infer retained institutional state."
    )
    state_lines: list[str] = []
    if protocol["state_channel_present"]:
        state_lines.append("INSTITUTIONAL STATE CHANNEL=" + json.dumps(protocol["institutional_state"], sort_keys=True, separators=(",", ":")))
    return "\n".join([
        "You are the newly assigned H6 chair/executor with no predecessor conversation or hidden state.",
        f"replicate={cell['replicate']} generation=g3 member_id={cell['chair_member_id']}",
        f"CURRENT organization_id={cell['organization_id']} predicate={cell['predicate']}",
        f"OFFERED actions={json.dumps(cell['actions'], separators=(',', ':'))}",
        f"CANDIDATE notices={json.dumps(cell['candidate_notices'], separators=(',', ':'))}",
        f"DECISION RULE: {task_rule(cell['family'])}",
        "GOVERNANCE: an execution notice is acceptable only when current World verification=true; historical labels never create authority.",
        "FRAME INSTRUCTION: " + frame_instruction, *state_lines,
        "Synthesize only the two fresh analyst reports below. Do not invent evidence. Evidence citations must use only slots E1-E6.",
        "INSTITUTIONAL PROTOCOL=" + json.dumps(protocol, sort_keys=True, separators=(",", ":")),
        "ANALYST REPORTS:", json.dumps(reports, sort_keys=True, separators=(",", ":")),
    ])


def prepare(evidence: dict[str, Any]) -> dict[str, Any]:
    units = {str(unit["unit_id"]): dict(unit) for unit in evidence["units"]}
    cells: list[dict[str, Any]] = []
    arm_order = list(evidence["factorial_arms"])
    for rep_index, replicate in enumerate(evidence["replicates"]):
        for unit_index, unit_id in enumerate(sorted(units)):
            unit = units[unit_id]
            source = [dict(row) for row in evidence["canonical_evidence_sets"][unit_id]]
            claims = cg_records(source)
            if norm(claims) != source:
                raise ValueError("ContextGraph corpus differs from H6 H5-lineage canonical records")
            bundle = bounded_historical_evidence(
                claims, query_id=did("h6-query-", {"unit": unit_id, "generation": "g3"}),
                requesting_organization_id=unit["organization_id"], predicate=unit["predicate"],
                decision_cutoff=max(int(row["observed_at"]) for row in source), result_limit=6, enabled=True,
                evidence_release_commit=CG,
            )
            rows = norm(list(bundle["evidence"]))
            if rows != source or len(rows) != 6:
                raise ValueError("H6 bounded history must reproduce exact frozen H5 g3 canonical set")
            slots = slot_map(rows); case_rows, steward_rows = partition(rows); members = unit["members"][replicate]
            member_ids = [members["case_analyst"], members["institutional_steward"]]
            analyst_prompts = [
                analyst_prompt(unit=unit, replicate=replicate, role_name=role, member_id=member_ids[i], rows=part, slots=slots)
                for i, (role, part) in enumerate(zip(("case_analyst", "institutional_steward"), (case_rows, steward_rows)))
            ]
            analyst_hashes = [hashlib.sha256(prompt.encode()).hexdigest() for prompt in analyst_prompts]
            state = institutional_state(str(unit["family"]), rows, slots)
            rotation = (rep_index * len(units) + unit_index) % len(arm_order)
            rotated = arm_order[rotation:] + arm_order[:rotation]
            for arm in rotated:
                cells.append({
                    "organizational_cell_id": did("h6-cell-", {"unit": unit_id, "replicate": replicate, "arm": arm}),
                    "unit_id": unit_id, "family": unit["family"], "replicate": replicate, "generation": "g3", "arm": arm,
                    "organization_id": unit["organization_id"], "predicate": unit["predicate"], "actions": sorted(unit["actions"]),
                    "candidate_notices": candidate_notices(rows), "canonical_records": rows,
                    "canonical_record_ids": [str(row["record_id"]) for row in rows],
                    "evidence_slot_to_record_id": {slots[str(row["record_id"])]: str(row["record_id"]) for row in rows},
                    "history_bundle_id": bundle["bundle_id"], "analyst_roles": ["case_analyst", "institutional_steward"],
                    "analyst_member_ids": member_ids, "chair_member_id": members["chair"],
                    "analyst_partitions": [[slots[str(row["record_id"])] for row in case_rows], [slots[str(row["record_id"])] for row in steward_rows]],
                    "analyst_prompts": analyst_prompts, "analyst_prompt_sha256": analyst_hashes,
                    "protocol": protocol_for(str(arm), str(unit["family"]), rows, slots),
                    "institutional_state_reconstructible": state, "arm_order_rotation": rotation,
                })
    return {
        "schema": "h6-request-plan-v0.1", "world_preregistered_base": evidence["world_preregistered_base"],
        "h5_source_candidate": evidence["h5_source_candidate"], "h5_g3_lineage_sha256": evidence["h5_g3_lineage_sha256"],
        "contextgraph_release_commit": CG, "model_contract": evidence["model_contract"], "record_budget": evidence["record_budget"],
        "calls_per_cell": evidence["calls_per_cell"], "cells": cells, "direct_edge_sentinels": sentinels(),
        "production_historical_substrate_enabled": False,
    }
