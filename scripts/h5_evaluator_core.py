"""Deterministic H5 frozen-output evaluator core."""
from __future__ import annotations

import math
import re
from collections import defaultdict
from typing import Any

from h5_institutional_core import routine_digest
from resonance_world.authority import AuthorityGrant, AuthorityLedger
from resonance_world.historical_substrate import HISTORICAL_ACCESS_DEFAULT_ENABLED, HistoricalAccessForbidden, require_historical_consumer

PASS = "historical_substrate_institutional_mediation_pass"
FAIL = "historical_substrate_institutional_mediation_failed"
PRIVATE_SENTINEL = "H5_PRIVATE_EVALUATOR_SENTINEL_41C7"
WORLD_BASE = "935e0463acc88f7f7756861d734eeba7b4efb034"
CG = "b896891108fd954869a8cd0423f6e8440ab0cdc0"
ARMS = ("equal_compute_direct", "roles_only", "governed_static", "governed_persistent")
GENS = ("g1", "g2", "g3")
REPS = ("r1", "r2", "r3")


def exact_p(w: int, l: int) -> float:
    n = w + l
    return 1.0 if not n else sum(math.comb(n, k) for k in range(w, n + 1)) / 2**n


def holm(raw: dict[str, float]) -> dict[str, Any]:
    order = sorted(raw, key=lambda x: (raw[x], x)); out = {}; active = True; m = len(order)
    for rank, name in enumerate(order, 1):
        threshold = 0.05 / (m - rank + 1); rejected = active and raw[name] <= threshold
        if not rejected: active = False
        out[name] = {"rank": rank, "raw_one_sided_p": raw[name], "threshold": threshold, "rejected": rejected}
    return {"method": "Holm", "alpha": 0.05, "order": order, "decisions": out}


def ledger_for(e: dict[str, Any]) -> AuthorityLedger:
    ledger = AuthorityLedger()
    for raw in e["authority_grants"]: ledger.register(AuthorityGrant(**raw))
    return ledger


def boundary_ok() -> bool:
    if HISTORICAL_ACCESS_DEFAULT_ENABLED: return False
    for consumer in ("contextgraph_to_world_outcome_law", "contextgraph_to_field_capability_state", "contextgraph_to_automatic_authority", "contextgraph_to_automatic_policy"):
        try: require_historical_consumer(consumer)
        except HistoricalAccessForbidden: continue
        return False
    return True


def evaluate(e: dict[str, Any], k: dict[str, Any], fm: dict[str, Any], live: dict[str, Any], *, candidate: str, hashes: dict[str, str]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    units = {str(u["unit_id"]): u for u in e["units"]}; truth = {str(u["unit_id"]): str(u["correct_action"]) for u in k["units"]}; ledger = ledger_for(e)
    gates: dict[str, bool] = {}
    gates["gate_0_safety_boundary"] = boundary_ok() and live.get("production_historical_substrate_enabled") is False and e["world_preregistered_base"] == WORLD_BASE and e["contextgraph_release_commit"] == CG
    gates["gate_1_frozen_apparatus_identity"] = fm.get("plane_e_sha256") == hashes["plane_e_sha256"] and fm.get("plane_k_sha256") == hashes["plane_k_sha256"] and fm.get("unit_count") == 12 and fm.get("organization_cell_count") == 432 and fm.get("logical_model_call_count") == 1296 and fm.get("canonical_record_budget") == 6 and bool(re.fullmatch(r"[0-9a-f]{40}", candidate))
    gates["gate_9_evaluator_future_private_leakage_exclusion"] = PRIVATE_SENTINEL not in str(e) and PRIVATE_SENTINEL not in str(live) and "correct_action" not in str(e) and "correct_action" not in str(live)

    expected = {(u, r, g, a) for u in units for r in REPS for g in GENS for a in ARMS}; cmap = {}; duplicate = False
    for cell in live.get("cells", []):
        key = (str(cell["unit_id"]), str(cell["replicate"]), str(cell["generation"]), str(cell["arm"])); duplicate |= key in cmap; cmap[key] = cell
    complete = not duplicate and set(cmap) == expected and len(cmap) == 432

    turnover = True
    for uid, unit in units.items():
        for rep in REPS:
            prior: set[str] = set()
            for gen in GENS:
                vals = set(str(x) for x in unit["members"][rep][gen].values()); turnover &= len(vals) == 3 and not bool(vals & prior); prior |= vals
                for arm in ARMS:
                    cell = cmap.get((uid, rep, gen, arm)); turnover &= cell is not None and set(cell.get("analyst_member_ids", []) + [cell.get("chair_member_id", "")]) == vals
    gates["gate_2_complete_turnover_integrity"] = complete and turnover

    info = protocol = budget = isolated = refs = auth = audit = routine_state = True
    transport = complete and live.get("logical_model_call_count") == 1296 and live.get("model") == "glm-5-turbo"
    request_ids: set[str] = set(); call_count = 0; outcomes = {}; audit_rows = []
    for uid, rep, gen, arm in sorted(expected):
        cell = cmap.get((uid, rep, gen, arm))
        if cell is None: continue
        unit = units[uid]; rows = [dict(x) for x in e["canonical_evidence_sets"][f"{uid}:{gen}"]]; ids = [str(x["record_id"]) for x in rows]
        info &= cell.get("canonical_record_ids") == ids and len(ids) == 6
        parts = cell.get("analyst_partitions", [[], []]); info &= len(parts) == 2 and sorted(set(str(x) for p in parts for x in p)) == sorted(ids) and sum(len(p) for p in parts) == 6
        digest = routine_digest(str(unit["family"]), rows); info &= cell.get("routine_digest_reconstructible") == digest
        p = cell.get("protocol", {})
        if arm == "equal_compute_direct": protocol &= p.get("mode") == "neutral_peer_synthesis" and not p.get("role_binding") and not p.get("authority_governance") and "routine_digest" not in p
        elif arm == "roles_only": protocol &= p.get("mode") == "role_report_synthesis" and p.get("role_binding") is True and not p.get("authority_governance") and "routine_digest" not in p
        elif arm == "governed_static": protocol &= p.get("mode") == "governed_static" and p.get("authority_governance") is True and p.get("routine_state") == "reset_each_generation" and "routine_digest" not in p
        else: protocol &= p.get("mode") == "governed_persistent" and p.get("authority_governance") is True and p.get("routine_state") == "organization_owned_persistent" and p.get("routine_digest") == digest
        routine_state &= (arm == "governed_persistent") == ("routine_digest" in p)

        calls = [*cell.get("analyst_calls", []), cell.get("chair_call", {})]; budget &= len(cell.get("analyst_calls", [])) == 2 and bool(cell.get("chair_call")); call_count += len(calls)
        for i, call in enumerate(calls):
            transport &= call.get("model") == "glm-5-turbo" and int(call.get("output_tokens", 9999)) <= 96 and bool(call.get("attempt_log")) and call.get("attempt_log", [{}])[-1].get("status") == "ok"
            rid = str(call.get("request_id", "")); isolated &= bool(rid) and rid not in request_ids; request_ids.add(rid)
            cited = call.get("payload", {}).get("evidence_ids", []); allowed = set(ids if i == 2 else parts[i]); refs &= isinstance(cited, list) and all(str(x) in allowed for x in cited)
        budget &= len(calls) == 3
        chair = cell.get("chair_call", {}).get("payload", {}); action = str(chair.get("action", "")); notice = str(chair.get("notice_id", ""))
        v = ledger.verify(notice_id=notice, organization_id=str(unit["organization_id"]), scenario_id=f"{uid}-{gen}", action=f"execute:{uid}-{gen}").canonical_record(); auth &= cell.get("authority_verification") == v
        ack = cell.get("execution_acknowledgement", {}); chain = ack.get("organizational_cell_id") == cell.get("organizational_cell_id") and ack.get("selected_action") == action and ack.get("selected_notice_id") == notice and bool(ack.get("authority_verified")) == bool(v["verified"]); auth &= chain; audit &= chain
        correct = action == truth[uid] and bool(v["verified"]); outcomes[(uid, rep, gen, arm)] = correct
        audit_rows.append({"organizational_cell_id": cell.get("organizational_cell_id"), "unit_id": uid, "family": unit["family"], "replicate": rep, "generation": gen, "arm": arm, "canonical_record_ids": ids, "analyst_partitions": parts, "routine_digest": p.get("routine_digest") if arm == "governed_persistent" else None, "chair_action": action, "chair_notice_id": notice, "authority_verified": bool(v["verified"]), "authorized_correct": correct})

    gates["gate_3_canonical_information_equivalence"] = complete and info
    gates["gate_4_equal_compute_output_budget"] = complete and budget and call_count == 1296
    gates["gate_5_role_protocol_integrity"] = complete and protocol
    gates["gate_6_authority_separation"] = complete and auth
    gates["gate_7_model_call_isolation"] = complete and isolated and len(request_ids) == 1296
    gates["gate_8_live_transport_contract"] = transport and call_count == 1296
    gates["gate_10_evidence_reference_integrity"] = complete and refs

    counts = {g: {a: 0 for a in ARMS} for g in GENS}; fcounts: dict[str, dict[str, dict[str, int]]] = defaultdict(lambda: {g: {a: 0 for a in ARMS} for g in GENS})
    for (uid, _rep, gen, arm), ok in outcomes.items():
        if ok: counts[gen][arm] += 1; fcounts[str(units[uid]["family"])][gen][arm] += 1

    def contrast(a: str, b: str) -> dict[str, Any]:
        av = bv = w = l = 0
        for uid in sorted(units):
            for rep in REPS:
                x = bool(outcomes.get((uid, rep, "g3", a), False)); y = bool(outcomes.get((uid, rep, "g3", b), False)); av += int(x); bv += int(y); w += int(x and not y); l += int(y and not x)
        return {"paired_n": 36, "a_correct": av, "b_correct": bv, "difference": (av - bv) / 36, "discordant_a_wins": w, "discordant_b_wins": l, "raw_one_sided_p": exact_p(w, l)}

    contrasts = {"persistent_g3_vs_direct_g3": contrast("governed_persistent", "equal_compute_direct"), "persistent_g3_vs_static_g3": contrast("governed_persistent", "governed_static"), "persistent_g3_vs_roles_g3": contrast("governed_persistent", "roles_only")}
    h = holm({name: float(row["raw_one_sided_p"]) for name, row in contrasts.items()}); gates["gate_12_primary_confirmatory_superiority"] = all(float(contrasts[n]["difference"]) > 0 and bool(h["decisions"][n]["rejected"]) for n in contrasts)

    rp = rs = 0
    for uid, unit in units.items():
        if unit["family"] == "routine_transfer":
            for rep in REPS: rp += int(outcomes.get((uid, rep, "g3", "governed_persistent"), False)); rs += int(outcomes.get((uid, rep, "g3", "governed_static"), False))
    gates["gate_11_institutional_mechanism_consistency"] = rp > rs and routine_state and auth
    rep_counts = {}; rep_ok = True
    for rep in REPS:
        pscore = sum(int(outcomes.get((uid, rep, "g3", "governed_persistent"), False)) for uid in units); dscore = sum(int(outcomes.get((uid, rep, "g3", "equal_compute_direct"), False)) for uid in units); rep_counts[rep] = {"governed_persistent": pscore, "equal_compute_direct": dscore}; rep_ok &= pscore > dscore
    gates["gate_13_replicate_direction_consistency"] = rep_ok
    gates["gate_14_causal_audit_chain"] = complete and audit and len(audit_rows) == 432

    result = {"schema": "h5-result-v0.1", "scientific_claim": "registered_institutional_mediation_only", "classification": FAIL, "gates": gates, "diagnostics": {"unit_count": 12, "generation_count": 3, "replicate_count": 3, "organization_cell_count": 432, "logical_model_call_count": call_count, "physical_provider_attempt_count": live.get("physical_provider_attempt_count"), "correctness_counts_out_of_36": counts, "family_correctness_counts_out_of_12": {x: y for x, y in sorted(fcounts.items())}, "primary_contrasts": contrasts, "holm": h, "replicate_g3_counts_out_of_12": rep_counts, "routine_transfer_g3_counts_out_of_12": {"governed_persistent": rp, "governed_static": rs}, "production_historical_substrate_enabled": False, "pre_key_live_output_sha256": hashes["live_output_sha256"]}}
    manifest = {"schema": "h5-manifest-v0.1", "candidate_head": candidate, "world_preregistered_base": WORLD_BASE, "contextgraph_release_commit": CG, "preregistration_issue": 152, "model": "glm-5-turbo", **hashes, "production_historical_substrate_enabled": False, "reproducibility_contract": "two-isolated-evaluator-runs-over-one-frozen-live-output"}
    audit_doc = {"schema": "h5-audit-v0.1", "candidate_head": candidate, "cell_count": len(audit_rows), "cells": audit_rows}
    return result, manifest, audit_doc
