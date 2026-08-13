#!/usr/bin/env python3
"""Materialize the preregistered H1 bounded-history benchmark fixtures."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

BASE_REVISION = "4c815a0d47b7818787750ae9f2d74dc1ff58709d"
CONTEXTGRAPH_RELEASE_COMMIT = "b896891108fd954869a8cd0423f6e8440ab0cdc0"


def canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        + "\n"
    ).encode()


def opaque(*parts: object) -> str:
    raw = "|".join(str(part) for part in parts)
    digest = hashlib.sha256(("resonance-h1-v1|" + raw).encode()).hexdigest()
    return "h1-" + digest[:24]


def record(
    unit_index: int,
    role: str,
    organization_id: str,
    predicate: str,
    support_action: str,
    observed_at: int,
) -> dict[str, Any]:
    return {
        "record_id": opaque("record", unit_index, role),
        "organization_id": organization_id,
        "subject_id": opaque("subject", unit_index, role),
        "predicate": predicate,
        "support_action": support_action,
        "source_id": opaque("source", unit_index, role),
        "source_class": "direct-observation",
        "observed_by": opaque("observer", unit_index),
        "observed_at": observed_at,
        "confidence": 1.0,
        "direct": True,
    }


def materialize() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    plane_e_units: list[dict[str, Any]] = []
    plane_k_units: list[dict[str, Any]] = []
    evidence_records: list[dict[str, Any]] = []

    for unit_index in range(30):
        family = ("f0", "f1", "f2")[unit_index // 10]
        organization_id = opaque("org", unit_index)
        other_organization_id = opaque("org-decoy", unit_index)
        predicate = opaque("predicate", unit_index)
        other_predicate = opaque("predicate-decoy", unit_index)
        actions = sorted(
            [
                opaque("action", unit_index, 0),
                opaque("action", unit_index, 1),
            ]
        )
        correct_action = actions[unit_index % 2]
        wrong_action = actions[1 - (unit_index % 2)]
        time_base = 1000 + unit_index * 20
        decision_cutoff = time_base + 9

        relevant = [
            record(
                unit_index,
                "relevant-0",
                organization_id,
                predicate,
                correct_action,
                time_base + 1,
            ),
            record(
                unit_index,
                "relevant-1",
                organization_id,
                predicate,
                correct_action,
                time_base + 2,
            ),
        ]

        collisions: list[dict[str, Any]] = []
        if family == "f1":
            collisions = [
                record(
                    unit_index,
                    "collision-0",
                    other_organization_id,
                    predicate,
                    wrong_action,
                    time_base + 3,
                ),
                record(
                    unit_index,
                    "collision-1",
                    other_organization_id,
                    predicate,
                    wrong_action,
                    time_base + 4,
                ),
            ]
        elif family == "f2":
            collisions = [
                record(
                    unit_index,
                    "collision-0",
                    organization_id,
                    other_predicate,
                    wrong_action,
                    time_base + 3,
                ),
                record(
                    unit_index,
                    "collision-1",
                    organization_id,
                    other_predicate,
                    wrong_action,
                    time_base + 4,
                ),
            ]

        future = record(
            unit_index,
            "future",
            organization_id,
            predicate,
            wrong_action,
            time_base + 11,
        )
        unit_records = relevant + collisions + [future]
        evidence_records.extend(unit_records)

        flat_pre_cutoff = sorted(
            [
                row
                for row in unit_records
                if int(row["observed_at"]) <= decision_cutoff
            ],
            key=lambda row: (int(row["observed_at"]), str(row["record_id"])),
        )
        flat_window = flat_pre_cutoff[-2:]

        unit_id = opaque("unit", unit_index)
        plane_e_units.append(
            {
                "unit_id": unit_id,
                "organization_id": organization_id,
                "predicate": predicate,
                "decision_cutoff": decision_cutoff,
                "result_limit": 2,
                "actions": actions,
                "query_id": opaque("query", unit_index),
            }
        )
        plane_k_units.append(
            {
                "unit_id": unit_id,
                "family": family,
                "correct_action": correct_action,
                "wrong_action": wrong_action,
                "expected_relevant_record_ids": [
                    row["record_id"] for row in relevant
                ],
                "expected_flat_record_ids": [
                    row["record_id"] for row in flat_window
                ],
                "expected_structured_record_ids": [
                    row["record_id"] for row in relevant
                ],
                "expected_no_history_action": actions[0],
                "expected_flat_action": (
                    correct_action if family == "f0" else wrong_action
                ),
                "expected_structured_action": correct_action,
                "future_record_id": future["record_id"],
                "hidden_private_sentinel": opaque("private", unit_index),
            }
        )

    plane_e = {
        "schema": "h1-plane-e-v0.1",
        "base_revision": BASE_REVISION,
        "contextgraph_release_commit": CONTEXTGRAPH_RELEASE_COMMIT,
        "result_limit": 2,
        "units": plane_e_units,
        "evidence_records": sorted(
            evidence_records,
            key=lambda row: (int(row["observed_at"]), str(row["record_id"])),
        ),
    }
    plane_k = {
        "schema": "h1-plane-k-v0.1",
        "units": plane_k_units,
    }
    fixture_manifest = {
        "schema": "h1-fixture-manifest-v0.1",
        "base_revision": BASE_REVISION,
        "contextgraph_release_commit": CONTEXTGRAPH_RELEASE_COMMIT,
        "unit_count": 30,
        "family_counts": {"f0": 10, "f1": 10, "f2": 10},
        "result_limit": 2,
        "correct_action_balance": {
            "lexicographic_first": 15,
            "lexicographic_second": 15,
        },
        "evidence_record_count": len(evidence_records),
        "future_record_count": 30,
        "collision_record_count": 40,
    }
    return plane_e, plane_k, fixture_manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", required=True, type=Path)
    args = parser.parse_args()

    plane_e, plane_k, fixture_manifest = materialize()
    (args.output_root / "plane_e").mkdir(parents=True, exist_ok=True)
    (args.output_root / "plane_k").mkdir(parents=True, exist_ok=True)
    (args.output_root / "meta").mkdir(parents=True, exist_ok=True)

    outputs = {
        "plane_e/evidence.json": plane_e,
        "plane_k/evaluator.json": plane_k,
        "meta/fixture-manifest.json": fixture_manifest,
    }
    file_hashes: dict[str, str] = {}
    for relative, value in outputs.items():
        path = args.output_root / relative
        payload = canonical_bytes(value)
        path.write_bytes(payload)
        file_hashes[relative] = hashlib.sha256(payload).hexdigest()

    materialization_manifest = {
        "schema": "h1-materialization-manifest-v0.1",
        "base_revision": BASE_REVISION,
        "contextgraph_release_commit": CONTEXTGRAPH_RELEASE_COMMIT,
        "files": file_hashes,
    }
    (args.output_root / "materialization-manifest.json").write_bytes(
        canonical_bytes(materialization_manifest)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
