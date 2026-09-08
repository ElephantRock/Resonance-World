"""Fail-closed provider-send accounting with Hermes worker-thread attribution.

The guard is transport-agnostic: callers invoke :meth:`ProviderSendBudget.reserve`
immediately before a physical provider send.  The optional thread bridge exists for
runtimes such as Hermes that move the actual HTTP request into a child ``Thread``.

No network I/O is performed by this module.
"""

from __future__ import annotations

import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass


class PhysicalSendBudgetExceeded(RuntimeError):
    """Raised before a provider send would exceed a registered hard ceiling."""


class UnexpectedOutboundRequest(RuntimeError):
    """Raised before a send that lacks registered logical-call authority."""


@dataclass(frozen=True, slots=True)
class SendReservation:
    """Accounting identity assigned immediately before a physical provider send."""

    logical_index: int
    logical_send_index: int
    total_send_index: int


_MISSING = object()
_THREAD_START_PATCH_LOCK = threading.Lock()


class ProviderSendBudget:
    """Thread-safe, fail-closed physical-send budget for a registered call topology.

    Logical-call authority is stored in thread-local state so concurrent parent calls
    remain isolated.  ``propagate_to_child_threads`` bridges that authority only into
    child threads started while a registered logical call is active.  Threads started
    without such authority remain unregistered and therefore fail closed in
    :meth:`reserve`.
    """

    def __init__(
        self,
        *,
        allowed_url_prefix: str,
        maximum_logical_calls: int,
        maximum_sends_per_logical_call: int,
        maximum_sends_total: int,
    ) -> None:
        if not allowed_url_prefix.strip():
            raise ValueError("allowed_url_prefix must be non-empty")
        if maximum_logical_calls <= 0:
            raise ValueError("maximum_logical_calls must be positive")
        if maximum_sends_per_logical_call <= 0:
            raise ValueError("maximum_sends_per_logical_call must be positive")
        if maximum_sends_total <= 0:
            raise ValueError("maximum_sends_total must be positive")

        self.allowed_url_prefix = allowed_url_prefix.rstrip("/") + "/"
        self.maximum_logical_calls = maximum_logical_calls
        self.maximum_sends_per_logical_call = maximum_sends_per_logical_call
        self.maximum_sends_total = maximum_sends_total

        self._local = threading.local()
        self._lock = threading.Lock()
        self._per_logical_sends = [0 for _ in range(maximum_logical_calls)]
        self._total_sends = 0
        self._blocked_budget = 0
        self._blocked_unexpected = 0

    def _validate_logical_index(self, logical_index: int) -> None:
        if isinstance(logical_index, bool) or not isinstance(logical_index, int):
            raise TypeError("logical_index must be an integer")
        if not 0 <= logical_index < self.maximum_logical_calls:
            raise ValueError("logical_index is outside the registered topology")

    def current_logical_index(self) -> int | None:
        """Return the logical index registered on the current thread, if any."""

        return getattr(self._local, "logical_index", None)

    @contextmanager
    def logical_call(self, logical_index: int) -> Iterator[None]:
        """Register one logical-call identity on the current thread for this scope."""

        self._validate_logical_index(logical_index)
        previous = getattr(self._local, "logical_index", _MISSING)
        self._local.logical_index = logical_index
        try:
            yield
        finally:
            if previous is _MISSING:
                try:
                    del self._local.logical_index
                except AttributeError:
                    pass
            else:
                self._local.logical_index = previous

    def reserve(self, url: str) -> SendReservation:
        """Reserve one physical send or raise before transmission.

        The caller must invoke this method directly before the transport performs the
        physical send.  A missing logical context or a URL outside the registered
        provider prefix is classified as unexpected outbound traffic.
        """

        logical_index = self.current_logical_index()
        with self._lock:
            if logical_index is None or not str(url).startswith(self.allowed_url_prefix):
                self._blocked_unexpected += 1
                raise UnexpectedOutboundRequest("unregistered outbound HTTP request blocked")

            logical_count = self._per_logical_sends[logical_index]
            if (
                logical_count >= self.maximum_sends_per_logical_call
                or self._total_sends >= self.maximum_sends_total
            ):
                self._blocked_budget += 1
                raise PhysicalSendBudgetExceeded("physical provider-send budget exhausted")

            logical_count += 1
            self._total_sends += 1
            self._per_logical_sends[logical_index] = logical_count
            return SendReservation(
                logical_index=logical_index,
                logical_send_index=logical_count,
                total_send_index=self._total_sends,
            )

    @property
    def total_sends(self) -> int:
        with self._lock:
            return self._total_sends

    @property
    def blocked_budget(self) -> int:
        with self._lock:
            return self._blocked_budget

    @property
    def blocked_unexpected(self) -> int:
        with self._lock:
            return self._blocked_unexpected

    def sends_for_logical_call(self, logical_index: int) -> int:
        self._validate_logical_index(logical_index)
        with self._lock:
            return self._per_logical_sends[logical_index]

    @contextmanager
    def propagate_to_child_threads(self) -> Iterator[None]:
        """Propagate active logical authority into plain child ``Thread`` targets.

        Hermes performs provider requests in newly spawned ``threading.Thread``
        workers.  Python 3.12 does not inherit ``threading.local`` values into those
        workers.  While this context is active, ``Thread.start`` captures the logical
        index from the starting thread and wraps that child thread's target so the
        same index is installed for the target's lifetime.

        The patch is process-global but bounded by this context and guarded so only
        one bridge may be active at a time.  Threads started with no registered
        logical index are not granted authority.  The original ``Thread.start`` is
        restored even when the guarded operation raises.
        """

        if not _THREAD_START_PATCH_LOCK.acquire(blocking=False):
            raise RuntimeError("provider thread-context propagation is already active")

        original_start = threading.Thread.start
        marker_name = "_rw_provider_guard_context_wrapped"

        def start_with_logical_context(
            thread: threading.Thread, *args: object, **kwargs: object
        ) -> object:
            inherited = self.current_logical_index()
            target = getattr(thread, "_target", None)
            already_wrapped = bool(getattr(thread, marker_name, False))

            if inherited is not None and target is not None and not already_wrapped:
                self._validate_logical_index(inherited)
                original_target = target

                def target_with_logical_context(*target_args: object, **target_kwargs: object) -> object:
                    with self.logical_call(inherited):
                        return original_target(*target_args, **target_kwargs)

                thread._target = target_with_logical_context  # type: ignore[attr-defined]
                setattr(thread, marker_name, True)

            return original_start(thread, *args, **kwargs)

        threading.Thread.start = start_with_logical_context  # type: ignore[method-assign]
        try:
            yield
        finally:
            threading.Thread.start = original_start  # type: ignore[method-assign]
            _THREAD_START_PATCH_LOCK.release()
