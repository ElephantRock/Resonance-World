#!/usr/bin/env python3
"""Materialize the frozen O2 corpus plus the preregistered D2 contract amendment."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from scripts.materialize_o2_benchmarks import (
    canonical_bytes,
    file_manifest,
    manifest_root,
    materialize,
    write_json,
)

AMENDED_QUERY_ID = "contribution_vector_by_interval"


def read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def contribution_vector_by_interval(events: list[dict[str, Any]]) -> list[dict[str, int]]:
    member_rows = [row for row in events if isinstance(row.get("member_ids"), list)]
    members = sorted({str(member) for row in member_rows for member in row["member_ids"]})
    performance = [row for row in events if row.get("kind") == "performance"]
    if not members or not performance:
        raise ValueError("D2 amendment requires observable membership and performance events")
    max_interval = max(int(row["interval"]) for row in performance)
    vectors: list[dict[str, int]] = []
    for interval in range(1, max_interval + 1):
        vector = {member: 0 for member in members}
        for row in performance:
            if int(row["interval"]) != interval:
                continue
            member = str(row.get("subject_id"))
            if member in vector:
                vector[member] += int(row.get("successes", 0))
        vectors.append(vector)
    return vectors


def amend(root: Path, original_lock: Path | None) -> dict[str, Any]:
    materialize(root)

    query_path = root / "meta/query-manifest.json"
    query_manifest = read_object(query_path)
    d2_queries = list(query_manifest["templates"]["D2"])
    if any(str(row["query_id"]) == AMENDED_QUERY_ID for row in d2_queries):
        raise ValueError("D2 amended query already present in original materialization")
    d2_queries.append({"query_id": AMENDED_QUERY_ID, "kind": "identifiable"})
    query_manifest["templates"]["D2"] = d2_queries
    query_manifest["amendment_issue"] = 126
    query_manifest["amendment_schema"] = "o2-d2-contract-amendment-v0.1"
    write_json(query_path, query_manifest)

    amended_histories = 0
    d2_by_pair: dict[str, list[bytes]] = defaultdict(list)
    for key_path in sorted((root / "plane_k").glob("*.json")):
        key = read_object(key_path)
        if str(key.get("template")) != "D2":
            continue
        evidence = read_object(root / "plane_e" / key_path.name)
        vector = contribution_vector_by_interval(list(evidence["events"]))
        answers = dict(key["distinguishing_answers"])
        if AMENDED_QUERY_ID in answers:
            raise ValueError("D2 amended answer already present")
        answers[AMENDED_QUERY_ID] = vector
        key["distinguishing_answers"] = answers
        key["contract_amendment_issue"] = 126
        write_json(key_path, key)
        amended_histories += 1
        d2_by_pair[str(key["pair_id"])].append(canonical_bytes(vector))

    if amended_histories != 8:
        raise ValueError(f"expected 8 D2 histories, amended {amended_histories}")
    if len(d2_by_pair) != 4:
        raise ValueError(f"expected 4 D2 collision pairs, found {len(d2_by_pair)}")
    for pair_id, vectors in d2_by_pair.items():
        if len(vectors) != 2 or vectors[0] == vectors[1]:
            raise ValueError(f"amended D2 query does not distinguish collision pair {pair_id}")

    roots: dict[str, Any] = {}
    for name in ("plane_e", "plane_k", "r0", "r1", "meta"):
        rows = file_manifest(root / name)
        roots[name] = {
            "file_count": len(rows),
            "manifest_root_sha256": manifest_root(rows),
            "files": rows,
        }

    if original_lock is not None:
        frozen = read_object(original_lock)
        for name in ("plane_e", "r0", "r1"):
            expected = frozen["roots"][name]
            actual = roots[name]
            if (
                int(actual["file_count"]) != int(expected["file_count"])
                or str(actual["manifest_root_sha256"])
                != str(expected["manifest_root_sha256"])
            ):
                raise ValueError(f"amendment changed frozen {name} corpus")

    manifest = read_object(root / "materialization-manifest.json")
    manifest["schema"] = "o2-apparatus-materialization-v0.2"
    manifest["amendment_issue"] = 126
    manifest["amendment_query_id"] = AMENDED_QUERY_ID
    manifest["roots"] = roots
    write_json(root / "materialization-manifest.json", manifest)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--original-lock", type=Path)
    args = parser.parse_args()
    result = amend(args.output_root, args.original_lock)
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
