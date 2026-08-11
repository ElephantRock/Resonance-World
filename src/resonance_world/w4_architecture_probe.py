"""Probe pinned Field and W3 source trees for W4-00 architecture evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _read(root: Path, relative: str) -> str:
    path = root / relative
    if not path.is_file():
        raise ValueError(f"required audited source is missing: {path}")
    return path.read_text(encoding="utf-8")


def _require(text: str, needle: str, *, label: str) -> None:
    if needle not in text:
        raise ValueError(f"{label}: missing required source evidence: {needle!r}")


def _forbid(text: str, needle: str, *, label: str) -> None:
    if needle in text:
        raise ValueError(f"{label}: unexpected pair-state marker found: {needle!r}")


def probe(field_root: str | Path, w3_world_root: str | Path) -> dict[str, Any]:
    field_root = Path(field_root)
    w3_world_root = Path(w3_world_root)

    integration = _read(field_root, "src/resonance/experiments/integration_campaign.py")
    traces = _read(field_root, "src/resonance/substrate/models.py")
    topology = _read(field_root, "migrations/014_coordination_topology_experiments.sql")
    w3_export = _read(w3_world_root, "src/resonance_world/w3_source_export.py")
    w3_core = _read(w3_world_root, "src/resonance_world/w3_swarm_core.py")

    _require(
        integration,
        "practice: dict[tuple[int, str], int] = {}",
        label="Field individual practice",
    )
    _require(
        integration,
        "practice.get((winner_slot, required_skill), 0)",
        label="Field individual practice lookup",
    )
    _require(
        integration,
        "practice[(winner_slot, required_skill)] = practiced + 1",
        label="Field individual practice update",
    )

    _require(traces, "class Trace:", label="Field trace model")
    _require(traces, "author_agent_id", label="Field trace model")
    _require(traces, 'visibility: str = "shared"', label="Field trace model")
    for marker in ("pair_id", "partner_id", "partner_agent_id", "pair_owner"):
        _forbid(traces, marker, label="Field trace model")

    _require(
        topology,
        "CREATE TABLE IF NOT EXISTS topology_opportunity_observations",
        label="Field topology evidence",
    )
    _require(
        topology,
        "PRIMARY KEY (run_id, cycle, candidate_slot)",
        label="Field topology evidence",
    )

    _require(
        w3_export,
        '"coordination_exposure": successful',
        label="World W3 coordination proxy derivation",
    )
    _require(
        w3_export,
        '"interaction_count": interactions',
        label="World W3 interaction proxy derivation",
    )
    _require(
        w3_core,
        'float(law["coordination_gain"]) * math.sqrt(max(0.0, coordination_exposure))',
        label="World W3 direct coordination outcome effect",
    )
    _require(
        w3_core,
        'float(law["maximum_coordination_bonus"]), bonus',
        label="World W3 coordination bonus cap",
    )

    return {
        "classification": "A_NO_NATIVE_PAIR_STATE",
        "field_individual_practice_verified": True,
        "field_pair_owned_trace_state_absent": True,
        "field_topology_is_observation_evidence": True,
        "w3_coordination_exposure_is_world_derived": True,
        "w3_coordination_exposure_has_direct_outcome_effect": True,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("field_root", type=Path)
    parser.add_argument("w3_world_root", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)

    payload = json.dumps(probe(args.field_root, args.w3_world_root), indent=2, sort_keys=True) + "\n"
    if args.output is None:
        print(payload, end="")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
