#!/usr/bin/env python3
"""Run the preregistered H3 multi-generation accumulation benchmark."""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from h1_runtime_core import CG, NI, cb, cg_records, did, norm, ordered, sentinels
from resonance_world.historical_substrate import bounded_historical_evidence

CONTROLLER_REVISION = "h3-fixed-support-counter-default-tie-v0.1"


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError("expected JSON object")
    return value


def flat_window(source: list[dict[str, Any]], unit: dict[str, Any], generation: str) -> dict[str, Any]:
    cutoff = int(unit["decision_cutoffs"][generation])
    limit = int(unit["result_limit"])
    rows = ordered([row for row in source if int(row["observed_at"]) <= cutoff])[-limit:]
    base = {
        "schema": "h3-flat-history-window-v0.1",
        "unit_id": unit["unit_id"],
        "generation": generation,
        "decision_cutoff": cutoff,
        "result_limit": limit,
        "records": rows,
    }
    return {**base, "window_id": did("h3-flat-window-", base)}


def decision(
    unit: dict[str, Any],
    generation: str,
    history_input_id: str,
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    actions = sorted(str(action) for action in unit["actions"])
    counts = Counter(str(row["support_action"]) for row in rows)
    if set(counts) - set(actions):
        raise ValueError("unsupported action")
    top = max((counts[action] for action in actions), default=0)
    leaders = [action for action in actions if counts[action] == top]
    default_action = str(unit["default_action"])
    chosen = default_action if len(leaders) != 1 else leaders[0]
    base = {
        "schema": "h3-controller-decision-v0.1",
        "controller_revision": CONTROLLER_REVISION,
        "unit_id": unit["unit_id"],
        "generation": generation,
        "actions": actions,
        "history_input_id": history_input_id,
        "record_ids": [row["record_id"] for row in rows],
        "chosen_action": chosen,
    }
    return {**base, "decision_id": did("h3-decision-", base)}


def path(
    unit: dict[str, Any],
    generation: str,
    history: dict[str, Any],
    history_input_id: str,
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    dec = decision(unit, generation, history_input_id, rows)
    accepted = dec["chosen_action"] in unit["actions"]
    consequence = {
        "schema": "h3-world-consequence-v0.1",
        "unit_id": unit["unit_id"],
        "generation": generation,
        "decision_id": dec["decision_id"],
        "chosen_action": dec["chosen_action"],
        "action_accepted": accepted,
        "executed": accepted,
    }
    consequence["consequence_id"] = did("h3-consequence-", consequence)
    acknowledgement = {
        "schema": "h3-execution-ack-v0.1",
        "decision_id": dec["decision_id"],
        "consequence_id": consequence["consequence_id"],
        "chosen_action": dec["chosen_action"],
        "executed": consequence["executed"],
    }
    acknowledgement["ack_id"] = did("h3-ack-", acknowledgement)
    return {
        "history": history,
        "normalized_records": rows,
        "decision": dec,
        "consequence": consequence,
        "execution_acknowledgement": acknowledgement,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plane-e", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()

    evidence = load(args.plane_e)
    source = ordered([dict(row) for row in evidence["evidence_records"]])
    legacy_source = ordered([dict(row) for row in evidence["legacy_records"]])
    structured_accumulating = cg_records(source)
    structured_static = cg_records(legacy_source)
    if source != norm(structured_accumulating):
        raise ValueError("flat and accumulating ContextGraph corpora differ")
    if legacy_source != norm(structured_static):
        raise ValueError("static legacy corpus and ContextGraph snapshot differ")

    cells: list[dict[str, Any]] = []
    for generation in evidence["generations"]:
        for arm in evidence["history_arms"]:
            for raw_unit in evidence["units"]:
                unit = dict(raw_unit)
                request = {
                    "query_id": unit["query_ids"][generation],
                    "requesting_organization_id": unit["organization_id"],
                    "predicate": unit["predicate"],
                    "decision_cutoff": unit["decision_cutoffs"][generation],
                    "result_limit": unit["result_limit"],
                    "evidence_release_commit": CG,
                }
                if arm == "no_history":
                    denial = bounded_historical_evidence(
                        structured_accumulating, enabled=False, **request
                    )
                    input_id = did(
                        "h3-no-history-",
                        {"unit_id": unit["unit_id"], "generation": generation},
                    )
                    history = {
                        "schema": "h3-no-history-v0.1",
                        "history_input_id": input_id,
                        "query_denial": denial,
                    }
                    rows: list[dict[str, Any]] = []
                    source_kind = "no_history"
                elif arm == "flat_accumulating_history":
                    history = flat_window(source, unit, generation)
                    input_id = str(history["window_id"])
                    rows = [dict(row) for row in history["records"]]
                    source_kind = "flat_accumulating_history"
                elif arm == "structured_static_history":
                    bundle = bounded_historical_evidence(
                        structured_static, enabled=True, **request
                    )
                    history = bundle
                    input_id = str(bundle["bundle_id"])
                    rows = norm(list(bundle["evidence"]))
                    source_kind = "structured_static_history"
                elif arm == "structured_accumulating_history":
                    bundle = bounded_historical_evidence(
                        structured_accumulating, enabled=True, **request
                    )
                    history = bundle
                    input_id = str(bundle["bundle_id"])
                    rows = norm(list(bundle["evidence"]))
                    source_kind = "structured_accumulating_history"
                else:
                    raise ValueError(f"unknown history arm: {arm}")

                cells.append(
                    {
                        "unit_id": unit["unit_id"],
                        "generation": generation,
                        "history_arm": arm,
                        "member_id": unit["members"][generation],
                        "source_kind": source_kind,
                        "path": path(unit, generation, history, input_id, rows),
                    }
                )

    source_sha = hashlib.sha256(cb(source)).hexdigest()
    legacy_sha = hashlib.sha256(cb(legacy_source)).hexdigest()
    turnover_plan = {
        str(unit["unit_id"]): {
            "founder_id": unit["founder_id"],
            "members": dict(unit["members"]),
        }
        for unit in evidence["units"]
    }
    cutoffs = {
        str(unit["unit_id"]): dict(unit["decision_cutoffs"]) for unit in evidence["units"]
    }
    result = {
        "schema": "h3-researcher-output-v0.1",
        "contextgraph_release_commit": CG,
        "controller_revision": CONTROLLER_REVISION,
        "corpus": {
            "flat_accumulating_source_sha256": source_sha,
            "structured_accumulating_decoded_source_sha256": source_sha,
            "structured_static_source_sha256": legacy_sha,
            "flat_accumulating_source_record_count": len(source),
            "structured_accumulating_claim_count": len(structured_accumulating),
            "structured_static_claim_count": len(structured_static),
        },
        "pre_generation": {
            "turnover_plan_sha256": hashlib.sha256(cb(turnover_plan)).hexdigest(),
            "decision_cutoffs_sha256": hashlib.sha256(cb(cutoffs)).hexdigest(),
            "legacy_snapshot_sha256": legacy_sha,
        },
        "cells": cells,
        "direct_edge_sentinels": sentinels(),
        "negative_controls": {
            "future_evidence_as_current_authority": NI,
            "private_evaluator_state": NI,
            "history_as_world_outcome_law": NI,
        },
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "h3-researcher-output.json").write_bytes(cb(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
