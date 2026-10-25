from __future__ import annotations

import pytest

from resonance_world.experimental_runtime.kernel import WorldKernel
from resonance_world.experimental_runtime.machine import StateMachine


def build_machine() -> StateMachine:
    machine = StateMachine()
    machine.register("tick", lambda state, event, sealed: state)
    machine.register("note", lambda state, event, sealed: state)
    return machine


def new_kernel() -> WorldKernel:
    return WorldKernel.create("scheduler-test", build_machine())


def test_same_tick_order_is_fifo_for_equal_priority() -> None:
    kernel = new_kernel()
    kernel.schedule("note", {"order": "first"})
    kernel.schedule("note", {"order": "second"})
    kernel.schedule("note", {"order": "third"})
    kernel.advance()
    payloads = [
        event.payload for event in kernel.events() if event.kind == "note"
    ]
    assert payloads == [
        {"order": "first"},
        {"order": "second"},
        {"order": "third"},
    ]


def test_priority_overrides_insertion_order_stably() -> None:
    kernel = new_kernel()
    kernel.schedule("note", {"order": "a"}, priority=0)
    kernel.schedule("note", {"order": "b"}, priority=-1)
    kernel.schedule("note", {"order": "c"}, priority=0)
    kernel.advance()
    payloads = [event.payload for event in kernel.events() if event.kind == "note"]
    assert payloads == [{"order": "b"}, {"order": "a"}, {"order": "c"}]


def test_drain_order_is_deterministic_across_constructions() -> None:
    def capture() -> list[dict[str, str] | None]:
        kernel = new_kernel()
        for index in range(20):
            kernel.schedule("note", {"index": index}, priority=index % 3)
        kernel.advance()
        return [event.payload for event in kernel.events() if event.kind == "note"]

    assert capture() == capture()


def test_scheduled_events_take_their_tick_before_the_boundary() -> None:
    kernel = new_kernel()
    kernel.advance(3)
    kernel.schedule("note", {"at": "tick-3"})
    kernel.advance()
    notes = [event for event in kernel.events() if event.kind == "note"]
    boundaries = [event for event in kernel.events() if event.kind == "tick"]
    assert notes[-1].tick == 3
    assert notes[-1].seq < boundaries[-1].seq
    assert boundaries[-1].tick == 4


def test_scheduler_rejects_invalid_drafts() -> None:
    kernel = new_kernel()
    with pytest.raises(ValueError, match="kind is required"):
        kernel.schedule("")
    with pytest.raises(ValueError, match="visibility"):
        kernel.schedule("note", visibility="hidden")
    with pytest.raises(ValueError, match="private events require"):
        kernel.schedule("note", visibility="private")
    with pytest.raises(TypeError, match="priority"):
        kernel.schedule("note", priority=1.5)  # type: ignore[arg-type]


def test_scheduler_pending_count_tracks_the_queue() -> None:
    kernel = new_kernel()
    assert kernel._scheduler.pending() == 0
    kernel.schedule("note", {})
    kernel.schedule("note", {})
    assert kernel._scheduler.pending() == 2
    kernel.advance()
    assert kernel._scheduler.pending() == 0
