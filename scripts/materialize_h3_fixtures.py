#!/usr/bin/env python3
"""Materialize the preregistered H3 multi-generation accumulation fixtures."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

BASE_REVISION = "230f468a234bebaddbf2245f58327a84f959c00f"
CONTEXTGRAPH_RELEASE_COMMIT = "b896891108fd954869a8cd0423f6e8440ab0cdc0"
GENERATIONS = ("g1", "g2", "g3", "g4", "g5")
ARMS = (
    "no_history",
    "flat_accumulating_history",
    "structured_static_history",
    "structured_accumulating_history",
)
RESULT_LIMIT = 7


def cb(value: Any) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
    ).encode()


def opaque(*parts: object) -> str:
    raw = "|".join(str(part) for part in parts)
    return "h3-" + hashlib.sha256(("resonance-h3-v1|" + raw).encode()).hexdigest()[:24]


def record(
    *,
    record_id: str,
    organization_id: str,
    predicate: str,
    support_action: str,
    observed_at: int,
    source_tag: str,
) -> dict[str, Any]:
    return {
        "record_id": record_id,
        "organization_id": organization_id,
        "subject_id": opaque("subject", record_id),
        "predicate": predicate,
        "support_action": support_action,
        "source_id": opaque("source", source_tag, record_id),
        "source_class": "direct-observation",
        "observed_by": opaque("observer", source_tag),
        "observed_at": observed_at,
        "confidence": 1.0,
        "direct": True,
    }


def materialize() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    units_e: list[dict[str, Any]] = []
    units_k: list[dict[str, Any]] = []
    records: list[dict[str, Any]] = []
    legacy_records: list[dict[str, Any]] = []
    family_counts = {"f1": 0, "f2": 0, "f3": 0}
    default_balance = {"lexicographic_first": 0, "lexicographic_second": 0}
    correct_balance = {"lexicographic_first": 0, "lexicographic_second": 0}

    for i in range(24):
        org_index, slot_index = divmod(i, 3)
        family = ("f1", "f2", "f3")[i % 3]
        legacy_count = int(family[1:])
        family_counts[family] += 1

        organization_id = opaque("org", org_index)
        slot_id = opaque("slot", org_index, slot_index)
        predicate = opaque("predicate", i)
        decoy_org = opaque("decoy-org", i)
        decoy_predicate = opaque("decoy-predicate", i)
        actions = sorted([opaque("action", i, 0), opaque("action", i, 1)])
        default_action = actions[i % 2]
        correct_action = actions[1 - (i % 2)]
        default_balance[
            "lexicographic_first" if default_action == actions[0] else "lexicographic_second"
        ] += 1
        correct_balance[
            "lexicographic_first" if correct_action == actions[0] else "lexicographic_second"
        ] += 1

        unit_id = opaque("unit", i)
        founder_id = opaque("founder", i)
        members = {generation: opaque("member", i, generation) for generation in GENERATIONS}
        query_ids = {generation: opaque("query", i, generation) for generation in GENERATIONS}
        cutoffs: dict[str, int] = {}
        legacy_ids: list[str] = []
        decoy_ids: dict[str, list[str]] = {}
        lesson_ids: dict[str, str] = {}

        for legacy_index in range(legacy_count):
            rid = opaque("legacy", i, legacy_index)
            legacy = record(
                record_id=rid,
                organization_id=organization_id,
                predicate=predicate,
                support_action=default_action,
                observed_at=1000 + i * 10 + legacy_index,
                source_tag=f"legacy-{i}-{legacy_index}",
            )
            legacy_ids.append(rid)
            legacy_records.append(legacy)
            records.append(legacy)

        for generation_index, generation in enumerate(GENERATIONS, start=1):
            base_time = generation_index * 100_000 + i * 100
            ids: list[str] = []
            for decoy_index in range(7):
                rid = opaque("decoy", i, generation, decoy_index)
                if decoy_index % 2 == 0:
                    d_org = decoy_org
                    d_predicate = predicate
                else:
                    d_org = organization_id
                    d_predicate = decoy_predicate
                decoy = record(
                    record_id=rid,
                    organization_id=d_org,
                    predicate=d_predicate,
                    support_action=default_action,
                    observed_at=base_time + decoy_index + 1,
                    source_tag=f"decoy-{i}-{generation}-{decoy_index}",
                )
                ids.append(rid)
                records.append(decoy)
            decoy_ids[generation] = ids
            cutoff = base_time + 8
            cutoffs[generation] = cutoff
            lesson_rid = opaque("lesson", i, generation)
            lesson = record(
                record_id=lesson_rid,
                organization_id=organization_id,
                predicate=predicate,
                support_action=correct_action,
                observed_at=base_time + 9,
                source_tag=f"lesson-{i}-{generation}",
            )
            lesson_ids[generation] = lesson_rid
            records.append(lesson)

        units_e.append(
            {
                "unit_id": unit_id,
                "organization_id": organization_id,
                "slot_id": slot_id,
                "predicate": predicate,
                "actions": actions,
                "default_action": default_action,
                "founder_id": founder_id,
                "members": members,
                "query_ids": query_ids,
                "decision_cutoffs": cutoffs,
                "result_limit": RESULT_LIMIT,
            }
        )
        units_k.append(
            {
                "unit_id": unit_id,
                "family": family,
                "correct_action": correct_action,
                "legacy_record_ids": legacy_ids,
                "decoy_record_ids": decoy_ids,
                "lesson_record_ids": lesson_ids,
                "first_correct_generation": {"f1": "g3", "f2": "g4", "f3": "g5"}[family],
                "private_sentinel": opaque("private", i),
            }
        )

    ordered_records = sorted(
        records, key=lambda row: (int(row["observed_at"]), str(row["record_id"]))
    )
    ordered_legacy = sorted(
        legacy_records, key=lambda row: (int(row["observed_at"]), str(row["record_id"]))
    )
    plane_e = {
        "schema": "h3-plane-e-v0.1",
        "base_revision": BASE_REVISION,
        "contextgraph_release_commit": CONTEXTGRAPH_RELEASE_COMMIT,
        "generations": list(GENERATIONS),
        "history_arms": list(ARMS),
        "result_limit": RESULT_LIMIT,
        "units": units_e,
        "legacy_records": ordered_legacy,
        "evidence_records": ordered_records,
    }
    plane_k = {"schema": "h3-plane-k-v0.1", "units": units_k}
    fixture_manifest = {
        "schema": "h3-fixture-manifest-v0.1",
        "base_revision": BASE_REVISION,
        "unit_count": 24,
        "organization_count": 8,
        "slots_per_organization": 3,
        "generation_count": 5,
        "cell_count": 24 * 5 * 4,
        "family_counts": family_counts,
        "complete_turnover_per_generation": {generation: 24 for generation in GENERATIONS},
        "result_limit": RESULT_LIMIT,
        "default_action_balance": default_balance,
        "correct_action_balance": correct_balance,
        "legacy_record_count": len(ordered_legacy),
        "collision_record_count": 24 * 5 * 7,
        "lesson_record_count": 24 * 5,
        "evidence_record_count": len(ordered_records),
    }
    return plane_e, plane_k, fixture_manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", required=True, type=Path)
    args = parser.parse_args()
    plane_e, plane_k, manifest = materialize()
    outputs = {
        "plane_e/evidence.json": plane_e,
        "plane_k/evaluator.json": plane_k,
        "meta/fixture-manifest.json": manifest,
    }
    hashes: dict[str, str] = {}
    for relative, value in outputs.items():
        path = args.output_root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = cb(value)
        path.write_bytes(payload)
        hashes[relative] = hashlib.sha256(payload).hexdigest()
    materialization_manifest = {
        "schema": "h3-materialization-manifest-v0.1",
        "base_revision": BASE_REVISION,
        "contextgraph_release_commit": CONTEXTGRAPH_RELEASE_COMMIT,
        "files": hashes,
    }
    (args.output_root / "materialization-manifest.json").write_bytes(cb(materialization_manifest))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
