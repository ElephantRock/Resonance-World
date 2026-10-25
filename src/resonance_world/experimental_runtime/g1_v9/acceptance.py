"""Model-free acceptance runner for the G1 v9 integration gate.

Executes the four arms on the approved World Kernel with offline
policies, verifies the structural guarantees of the scenario contract
(shared schedule, exclusive ablation, no rule leakage, replay identity,
determinism), and reports per-arm measurements from public counters.

This runner establishes apparatus only. It makes no scientific claim
about model learning or adaptation, and it performs no provider calls.
"""

from __future__ import annotations

import json
import secrets
from collections.abc import Mapping
from dataclasses import dataclass

from ..kernel import WorldKernel
from ..replay import replay_branch
from ..store import KernelStore
from .arms import ARMS, build_policy
from .contract import G1V9Contract, default_contract
from .scenario import (
    build_machine,
    seal_initial_rule,
    seal_switch_rule,
    start_arm,
)

#: Event kinds that must be byte-identical across all four arms.
SHARED_EVENT_KINDS = frozenset({"tick", "world_pulse", "rule_epoch", "epoch_boundary"})


@dataclass(frozen=True, slots=True)
class ArmReport:
    """Structural and measurement outcome for one experimental arm."""

    branch_id: str
    arm_kind: str
    decisions: int
    pre_attempts: int
    pre_accuracy: float
    post_attempts: int
    post_accuracy: float
    adaptation_delta: float
    ablation_recorded: bool
    capture_state_sha256: str
    replay_state_sha256: str
    replay_checkpoints_matched: int
    port_calls: int

    @property
    def replay_matched(self) -> bool:
        return self.capture_state_sha256 == self.replay_state_sha256


@dataclass(frozen=True, slots=True)
class G1V9AcceptanceReport:
    """Machine-checkable summary of one integration-gate run."""

    contract_digest: str
    rules_version: str
    ticks: int
    arm_reports: tuple[ArmReport, ...]
    shared_schedule_identical: bool
    leak_scan_clean: bool
    ablation_exclusive_to_b: bool
    all_replays_matched: bool
    port_calls_total: int


def _accuracy(successes: int, attempts: int) -> float:
    if attempts == 0:
        return 0.0
    return successes / attempts


def _run_arm(
    kernel: WorldKernel,
    contract: G1V9Contract,
    policy,
) -> None:
    seal_initial_rule(kernel)
    for current in range(contract.total_ticks):
        if current == contract.rule_switch_tick:
            seal_switch_rule(kernel)
            if kernel.branch_id == contract.ablated_branch:
                kernel.emit(
                    "memory_ablation",
                    {
                        "arm": contract.ablated_branch,
                        "cleared": "agent_experience_memory",
                    },
                )
                policy.ablate()
        kernel.schedule("world_pulse", {"tick": current})
        if current % contract.decision_cadence == 0:
            kernel.decide_via(policy)
        kernel.advance()
        if kernel.tick in contract.checkpoint_ticks:
            kernel.checkpoint(f"cp-{kernel.tick}")


def _shared_schedule(kernel: WorldKernel) -> tuple[tuple[str, int, str], ...]:
    """Return the content identity of the shared event schedule.

    Comparison uses the payload commitment, not the event digest: the
    causal chains differ across arms by construction (different decision
    streams), while the shared schedule content must not.
    """

    return tuple(
        (event.kind, event.tick, event.payload_sha256)
        for event in kernel.events()
        if event.kind in SHARED_EVENT_KINDS
    )


def _public_leak_scan(kernel: WorldKernel) -> bool:
    """Return True when no public path exposes sealed rule content."""

    for event in kernel.events():
        if event.visibility != "public":
            continue
        if event.kind == "rule_epoch":
            return False
        if event.kind == "agent_decision":
            continue  # chosen orderings are the lawful public channel
        payload_text = json.dumps(
            _plain(event.payload), sort_keys=True, default=str
        )
        if '"ordering"' in payload_text:
            return False
    if "current_ordering" in kernel.state.public:
        return False
    return True


def _plain(value):
    """Convert read-only payload views into JSON-serializable structures."""

    if isinstance(value, Mapping):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    return value


def run_g1_v9_acceptance(
    *,
    contract: G1V9Contract | None = None,
    commitment_key: bytes | None = None,
) -> G1V9AcceptanceReport:
    """Execute the full G1 v9 integration gate and return its report."""

    contract = contract or default_contract()
    key = commitment_key if commitment_key is not None else secrets.token_bytes(32)
    store = KernelStore(commitment_key=key)
    machine = build_machine(contract)

    trunk = start_arm(store, contract, "trunk")
    kernels: dict[str, WorldKernel] = {}
    policies = {}
    for branch_id, arm_kind in zip(contract.arm_branches, ARMS, strict=True):
        child = trunk.fork(branch_id)
        policy = build_policy(arm_kind, contract_freeze_tick=contract.freeze_tick)
        kernels[branch_id] = child
        policies[branch_id] = (arm_kind, policy)

    arm_reports: list[ArmReport] = []
    for branch_id, arm_kind in zip(contract.arm_branches, ARMS, strict=True):
        kernel = kernels[branch_id]
        policy = policies[branch_id][1]
        _run_arm(kernel, contract, policy)

        public = kernel.state.public
        pre_attempts = int(public["attempts_pre"])
        post_attempts = int(public["attempts_post"])
        pre_accuracy = _accuracy(int(public["successes_pre"]), pre_attempts)
        post_accuracy = _accuracy(int(public["successes_post"]), post_attempts)
        capture_hash = kernel.state_hash()

        replay = replay_branch(store, branch_id, machine)
        arm_reports.append(
            ArmReport(
                branch_id=branch_id,
                arm_kind=arm_kind,
                decisions=int(public["decisions"]),
                pre_attempts=pre_attempts,
                pre_accuracy=round(pre_accuracy, 6),
                post_attempts=post_attempts,
                post_accuracy=round(post_accuracy, 6),
                adaptation_delta=round(post_accuracy - pre_accuracy, 6),
                ablation_recorded=int(public["ablation_at"]) != -1,
                capture_state_sha256=capture_hash,
                replay_state_sha256=replay.final_state_sha256,
                replay_checkpoints_matched=sum(
                    1 for item in replay.checkpoint_verifications if item.matched
                ),
                port_calls=policy.calls,
            )
        )

    schedules = [_shared_schedule(kernels[branch]) for branch in contract.arm_branches]
    shared_identical = all(schedule == schedules[0] for schedule in schedules[1:])

    leak_clean = all(
        _public_leak_scan(kernels[branch]) for branch in contract.arm_branches
    )

    ablation_flags = [report.ablation_recorded for report in arm_reports]
    ablation_exclusive = ablation_flags == [
        branch == contract.ablated_branch for branch in contract.arm_branches
    ]

    all_replays = all(report.replay_matched for report in arm_reports)

    return G1V9AcceptanceReport(
        contract_digest=contract.digest(),
        rules_version=contract.rules_version,
        ticks=kernels[contract.arm_branches[0]].tick,
        arm_reports=tuple(arm_reports),
        shared_schedule_identical=shared_identical,
        leak_scan_clean=leak_clean,
        ablation_exclusive_to_b=ablation_exclusive,
        all_replays_matched=all_replays,
        port_calls_total=sum(report.port_calls for report in arm_reports),
    )
