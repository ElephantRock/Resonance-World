#!/usr/bin/env python3
"""Evaluate the preregistered H0 Historical Substrate activation-safety gates."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from resonance_world.context_graph_runtime import (
    HISTORICAL_SUBSTRATE_ENABLED,
    INTEGRATION_MODE,
    STANDALONE_RELEASE_COMMIT,
)

PASS = "historical_substrate_activation_safety_pass"
FAIL = "historical_substrate_activation_safety_failed"
REPRO_CONTRACT = "two-isolated-exact-head-with-downstream-byte-compare"


def canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        + "\n"
    ).encode()


def read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def production_boundary_clean(repo_root: Path) -> bool:
    allowed = {
        repo_root / "src/resonance_world/context_graph_adapter.py",
        repo_root / "src/resonance_world/context_graph_runtime.py",
        repo_root / "src/resonance_world/observatory.py",
    }
    tokens = (
        "resonance_contextgraph",
        "context_graph_adapter",
        "context_graph_runtime",
        "resonance_world.observatory",
        "from .observatory",
        "import observatory",
    )
    for path in (repo_root / "src/resonance_world").glob("*.py"):
        if path in allowed:
            continue
        text = path.read_text(encoding="utf-8")
        if any(token in text for token in tokens):
            return False
    return True


def no_truth_collapse(bundle: dict[str, Any]) -> bool:
    forbidden = {"world_truth", "resolved_value", "prescribed_action", "inferred_authority"}
    if forbidden.intersection(bundle):
        return False
    values = [entry.get("value") for entry in bundle.get("evidence", [])]
    return len(values) == 2 and set(values) == {"left", "right"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--lock-verification", required=True, type=Path)
    parser.add_argument("--corpus-root", required=True, type=Path)
    parser.add_argument("--researcher-output", required=True, type=Path)
    parser.add_argument("--pre-key-manifest", required=True, type=Path)
    parser.add_argument("--candidate-head", required=True)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()

    lock_check = read_object(args.lock_verification)
    key = read_object(args.corpus_root / "plane_k/evaluator.json")
    query_manifest = read_object(args.corpus_root / "meta/query-manifest.json")
    researcher = read_object(args.researcher_output / "h0-researcher-output.json")
    pre_key = read_object(args.pre_key_manifest)

    bundles = dict(researcher["bundles"])
    denials = dict(researcher["disabled_query_denials"])
    purpose_to_query = dict(researcher["purpose_to_query"])
    expected_queries = dict(key["expected_queries"])

    retrieval_exact = set(bundles) == set(expected_queries)
    if retrieval_exact:
        for query_id, expected_ids in expected_queries.items():
            bundle = bundles[query_id]
            actual = [str(row["evidence_event_id"]) for row in bundle["evidence"]]
            if actual != list(expected_ids):
                retrieval_exact = False
                break

    researcher_bytes = canonical_bytes(researcher)
    future_excluded = str(key["future_event_id"]).encode() not in researcher_bytes
    hidden_value = str(key["hidden_private_field_fact"]["private_capability"]).encode()
    hidden_excluded = hidden_value not in researcher_bytes

    conflict_bundle = bundles[purpose_to_query["conflicting-evidence"]]
    evidence_not_truth = no_truth_collapse(conflict_bundle)

    authority_bundle = bundles[purpose_to_query["authority-separation"]]
    authority_path = researcher["authority_path"]
    decision = authority_path["decision"]
    consequence = authority_path["consequence"]
    ack = authority_path["execution_acknowledgement"]
    historical_actor = str(authority_bundle["evidence"][0]["subject_id"])
    authority_separation = (
        historical_actor == str(key["old_actor"])
        and authority_bundle["evidence"][0]["value"] is True
        and str(decision["actor_id"]) == historical_actor
        and consequence["authorized"] is False
        and consequence["executed"] is False
        and authority_path["current_actor_control_consequence"]["authorized"] is True
    )

    direct_sentinels = {
        str(row["route"]): str(row["status"])
        for row in researcher["direct_edge_sentinels"]
    }
    direct_edges_rejected = (
        set(direct_sentinels) == set(key["forbidden_direct_edges"])
        and all(value == "rejected" for value in direct_sentinels.values())
        and production_boundary_clean(args.repo_root)
    )

    audit_chain = (
        str(decision["bundle_id"]) == str(authority_bundle["bundle_id"])
        and str(consequence["decision_id"]) == str(decision["decision_id"])
        and str(ack["decision_id"]) == str(decision["decision_id"])
        and str(ack["action_id"]) == str(decision["action_id"])
        and bool(ack["authorized"]) == bool(consequence["authorized"])
        and bool(ack["executed"]) == bool(consequence["executed"])
    )

    disabled_denials = (
        set(denials) == set(expected_queries)
        and all(
            row.get("status") == "historical_access_disabled" and row.get("bundle") is None
            for row in denials.values()
        )
    )
    disabled_noninterference = (
        canonical_bytes(researcher["observer_only_baseline_trajectory"])
        == canonical_bytes(researcher["access_disabled_no_retrieval_trajectory"])
    )
    prekey_unchanged = all(
        sha256_file(args.researcher_output / filename) == str(digest)
        for filename, digest in pre_key["files"].items()
    )

    gates = {
        "gate_0_default_off_treatment_isolation": (
            INTEGRATION_MODE == "observer-only"
            and HISTORICAL_SUBSTRATE_ENABLED is False
            and disabled_denials
        ),
        "gate_1_exact_bounded_retrieval_correctness": (
            bool(lock_check.get("all_match")) and retrieval_exact
        ),
        "gate_2_temporal_hidden_state_exclusion": future_excluded and hidden_excluded,
        "gate_3_evidence_not_truth_semantics": evidence_not_truth,
        "gate_4_authority_separation": authority_separation,
        "gate_5_no_direct_world_field_causal_edge": direct_edges_rejected,
        "gate_6_decision_audit_chain_integrity": audit_chain and prekey_unchanged,
        "gate_7_disabled_arm_noninterference": disabled_noninterference,
        "gate_8_exact_head_reproducibility_contract": len(args.candidate_head) == 40,
    }
    classification = PASS if all(gates.values()) else FAIL
    result = {
        "schema": "h0-result-v0.1",
        "classification": classification,
        "scientific_claim": "registered_historical_substrate_activation_safety_only",
        "production_historical_substrate_enabled": False,
        "gates": gates,
        "diagnostics": {
            "query_count": len(expected_queries),
            "contextgraph_claim_count": len(researcher["contextgraph_claims"]),
            "retrieval_exact": retrieval_exact,
            "future_sentinel_excluded": future_excluded,
            "hidden_state_excluded": hidden_excluded,
            "conflicting_evidence_preserved": evidence_not_truth,
            "historical_authority_rejected_by_current_world_verifier": authority_separation,
            "direct_edge_sentinels_rejected": direct_edges_rejected,
            "disabled_noninterference_byte_exact": disabled_noninterference,
            "pre_key_hashes_unchanged": prekey_unchanged,
        },
    }
    manifest = {
        "schema": "h0-manifest-v0.1",
        "candidate_head": args.candidate_head,
        "world_preregistered_base": "039657c198f9c1bc5158031f579d74a40717828f",
        "contextgraph_release_commit": STANDALONE_RELEASE_COMMIT,
        "apparatus_lock_verification_sha256": sha256_file(args.lock_verification),
        "pre_key_manifest_sha256": sha256_file(args.pre_key_manifest),
        "researcher_output_sha256": sha256_file(args.researcher_output / "h0-researcher-output.json"),
        "reproducibility_contract": REPRO_CONTRACT,
        "production_historical_substrate_enabled": False,
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    result_path = args.output_dir / "h0-result.json"
    result_path.write_bytes(canonical_bytes(result))
    manifest["authoritative_result_sha256"] = sha256_file(result_path)
    (args.output_dir / "h0-manifest.json").write_bytes(canonical_bytes(manifest))
    return 0 if classification == PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())
