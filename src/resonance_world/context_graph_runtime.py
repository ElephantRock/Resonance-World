"""Resonance World facade for the standalone ContextGraph runtime.

Production/runtime consumers should import ContextGraph integration through this module.
The dependency direction is intentionally one-way::

    Resonance World -> resonance_contextgraph
    resonance_contextgraph -X-> Resonance World

The v0.1.0 World adoption is **observer-only**. It provides an Observatory/evaluator
substrate and does not authorize agents or organizations to consume accumulated history.
Historical-substrate access requires a separate preregistered intervention.

Install the optional ``contextgraph`` extra to activate this facade.
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
STANDALONE_RELEASE_WORKFLOW_RUN = 31641381598
RELEASE_PARITY_RUN = 31641586497
INTEGRATION_MODE = "observer-only"
HISTORICAL_SUBSTRATE_ENABLED = False
LEGACY_WORLD_MODULE_STATUS = "research-branch-scientific-compatibility-fixture"

__all__ = [
    "HISTORICAL_SUBSTRATE_ENABLED",
    "INTEGRATION_MODE",
    "LEGACY_WORLD_MODULE_STATUS",
    "RELEASE_PARITY_RUN",
    "STANDALONE_RELEASE",
    "STANDALONE_RELEASE_COMMIT",
    "STANDALONE_RELEASE_WORKFLOW_RUN",
    "STANDALONE_REPOSITORY",
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
