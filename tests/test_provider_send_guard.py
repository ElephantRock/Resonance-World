from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from resonance_world.provider_send_guard import (
    PhysicalSendBudgetExceeded,
    ProviderSendBudget,
    UnexpectedOutboundRequest,
)

ALLOWED_PREFIX = "https://api.example.test/provider/v1"
ALLOWED_URL = ALLOWED_PREFIX + "/chat/completions"
DISALLOWED_URL = "https://elsewhere.example.test/chat/completions"


def budget(
    *,
    logical_calls: int = 16,
    per_logical: int = 4,
    total: int = 32,
) -> ProviderSendBudget:
    return ProviderSendBudget(
        allowed_url_prefix=ALLOWED_PREFIX,
        maximum_logical_calls=logical_calls,
        maximum_sends_per_logical_call=per_logical,
        maximum_sends_total=total,
    )


def test_registered_logical_context_propagates_to_child_worker() -> None:
    send_budget = budget()
    reservations = []

    def child() -> None:
        reservations.append(send_budget.reserve(ALLOWED_URL))

    with send_budget.propagate_to_child_threads():
        with send_budget.logical_call(7):
            worker = threading.Thread(target=child)
            worker.start()
            worker.join()

    assert len(reservations) == 1
    assert reservations[0].logical_index == 7
    assert reservations[0].logical_send_index == 1
    assert reservations[0].total_send_index == 1
    assert send_budget.sends_for_logical_call(7) == 1
    assert send_budget.blocked_unexpected == 0


def test_concurrent_parent_calls_keep_child_attribution_disjoint() -> None:
    send_budget = budget(logical_calls=8, per_logical=3, total=8)
    barrier = threading.Barrier(4)

    def parent(logical_index: int) -> None:
        with send_budget.logical_call(logical_index):
            barrier.wait()
            children = [
                threading.Thread(target=lambda: send_budget.reserve(ALLOWED_URL))
                for _ in range(2)
            ]
            for child in children:
                child.start()
            for child in children:
                child.join()

    with send_budget.propagate_to_child_threads():
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(parent, range(4)))

    assert send_budget.total_sends == 8
    assert [send_budget.sends_for_logical_call(i) for i in range(4)] == [2, 2, 2, 2]
    assert send_budget.blocked_unexpected == 0


def test_child_without_registered_parent_context_remains_blocked() -> None:
    send_budget = budget()
    errors: list[BaseException] = []

    def child() -> None:
        try:
            send_budget.reserve(ALLOWED_URL)
        except BaseException as exc:
            errors.append(exc)

    with send_budget.propagate_to_child_threads():
        worker = threading.Thread(target=child)
        worker.start()
        worker.join()

    assert len(errors) == 1
    assert isinstance(errors[0], UnexpectedOutboundRequest)
    assert send_budget.total_sends == 0
    assert send_budget.blocked_unexpected == 1


def test_disallowed_url_remains_blocked_with_inherited_context() -> None:
    send_budget = budget()
    errors: list[BaseException] = []

    def child() -> None:
        try:
            send_budget.reserve(DISALLOWED_URL)
        except BaseException as exc:
            errors.append(exc)

    with send_budget.propagate_to_child_threads():
        with send_budget.logical_call(3):
            worker = threading.Thread(target=child)
            worker.start()
            worker.join()

    assert len(errors) == 1
    assert isinstance(errors[0], UnexpectedOutboundRequest)
    assert send_budget.sends_for_logical_call(3) == 0
    assert send_budget.blocked_unexpected == 1


def test_exact_per_logical_and_campaign_send_ceilings_fail_closed() -> None:
    send_budget = budget(logical_calls=2, per_logical=2, total=3)

    with send_budget.logical_call(0):
        assert send_budget.reserve(ALLOWED_URL).total_send_index == 1
        assert send_budget.reserve(ALLOWED_URL).total_send_index == 2
        with pytest.raises(PhysicalSendBudgetExceeded):
            send_budget.reserve(ALLOWED_URL)

    with send_budget.logical_call(1):
        assert send_budget.reserve(ALLOWED_URL).total_send_index == 3
        with pytest.raises(PhysicalSendBudgetExceeded):
            send_budget.reserve(ALLOWED_URL)

    assert send_budget.total_sends == 3
    assert send_budget.sends_for_logical_call(0) == 2
    assert send_budget.sends_for_logical_call(1) == 1
    assert send_budget.blocked_budget == 2


def test_thread_start_patch_is_restored_after_bridge_scope() -> None:
    send_budget = budget()
    original_start = threading.Thread.start

    with send_budget.propagate_to_child_threads():
        assert threading.Thread.start is not original_start

    assert threading.Thread.start is original_start


def test_nested_child_threads_inherit_registered_logical_context() -> None:
    send_budget = budget()
    reservations = []

    def grandchild() -> None:
        reservations.append(send_budget.reserve(ALLOWED_URL))

    def child() -> None:
        worker = threading.Thread(target=grandchild)
        worker.start()
        worker.join()

    with send_budget.propagate_to_child_threads():
        with send_budget.logical_call(5):
            worker = threading.Thread(target=child)
            worker.start()
            worker.join()

    assert [reservation.logical_index for reservation in reservations] == [5]
    assert send_budget.sends_for_logical_call(5) == 1
