from __future__ import annotations

import sqlite3

import pytest

from resonance_world.experimental_runtime.kernel import WorldKernel
from resonance_world.experimental_runtime.scenario import (
    ScriptedPolicy,
    build_machine,
    drive,
    start_kernel,
)
from resonance_world.experimental_runtime.store import KernelStore


def test_four_branches_are_fully_isolated() -> None:
    store = KernelStore()
    parent = start_kernel(store)
    drive(parent, ticks=10, policy=ScriptedPolicy())
    parent_hash = parent.state_hash()
    parent_events = parent.event_count

    children = [parent.fork(f"branch-{index}") for index in range(1, 5)]
    # Distinct lengths guarantee distinct growth totals, hence distinct
    # final state hashes even though the scenario aggregates decisions.
    for child, ticks in zip(children, (9, 10, 11, 12), strict=True):
        drive(child, ticks=ticks, policy=ScriptedPolicy())

    assert parent.state_hash() == parent_hash
    assert parent.event_count == parent_events

    hashes = [child.state_hash() for child in children]
    assert len(set(hashes)) == 4

    for child in children:
        assert child.state.public["forked_from"] == "main"
        for event in child.events():
            payload = event.payload or {}
            assert payload.get("parent_branch_id") in (None, "main")

    fork_records = [event for event in children[0].events() if event.kind == "branch_fork"]
    assert len(fork_records) == 1
    assert fork_records[0].payload is not None
    assert fork_records[0].payload["parent_branch_id"] == "main"
    assert fork_records[0].payload["parent_event_count"] == parent_events


def test_branch_fork_requires_a_store() -> None:
    kernel = WorldKernel.create("no-store", build_machine())
    with pytest.raises(ValueError, match="requires a persistence store"):
        kernel.fork("child")


def test_duplicate_branch_registration_fails_closed() -> None:
    store = KernelStore()
    parent = start_kernel(store)
    parent.fork("twin")
    with pytest.raises(ValueError, match="already registered"):
        parent.fork("twin")


def test_checkpoint_round_trip_and_integrity() -> None:
    store = KernelStore()
    kernel = start_kernel(store)
    drive(kernel, ticks=25, policy=ScriptedPolicy())
    checkpoint = kernel.checkpoint("mid")
    assert checkpoint.tick == 25

    loaded = store.load_checkpoint("main", "mid")
    assert loaded.state_sha256 == checkpoint.state_sha256
    assert loaded.state.public == checkpoint.state.public

    with pytest.raises(ValueError, match="already exists"):
        kernel.checkpoint("mid")
    with pytest.raises(ValueError, match="no checkpoint"):
        store.load_checkpoint("main", "missing")


def test_checkpoint_blob_tampering_detected(tmp_path) -> None:
    store_path = tmp_path / "world.sqlite3"
    store = KernelStore(store_path)
    kernel = start_kernel(store)
    drive(kernel, ticks=5, policy=ScriptedPolicy())
    kernel.checkpoint("mid")
    store.close()

    connection = sqlite3.connect(str(store_path))
    connection.execute(
        "UPDATE checkpoints SET state_blob = ? WHERE name = 'mid'", (b"{\"tampered\": true}",)
    )
    connection.commit()
    connection.close()

    reopened = KernelStore(store_path)
    with pytest.raises(ValueError, match="verification"):
        reopened.load_checkpoint("main", "mid")


def test_resume_from_head_checkpoint_continues_the_sequence() -> None:
    store = KernelStore()
    kernel = start_kernel(store)
    drive(kernel, ticks=10, policy=ScriptedPolicy())
    head = kernel.event_count
    kernel.checkpoint("head")

    resumed = WorldKernel.resume(
        store=store, branch_id="main", machine=build_machine(), checkpoint_name="head"
    )
    assert resumed.event_count == head
    assert resumed.state_hash() == kernel.state_hash()
    kind = "note" if "note" in build_machine().kinds() else "world_effect"
    emitted = resumed.emit(kind, {"x": 1})
    assert emitted.seq == head


def test_resume_rebuilds_from_log_without_checkpoint() -> None:
    store = KernelStore()
    kernel = start_kernel(store)
    drive(kernel, ticks=10, policy=ScriptedPolicy())

    resumed = WorldKernel.resume(store=store, branch_id="main", machine=build_machine())
    assert resumed.state_hash() == kernel.state_hash()
    assert resumed.event_count == kernel.event_count


def test_resume_rejects_stale_checkpoints() -> None:
    store = KernelStore()
    kernel = start_kernel(store)
    drive(kernel, ticks=10, policy=ScriptedPolicy())
    kernel.checkpoint("mid")
    drive(kernel, ticks=10, policy=ScriptedPolicy())
    with pytest.raises(ValueError, match="not at the head"):
        WorldKernel.resume(
            store=store, branch_id="main", machine=build_machine(), checkpoint_name="mid"
        )


def test_resume_rejects_unknown_branch() -> None:
    store = KernelStore()
    start_kernel(store)
    with pytest.raises(ValueError, match="unknown branch"):
        WorldKernel.resume(store=store, branch_id="ghost", machine=build_machine())


def test_event_log_is_append_only() -> None:
    store = KernelStore()
    kernel = start_kernel(store)
    drive(kernel, ticks=3, policy=ScriptedPolicy())
    count = store.event_count("main")
    assert count > 0
    duplicate = store.iter_events("main")[-1]
    with pytest.raises(ValueError, match="rolled back"):
        store.append_event("main", duplicate)
