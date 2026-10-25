"""G1 v9 integration: scenario contract, four arms, model-free acceptance.

This package binds the approved World Kernel to the G1 v9 world-time
adaptation scenario. The integration gate runs entirely offline: all
decision ports are deterministic scripted stand-ins and no provider
call exists on any code path. Hidden task truth is derived and sealed
exclusively by the evaluator module and never appears as an importable
constant. Scientific claims require the separately frozen protocol and
budget (see docs/g1-v9-freeze-file.md).
"""

from __future__ import annotations

from .acceptance import (
    ArmReport,
    G1V9AcceptanceReport,
    run_g1_v9_acceptance,
)
from .arms import ARMS, build_policy
from .contract import (
    ACQUISITION_BRANCH,
    ARM_A_BRANCH,
    ARM_B_BRANCH,
    ARM_C_BRANCH,
    ARM_D_BRANCH,
    CONTRACT_SCHEMA,
    RULES_VERSION,
    SCENARIO_ID,
    G1V9Contract,
    default_contract,
)
from .evaluator import (
    context_schedule,
    derive_epoch_table,
    derive_evaluator_seed,
)
from .memory import (
    MEMORY_SNAPSHOT_KIND,
    MEMORY_STATE_KIND,
    canonical_memory,
    latest_memory_state,
    record_memory_event,
    verify_memory_attestation,
)
from .scenario import build_machine, present_context, seal_epoch, start_arm

__all__ = [
    "ACQUISITION_BRANCH",
    "ARMS",
    "ARM_A_BRANCH",
    "ARM_B_BRANCH",
    "ARM_C_BRANCH",
    "ARM_D_BRANCH",
    "CONTRACT_SCHEMA",
    "MEMORY_SNAPSHOT_KIND",
    "MEMORY_STATE_KIND",
    "RULES_VERSION",
    "SCENARIO_ID",
    "ArmReport",
    "G1V9AcceptanceReport",
    "G1V9Contract",
    "build_machine",
    "build_policy",
    "canonical_memory",
    "context_schedule",
    "default_contract",
    "derive_epoch_table",
    "derive_evaluator_seed",
    "latest_memory_state",
    "present_context",
    "record_memory_event",
    "replay_branch",
    "run_g1_v9_acceptance",
    "seal_epoch",
    "start_arm",
    "verify_memory_attestation",
]
