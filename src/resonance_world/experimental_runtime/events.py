"""Append-only world events with canonical digests and causal dependencies.

Every event is an immutable record. Its content digest covers every
hash-relevant field (sequence, tick, kind, source, visibility, payload
digest, and causal dependencies) so that any tampering with a persisted
event is detectable during replay.

Private events commit only to the digest of their payload. The payload
itself is withheld from the event and from every public log path; the
kernel keeps it in a sealed ledger that is persisted separately.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from resonance_world.adapters import canonical_json_bytes, sha256_json

EVENT_SOURCES = frozenset({"kernel", "agent", "external"})
EVENT_VISIBILITIES = frozenset({"public", "private"})

_HEX_DIGEST_CHARS = frozenset("0123456789abcdef")


def _validate_digest(value: str, name: str) -> None:
    if len(value) != 64 or any(char not in _HEX_DIGEST_CHARS for char in value):
        raise ValueError(f"{name} must be a lowercase 64-character hex digest")


def _validate_depends_on(seq: int, depends_on: tuple[int, ...]) -> None:
    previous = -1
    for dependency in depends_on:
        if isinstance(dependency, bool) or not isinstance(dependency, int):
            raise TypeError("depends_on entries must be integers")
        if dependency <= previous:
            raise ValueError("depends_on must be strictly increasing")
        if dependency < 0 or dependency >= seq:
            raise ValueError("depends_on entries must precede the event")
        previous = dependency


def event_digest(
    *,
    seq: int,
    tick: int,
    kind: str,
    source: str,
    visibility: str,
    payload_sha256: str,
    depends_on: tuple[int, ...],
) -> str:
    """Return the canonical content digest of an event record."""

    record = {
        "depends_on": list(depends_on),
        "kind": kind,
        "payload_sha256": payload_sha256,
        "seq": seq,
        "source": source,
        "tick": tick,
        "visibility": visibility,
    }
    return sha256_json(record)


@dataclass(frozen=True, slots=True)
class WorldEvent:
    """One immutable entry of the branch-local append-only event log.

    ``seq`` is the branch-local total order position; ``tick`` is the world
    time at which the event takes effect; ``depends_on`` names the events
    that causally precede this one.
    """

    seq: int
    tick: int
    kind: str
    source: str
    visibility: str
    payload: Mapping[str, Any] | None
    payload_sha256: str
    depends_on: tuple[int, ...]
    event_sha256: str

    @classmethod
    def create(
        cls,
        *,
        seq: int,
        tick: int,
        kind: str,
        source: str = "kernel",
        visibility: str = "public",
        payload: Mapping[str, Any] | None = None,
        payload_sha256: str | None = None,
        depends_on: tuple[int, ...] = (),
    ) -> WorldEvent:
        """Build and digest a validated event record.

        Public events carry an inline canonical payload (or a pre-committed
        digest for payload reconstructed at load time). Private events never
        carry an inline payload; callers must supply the payload digest so
        the public record can commit to content it does not reveal.
        """

        if isinstance(seq, bool) or not isinstance(seq, int) or seq < 0:
            raise ValueError("seq must be a non-negative integer")
        if isinstance(tick, bool) or not isinstance(tick, int) or tick < 0:
            raise ValueError("tick must be a non-negative integer")
        if not kind:
            raise ValueError("kind is required")
        if source not in EVENT_SOURCES:
            raise ValueError(f"source must be one of {sorted(EVENT_SOURCES)}")
        if visibility not in EVENT_VISIBILITIES:
            raise ValueError(f"visibility must be one of {sorted(EVENT_VISIBILITIES)}")

        depends_on_tuple = tuple(depends_on)
        _validate_depends_on(seq, depends_on_tuple)

        if visibility == "private":
            if payload is not None:
                raise ValueError("private events must not carry an inline payload")
            if payload_sha256 is None:
                raise ValueError("private events require a committed payload digest")
        else:
            if payload is None and payload_sha256 is None:
                raise ValueError("public events require a payload or payload digest")
            if payload is not None:
                computed = sha256_json(payload)
                if payload_sha256 is not None and payload_sha256 != computed:
                    raise ValueError("payload_sha256 does not match the payload")
                payload_sha256 = computed

        assert payload_sha256 is not None
        _validate_digest(payload_sha256, "payload_sha256")

        return cls(
            seq=seq,
            tick=tick,
            kind=kind,
            source=source,
            visibility=visibility,
            payload=payload,
            payload_sha256=payload_sha256,
            depends_on=depends_on_tuple,
            event_sha256=event_digest(
                seq=seq,
                tick=tick,
                kind=kind,
                source=source,
                visibility=visibility,
                payload_sha256=payload_sha256,
                depends_on=depends_on_tuple,
            ),
        )

    def redacted(self) -> WorldEvent:
        """Return an equivalent event with any inline payload withheld."""

        if self.payload is None:
            return self
        return WorldEvent(
            seq=self.seq,
            tick=self.tick,
            kind=self.kind,
            source=self.source,
            visibility=self.visibility,
            payload=None,
            payload_sha256=self.payload_sha256,
            depends_on=self.depends_on,
            event_sha256=self.event_sha256,
        )


def encoded_payload_bytes(payload: Mapping[str, Any]) -> bytes:
    """Return the canonical bytes of an event or private payload."""

    return canonical_json_bytes(payload)
