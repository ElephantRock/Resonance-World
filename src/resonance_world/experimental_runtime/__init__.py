"""Deterministic, event-driven world kernel for experimental worlds (v0.1).

The package provides causal world time, a deterministic event scheduler
with explicit causal dependencies, append-only event records with
content digests, branch isolation, hash-anchored checkpoints, and exact
offline replay. Model-generated decisions are recorded as external
inputs; replay never invokes a model. Agent-visible observations are
strictly separated from private evaluator state.
"""

from __future__ import annotations

from .anchoring import ANCHOR_SCHEMA, build_log_anchor, log_chain_head, verify_log_anchor
from .checkpoints import Checkpoint
from .events import EVENT_SOURCES, EVENT_VISIBILITIES, WorldEvent
from .kernel import WorldKernel
from .machine import Reducer, StateMachine
from .replay import CheckpointVerification, ReplayResult, replay_branch, replay_state
from .scheduler import EventScheduler, ScheduledEvent
from .state import (
    WorldState,
    full_state_bytes,
    full_state_sha256,
    public_state_bytes,
    public_state_sha256,
)
from .store import SCHEMA_VERSION, BranchRecord, KernelStore
from .views import DecisionRequest, ModelDecisionPort, Observation
from .world_time import WorldClock

WORLD_KERNEL_VERSION = "0.1"

__all__ = [
    "ANCHOR_SCHEMA",
    "EVENT_SOURCES",
    "EVENT_VISIBILITIES",
    "SCHEMA_VERSION",
    "WORLD_KERNEL_VERSION",
    "BranchRecord",
    "Checkpoint",
    "CheckpointVerification",
    "DecisionRequest",
    "EventScheduler",
    "KernelStore",
    "ModelDecisionPort",
    "Observation",
    "Reducer",
    "ReplayResult",
    "ScheduledEvent",
    "StateMachine",
    "WorldClock",
    "WorldEvent",
    "WorldKernel",
    "WorldState",
    "build_log_anchor",
    "full_state_bytes",
    "full_state_sha256",
    "log_chain_head",
    "public_state_bytes",
    "public_state_sha256",
    "replay_branch",
    "replay_state",
    "verify_log_anchor",
]
