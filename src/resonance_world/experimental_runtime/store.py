"""SQLite persistence for the experimental world kernel.

The store keeps four append-only ledgers: branch registrations, the
branch-local event log, sealed private payloads, and checkpoints.
Nothing is ever updated or deleted through this module; conflicting
inserts fail closed.

Integrity rules:

- every hash-relevant field is canonical JSON and covered by an event
  or state digest, recomputed and compared on every read;
- private payloads live in a dedicated sealed table, are applied to
  state only through the reducer path, and never appear in the public
  event log;
- wall-clock provenance is stamped into dedicated ``recorded_at``
  columns that no digest ever covers.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from resonance_world.adapters import canonical_json_bytes, sha256_json

from .checkpoints import Checkpoint
from .events import WorldEvent, event_digest
from .state import WorldState, full_state_bytes, public_state_sha256

SCHEMA_VERSION = "world-kernel-store-v2"
COMMITMENT_SCHEME = "hmac-sha256-v1"


def commitment_digest(key: bytes, payload: Any) -> str:
    """Return a keyed commitment for a JSON payload.

    Bare SHA-256 lets an attacker verify guesses about low-entropy
    content directly from the published digest. A keyed HMAC commitment
    is only checkable by holders of the key, which must live outside
    the world file when confidentiality matters.
    """

    return commitment_digest_bytes(key, canonical_json_bytes(payload))


def commitment_digest_bytes(key: bytes, data: bytes) -> str:
    """Return a keyed commitment for raw bytes."""

    if not isinstance(key, bytes) or len(key) < 16 or len(key) > 64:
        raise ValueError("commitment key must be 16 to 64 bytes")
    return hmac.new(key, data, hashlib.sha256).hexdigest()


@dataclass(frozen=True, slots=True)
class BranchRecord:
    """Registration of one isolated branch and its genesis state."""

    branch_id: str
    genesis_state_sha256: str
    parent_branch_id: str | None = None
    fork_tick: int | None = None
    fork_event_count: int | None = None
    parent_state_sha256: str | None = None


def _default_wall_clock() -> str:
    return datetime.now(UTC).isoformat()


def _state_from_blob(blob: bytes) -> WorldState:
    raw = json.loads(bytes(blob).decode("utf-8"))
    return WorldState(
        scenario_id=raw["scenario_id"],
        tick=raw["tick"],
        event_count=raw["event_count"],
        public=raw["public"],
        private=raw["private"],
    )


def _event_from_row(row: sqlite3.Row) -> WorldEvent:
    payload_text = row["payload"]
    payload = json.loads(payload_text) if payload_text is not None else None
    depends_on = tuple(json.loads(row["depends_on"]))
    expected = event_digest(
        seq=row["seq"],
        tick=row["tick"],
        kind=row["kind"],
        source=row["source"],
        visibility=row["visibility"],
        payload_sha256=row["payload_sha256"],
        depends_on=depends_on,
    )
    if expected != row["event_sha256"]:
        raise ValueError(
            f"event digest mismatch at {row['branch_id']}#{row['seq']}: "
            "stored record does not match its committed content digest"
        )
    if row["visibility"] == "private" and payload is not None:
        raise ValueError(f"sealed event {row['seq']} leaked an inline payload")
    if payload is not None and sha256_json(payload) != row["payload_sha256"]:
        raise ValueError(f"payload digest mismatch at {row['branch_id']}#{row['seq']}")
    return WorldEvent(
        seq=row["seq"],
        tick=row["tick"],
        kind=row["kind"],
        source=row["source"],
        visibility=row["visibility"],
        payload=payload,
        payload_sha256=row["payload_sha256"],
        depends_on=depends_on,
        event_sha256=row["event_sha256"],
    )


class KernelStore:
    """Append-only SQLite persistence for one kernel world file.

    Confidentiality model: private payloads are sealed out of the public
    event log, and every digest that covers confidential content (sealed
    payload commitments, checkpoint and genesis state digests) is a keyed
    HMAC commitment under ``commitment_key``. The key is generated at
    store creation unless supplied. With ``persist_commitment_key=False``
    (the default) the key lives only in this process and must be
    custodied externally; with ``True`` it is stored in ``meta`` for
    convenience, which protects the log only against readers who do not
    have the world file.
    """

    def __init__(
        self,
        path: str | Path | None = None,
        *,
        wall_clock: Callable[[], str] | None = None,
        commitment_key: bytes | None = None,
        persist_commitment_key: bool = False,
    ) -> None:
        self._conn = sqlite3.connect(str(path) if path is not None else ":memory:")
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._wall_clock = wall_clock if wall_clock is not None else _default_wall_clock
        self._create_schema()
        self._reject_legacy_version()
        self._adopt_commitment_key(commitment_key, persist_commitment_key)

    def _reject_legacy_version(self) -> None:
        row = self._conn.execute(
            "SELECT value FROM meta WHERE key = 'schema_version'"
        ).fetchone()
        if row is not None and row["value"] != SCHEMA_VERSION:
            raise ValueError(
                f"world file uses store schema {row['value']!r}; this kernel "
                f"requires {SCHEMA_VERSION!r} (digest commitments changed)"
            )

    def _adopt_commitment_key(
        self, supplied: bytes | None, persist: bool
    ) -> None:
        row = self._conn.execute(
            "SELECT value FROM meta WHERE key = 'commitment_key'"
        ).fetchone()
        stored = bytes.fromhex(row["value"]) if row is not None else None
        if supplied is not None and stored is not None and supplied != stored:
            raise ValueError(
                "supplied commitment key does not match the key stored in this world file"
            )
        key = supplied if supplied is not None else stored
        if key is None:
            key = secrets.token_bytes(32)
        if not isinstance(key, bytes) or not 16 <= len(key) <= 64:
            raise ValueError("commitment key must be 16 to 64 bytes")
        self._commitment_key = key
        self._conn.execute(
            "INSERT OR IGNORE INTO meta(key, value) VALUES ('commitment_scheme', ?)",
            (COMMITMENT_SCHEME,),
        )
        if persist:
            self._conn.execute(
                "INSERT INTO meta(key, value) VALUES ('commitment_key', ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key.hex(),),
            )
        self._conn.commit()

    @property
    def commitment_key(self) -> bytes:
        """Return the commitment key for external custody by the operator."""

        return self._commitment_key

    def commit_payload(self, payload: Any) -> str:
        """Return the keyed commitment for a sealed payload."""

        return commitment_digest(self._commitment_key, payload)

    def commit_state(self, state: WorldState) -> str:
        """Return the keyed commitment for a complete state snapshot."""

        return commitment_digest_bytes(self._commitment_key, full_state_bytes(state))

    def _create_schema(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS branches (
                branch_id TEXT PRIMARY KEY,
                parent_branch_id TEXT,
                fork_tick INTEGER,
                fork_event_count INTEGER,
                parent_state_sha256 TEXT,
                genesis_state_sha256 TEXT NOT NULL,
                genesis_state_blob BLOB NOT NULL,
                registered_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS events (
                branch_id TEXT NOT NULL REFERENCES branches(branch_id),
                seq INTEGER NOT NULL,
                tick INTEGER NOT NULL,
                kind TEXT NOT NULL,
                source TEXT NOT NULL,
                visibility TEXT NOT NULL,
                depends_on TEXT NOT NULL,
                payload TEXT,
                payload_sha256 TEXT NOT NULL,
                event_sha256 TEXT NOT NULL,
                recorded_at TEXT NOT NULL,
                PRIMARY KEY (branch_id, seq)
            );
            CREATE TABLE IF NOT EXISTS sealed_payloads (
                branch_id TEXT NOT NULL REFERENCES branches(branch_id),
                seq INTEGER NOT NULL,
                payload TEXT NOT NULL,
                payload_sha256 TEXT NOT NULL,
                recorded_at TEXT NOT NULL,
                PRIMARY KEY (branch_id, seq)
            );
            CREATE TABLE IF NOT EXISTS checkpoints (
                branch_id TEXT NOT NULL REFERENCES branches(branch_id),
                name TEXT NOT NULL,
                tick INTEGER NOT NULL,
                event_count INTEGER NOT NULL,
                state_sha256 TEXT NOT NULL,
                public_state_sha256 TEXT NOT NULL,
                state_blob BLOB NOT NULL,
                recorded_at TEXT NOT NULL,
                PRIMARY KEY (branch_id, name)
            );
            """
        )
        self._conn.execute(
            "INSERT OR IGNORE INTO meta(key, value) VALUES ('schema_version', ?)",
            (SCHEMA_VERSION,),
        )
        self._conn.commit()

    # -- branches ---------------------------------------------------------

    def register_branch(self, record: BranchRecord, *, genesis_state: WorldState) -> None:
        """Register a branch with its genesis state snapshot."""

        genesis_blob = full_state_bytes(genesis_state)
        if self.commit_state(genesis_state) != record.genesis_state_sha256:
            raise ValueError("genesis_state_sha256 does not match the genesis state")
        try:
            self._conn.execute(
                """
                INSERT INTO branches (
                    branch_id, parent_branch_id, fork_tick, fork_event_count,
                    parent_state_sha256, genesis_state_sha256, genesis_state_blob,
                    registered_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.branch_id,
                    record.parent_branch_id,
                    record.fork_tick,
                    record.fork_event_count,
                    record.parent_state_sha256,
                    record.genesis_state_sha256,
                    genesis_blob,
                    self._wall_clock(),
                ),
            )
        except sqlite3.IntegrityError as error:
            raise ValueError(f"branch {record.branch_id!r} is already registered") from error
        self._conn.commit()

    def get_branch(self, branch_id: str) -> BranchRecord:
        """Return the registration record for ``branch_id``."""

        row = self._conn.execute(
            """
            SELECT branch_id, parent_branch_id, fork_tick, fork_event_count,
                   parent_state_sha256, genesis_state_sha256, genesis_state_blob
            FROM branches WHERE branch_id = ?
            """,
            (branch_id,),
        ).fetchone()
        if row is None:
            raise ValueError(f"unknown branch {branch_id!r}")
        return BranchRecord(
            branch_id=row["branch_id"],
            parent_branch_id=row["parent_branch_id"],
            fork_tick=row["fork_tick"],
            fork_event_count=row["fork_event_count"],
            parent_state_sha256=row["parent_state_sha256"],
            genesis_state_sha256=row["genesis_state_sha256"],
        )

    def list_branches(self) -> tuple[str, ...]:
        """Return all registered branch ids in registration order."""

        rows = self._conn.execute("SELECT branch_id FROM branches ORDER BY rowid").fetchall()
        return tuple(str(row["branch_id"]) for row in rows)

    def genesis_state(self, branch_id: str) -> WorldState:
        """Return the verified genesis state of ``branch_id``."""

        row = self._conn.execute(
            "SELECT genesis_state_sha256, genesis_state_blob FROM branches WHERE branch_id = ?",
            (branch_id,),
        ).fetchone()
        if row is None:
            raise ValueError(f"unknown branch {branch_id!r}")
        state = _state_from_blob(row["genesis_state_blob"])
        if self.commit_state(state) != row["genesis_state_sha256"]:
            raise ValueError(f"genesis state digest mismatch for branch {branch_id!r}")
        return state

    # -- events -----------------------------------------------------------

    def append_event(
        self,
        branch_id: str,
        event: WorldEvent,
        *,
        sealed_payload: Any = None,
    ) -> None:
        """Append one event, atomically with its sealed payload when private."""

        self.get_branch(branch_id)
        if event.visibility == "private":
            if sealed_payload is None:
                raise ValueError("private events require their sealed payload")
            if self.commit_payload(sealed_payload) != event.payload_sha256:
                raise ValueError("sealed payload does not match the committed digest")
        recorded_at = self._wall_clock()
        try:
            self._conn.execute(
                """
                INSERT INTO events (
                    branch_id, seq, tick, kind, source, visibility, depends_on,
                    payload, payload_sha256, event_sha256, recorded_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    branch_id,
                    event.seq,
                    event.tick,
                    event.kind,
                    event.source,
                    event.visibility,
                    canonical_json_bytes(list(event.depends_on)).decode("utf-8"),
                    None
                    if event.payload is None
                    else canonical_json_bytes(event.payload).decode("utf-8"),
                    event.payload_sha256,
                    event.event_sha256,
                    recorded_at,
                ),
            )
            if event.visibility == "private":
                self._conn.execute(
                    """
                    INSERT INTO sealed_payloads (
                        branch_id, seq, payload, payload_sha256, recorded_at
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        branch_id,
                        event.seq,
                        canonical_json_bytes(sealed_payload).decode("utf-8"),
                        event.payload_sha256,
                        recorded_at,
                    ),
                )
        except sqlite3.IntegrityError as error:
            raise ValueError(
                f"event {event.seq} cannot be appended to branch {branch_id!r}: "
                "the log is append-only"
            ) from error
        self._conn.commit()

    def iter_events(self, branch_id: str) -> tuple[WorldEvent, ...]:
        """Return the verified branch log in sequence order."""

        self.get_branch(branch_id)
        rows = self._conn.execute(
            "SELECT * FROM events WHERE branch_id = ? ORDER BY seq",
            (branch_id,),
        ).fetchall()
        return tuple(_event_from_row(row) for row in rows)

    def public_events(self, branch_id: str, *, since_seq: int = -1) -> tuple[WorldEvent, ...]:
        """Return verified public events with ``seq > since_seq``."""

        return tuple(
            event
            for event in self.iter_events(branch_id)
            if event.visibility == "public" and event.seq > since_seq
        )

    def event_count(self, branch_id: str) -> int:
        """Return the number of recorded events on ``branch_id``."""

        row = self._conn.execute(
            "SELECT COUNT(*) AS count FROM events WHERE branch_id = ?",
            (branch_id,),
        ).fetchone()
        return int(row["count"])

    def sealed_payload(self, branch_id: str, seq: int) -> Any:
        """Return one verified sealed payload."""

        row = self._conn.execute(
            "SELECT payload, payload_sha256 FROM sealed_payloads WHERE branch_id = ? AND seq = ?",
            (branch_id, seq),
        ).fetchone()
        if row is None:
            raise ValueError(f"no sealed payload recorded for {branch_id}#{seq}")
        payload = json.loads(row["payload"])
        if self.commit_payload(payload) != row["payload_sha256"]:
            raise ValueError(f"sealed payload digest mismatch at {branch_id}#{seq}")
        return payload

    def sealed_payloads(self, branch_id: str) -> dict[int, Any]:
        """Return all verified sealed payloads for ``branch_id`` keyed by seq."""

        rows = self._conn.execute(
            "SELECT seq, payload, payload_sha256 FROM sealed_payloads "
            "WHERE branch_id = ? ORDER BY seq",
            (branch_id,),
        ).fetchall()
        payloads: dict[int, Any] = {}
        for row in rows:
            payload = json.loads(row["payload"])
            if self.commit_payload(payload) != row["payload_sha256"]:
                raise ValueError(f"sealed payload digest mismatch at {branch_id}#{row['seq']}")
            payloads[int(row["seq"])] = payload
        return payloads

    # -- checkpoints ------------------------------------------------------

    def save_checkpoint(self, checkpoint: Checkpoint) -> None:
        """Persist one verified checkpoint snapshot."""

        blob = full_state_bytes(checkpoint.state)
        if self.commit_state(checkpoint.state) != checkpoint.state_sha256:
            raise ValueError("checkpoint state_sha256 does not match its state")
        if public_state_sha256(checkpoint.state) != checkpoint.public_state_sha256:
            raise ValueError("checkpoint public_state_sha256 does not match its state")
        try:
            self._conn.execute(
                """
                INSERT INTO checkpoints (
                    branch_id, name, tick, event_count, state_sha256,
                    public_state_sha256, state_blob, recorded_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    checkpoint.branch_id,
                    checkpoint.name,
                    checkpoint.tick,
                    checkpoint.event_count,
                    checkpoint.state_sha256,
                    checkpoint.public_state_sha256,
                    blob,
                    self._wall_clock(),
                ),
            )
        except sqlite3.IntegrityError as error:
            raise ValueError(
                f"checkpoint {checkpoint.name!r} already exists on {checkpoint.branch_id!r}"
            ) from error
        self._conn.commit()

    def load_checkpoint(self, branch_id: str, name: str) -> Checkpoint:
        """Load and verify one checkpoint snapshot."""

        row = self._conn.execute(
            """
            SELECT branch_id, name, tick, event_count, state_sha256,
                   public_state_sha256, state_blob
            FROM checkpoints WHERE branch_id = ? AND name = ?
            """,
            (branch_id, name),
        ).fetchone()
        if row is None:
            raise ValueError(f"no checkpoint {name!r} on branch {branch_id!r}")
        # Raw-blob integrity first (rejects non-JSON tampering before parsing),
        # then canonical-form proof that the parsed state matches the digest.
        if commitment_digest_bytes(self._commitment_key, row["state_blob"]) != row["state_sha256"]:
            raise ValueError(f"checkpoint {name!r} failed its stored-digest verification")
        state = _state_from_blob(row["state_blob"])
        if self.commit_state(state) != row["state_sha256"]:
            raise ValueError(f"checkpoint {name!r} state does not match its digest")
        if public_state_sha256(state) != row["public_state_sha256"]:
            raise ValueError(f"checkpoint {name!r} public projection does not match its digest")
        return Checkpoint(
            branch_id=row["branch_id"],
            name=row["name"],
            tick=row["tick"],
            event_count=row["event_count"],
            state_sha256=row["state_sha256"],
            public_state_sha256=row["public_state_sha256"],
            state=state,
        )

    def list_checkpoints(self, branch_id: str) -> tuple[str, ...]:
        """Return checkpoint names for ``branch_id`` in creation order."""

        rows = self._conn.execute(
            "SELECT name FROM checkpoints WHERE branch_id = ? ORDER BY rowid",
            (branch_id,),
        ).fetchall()
        return tuple(str(row["name"]) for row in rows)

    def checkpoints_by_event_count(self, branch_id: str) -> dict[int, Checkpoint]:
        """Return verified checkpoints keyed by their event watermark."""

        rows = self._conn.execute(
            "SELECT name FROM checkpoints WHERE branch_id = ? ORDER BY rowid",
            (branch_id,),
        ).fetchall()
        by_count: dict[int, Checkpoint] = {}
        for row in rows:
            checkpoint = self.load_checkpoint(branch_id, str(row["name"]))
            by_count[checkpoint.event_count] = checkpoint
        return by_count

    def close(self) -> None:
        """Close the underlying connection."""

        self._conn.close()
