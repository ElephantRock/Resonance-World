#!/usr/bin/env python3
"""Materialize the preregistered H0 Historical Substrate safety fixtures."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

BASE_REVISION = "039657c198f9c1bc5158031f579d74a40717828f"
SCHEMA = "h0-fixtures-v0.1"


def canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        + "\n"
    ).encode()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_bytes(value))


def opaque(*parts: object) -> str:
    raw = "|".join(str(part) for part in parts)
    return "h0-" + hashlib.sha256(("resonance-h0-v1|" + raw).encode()).hexdigest()[:24]


def claim(
    *,
    semantic_id: str,
    organization_id: str,
    subject_id: str,
    predicate: str,
    value: Any,
    observed_at: int,
) -> dict[str, Any]:
    return {
        "event_id": opaque("event", semantic_id),
        "organization_id": organization_id,
        "subject_id": subject_id,
        "predicate": predicate,
        "value": value,
        "observed_at": observed_at,
        "source_id": opaque("source", semantic_id),
        "observed_by": opaque("observer"),
        "source_class": "world-observation",
        "confidence": 1.0,
        "direct": True,
    }


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def file_manifest(directory: Path) -> dict[str, str]:
    return {
        path.relative_to(directory).as_posix(): sha256_file(path)
        for path in sorted(p for p in directory.rglob("*") if p.is_file())
    }


def manifest_root(rows: dict[str, str]) -> str:
    payload = "".join(
        f"{path}\0{digest}\n" for path, digest in sorted(rows.items())
    ).encode()
    return hashlib.sha256(payload).hexdigest()


def materialize(root: Path) -> dict[str, Any]:
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)

    org_a = opaque("org", "a")
    org_b = opaque("org", "b")
    old_actor = opaque("actor", "old")
    current_actor = opaque("actor", "current")
    subject_policy = opaque("subject", "policy")
    subject_future = opaque("subject", "future")
    subject_bound = opaque("subject", "bound")

    rows = [
        claim(
            semantic_id="policy-left",
            organization_id=org_a,
            subject_id=subject_policy,
            predicate="h0.policy.signal",
            value="left",
            observed_at=10,
        ),
        claim(
            semantic_id="policy-right",
            organization_id=org_a,
            subject_id=subject_policy,
            predicate="h0.policy.signal",
            value="right",
            observed_at=12,
        ),
        claim(
            semantic_id="historical-authority",
            organization_id=org_a,
            subject_id=old_actor,
            predicate="h0.authority.active",
            value=True,
            observed_at=14,
        ),
        claim(
            semantic_id="bound-1",
            organization_id=org_a,
            subject_id=subject_bound,
            predicate="h0.bound.signal",
            value=1,
            observed_at=15,
        ),
        claim(
            semantic_id="bound-2",
            organization_id=org_a,
            subject_id=subject_bound,
            predicate="h0.bound.signal",
            value=2,
            observed_at=16,
        ),
        claim(
            semantic_id="bound-3",
            organization_id=org_a,
            subject_id=subject_bound,
            predicate="h0.bound.signal",
            value=3,
            observed_at=17,
        ),
        claim(
            semantic_id="bound-4",
            organization_id=org_a,
            subject_id=subject_bound,
            predicate="h0.bound.signal",
            value=4,
            observed_at=18,
        ),
        claim(
            semantic_id="out-of-scope",
            organization_id=org_b,
            subject_id=subject_bound,
            predicate="h0.bound.signal",
            value=999,
            observed_at=11,
        ),
        claim(
            semantic_id="future-sentinel",
            organization_id=org_a,
            subject_id=subject_future,
            predicate="h0.future.signal",
            value="future-only",
            observed_at=30,
        ),
    ]
    rows.sort(key=lambda row: (int(row["observed_at"]), str(row["event_id"])))

    plane_e = {
        "schema": "h0-plane-e-v0.1",
        "decision_cutoff": 20,
        "evidence_events": rows,
    }
    write_json(root / "plane_e/evidence.json", plane_e)

    def event_ids(predicate: str, *, org: str = org_a, cutoff: int = 20, limit: int = 100) -> list[str]:
        selected = [
            row
            for row in rows
            if row["organization_id"] == org
            and row["predicate"] == predicate
            and int(row["observed_at"]) <= cutoff
        ]
        selected.sort(key=lambda row: (int(row["observed_at"]), str(row["event_id"])))
        return [str(row["event_id"]) for row in selected[:limit]]

    queries = [
        {
            "query_id": opaque("query", "conflict"),
            "purpose": "conflicting-evidence",
            "organization_id": org_a,
            "predicate": "h0.policy.signal",
            "decision_cutoff": 20,
            "result_limit": 10,
            "expected_event_ids": event_ids("h0.policy.signal"),
        },
        {
            "query_id": opaque("query", "future"),
            "purpose": "future-exclusion",
            "organization_id": org_a,
            "predicate": "h0.future.signal",
            "decision_cutoff": 20,
            "result_limit": 10,
            "expected_event_ids": [],
        },
        {
            "query_id": opaque("query", "bound"),
            "purpose": "scope-and-bound",
            "organization_id": org_a,
            "predicate": "h0.bound.signal",
            "decision_cutoff": 20,
            "result_limit": 2,
            "expected_event_ids": event_ids("h0.bound.signal", limit=2),
        },
        {
            "query_id": opaque("query", "authority"),
            "purpose": "authority-separation",
            "organization_id": org_a,
            "predicate": "h0.authority.active",
            "decision_cutoff": 20,
            "result_limit": 10,
            "expected_event_ids": event_ids("h0.authority.active"),
        },
    ]
    write_json(
        root / "meta/query-manifest.json",
        {"schema": "h0-query-manifest-v0.1", "queries": queries},
    )

    plane_k = {
        "schema": "h0-plane-k-v0.1",
        "organization_a": org_a,
        "organization_b": org_b,
        "old_actor": old_actor,
        "current_actor": current_actor,
        "current_authority": {old_actor: False, current_actor: True},
        "future_event_id": opaque("event", "future-sentinel"),
        "hidden_private_field_fact": {
            "subject_id": old_actor,
            "private_capability": 0.9375,
        },
        "expected_queries": {row["query_id"]: row["expected_event_ids"] for row in queries},
        "forbidden_direct_edges": [
            "contextgraph_to_world_outcome_law",
            "contextgraph_to_field_capability_state",
            "contextgraph_to_automatic_authority",
            "contextgraph_to_automatic_policy",
        ],
    }
    write_json(root / "plane_k/evaluator.json", plane_k)

    fixture_manifest = {
        "schema": "h0-fixture-manifest-v0.1",
        "base_revision": BASE_REVISION,
        "decision_cutoff": 20,
        "evidence_event_count": len(rows),
        "query_count": len(queries),
        "opaque_id_prefix": "h0-",
        "treatment_arms": ["access-disabled", "bounded-history-access"],
    }
    write_json(root / "meta/fixture-manifest.json", fixture_manifest)

    roots: dict[str, Any] = {}
    for name in ("plane_e", "plane_k", "meta"):
        rows_manifest = file_manifest(root / name)
        roots[name] = {
            "file_count": len(rows_manifest),
            "manifest_root_sha256": manifest_root(rows_manifest),
            "files": rows_manifest,
        }

    manifest = {
        "schema": "h0-apparatus-materialization-v0.1",
        "base_revision": BASE_REVISION,
        "fixture_schema": SCHEMA,
        "roots": roots,
    }
    write_json(root / "materialization-manifest.json", manifest)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", required=True, type=Path)
    args = parser.parse_args()
    manifest = materialize(args.output_root)
    print(json.dumps(manifest, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
