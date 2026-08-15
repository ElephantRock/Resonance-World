"""Deterministic H6 frozen-output evaluator core."""
from __future__ import annotations

import math
import re
from collections import defaultdict
from typing import Any, Callable

from h6_relevance_core import EVIDENCE_SLOTS, institutional_state, protocol_for
from resonance_world.authority import AuthorityGrant, AuthorityLedger
from resonance_world.historical_substrate import HISTORICAL_ACCESS_DEFAULT_ENABLED, HistoricalAccessForbidden, require_historical_consumer

PASS = "historical_substrate_relevance_gated_memory_mechanism_pass"
FAIL = "historical_substrate_relevance_gated_memory_mechanism_failed"
PRIVATE_SENTINEL = "H6_PRIVATE_EVALUATOR_SENTINEL_6B19"
WORLD_BASE = "935e0463acc88f7f7756861d734eeba7b4efb034"
H5_SOURCE = "7afa2d139049b1fdb80de2a95d76b49430b6a046"
H5_PLANE_E = "173b3e8a6461c38eb3bad6e3dd7ed6b38807f512b5ff64bfc0ead4f19ed4cbb9"
H5_PLANE_K = "f59804690f06782133881d648b0bcd1cb94c818a6e2747d8d2754b0a45dddb19"
H5_G3_LINEAGE = "a8fab225daa2aebe2584ac4b5bd8248322617a847f2e8a6a14b3cb06323905f7"
CG = "b896891108fd954869a8cd0423f6e8440ab0cdc0"
ARMS = ("static_no_state", "persistent_no_state", "static_with_state", "persistent_with_state")
REPS = tuple(f"r{i}" for i in range(1, 7))


def exact_p(wins: int, losses: int) -> float:
    n = wins + losses
    return 1.0 if not n else sum(math.comb(n, k) for k in range(wins, n + 1)) / 2**n


def holm(raw: dict[str, float]) -> dict[str, Any]:
    order = sorted(raw, key=lambda name: (raw[name], name)); out: dict[str, Any] = {}; active = True; m = len(order)
    for rank, name in enumerate(order, 1):
        threshold = 0.05 / (m - rank + 1); rejected = active and raw[name] <= threshold
        if not rejected: active = False
        out[name] = {"rank": rank, "raw_one_sided_p": raw[name], "threshold": threshold, "rejected": rejected}
    return {"method": "Holm", "alpha": 0.05, "order": order, "decisions": out}


def ledger_for(evidence: dict[str, Any]) -> AuthorityLedger:
    ledger = AuthorityLedger()
    for raw in evidence["authority_grants"]: ledger.register(AuthorityGrant(**raw))
    return ledger


def boundary_ok() -> bool:
    if HISTORICAL_ACCESS_DEFAULT_ENABLED: return False
    for consumer in ("contextgraph_to_world_outcome_law", "contextgraph_to_field_capability_state", "contextgraph_to_automatic_authority", "contextgraph_to_automatic_policy"):
        try: require_historical_consumer(consumer)
        except HistoricalAccessForbidden: continue
        return False
    return True


def paired_contrast(pairs: list[tuple[bool, bool]]) -> dict[str, Any]:
    a_correct = sum(int(a) for a, _ in pairs); b_correct = sum(int(b) for _, b in pairs)
    wins = sum(int(a and not b) for a, b in pairs); losses = sum(int(b and not a) for a, b in pairs); n = len(pairs)
    return {"paired_n": n, "a_correct": a_correct, "b_correct": b_correct,
            "difference": (a_correct - b_correct) / n if n else 0.0,
            "discordant_a_wins": wins, "discordant_b_wins": losses, "raw_one_sided_p": exact_p(wins, losses)}


def evaluate(evidence: dict[str, Any], evaluator: dict[str, Any], fixture_manifest: dict[str, Any], live: dict[str, Any],
             *, candidate: str, hashes: dict[str, str]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    units = {str(unit["unit_id"]): unit for unit in evidence["units"]}
    truth = {str(unit["unit_id"]): str(unit["correct_action"]) for unit in evaluator["units"]}; ledger = ledger_for(evidence); gates: dict[str, bool] = {}
    gates["gate_0_safety_boundary"] = boundary_ok() and live.get("production_historical_substrate_enabled") is False and evidence["world_preregistered_base"] == WORLD_BASE and evidence["contextgraph_release_commit"] == CG
    gates["gate_1_frozen_h5_lineage_and_h6_apparatus_identity"] = (
        fixture_manifest.get("plane_e_sha256") == hashes["plane_e_sha256"] and fixture_manifest.get("plane_k_sha256") == hashes["plane_k_sha256"]
        and evidence.get("h5_source_candidate") == H5_SOURCE and evidence.get("h5_plane_e_sha256") == H5_PLANE_E
        and evidence.get("h5_plane_k_sha256") == H5_PLANE_K and evidence.get("h5_g3_lineage_sha256") == H5_G3_LINEAGE
        and fixture_manifest.get("h5_g3_lineage_sha256") == H5_G3_LINEAGE and fixture_manifest.get("unit_count") == 12
        and fixture_manifest.get("organization_cell_count") == 288 and fixture_manifest.get("logical_model_call_count") == 864
        and fixture_manifest.get("canonical_record_budget") == 6 and bool(re.fullmatch(r"[0-9a-f]{40}", candidate)))
    gates["gate_9_evaluator_future_private_leakage_exclusion"] = PRIVATE_SENTINEL not in str(evidence) and PRIVATE_SENTINEL not in str(live) and "correct_action" not in str(evidence) and "correct_action" not in str(live)
    expected = {(uid, rep, arm) for uid in units for rep in REPS for arm in ARMS}; cell_map: dict[tuple[str, str, str], dict[str, Any]] = {}; duplicate = False
    for cell in live.get("cells", []):
        key = (str(cell["unit_id"]), str(cell["replicate"]), str(cell["arm"])); duplicate |= key in cell_map; cell_map[key] = cell
    complete = not duplicate and set(cell_map) == expected and len(cell_map) == 288
    fresh = True; member_ids_seen: set[str] = set()
    for uid, unit in units.items():
        for rep in REPS:
            expected_members = unit["members"][rep]; values = set(str(value) for value in expected_members.values())
            fresh &= len(values) == 3 and all(value.startswith("h6-member-") for value in values) and not bool(values & member_ids_seen); member_ids_seen |= values
            for arm in ARMS:
                cell = cell_map.get((uid, rep, arm))
                if cell is None: fresh = False; continue
                observed = set(str(x) for x in cell.get("analyst_member_ids", [])) | {str(cell.get("chair_member_id", ""))}; fresh &= observed == values
    gates["gate_2_fresh_successor_identity_and_no_conversation_state"] = complete and fresh
    info = budget = protocol_ok = authority_ok = isolated = refs_ok = state_ok = causal_audit = True
    transport = complete and live.get("logical_model_call_count") == 864 and live.get("model") == "glm-5-turbo"
    logical_request_ids: set[str] = set(); physical_request_ids: set[str] = set(); call_count = 0
    outcomes: dict[tuple[str, str, str], bool] = {}; audit_rows: list[dict[str, Any]] = []
    matched_prompt_hashes: dict[tuple[str, str], tuple[str, ...]] = {}; matched_partitions: dict[tuple[str, str], tuple[tuple[str, ...], ...]] = {}; matched_info: dict[tuple[str, str], tuple[Any, ...]] = {}
    for uid, rep, arm in sorted(expected):
        cell = cell_map.get((uid, rep, arm))
        if cell is None: continue
        unit = units[uid]; rows = [dict(row) for row in evidence["canonical_evidence_sets"][uid]]; ids = [str(row["record_id"]) for row in rows]
        expected_slots = {f"E{i + 1}": ids[i] for i in range(6)}; slots_by_record = {record_id: slot for slot, record_id in expected_slots.items()}
        notices = sorted(str(row["payload"]["notice_id"]) for row in rows if row["record_kind"] == "authority_notice")
        info &= cell.get("generation") == "g3" and cell.get("canonical_record_ids") == ids and cell.get("evidence_slot_to_record_id") == expected_slots
        info &= cell.get("actions") == sorted(unit["actions"]) and cell.get("candidate_notices") == notices
        parts = cell.get("analyst_partitions", [[], []]); info &= len(parts) == 2 and sorted(str(x) for part in parts for x in part) == sorted(EVIDENCE_SLOTS) and sum(len(part) for part in parts) == 6
        pair_key = (uid, rep); prompt_hashes = tuple(str(x) for x in cell.get("analyst_prompt_sha256", [])); partition_key = tuple(tuple(str(x) for x in part) for part in parts)
        info_key = (tuple(ids), tuple(cell.get("actions", [])), tuple(cell.get("candidate_notices", [])), tuple(sorted(expected_slots.items())))
        if pair_key not in matched_prompt_hashes:
            matched_prompt_hashes[pair_key] = prompt_hashes; matched_partitions[pair_key] = partition_key; matched_info[pair_key] = info_key
        else:
            protocol_ok &= prompt_hashes == matched_prompt_hashes[pair_key] and partition_key == matched_partitions[pair_key]; info &= info_key == matched_info[pair_key]
        expected_protocol = protocol_for(str(arm), str(unit["family"]), rows, slots_by_record); protocol_ok &= cell.get("protocol") == expected_protocol
        reconstructed_state = institutional_state(str(unit["family"]), rows, slots_by_record); state_ok &= cell.get("institutional_state_reconstructible") == reconstructed_state
        if arm.endswith("_with_state"): state_ok &= expected_protocol.get("institutional_state") == reconstructed_state
        else: state_ok &= "institutional_state" not in expected_protocol
        if unit["family"] != "routine_transfer" and arm.endswith("_with_state"):
            state_ok &= expected_protocol.get("institutional_state") == {"schema": "h6-institutional-state-v0.1", "status": "not_applicable"}
        calls = [*cell.get("analyst_calls", []), cell.get("chair_call", {})]; budget &= len(cell.get("analyst_calls", [])) == 2 and bool(cell.get("chair_call")) and len(calls) == 3; call_count += len(calls)
        for index, call in enumerate(calls):
            transport &= call.get("model") == "glm-5-turbo" and int(call.get("output_tokens", 9999)) <= 96
            attempt_log = call.get("attempt_log", []); transport &= isinstance(attempt_log, list) and bool(attempt_log)
            if attempt_log: transport &= attempt_log[-1].get("status") == "ok"
            rid = str(call.get("request_id", "")); isolated &= bool(rid) and rid not in logical_request_ids; logical_request_ids.add(rid)
            for attempt in attempt_log:
                arid = str(attempt.get("request_id", "")); isolated &= bool(arid) and arid not in physical_request_ids; physical_request_ids.add(arid)
                status = str(attempt.get("status", "")); transport &= (status == "ok" or status.startswith("http_429") or status.startswith("http_5") or status.startswith("format_") or status in {"URLError", "TimeoutError", "JSONDecodeError"}) and "correct" not in status.lower()
            cited = call.get("payload", {}).get("evidence_ids", []); allowed = set(EVIDENCE_SLOTS if index == 2 else parts[index]); refs_ok &= isinstance(cited, list) and all(str(ref) in allowed for ref in cited)
        chair = cell.get("chair_call", {}).get("payload", {}); action, notice = str(chair.get("action", "")), str(chair.get("notice_id", ""))
        verification = ledger.verify(notice_id=notice, organization_id=str(unit["organization_id"]), scenario_id=f"{uid}-g3", action=f"execute:{uid}-g3").canonical_record(); authority_ok &= cell.get("authority_verification") == verification
        acknowledgement = cell.get("execution_acknowledgement", {}); chain = acknowledgement.get("organizational_cell_id") == cell.get("organizational_cell_id") and acknowledgement.get("selected_action") == action and acknowledgement.get("selected_notice_id") == notice and bool(acknowledgement.get("authority_verified")) == bool(verification["verified"])
        authority_ok &= chain; causal_audit &= chain; correct = action == truth[uid] and bool(verification["verified"]); outcomes[(uid, rep, arm)] = correct
        audit_rows.append({"organizational_cell_id": cell.get("organizational_cell_id"), "unit_id": uid, "family": unit["family"], "replicate": rep, "arm": arm,
                           "canonical_record_ids": ids, "evidence_slot_to_record_id": expected_slots, "analyst_partitions": parts, "protocol": expected_protocol,
                           "chair_action": action, "chair_notice_id": notice, "authority_verified": bool(verification["verified"]), "authorized_correct": correct})
    gates["gate_3_canonical_information_and_offer_equivalence"] = complete and info
    gates["gate_4_equal_three_call_compute_and_output_budget"] = complete and budget and call_count == 864
    gates["gate_5_exact_2x2_protocol_integrity"] = complete and protocol_ok
    gates["gate_6_authority_separation_and_current_notice_verification"] = complete and authority_ok
    gates["gate_7_model_call_isolation"] = complete and isolated and len(logical_request_ids) == 864 and len(physical_request_ids) >= 864
    gates["gate_8_live_transport_contract"] = transport and call_count == 864
    gates["gate_10_evidence_slot_reference_integrity"] = complete and refs_ok
    gates["gate_11_state_reconstruction_and_no_new_information_parity"] = complete and state_ok and info
    counts = {arm: 0 for arm in ARMS}; family_counts: dict[str, dict[str, int]] = defaultdict(lambda: {arm: 0 for arm in ARMS})
    for (uid, _rep, arm), ok in outcomes.items():
        if ok: counts[arm] += 1; family_counts[str(units[uid]["family"])][arm] += 1
    routine_units = [uid for uid, unit in units.items() if unit["family"] == "routine_transfer"]; nonroutine_units = [uid for uid, unit in units.items() if unit["family"] != "routine_transfer"]
    p1_pairs = [(bool(outcomes.get((uid, rep, f"{framing}_with_state"), False)), bool(outcomes.get((uid, rep, f"{framing}_no_state"), False))) for uid in sorted(routine_units) for rep in REPS for framing in ("static", "persistent")]
    p2_pairs = [(bool(outcomes.get((uid, rep, f"{framing}_no_state"), False)), bool(outcomes.get((uid, rep, f"{framing}_with_state"), False))) for uid in sorted(nonroutine_units) for rep in REPS for framing in ("static", "persistent")]
    p1, p2 = paired_contrast(p1_pairs), paired_contrast(p2_pairs); primary = {"p1_relevant_state_benefit": p1, "p2_irrelevant_state_burden": p2}; correction = holm({name: float(row["raw_one_sided_p"]) for name, row in primary.items()})
    gates["gate_12_p1_relevant_state_benefit"] = float(p1["difference"]) >= 0.10 and bool(correction["decisions"]["p1_relevant_state_benefit"]["rejected"])
    gates["gate_13_p2_irrelevant_state_burden"] = float(p2["difference"]) >= 0.10 and bool(correction["decisions"]["p2_irrelevant_state_burden"]["rejected"])
    p1_replicates: dict[str, dict[str, int]] = {}; positive_replicates = 0
    for rep in REPS:
        with_score = sum(int(bool(outcomes.get((uid, rep, f"{framing}_with_state"), False))) for uid in routine_units for framing in ("static", "persistent")); no_score = sum(int(bool(outcomes.get((uid, rep, f"{framing}_no_state"), False))) for uid in routine_units for framing in ("static", "persistent"))
        p1_replicates[rep] = {"with_state": with_score, "no_state": no_score}; positive_replicates += int(with_score > no_score)
    gates["gate_14_replicate_and_causal_audit_integrity"] = complete and causal_audit and len(audit_rows) == 288 and positive_replicates >= 5
    gates["gate_15_frozen_output_evaluator_reproducibility"] = False
    def framing_pairs(unit_filter: Callable[[str], bool]) -> list[tuple[bool, bool]]:
        return [(bool(outcomes.get((uid, rep, f"persistent_{state}"), False)), bool(outcomes.get((uid, rep, f"static_{state}"), False))) for uid in sorted(units) if unit_filter(uid) for rep in REPS for state in ("no_state", "with_state")]
    state_by_family: dict[str, dict[str, Any]] = {}
    for family in ("cross_role_composition", "authority_conflict"):
        pairs = [(bool(outcomes.get((uid, rep, f"{framing}_no_state"), False)), bool(outcomes.get((uid, rep, f"{framing}_with_state"), False))) for uid in sorted(units) if units[uid]["family"] == family for rep in REPS for framing in ("static", "persistent")]
        state_by_family[family] = paired_contrast(pairs)
    result = {"schema": "h6-result-v0.1", "scientific_claim": "registered_relevance_gated_institutional_state_mechanism_only", "classification": FAIL, "gates": gates,
              "diagnostics": {"unit_count": 12, "replicate_count": 6, "organization_cell_count": 288, "logical_model_call_count": call_count,
                              "physical_provider_attempt_count": live.get("physical_provider_attempt_count"), "correctness_counts_out_of_72": counts,
                              "family_correctness_counts_out_of_24": {family: row for family, row in sorted(family_counts.items())}, "primary_contrasts": primary,
                              "holm": correction, "p1_positive_replicates": positive_replicates, "p1_replicate_counts_out_of_8": p1_replicates,
                              "secondary_persistent_framing_routine": paired_contrast(framing_pairs(lambda uid: units[uid]["family"] == "routine_transfer")),
                              "secondary_persistent_framing_nonroutine": paired_contrast(framing_pairs(lambda uid: units[uid]["family"] != "routine_transfer")),
                              "secondary_irrelevant_state_burden_by_family": state_by_family, "production_historical_substrate_enabled": False,
                              "pre_key_live_output_sha256": hashes["live_output_sha256"]}}
    manifest = {"schema": "h6-manifest-v0.1", "candidate_head": candidate, "world_preregistered_base": WORLD_BASE, "h5_source_candidate": H5_SOURCE,
                "h5_plane_e_sha256": H5_PLANE_E, "h5_plane_k_sha256": H5_PLANE_K, "h5_g3_lineage_sha256": H5_G3_LINEAGE,
                "contextgraph_release_commit": CG, "preregistration_issue": 154, "model": "glm-5-turbo", **hashes,
                "production_historical_substrate_enabled": False, "reproducibility_contract": "two-isolated-evaluator-runs-over-one-frozen-live-output"}
    audit_doc = {"schema": "h6-audit-v0.1", "candidate_head": candidate, "cell_count": len(audit_rows), "cells": audit_rows}
    return result, manifest, audit_doc
