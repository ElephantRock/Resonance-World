"""Causal world time for the experimental world kernel.

World time is an integer tick counter owned by the kernel. It is fully
decoupled from wall-clock time: advancing world time performs pure state
work and never sleeps, and no wall-clock reading may enter world state,
event payloads, or any digest. Wall-clock provenance, when a persistence
store records it, lives only in dedicated store columns outside the
digest path.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True, order=True)
class WorldClock:
    """An immutable causal world-time instant measured in ticks."""

    tick: int = 0

    def __post_init__(self) -> None:
        if isinstance(self.tick, bool) or not isinstance(self.tick, int):
            raise TypeError("tick must be an integer")
        if self.tick < 0:
            raise ValueError("tick must be non-negative")

    def advance(self, ticks: int = 1) -> WorldClock:
        """Return the clock moved forward by ``ticks`` ticks.

        This is a pure computation on integers. It performs no sleeping and
        reads no clock, so any number of ticks costs the same regardless of
        the wall-clock duration the represented world time would "take".
        """

        if isinstance(ticks, bool) or not isinstance(ticks, int):
            raise TypeError("ticks must be an integer")
        if ticks <= 0:
            raise ValueError("ticks must be positive")
        return WorldClock(self.tick + ticks)
