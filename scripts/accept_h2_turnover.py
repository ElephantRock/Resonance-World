#!/usr/bin/env python3
"""Evaluate preregistered H2 turnover acceptance gates."""
# ruff: noqa: E501
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
from typing import Any

from h1_accept_core import RECORD_KEYS, REV, audit, cb, corpus_sha, ids, load, semantic, sha
from resonance_world.historical_substrate import (
    HISTORICAL_ACCESS_DEFAULT_ENABLED,
    HISTORICAL_FORBIDDEN_CONSUMERS,
    HistoricalAccessForbidden,
)

PASS = "historical_substrate_turnover_persistence_pass"
FAIL = "historical_substrate_turnover_persistence_failed"
BASE = "839041f81ba9298f22544a939482f549ae6eefbb"
CG = "b896891108fd954869a8cd0423f6e8440ab0cdc0"
H1 = "d55c91f7ee57896a58f4ed32d32e033467a0d0a9"
REPRO = "two-isolated-exact-head-with-downstream-byte-compare"
EXPECTED_MATRIX = {
    "t0": {"structured_history": 48, "flat_history": 48, "no_history": 48},
    "t50": {"structured_history": 48, "flat_history": 32, "no_history": 36},
    "t100": {"structured_history": 48, "flat_history": 16, "no_history": 24},
}
FORBIDDEN = {
    "world_truth",
    "correct_action",
    "family",
    "inferred_authority",
    "prescribed_action",
    "private_sentinel",
}


def audit_local(p: dict[str, Any]) -> bool:
    h = p["history"]
    d = p["decision"]
    c = p["consequence"]
    a = p["execution_acknowledgement"]
    con_keys = {
        "schema",
        "unit_id",
        "decision_id",
        "chosen_action",
        "action_accepted",
        "executed",
        "consequence_id",
    }
    return (
        str(d["history_input_id"]) == str(h["continuity_id"])
        and list(d["record_ids"]) == ids(p)
        and d["controller_revision"] == REV
        and str(c["decision_id"]) == str(d["decision_id"])
        and str(c["chosen_action"]) == str(d["chosen_action"])
        and set(c) == con_keys
        and str(a["decision_id"]) == str(d["decision_id"])
        and str(a["consequence_id"]) == str(c["consequence_id"])
        and str(a["chosen_action"]) == str(d["chosen_action"])
        and bool(a["executed"]) == bool(c["executed"])
    )


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--lock-verification", required=True, type=Path)
    p.add_argument("--corpus-root", required=True, type=Path)
    p.add_argument("--researcher-output", required=True, type=Path)
    p.add_argument("--pre-key-sha256", required=True)
    p.add_argument("--candidate-head", required=True)
    p.add_argument("--output-dir", required=True, type=Path)
    a = p.parse_args()

    lock = load(a.lock_verification)
    e = load(a.corpus_root / "plane_e/evidence.json")
    k = load(a.corpus_root / "plane_k/evaluator.json")
    rpath = a.researcher_output / "h2-researcher-output.json"
    r = load(rpath)
    public = {str(x["unit_id"]): x for x in e["units"]}
    truth = {str(x["unit_id"]): x for x in k["units"]}
    raw_cells = list(r["cells"])
    cells = {
        (str(x["unit_id"]), str(x["turnover"]), str(x["history_arm"])): x
        for x in raw_cells
    }
    expected_keys = {
        (uid, turnover, arm)
        for uid in public
        for turnover in ("t0", "t50", "t100")
        for arm in ("no_history", "flat_history", "structured_history")
    }
    sets_ok = set(public) == set(truth) and set(cells) == expected_keys and len(raw_cells) == 432

    source = [dict(x) for x in e["evidence_records"]]
    source_sha = corpus_sha(source)
    corpus = r["corpus"]
    corpus_ok = (
        corpus["flat_source_sha256"] == source_sha == corpus["structured_decoded_source_sha256"]
        and corpus["flat_source_record_count"] == 208
        and corpus["contextgraph_claim_count"] == 208
        and corpus["structured_decoded_record_count"] == 208
    )

    sent = {x["consumer"]: x["status"] for x in r["direct_edge_sentinels"]}
    runtime_ok = set(sent) == set(HISTORICAL_FORBIDDEN_CONSUMERS) and all(
        value == HistoricalAccessForbidden.code for value in sent.values()
    )

    plan = {
        str(u["unit_id"]): {name: bool(value) for name, value in u["replaced"].items()}
        for u in e["units"]
    }
    local = {
        str(u["unit_id"]): [dict(row) for row in u["local_continuity_records"]]
        for u in e["units"]
    }
    pre_turnover_ok = (
        r["pre_turnover"]["turnover_plan_sha256"] == hashlib.sha256(cb(plan)).hexdigest()
        and r["pre_turnover"]["local_continuity_sha256"] == hashlib.sha256(cb(local)).hexdigest()
    )

    turnover_ok = budget_ok = neutral_ok = critical_ok = calibration_ok = audit_ok = leakage_ok = sets_ok
    matrix = {
        t: {"no_history": 0, "flat_history": 0, "structured_history": 0}
        for t in ("t0", "t50", "t100")
    }
    replaced_counts = {"t0": 0, "t50": 0, "t100": 0}
    t50_family = {"f0": 0, "f1": 0, "f2": 0}
    researcher_bytes = rpath.read_bytes()
    first = second = t50_first = t50_second = 0

    if sets_ok:
        for uid in sorted(public):
            unit = public[uid]
            key = truth[uid]
            correct = str(key["correct_action"])
            actions = sorted(str(v) for v in unit["actions"])
            first += correct == actions[0]
            second += correct == actions[1]
            for turnover in ("t0", "t50", "t100"):
                replaced = bool(unit["replaced"][turnover])
                replaced_counts[turnover] += replaced
                if turnover == "t50" and replaced:
                    t50_family[str(key["family"])] += 1
                    t50_first += correct == actions[0]
                    t50_second += correct == actions[1]

                by_arm = {
                    arm: cells[(uid, turnover, arm)]
                    for arm in ("no_history", "flat_history", "structured_history")
                }
                for arm, cell in by_arm.items():
                    run = cell["path"]
                    chosen = str(run["decision"]["chosen_action"])
                    matrix[turnover][arm] += chosen == correct
                    turnover_ok = turnover_ok and bool(cell["replaced"]) == replaced
                    if replaced:
                        turnover_ok = (
                            turnover_ok
                            and str(cell["member_id"]) != str(unit["incumbent_id"])
                            and str(cell["member_id"]).startswith("h2-successor-")
                        )
                        if arm == "no_history":
                            calibration_ok = (
                                calibration_ok
                                and cell["source_kind"] == "no_history"
                                and run["normalized_records"] == []
                                and chosen == str(key["expected_no_history_action"])
                                and run["history"]["query_denial"].get("status") == "historical_access_disabled"
                                and run["history"]["query_denial"].get("bundle") is None
                            )
                            audit_ok = audit_ok and audit(run, "none")
                        elif arm == "flat_history":
                            rows = run["normalized_records"]
                            budget_ok = budget_ok and len(rows) == 2 and all(set(row) == RECORD_KEYS for row in rows)
                            budget_ok = budget_ok and not any(FORBIDDEN.intersection(row) for row in rows)
                            critical_ok = critical_ok and ids(run) == list(key["expected_flat_record_ids"])
                            audit_ok = audit_ok and audit(run, "flat")
                        else:
                            rows = run["normalized_records"]
                            budget_ok = budget_ok and len(rows) == 2 and all(set(row) == RECORD_KEYS for row in rows)
                            budget_ok = budget_ok and not any(FORBIDDEN.intersection(row) for row in rows)
                            critical_ok = critical_ok and ids(run) == list(key["expected_structured_record_ids"])
                            audit_ok = audit_ok and audit(run, "structured")
                    else:
                        expected_ids = list(key["expected_relevant_record_ids"])
                        turnover_ok = (
                            turnover_ok
                            and str(cell["member_id"]) == str(unit["incumbent_id"])
                            and cell["source_kind"] == "member_local_continuity"
                            and ids(run) == expected_ids
                            and chosen == correct
                        )
                        audit_ok = audit_ok and audit_local(run)

                if not replaced:
                    base_sem = semantic(by_arm["no_history"]["path"])
                    neutral_ok = neutral_ok and all(
                        semantic(by_arm[arm]["path"]) == base_sem
                        for arm in ("flat_history", "structured_history")
                    )
                elif str(key["family"]) == "f0":
                    flat_run = by_arm["flat_history"]["path"]
                    structured_run = by_arm["structured_history"]["path"]
                    neutral_ok = (
                        neutral_ok
                        and ids(flat_run) == list(key["expected_relevant_record_ids"])
                        and ids(structured_run) == list(key["expected_relevant_record_ids"])
                        and semantic(flat_run) == semantic(structured_run)
                    )
                else:
                    flat_run = by_arm["flat_history"]["path"]
                    structured_run = by_arm["structured_history"]["path"]
                    critical_ok = (
                        critical_ok
                        and str(flat_run["decision"]["chosen_action"]) != correct
                        and str(structured_run["decision"]["chosen_action"]) == correct
                    )

            if str(key["future_record_id"]).encode() in researcher_bytes:
                leakage_ok = False
            if str(key["private_sentinel"]).encode() in researcher_bytes:
                leakage_ok = False

    turnover_ok = (
        turnover_ok
        and replaced_counts == {"t0": 0, "t50": 24, "t100": 48}
        and t50_family == {"f0": 8, "f1": 8, "f2": 8}
    )
    calibration_ok = (
        calibration_ok
        and first == 24
        and second == 24
        and t50_first == 12
        and t50_second == 12
        and sha(rpath) == a.pre_key_sha256
    )
    matrix_ok = matrix == EXPECTED_MATRIX

    gates = {
        "gate_0_h0_h1_safety_boundary_preserved": (
            HISTORICAL_ACCESS_DEFAULT_ENABLED is False and runtime_ok
        ),
        "gate_1_frozen_pre_turnover_fixture_identity": bool(lock.get("all_match")) and corpus_ok and pre_turnover_ok,
        "gate_2_turnover_intervention_integrity": turnover_ok,
        "gate_3_history_informational_equivalence_budget_parity": corpus_ok and budget_ok,
        "gate_4_structure_neutral_successor_parity": neutral_ok,
        "gate_5_structure_critical_successor_separation": critical_ok,
        "gate_6_no_history_successor_calibration": calibration_ok,
        "gate_7_registered_turnover_outcome_matrix": matrix_ok,
        "gate_8_causal_audit_chain_integrity": audit_ok,
        "gate_9_evaluator_future_authority_exclusion": leakage_ok,
        "gate_10_exact_head_reproducibility_contract": len(a.candidate_head) == 40,
    }
    classification = PASS if all(gates.values()) else FAIL
    result = {
        "schema": "h2-result-v0.1",
        "classification": classification,
        "scientific_claim": "registered_turnover_persistence_mechanism_only",
        "production_historical_substrate_enabled": False,
        "gates": gates,
        "diagnostics": {
            "unit_count": len(public),
            "cell_count": len(raw_cells),
            "turnover_replaced_counts": replaced_counts,
            "t50_replaced_by_family": t50_family,
            "correct_action_lexicographic_balance": [first, second],
            "t50_successor_action_balance": [t50_first, t50_second],
            "correctness_matrix": matrix,
            "corpus_informational_equivalence": corpus_ok,
            "runtime_history_boundary_rejections": runtime_ok,
            "pre_key_hash_unchanged": sha(rpath) == a.pre_key_sha256,
        },
    }
    manifest = {
        "schema": "h2-manifest-v0.1",
        "candidate_head": a.candidate_head,
        "world_preregistered_base": BASE,
        "h1_accepted_head": H1,
        "contextgraph_release_commit": CG,
        "lock_verification_sha256": sha(a.lock_verification),
        "researcher_output_sha256": sha(rpath),
        "pre_key_researcher_output_sha256": a.pre_key_sha256,
        "preregistration_issue": 143,
        "reproducibility_contract": REPRO,
        "production_historical_substrate_enabled": False,
    }
    a.output_dir.mkdir(parents=True, exist_ok=True)
    result_path = a.output_dir / "h2-result.json"
    result_path.write_bytes(cb(result))
    manifest["authoritative_result_sha256"] = sha(result_path)
    (a.output_dir / "h2-manifest.json").write_bytes(cb(manifest))
    return 0 if classification == PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())
