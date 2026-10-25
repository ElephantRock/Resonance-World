from __future__ import annotations

import json

from resonance_world.experimental_runtime.kernel import WorldKernel
from resonance_world.experimental_runtime.scenario import (
    SCENARIO_ID,
    ScriptedPolicy,
    build_machine,
    drive,
    start_kernel,
)
from resonance_world.experimental_runtime.state import (
    WorldState,
    full_state_bytes,
    full_state_sha256,
    public_state_bytes,
    public_state_sha256,
)
from resonance_world.experimental_runtime.store import KernelStore


def test_public_hash_is_stable_under_private_changes() -> None:
    machine = build_machine()
    first = WorldKernel.create(
        SCENARIO_ID,
        machine,
        initial_public={"stock": 10},
        initial_private={"hidden_threshold": 6},
    )
    second = WorldKernel.create(
        SCENARIO_ID,
        machine,
        initial_public={"stock": 10},
        initial_private={"hidden_threshold": 9},
    )
    assert public_state_sha256(first.state) == public_state_sha256(second.state)
    assert full_state_sha256(first.state) != full_state_sha256(second.state)


def test_observation_exposes_no_private_evaluator_state() -> None:
    store = KernelStore()
    kernel = start_kernel(store)
    policy = ScriptedPolicy()
    drive(kernel, ticks=100, policy=policy)
    observation = kernel.observe()
    assert "stress_total" not in observation.public_state
    assert "signals" not in observation.public_state
    assert "assessments" not in observation.public_state
    assert kernel.state.private["assessments"] == 1
    assert kernel.state.private["stress_total"] >= 0


def test_public_event_log_never_carries_sealed_payloads() -> None:
    from collections.abc import Mapping

    def plain(value):
        if isinstance(value, Mapping):
            return {key: plain(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [plain(item) for item in value]
        return value

    store = KernelStore()
    kernel = start_kernel(store)
    drive(kernel, ticks=100, policy=ScriptedPolicy())

    public_json = json.dumps(
        [plain(event.payload) for event in kernel.public_events()], sort_keys=True
    )
    assert "stress" not in public_json
    assert "hidden_threshold" not in public_json

    sealed_events = [event for event in kernel.events() if event.visibility == "private"]
    assert len(sealed_events) == 1
    assert sealed_events[0].payload is None
    assert len(sealed_events[0].payload_sha256) == 64


def test_full_state_bytes_cover_private_state() -> None:
    state = WorldState(
        scenario_id="s",
        tick=3,
        event_count=7,
        public={"a": 1},
        private={"hidden": "x"},
    )
    assert b"hidden" in full_state_bytes(state)
    assert b"hidden" not in public_state_bytes(state)
    assert full_state_sha256(state) != public_state_sha256(state)
    moved_private = WorldState(
        scenario_id="s",
        tick=3,
        event_count=7,
        public={"a": 1},
        private={"hidden": "y"},
    )
    assert public_state_sha256(moved_private) == public_state_sha256(state)
    assert full_state_sha256(moved_private) != full_state_sha256(state)


def test_state_value_constraints() -> None:
    import pytest

    with pytest.raises(ValueError, match="state values"):
        WorldState(scenario_id="s", public={"a": 1.5})  # type: ignore[dict-item]
    with pytest.raises(ValueError, match="state values"):
        WorldState(scenario_id="s", public={"a": True})  # type: ignore[dict-item]
    with pytest.raises(ValueError, match="state keys"):
        WorldState(scenario_id="s", public={"": 1})


def test_agent_decisions_are_recorded_with_provenance() -> None:
    store = KernelStore()
    kernel = start_kernel(store)
    policy = ScriptedPolicy()
    drive(kernel, ticks=5, policy=policy)
    decisions = [event for event in kernel.events() if event.kind == "agent_decision"]
    assert len(decisions) == 1
    payload = decisions[0].payload
    assert payload is not None
    assert payload["model_id"] == policy.model_id
    assert payload["decision"]["action"] in ("harvest", "maintain")
    assert decisions[0].source == "agent"
    assert decisions[0].depends_on != ()
