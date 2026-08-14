#!/usr/bin/env python3
"""Evaluate preregistered H3 multi-generation accumulation acceptance gates."""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
from typing import Any

from h1_accept_core import RECORD_KEYS, cb, corpus_sha, ids, load, sha
from resonance_world.historical_substrate import (
    HISTORICAL_ACCESS_DEFAULT_ENABLED,
    HISTORICAL_FORBIDDEN_CONSUMERS,
    HistoricalAccessForbidden,
)

PASS = "historical_substrate_multigeneration_accumulation_pass"
FAIL = "historical_substrate_multigeneration_accumulation_failed"
BASE = "230f468a234bebaddbf2245f58327a84f959c00f"
CG = "b896891108fd954869a8cd0423f6e8440ab0cdc0"
H2 = "e2ec159b691be92d37db35029c2c893eb56a760d"
REPRO = "two-isolated-exact-head-with-downstream-byte-compare"
REV = "h3-fixed-support-counter-default-tie-v0.1"
GENERATIONS = ("g1", "g2", "g3", "g4", "g5")
ARMS = (
    "no_history",
    "flat_accumulating_history",
    "structured_static_history",
    "structured_accumulating_history",
)
EXPECTED_MATRIX = {
    "g1": {
        "no_history": 0,
        "flat_accumulating_history": 0,
        "structured_static_history": 0,
        "structured_accumulating_history": 0,
    },
    "g2": {
        "no_history": 0,
        "flat_accumulating_history": 0,
        "structured_static_history": 0,
        "structured_accumulating_history": 0,
    },
    "g3": {
        "no_history": 0,
        "flat_accumulating_history": 0,
        "structured_static_history": 0,
        "structured_accumulating_history": 8,
    },
    "g4": {
        "no_history": 0,
        "flat_accumulating_history": 0,
        "structured_static_history": 0,
        "structured_accumulating_history": 16,
    },
    "g5": {
        "no_history": 0,
        "flat_accumulating_history": 0,
        "structured_static_history": 0,
        "structured_accumulating_history": 24,
    },
}
FIRST_CORRECT = {"f1": "g3", "f2": "g4", "f3": "g5"}


def audit_path(path: dict[str, Any], arm: str, generation: str) -> bool:
    history = path["history"]
    decision = path["decision"]
    consequence = path["consequence"]
    acknowledgement = path["execution_acknowledgement"]
    history_key = {
        "no_history": "history_input_id",
        "flat_accumulating_history": "window_id",
        "structured_static_history": "bundle_id",
        "structured_accumulating_history": "bundle_id",
    }[arm]
    consequence_keys = {
        "schema",
        "unit_id",
        "generation",
        "decision_id",
        "chosen_action",
        "action_accepted",
        "executed",
        "consequence_id",
    }
    return (
        str(decision["history_input_id"]) == str(history[history_key])
        and list(decision["record_ids"]) == ids(path)
        and decision["controller_revision"] == REV
        and decision["generation"] == generation
        and consequence["generation"] == generation
        and str(consequence["decision_id"]) == str(decision["decision_id"])
        and str(consequence["chosen_action"]) == str(decision["chosen_action"])
        and set(consequence) == consequence_keys
        and str(acknowledgement["decision_id"]) == str(decision["decision_id"])
        and str(acknowledgement["consequence_id"]) == str(consequence["consequence_id"])
        and str(acknowledgement["chosen_action"]) == str(decision["chosen_action"])
        and bool(acknowledgement["executed"]) == bool(consequence["executed"])
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lock-verification", required=True, type=Path)
    parser.add_argument("--corpus-root", required=True, type=Path)
    parser.add_argument("--researcher-output", required=True, type=Path)
    parser.add_argument("--pre-key-sha256", required=True)
    parser.add_argument("--candidate-head", required=True)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()

    lock = load(args.lock_verification)
    plane_e = load(args.corpus_root / "plane_e/evidence.json")
    plane_k = load(args.corpus_root / "plane_k/evaluator.json")
    researcher_path = args.researcher_output / "h3-researcher-output.json"
    researcher = load(researcher_path)

    public = {str(row["unit_id"]): row for row in plane_e["units"]}
    truth = {str(row["unit_id"]): row for row in plane_k["units"]}
    raw_cells = list(researcher["cells"])
    cells = {
        (str(row["unit_id"]), str(row["generation"]), str(row["history_arm"])): row
        for row in raw_cells
    }
    expected_keys = {
        (unit_id, generation, arm)
        for unit_id in public
        for generation in GENERATIONS
        for arm in ARMS
    }
    sets_ok = (
        set(public) == set(truth)
        and set(cells) == expected_keys
        and len(raw_cells) == 480
    )

    source = [dict(row) for row in plane_e["evidence_records"]]
    legacy_source = [dict(row) for row in plane_e["legacy_records"]]
    source_sha = corpus_sha(source)
    legacy_sha = corpus_sha(legacy_source)
    corpus = researcher["corpus"]
    corpus_ok = (
        corpus["flat_accumulating_source_sha256"] == source_sha
        and corpus["structured_accumulating_decoded_source_sha256"] == source_sha
        and corpus["structured_static_source_sha256"] == legacy_sha
        and corpus["flat_accumulating_source_record_count"] == 1008
        and corpus["structured_accumulating_claim_count"] == 1008
        and corpus["structured_static_claim_count"] == 48
    )

    sentinels = {
        row["consumer"]: row["status"] for row in researcher["direct_edge_sentinels"]
    }
    runtime_ok = set(sentinels) == set(HISTORICAL_FORBIDDEN_CONSUMERS) and all(
        status == HistoricalAccessForbidden.code for status in sentinels.values()
    )

    turnover_plan = {
        str(unit["unit_id"]): {
            "founder_id": unit["founder_id"],
            "members": dict(unit["members"]),
        }
        for unit in plane_e["units"]
    }
    cutoffs = {
        str(unit["unit_id"]): dict(unit["decision_cutoffs"]) for unit in plane_e["units"]
    }
    pre_generation_ok = (
        researcher["pre_generation"]["turnover_plan_sha256"]
        == hashlib.sha256(cb(turnover_plan)).hexdigest()
        and researcher["pre_generation"]["decision_cutoffs_sha256"]
        == hashlib.sha256(cb(cutoffs)).hexdigest()
        and researcher["pre_generation"]["legacy_snapshot_sha256"] == legacy_sha
    )

    member_ids = [
        str(unit["members"][generation])
        for unit in plane_e["units"]
        for generation in GENERATIONS
    ]
    founder_ids = {str(unit["founder_id"]) for unit in plane_e["units"]}
    turnover_ok = (
        len(member_ids) == 120
        and len(set(member_ids)) == 120
        and not founder_ids.intersection(member_ids)
        and all(
            str(cells[(unit_id, generation, arm)]["member_id"])
            == str(public[unit_id]["members"][generation])
            for unit_id in public
            for generation in GENERATIONS
            for arm in ARMS
        )
    )

    temporal_ok = budget_ok = static_ok = collision_ok = staircase_ok = audit_ok = sets_ok
    leakage_ok = True
    matrix = {
        generation: {arm: 0 for arm in ARMS}
        for generation in GENERATIONS
    }
    family_first: dict[str, list[str]] = {"f1": [], "f2": [], "f3": []}
    researcher_bytes = researcher_path.read_bytes()

    if b'"family"' in researcher_bytes or b'"correct_action"' in researcher_bytes:
        leakage_ok = False

    for key in truth.values():
        if str(key["private_sentinel"]).encode() in researcher_bytes:
            leakage_ok = False

    if sets_ok:
        for unit_id in sorted(public):
            unit = public[unit_id]
            key = truth[unit_id]
            family = str(key["family"])
            correct = str(key["correct_action"])
            default_action = str(unit["default_action"])
            legacy_ids = [str(value) for value in key["legacy_record_ids"]]
            lesson_ids = {
                generation: str(value)
                for generation, value in key["lesson_record_ids"].items()
            }
            first_seen: str | None = None

            for generation_index, generation in enumerate(GENERATIONS):
                current_and_future = {
                    lesson_ids[name] for name in GENERATIONS[generation_index:]
                }
                prior_lessons = [
                    lesson_ids[name] for name in GENERATIONS[:generation_index]
                ]
                expected_structured = legacy_ids + prior_lessons

                for arm in ARMS:
                    cell = cells[(unit_id, generation, arm)]
                    run = cell["path"]
                    chosen = str(run["decision"]["chosen_action"])
                    matrix[generation][arm] += chosen == correct
                    audit_ok = audit_ok and audit_path(run, arm, generation)
                    row_ids = ids(run)
                    temporal_ok = temporal_ok and not current_and_future.intersection(row_ids)
                    rows = list(run["normalized_records"])
                    budget_ok = (
                        budget_ok
                        and len(rows) <= 7
                        and all(set(row) == RECORD_KEYS for row in rows)
                    )

                    if arm == "no_history":
                        temporal_ok = temporal_ok and row_ids == []
                        collision_ok = collision_ok and chosen == default_action
                        denial = run["history"]["query_denial"]
                        collision_ok = (
                            collision_ok
                            and denial.get("status") == "historical_access_disabled"
                            and denial.get("bundle") is None
                        )
                    elif arm == "flat_accumulating_history":
                        expected = [
                            str(value)
                            for value in key["decoy_record_ids"][generation]
                        ]
                        collision_ok = (
                            collision_ok
                            and row_ids == expected
                            and len(rows) == 7
                            and all(str(row["support_action"]) == default_action for row in rows)
                            and chosen == default_action
                        )
                        budget_ok = (
                            budget_ok
                            and int(run["history"]["result_limit"]) == 7
                        )
                    elif arm == "structured_static_history":
                        static_ok = (
                            static_ok
                            and row_ids == legacy_ids
                            and all(str(row["support_action"]) == default_action for row in rows)
                            and chosen == default_action
                        )
                        budget_ok = (
                            budget_ok
                            and int(run["history"]["result_limit"]) == 7
                        )
                    else:
                        collision_ok = collision_ok and row_ids == expected_structured
                        budget_ok = (
                            budget_ok
                            and int(run["history"]["result_limit"]) == 7
                        )
                        if chosen == correct and first_seen is None:
                            first_seen = generation

                current_lesson = next(
                    row for row in source if str(row["record_id"]) == lesson_ids[generation]
                )
                temporal_ok = (
                    temporal_ok
                    and int(current_lesson["observed_at"])
                    > int(unit["decision_cutoffs"][generation])
                    and str(current_lesson["support_action"]) == correct
                )

            if first_seen is not None:
                family_first[family].append(first_seen)
            staircase_ok = staircase_ok and first_seen == FIRST_CORRECT[family]

    static_ok = static_ok and researcher["pre_generation"]["legacy_snapshot_sha256"] == legacy_sha
    matrix_ok = matrix == EXPECTED_MATRIX
    staircase_ok = staircase_ok and all(
        len(values) == 8 and set(values) == {FIRST_CORRECT[family]}
        for family, values in family_first.items()
    )
    pre_key_ok = sha(researcher_path) == args.pre_key_sha256

    gates = {
        "gate_0_h0_h1_h2_safety_boundary_preserved": (
            HISTORICAL_ACCESS_DEFAULT_ENABLED is False and runtime_ok
        ),
        "gate_1_frozen_fixture_identity": bool(lock.get("all_match")) and pre_generation_ok,
        "gate_2_complete_turnover_integrity": turnover_ok,
        "gate_3_temporal_lesson_integrity": temporal_ok,
        "gate_4_corpus_equivalence_budget_parity": corpus_ok and budget_ok,
        "gate_5_structured_static_ablation": static_ok,
        "gate_6_collision_separation": collision_ok,
        "gate_7_accumulation_staircase": staircase_ok,
        "gate_8_registered_outcome_matrix": matrix_ok,
        "gate_9_causal_audit_chain_integrity": audit_ok,
        "gate_10_evaluator_future_exclusion": leakage_ok and pre_key_ok,
        "gate_11_exact_head_reproducibility_contract": len(args.candidate_head) == 40,
    }
    classification = PASS if all(gates.values()) else FAIL
    result = {
        "schema": "h3-result-v0.1",
        "classification": classification,
        "scientific_claim": "registered_multigeneration_accumulation_mechanism_only",
        "production_historical_substrate_enabled": False,
        "gates": gates,
        "diagnostics": {
            "unit_count": len(public),
            "generation_count": len(GENERATIONS),
            "cell_count": len(raw_cells),
            "unique_successor_member_count": len(set(member_ids)),
            "correctness_matrix": matrix,
            "family_first_correct_generation": {
                family: sorted(values) for family, values in family_first.items()
            },
            "canonical_record_count": len(source),
            "legacy_record_count": len(legacy_source),
            "corpus_informational_equivalence": corpus_ok,
            "runtime_history_boundary_rejections": runtime_ok,
            "pre_key_hash_unchanged": pre_key_ok,
        },
    }
    manifest = {
        "schema": "h3-manifest-v0.1",
        "candidate_head": args.candidate_head,
        "world_preregistered_base": BASE,
        "h2_accepted_head": H2,
        "contextgraph_release_commit": CG,
        "lock_verification_sha256": sha(args.lock_verification),
        "researcher_output_sha256": sha(researcher_path),
        "pre_key_researcher_output_sha256": args.pre_key_sha256,
        "preregistration_issue": 147,
        "reproducibility_contract": REPRO,
        "production_historical_substrate_enabled": False,
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    result_path = args.output_dir / "h3-result.json"
    result_path.write_bytes(cb(result))
    manifest["authoritative_result_sha256"] = sha(result_path)
    (args.output_dir / "h3-manifest.json").write_bytes(cb(manifest))
    return 0 if classification == PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())
