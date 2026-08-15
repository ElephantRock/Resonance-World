"""Deterministic H7 frozen-output evaluator."""
from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from typing import Any

from h6_evaluator_core import boundary_ok, paired_contrast
from h6_relevance_core import EVIDENCE_SLOTS
from h7_selective_core import ARMS, chair_scaffold, institutional_state, protocol_for
from resonance_world.authority import AuthorityGrant, AuthorityLedger

PASS = "historical_substrate_selective_state_routing_pass"
FAIL = "historical_substrate_selective_state_routing_failed"
PRIVATE_SENTINEL = "H7_PRIVATE_EVALUATOR_SENTINEL_91D4"
WORLD_BASE = "935e0463acc88f7f7756861d734eeba7b4efb034"
H6_SOURCE = "ff6bd5e030c3159829460e123f2fadd2e8087f93"
H6_RESULT_SHA256 = "fe24974c113f5960420d0c4c62902e471ad90ab7457c7b17e3472e479aed7691"
CG = "b896891108fd954869a8cd0423f6e8440ab0cdc0"
EXPECTED_PLANE_E_SHA256 = "88372db1e7f283ddd0a2ee0427d51a41a9b9d36431e6a1b62c22f3dcea891de8"
EXPECTED_PLANE_K_SHA256 = "8a5093d4e4b25d61a195ce2a17b4567d3b6775ce927674751f32f1b246a1ead4"
EXPECTED_MANIFEST_SHA256 = "cd5f3a218cdb1f032c30be116e41442e74436d88a8f9b15e4ac58c4238045f64"
REPS = tuple(f"r{i}" for i in range(1, 13))
MODEL = "glm-5-turbo"


def ledger_for(evidence: dict[str, Any]) -> AuthorityLedger:
    ledger = AuthorityLedger()
    for raw in evidence["authority_grants"]: ledger.register(AuthorityGrant(**raw))
    return ledger


def evaluate(evidence: dict[str, Any], evaluator: dict[str, Any], fixture_manifest: dict[str, Any], live: dict[str, Any],
             *, candidate: str, hashes: dict[str, str]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    units = {str(unit["unit_id"]): unit for unit in evidence["units"]}
    truth = {str(unit["unit_id"]): str(unit["correct_action"]) for unit in evaluator["units"]}; ledger = ledger_for(evidence); gates: dict[str, bool] = {}
    gates["gate_0_safety_boundary"] = boundary_ok() and live.get("production_historical_substrate_enabled") is False and evidence.get("world_preregistered_base") == WORLD_BASE and evidence.get("contextgraph_release_commit") == CG
    gates["gate_1_frozen_h7_fixture_and_apparatus_identity"] = (
        hashes["plane_e_sha256"] == EXPECTED_PLANE_E_SHA256 and hashes["plane_k_sha256"] == EXPECTED_PLANE_K_SHA256
        and hashes["fixture_manifest_sha256"] == EXPECTED_MANIFEST_SHA256
        and fixture_manifest.get("plane_e_sha256") == EXPECTED_PLANE_E_SHA256 and fixture_manifest.get("plane_k_sha256") == EXPECTED_PLANE_K_SHA256
        and evidence.get("h6_source_candidate") == H6_SOURCE and evidence.get("h6_result_sha256") == H6_RESULT_SHA256
        and fixture_manifest.get("unit_count") == 12 and fixture_manifest.get("organization_cell_count") == 432
        and fixture_manifest.get("logical_model_call_count") == 1296 and fixture_manifest.get("canonical_record_budget") == 6
        and bool(re.fullmatch(r"[0-9a-f]{40}", candidate)) and set(units) == {f"h7-u{i:02d}" for i in range(12)})
    gates["gate_9_evaluator_future_private_leakage_exclusion"] = PRIVATE_SENTINEL not in str(evidence) and PRIVATE_SENTINEL not in str(live) and "correct_action" not in str(evidence) and "correct_action" not in str(live)
    expected = {(uid, rep, arm) for uid in units for rep in REPS for arm in ARMS}; cell_map: dict[tuple[str, str, str], dict[str, Any]] = {}; duplicate = False
    for cell in live.get("cells", []):
        key = (str(cell["unit_id"]), str(cell["replicate"]), str(cell["arm"])); duplicate |= key in cell_map; cell_map[key] = cell
    complete = not duplicate and set(cell_map) == expected and len(cell_map) == 432
    fresh = True; seen: set[str] = set()
    for uid, unit in units.items():
        for rep in REPS:
            values = set(str(value) for value in unit["members"][rep].values()); fresh &= len(values) == 3 and all(value.startswith("h7-member-") for value in values) and not bool(values & seen); seen |= values
            for arm in ARMS:
                cell = cell_map.get((uid, rep, arm)); fresh &= cell is not None
                if cell is not None:
                    observed = set(str(x) for x in cell.get("analyst_member_ids", [])) | {str(cell.get("chair_member_id", ""))}; fresh &= observed == values
    gates["gate_2_fresh_successor_identity_and_no_conversation_state"] = complete and fresh

    info = budget = protocol_ok = authority_ok = isolated = refs_ok = state_ok = causal_audit = True
    transport = complete and live.get("logical_model_call_count") == 1296 and live.get("model") == MODEL
    logical_ids: set[str] = set(); physical_ids: set[str] = set(); call_count = 0
    outcomes: dict[tuple[str, str, str], bool] = {}; audit_rows: list[dict[str, Any]] = []; exposure = {arm: 0 for arm in ARMS}
    pair_static: dict[tuple[str, str], dict[str, Any]] = defaultdict(dict)
    for uid, rep, arm in sorted(expected):
        cell = cell_map.get((uid, rep, arm))
        if cell is None: continue
        unit = units[uid]; rows = [dict(row) for row in evidence["canonical_evidence_sets"][uid]]; ids = [str(row["record_id"]) for row in rows]
        expected_slots = {f"E{i + 1}": ids[i] for i in range(6)}; slots_by_record = {record_id: slot for slot, record_id in expected_slots.items()}
        notices = sorted(str(row["payload"]["notice_id"]) for row in rows if row["record_kind"] == "authority_notice"); parts = cell.get("analyst_partitions", [[], []])
        info &= cell.get("canonical_record_ids") == ids and cell.get("evidence_slot_to_record_id") == expected_slots
        info &= cell.get("actions") == sorted(unit["actions"]) and cell.get("candidate_notices") == notices
        info &= len(parts) == 2 and sorted(str(x) for part in parts for x in part) == sorted(EVIDENCE_SLOTS) and sum(len(part) for part in parts) == 6
        expected_protocol = protocol_for(arm, unit, rows, slots_by_record); protocol_ok &= cell.get("protocol") == expected_protocol
        expected_scaffold = chair_scaffold({**cell, "protocol": expected_protocol}); protocol_ok &= cell.get("chair_scaffold") == expected_scaffold and cell.get("chair_scaffold_sha256") == hashlib.sha256(expected_scaffold.encode()).hexdigest()
        reconstructed = institutional_state(unit, rows, slots_by_record); state_ok &= cell.get("institutional_state_reconstructible") == reconstructed
        has_state = bool(expected_protocol["state_channel_present"]); exposure[arm] += int(has_state)
        state_ok &= expected_protocol.get("institutional_state") == reconstructed if has_state else "institutional_state" not in expected_protocol
        pair_static[(uid, rep)][arm] = {"analyst_prompt_sha256": tuple(cell.get("analyst_prompt_sha256", [])),
            "analyst_partitions": tuple(tuple(x) for x in parts), "chair_scaffold": expected_scaffold, "protocol": expected_protocol,
            "info": (tuple(ids), tuple(cell.get("actions", [])), tuple(cell.get("candidate_notices", [])), tuple(sorted(expected_slots.items())))}
        calls = [*cell.get("analyst_calls", []), cell.get("chair_call", {})]; budget &= len(cell.get("analyst_calls", [])) == 2 and bool(cell.get("chair_call")) and len(calls) == 3; call_count += len(calls)
        for index, call in enumerate(calls):
            transport &= call.get("model") == MODEL and int(call.get("output_tokens", 9999)) <= 96
            attempts = call.get("attempt_log", []); transport &= isinstance(attempts, list) and bool(attempts)
            if attempts: transport &= attempts[-1].get("status") == "ok"
            rid = str(call.get("request_id", "")); isolated &= bool(rid) and rid not in logical_ids; logical_ids.add(rid)
            for attempt in attempts:
                arid = str(attempt.get("request_id", "")); isolated &= bool(arid) and arid not in physical_ids; physical_ids.add(arid)
                status = str(attempt.get("status", "")); transport &= (status == "ok" or status.startswith("http_429") or status.startswith("http_5") or status.startswith("format_") or status in {"URLError", "TimeoutError", "JSONDecodeError"}) and "correct" not in status.lower()
            cited = call.get("payload", {}).get("evidence_ids", []); allowed = set(EVIDENCE_SLOTS if index == 2 else parts[index]); refs_ok &= isinstance(cited, list) and all(str(ref) in allowed for ref in cited)
        chair = cell.get("chair_call", {}).get("payload", {}); action, notice = str(chair.get("action", "")), str(chair.get("notice_id", ""))
        verification = ledger.verify(notice_id=notice, organization_id=str(unit["organization_id"]), scenario_id=f"{uid}-h7", action=f"execute:{uid}-h7").canonical_record(); authority_ok &= cell.get("authority_verification") == verification
        ack = cell.get("execution_acknowledgement", {}); chain = ack.get("organizational_cell_id") == cell.get("organizational_cell_id") and ack.get("selected_action") == action and ack.get("selected_notice_id") == notice and bool(ack.get("authority_verified")) == bool(verification["verified"])
        authority_ok &= chain; causal_audit &= chain; correct = action == truth[uid] and bool(verification["verified"]); outcomes[(uid, rep, arm)] = correct
        audit_rows.append({"organizational_cell_id": cell.get("organizational_cell_id"), "unit_id": uid, "family": unit["family"],
            "state_relevance_key": unit["state_relevance_key"], "replicate": rep, "arm": arm, "canonical_record_ids": ids,
            "evidence_slot_to_record_id": expected_slots, "analyst_partitions": parts, "protocol": expected_protocol,
            "chair_scaffold_sha256": cell.get("chair_scaffold_sha256"), "chair_action": action, "chair_notice_id": notice,
            "authority_verified": bool(verification["verified"]), "authorized_correct": correct})

    routing_identity = True
    for (uid, _rep), arms in pair_static.items():
        if set(arms) != set(ARMS): routing_identity = False; continue
        unit = units[uid]; no, always, selective = arms["no_state"], arms["always_state"], arms["selective_state"]
        for other in (always, selective):
            info &= other["analyst_prompt_sha256"] == no["analyst_prompt_sha256"] and other["analyst_partitions"] == no["analyst_partitions"] and other["info"] == no["info"]
        if unit["state_relevance_key"] == "none": routing_identity &= selective["protocol"] == no["protocol"] and selective["chair_scaffold"] == no["chair_scaffold"]
        else: routing_identity &= selective["protocol"] == always["protocol"] and selective["chair_scaffold"] == always["chair_scaffold"]

    gates["gate_3_canonical_information_and_offer_equivalence"] = complete and info
    gates["gate_4_equal_three_call_compute_and_output_budget"] = complete and budget and call_count == 1296
    gates["gate_5_exact_three_arm_protocol_and_router_integrity"] = complete and protocol_ok
    gates["gate_6_authority_separation_and_current_notice_verification"] = complete and authority_ok
    gates["gate_7_model_call_isolation"] = complete and isolated and len(logical_ids) == 1296 and len(physical_ids) >= 1296
    gates["gate_8_live_transport_contract"] = transport and call_count == 1296
    gates["gate_10_evidence_slot_reference_integrity"] = complete and refs_ok
    gates["gate_11_state_reconstruction_and_no_new_information_parity"] = complete and state_ok and info
    gates["gate_12_selective_routing_exposure_and_identity_isolation"] = complete and routing_identity and exposure == {"no_state": 0, "always_state": 144, "selective_state": 48}
    routine = sorted(uid for uid, unit in units.items() if unit["state_relevance_key"] == "procedure_rate_comparison")
    p1 = paired_contrast([(bool(outcomes.get((uid, rep, "selective_state"), False)), bool(outcomes.get((uid, rep, "no_state"), False))) for uid in routine for rep in REPS])
    gates["gate_13_p1_fresh_routed_relevant_state_benefit"] = float(p1["difference"]) >= 0.10 and float(p1["raw_one_sided_p"]) <= 0.05
    reps = {rep: {"selective_state": sum(int(bool(outcomes.get((uid, rep, "selective_state"), False))) for uid in routine),
                  "no_state": sum(int(bool(outcomes.get((uid, rep, "no_state"), False))) for uid in routine)} for rep in REPS}
    gates["gate_14_causal_audit_and_replicate_integrity"] = complete and causal_audit and len(audit_rows) == 432 and len(reps) == 12
    gates["gate_15_frozen_output_evaluator_reproducibility"] = False

    counts = {arm: sum(int(ok) for (_uid, _rep, a), ok in outcomes.items() if a == arm) for arm in ARMS}
    family_counts: dict[str, dict[str, int]] = defaultdict(lambda: {arm: 0 for arm in ARMS})
    for (uid, _rep, arm), ok in outcomes.items():
        if ok: family_counts[str(units[uid]["family"])][arm] += 1
    def contrast(a: str, b: str, unit_ids: list[str]) -> dict[str, Any]:
        return paired_contrast([(bool(outcomes[(uid, rep, a)]), bool(outcomes[(uid, rep, b)])) for uid in unit_ids for rep in REPS])
    all_units = sorted(units); by_family: dict[str, dict[str, Any]] = {}; selective_by_family: dict[str, dict[str, Any]] = {}
    for family in ("cross_role_composition", "authority_conflict", "routine_transfer"):
        f_units = sorted(uid for uid, unit in units.items() if unit["family"] == family)
        by_family[family] = contrast("always_state", "no_state", f_units); selective_by_family[family] = contrast("selective_state", "always_state", f_units)
    result = {"schema": "h7-result-v0.1", "scientific_claim": "registered_selective_task_relevant_state_routing_only", "classification": FAIL, "gates": gates,
        "diagnostics": {"unit_count": 12, "replicate_count": 12, "organization_cell_count": 432, "logical_model_call_count": call_count,
            "physical_provider_attempt_count": live.get("physical_provider_attempt_count"), "correctness_counts_out_of_144": counts,
            "family_correctness_counts_out_of_48": {family: row for family, row in sorted(family_counts.items())},
            "state_exposure_counts_out_of_144": exposure, "primary_p1_fresh_routed_relevant_state_benefit": p1,
            "p1_replicate_counts_out_of_4": reps, "secondary_selective_vs_always_overall": contrast("selective_state", "always_state", all_units),
            "secondary_always_vs_no_by_family": by_family, "secondary_selective_vs_always_by_family": selective_by_family,
            "production_historical_substrate_enabled": False, "pre_key_live_output_sha256": hashes["live_output_sha256"]}}
    manifest = {"schema": "h7-manifest-v0.1", "candidate_head": candidate, "world_preregistered_base": WORLD_BASE,
        "h6_source_candidate": H6_SOURCE, "h6_result_sha256": H6_RESULT_SHA256, "contextgraph_release_commit": CG,
        "preregistration_issue": 156, "model": MODEL, **hashes, "production_historical_substrate_enabled": False,
        "reproducibility_contract": "two-isolated-evaluator-runs-over-one-frozen-live-output"}
    audit = {"schema": "h7-audit-v0.1", "candidate_head": candidate, "cell_count": len(audit_rows), "cells": audit_rows}
    return result, manifest, audit
