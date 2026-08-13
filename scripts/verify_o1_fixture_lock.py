#!/usr/bin/env python3
"""Verify the prospectively frozen O1 benchmark-plane bytes and information boundary."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

EXPECTED = {
    "plane_e/authority.json": "add7132059e94d0421e0743c9e79bb04290e550730fda82add38b88256509223",
    "plane_e/source-sustainability.json": (
        "62a80e31af5adeecd28dc08417a7744c41cd288d526fa9622c481674ed232599"
    ),
    "plane_e/turnover.json": "d81ff91370e5f2c798bb4abc004746e63240c45323a157c30be6b0f79d44c8d9",
    "plane_k/authority.json": "d00ef3349c1a746a026dbe51ed562daacfa93c57257632b8dcdd45eb3ce7b85a",
    "plane_k/source-sustainability.json": (
        "2049828d892479ad851b658ec62ab261969ff13cd6d7fcf81a622ff6ca68912e"
    ),
    "plane_k/turnover.json": "828769906112a960fb20559d67814f838f45f1c10d0ca43d77f33c5e248eac73",
}
FORBIDDEN_PLANE_E_FIELDS = {
    "practice_by_skill",
    "hidden_regime",
    "target_hypothesis",
    "target_policy",
    "neutral_preferred_policy",
    "expected_action",
    "spoof_action",
    "legitimate_notice_id",
    "spoof_notice_id",
    "classification",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AssertionError(f"{path} is not a JSON object")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--benchmark-root", type=Path, required=True)
    parser.add_argument("--provenance", type=Path, required=True)
    args = parser.parse_args()

    root = args.benchmark_root
    provenance = _read(args.provenance)
    assert provenance["fixture_sha256"] == EXPECTED
    for relative, expected in EXPECTED.items():
        path = root / relative
        assert _sha256(path) == expected, relative

    planes_e: dict[str, dict[str, object]] = {}
    for path in sorted((root / "plane_e").glob("*.json")):
        plane = _read(path)
        assert plane.get("schema") == "o1-plane-e-v0.1"
        family = str(plane["family"])
        planes_e[family] = plane
        for event in plane["events"]:  # type: ignore[index]
            fields = event["fields"]  # type: ignore[index]
            assert not FORBIDDEN_PLANE_E_FIELDS.intersection(fields)
            assert all(isinstance(value, str) for value in fields.values())

    assert set(planes_e) == {"A", "T", "S"}
    assert len(planes_e["A"]["events"]) == 120  # type: ignore[arg-type]
    assert len(planes_e["T"]["events"]) == 72  # type: ignore[arg-type]
    source_events = planes_e["S"]["events"]  # type: ignore[index]
    event_types: dict[str, int] = {}
    for event in source_events:
        event_type = str(event["fields"]["event_type"])
        event_types[event_type] = event_types.get(event_type, 0) + 1
    assert event_types == {
        "contract_service_right": 216,
        "observable_accounting_summary": 1,
        "organization_service_cycle": 72,
        "organization_service_summary": 3,
        "source_agent_public_record": 60,
    }
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
