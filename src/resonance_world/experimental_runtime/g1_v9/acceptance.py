"""Model-free acceptance runner for the G1 v9 integration gate.

Topology (per the hardened design):

- ``acquisition``: one shared acquisition path, ticks 0..499, one adaptive
  learner. Ticks 0..399 are the common pre-freeze history; at tick 400 the
  memory custody chain records a ``save`` snapshot. At tick 500 the
  evaluator seals the epoch-1 table (balanced switch) and records the
  second ``save``; this head is the paired fork point.
- ``arm-a`` / ``arm-b``: forked from that head. A continues with the live
  memory; B records ``memory_ablation`` plus an ``ablated`` memory
  snapshot and continues from cleared memory. Paired measurement to tick
  1000.
- ``arm-c``: forked at tick 400 with the sealed snapshot; never learns.
- ``arm-d``: forked at tick 0; a full 1,000-tick canonical baseline with
  identical sealed rules.

Everything is offline: policies are deterministic stand-ins, replay
performs zero policy calls, and no provider call exists on any path.
"""

from __future__ import annotations

import json
import secrets
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from ..kernel import WorldKernel
from ..replay import replay_branch
from ..store import KernelStore
from .arms import ContextMemoryPolicy, build_policy
from .contract import (
    ACQUISITION_BRANCH,
    ARM_A_BRANCH,
    ARM_B_BRANCH,
    ARM_C_BRANCH,
    ARM_D_BRANCH,
    G1V9Contract,
    default_contract,
)
from .evaluator import context_schedule, derive_evaluator_seed
from .memory import (
    canonical_memory,
    latest_memory_state,
    record_memory_event,
)
from .scenario import build_machine, present_context, seal_epoch, start_arm

SHARED_EVENT_KINDS = frozenset(
    {
        "tick",
        "world_pulse",
        "rule_epoch",
        "context_presented",
        "epoch_boundary",
    }
)


@dataclass(frozen=True, slots=True)
class ArmReport:
    """Structural and measurement outcome for one experimental arm."""

    branch_id: str
    arm_kind: str
    ticks: int
    decisions: int
    pre_attempts: int
    pre_accuracy: float
    post_attempts: int
    post_accuracy: float
    adaptation_delta: float
    ablation_recorded: bool
    forked_from: str
    capture_state_sha256: str
    replay_state_sha256: str
    replay_checkpoints_matched: int
    port_calls: int
    inherited_port_calls: int

    @property
    def replay_matched(self) -> bool:
        return self.capture_state_sha256 == self.replay_state_sha256


@dataclass(frozen=True, slots=True)
class G1V9AcceptanceReport:
    """Machine-checkable summary of one integration-gate run."""

    contract_digest: str
    rules_version: str
    arm_reports: tuple[ArmReport, ...]
    pre_treatment_identity_verified: bool
    post_treatment_shared_schedule_identical: bool
    ablation_exclusive_to_b: bool
    ablation_custody_verified: bool
    leak_scan_clean: bool
    all_replays_matched: bool
    port_calls_total: int


def _accuracy(successes: int, attempts: int) -> float:
    return successes / attempts if attempts else 0.0


def _plain(value):
    if isinstance(value, Mapping):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    return value


def _shared_schedule(kernel: WorldKernel) -> tuple[tuple[str, int, str], ...]:
    """Content identity of the shared event kinds (payload commitments)."""

    return tuple(
        (event.kind, event.tick, event.payload_sha256)
        for event in kernel.events()
        if event.kind in SHARED_EVENT_KINDS
    )


def _leak_scan(kernel: WorldKernel) -> bool:
    for event in kernel.events():
        if event.visibility != "public":
            continue
        if event.kind == "rule_epoch":
            return False
        if event.kind == "agent_decision":
            continue
        payload_text = json.dumps(_plain(event.payload), sort_keys=True, default=str)
        if '"table"' in payload_text or '"hidden_table"' in payload_text:
            return False
    if "hidden_table" in kernel.state.public:
        return False
    return True


def _drive_decision_tick(kernel: WorldKernel, policy, context: str) -> None:
    present_context(kernel, context)
    kernel.decide_via(policy)


def _run_path(
    kernel: WorldKernel,
    policy,
    *,
    contexts: list[str],
    contract: G1V9Contract,
    seal_switch: bool,
    seed: bytes,
    table0: dict[str, str],
    memory_custody: bool = False,
) -> None:
    """Advance one branch from its head through the measurement tail.

    When ``memory_custody`` is set (the paired arms), the policy's memory
    is attested into the world at every restore point, so an interrupted
    run can be resumed from the log with the exact recorded memory.
    """

    for current in range(kernel.tick, contract.acquisition_ticks + contract.measurement_ticks):
        if seal_switch and current == contract.acquisition_ticks:
            seal_epoch(
                kernel,
                epoch=1,
                seed=seed,
                contract=contract,
                previous_table=table0,
            )
        decision_index = current // contract.decision_cadence
        context = contexts[decision_index] if decision_index < len(contexts) else contexts[-1]
        if current % contract.decision_cadence == 0:
            _drive_decision_tick(kernel, policy, context=context)
        kernel.schedule("world_pulse", {"tick": current})
        kernel.advance()
        checkpoint = kernel.tick in contract.measurement_checkpoints or (
            branch_checkpoint(kernel.tick, contract)
        )
        if checkpoint:
            if memory_custody:
                # Attest the memory BEFORE the checkpoint so the snapshot
                # watermark covers the attested state exactly.
                record_memory_event(
                    kernel=kernel,
                    tick=kernel.tick,
                    kind="save",
                    memory=canonical_memory(policy.snapshot()),
                    memory_id=f"memory@{kernel.tick}",
                )
            kernel.checkpoint(f"cp-{kernel.tick}")


def branch_checkpoint(tick: int, contract: G1V9Contract) -> bool:
    return tick in contract.acquisition_checkpoints


def _memory_state_at_tick(
    store: KernelStore, branch_id: str, tick: int
) -> dict[str, Any] | None:
    """Return the sealed memory content of the last save at or before tick."""

    latest: dict[str, Any] | None = None
    for event in store.iter_events(branch_id):
        if event.kind != "memory_snapshot" or event.payload is None:
            continue
        if event.payload.get("kind") != "save" or event.tick > tick:
            continue
        sealed_seq = event.seq - 1
        latest = store.sealed_payload(branch_id, sealed_seq)
    return latest


def run_g1_v9_acceptance(
    *,
    contract: G1V9Contract | None = None,
    commitment_key: bytes | None = None,
    evaluator_seed_material: bytes | None = None,
) -> G1V9AcceptanceReport:
    """Execute the full G1 v9 integration gate and return its report."""

    contract = contract or default_contract()
    key = commitment_key if commitment_key is not None else secrets.token_bytes(32)
    seed = derive_evaluator_seed(
        evaluator_seed_material if evaluator_seed_material is not None else key
    )
    store = KernelStore(commitment_key=key)
    machine = build_machine(contract)
    contexts = context_schedule(
        seed,
        contract.acquisition_ticks + contract.measurement_ticks,
        contract.context_count,
        contract.decision_cadence,
    )

    # -- shared acquisition path (ticks 0..499) ---------------------------
    acquisition = start_arm(store, contract, ACQUISITION_BRANCH)
    learner = ContextMemoryPolicy()
    table0 = seal_epoch(acquisition, epoch=0, seed=seed, contract=contract)

    arm_c: WorldKernel | None = None
    policy_c = None
    learner_calls_at_freeze = 0
    for current in range(contract.acquisition_ticks):
        if current == contract.freeze_tick:
            learner_calls_at_freeze = learner.calls
            record_memory_event(
                kernel=acquisition,
                tick=current,
                kind="save",
                memory=canonical_memory(learner.snapshot()),
                memory_id=f"freeze-snapshot@{current}",
            )
            arm_c = acquisition.fork(ARM_C_BRANCH)
            policy_c = build_policy(
                "frozen",
                contract=contract,
                sealed_memory=_memory_state_at_tick(
                    store, ACQUISITION_BRANCH, contract.freeze_tick
                ),
            )
        decision_index = current // contract.decision_cadence
        context = contexts[decision_index] if decision_index < len(contexts) else contexts[-1]
        if current % contract.decision_cadence == 0:
            _drive_decision_tick(acquisition, learner, context=context)
        acquisition.schedule("world_pulse", {"tick": current})
        acquisition.advance()
        if acquisition.tick in contract.acquisition_checkpoints:
            acquisition.checkpoint(f"cp-{acquisition.tick}")

    # Treatment-point memory save, then the balanced rule switch.
    record_memory_event(
        kernel=acquisition,
        tick=acquisition.tick,
        kind="save",
        memory=canonical_memory(learner.snapshot()),
        memory_id=f"treatment-snapshot@{acquisition.tick}",
    )
    seal_epoch(
        acquisition,
        epoch=1,
        seed=seed,
        contract=contract,
        previous_table=table0,
    )

    # -- paired fork: A keeps memory, B records ablation -------------------
    # Branch isolation means children never inherit events, so the sealed
    # memory content is read from the acquisition ledger and passed
    # explicitly to the forked policies.
    live_memory = latest_memory_state(store, ACQUISITION_BRANCH)
    arm_a = acquisition.fork(ARM_A_BRANCH)
    policy_a = ContextMemoryPolicy()
    policy_a.restore(live_memory)

    arm_b = acquisition.fork(ARM_B_BRANCH)
    policy_b = ContextMemoryPolicy()
    policy_b.restore(live_memory)

    arm_b.emit(
        "memory_ablation",
        {"arm": ARM_B_BRANCH, "cleared": "agent_experience_memory"},
    )
    policy_b.ablate()
    record_memory_event(
        kernel=arm_b,
        tick=arm_b.tick,
        kind="ablated",
        memory=canonical_memory(policy_b.snapshot()),
        memory_id=f"ablation@{arm_b.tick}",
    )

    # -- arm D: independent canonical baseline over the full timeline ------
    arm_d = start_arm(store, contract, ARM_D_BRANCH)
    seal_epoch(arm_d, epoch=0, seed=seed, contract=contract)
    policy_d = build_policy("canonical", contract=contract)

    # -- run the measurement tails -----------------------------------------
    _run_path(
        arm_a,
        policy_a,
        contexts=contexts,
        contract=contract,
        seal_switch=False,
        seed=seed,
        table0=table0,
        memory_custody=True,
    )
    _run_path(
        arm_b,
        policy_b,
        contexts=contexts,
        contract=contract,
        seal_switch=False,
        seed=seed,
        table0=table0,
        memory_custody=True,
    )
    _run_path(
        arm_c,
        policy_c,
        contexts=contexts,
        contract=contract,
        seal_switch=True,
        seed=seed,
        table0=table0,
    )
    _run_path(
        arm_d,
        policy_d,
        contexts=contexts,
        contract=contract,
        seal_switch=True,
        seed=seed,
        table0=table0,
    )

    # -- reports and structural verification -------------------------------
    kernel_map = {
        ARM_A_BRANCH: (arm_a, policy_a, "adaptive"),
        ARM_B_BRANCH: (arm_b, policy_b, "memory-ablated"),
        ARM_C_BRANCH: (arm_c, policy_c, "frozen"),
        ARM_D_BRANCH: (arm_d, policy_d, "canonical"),
    }

    arm_reports: list[ArmReport] = []
    for branch_id in contract.arm_branches:
        kernel, policy, arm_kind = kernel_map[branch_id]
        public = kernel.state.public
        pre_attempts = int(public["attempts_pre"])
        post_attempts = int(public["attempts_post"])
        capture_hash = kernel.state_hash()
        replay = replay_branch(store, branch_id, machine)
        arm_reports.append(
            ArmReport(
                branch_id=branch_id,
                arm_kind=arm_kind,
                ticks=kernel.tick,
                decisions=int(public["decisions"]),
                pre_attempts=pre_attempts,
                pre_accuracy=round(
                    _accuracy(int(public["successes_pre"]), pre_attempts), 6
                ),
                post_attempts=post_attempts,
                post_accuracy=round(
                    _accuracy(int(public["successes_post"]), post_attempts), 6
                ),
                adaptation_delta=round(
                    _accuracy(int(public["successes_post"]), post_attempts)
                    - _accuracy(int(public["successes_pre"]), pre_attempts),
                    6,
                ),
                ablation_recorded=int(public["ablation_at"]) != -1,
                forked_from=str(public.get("forked_from", "")),
                capture_state_sha256=capture_hash,
                replay_state_sha256=replay.final_state_sha256,
                replay_checkpoints_matched=sum(
                    1 for item in replay.checkpoint_verifications if item.matched
                ),
                port_calls=policy.calls,
                inherited_port_calls=(
                    learner.calls
                    if branch_id in (ARM_A_BRANCH, ARM_B_BRANCH)
                    else (learner_calls_at_freeze if branch_id == ARM_C_BRANCH else 0)
                ),
            )
        )

    # Pre-treatment identity: A and B fork from one recorded head.
    head_a = store.get_branch(ARM_A_BRANCH)
    head_b = store.get_branch(ARM_B_BRANCH)
    pre_treatment_identity = (
        head_a.parent_branch_id == ACQUISITION_BRANCH
        and head_b.parent_branch_id == ACQUISITION_BRANCH
        and head_a.fork_event_count == head_b.fork_event_count
        and head_a.parent_state_sha256 == head_b.parent_state_sha256
        and head_a.fork_tick == contract.acquisition_ticks
    )

    schedule_a = _shared_schedule(arm_a)
    shared_identical = schedule_a == _shared_schedule(arm_b)

    leak_clean = all(_leak_scan(kernel_map[branch][0]) for branch in kernel_map)

    ablation_flags = {
        report.branch_id: report.ablation_recorded for report in arm_reports
    }
    ablation_exclusive = ablation_flags == {
        branch: branch == ARM_B_BRANCH for branch in kernel_map
    }
    all_replays = all(report.replay_matched for report in arm_reports)

    return G1V9AcceptanceReport(
        contract_digest=contract.digest(),
        rules_version=contract.rules_version,
        arm_reports=tuple(arm_reports),
        pre_treatment_identity_verified=pre_treatment_identity,
        post_treatment_shared_schedule_identical=shared_identical,
        ablation_exclusive_to_b=ablation_exclusive,
        ablation_custody_verified=_ablation_custody(store, contract),
        leak_scan_clean=leak_clean,
        all_replays_matched=all_replays,
        port_calls_total=sum(report.port_calls for report in arm_reports),
    )


def _ablation_custody(store: KernelStore, contract: G1V9Contract) -> bool:
    """Verify the ablation attestation chain from the world alone.

    The check targets the snapshot co-recorded with the ablation
    transaction (not later saves: the arm legitimately keeps acting and
    attesting further memory states after the treatment).
    """

    events = store.iter_events(ARM_B_BRANCH)
    if sum(1 for event in events if event.kind == "memory_ablation") != 1:
        return False
    ablated_snapshots = [
        event
        for event in events
        if event.kind == "memory_snapshot"
        and event.payload is not None
        and event.payload.get("kind") == "ablated"
    ]
    if len(ablated_snapshots) != 1:
        return False
    attestation = ablated_snapshots[0]
    sealed_seq = attestation.seq - 1
    sealed_event = next((event for event in events if event.seq == sealed_seq), None)
    if sealed_event is None or sealed_event.kind != "memory_state":
        return False
    try:
        memory = store.sealed_payload(ARM_B_BRANCH, sealed_seq)
    except ValueError:
        return False
    cleared = canonical_memory(memory)
    if cleared.get("chosen") or cleared.get("outcomes") or cleared.get("successes"):
        return False
    return store.commit_payload(cleared) == attestation.payload["memory_commitment"]
