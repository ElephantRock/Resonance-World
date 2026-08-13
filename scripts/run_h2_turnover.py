#!/usr/bin/env python3
"""Run the preregistered H2 member-turnover benchmark."""
# ruff: noqa: E501
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from h1_runtime_core import (
    CG,
    NI,
    cb,
    cg_records,
    did,
    flat,
    norm,
    ordered,
    path,
    sentinels,
)
from resonance_world.historical_substrate import bounded_historical_evidence


def load(path_: Path) -> dict[str, Any]:
    value = json.loads(path_.read_text())
    if not isinstance(value, dict):
        raise ValueError("expected JSON object")
    return value


def local_input(unit: dict[str, Any]) -> tuple[dict[str, Any], str, list[dict[str, Any]]]:
    rows = [dict(r) for r in unit["local_continuity_records"]]
    base = {
        "schema": "h2-member-local-continuity-v0.1",
        "unit_id": unit["unit_id"],
        "incumbent_id": unit["incumbent_id"],
        "records": rows,
    }
    input_id = did("h2-local-", base)
    return {**base, "continuity_id": input_id}, input_id, rows


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--plane-e", required=True, type=Path)
    p.add_argument("--output-dir", required=True, type=Path)
    a = p.parse_args()
    evidence = load(a.plane_e)
    source = ordered([dict(row) for row in evidence["evidence_records"]])
    structured = cg_records(source)
    if source != norm(structured):
        raise ValueError("flat and ContextGraph corpora differ")

    cells: list[dict[str, Any]] = []
    for turnover in evidence["turnover_levels"]:
        for arm in evidence["history_arms"]:
            for raw in evidence["units"]:
                unit = dict(raw)
                replaced = bool(unit["replaced"][turnover])
                if not replaced:
                    hist, input_id, rows = local_input(unit)
                    member_id = str(unit["incumbent_id"])
                    source_kind = "member_local_continuity"
                    run_path = path(unit, hist, input_id, rows)
                else:
                    member_id = did("h2-successor-", {"unit_id": unit["unit_id"], "turnover": turnover})
                    request = {
                        "query_id": unit["query_id"],
                        "requesting_organization_id": unit["organization_id"],
                        "predicate": unit["predicate"],
                        "decision_cutoff": unit["decision_cutoff"],
                        "result_limit": unit["result_limit"],
                        "evidence_release_commit": CG,
                    }
                    if arm == "no_history":
                        denial = bounded_historical_evidence(structured, enabled=False, **request)
                        input_id = did("h2-no-history-", {"unit_id": unit["unit_id"], "turnover": turnover})
                        hist = {
                            "schema": "h2-no-history-v0.1",
                            "history_input_id": input_id,
                            "query_denial": denial,
                        }
                        run_path = path(unit, hist, input_id, [])
                        source_kind = "no_history"
                    elif arm == "flat_history":
                        window = flat(source, unit)
                        run_path = path(
                            unit,
                            window,
                            window["window_id"],
                            [dict(row) for row in window["records"]],
                        )
                        source_kind = "flat_history"
                    elif arm == "structured_history":
                        bundle = bounded_historical_evidence(structured, enabled=True, **request)
                        run_path = path(
                            unit,
                            bundle,
                            bundle["bundle_id"],
                            norm(list(bundle["evidence"])),
                        )
                        source_kind = "structured_history"
                    else:
                        raise ValueError(f"unknown history arm: {arm}")
                cells.append({
                    "unit_id": unit["unit_id"],
                    "turnover": turnover,
                    "history_arm": arm,
                    "replaced": replaced,
                    "member_id": member_id,
                    "source_kind": source_kind,
                    "path": run_path,
                })

    corpus_sha = hashlib.sha256(cb(source)).hexdigest()
    plan = {
        str(u["unit_id"]): {k: bool(v) for k, v in u["replaced"].items()}
        for u in evidence["units"]
    }
    local = {
        str(u["unit_id"]): [dict(r) for r in u["local_continuity_records"]]
        for u in evidence["units"]
    }
    result = {
        "schema": "h2-researcher-output-v0.1",
        "contextgraph_release_commit": CG,
        "corpus": {
            "flat_source_sha256": corpus_sha,
            "structured_decoded_source_sha256": corpus_sha,
            "flat_source_record_count": len(source),
            "contextgraph_claim_count": len(structured),
            "structured_decoded_record_count": len(structured),
        },
        "pre_turnover": {
            "turnover_plan_sha256": hashlib.sha256(cb(plan)).hexdigest(),
            "local_continuity_sha256": hashlib.sha256(cb(local)).hexdigest(),
        },
        "cells": cells,
        "direct_edge_sentinels": sentinels(),
        "negative_controls": {
            "future_evidence": NI,
            "private_state": NI,
            "history_as_authority": NI,
        },
    }
    a.output_dir.mkdir(parents=True, exist_ok=True)
    (a.output_dir / "h2-researcher-output.json").write_bytes(cb(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
