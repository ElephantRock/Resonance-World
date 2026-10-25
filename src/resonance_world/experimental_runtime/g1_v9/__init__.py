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

from ..replay import replay_branch
from .acceptance import (
    ArmReport,
    G1V9AcceptanceReport,
    run_g1_v9_acceptance,
)
from .arms import ARMS, build_policy
from .call_contract import (
    MODEL,
    PROVIDER,
    arm_call_contracts,
    budget_summary,
)
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
from .freeze import (
    FROZEN_UNAUTHORIZED_STATUS,
    MANIFEST_STATUS,
    FreezeManifest,
    build_freeze_manifest,
    governance_entry,
    manifest_digest,
    validate_governance_entry,
    verify_freeze_anchor,
    verify_pinned_files,
)
from .memory import (
    MEMORY_SNAPSHOT_KIND,
    MEMORY_STATE_KIND,
    canonical_memory,
    latest_memory_state,
    record_memory_event,
    verify_memory_attestation,
)
from .power import (
    PlanningAssumptions,
    intra_world_correlation_table,
    minimum_detectable_delta,
    power,
    sensitivity_table,
)
from .qualification import (
    PROPOSED_QUALIFICATION_SEND_CAP,
    DryRunTransport,
    PhysicalSendCapExceeded,
    QualificationPlan,
    SendMeter,
    build_authorization_candidate,
    build_qualification_plan,
    preflight_failure_classes,
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
    "FROZEN_UNAUTHORIZED_STATUS",
    "FreezeManifest",
    "MANIFEST_STATUS",
    "MEMORY_SNAPSHOT_KIND",
    "MEMORY_STATE_KIND",
    "MODEL",
    "PROVIDER",
    "PlanningAssumptions",
    "PROPOSED_QUALIFICATION_SEND_CAP",
    "PhysicalSendCapExceeded",
    "QualificationPlan",
    "RULES_VERSION",
    "SCENARIO_ID",
    "ArmReport",
    "DryRunTransport",
    "G1V9AcceptanceReport",
    "G1V9Contract",
    "SendMeter",
    "arm_call_contracts",
    "budget_summary",
    "build_authorization_candidate",
    "build_freeze_manifest",
    "build_machine",
    "build_policy",
    "build_qualification_plan",
    "canonical_memory",
    "context_schedule",
    "default_contract",
    "derive_epoch_table",
    "derive_evaluator_seed",
    "governance_entry",
    "intra_world_correlation_table",
    "latest_memory_state",
    "manifest_digest",
    "minimum_detectable_delta",
    "power",
    "preflight_failure_classes",
    "present_context",
    "record_memory_event",
    "replay_branch",
    "run_g1_v9_acceptance",
    "sensitivity_table",
    "seal_epoch",
    "start_arm",
    "validate_governance_entry",
    "verify_freeze_anchor",
    "verify_memory_attestation",
    "verify_pinned_files",
]
