"""H1 acceptance helpers."""
# ruff: noqa: E501
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

PASS = "historical_substrate_structured_bounded_value_pass"
FAIL = "historical_substrate_structured_bounded_value_failed"
CG = "b896891108fd954869a8cd0423f6e8440ab0cdc0"
H0 = "91ef1c6403adf0062b63e62447ac8683d74101e0"
BASE = "4c815a0d47b7818787750ae9f2d74dc1ff58709d"
REPRO = "two-isolated-exact-head-with-downstream-byte-compare"
REV = "h1-fixed-support-counter-v0.1"
RECORD_KEYS = {"record_id", "organization_id", "subject_id", "predicate", "support_action", "source_id", "source_class", "observed_by", "observed_at", "confidence", "direct"}


def cb(v: Any) -> bytes:
    return (json.dumps(v, sort_keys=True, separators=(",", ":")) + "\n").encode()


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError("expected JSON object")
    return value


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def corpus_sha(rows: list[dict[str, Any]]) -> str:
    rows = sorted(rows, key=lambda r: (int(r["observed_at"]), str(r["record_id"])))
    return hashlib.sha256(cb(rows)).hexdigest()


def ids(path: dict[str, Any]) -> list[str]:
    return [str(r["record_id"]) for r in path["normalized_records"]]


def semantic(path: dict[str, Any]) -> dict[str, Any]:
    d, c, a = path["decision"], path["consequence"], path["execution_acknowledgement"]
    return {
        "normalized_records": path["normalized_records"],
        "decision": {k: d[k] for k in ("controller_revision", "actions", "record_ids", "chosen_action")},
        "consequence": {k: c[k] for k in ("chosen_action", "action_accepted", "executed")},
        "ack": {k: a[k] for k in ("chosen_action", "executed")},
    }


def audit(path: dict[str, Any], kind: str) -> bool:
    h = path["history"]
    d = path["decision"]
    c = path["consequence"]
    a = path["execution_acknowledgement"]
    key = {"none": "history_input_id", "flat": "window_id", "structured": "bundle_id"}[kind]
    con_keys = {"schema", "unit_id", "decision_id", "chosen_action", "action_accepted", "executed", "consequence_id"}
    return (
        str(d["history_input_id"]) == str(h[key])
        and list(d["record_ids"]) == ids(path)
        and d["controller_revision"] == REV
        and str(c["decision_id"]) == str(d["decision_id"])
        and str(c["chosen_action"]) == str(d["chosen_action"])
        and set(c) == con_keys
        and str(a["decision_id"]) == str(d["decision_id"])
        and str(a["consequence_id"]) == str(c["consequence_id"])
        and str(a["chosen_action"]) == str(d["chosen_action"])
        and bool(a["executed"]) == bool(c["executed"])
    )
