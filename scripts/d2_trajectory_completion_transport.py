"""Fail-closed transport instrumentation for D2 trajectory qualification."""

from __future__ import annotations

import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import d2_trajectory_completion_contract as contract

from resonance_world.provider_send_guard import ProviderSendBudget, SendReservation


class LogicalAttributionMismatch(RuntimeError):
    """Raised before transmission when request origin disagrees with logical context."""


class TransportLedger:
    """Bounded metadata preserving independent origin and reservation identity."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._rows = {index: [] for index in range(contract.MAX_LOGICAL_CALLS)}
        self._attribution_mismatches = 0

    def record_attribution_mismatch(self) -> None:
        with self._lock:
            self._attribution_mismatches += 1

    @property
    def attribution_mismatches(self) -> int:
        with self._lock:
            return self._attribution_mismatches

    def begin(self, reservation: SendReservation, origin_logical_index: int) -> int:
        if origin_logical_index != reservation.logical_index:
            self.record_attribution_mismatch()
            raise LogicalAttributionMismatch(
                "request origin disagrees with provider-send reservation"
            )
        row = {
            "origin_logical_index": origin_logical_index,
            "logical_index": reservation.logical_index,
            "logical_send_index": reservation.logical_send_index,
            "total_send_index": reservation.total_send_index,
            "http_status": None,
            "transport_error_type": None,
        }
        with self._lock:
            rows = self._rows[reservation.logical_index]
            rows.append(row)
            return len(rows) - 1

    def response(self, reservation: SendReservation, row_index: int, status: int) -> None:
        with self._lock:
            self._rows[reservation.logical_index][row_index]["http_status"] = int(status)

    def error(self, reservation: SendReservation, row_index: int, exc: BaseException) -> None:
        with self._lock:
            self._rows[reservation.logical_index][row_index]["transport_error_type"] = (
                type(exc).__name__
            )

    def rows(self, logical_index: int) -> list[dict[str, Any]]:
        with self._lock:
            return [dict(row) for row in self._rows[logical_index]]


def verified_origin_logical_index(
    request: Any,
    budget: ProviderSendBudget,
    ledger: TransportLedger,
) -> int:
    raw = request.headers.get(contract.PROBE_ORIGIN_HEADER)
    try:
        origin = int(raw) if raw is not None else -1
    except (TypeError, ValueError):
        origin = -1
    registered = budget.current_logical_index()
    if (
        not 0 <= origin < contract.MAX_LOGICAL_CALLS
        or registered is None
        or origin != registered
    ):
        ledger.record_attribution_mismatch()
        raise LogicalAttributionMismatch(
            "independent request origin does not match registered logical context"
        )
    return origin


class ProviderWorkerTracker:
    """Track pinned Hermes provider workers and drain before hook restoration."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._threads: set[threading.Thread] = set()
        self._observed = 0
        self._alive_after_drain = 0
        self._transport_hooks_restored = False

    @staticmethod
    def is_provider_worker(thread: threading.Thread) -> bool:
        target = getattr(thread, "_target", None)
        return (
            getattr(target, "__module__", None) == contract.PROVIDER_WORKER_TARGET_MODULE
            and getattr(target, "__name__", None) == contract.PROVIDER_WORKER_TARGET_NAME
        )

    def observe_before_start(self, thread: threading.Thread) -> None:
        if not self.is_provider_worker(thread):
            return
        with self._lock:
            self._threads.add(thread)
            self._observed += 1

    @property
    def observed(self) -> int:
        with self._lock:
            return self._observed

    @property
    def alive_after_drain(self) -> int:
        with self._lock:
            return self._alive_after_drain

    @property
    def transport_hooks_restored(self) -> bool:
        with self._lock:
            return self._transport_hooks_restored

    def mark_transport_hooks_restored(self) -> None:
        with self._lock:
            self._transport_hooks_restored = True

    def drain(
        self, timeout_seconds: float = contract.PROVIDER_WORKER_DRAIN_TIMEOUT_SECONDS
    ) -> int:
        deadline = time.monotonic() + timeout_seconds
        while True:
            with self._lock:
                alive = [thread for thread in self._threads if thread.is_alive()]
            if not alive:
                with self._lock:
                    self._alive_after_drain = 0
                return 0
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                with self._lock:
                    self._alive_after_drain = len(alive)
                return len(alive)
            for thread in alive:
                thread.join(timeout=min(0.2, remaining))


@contextmanager
def transport_guard(
    budget: ProviderSendBudget,
    ledger: TransportLedger,
    workers: ProviderWorkerTracker,
) -> Iterator[None]:
    """Guard physical sends and restore hooks only after provider workers drain.

    This context is intended to be nested *inside* `budget.propagate_to_child_threads()`.
    The tracker therefore sees Hermes' original `run_agent._call` target before the
    provider guard's Thread.start bridge wraps that target with logical-call context.

    If a provider worker remains alive after the bounded drain, the HTTPX hooks are
    intentionally left installed until process exit. That makes a late daemon retry
    remain subject to attribution and physical-send ceilings instead of bypassing them.
    The result is then fail-closed because the tracker records a live worker and does
    not mark transport hooks as restored.
    """
    import httpx

    original_sync = httpx.Client._send_single_request
    original_async = httpx.AsyncClient._send_single_request
    original_thread_start = threading.Thread.start

    def tracked_thread_start(
        thread: threading.Thread, *args: object, **kwargs: object
    ) -> object:
        workers.observe_before_start(thread)
        return original_thread_start(thread, *args, **kwargs)

    def capped_sync(client: Any, request: Any) -> Any:
        origin = verified_origin_logical_index(request, budget, ledger)
        reservation = budget.reserve(str(request.url))
        row_index = ledger.begin(reservation, origin)
        try:
            response = original_sync(client, request)
        except Exception as exc:
            ledger.error(reservation, row_index, exc)
            raise
        ledger.response(reservation, row_index, response.status_code)
        return response

    async def capped_async(client: Any, request: Any) -> Any:
        origin = verified_origin_logical_index(request, budget, ledger)
        reservation = budget.reserve(str(request.url))
        row_index = ledger.begin(reservation, origin)
        try:
            response = await original_async(client, request)
        except Exception as exc:
            ledger.error(reservation, row_index, exc)
            raise
        ledger.response(reservation, row_index, response.status_code)
        return response

    threading.Thread.start = tracked_thread_start  # type: ignore[method-assign]
    httpx.Client._send_single_request = capped_sync
    httpx.AsyncClient._send_single_request = capped_async
    try:
        yield
    finally:
        alive = workers.drain()
        threading.Thread.start = original_thread_start  # type: ignore[method-assign]
        if alive == 0:
            httpx.Client._send_single_request = original_sync
            httpx.AsyncClient._send_single_request = original_async
            workers.mark_transport_hooks_restored()
