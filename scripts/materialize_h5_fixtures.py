#!/usr/bin/env python3
"""Materialize the preregistered H5 institutional-mediation fixtures."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

WORLD_BASE = "935e0463acc88f7f7756861d734eeba7b4efb034"
CONTEXTGRAPH_COMMIT = "b896891108fd954869a8cd0423f6e8440ab0cdc0"
MODEL = "glm-5-turbo"
MODEL_ENDPOINT = "https://api.z.ai/api/coding/paas/v4/chat/completions"
FAMILIES = ("cross_role_composition", "authority_conflict", "routine_transfer")
GENERATIONS = ("g1", "g2", "g3")
REPLICATES = ("r1", "r2", "r3")
ARMS = (
    "equal_compute_direct",
    "roles_only",
    "governed_static",
    "governed_persistent",
)
ROLES = ("case_analyst", "institutional_steward", "chair")
RECORD_BUDGET = 6
CALLS_PER_CELL = 3
PRIVATE_SENTINEL = "H5_PRIVATE_EVALUATOR_SENTINEL_41C7"


def cb(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def token(prefix: str, *parts: object, n: int = 10) -> str:
    raw = "|".join(str(part) for part in parts).encode()
    return f"{prefix}-{hashlib.sha256(raw).hexdigest()[:n]}"


def record(
    *,
    record_id: str,
    organization_id: str,
    predicate: str,
    observed_at: int,
    responsibility: str,
    record_kind: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    return {
        "record_id": record_id,
        "organization_id": organization_id,
        "predicate": predicate,
        "observed_at": observed_at,
        "observed_by": f"h5-{responsibility}-observer",
        "source_id": f"{record_id}-source",
        "source_class": "direct",
        "confidence": 1.0,
        "direct": True,
        "responsibility": responsibility,
        "record_kind": record_kind,
        "payload": payload,
    }


def _action_records(
    *,
    family: str,
    unit_id: str,
    org: str,
    predicate: str,
    cutoff: int,
    actions: list[str],
    correct_position: int,
    provenance: list[str],
) -> list[dict[str, Any]]:
    if family == "routine_transfer":
        return [
            record(
                record_id=f"{unit_id}-action-0",
                organization_id=org,
                predicate=predicate,
                observed_at=cutoff - 60,
                responsibility="case",
                record_kind="decision_observation",
                payload={
                    "provenance_class": provenance[0],
                    "recommended_action": actions[0],
                    "observation_token": token("obs", unit_id, 0),
                },
            ),
            record(
                record_id=f"{unit_id}-action-1",
                organization_id=org,
                predicate=predicate,
                observed_at=cutoff - 50,
                responsibility="case",
                record_kind="decision_observation",
                payload={
                    "provenance_class": provenance[1],
                    "recommended_action": actions[1],
                    "observation_token": token("obs", unit_id, 1),
                },
            ),
        ]

    first = (int(hashlib.sha256((unit_id + "alpha").encode()).hexdigest(), 16) & 1)
    second = first ^ correct_position
    responsibilities = ("case", "steward") if family == "cross_role_composition" else ("case", "case")
    return [
        record(
            record_id=f"{unit_id}-signal-alpha",
            organization_id=org,
            predicate=predicate,
            observed_at=cutoff - 60,
            responsibility=responsibilities[0],
            record_kind="decision_signal",
            payload={"signal_name": "alpha", "bit": first},
        ),
        record(
            record_id=f"{unit_id}-signal-beta",
            organization_id=org,
            predicate=predicate,
            observed_at=cutoff - 50,
            responsibility=responsibilities[1],
            record_kind="decision_signal",
            payload={"signal_name": "beta", "bit": second},
        ),
    ]


def _procedure_records(
    *,
    family: str,
    unit_id: str,
    org: str,
    predicate: str,
    cutoff: int,
    generation_index: int,
    correct_position: int,
    provenance: list[str],
) -> list[dict[str, Any]]:
    if family != "routine_transfer":
        return [
            record(
                record_id=f"{unit_id}-procedure-a",
                organization_id=org,
                predicate=predicate,
                observed_at=cutoff - 40,
                responsibility="case",
                record_kind="procedure_outcome",
                payload={"status": "not_applicable", "slot": "a"},
            ),
            record(
                record_id=f"{unit_id}-procedure-b",
                organization_id=org,
                predicate=predicate,
                observed_at=cutoff - 30,
                responsibility="steward",
                record_kind="procedure_outcome",
                payload={"status": "not_applicable", "slot": "b"},
            ),
        ]

    # At g1 no completed procedure evidence exists; at g2 one observation exists;
    # at g3 two observations identify the trusted provenance class. The digest is
    # a deterministic compilation of these same public records.
    trusted = provenance[correct_position]
    other = provenance[1 - correct_position]
    first_complete = generation_index >= 1
    second_complete = generation_index >= 2
    return [
        record(
            record_id=f"{unit_id}-procedure-a",
            organization_id=org,
            predicate=predicate,
            observed_at=cutoff - 40,
            responsibility="steward",
            record_kind="procedure_outcome",
            payload=(
                {
                    "status": "observed",
                    "provenance_class": trusted,
                    "attempts": 3,
                    "successes": 3,
                    "episode_token": token("ep", unit_id, "a"),
                }
                if first_complete
                else {"status": "pending", "episode_token": token("ep", unit_id, "a")}
            ),
        ),
        record(
            record_id=f"{unit_id}-procedure-b",
            organization_id=org,
            predicate=predicate,
            observed_at=cutoff - 30,
            responsibility="steward",
            record_kind="procedure_outcome",
            payload=(
                {
                    "status": "observed",
                    "provenance_class": other,
                    "attempts": 3,
                    "successes": 0,
                    "episode_token": token("ep", unit_id, "b"),
                }
                if second_complete
                else {"status": "pending", "episode_token": token("ep", unit_id, "b")}
            ),
        ),
    ]


def _authority_records(
    *,
    family: str,
    unit_id: str,
    org: str,
    predicate: str,
    cutoff: int,
    generation: str,
    valid_position: int,
    capability: str,
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    notices = sorted(
        [token("notice", unit_id, generation, 0, n=12), token("notice", unit_id, generation, 1, n=12)]
    )
    valid_notice = notices[valid_position]
    invalid_notice = notices[1 - valid_position]
    valid_payload: dict[str, Any] = {
        "notice_id": valid_notice,
        "world_verification": True,
        "execution_capability": capability,
        "historical_label": "archival" if family == "authority_conflict" else "current",
    }
    invalid_payload: dict[str, Any] = {
        "notice_id": invalid_notice,
        "world_verification": False,
        "execution_capability": capability,
        "historical_label": "previously_authoritative" if family == "authority_conflict" else "inactive",
    }
    rows = [
        record(
            record_id=f"{unit_id}-{generation}-authority-valid",
            organization_id=org,
            predicate=predicate,
            observed_at=cutoff - 20,
            responsibility="steward",
            record_kind="authority_notice",
            payload=valid_payload,
        ),
        record(
            record_id=f"{unit_id}-{generation}-authority-stale",
            organization_id=org,
            predicate=predicate,
            observed_at=cutoff - 10,
            responsibility="steward",
            record_kind="authority_notice",
            payload=invalid_payload,
        ),
    ]
    rows.sort(key=lambda row: str(row["payload"]["notice_id"]))
    return rows, {
        "organization_id": org,
        "scenario_id": f"{unit_id}-{generation}",
        "action": capability,
        "notice_id": valid_notice,
    }


def materialize() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    units: list[dict[str, Any]] = []
    evaluator_units: list[dict[str, Any]] = []
    evidence_sets: dict[str, list[dict[str, Any]]] = {}
    authority_grants: list[dict[str, str]] = []

    for idx in range(12):
        family = FAMILIES[idx // 4]
        unit_id = f"h5-u{idx:02d}"
        org = token("org", unit_id)
        predicate = token("pred", unit_id)
        actions = sorted([token("act", unit_id, "a"), token("act", unit_id, "b")])
        correct_position = idx % 2
        provenance = sorted([token("prov", unit_id, "p"), token("prov", unit_id, "q")])
        members: dict[str, dict[str, dict[str, str]]] = {}
        for replicate in REPLICATES:
            members[replicate] = {}
            for generation in GENERATIONS:
                members[replicate][generation] = {
                    role: token("member", unit_id, replicate, generation, role, n=14)
                    for role in ROLES
                }
        unit = {
            "unit_id": unit_id,
            "family": family,
            "organization_id": org,
            "predicate": predicate,
            "actions": actions,
            "provenance_classes": provenance,
            "members": members,
            "record_budget": RECORD_BUDGET,
        }
        units.append(unit)
        evaluator_units.append(
            {
                "unit_id": unit_id,
                "correct_action": actions[correct_position],
                "correct_position": correct_position,
            }
        )

        for generation_index, generation in enumerate(GENERATIONS):
            cutoff = (generation_index + 1) * 100_000 + idx * 100
            capability = f"execute:{unit_id}-{generation}"
            valid_position = (idx + generation_index) % 2
            action_rows = _action_records(
                family=family,
                unit_id=unit_id,
                org=org,
                predicate=predicate,
                cutoff=cutoff,
                actions=actions,
                correct_position=correct_position,
                provenance=provenance,
            )
            procedure_rows = _procedure_records(
                family=family,
                unit_id=unit_id,
                org=org,
                predicate=predicate,
                cutoff=cutoff,
                generation_index=generation_index,
                correct_position=correct_position,
                provenance=provenance,
            )
            authority_rows, grant = _authority_records(
                family=family,
                unit_id=unit_id,
                org=org,
                predicate=predicate,
                cutoff=cutoff,
                generation=generation,
                valid_position=valid_position,
                capability=capability,
            )
            rows = action_rows + procedure_rows + authority_rows
            if len(rows) != RECORD_BUDGET:
                raise AssertionError("H5 requires exactly six canonical records")
            evidence_sets[f"{unit_id}:{generation}"] = sorted(
                rows, key=lambda row: (int(row["observed_at"]), str(row["record_id"]))
            )
            authority_grants.append(grant)

    plane_e = {
        "schema": "h5-plane-e-v0.1",
        "world_preregistered_base": WORLD_BASE,
        "contextgraph_release_commit": CONTEXTGRAPH_COMMIT,
        "model_contract": {
            "provider": "zai-chat-completions",
            "model": MODEL,
            "endpoint": MODEL_ENDPOINT,
            "do_sample": True,
            "temperature": 0.8,
            "thinking": {"type": "disabled"},
            "stream": False,
            "response_format": {"type": "json_object"},
            "max_output_tokens": 96,
        },
        "generations": list(GENERATIONS),
        "replicates": list(REPLICATES),
        "institutional_arms": list(ARMS),
        "roles": list(ROLES),
        "record_budget": RECORD_BUDGET,
        "calls_per_cell": CALLS_PER_CELL,
        "units": units,
        "canonical_evidence_sets": evidence_sets,
        "authority_grants": authority_grants,
        "private_evaluator_sentinel": "ABSENT_FROM_PLANE_E_BY_CONSTRUCTION",
    }
    plane_k = {
        "schema": "h5-plane-k-v0.1",
        "private_evaluator_sentinel": PRIVATE_SENTINEL,
        "units": evaluator_units,
    }
    manifest = {
        "schema": "h5-fixture-manifest-v0.1",
        "unit_count": len(units),
        "organization_cell_count": len(units) * len(GENERATIONS) * len(REPLICATES) * len(ARMS),
        "logical_model_call_count": len(units) * len(GENERATIONS) * len(REPLICATES) * len(ARMS) * CALLS_PER_CELL,
        "canonical_record_budget": RECORD_BUDGET,
        "canonical_evidence_set_count": len(evidence_sets),
        "authority_grant_count": len(authority_grants),
        "correct_position_balance": {
            "first": sum(1 for unit in evaluator_units if unit["correct_position"] == 0),
            "second": sum(1 for unit in evaluator_units if unit["correct_position"] == 1),
        },
        "family_counts": {
            family: sum(1 for unit in units if unit["family"] == family)
            for family in FAMILIES
        },
    }
    return plane_e, plane_k, manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    plane_e, plane_k, manifest = materialize()
    evidence_path = args.output_dir / "plane_e" / "evidence.json"
    evaluator_path = args.output_dir / "plane_k" / "evaluator.json"
    manifest_path = args.output_dir / "meta" / "fixture-manifest.json"
    for path in (evidence_path, evaluator_path, manifest_path):
        path.parent.mkdir(parents=True, exist_ok=True)
    evidence_bytes, evaluator_bytes = cb(plane_e), cb(plane_k)
    manifest = {
        **manifest,
        "plane_e_sha256": hashlib.sha256(evidence_bytes).hexdigest(),
        "plane_k_sha256": hashlib.sha256(evaluator_bytes).hexdigest(),
    }
    manifest_bytes = cb(manifest)
    evidence_path.write_bytes(evidence_bytes)
    evaluator_path.write_bytes(evaluator_bytes)
    manifest_path.write_bytes(manifest_bytes)
    print(json.dumps({
        "plane_e_sha256": manifest["plane_e_sha256"],
        "plane_k_sha256": manifest["plane_k_sha256"],
        "fixture_manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "organization_cell_count": manifest["organization_cell_count"],
        "logical_model_call_count": manifest["logical_model_call_count"],
        "authority_grant_count": manifest["authority_grant_count"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
