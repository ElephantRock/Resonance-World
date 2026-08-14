#!/usr/bin/env python3
"""Materialize preregistered H7 fresh held-out selective-routing fixtures."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

WORLD_BASE = "935e0463acc88f7f7756861d734eeba7b4efb034"
H6_SOURCE_CANDIDATE = "ff6bd5e030c3159829460e123f2fadd2e8087f93"
H6_RESULT_SHA256 = "fe24974c113f5960420d0c4c62902e471ad90ab7457c7b17e3472e479aed7691"
CONTEXTGRAPH_COMMIT = "b896891108fd954869a8cd0423f6e8440ab0cdc0"
MODEL = "glm-5-turbo"
MODEL_ENDPOINT = "https://api.z.ai/api/coding/paas/v4/chat/completions"
FAMILIES = ("cross_role_composition", "authority_conflict", "routine_transfer")
REPLICATES = tuple(f"r{i}" for i in range(1, 13))
ARMS = ("no_state", "always_state", "selective_state")
ROLES = ("case_analyst", "institutional_steward", "chair")
RECORD_BUDGET = 6
CALLS_PER_CELL = 3
PRIVATE_SENTINEL = "H7_PRIVATE_EVALUATOR_SENTINEL_91D4"


def cb(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def token(prefix: str, *parts: object, n: int = 12) -> str:
    raw = "h7|" + "|".join(str(part) for part in parts)
    return f"{prefix}-{hashlib.sha256(raw.encode()).hexdigest()[:n]}"


def record(*, record_id: str, organization_id: str, predicate: str, observed_at: int,
           responsibility: str, record_kind: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "record_id": record_id,
        "organization_id": organization_id,
        "predicate": predicate,
        "observed_at": observed_at,
        "observed_by": f"h7-{responsibility}-observer",
        "source_id": f"{record_id}-source",
        "source_class": "direct",
        "confidence": 1.0,
        "direct": True,
        "responsibility": responsibility,
        "record_kind": record_kind,
        "payload": payload,
    }


def materialize() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    units: list[dict[str, Any]] = []
    evaluator_units: list[dict[str, Any]] = []
    evidence_sets: dict[str, list[dict[str, Any]]] = {}
    grants: list[dict[str, str]] = []
    for idx in range(12):
        family = FAMILIES[idx // 4]
        unit_id = f"h7-u{idx:02d}"
        org = token("org", unit_id)
        predicate = token("pred", unit_id)
        actions = sorted([token("act", unit_id, "a"), token("act", unit_id, "b")])
        correct_position = idx % 2
        provenance = sorted([token("prov", unit_id, "p"), token("prov", unit_id, "q")])
        state_relevance_key = "procedure_rate_comparison" if family == "routine_transfer" else "none"
        members = {
            rep: {role: token("h7-member", unit_id, rep, role, n=14) for role in ROLES}
            for rep in REPLICATES
        }
        units.append({
            "unit_id": unit_id,
            "family": family,
            "state_relevance_key": state_relevance_key,
            "organization_id": org,
            "predicate": predicate,
            "actions": actions,
            "provenance_classes": provenance,
            "members": members,
            "record_budget": RECORD_BUDGET,
        })
        evaluator_units.append({"unit_id": unit_id, "correct_action": actions[correct_position], "correct_position": correct_position})
        cutoff = 700_000 + idx * 100
        rows: list[dict[str, Any]] = []
        if family == "routine_transfer":
            rows.extend([
                record(record_id=f"{unit_id}-action-0", organization_id=org, predicate=predicate,
                       observed_at=cutoff - 60, responsibility="case", record_kind="decision_observation",
                       payload={"provenance_class": provenance[0], "recommended_action": actions[0], "observation_token": token("obs", unit_id, 0)}),
                record(record_id=f"{unit_id}-action-1", organization_id=org, predicate=predicate,
                       observed_at=cutoff - 50, responsibility="case", record_kind="decision_observation",
                       payload={"provenance_class": provenance[1], "recommended_action": actions[1], "observation_token": token("obs", unit_id, 1)}),
            ])
            trusted = provenance[correct_position]
            other = provenance[1 - correct_position]
            rows.extend([
                record(record_id=f"{unit_id}-procedure-a", organization_id=org, predicate=predicate,
                       observed_at=cutoff - 40, responsibility="steward", record_kind="procedure_outcome",
                       payload={"status": "observed", "provenance_class": trusted, "attempts": 4, "successes": 4,
                                "episode_token": token("ep", unit_id, "a")}),
                record(record_id=f"{unit_id}-procedure-b", organization_id=org, predicate=predicate,
                       observed_at=cutoff - 30, responsibility="steward", record_kind="procedure_outcome",
                       payload={"status": "observed", "provenance_class": other, "attempts": 4, "successes": 0,
                                "episode_token": token("ep", unit_id, "b")}),
            ])
        else:
            first = int(hashlib.sha256(("h7-alpha|" + unit_id).encode()).hexdigest(), 16) & 1
            second = first ^ correct_position
            responsibilities = ("case", "steward") if family == "cross_role_composition" else ("case", "case")
            rows.extend([
                record(record_id=f"{unit_id}-signal-alpha", organization_id=org, predicate=predicate,
                       observed_at=cutoff - 60, responsibility=responsibilities[0], record_kind="decision_signal",
                       payload={"signal_name": "alpha", "bit": first}),
                record(record_id=f"{unit_id}-signal-beta", organization_id=org, predicate=predicate,
                       observed_at=cutoff - 50, responsibility=responsibilities[1], record_kind="decision_signal",
                       payload={"signal_name": "beta", "bit": second}),
                record(record_id=f"{unit_id}-procedure-a", organization_id=org, predicate=predicate,
                       observed_at=cutoff - 40, responsibility="case", record_kind="procedure_outcome",
                       payload={"status": "not_applicable", "slot": "a"}),
                record(record_id=f"{unit_id}-procedure-b", organization_id=org, predicate=predicate,
                       observed_at=cutoff - 30, responsibility="steward", record_kind="procedure_outcome",
                       payload={"status": "not_applicable", "slot": "b"}),
            ])
        capability = f"execute:{unit_id}-h7"
        notices = sorted([token("notice", unit_id, 0), token("notice", unit_id, 1)])
        valid_position = (idx + 1) % 2
        valid_notice, stale_notice = notices[valid_position], notices[1 - valid_position]
        valid_payload = {
            "notice_id": valid_notice,
            "world_verification": True,
            "execution_capability": capability,
            "historical_label": "archival" if family == "authority_conflict" else "current",
        }
        stale_payload = {
            "notice_id": stale_notice,
            "world_verification": False,
            "execution_capability": capability,
            "historical_label": "previously_authoritative" if family == "authority_conflict" else "inactive",
        }
        authority_rows = [
            record(record_id=f"{unit_id}-authority-valid", organization_id=org, predicate=predicate,
                   observed_at=cutoff - 20, responsibility="steward", record_kind="authority_notice", payload=valid_payload),
            record(record_id=f"{unit_id}-authority-stale", organization_id=org, predicate=predicate,
                   observed_at=cutoff - 10, responsibility="steward", record_kind="authority_notice", payload=stale_payload),
        ]
        authority_rows.sort(key=lambda row: str(row["payload"]["notice_id"]))
        rows.extend(authority_rows)
        if len(rows) != 6:
            raise AssertionError("H7 requires exactly six canonical records")
        evidence_sets[unit_id] = sorted(rows, key=lambda row: (int(row["observed_at"]), str(row["record_id"])))
        grants.append({"organization_id": org, "scenario_id": f"{unit_id}-h7", "action": capability, "notice_id": valid_notice})
    plane_e = {
        "schema": "h7-plane-e-v0.1",
        "world_preregistered_base": WORLD_BASE,
        "h6_source_candidate": H6_SOURCE_CANDIDATE,
        "h6_result_sha256": H6_RESULT_SHA256,
        "contextgraph_release_commit": CONTEXTGRAPH_COMMIT,
        "model_contract": {
            "provider": "zai-chat-completions", "model": MODEL, "endpoint": MODEL_ENDPOINT,
            "do_sample": True, "temperature": 0.8, "thinking": {"type": "disabled"},
            "stream": False, "response_format": {"type": "json_object"}, "max_output_tokens": 96,
        },
        "replicates": list(REPLICATES), "arms": list(ARMS), "roles": list(ROLES),
        "record_budget": RECORD_BUDGET, "calls_per_cell": CALLS_PER_CELL,
        "units": units, "canonical_evidence_sets": evidence_sets, "authority_grants": grants,
        "private_evaluator_sentinel": "ABSENT_FROM_PLANE_E_BY_CONSTRUCTION",
    }
    plane_k = {
        "schema": "h7-plane-k-v0.1", "private_evaluator_sentinel": PRIVATE_SENTINEL,
        "h6_source_candidate": H6_SOURCE_CANDIDATE, "units": evaluator_units,
    }
    manifest = {
        "schema": "h7-fixture-manifest-v0.1", "unit_count": 12,
        "organization_cell_count": 12 * len(REPLICATES) * len(ARMS),
        "logical_model_call_count": 12 * len(REPLICATES) * len(ARMS) * CALLS_PER_CELL,
        "canonical_record_budget": RECORD_BUDGET, "canonical_evidence_set_count": len(evidence_sets),
        "authority_grant_count": len(grants),
        "correct_position_balance": {"first": 6, "second": 6},
        "family_counts": {family: 4 for family in FAMILIES},
        "state_relevance_counts": {"procedure_rate_comparison": 4, "none": 8},
    }
    return plane_e, plane_k, manifest


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--output-dir", type=Path, required=True); args = parser.parse_args()
    plane_e, plane_k, manifest = materialize()
    e_path = args.output_dir / "plane_e" / "evidence.json"
    k_path = args.output_dir / "plane_k" / "evaluator.json"
    m_path = args.output_dir / "meta" / "fixture-manifest.json"
    for path in (e_path, k_path, m_path): path.parent.mkdir(parents=True, exist_ok=True)
    e_bytes, k_bytes = cb(plane_e), cb(plane_k)
    manifest = {**manifest, "plane_e_sha256": hashlib.sha256(e_bytes).hexdigest(), "plane_k_sha256": hashlib.sha256(k_bytes).hexdigest()}
    m_bytes = cb(manifest)
    e_path.write_bytes(e_bytes); k_path.write_bytes(k_bytes); m_path.write_bytes(m_bytes)
    print(json.dumps({"plane_e_sha256": manifest["plane_e_sha256"], "plane_k_sha256": manifest["plane_k_sha256"],
                      "fixture_manifest_sha256": hashlib.sha256(m_bytes).hexdigest(),
                      "organization_cell_count": manifest["organization_cell_count"],
                      "logical_model_call_count": manifest["logical_model_call_count"]}, sort_keys=True))
    return 0

if __name__ == "__main__": raise SystemExit(main())
