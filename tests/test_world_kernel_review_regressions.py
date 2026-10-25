"""Regression tests for the independent review findings on PR #311.

Each test class maps to one review finding. These tests fail on commit
``c75bb430`` and must pass on every follow-up commit.
"""

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


def test_duplicate_decision_is_rejected_after_being_recorded() -> None:
    """P0-3: the answered set must be updated once a decision is recorded."""

    store = KernelStore()
    kernel = start_kernel(store)
    request = kernel.request_decision()
    kernel.record_decision(request, {"action": "harvest"}, model_id="test-model")

    with pytest.raises(ValueError, match="already answered"):
        kernel.record_decision(request, {"action": "maintain"}, model_id="test-model")

    second = [event for event in kernel.events() if event.kind == "agent_decision"]
    assert len(second) == 1
    assert second[0].payload["decision"]["action"] == "harvest"


def test_forged_request_from_another_branch_is_rejected() -> None:
    parent_store = KernelStore()
    parent = start_kernel(parent_store)
    drive(parent, ticks=5, policy=ScriptedPolicy())
    child = parent.fork("child")

    request = parent.request_decision()
    with pytest.raises(ValueError, match="different branch"):
        child.record_decision(request, {"action": "harvest"}, model_id="test-model")


def test_stale_request_is_rejected_after_the_world_advances() -> None:
    store = KernelStore()
    kernel = start_kernel(store)
    request = kernel.request_decision()
    kernel.advance()

    with pytest.raises(ValueError, match="stale"):
        kernel.record_decision(request, {"action": "harvest"}, model_id="test-model")


def test_request_not_matching_latest_observation_is_rejected() -> None:
    store = KernelStore()
    kernel = start_kernel(store)
    first = kernel.request_decision()
    second = kernel.request_decision()
    assert first.request_id != second.request_id

    with pytest.raises(ValueError, match="latest recorded observation"):
        kernel.record_decision(first, {"action": "harvest"}, model_id="test-model")
    kernel.record_decision(second, {"action": "harvest"}, model_id="test-model")


def test_answered_requests_survive_resume() -> None:
    store = KernelStore()
    kernel = start_kernel(store)
    policy = ScriptedPolicy()
    drive(kernel, ticks=10, policy=policy)
    kernel.checkpoint("head")

    resumed = WorldKernel.resume(
        store=store, branch_id="main", machine=build_machine(), checkpoint_name="head"
    )
    answered = resumed._answered_requests
    assert len(answered) == 2  # ticks 4 and 9 carry decisions

    stale = resumed.request_decision()
    # A reconstructed kernel must not accept the pre-resume answered set as new.
    assert stale.request_id not in answered
    resumed.record_decision(stale, {"action": "maintain"}, model_id="test-model")
    with pytest.raises(ValueError, match="already answered"):
        resumed.record_decision(stale, {"action": "harvest"}, model_id="test-model")


# ---------------------------------------------------------------------------
# P0-4: atomicity of world transition and storage
# ---------------------------------------------------------------------------


class _FailingStore(KernelStore):
    """A store whose next append can be made to fail on demand."""

    def __init__(self) -> None:
        super().__init__()
        self.fail_next = False
        self.failures = 0

    def append_event(self, branch_id, event, *, sealed_payload=None):  # type: ignore[override]
        if self.fail_next:
            self.fail_next = False
            self.failures += 1
            import sqlite3

            raise sqlite3.OperationalError("injected storage failure")
        return super().append_event(branch_id, event, sealed_payload=sealed_payload)


def test_world_does_not_advance_when_storage_fails() -> None:
    """P0-4: a failed append must leave the live engine at the logged state."""

    store = _FailingStore()
    kernel = start_kernel(store)
    first = kernel.emit("world_effect", {"tick": 0})
    hash_after_first = kernel.state_hash()
    count_after_first = kernel.event_count

    store.fail_next = True
    with pytest.raises(sqlite3.OperationalError, match="injected"):
        kernel.emit("world_effect", {"tick": 0})

    assert kernel.state_hash() == hash_after_first
    assert kernel.event_count == count_after_first
    assert len(kernel.events()) == count_after_first

    # The failed sequence number is not consumed: the next event takes it.
    second = kernel.emit("world_effect", {"tick": 0})
    assert second.seq == first.seq + 1
    assert kernel.event_count == count_after_first + 1


def test_sealed_state_is_not_committed_when_storage_fails() -> None:
    store = _FailingStore()
    kernel = start_kernel(store)
    drive(kernel, ticks=4, policy=ScriptedPolicy())
    sealed_before = dict(kernel._sealed)
    state_hash = kernel.state_hash()
    store_count = store.event_count("main")

    store.fail_next = True
    kernel.schedule(
        "assessment",
        {"epoch": 99, "stress": 9},
        source="external",
        visibility="private",
    )
    with pytest.raises(sqlite3.OperationalError, match="injected"):
        kernel.advance()

    assert kernel.state_hash() == state_hash
    assert kernel._sealed == sealed_before
    assert store.event_count("main") == store_count


def test_log_stays_verifiable_after_recovered_storage_failure() -> None:
    from resonance_world.experimental_runtime.replay import replay_branch

    store = _FailingStore()
    kernel = start_kernel(store)
    drive(kernel, ticks=6, policy=ScriptedPolicy())
    store.fail_next = True
    with pytest.raises(sqlite3.OperationalError, match="injected"):
        kernel.emit("world_effect", {"tick": kernel.tick})
    drive(kernel, ticks=2, policy=ScriptedPolicy())

    result = replay_branch(store, "main", build_machine())
    assert result.final_state_sha256 == kernel.state_hash()
    assert result.all_checkpoints_matched or not result.checkpoint_verifications
