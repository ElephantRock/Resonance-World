"""G1 v9 world definition: multi-context hidden rules, decisions, ablation.

World mechanics follow the scenario contract and the evaluator's sealed
truth:

- the hidden rule of each rule epoch is a per-context ordering table derived
  by the evaluator and entering the world only as sealed private events; the
  switch at the treatment point flips exactly half of the contexts and keeps
  the other half (no-change controls);
- each `agent_decision` names a context and a chosen ordering; the reducer
  evaluates it against the current hidden table and publishes outcome
  counters only - the lawful feedback channel;
- the presented task context is public (`context_presented` events); only
  the rewarded ordering is hidden;
- `memory_ablation` plus the memory custody chain (`memory.py`) records the
  explicit arm-B treatment; shared history, evaluator rules, and hidden
  targets are identical across arms.

No ordering constant exists in this module or anywhere importable: the
hidden truth lives only in the sealed ledger.
"""

from __future__ import annotations

import dataclasses
import json
from collections.abc import Mapping
from typing import Any

from resonance_world.adapters import canonical_json_bytes

from ..events import WorldEvent
from ..kernel import WorldKernel
from ..machine import StateMachine
from ..state import WorldState
from ..store import KernelStore
from .contract import G1V9Contract
from .evaluator import derive_epoch_table


def build_machine(contract: G1V9Contract) -> StateMachine:
    """Build the G1 v9 reducer registry bound to the contract's rules."""

    machine = StateMachine(**contract.with_fingerprint_kwargs())
    machine.register("tick", _reduce_noop)
    machine.register("world_pulse", _reduce_world_pulse)
    machine.register("context_presented", _reduce_context_presented)
    machine.register("observation", _reduce_noop)
    machine.register("rule_epoch", _reduce_rule_epoch)
    machine.register("agent_decision", _reduce_agent_decision)
    machine.register("memory_ablation", _reduce_memory_ablation)
    machine.register("memory_snapshot", _reduce_noop)
    machine.register("memory_state", _reduce_noop)
    machine.register("branch_fork", _reduce_branch_fork)
    return machine


def _reduce_noop(state: WorldState, event: WorldEvent, sealed: Any) -> WorldState:
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


def _reduce_context_presented(
    state: WorldState, event: WorldEvent, sealed: Any
) -> WorldState:
    payload = event.payload or {}
    context = payload.get("context")
    if not isinstance(context, str) or not context:
        raise ValueError("context_presented requires a context label")
    public = dict(state.public)
    public["current_context"] = context
    public["presented"] = int(public.get("presented", 0)) + 1
    return dataclasses.replace(state, public=public)


def _reduce_rule_epoch(state: WorldState, event: WorldEvent, sealed: Any) -> WorldState:
    """Apply a sealed rule epoch: store the hidden table privately."""

    if not isinstance(sealed, Mapping):
        raise ValueError("rule_epoch requires its sealed payload")
    table = sealed.get("table")
    epoch = sealed.get("epoch")
    if not isinstance(table, Mapping) or not table:
        raise ValueError("sealed rule epoch carries a malformed table")
    if isinstance(epoch, bool) or not isinstance(epoch, int):
        raise ValueError("sealed rule epoch carries a malformed epoch")
    private = dict(state.private)
    private["current_epoch"] = epoch
    # The hidden table is a nested mapping; the state compartment only
    # carries canonical strings, so it is stored in canonical JSON form.
    private["hidden_table_json"] = canonical_json_bytes(dict(table)).decode("utf-8")
    private["rule_epochs_sealed"] = int(private.get("rule_epochs_sealed", 0)) + 1
    return dataclasses.replace(state, private=private)


def _reduce_agent_decision(state: WorldState, event: WorldEvent, sealed: Any) -> WorldState:
    """Evaluate one chosen ordering against the hidden table; publish counters."""

    payload = event.payload or {}
    decision = payload.get("decision")
    if not isinstance(decision, Mapping) or "ordering" not in decision:
        raise ValueError("agent decision payload is malformed")
    chosen = decision["ordering"]
    context = decision.get("context")
    if not isinstance(context, str) or not context:
        raise ValueError("agent decision must name its task context")

    hidden_table_json = state.private.get("hidden_table_json", "")
    if not hidden_table_json:
        raise ValueError("decision evaluated before any rule epoch was sealed")
    hidden_table = json.loads(hidden_table_json)
    if context not in hidden_table:
        raise ValueError("decision evaluated for a context without a sealed rule")

    switch_tick = int(state.public["rule_switch_tick"])
    prefix = "pre" if event.tick < switch_tick else "post"
    success = chosen == hidden_table[context]

    public = dict(state.public)
    public[f"attempts_{prefix}"] = int(public.get(f"attempts_{prefix}", 0)) + 1
    if success:
        public[f"successes_{prefix}"] = int(public.get(f"successes_{prefix}", 0)) + 1
    public["attempts"] = int(public.get("attempts", 0)) + 1
    public["successes"] = int(public.get("successes", 0)) + (1 if success else 0)
    public["decisions"] = int(public.get("decisions", 0)) + 1
    return dataclasses.replace(state, public=public)


def _reduce_memory_ablation(state: WorldState, event: WorldEvent, sealed: Any) -> WorldState:
    """Record the explicit ablation transaction of arm B (at most once)."""

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
    """Create one genesis branch of the G1 v9 scenario."""

    return WorldKernel.create(
        contract.scenario_id,
        build_machine(contract),
        store=store,
        branch_id=branch_id,
        initial_public={
            "rule_switch_tick": contract.acquisition_ticks,
            "attempts_pre": 0,
            "successes_pre": 0,
            "attempts_post": 0,
            "successes_post": 0,
            "attempts": 0,
            "successes": 0,
            "decisions": 0,
            "presented": 0,
            "world_pulses": 0,
            "ablation_at": -1,
        },
        initial_private={
            "current_epoch": -1,
            "hidden_table_json": "",
            "rule_epochs_sealed": 0,
            "decisions": 0,
        },
    )


def seal_epoch(
    kernel: WorldKernel,
    *,
    epoch: int,
    seed: bytes,
    contract: G1V9Contract,
    previous_table: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Derive and seal one rule epoch; return the sealed (hidden) table."""

    table = derive_epoch_table(
        seed,
        epoch,
        contract.context_count,
        dict(previous_table) if previous_table is not None else None,
    )
    kernel.emit(
        "rule_epoch",
        {"epoch": epoch, "table": dict(table)},
        source="external",
        visibility="private",
    )
    return table


def present_context(kernel: WorldKernel, context: str) -> None:
    """Present one public task context to the agent."""

    kernel.emit("context_presented", {"context": context})
