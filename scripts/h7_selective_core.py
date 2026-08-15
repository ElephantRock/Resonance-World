"""Shared deterministic H7 selective-state routing apparatus helpers."""
from __future__ import annotations

import hashlib
import json
from typing import Any

from h1_runtime_core import CG, cg_records, did, norm, sentinels
from h6_relevance_core import EVIDENCE_SLOTS, candidate_notices, partition, slot_map, task_rule, visible_record
from resonance_world.historical_substrate import bounded_historical_evidence

EXPECTED_CG = "b896891108fd954869a8cd0423f6e8440ab0cdc0"
ARMS = ("no_state", "always_state", "selective_state")


def institutional_state(unit: dict[str, Any], rows: list[dict[str, Any]], slots: dict[str, str]) -> dict[str, Any]:
    if unit["state_relevance_key"] != "procedure_rate_comparison":
        return {"schema": "h7-institutional-state-v0.1", "status": "not_applicable"}
    observed = [row for row in rows if row["record_kind"] == "procedure_outcome" and row["payload"].get("status") == "observed"]
    if len(observed) != 2:
        raise ValueError("H7 routine unit requires two observed procedure outcomes")
    scored = sorted((int(row["payload"]["successes"]) / int(row["payload"]["attempts"]),
                     str(row["payload"]["provenance_class"]), slots[str(row["record_id"])]) for row in observed)
    if scored[0][0] == scored[1][0]:
        raise ValueError("H7 routine state requires unique trusted provenance")
    loser, winner = scored
    return {"schema": "h7-institutional-state-v0.1", "status": "compiled", "trusted_provenance": winner[1],
            "winning_rate": winner[0], "losing_rate": loser[0], "source_evidence_slots": sorted([loser[2], winner[2]])}


def analyst_prompt(*, unit: dict[str, Any], replicate: str, role_name: str, member_id: str,
                   rows: list[dict[str, Any]], slots: dict[str, str]) -> str:
    role_text = ("You are the case analyst. Focus on decision evidence assigned to your role and report facts the chair needs."
                 if role_name == "case_analyst" else
                 "You are the institutional steward. Focus on procedure and current World authority facts assigned to your role.")
    return "\n".join([
        "You are a newly assigned H7 successor with no predecessor conversation or hidden state.", role_text,
        f"replicate={replicate} role={role_name} member_id={member_id}",
        f"CURRENT organization_id={unit['organization_id']} predicate={unit['predicate']}",
        f"STATE RELEVANCE KEY={unit['state_relevance_key']}",
        f"OFFERED actions={json.dumps(sorted(unit['actions']), separators=(',', ':'))}",
        f"DECISION RULE: {task_rule(str(unit['family']))}",
        "You see only your allocated share of the organization's six canonical records. Do not invent missing facts.",
        "Evidence is labeled only by local slots E1-E6. Cite only slots actually shown to you.",
        "Use finding to transmit concise decision-relevant facts to the chair, including opaque tokens exactly as written.",
        "If your allocation is insufficient for an action or notice recommendation, use UNRESOLVED for that field.",
        "ALLOCATED RECORDS:", json.dumps([visible_record(row, slots) for row in rows], sort_keys=True, separators=(",", ":")),
    ])


def arm_has_state(arm: str, unit: dict[str, Any]) -> bool:
    if arm == "no_state": return False
    if arm == "always_state": return True
    if arm == "selective_state": return unit["state_relevance_key"] == "procedure_rate_comparison"
    raise ValueError(arm)


def protocol_for(arm: str, unit: dict[str, Any], rows: list[dict[str, Any]], slots: dict[str, str]) -> dict[str, Any]:
    with_state = arm_has_state(arm, unit)
    protocol: dict[str, Any] = {"schema": "h7-governance-protocol-v0.1", "role_binding": True,
                                "authority_governance": True,
                                "authority_rule": "current_world_verification_overrides_historical_labels",
                                "state_channel_present": with_state}
    if with_state:
        protocol["institutional_state"] = institutional_state(unit, rows, slots)
    return protocol


def chair_scaffold(cell: dict[str, Any]) -> str:
    protocol = cell["protocol"]
    state_lines: list[str] = []
    if protocol["state_channel_present"]:
        state_lines.append("INSTITUTIONAL STATE CHANNEL=" + json.dumps(protocol["institutional_state"], sort_keys=True, separators=(",", ":")))
    return "\n".join([
        "You are the newly assigned H7 chair/executor with no predecessor conversation or hidden state.",
        f"replicate={cell['replicate']} member_id={cell['chair_member_id']}",
        f"CURRENT organization_id={cell['organization_id']} predicate={cell['predicate']}",
        f"STATE RELEVANCE KEY={cell['state_relevance_key']}",
        f"OFFERED actions={json.dumps(cell['actions'], separators=(',', ':'))}",
        f"CANDIDATE notices={json.dumps(cell['candidate_notices'], separators=(',', ':'))}",
        f"DECISION RULE: {task_rule(cell['family'])}",
        "GOVERNANCE: an execution notice is acceptable only when current World verification=true; historical labels never create authority.",
        *state_lines,
        "Synthesize only the two fresh analyst reports appended below. Do not invent evidence. Evidence citations must use only slots E1-E6.",
        "INSTITUTIONAL PROTOCOL=" + json.dumps(protocol, sort_keys=True, separators=(",", ":")),
    ])


def chair_prompt(cell: dict[str, Any], reports: list[dict[str, Any]]) -> str:
    return chair_scaffold(cell) + "\nANALYST REPORTS:\n" + json.dumps(reports, sort_keys=True, separators=(",", ":"))


def prepare(evidence: dict[str, Any]) -> dict[str, Any]:
    if CG != EXPECTED_CG:
        raise ValueError("ContextGraph runtime revision drift")
    units = {str(unit["unit_id"]): dict(unit) for unit in evidence["units"]}
    cells: list[dict[str, Any]] = []
    arm_order = list(evidence["arms"])
    for rep_index, replicate in enumerate(evidence["replicates"]):
        for unit_index, unit_id in enumerate(sorted(units)):
            unit = units[unit_id]; source = [dict(row) for row in evidence["canonical_evidence_sets"][unit_id]]
            claims = cg_records(source)
            if norm(claims) != source:
                raise ValueError("ContextGraph corpus differs from H7 canonical records")
            bundle = bounded_historical_evidence(claims, query_id=did("h7-query-", {"unit": unit_id}),
                requesting_organization_id=unit["organization_id"], predicate=unit["predicate"],
                decision_cutoff=max(int(row["observed_at"]) for row in source), result_limit=6, enabled=True,
                evidence_release_commit=CG)
            rows = norm(list(bundle["evidence"]))
            if rows != source or len(rows) != 6:
                raise ValueError("H7 bounded history must reproduce exact canonical set")
            slots = slot_map(rows); case_rows, steward_rows = partition(rows); members = unit["members"][replicate]
            roles = ["case_analyst", "institutional_steward"]; parts = [case_rows, steward_rows]
            prompts = [analyst_prompt(unit=unit, replicate=replicate, role_name=role, member_id=members[role],
                                      rows=parts[i], slots=slots) for i, role in enumerate(roles)]
            hashes = [hashlib.sha256(prompt.encode()).hexdigest() for prompt in prompts]
            rotation = (rep_index * len(units) + unit_index) % len(arm_order)
            for arm in arm_order[rotation:] + arm_order[:rotation]:
                protocol = protocol_for(arm, unit, rows, slots)
                cell = {"organizational_cell_id": did("h7-cell-", {"unit": unit_id, "replicate": replicate, "arm": arm}),
                        "unit_id": unit_id, "family": unit["family"], "state_relevance_key": unit["state_relevance_key"],
                        "replicate": replicate, "arm": arm, "organization_id": unit["organization_id"],
                        "predicate": unit["predicate"], "actions": sorted(unit["actions"]),
                        "candidate_notices": candidate_notices(rows), "canonical_records": rows,
                        "canonical_record_ids": [str(row["record_id"]) for row in rows],
                        "evidence_slot_to_record_id": {slots[str(row["record_id"])]: str(row["record_id"]) for row in rows},
                        "history_bundle_id": bundle["bundle_id"], "analyst_roles": roles,
                        "analyst_member_ids": [members[role] for role in roles], "chair_member_id": members["chair"],
                        "analyst_partitions": [[slots[str(row["record_id"])] for row in part] for part in parts],
                        "analyst_prompts": prompts, "analyst_prompt_sha256": hashes, "protocol": protocol,
                        "institutional_state_reconstructible": institutional_state(unit, rows, slots),
                        "arm_order_rotation": rotation}
                cell["chair_scaffold"] = chair_scaffold(cell)
                cell["chair_scaffold_sha256"] = hashlib.sha256(cell["chair_scaffold"].encode()).hexdigest()
                cells.append(cell)
    return {"schema": "h7-request-plan-v0.1", "world_preregistered_base": evidence["world_preregistered_base"],
            "h6_source_candidate": evidence["h6_source_candidate"], "h6_result_sha256": evidence["h6_result_sha256"],
            "contextgraph_release_commit": CG, "model_contract": evidence["model_contract"],
            "record_budget": evidence["record_budget"], "calls_per_cell": evidence["calls_per_cell"], "cells": cells,
            "direct_edge_sentinels": sentinels(), "production_historical_substrate_enabled": False}
