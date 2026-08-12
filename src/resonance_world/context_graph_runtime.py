"""Resonance World facade for the graduated standalone ContextGraph runtime.

Production/runtime consumers should import ContextGraph integration through this module
rather than from the historical ``context_graph_*`` experiment modules. Those legacy
modules remain in Resonance World solely as scientific compatibility fixtures until all
downstream imports have migrated.

The dependency direction is intentionally one-way::

    Resonance World -> resonance_contextgraph
    resonance_contextgraph -X-> Resonance World

Install the optional ``contextgraph`` extra to activate this facade. The extra resolves
through the immutable standalone release tag recorded below.
"""

from __future__ import annotations

from .context_graph_adapter import (
    build_evidence_store,
    checkpoint_from_live_contexts,
    choose_stopping_point,
    compile_live_context,
    next_balanced_cell,
    pair_from_live_context,
    to_evidence_claim,
    to_mission_spec,
    validated_estimator,
)

STANDALONE_REPOSITORY = "ElephantRock/Resonance-ContextGraph"
STANDALONE_RELEASE = "v0.1.0"
STANDALONE_RELEASE_COMMIT = "b896891108fd954869a8cd0423f6e8440ab0cdc0"
STANDALONE_TESTED_COMMIT = "55ce7bb435b3d4a1ff888474a5ca76ccff843150"
STANDALONE_RELEASE_WORKFLOW_RUN = 31641381598
ARCHITECTURAL_PARITY_RUN = 31638854949
LEGACY_WORLD_MODULE_STATUS = "scientific-compatibility-fixture"

__all__ = [
    "ARCHITECTURAL_PARITY_RUN",
    "LEGACY_WORLD_MODULE_STATUS",
    "STANDALONE_RELEASE",
    "STANDALONE_RELEASE_COMMIT",
    "STANDALONE_RELEASE_WORKFLOW_RUN",
    "STANDALONE_REPOSITORY",
    "STANDALONE_TESTED_COMMIT",
    "build_evidence_store",
    "checkpoint_from_live_contexts",
    "choose_stopping_point",
    "compile_live_context",
    "next_balanced_cell",
    "pair_from_live_context",
    "to_evidence_claim",
    "to_mission_spec",
    "validated_estimator",
]
