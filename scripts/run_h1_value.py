#!/usr/bin/env python3
"""H1 experiment runner."""
# ruff: noqa: E501
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from h1_runtime_core import CG, NI, cb, cg_records, did, flat, norm, ordered, path, sentinels
from resonance_world.historical_substrate import bounded_historical_evidence


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError("expected JSON object")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plane-e", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    evidence = load(args.plane_e)
    source = ordered([dict(row) for row in evidence["evidence_records"]])
    structured = cg_records(source)
    if source != norm(structured):
        raise ValueError("flat and ContextGraph corpora differ")
    outputs = []
    for raw in evidence["units"]:
        unit = dict(raw)
        request = {
            "query_id": unit["query_id"],
            "requesting_organization_id": unit["organization_id"],
            "predicate": unit["predicate"],
            "decision_cutoff": unit["decision_cutoff"],
            "result_limit": unit["result_limit"],
            "evidence_release_commit": CG,
        }
        denial = bounded_historical_evidence(structured, enabled=False, **request)
        none_id = did("h1-no-history-", {"unit_id": unit["unit_id"], "query_id": unit["query_id"]})
        no_history = path(unit, {"schema": "h1-no-history-v0.1", "history_input_id": none_id, "query_denial": denial}, none_id, [])
        window = flat(source, unit)
        flat_history = path(unit, window, window["window_id"], [dict(row) for row in window["records"]])
        bundle = bounded_historical_evidence(structured, enabled=True, **request)
        structured_history = path(unit, bundle, bundle["bundle_id"], norm(list(bundle["evidence"])))
        outputs.append({"unit_id": unit["unit_id"], "actions": sorted(unit["actions"]), "no_history": no_history, "flat_history": flat_history, "structured_history": structured_history})
    corpus_sha = hashlib.sha256(cb(source)).hexdigest()
    result = {
        "schema": "h1-researcher-output-v0.1",
        "contextgraph_release_commit": CG,
        "corpus": {
            "flat_source_sha256": corpus_sha,
            "structured_decoded_source_sha256": corpus_sha,
            "flat_source_record_count": len(source),
            "contextgraph_claim_count": len(structured),
            "structured_decoded_record_count": len(structured),
        },
        "units": outputs,
        "direct_edge_sentinels": sentinels(),
        "negative_controls": {"future_evidence": NI, "private_state": NI, "history_as_authority": NI},
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "h1-researcher-output.json").write_bytes(cb(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
