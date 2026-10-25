"""Deterministic demonstration scenario and the v0.1 acceptance run.

The scenario is a small resource world driven entirely by kernel
mechanics: a per-tick environment effect derived deterministically from
the scenario identity and world tick, scripted external agent decisions
recorded as external-input events, epoch boundaries, and a private
evaluator assessment whose payload is sealed (the public log commits
only to its digest).

No code in this module contacts a model provider: ``ScriptedPolicy`` is
an offline stand-in that implements the same decision-port contract a
real model integration would use.
"""

from __future__ import annotations

import dataclasses
import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from .events import WorldEvent
from .kernel import WorldKernel
from .machine import StateMachine
from .replay import ReplayResult, replay_branch
from .state import WorldState, full_state_bytes
from .store import KernelStore
from .views import DecisionRequest

SCENARIO_ID = "world-kernel-acceptance-v1"

_ACTION_HARVEST = "harvest"
_ACTION_MAINTAIN = "maintain"
_VALID_ACTIONS = (_ACTION_HARVEST, _ACTION_MAINTAIN)


def _derived(scenario_id: str, label: str) -> int:
    digest = hashlib.sha256(f"{scenario_id}:{label}".encode()).digest()
    return int.from_bytes(digest[:8], "big")


def _reduce_tick(state: WorldState, event: WorldEvent, sealed: Any) -> WorldState:
    return state


def _reduce_observation(state: WorldState, event: WorldEvent, sealed: Any) -> WorldState:
    return state


def _reduce_world_effect(state: WorldState, event: WorldEvent, sealed: Any) -> WorldState:
    value = _derived(state.scenario_id, f"effect:{event.tick}")
    season = value % 4
    growth = 4 + (value // 4) % 9
    public = dict(state.public)
    public["stock"] = int(public.get("stock", 0)) + growth
    public["season"] = season
    public["last_growth"] = growth
    return dataclasses.replace(state, public=public)


def _reduce_agent_decision(state: WorldState, event: WorldEvent, sealed: Any) -> WorldState:
    payload = event.payload or {}
    decision = payload.get("decision")
    if not isinstance(decision, Mapping) or "action" not in decision:
        raise ValueError("agent decision payload is malformed")
    action = decision["action"]
    if action not in _VALID_ACTIONS:
        raise ValueError(f"unknown decision action {action!r}")
    public = dict(state.public)
    stock = int(public.get("stock", 0))
    wear = int(public.get("tools_wear", 0))
    if action == _ACTION_HARVEST:
        # Consumption depends on the decision tick, so the state captures
        # when decisions happened, not only how many were made.
        stock = max(0, stock - (2 + event.tick % 3))
        wear += 1
    else:
        wear = max(0, wear - 2)
    public["stock"] = stock
    public["tools_wear"] = wear
    public["decisions"] = int(public.get("decisions", 0)) + 1
    return dataclasses.replace(state, public=public)


def _reduce_epoch_boundary(state: WorldState, event: WorldEvent, sealed: Any) -> WorldState:
    public = dict(state.public)
    public["epochs"] = int(public.get("epochs", 0)) + 1
    return dataclasses.replace(state, public=public)


def _reduce_assessment(state: WorldState, event: WorldEvent, sealed: Any) -> WorldState:
    if not isinstance(sealed, Mapping) or "stress" not in sealed or "epoch" not in sealed:
        raise ValueError("assessment requires a sealed stress payload")
    stress = sealed["stress"]
    if isinstance(stress, bool) or not isinstance(stress, int) or not 0 <= stress <= 9:
        raise ValueError("assessment stress must be an integer in [0, 9]")
    private = dict(state.private)
    private["stress_total"] = int(private.get("stress_total", 0)) + stress
    private["assessments"] = int(private.get("assessments", 0)) + 1
    public = dict(state.public)
    threshold = int(private.get("hidden_threshold", 6))
    if stress > threshold:
        public["signal"] = int(public.get("signal", 0)) + 1
        private["signals"] = int(private.get("signals", 0)) + 1
    return dataclasses.replace(state, public=public, private=private)


def _reduce_branch_fork(state: WorldState, event: WorldEvent, sealed: Any) -> WorldState:
    payload = event.payload or {}
    public = dict(state.public)
    public["forked_from"] = str(payload.get("parent_branch_id", ""))
    public["fork_parent_event_count"] = int(payload.get("parent_event_count", 0))
    return dataclasses.replace(state, public=public)


def build_machine() -> StateMachine:
    """Build the full reducer registry for the demonstration scenario."""

    machine = StateMachine()
    machine.register("tick", _reduce_tick)
    machine.register("world_effect", _reduce_world_effect)
    machine.register("observation", _reduce_observation)
    machine.register("agent_decision", _reduce_agent_decision)
    machine.register("epoch_boundary", _reduce_epoch_boundary)
    machine.register("assessment", _reduce_assessment)
    machine.register("branch_fork", _reduce_branch_fork)
    return machine


@dataclass
class ScriptedPolicy:
    """A deterministic offline stand-in for a model decision port.

    It reads only the agent-visible observation, counts its own
    invocations, and is the only decision source used in tests, so any
    replay that silently tried to call a model would be unable to do so.
    """

    model_id: str = "scripted-offline-policy-v1"
    wear_limit: int = 8
    calls: int = 0

    def decide(self, request: DecisionRequest) -> dict[str, int | str]:
        self.calls += 1
        wear = int(request.observation.public_state.get("tools_wear", 0))
        action = _ACTION_MAINTAIN if wear >= self.wear_limit else _ACTION_HARVEST
        return {"action": action, "decided_at": request.tick}


def start_kernel(
    store: KernelStore,
    *,
    branch_id: str = "main",
    scenario_id: str = SCENARIO_ID,
) -> WorldKernel:
    """Create a fresh genesis branch of the demonstration scenario."""

    return WorldKernel.create(
        scenario_id,
        build_machine(),
        store=store,
        branch_id=branch_id,
        initial_public={
            "stock": 40,
            "tools_wear": 0,
            "epochs": 0,
            "signal": 0,
            "decisions": 0,
        },
        initial_private={
            "hidden_threshold": 6,
            "stress_total": 0,
            "assessments": 0,
            "signals": 0,
        },
    )


def drive(
    kernel: WorldKernel,
    *,
    ticks: int,
    policy: ScriptedPolicy,
    decision_every: int = 5,
    epoch_every: int = 100,
    checkpoint_ticks: tuple[int, ...] = (),
) -> WorldKernel:
    """Advance ``kernel`` by ``ticks`` ticks with the full event mix."""

    for _ in range(ticks):
        current = kernel.tick
        kernel.schedule("world_effect", {"tick": current})
        if decision_every > 0 and (current + 1) % decision_every == 0:
            kernel.decide_via(policy)
        if epoch_every > 0 and (current + 1) % epoch_every == 0:
            epoch = (current + 1) // epoch_every
            kernel.schedule("epoch_boundary", {"epoch": epoch})
            stress = _derived(kernel.scenario_id, f"stress:{epoch}") % 10
            kernel.schedule(
                "assessment",
                {"epoch": epoch, "stress": stress},
                source="external",
                visibility="private",
            )
        kernel.advance()
        if kernel.tick in checkpoint_ticks:
            kernel.checkpoint(f"cp-{kernel.tick}")
    return kernel


@dataclass(frozen=True, slots=True)
class BranchReplaySummary:
    """Capture-versus-replay outcome for one forked branch."""

    branch_id: str
    event_count: int
    capture_state_sha256: str
    replay_state_sha256: str
    all_checkpoints_matched: bool

    @property
    def matches_capture(self) -> bool:
        return self.capture_state_sha256 == self.replay_state_sha256


@dataclass(frozen=True, slots=True)
class AcceptanceReport:
    """Machine-checkable summary of one acceptance run."""

    scenario_id: str
    main_branch_id: str
    ticks: int
    branch_ids: tuple[str, ...]
    event_count: int
    capture_state_sha256: str
    capture_public_state_sha256: str
    replay_state_sha256: str
    replay_public_state_sha256: str
    replay_checkpoint_matches: int
    replay_recorded_agent_decisions: int
    capture_agent_decisions: int
    branch_summaries: tuple[BranchReplaySummary, ...]
    checkpoint_transparency_verified: bool
    checkpoint_restore_tick: int
    policy_invocations: int


def _verify_checkpoint_transparency(length: int) -> tuple[bool, int]:
    """A checkpointed run must continue exactly like an uninterrupted one.

    Returns ``(verified, restored_tick)`` where ``restored_tick`` is the
    world tick the resumed kernel landed on after restoring the
    checkpoint taken at the split point.
    """

    straight_store = KernelStore()
    straight = start_kernel(straight_store, branch_id="straight")
    straight_policy = ScriptedPolicy()
    drive(straight, ticks=length, policy=straight_policy)
    uninterrupted_state = full_state_bytes(straight.state)

    split_store = KernelStore()
    split = start_kernel(split_store, branch_id="split")
    split_policy = ScriptedPolicy()
    drive(split, ticks=length - 100, policy=split_policy)
    split.checkpoint("mid")
    resumed = WorldKernel.resume(
        store=split_store, branch_id="split", machine=build_machine(), checkpoint_name="mid"
    )
    restored_tick = resumed.tick
    drive(resumed, ticks=100, policy=split_policy)
    # Keyed state commitments differ across stores by design, so equality
    # is asserted over canonical state bytes, not over commitments.
    return full_state_bytes(resumed.state) == uninterrupted_state, restored_tick


def run_acceptance(*, ticks: int = 1000, store_path: str | None = None) -> AcceptanceReport:
    """Execute the full v0.1 acceptance scenario and return its report."""

    if ticks < 200:
        raise ValueError("ticks must be at least 200 for the acceptance shape")
    fork_at = ticks // 2 - 100
    branch_length = ticks // 5
    mid_tick = ticks // 2
    late_tick = 3 * ticks // 4

    store = KernelStore(store_path)
    kernel = start_kernel(store)
    policy = ScriptedPolicy()
    drive(kernel, ticks=fork_at, policy=policy)

    branches = [kernel.fork(f"branch-{index}") for index in range(1, 5)]
    branch_captures: dict[str, str] = {}
    for index, branch in enumerate(branches, start=1):
        branch_policy = ScriptedPolicy(wear_limit=6 + index)
        branch_checkpoint = branch.tick + branch_length
        drive(
            branch,
            ticks=branch_length,
            policy=branch_policy,
            checkpoint_ticks=(branch_checkpoint,),
        )
        branch_captures[branch.branch_id] = branch.state_hash()

    drive(kernel, ticks=ticks - fork_at, policy=policy, checkpoint_ticks=(mid_tick, late_tick))

    machine = build_machine()
    replay_main: ReplayResult = replay_branch(store, kernel.branch_id, machine)
    branch_summaries: list[BranchReplaySummary] = []
    for branch_id in store.list_branches():
        if branch_id == kernel.branch_id:
            continue
        branch_replay = replay_branch(store, branch_id, machine)
        branch_summaries.append(
            BranchReplaySummary(
                branch_id=branch_id,
                event_count=branch_replay.event_count,
                capture_state_sha256=branch_captures[branch_id],
                replay_state_sha256=branch_replay.final_state_sha256,
                all_checkpoints_matched=branch_replay.all_checkpoints_matched,
            )
        )

    checkpoint_transparency_verified, checkpoint_restore_tick = _verify_checkpoint_transparency(
        mid_tick
    )

    return AcceptanceReport(
        scenario_id=kernel.scenario_id,
        main_branch_id=kernel.branch_id,
        ticks=kernel.tick,
        branch_ids=tuple(branch.branch_id for branch in branches),
        event_count=kernel.event_count,
        capture_state_sha256=kernel.state_hash(),
        capture_public_state_sha256=kernel.public_state_hash(),
        replay_state_sha256=replay_main.final_state_sha256,
        replay_public_state_sha256=replay_main.final_public_state_sha256,
        replay_checkpoint_matches=sum(
            1 for item in replay_main.checkpoint_verifications if item.matched
        ),
        replay_recorded_agent_decisions=replay_main.recorded_agent_decisions,
        capture_agent_decisions=policy.calls,
        branch_summaries=tuple(branch_summaries),
        checkpoint_transparency_verified=checkpoint_transparency_verified,
        checkpoint_restore_tick=checkpoint_restore_tick,
        policy_invocations=policy.calls,
    )
