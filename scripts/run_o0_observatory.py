#!/usr/bin/env python3
"""Run the frozen O0 joint-learning schedule with or without the Observatory.

This script is intentionally compatible with the pre-O0 World base when invoked with
``--mode baseline``. The ContextGraph observer is imported only for the instrumented arm.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from resonance_world.w4a_joint_learning import (
    CommunicationPolicy,
    IndividualState,
    JointController,
    JointEnvironment,
    JointLearningSession,
    JointMission,
    RelationshipStateStore,
)

SEEDS = (7001, 7103, 7207, 7309, 7411)
COMMUNICATION_CONDITIONS = (
    ("communication-0", 0),
    ("communication-1", 1),
)
PAIRS = (
    ("agent-a", "agent-b"),
    ("agent-c", "agent-d"),
    ("agent-a", "agent-c"),
    ("agent-b", "agent-d"),
    ("agent-a", "agent-d"),
    ("agent-b", "agent-c"),
)
CONTEXTS = (
    "o0-context-alpha",
    "o0-context-beta",
    "o0-context-alpha",
    "o0-context-beta",
)
LEAD_SKILL = "planning"
SUPPORT_SKILL = "verification"
ENVIRONMENT = JointEnvironment()


def _canonical_bytes(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _agents() -> dict[str, IndividualState]:
    return {
        "agent-a": IndividualState("agent-a", {"planning": 9, "verification": 1}),
        "agent-b": IndividualState("agent-b", {"planning": 9, "verification": 1}),
        "agent-c": IndividualState("agent-c", {"planning": 1, "verification": 9}),
        "agent-d": IndividualState("agent-d", {"planning": 1, "verification": 9}),
    }


def _mission_id(condition: str, seed: int, cycle: int, pair_index: int) -> str:
    return f"o0:{condition}:{seed}:cycle:{cycle}:pair:{pair_index}"


def run(mode: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if mode not in {"baseline", "observatory"}:
        raise ValueError(f"unsupported mode: {mode}")

    observatory_type = None
    if mode == "observatory":
        from resonance_world.observatory import ContextGraphObservatory

        observatory_type = ContextGraphObservatory

    units: list[dict[str, Any]] = []
    evidence: list[dict[str, Any]] = []
    for condition, bandwidth_bits in COMMUNICATION_CONDITIONS:
        for seed in SEEDS:
            agents = _agents()
            relationships = RelationshipStateStore()
            scope_id = f"o0:{condition}:{seed}"
            observer = observatory_type(scope_id=scope_id) if observatory_type is not None else None
            if observer is None:
                session = JointLearningSession(
                    environment=ENVIRONMENT,
                    controller=JointController(),
                    relationships=relationships,
                    communication=CommunicationPolicy(bandwidth_bits=bandwidth_bits),
                )
            else:
                session = JointLearningSession(
                    environment=ENVIRONMENT,
                    controller=JointController(),
                    relationships=relationships,
                    communication=CommunicationPolicy(bandwidth_bits=bandwidth_bits),
                    observer=observer,
                )

            episodes: list[dict[str, Any]] = []
            for cycle, context in enumerate(CONTEXTS):
                for pair_index, (first_id, second_id) in enumerate(PAIRS):
                    mission = JointMission(
                        mission_id=_mission_id(condition, seed, cycle, pair_index),
                        context=context,
                        lead_skill=LEAD_SKILL,
                        support_skill=SUPPORT_SKILL,
                    )
                    episode = session.run_episode(
                        agents[first_id],
                        agents[second_id],
                        mission,
                        seed=seed + cycle * 100 + pair_index,
                    )
                    episodes.append(asdict(episode))

            units.append(
                {
                    "communication_condition": condition,
                    "bandwidth_bits": bandwidth_bits,
                    "seed": seed,
                    "environment": {
                        "base_success_probability": ENVIRONMENT.base_success_probability,
                        "practice_gain": ENVIRONMENT.practice_gain,
                        "maximum_role_success": ENVIRONMENT.maximum_role_success,
                    },
                    "episodes": episodes,
                    "relationship_state": relationships.snapshot(),
                }
            )
            if observer is not None:
                evidence.extend(asdict(claim) for claim in observer.evidence())

    trace = {
        "schema": "o0-world-trace-v0.1",
        "units": units,
    }
    return trace, evidence


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("baseline", "observatory"), required=True)
    parser.add_argument("--trace-output", type=Path, required=True)
    parser.add_argument("--evidence-output", type=Path)
    args = parser.parse_args()

    if args.mode == "observatory" and args.evidence_output is None:
        parser.error("--evidence-output is required for observatory mode")
    if args.mode == "baseline" and args.evidence_output is not None:
        parser.error("--evidence-output is not valid for baseline mode")

    trace, evidence = run(args.mode)
    args.trace_output.parent.mkdir(parents=True, exist_ok=True)
    args.trace_output.write_bytes(_canonical_bytes(trace))
    if args.evidence_output is not None:
        args.evidence_output.parent.mkdir(parents=True, exist_ok=True)
        args.evidence_output.write_bytes(
            _canonical_bytes(
                {
                    "schema": "o0-contextgraph-evidence-v0.1",
                    "claims": evidence,
                }
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
