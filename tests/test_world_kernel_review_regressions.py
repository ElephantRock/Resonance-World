"""Regression tests for the independent review findings on PR #311.

Each test class maps to one review finding. These tests fail on commit
``c75bb430`` and must pass on every follow-up commit.
"""

from __future__ import annotations

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
