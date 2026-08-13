"""Exact evaluator for the preregistered O2 longitudinal-utility experiment."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from .o2_accept_support import event_support, structural_plane_k_exclusion
from .o2_utility import NEGATIVE_CONTROLS, NOT_IDENTIFIABLE, canonical_bytes

CLASS_PASS = "observatory_registered_longitudinal_utility_pass"
CLASS_FAIL = "observatory_registered_longitudinal_utility_failed"
REPRO_CONTRACT = "two-isolated-exact-head-with-downstream-byte-compare"


def read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_directory(directory: Path) -> list[dict[str, Any]]:
    return [read_object(path) for path in sorted(directory.glob("*.json"))]


def by_history(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    result = {str(row["history_id"]): row for row in rows}
    if len(result) != len(rows):
        raise ValueError("duplicate O2 history identity")
    return result


def _collision_integrity(
    plane_k: dict[str, dict[str, Any]],
    r0_inputs: list[dict[str, Any]],
) -> tuple[bool, dict[str, list[dict[str, Any]]]]:
    k_by_pair: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in plane_k.values():
        k_by_pair[str(row["pair_id"])].append(row)
    r0_by_pair: dict[str, list[bytes]] = defaultdict(list)
    for row in r0_inputs:
        r0_by_pair[str(row["pair_id"])].append(canonical_bytes(row))
    ok = len(k_by_pair) == 40 and len(r0_by_pair) == 40
    if ok:
        for pair_id, rows in k_by_pair.items():
            payloads = r0_by_pair[pair_id]
            answers = [canonical_bytes(row["distinguishing_answers"]) for row in rows]
            if (
                len(rows) != 2
                or len(payloads) != 2
                or payloads[0] != payloads[1]
                or answers[0] == answers[1]
            ):
                ok = False
                break
    return ok, k_by_pair


def _opaque_integrity(relabel_manifest: dict[str, Any]) -> bool:
    for record in relabel_manifest["records"]:
        ids = [str(item) for item in record["opaque_entity_ids"]]
        ids.append(str(record["pair_id"]))
        if any(not item.startswith("o2-") for item in ids):
            return False
        if any(
            any(token in item for token in ("m0", "org", "source", "role0"))
            for item in ids
        ):
            return False
    return True


def evaluate_o2(
    *,
    lock_path: Path,
    lock_verification_path: Path,
    corpus_root: Path,
    research_output: Path,
    pre_key_manifest_path: Path,
    candidate_head: str,
    reproducibility_contract: str,
    integration_mode: str,
    historical_substrate_enabled: bool,
    standalone_release_commit: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    lock = read_object(lock_path)
    lock_check = read_object(lock_verification_path)
    materialization = read_object(corpus_root / "materialization-manifest.json")
    query_manifest = read_object(corpus_root / "meta/query-manifest.json")
    relabel_manifest = read_object(corpus_root / "meta/relabeling-manifest.json")
    plane_e = by_history(load_directory(corpus_root / "plane_e"))
    plane_k = by_history(load_directory(corpus_root / "plane_k"))
    r0_inputs = load_directory(corpus_root / "r0")

    ledger_doc = read_object(research_output / "r2-event-ledger.json")
    r2_doc = read_object(research_output / "r2-researcher-answers.json")
    r1_doc = read_object(research_output / "r1-researcher-answers.json")
    r0_doc = read_object(research_output / "r0-researcher-answers.json")
    evidence_doc = read_object(research_output / "contextgraph-evidence.json")
    pre_key = read_object(pre_key_manifest_path)

    ledgers = by_history(list(ledger_doc["histories"]))
    r2 = by_history(list(r2_doc["histories"]))
    r1 = by_history(list(r1_doc["histories"]))
    r0 = {str(row["pair_id"]): row for row in r0_doc["pairs"]}

    expected_roots = lock["roots"]
    actual_roots = materialization["roots"]
    root_match = all(
        int(actual_roots[name]["file_count"]) == int(expected_roots[name]["file_count"])
        and str(actual_roots[name]["manifest_root_sha256"])
        == str(expected_roots[name]["manifest_root_sha256"])
        for name in ("plane_e", "plane_k", "r0", "r1", "meta")
    )
    collision_ok, k_by_pair = _collision_integrity(plane_k, r0_inputs)
    opaque_ok = _opaque_integrity(relabel_manifest)

    exact_ledger = set(ledgers) == set(plane_e)
    if exact_ledger:
        for history_id, source in plane_e.items():
            observed = ledgers[history_id]
            if str(observed["pair_id"]) != str(source["pair_id"]):
                exact_ledger = False
                break
            if canonical_bytes(observed["events"]) != canonical_bytes(source["events"]):
                exact_ledger = False
                break

    expected_claim_count = sum(
        len(event) for history in plane_e.values() for event in history["events"]
    )
    claims = list(evidence_doc["claims"])
    claim_integrity = (
        len(claims) == expected_claim_count
        and len({str(row["claim_id"]) for row in claims}) == len(claims)
        and len({str(row["source_id"]) for row in claims}) == len(claims)
    )
    no_plane_k_structure = all(
        structural_plane_k_exclusion(value)
        for value in (ledger_doc, r2_doc, r1_doc, r0_doc, evidence_doc)
    )

    registered_correct = True
    flat_log_correct = True
    provenance_correct = True
    registered_query_count = 0
    support_check_count = 0
    templates = query_manifest["templates"]
    for history_id, key in plane_k.items():
        template = str(key["template"])
        source_events = list(plane_e[history_id]["events"])
        r2_answers = r2[history_id]["answers"]
        r1_answers = r1[history_id]["answers"]
        admissible_event_ids = {str(row["event_id"]) for row in source_events}
        for query in templates[template]:
            query_id = str(query["query_id"])
            expected_value = key["distinguishing_answers"][query_id]
            registered_query_count += 1
            r2_answer = r2_answers.get(query_id)
            r1_answer = r1_answers.get(query_id)
            if not isinstance(r2_answer, dict) or r2_answer.get("value") != expected_value:
                registered_correct = False
                continue
            if not isinstance(r1_answer, dict) or r1_answer.get("value") != expected_value:
                flat_log_correct = False
            expected_support = event_support(template, query_id, source_events, expected_value)
            actual_support = list(r2_answer.get("support_event_ids", []))
            support_check_count += 1
            if actual_support != expected_support:
                provenance_correct = False
            if any(item not in admissible_event_ids for item in actual_support):
                provenance_correct = False

    aggregate_erasure = len(r0) == 40
    if aggregate_erasure:
        for pair_id, rows in k_by_pair.items():
            answer_doc = r0.get(pair_id)
            if answer_doc is None:
                aggregate_erasure = False
                break
            template = str(rows[0]["template"])
            if any(
                answer_doc["answers"].get(str(query["query_id"])) != NOT_IDENTIFIABLE
                for query in templates[template]
            ):
                aggregate_erasure = False
                break

    negative_controls_ok = set(r2) == set(plane_k)
    if negative_controls_ok:
        for history_id in sorted(r2):
            controls = r2[history_id].get("negative_controls")
            if not isinstance(controls, dict) or any(
                controls.get(query_id) != NOT_IDENTIFIABLE
                for query_id in NEGATIVE_CONTROLS
            ):
                negative_controls_ok = False
                break

    prekey_hashes_ok = all(
        sha256_file(research_output / filename) == str(digest)
        for filename, digest in pre_key["files"].items()
    )

    gates = {
        "gate_0_observer_only_boundary": (
            integration_mode == "observer-only" and historical_substrate_enabled is False
        ),
        "gate_1_benchmark_lock_collision_integrity": (
            bool(lock_check.get("all_match")) and root_match and collision_ok and opaque_ok
        ),
        "gate_2_admissible_evidence_fidelity": (
            exact_ledger and claim_integrity and no_plane_k_structure and prekey_hashes_ok
        ),
        "gate_3_identifiable_longitudinal_query_correctness": registered_correct,
        "gate_4_aggregate_erasure_nonidentifiability": aggregate_erasure,
        "gate_5_negative_control_epistemic_calibration": negative_controls_ok,
        "gate_6_provenance_sufficiency": provenance_correct,
        "gate_7_exact_head_reproducibility_contract": (
            reproducibility_contract == REPRO_CONTRACT and len(candidate_head) == 40
        ),
    }
    classification = CLASS_PASS if all(gates.values()) else CLASS_FAIL
    result = {
        "schema": "o2-result-v0.1",
        "classification": classification,
        "scientific_claim": "registered_observer_side_longitudinal_utility_only",
        "historical_substrate_enabled": False,
        "participant_query_access": False,
        "gates": gates,
        "diagnostics": {
            "collision_pairs": len(k_by_pair),
            "histories": len(plane_k),
            "contextgraph_claim_count": len(claims),
            "registered_query_count": registered_query_count,
            "provenance_check_count": support_check_count,
            "flat_log_registered_query_parity": flat_log_correct,
            "r0_collision_inputs_byte_identical": collision_ok,
            "pre_key_hashes_unchanged_after_plane_k_restore": prekey_hashes_ok,
        },
    }

    product_paths = {
        "apparatus-lock-verification.json": lock_verification_path,
        "pre-key-manifest.json": pre_key_manifest_path,
        "contextgraph-evidence.json": research_output / "contextgraph-evidence.json",
        "r0-researcher-answers.json": research_output / "r0-researcher-answers.json",
        "r1-researcher-answers.json": research_output / "r1-researcher-answers.json",
        "r2-event-ledger.json": research_output / "r2-event-ledger.json",
        "r2-researcher-answers.json": research_output / "r2-researcher-answers.json",
    }
    manifest = {
        "schema": "o2-manifest-v0.1",
        "candidate_head": candidate_head,
        "world_preregistered_base": lock["frozen_base_revision"],
        "contextgraph_release_commit": standalone_release_commit,
        "generator_revision": lock["generator_revision"],
        "apparatus_roots": lock["roots"],
        "reproducibility_contract": REPRO_CONTRACT,
        "historical_substrate_enabled": False,
        "participant_query_access": False,
        "authoritative_pre_result_sha256": {
            name: sha256_file(path) for name, path in sorted(product_paths.items())
        },
    }
    return result, manifest
