"""Deterministic event scheduler with stable total ordering.

Events submitted for the current world tick are queued with an explicit
integer priority and a monotonic insertion index. Draining orders the
queue by ``(priority, insertion_index)``; Python's stable sort plus the
unique insertion index gives a total, reproducible order that does not
depend on hashing, dict iteration, or timing.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from .events import EVENT_SOURCES, EVENT_VISIBILITIES


@dataclass(frozen=True, slots=True)
class ScheduledEvent:
    """One queued event draft awaiting dispatch at the current tick."""

    kind: str
    source: str
    visibility: str
    priority: int
    order_index: int
    payload: Mapping[str, Any] | None
    payload_sha256: str | None
    depends_on: tuple[int, ...]


class EventScheduler:
    """A deterministic same-tick event queue."""

    def __init__(self) -> None:
        self._queue: list[ScheduledEvent] = []
        self._next_order_index = 0

    def submit(
        self,
        kind: str,
        *,
        payload: Mapping[str, Any] | None = None,
        payload_sha256: str | None = None,
        source: str = "kernel",
        visibility: str = "public",
        priority: int = 0,
        depends_on: tuple[int, ...] = (),
    ) -> None:
        """Queue one event draft for the current tick."""

        if not kind:
            raise ValueError("kind is required")
        if source not in EVENT_SOURCES:
            raise ValueError(f"source must be one of {sorted(EVENT_SOURCES)}")
        if visibility not in EVENT_VISIBILITIES:
            raise ValueError(f"visibility must be one of {sorted(EVENT_VISIBILITIES)}")
        if visibility == "private" and payload is None and payload_sha256 is None:
            raise ValueError("private events require a payload or payload digest")
        if isinstance(priority, bool) or not isinstance(priority, int):
            raise TypeError("priority must be an integer")
        self._queue.append(
            ScheduledEvent(
                kind=kind,
                source=source,
                visibility=visibility,
                priority=priority,
                order_index=self._next_order_index,
                payload=payload,
                payload_sha256=payload_sha256,
                depends_on=tuple(depends_on),
            )
        )
        self._next_order_index += 1

    def drain(self) -> tuple[ScheduledEvent, ...]:
        """Return every queued draft in dispatch order and empty the queue."""

        ordered = tuple(sorted(self._queue, key=lambda item: (item.priority, item.order_index)))
        self._queue = []
        return ordered

    def pending(self) -> int:
        """Return the number of queued drafts."""

        return len(self._queue)
