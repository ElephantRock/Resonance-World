#!/usr/bin/env python3
"""Materialize the preregistered H4 stochastic-successor fixtures."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

WORLD_BASE = "392e9648fec9c4431fbf695cdd82a23c3ce11f48"
CONTEXTGRAPH_COMMIT = "b896891108fd954869a8cd0423f6e8440ab0cdc0"
MODEL = "glm-5-turbo"
MODEL_ENDPOINT = "https://api.z.ai/api/coding/paas/v4/chat/completions"
FAMILIES = ("temporal_latest", "two_key_composition", "provenance_temporal")
GENERATIONS = ("g1", "g2", "g3")
REPLICATES = ("r1", "r2", "r3")
ARMS = (
    "no_history",
    "flat_accumulating_history",
    "structured_static_history",
    "structured_accumulating_history",
)
RESULT_LIMIT = 6


def cb(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def hid(prefix: str, value: Any) -> str:
    return prefix + hashlib.sha256(cb(value)).hexdigest()[:24]


def record(
    *,
    record_id: str,
    organization_id: str,
    predicate: str,
    observed_at: int,
    observed_by: str,
    source_id: str,
    source_class: str,
    direct: bool,
    record_kind: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    return {
        "record_id": record_id,
        "organization_id": organization_id,
        "predicate": predicate,
        "observed_at": observed_at,
        "observed_by": observed_by,
        "source_id": source_id,
        "source_class": source_class,
        "confidence": 1.0,
        "direct": direct,
        "record_kind": record_kind,
        "payload": payload,
    }


def lesson_payload(
    family: str,
    generation: str,
    correct_position: int,
    unit_index: int,
) -> tuple[dict[str, Any], str, bool]:
    if family == "temporal_latest":
        return (
            {"decision_token": "FIRST" if correct_position == 0 else "SECOND"},
            "direct",
            True,
        )
    if family == "two_key_composition":
        first = unit_index % 2
        if generation == "g1":
            bit = first
        elif generation == "g2":
            bit = first ^ correct_position
        else:
            bit = (unit_index + 1) % 2
        return ({"key_part": bit}, "direct", True)
    if family == "provenance_temporal":
        if generation == "g1":
            return ({"signal": unit_index % 2}, "secondary", False)
        if generation == "g2":
            older = unit_index % 2
            signal = older if correct_position == 0 else 1 - older
            return ({"signal": signal}, "direct", True)
        return ({"signal": (unit_index + 1) % 2}, "direct", True)
    raise ValueError(family)


def materialize() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    units: list[dict[str, Any]] = []
    evaluator_units: list[dict[str, Any]] = []
    evidence_records: list[dict[str, Any]] = []
    legacy_records: list[dict[str, Any]] = []

    for idx in range(12):
        family = FAMILIES[idx // 4]
        unit_id = f"h4-u{idx:02d}"
        org = f"org-{hashlib.sha256((unit_id + '-org').encode()).hexdigest()[:10]}"
        predicate = f"pred-{hashlib.sha256((unit_id + '-pred').encode()).hexdigest()[:10]}"
        raw_actions = [
            f"act-{hashlib.sha256((unit_id + '-a').encode()).hexdigest()[:10]}",
            f"act-{hashlib.sha256((unit_id + '-b').encode()).hexdigest()[:10]}",
        ]
        actions = sorted(raw_actions)
        correct_position = idx % 2
        correct_action = actions[correct_position]
        cutoffs = {
            generation: (generation_index + 1) * 100_000 + idx * 100
            for generation_index, generation in enumerate(GENERATIONS)
        }
        members = {
            replicate: {
                generation: (
                    f"member-{replicate}-{generation}-"
                    f"{hashlib.sha256((unit_id + replicate + generation).encode()).hexdigest()[:12]}"
                )
                for generation in GENERATIONS
            }
            for replicate in REPLICATES
        }
        query_ids = {
            generation: hid("h4-query-", {"unit": unit_id, "generation": generation})
            for generation in GENERATIONS
        }
        units.append(
            {
                "unit_id": unit_id,
                "family": family,
                "organization_id": org,
                "predicate": predicate,
                "actions": actions,
                "decision_cutoffs": cutoffs,
                "members": members,
                "query_ids": query_ids,
                "result_limit": RESULT_LIMIT,
            }
        )
        evaluator_units.append(
            {
                "unit_id": unit_id,
                "correct_action": correct_action,
                "correct_position": correct_position,
            }
        )

        legacy = record(
            record_id=f"{unit_id}-legacy",
            organization_id=org,
            predicate=predicate,
            observed_at=idx * 100 + 1,
            observed_by="founder-observer",
            source_id=f"{unit_id}-legacy-source",
            source_class="legacy",
            direct=False,
            record_kind="legacy_note",
            payload={
                "note_token": hashlib.sha256((unit_id + "legacy").encode()).hexdigest()[:8]
            },
        )
        evidence_records.append(legacy)
        legacy_records.append(legacy)

        for generation_index, generation in enumerate(GENERATIONS):
            cutoff = cutoffs[generation]
            for collision_index in range(RESULT_LIMIT):
                collision = record(
                    record_id=f"{unit_id}-{generation}-collision-{collision_index}",
                    organization_id=(
                        f"decoy-org-{idx:02d}-{generation_index}-{collision_index}"
                    ),
                    predicate=(
                        f"decoy-pred-{idx:02d}-{generation_index}-{collision_index}"
                    ),
                    observed_at=cutoff - RESULT_LIMIT + collision_index,
                    observed_by="decoy-observer",
                    source_id=(
                        f"decoy-source-{idx:02d}-{generation_index}-{collision_index}"
                    ),
                    source_class="direct" if collision_index % 2 == 0 else "secondary",
                    direct=collision_index % 2 == 0,
                    record_kind="predecessor_lesson",
                    payload={
                        "decision_token": (
                            "FIRST" if collision_index % 2 == 0 else "SECOND"
                        ),
                        "key_part": collision_index % 2,
                        "signal": (collision_index + idx) % 2,
                    },
                )
                evidence_records.append(collision)
                if generation == "g1":
                    legacy_records.append(collision)

            payload, source_class, direct = lesson_payload(
                family,
                generation,
                correct_position,
                idx,
            )
            evidence_records.append(
                record(
                    record_id=f"{unit_id}-{generation}-lesson",
                    organization_id=org,
                    predicate=predicate,
                    observed_at=cutoff + 1,
                    observed_by=f"world-observer-{generation}",
                    source_id=f"{unit_id}-{generation}-consequence",
                    source_class=source_class,
                    direct=direct,
                    record_kind="predecessor_lesson",
                    payload=payload,
                )
            )

    plane_e = {
        "schema": "h4-plane-e-v0.1",
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
        "history_arms": list(ARMS),
        "result_limit": RESULT_LIMIT,
        "units": units,
        "legacy_records": sorted(
            legacy_records,
            key=lambda row: (row["observed_at"], row["record_id"]),
        ),
        "evidence_records": sorted(
            evidence_records,
            key=lambda row: (row["observed_at"], row["record_id"]),
        ),
        "private_evaluator_sentinel": "ABSENT_FROM_PLANE_E_BY_CONSTRUCTION",
    }
    plane_k = {
        "schema": "h4-plane-k-v0.1",
        "private_evaluator_sentinel": "H4_PRIVATE_EVALUATOR_SENTINEL_9A71",
        "units": evaluator_units,
    }
    manifest = {
        "schema": "h4-fixture-manifest-v0.1",
        "unit_count": len(units),
        "logical_cell_count": (
            len(units) * len(GENERATIONS) * len(REPLICATES) * len(ARMS)
        ),
        "canonical_record_count": len(evidence_records),
        "legacy_record_count": len(legacy_records),
        "correct_position_balance": {
            "first": sum(
                1 for unit in evaluator_units if unit["correct_position"] == 0
            ),
            "second": sum(
                1 for unit in evaluator_units if unit["correct_position"] == 1
            ),
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
    print(
        json.dumps(
            {
                "plane_e_sha256": manifest["plane_e_sha256"],
                "plane_k_sha256": manifest["plane_k_sha256"],
                "fixture_manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
                "canonical_record_count": manifest["canonical_record_count"],
                "legacy_record_count": manifest["legacy_record_count"],
                "logical_cell_count": manifest["logical_cell_count"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
