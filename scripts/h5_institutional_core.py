"""Shared deterministic H5 institutional-mediation apparatus helpers."""
from __future__ import annotations

import hashlib
import json
from typing import Any

from h1_runtime_core import CG, cg_records, did, norm, sentinels
from resonance_world.historical_substrate import bounded_historical_evidence


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
            "provenance_class. Procedure-outcome evidence, when complete, determines which provenance to trust: "
            "among observed procedure_outcome records, compute successes/attempts for each provenance and trust "
            "the unique higher-rate provenance. Choose the action recommended by that provenance. With fewer "
            "than two observed procedure outcomes, the evidence is insufficient and requires best effort. " + authority
        )
    raise ValueError(family)


def visible_record(row: dict[str, Any]) -> dict[str, Any]:
    return {
        key: row[key]
        for key in (
            "record_id", "organization_id", "predicate", "observed_at",
            "responsibility", "record_kind", "payload",
        )
    }


def routine_digest(family: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    if family != "routine_transfer":
        return {"schema": "institutional-routine-digest-v0.1", "status": "not_applicable"}
    observed = [
        row for row in rows
        if row["record_kind"] == "procedure_outcome" and row["payload"].get("status") == "observed"
    ]
    base: dict[str, Any] = {
        "schema": "institutional-routine-digest-v0.1",
        "source_record_ids": sorted(str(row["record_id"]) for row in observed),
    }
    if len(observed) < 2:
        return {**base, "status": "insufficient", "observed_count": len(observed)}
    scored = sorted(
        (
            int(row["payload"]["successes"]) / int(row["payload"]["attempts"]),
            str(row["payload"]["provenance_class"]),
        )
        for row in observed
    )
    if len(scored) != 2 or scored[0][0] == scored[1][0]:
        return {**base, "status": "ambiguous", "observed_count": len(observed)}
    loser, winner = scored
    return {
        **base,
        "status": "compiled",
        "trusted_provenance": winner[1],
        "winning_rate": winner[0],
        "losing_rate": loser[0],
    }


def candidate_notices(rows: list[dict[str, Any]]) -> list[str]:
    values = [
        str(row["payload"]["notice_id"])
        for row in rows if row["record_kind"] == "authority_notice"
    ]
    if len(values) != 2 or len(set(values)) != 2:
        raise ValueError("H5 requires exactly two candidate notices")
    return sorted(values)


def partition(rows: list[dict[str, Any]], direct: bool) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if direct:
        ordered = sorted(rows, key=lambda row: str(row["record_id"]))
        return ordered[::2], ordered[1::2]
    case = [row for row in rows if row["responsibility"] == "case"]
    steward = [row for row in rows if row["responsibility"] == "steward"]
    if not case or not steward or len(case) + len(steward) != len(rows):
        raise ValueError("invalid H5 role partition")
    return case, steward


def analyst_prompt(
    *, unit: dict[str, Any], generation: str, replicate: str, arm: str,
    role_name: str, member_id: str, rows: list[dict[str, Any]],
) -> str:
    role_text = (
        "You are one generic peer analyst. Do not assume a specialized institutional responsibility."
        if arm == "equal_compute_direct"
        else (
            "You are the case analyst. Focus on decision evidence assigned to your role and report facts the chair needs."
            if role_name == "case_analyst"
            else "You are the institutional steward. Focus on procedure and current World authority facts assigned to your role."
        )
    )
    return "\n".join([
        "You are a newly assigned successor with no predecessor conversation or hidden state.",
        role_text,
        f"replicate={replicate} generation={generation} arm={arm} role={role_name} member_id={member_id}",
        f"CURRENT organization_id={unit['organization_id']} predicate={unit['predicate']}",
        f"OFFERED actions={json.dumps(sorted(unit['actions']), separators=(',', ':'))}",
        f"DECISION RULE: {task_rule(str(unit['family']))}",
        "You see only your allocated share of the organization's six canonical records. Do not invent missing facts.",
        "Use finding to transmit concise decision-relevant facts to the chair, including opaque tokens exactly as written.",
        "If your allocation is insufficient for an action or notice recommendation, use UNRESOLVED for that field.",
        "ALLOCATED RECORDS:",
        json.dumps([visible_record(row) for row in rows], sort_keys=True, separators=(",", ":")),
    ])


def protocol_for(arm: str, digest: dict[str, Any]) -> dict[str, Any]:
    if arm == "equal_compute_direct":
        return {"schema": "h5-neutral-reducer-v0.1", "mode": "neutral_peer_synthesis", "role_binding": False, "authority_governance": False, "routine_state": "absent"}
    if arm == "roles_only":
        return {"schema": "h5-role-reducer-v0.1", "mode": "role_report_synthesis", "role_binding": True, "authority_governance": False, "routine_state": "absent"}
    if arm == "governed_static":
        return {"schema": "h5-governance-protocol-v0.1", "mode": "governed_static", "role_binding": True, "authority_governance": True, "authority_rule": "current_world_verification_overrides_historical_labels", "routine_state": "reset_each_generation"}
    if arm == "governed_persistent":
        return {"schema": "h5-governance-protocol-v0.1", "mode": "governed_persistent", "role_binding": True, "authority_governance": True, "authority_rule": "current_world_verification_overrides_historical_labels", "routine_state": "organization_owned_persistent", "routine_digest": digest}
    raise ValueError(arm)


def chair_prompt(cell: dict[str, Any], reports: list[dict[str, Any]]) -> str:
    protocol = cell["protocol"]
    extra = ""
    if protocol.get("authority_governance"):
        extra += " GOVERNANCE: an execution notice is acceptable only when the steward reports current World verification=true; historical authority labels never create authority."
    digest = protocol.get("routine_digest", {})
    if cell["arm"] == "governed_persistent" and digest.get("status") == "compiled":
        extra += f" PERSISTENT ROUTINE: organization-owned trusted_provenance={digest['trusted_provenance']}."
    return "\n".join([
        "You are the newly assigned chair/executor. You have no predecessor conversation or hidden state.",
        f"replicate={cell['replicate']} generation={cell['generation']} arm={cell['arm']} member_id={cell['chair_member_id']}",
        f"CURRENT organization_id={cell['organization_id']} predicate={cell['predicate']}",
        f"OFFERED actions={json.dumps(cell['actions'], separators=(',', ':'))}",
        f"CANDIDATE notices={json.dumps(cell['candidate_notices'], separators=(',', ':'))}",
        f"DECISION RULE: {task_rule(cell['family'])}{extra}",
        "Synthesize only the two fresh analyst reports below. Do not invent evidence. Evidence IDs may cite records allocated to either analyst.",
        f"INSTITUTIONAL PROTOCOL={json.dumps(protocol, sort_keys=True, separators=(',', ':'))}",
        "ANALYST REPORTS:",
        json.dumps(reports, sort_keys=True, separators=(",", ":")),
    ])


def prepare(evidence: dict[str, Any]) -> dict[str, Any]:
    units = {str(unit["unit_id"]): dict(unit) for unit in evidence["units"]}
    cells: list[dict[str, Any]] = []
    for replicate in evidence["replicates"]:
        for generation in evidence["generations"]:
            for arm in evidence["institutional_arms"]:
                for unit_id in sorted(units):
                    unit = units[unit_id]
                    source = [dict(row) for row in evidence["canonical_evidence_sets"][f"{unit_id}:{generation}"]]
                    claims = cg_records(source)
                    if norm(claims) != source:
                        raise ValueError("ContextGraph corpus differs from H5 canonical records")
                    bundle = bounded_historical_evidence(
                        claims,
                        query_id=did("h5-query-", {"unit": unit_id, "generation": generation}),
                        requesting_organization_id=unit["organization_id"], predicate=unit["predicate"],
                        decision_cutoff=max(int(row["observed_at"]) for row in source), result_limit=6,
                        enabled=True, evidence_release_commit=CG,
                    )
                    rows = norm(list(bundle["evidence"]))
                    if rows != source or len(rows) != 6:
                        raise ValueError("H5 bounded history must reproduce exact canonical set")
                    direct = arm == "equal_compute_direct"
                    first_rows, second_rows = partition(rows, direct)
                    roles = ("generic_analyst_a", "generic_analyst_b") if direct else ("case_analyst", "institutional_steward")
                    members = unit["members"][replicate][generation]
                    member_ids = [members["case_analyst"], members["institutional_steward"]]
                    digest = routine_digest(str(unit["family"]), rows)
                    prompts = [
                        analyst_prompt(unit=unit, generation=generation, replicate=replicate, arm=arm, role_name=roles[i], member_id=member_ids[i], rows=part)
                        for i, part in enumerate((first_rows, second_rows))
                    ]
                    cells.append({
                        "organizational_cell_id": did("h5-cell-", {"unit": unit_id, "replicate": replicate, "generation": generation, "arm": arm}),
                        "unit_id": unit_id, "family": unit["family"], "replicate": replicate,
                        "generation": generation, "arm": arm, "organization_id": unit["organization_id"],
                        "predicate": unit["predicate"], "actions": sorted(unit["actions"]),
                        "candidate_notices": candidate_notices(rows), "canonical_records": rows,
                        "canonical_record_ids": [row["record_id"] for row in rows], "history_bundle_id": bundle["bundle_id"],
                        "analyst_roles": list(roles), "analyst_member_ids": member_ids, "chair_member_id": members["chair"],
                        "analyst_partitions": [[row["record_id"] for row in first_rows], [row["record_id"] for row in second_rows]],
                        "analyst_prompts": prompts,
                        "analyst_prompt_sha256": [hashlib.sha256(prompt.encode()).hexdigest() for prompt in prompts],
                        "protocol": protocol_for(str(arm), digest), "routine_digest_reconstructible": digest,
                    })
    return {
        "schema": "h5-request-plan-v0.1", "world_preregistered_base": evidence["world_preregistered_base"],
        "contextgraph_release_commit": CG, "model_contract": evidence["model_contract"],
        "record_budget": evidence["record_budget"], "calls_per_cell": evidence["calls_per_cell"],
        "cells": cells, "direct_edge_sentinels": sentinels(), "production_historical_substrate_enabled": False,
    }
