#!/usr/bin/env python3
"""Evaluate preregistered H1 exact acceptance gates."""
# ruff: noqa: E501
from __future__ import annotations

import argparse
from pathlib import Path

from h1_accept_core import BASE, CG, FAIL, H0, PASS, RECORD_KEYS, REPRO, audit, cb, corpus_sha, ids, load, semantic, sha
from resonance_world.historical_substrate import HISTORICAL_ACCESS_DEFAULT_ENABLED, HISTORICAL_FORBIDDEN_CONSUMERS, HistoricalAccessForbidden


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--lock-verification", required=True, type=Path)
    p.add_argument("--corpus-root", required=True, type=Path)
    p.add_argument("--researcher-output", required=True, type=Path)
    p.add_argument("--pre-key-manifest", required=True, type=Path)
    p.add_argument("--candidate-head", required=True)
    p.add_argument("--output-dir", required=True, type=Path)
    a = p.parse_args()
    lock = load(a.lock_verification)
    e = load(a.corpus_root / "plane_e/evidence.json")
    k = load(a.corpus_root / "plane_k/evaluator.json")
    rpath = a.researcher_output / "h1-researcher-output.json"
    r = load(rpath)
    pre = load(a.pre_key_manifest)
    actual = {str(x["unit_id"]): x for x in r["units"]}
    public = {str(x["unit_id"]): x for x in e["units"]}
    keys = {str(x["unit_id"]): x for x in k["units"]}
    sets = set(actual) == set(public) == set(keys)
    source_sha = corpus_sha([dict(x) for x in e["evidence_records"]])
    corpus = r["corpus"]
    corpus_ok = (
        corpus["flat_source_sha256"] == source_sha == corpus["structured_decoded_source_sha256"]
        and corpus["flat_source_record_count"] == 130
        and corpus["contextgraph_claim_count"] == 130
        and corpus["structured_decoded_record_count"] == 130
    )
    sent = {x["consumer"]: x["status"] for x in r["direct_edge_sentinels"]}
    runtime_ok = set(sent) == set(HISTORICAL_FORBIDDEN_CONSUMERS) and all(
        v == HistoricalAccessForbidden.code for v in sent.values()
    )
    denials = sets and all(
        x["no_history"]["history"]["query_denial"].get("status") == "historical_access_disabled"
        and x["no_history"]["history"]["query_denial"].get("bundle") is None
        for x in actual.values()
    )
    budget = neutral = critical = calibration = audit_ok = leakage = sets
    structured_correct = flat_correct = none_correct = neutral_n = critical_n = first = second = 0
    rbytes = rpath.read_bytes()
    forbidden = {
        "world_truth",
        "correct_action",
        "family",
        "inferred_authority",
        "prescribed_action",
        "hidden_private_sentinel",
    }
    if sets:
        for uid in sorted(actual):
            x, u, truth = actual[uid], public[uid], keys[uid]
            none = x["no_history"]
            flat = x["flat_history"]
            structured = x["structured_history"]
            fr = flat["normalized_records"]
            sr = structured["normalized_records"]
            if len(fr) != 2 or len(sr) != 2 or any(set(row) != RECORD_KEYS for row in fr + sr):
                budget = False
            if any(forbidden.intersection(row) for row in fr + sr):
                leakage = False
            if (
                flat["decision"]["controller_revision"] != structured["decision"]["controller_revision"]
                or flat["decision"]["actions"] != structured["decision"]["actions"]
                or flat["decision"]["actions"] != sorted(u["actions"])
            ):
                budget = False
            correct = str(truth["correct_action"])
            fa = str(flat["decision"]["chosen_action"])
            sa = str(structured["decision"]["chosen_action"])
            na = str(none["decision"]["chosen_action"])
            structured_correct += sa == correct
            flat_correct += fa == correct
            none_correct += na == correct
            actions = sorted(str(v) for v in u["actions"])
            first += correct == actions[0]
            second += correct == actions[1]
            family = str(truth["family"])
            if family == "f0":
                neutral_n += 1
                expected = list(truth["expected_relevant_record_ids"])
                if ids(flat) != expected or ids(structured) != expected or semantic(flat) != semantic(structured):
                    neutral = False
            elif family in {"f1", "f2"}:
                critical_n += 1
                if (
                    ids(flat) != list(truth["expected_flat_record_ids"])
                    or ids(structured) != list(truth["expected_structured_record_ids"])
                    or sa != correct
                    or fa == correct
                ):
                    critical = False
            else:
                neutral = critical = False
            if none["normalized_records"] != [] or na != str(truth["expected_no_history_action"]):
                calibration = False
            audit_ok = (
                audit_ok
                and audit(none, "none")
                and audit(flat, "flat")
                and audit(structured, "structured")
            )
            if str(truth["future_record_id"]).encode() in rbytes:
                leakage = False
            if str(truth["hidden_private_sentinel"]).encode() in rbytes:
                leakage = False
    prekey = all(
        sha(a.researcher_output / name) == digest for name, digest in pre["files"].items()
    )
    calibration = calibration and first == 15 and second == 15 and prekey
    gates = {
        "gate_0_h0_safety_boundary_preserved": (
            HISTORICAL_ACCESS_DEFAULT_ENABLED is False and runtime_ok and denials
        ),
        "gate_1_corpus_informational_equivalence": bool(lock.get("all_match")) and corpus_ok,
        "gate_2_delivered_budget_controller_parity": budget,
        "gate_3_structure_neutral_parity": neutral and neutral_n == 10,
        "gate_4_structure_critical_retrieval_correctness": critical and critical_n == 20,
        "gate_5_no_history_calibration_answer_key_independence": calibration,
        "gate_6_causal_audit_chain_integrity": audit_ok,
        "gate_7_hidden_future_authority_exclusion": leakage,
        "gate_8_exact_head_reproducibility_contract": len(a.candidate_head) == 40,
    }
    classification = PASS if all(gates.values()) else FAIL
    result = {
        "schema": "h1-result-v0.1",
        "classification": classification,
        "scientific_claim": "registered_structured_bounded_history_value_only",
        "production_historical_substrate_enabled": False,
        "gates": gates,
        "diagnostics": {
            "unit_count": len(actual),
            "neutral_unit_count": neutral_n,
            "structure_critical_unit_count": critical_n,
            "structured_correct_count": structured_correct,
            "flat_correct_count": flat_correct,
            "no_history_correct_count": none_correct,
            "corpus_informational_equivalence": corpus_ok,
            "runtime_history_boundary_rejections": runtime_ok,
            "pre_key_hashes_unchanged": prekey,
            "correct_action_lexicographic_balance": [first, second],
        },
    }
    manifest = {
        "schema": "h1-manifest-v0.1",
        "candidate_head": a.candidate_head,
        "world_preregistered_base": BASE,
        "h0_accepted_head": H0,
        "contextgraph_release_commit": CG,
        "apparatus_lock_verification_sha256": sha(a.lock_verification),
        "pre_key_manifest_sha256": sha(a.pre_key_manifest),
        "researcher_output_sha256": sha(rpath),
        "reproducibility_contract": REPRO,
        "production_historical_substrate_enabled": False,
    }
    a.output_dir.mkdir(parents=True, exist_ok=True)
    result_path = a.output_dir / "h1-result.json"
    result_path.write_bytes(cb(result))
    manifest["authoritative_result_sha256"] = sha(result_path)
    (a.output_dir / "h1-manifest.json").write_bytes(cb(manifest))
    return 0 if classification == PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())
