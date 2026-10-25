from __future__ import annotations

import time

import pytest

from resonance_world.experimental_runtime.events import (
    EVENT_SOURCES,
    EVENT_VISIBILITIES,
    WorldEvent,
)
from resonance_world.experimental_runtime.kernel import WorldKernel
from resonance_world.experimental_runtime.machine import StateMachine
from resonance_world.experimental_runtime.state import WorldState
from resonance_world.experimental_runtime.world_time import WorldClock


def build_machine() -> StateMachine:
    machine = StateMachine()
    machine.register("tick", lambda state, event, sealed: state)
    machine.register("note", lambda state, event, sealed: state)
    return machine


def new_kernel(**kwargs: object) -> WorldKernel:
    return WorldKernel.create("kernel-core-test", build_machine(), **kwargs)


def test_world_clock_is_pure_causal_time() -> None:
    clock = WorldClock()
    assert clock.tick == 0
    assert clock.advance(500).tick == 500
    assert clock.advance().tick == 1
    assert clock.advance(3).advance(4).tick == 7
    assert (WorldClock(2) < WorldClock(3)) is True


def test_world_clock_advances_without_sleeping() -> None:
    clock = WorldClock()
    started = time.perf_counter()
    advanced = clock.advance(1_000_000)
    elapsed = time.perf_counter() - started
    assert advanced.tick == 1_000_000
    assert elapsed < 1.0


def test_world_clock_rejects_invalid_advances() -> None:
    clock = WorldClock(5)
    with pytest.raises(ValueError, match="positive"):
        clock.advance(0)
    with pytest.raises(ValueError, match="positive"):
        clock.advance(-2)
    with pytest.raises(TypeError):
        clock.advance(True)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="non-negative"):
        WorldClock(-1)


def test_event_digest_is_deterministic_and_tamper_evident() -> None:
    first = WorldEvent.create(seq=0, tick=0, kind="note", payload={"value": 1})
    second = WorldEvent.create(seq=0, tick=0, kind="note", payload={"value": 1})
    assert first.event_sha256 == second.event_sha256

    changed = WorldEvent.create(seq=0, tick=0, kind="note", payload={"value": 2})
    assert changed.event_sha256 != first.event_sha256

    with pytest.raises(ValueError, match="payload_sha256"):
        WorldEvent.create(
            seq=0,
            tick=0,
            kind="note",
            payload={"value": 1},
            payload_sha256="0" * 64,
        )


def test_event_depends_on_must_strictly_precede() -> None:
    with pytest.raises(ValueError, match="precede"):
        WorldEvent.create(seq=2, tick=0, kind="note", payload={}, depends_on=(2,))
    with pytest.raises(ValueError, match="precede"):
        WorldEvent.create(seq=2, tick=0, kind="note", payload={}, depends_on=(5,))
    with pytest.raises(ValueError, match="strictly increasing"):
        WorldEvent.create(seq=3, tick=0, kind="note", payload={}, depends_on=(1, 1))
    event = WorldEvent.create(seq=3, tick=0, kind="note", payload={}, depends_on=(0, 2))
    assert event.depends_on == (0, 2)


def test_private_events_commit_only_to_a_digest() -> None:
    with pytest.raises(ValueError, match="inline payload"):
        WorldEvent.create(seq=0, tick=0, kind="assessment", visibility="private", payload={})
    with pytest.raises(ValueError, match="committed payload digest"):
        WorldEvent.create(seq=0, tick=0, kind="assessment", visibility="private")
    event = WorldEvent.create(
        seq=0, tick=0, kind="assessment", visibility="private", payload_sha256="a" * 64
    )
    assert event.payload is None
    assert event.payload_sha256 == "a" * 64


def test_event_source_and_visibility_are_restricted() -> None:
    assert EVENT_SOURCES == frozenset({"kernel", "agent", "external"})
    assert EVENT_VISIBILITIES == frozenset({"public", "private"})
    with pytest.raises(ValueError, match="source"):
        WorldEvent.create(seq=0, tick=0, kind="note", payload={}, source="wizard")
    with pytest.raises(ValueError, match="visibility"):
        WorldEvent.create(seq=0, tick=0, kind="note", payload={}, visibility="secret")


def test_kernel_records_events_and_stamps_watermarks() -> None:
    kernel = new_kernel()
    assert kernel.tick == 0
    first = kernel.emit("note", {"index": 1})
    assert first.seq == 0 and first.tick == 0
    assert kernel.state.event_count == 1
    kernel.advance(2)
    assert kernel.tick == 2
    assert kernel.state.event_count == kernel.event_count
    kinds = [event.kind for event in kernel.events()]
    assert kinds == ["note", "tick", "tick"]
    assert [event.tick for event in kernel.events()] == [0, 1, 2]


def test_kernel_rejects_unregistered_kinds_and_tick_violations() -> None:
    kernel = new_kernel()
    with pytest.raises(ValueError, match="no reducer registered"):
        kernel.emit("mystery", {})
    with pytest.raises(ValueError, match="only the tick boundary event"):
        kernel._record(
            kind="note",
            tick=kernel.tick + 1,
            source="kernel",
            visibility="public",
            payload={},
            depends_on=(),
        )


def test_kernel_causal_dependencies_are_validated_against_the_log() -> None:
    machine = build_machine()
    kernel = WorldKernel.create("deps-test", machine)
    anchor = kernel.emit("note", {"index": 0})
    dependent = kernel.emit("note", {"index": 1}, depends_on=(anchor.seq,))
    assert dependent.depends_on == (anchor.seq,)
    with pytest.raises(ValueError):
        kernel.emit("note", {"index": 2}, depends_on=(99,))


def test_kernel_requires_consistent_scenario_state() -> None:
    machine = build_machine()
    with pytest.raises(ValueError, match="scenario"):
        WorldKernel(
            scenario_id="a",
            machine=machine,
            state=WorldState(scenario_id="b"),
        )


def test_state_machine_forbids_reducer_watermark_mutation() -> None:
    machine = StateMachine()

    def bad_reducer(state: WorldState, event: WorldEvent, sealed: object) -> WorldState:
        from dataclasses import replace

        return replace(state, tick=99)

    machine.register("note", bad_reducer)
    kernel = WorldKernel.create("watermark-test", machine)
    with pytest.raises(ValueError, match="watermarks"):
        kernel.emit("note", {})


def test_duplicate_reducer_registration_rejected() -> None:
    machine = build_machine()
    with pytest.raises(ValueError, match="already registered"):
        machine.register("tick", lambda state, event, sealed: state)
