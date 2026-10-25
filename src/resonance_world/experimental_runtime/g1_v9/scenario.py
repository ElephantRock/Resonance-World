"""G1 v9 world definition: hidden rule epochs, decisions, ablation.

World mechanics follow the scenario contract (`docs/g1-v9-scenario-contract.md`):

- the hidden rule of an epoch (which ordering the environment rewards) enters
  the world only as a sealed private `rule_epoch` event; the reducer stores it
  in the private compartment and it never appears in any public path;
- each `agent_decision` records the chosen ordering publicly; the reducer
  evaluates it against the current hidden ordering and publishes only the
  outcome counters (the agent's lawful feedback channel);
- `memory_ablation` is the explicit experimental transaction that marks the
  treatment of arm B; shared history, evaluator rules, and hidden targets are
  identical across arms.

No model, SDK, or credential exists on this code path.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping
from typing import Any

from ..events import WorldEvent
from ..kernel import WorldKernel
from ..machine import StateMachine
from ..state import WorldState
from ..store import KernelStore
from .contract import G1V9Contract

#: Hidden rule of epoch 0 (P0). Sealed; never exposed through public paths.
P0_ORDERING = "AB"
#: Hidden rule of epoch 1 (P1). Sealed; never exposed through public paths.
P1_ORDERING = "BA"

_VALID_ORDERINGS = ("AB", "BA")


def build_machine(contract: G1V9Contract) -> StateMachine:
    """Build the G1 v9 reducer registry bound to the contract's rules."""

    machine = StateMachine(**contract.with_fingerprint_kwargs())
    machine.register("tick", _reduce_tick)
    machine.register("world_pulse", _reduce_world_pulse)
    machine.register("observation", _reduce_noop)
    machine.register("rule_epoch", _reduce_rule_epoch)
    machine.register("agent_decision", _reduce_agent_decision)
    machine.register("memory_ablation", _reduce_memory_ablation)
    machine.register("branch_fork", _reduce_branch_fork)
    return machine


def _reduce_noop(state: WorldState, event: WorldEvent, sealed: Any) -> WorldState:
    return state


def _reduce_tick(state: WorldState, event: WorldEvent, sealed: Any) -> WorldState:
    return state


def _reduce_branch_fork(state: WorldState, event: WorldEvent, sealed: Any) -> WorldState:
    payload = event.payload or {}
    public = dict(state.public)
    public["forked_from"] = str(payload.get("parent_branch_id", ""))
    return dataclasses.replace(state, public=public)


def _reduce_world_pulse(state: WorldState, event: WorldEvent, sealed: Any) -> WorldState:
    public = dict(state.public)
    public["world_pulses"] = int(public.get("world_pulses", 0)) + 1
    return dataclasses.replace(state, public=public)


def _reduce_rule_epoch(state: WorldState, event: WorldEvent, sealed: Any) -> WorldState:
    """Apply a sealed rule epoch: store the hidden ordering privately."""

    if not isinstance(sealed, Mapping):
        raise ValueError("rule_epoch requires its sealed payload")
    ordering = sealed.get("ordering")
    epoch = sealed.get("epoch")
    if ordering not in _VALID_ORDERINGS:
        raise ValueError("sealed rule epoch carries an unknown ordering")
    if isinstance(epoch, bool) or not isinstance(epoch, int):
        raise ValueError("sealed rule epoch carries a malformed epoch")
    private = dict(state.private)
    private["current_ordering"] = ordering
    private["current_epoch"] = epoch
    private["rule_epochs_sealed"] = int(private.get("rule_epochs_sealed", 0)) + 1
    return dataclasses.replace(state, private=private)


def _reduce_agent_decision(state: WorldState, event: WorldEvent, sealed: Any) -> WorldState:
    """Evaluate one chosen ordering against the hidden rule; publish counters."""

    payload = event.payload or {}
    decision = payload.get("decision")
    if not isinstance(decision, Mapping) or "ordering" not in decision:
        raise ValueError("agent decision payload is malformed")
    chosen = decision["ordering"]
    if chosen not in _VALID_ORDERINGS:
        raise ValueError(f"unknown chosen ordering {chosen!r}")

    hidden = state.private.get("current_ordering", "")
    if hidden not in _VALID_ORDERINGS:
        raise ValueError("decision evaluated before any rule epoch was sealed")

    switch_tick = int(state.public["rule_switch_tick"])
    success = chosen == hidden
    epoch_index = 0 if event.tick < switch_tick else 1
    prefix = "pre" if epoch_index == 0 else "post"

    public = dict(state.public)
    public[f"attempts_{prefix}"] = int(public.get(f"attempts_{prefix}", 0)) + 1
    if success:
        public[f"successes_{prefix}"] = int(public.get(f"successes_{prefix}", 0)) + 1
    public["attempts"] = int(public.get("attempts", 0)) + 1
    public["successes"] = int(public.get("successes", 0)) + (1 if success else 0)
    public["decisions"] = int(public.get("decisions", 0)) + 1

    private = dict(state.private)
    private["decisions"] = int(private.get("decisions", 0)) + 1
    return dataclasses.replace(state, public=public, private=private)


def _reduce_memory_ablation(state: WorldState, event: WorldEvent, sealed: Any) -> WorldState:
    """Record the explicit ablation transaction of arm B."""

    if state.public.get("ablation_at", -1) != -1:
        raise ValueError("memory ablation must be recorded at most once")
    public = dict(state.public)
    public["ablation_at"] = event.tick
    return dataclasses.replace(state, public=public)


def start_arm(
    store: KernelStore,
    contract: G1V9Contract,
    branch_id: str,
) -> WorldKernel:
    """Create one genesis branch of the G1 v9 scenario for an arm."""

    return WorldKernel.create(
        contract.scenario_id,
        build_machine(contract),
        store=store,
        branch_id=branch_id,
        initial_public={
            "rule_switch_tick": contract.rule_switch_tick,
            "attempts_pre": 0,
            "successes_pre": 0,
            "attempts_post": 0,
            "successes_post": 0,
            "attempts": 0,
            "successes": 0,
            "decisions": 0,
            "epochs": 0,
            "world_pulses": 0,
            "ablation_at": -1,
        },
        initial_private={
            "current_ordering": "",
            "current_epoch": -1,
            "rule_epochs_sealed": 0,
            "decisions": 0,
        },
    )


def seal_initial_rule(kernel: WorldKernel) -> None:
    """Seal the epoch-0 hidden rule (P0) at the genesis tick."""

    kernel.emit(
        "rule_epoch",
        {"epoch": 0, "ordering": P0_ORDERING},
        source="external",
        visibility="private",
    )


def seal_switch_rule(kernel: WorldKernel) -> None:
    """Seal the epoch-1 hidden rule (P1) at the switch tick."""

    kernel.emit(
        "rule_epoch",
        {"epoch": 1, "ordering": P1_ORDERING},
        source="external",
        visibility="private",
    )
