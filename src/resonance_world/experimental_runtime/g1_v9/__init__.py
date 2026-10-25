"""G1 v9 integration: scenario contract, four arms, model-free acceptance.

This package binds the approved World Kernel to the G1 v9 world-time
adaptation scenario. The integration gate runs entirely offline: all
decision ports are deterministic scripted stand-ins and no provider
call exists on any code path. Scientific claims require the separately
frozen protocol and budget (see docs/g1-v9-scenario-contract.md).
"""

from __future__ import annotations

from .acceptance import (
    ArmReport,
    G1V9AcceptanceReport,
    run_g1_v9_acceptance,
)
from .arms import ARMS, build_policy
from .contract import (
    CONTRACT_SCHEMA,
    SCENARIO_ID,
    G1V9Contract,
    default_contract,
)
from .scenario import (
    P0_ORDERING,
    P1_ORDERING,
    build_machine,
    seal_initial_rule,
    seal_switch_rule,
    start_arm,
)

__all__ = [
    "ARMS",
    "CONTRACT_SCHEMA",
    "P0_ORDERING",
    "P1_ORDERING",
    "SCENARIO_ID",
    "ArmReport",
    "G1V9AcceptanceReport",
    "G1V9Contract",
    "build_machine",
    "build_policy",
    "default_contract",
    "run_g1_v9_acceptance",
    "seal_initial_rule",
    "seal_switch_rule",
    "start_arm",
]
