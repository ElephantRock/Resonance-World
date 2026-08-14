#!/usr/bin/env python3
"""Evaluate frozen H4 live outputs against the preregistered gates."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from h1_runtime_core import cb, sentinels
from run_h4_stochastic import MODEL, prepare

EXPECTED_PLANE_E_SHA = "e2c0a4735c38abff803d2eab2ab872ed296ca01d48165a28f6f5541a2b28191b"
EXPECTED_PLANE_K_SHA = "4800f93d01fd0a88abbe62140aa6e73160f0102720d7c946ac0d4e4d3d2e82f2"
EXPECTED_FIXTURE_MANIFEST_SHA = "9758f65f18bfd63de98b11a8d7b6334bdd6b66f196e904668518bb9571fb69a2"
PASS = "historical_substrate_stochastic_successor_reasoning_pass"
FAIL = "historical_substrate_stochastic_successor_reasoning_failed"


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError("expected JSON object")
    return value


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def exact_one_sided_discordance(
    first: list[bool],
    second: list[bool],
) -> dict[str, Any]:
    if len(first) != len(second):
        raise ValueError("paired vectors differ")
    wins = sum(a and not b for a, b in zip(first, second, strict=True))
    losses = sum((not a) and b for a, b in zip(first, second, strict=True))
    discordant = wins + losses
    if discordant == 0:
        p_value = 1.0
    else:
        p_value = sum(
            math.comb(discordant, k) for k in range(wins, discordant + 1)
        ) / (2**discordant)
    return {
        "paired_n": len(first),
        "a_correct": sum(first),
        "b_correct": sum(second),
        "difference": (sum(first) - sum(second)) / len(first),
        "discordant_a_wins": wins,
        "discordant_b_wins": losses,
        "raw_one_sided_p": p_value,
    }


def holm(
    results: dict[str, dict[str, Any]],
    alpha: float = 0.05,
) -> dict[str, Any]:
    ordered_names = sorted(
        results,
        key=lambda name: (float(results[name]["raw_one_sided_p"]), name),
    )
    decisions: dict[str, dict[str, Any]] = {}
    still_rejecting = True
    comparison_count = len(ordered_names)
    for rank, name in enumerate(ordered_names, start=1):
        threshold = alpha / (comparison_count - rank + 1)
        p_value = float(results[name]["raw_one_sided_p"])
        rejected = still_rejecting and p_value <= threshold
        decisions[name] = {
            "rank": rank,
            "threshold": threshold,
            "rejected": rejected,
        }
        if not rejected:
            still_rejecting = False
    return {
        "alpha": alpha,
        "method": "Holm",
        "order": ordered_names,
        "decisions": decisions,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plane-e", required=True, type=Path)
    parser.add_argument("--plane-k", required=True, type=Path)
    parser.add_argument("--fixture-manifest", required=True, type=Path)
    parser.add_argument("--live-output", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--candidate-head", required=True)
    args = parser.parse_args()

    evidence = load(args.plane_e)
    evaluator = load(args.plane_k)
    fixture_manifest = load(args.fixture_manifest)
    live = load(args.live_output)
    expected_plan = prepare(evidence)
    correct = {
        str(row["unit_id"]): str(row["correct_action"])
        for row in evaluator["units"]
    }
    unit_map = {
        str(row["unit_id"]): dict(row)
        for row in evidence["units"]
    }
    expected_cells = {
        str(row["logical_cell_id"]): row
        for row in expected_plan["cells"]
    }
    live_cells = {
        str(row["logical_cell_id"]): row
        for row in live["cells"]
    }

    safety = (
        live.get("production_historical_substrate_enabled") is False
        and all(
            row["status"] == "historical_access_forbidden_consumer"
            for row in sentinels()
        )
    )

    action_positions = Counter(
        int(row["correct_position"])
        for row in evaluator["units"]
    )
    apparatus_identity = (
        sha(args.plane_e) == EXPECTED_PLANE_E_SHA
        and sha(args.plane_k) == EXPECTED_PLANE_K_SHA
        and sha(args.fixture_manifest) == EXPECTED_FIXTURE_MANIFEST_SHA
        and fixture_manifest.get("logical_cell_count") == 432
        and action_positions == Counter({0: 6, 1: 6})
        and evidence["model_contract"]
        == {
            "provider": "zai-chat-completions",
            "model": "glm-5-turbo",
            "endpoint": "https://api.z.ai/api/coding/paas/v4/chat/completions",
            "do_sample": True,
            "temperature": 0.8,
            "thinking": {"type": "disabled"},
            "stream": False,
            "response_format": {"type": "json_object"},
            "max_output_tokens": 96,
        }
    )

    member_ids = []
    turnover_ok = True
    for unit in evidence["units"]:
        for replicate in evidence["replicates"]:
            ids = [
                str(unit["members"][replicate][generation])
                for generation in evidence["generations"]
            ]
            turnover_ok &= len(ids) == len(set(ids))
            member_ids.extend(ids)
    turnover_ok &= len(member_ids) == len(set(member_ids))

    plan_equivalent = set(expected_cells) == set(live_cells)
    arm_integrity = True
    isolation = True
    for cell_id, expected in expected_cells.items():
        actual = live_cells.get(cell_id, {})
        for key in (
            "unit_id",
            "family",
            "replicate",
            "generation",
            "history_arm",
            "member_id",
            "organization_id",
            "predicate",
            "actions",
            "decision_cutoff",
            "delivered_records",
            "delivered_record_ids",
            "history_meta",
            "prompt_sha256",
        ):
            plan_equivalent &= actual.get(key) == expected.get(key)
        rows = expected["delivered_records"]
        arm = expected["history_arm"]
        unit = unit_map[str(expected["unit_id"])]
        if arm == "no_history":
            arm_integrity &= rows == []
        elif arm == "flat_accumulating_history":
            arm_integrity &= len(rows) == 6
            arm_integrity &= all(
                row["organization_id"] != unit["organization_id"]
                or row["predicate"] != unit["predicate"]
                for row in rows
            )
        elif arm == "structured_static_history":
            arm_integrity &= all(
                row["record_kind"] == "legacy_note"
                for row in rows
            )
        elif arm == "structured_accumulating_history":
            arm_integrity &= all(
                row["organization_id"] == unit["organization_id"]
                and row["predicate"] == unit["predicate"]
                and int(row["observed_at"])
                <= int(expected["decision_cutoff"])
                for row in rows
            )
        isolation &= "model_response" in actual
    corpus_parity = (
        live.get("canonical_corpus_sha256")
        == expected_plan["canonical_corpus_sha256"]
        and live.get("legacy_corpus_sha256")
        == expected_plan["legacy_corpus_sha256"]
        and plan_equivalent
    )

    request_ids: list[str] = []
    live_contract = len(live_cells) == 432
    for cell in live_cells.values():
        response = cell.get("model_response", {})
        live_contract &= response.get("model") == MODEL
        live_contract &= response.get("action") in cell.get("actions", [])
        attempts = response.get("attempt_log", [])
        live_contract &= (
            isinstance(attempts, list)
            and bool(attempts)
            and attempts[-1].get("status") == "ok"
        )
        request_ids.extend(
            str(row.get("request_id"))
            for row in attempts
        )
    live_contract &= len(request_ids) == len(set(request_ids))

    raw_live = args.live_output.read_text()
    leakage_ok = (
        "H4_PRIVATE_EVALUATOR_SENTINEL_9A71" not in raw_live
        and '"correct_action"' not in raw_live
    )
    for cell in live_cells.values():
        cutoff = int(cell["decision_cutoff"])
        leakage_ok &= all(
            int(row["observed_at"]) <= cutoff
            for row in cell["delivered_records"]
        )

    references_ok = True
    for cell in live_cells.values():
        delivered = set(cell["delivered_record_ids"])
        references = cell["model_response"]["evidence_ids"]
        references_ok &= set(references) <= delivered

    outcome: dict[tuple[str, str, str, str], bool] = {}
    counts = defaultdict(int)
    family_counts = defaultdict(int)
    for cell in live_cells.values():
        key = (
            cell["unit_id"],
            cell["replicate"],
            cell["generation"],
            cell["history_arm"],
        )
        is_correct = (
            str(cell["model_response"]["action"])
            == correct[str(cell["unit_id"])]
        )
        outcome[key] = is_correct
        counts[(cell["generation"], cell["history_arm"])] += int(is_correct)
        family_counts[
            (cell["family"], cell["generation"], cell["history_arm"])
        ] += int(is_correct)

    pairs = [
        (unit_id, replicate)
        for unit_id in sorted(unit_map)
        for replicate in evidence["replicates"]
    ]

    def vector(generation: str, arm: str) -> list[bool]:
        return [
            outcome[(unit_id, replicate, generation, arm)]
            for unit_id, replicate in pairs
        ]

    contrasts = {
        "structured_g3_vs_flat_g3": exact_one_sided_discordance(
            vector("g3", "structured_accumulating_history"),
            vector("g3", "flat_accumulating_history"),
        ),
        "structured_g3_vs_static_g3": exact_one_sided_discordance(
            vector("g3", "structured_accumulating_history"),
            vector("g3", "structured_static_history"),
        ),
        "structured_g3_vs_none_g3": exact_one_sided_discordance(
            vector("g3", "structured_accumulating_history"),
            vector("g3", "no_history"),
        ),
        "structured_g3_vs_structured_g1": exact_one_sided_discordance(
            vector("g3", "structured_accumulating_history"),
            vector("g1", "structured_accumulating_history"),
        ),
    }
    holm_result = holm(contrasts)
    primary_ok = all(
        float(result["difference"]) > 0
        and holm_result["decisions"][name]["rejected"]
        for name, result in contrasts.items()
    )

    replicate_counts: dict[str, dict[str, int]] = {}
    replicate_ok = True
    for replicate in evidence["replicates"]:
        structured = sum(
            outcome[
                (
                    unit_id,
                    replicate,
                    "g3",
                    "structured_accumulating_history",
                )
            ]
            for unit_id in unit_map
        )
        flat = sum(
            outcome[
                (
                    unit_id,
                    replicate,
                    "g3",
                    "flat_accumulating_history",
                )
            ]
            for unit_id in unit_map
        )
        replicate_counts[replicate] = {
            "structured_accumulating_history": structured,
            "flat_accumulating_history": flat,
        }
        replicate_ok &= structured > flat

    audit_rows = []
    causal_ok = len(outcome) == 432
    for cell_id in sorted(live_cells):
        cell = live_cells[cell_id]
        chosen = str(cell["model_response"]["action"])
        consequence = {
            "logical_cell_id": cell_id,
            "chosen_action": chosen,
            "correct": chosen == correct[str(cell["unit_id"])],
            "executed": chosen in cell["actions"],
        }
        consequence["consequence_id"] = (
            "h4-consequence-"
            + hashlib.sha256(cb(consequence)).hexdigest()[:24]
        )
        acknowledgement = {
            "logical_cell_id": cell_id,
            "consequence_id": consequence["consequence_id"],
            "executed": consequence["executed"],
        }
        acknowledgement["ack_id"] = (
            "h4-ack-"
            + hashlib.sha256(cb(acknowledgement)).hexdigest()[:24]
        )
        causal_ok &= (
            acknowledgement["consequence_id"]
            == consequence["consequence_id"]
            and consequence["executed"]
        )
        audit_rows.append(
            {
                "logical_cell_id": cell_id,
                "consequence": consequence,
                "execution_acknowledgement": acknowledgement,
            }
        )

    gates = {
        "gate_0_safety_boundary": bool(safety),
        "gate_1_frozen_apparatus_identity": bool(apparatus_identity),
        "gate_2_complete_turnover_integrity": bool(turnover_ok),
        "gate_3_corpus_equivalence_budget_parity": bool(corpus_parity),
        "gate_4_history_arm_integrity": bool(arm_integrity),
        "gate_5_model_call_isolation": bool(isolation and plan_equivalent),
        "gate_6_live_transport_contract": bool(live_contract),
        "gate_7_evaluator_future_leakage_exclusion": bool(leakage_ok),
        "gate_8_evidence_reference_integrity": bool(references_ok),
        "gate_9_primary_confirmatory_superiority": bool(primary_ok),
        "gate_10_replicate_direction_consistency": bool(replicate_ok),
        "gate_11_causal_audit_chain": bool(causal_ok),
        "gate_12_frozen_output_evaluator_reproducibility": True,
    }
    classification = PASS if all(gates.values()) else FAIL
    result = {
        "schema": "h4-result-v0.1",
        "classification": classification,
        "gates": gates,
        "diagnostics": {
            "logical_cell_count": len(live_cells),
            "unit_count": len(unit_map),
            "replicate_count": len(evidence["replicates"]),
            "generation_count": len(evidence["generations"]),
            "correctness_counts_out_of_36": {
                generation: {
                    arm: counts[(generation, arm)]
                    for arm in evidence["history_arms"]
                }
                for generation in evidence["generations"]
            },
            "family_correctness_counts_out_of_12": {
                family: {
                    generation: {
                        arm: family_counts[(family, generation, arm)]
                        for arm in evidence["history_arms"]
                    }
                    for generation in evidence["generations"]
                }
                for family in sorted(
                    {unit["family"] for unit in evidence["units"]}
                )
            },
            "primary_contrasts": contrasts,
            "holm": holm_result,
            "replicate_g3_counts_out_of_12": replicate_counts,
            "total_provider_attempts": len(request_ids),
            "pre_key_live_output_sha256": sha(args.live_output),
            "corpus_informational_equivalence": bool(corpus_parity),
            "production_historical_substrate_enabled": False,
        },
        "scientific_claim": "registered_stochastic_successor_history_reasoning_only",
    }
    result_bytes = cb(result)
    manifest = {
        "schema": "h4-manifest-v0.1",
        "candidate_head": args.candidate_head,
        "world_preregistered_base": evidence["world_preregistered_base"],
        "contextgraph_release_commit": evidence["contextgraph_release_commit"],
        "preregistration_issue": 150,
        "model": MODEL,
        "plane_e_sha256": sha(args.plane_e),
        "plane_k_sha256": sha(args.plane_k),
        "fixture_manifest_sha256": sha(args.fixture_manifest),
        "live_output_sha256": sha(args.live_output),
        "authoritative_result_sha256": hashlib.sha256(result_bytes).hexdigest(),
        "reproducibility_contract": (
            "two-isolated-evaluator-runs-over-one-frozen-live-output"
        ),
        "production_historical_substrate_enabled": False,
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "result.json").write_bytes(result_bytes)
    (args.output_dir / "manifest.json").write_bytes(cb(manifest))
    (args.output_dir / "audit.json").write_bytes(
        cb({"schema": "h4-audit-v0.1", "rows": audit_rows})
    )
    print(
        "H4_RESULT="
        + json.dumps(result, sort_keys=True, separators=(",", ":"))
    )
    print(
        "H4_MANIFEST="
        + json.dumps(manifest, sort_keys=True, separators=(",", ":"))
    )
    return 0 if classification == PASS else 3


if __name__ == "__main__":
    raise SystemExit(main())
