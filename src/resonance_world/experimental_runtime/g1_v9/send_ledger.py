"""Persistent, crash-safe, cross-process send ledger for the qualification.

Durable accounting for the 8-attempt qualification cap:

- every send attempt is appended to a JSONL ledger **before** the HTTP
  call, so a timeout or crash counts against the cap (an attempt with
  an unknown outcome is consumed, never retried automatically);
- entries are hash-chained, so any edit or deletion of recorded history
  is detectable on reload;
- a truncated final line (crash mid-write) is repaired conservatively:
  the file is rebuilt from the verified good prefix through a temporary
  file and an **atomic rename**, and one ``unknown-outcome`` consumed
  attempt is appended. Repeated crashes accumulate consumption - the
  consumed balance never shrinks;
- **cross-process exclusion**: every mutation happens while holding an
  exclusive lock file (O_CREAT|O_EXCL), and the on-disk state is
  re-read **under the lock** before the cap decision - two concurrent
  processes can never both consume a final slot;
- the ledger is **bound to one authorization id**: a file written for
  a different authorization (or cap) is rejected at load time, and the
  canonical ledger path is derived from that id so a second file
  cannot start a fresh balance.

The ledger records attempts and outcomes only: no credentials, no
response bodies, no endpoint URLs.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

LEDGER_SCHEMA = "g1-v9-send-ledger-v2"

_ACTION_ATTEMPT = "attempt"
_ACTION_UNKNOWN_OUTCOME = "unknown-outcome"
_ACTIONS_WITH_OUTCOME = (
    "succeeded",
    "auth-failure",
    "timeout",
    "malformed-response",
    "http-error",
    _ACTION_UNKNOWN_OUTCOME,
)
_GENESIS_PREV = "0" * 64
_LOCK_TIMEOUT_SECONDS = 10.0


class LedgerCorrupted(RuntimeError):
    """Raised when the ledger fails validation on load."""


class LedgerLocked(RuntimeError):
    """Raised when another process holds the ledger lock too long."""


class LedgerCrashInjected(RuntimeError):
    """Test-only interruption raised at a named repair stage."""


class PhysicalSendCapExceeded(RuntimeError):
    """Raised when a send is refused because the cap is exhausted."""


def _entry_digest(entry: dict[str, Any]) -> str:
    material = {key: value for key, value in entry.items() if key != "hash"}
    return hashlib.sha256(
        json.dumps(material, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _is_authorization_id(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(char in "0123456789abcdef" for char in value)
    )


def qualification_ledger_path(
    base_dir: str | Path, authorization_id: str
) -> Path:
    """Return the ONE canonical ledger path for an authorization id.

    A balance for an authorization lives in exactly this file; creating
    a differently named file cannot start a second balance for the same
    authorization because the transport requires the canonical path.
    """

    return Path(base_dir) / f"send-ledger-{authorization_id}.jsonl"


class _ExclusiveLock:
    """A small O_CREAT|O_EXCL lock file with a bounded wait."""

    def __init__(self, lock_path: Path) -> None:
        self._path = lock_path
        self._fd: int | None = None

    def __enter__(self) -> _ExclusiveLock:
        deadline = time.monotonic() + _LOCK_TIMEOUT_SECONDS
        while True:
            try:
                self._fd = os.open(
                    str(self._path), os.O_CREAT | os.O_EXCL | os.O_WRONLY
                )
                os.write(self._fd, str(os.getpid()).encode())
                return self
            except FileExistsError:
                if time.monotonic() >= deadline:
                    raise LedgerLocked(
                        f"ledger lock held by another process: {self._path}"
                    ) from None
                time.sleep(0.02)

    def __exit__(self, *exc) -> None:
        if self._fd is not None:
            os.close(self._fd)
            self._fd = None
        try:
            os.unlink(str(self._path))
        except FileNotFoundError:
            pass


class PersistentSendLedger:
    """Append-only, hash-chained, cross-process, cap-enforcing ledger."""

    def __init__(
        self,
        path: str | Path,
        *,
        send_cap: int,
        authorization_id: str,
    ) -> None:
        if isinstance(send_cap, bool) or not isinstance(send_cap, int) or send_cap <= 0:
            raise ValueError("send_cap must be a positive integer")
        if not _is_authorization_id(authorization_id):
            raise ValueError(
                "authorization_id must be a 64-hex digest binding this "
                "balance to one authorization"
            )
        self._path = Path(path)
        self._lock_path = self._path.with_suffix(self._path.suffix + ".lock")
        self._send_cap = send_cap
        self._authorization_id = authorization_id
        self._entries: list[dict[str, Any]] = []
        self._repair_consumed = 0
        #: Test-only interruption injection for the repair sequence.
        self.crash_point: str | None = None
        self._load()
        self._ensure_header()

    # -- locking ----------------------------------------------------------

    def _locked(self) -> _ExclusiveLock:
        """Acquire the exclusive cross-process lock (context manager)."""

        return _ExclusiveLock(self._lock_path)

    # -- loading and repair -----------------------------------------------

    def _load(self) -> None:
        self._entries = []
        self._repair_consumed = 0
        if not self._path.exists():
            return
        with self._locked():
            self._load_locked()

    def _ensure_header(self) -> None:
        """Create the authorization header when the ledger is brand new."""

        with self._locked():
            needs_header = (
                not self._path.exists() or self._path.stat().st_size == 0
            )
            if not needs_header:
                return
            with self._path.open("w", encoding="utf-8") as handle:
                handle.write(self._header_line() + "\n")
                handle.flush()
                os.fsync(handle.fileno())
            self._load_locked()

    def _load_locked(self) -> None:
        self._entries = []
        self._repair_consumed = 0
        if not self._path.exists():
            return
        raw = self._path.read_text(encoding="utf-8")
        lines = [line for line in raw.splitlines() if line.strip()]
        if not lines:
            return
        header = json.loads(lines[0])
        if header.get("type") != "header":
            raise LedgerCorrupted("ledger is missing its authorization header")
        if header.get("authorization_id") != self._authorization_id:
            raise LedgerCorrupted("ledger belongs to a different authorization id")
        if header.get("send_cap") != self._send_cap:
            raise LedgerCorrupted("ledger send cap differs from the bound cap")

        previous_hash = header.get("genesis", _GENESIS_PREV)
        consumed = 0
        content_lines = lines[1:]
        for position, line in enumerate(content_lines, start=1):
            try:
                entry = json.loads(line)
            except json.JSONDecodeError as error:
                if position == len(content_lines):
                    # Crash mid-write on the final line: everything before
                    # it is already verified - repair conservatively.
                    self._repair_truncated_tail_locked(
                        list(self._entries), previous_hash, line
                    )
                    return
                raise LedgerCorrupted(
                    f"ledger line {position + 1} is corrupt and not a final "
                    "write"
                ) from error
            if entry.get("prev") != previous_hash:
                raise LedgerCorrupted(
                    f"ledger hash-chain broken at entry {position + 1}"
                )
            if entry.get("hash") != _entry_digest(entry):
                raise LedgerCorrupted(
                    f"ledger entry digest mismatch at entry {position + 1}"
                )
            if entry.get("action") == _ACTION_UNKNOWN_OUTCOME and entry.get(
                "consumes_attempt"
            ):
                consumed += 1
            previous_hash = entry["hash"]
            self._entries.append(entry)
        self._repair_consumed = consumed

    def _repair_truncated_tail_locked(
        self,
        good_entries: list[dict[str, Any]],
        previous_hash: str,
        corrupt_line: str,
    ) -> None:
        """Rebuild the ledger from the verified good prefix plus one
        conservative ``unknown-outcome`` consumed attempt, written to a
        temporary file and installed with an **atomic rename** so an
        interrupted repair can never shrink the consumed balance. The
        repair is idempotent: if interrupted before the rename, the
        original file remains and the next load repairs it again."""

        corrupt_digest = hashlib.sha256(corrupt_line.encode("utf-8")).hexdigest()
        last_good_hash = (
            good_entries[-1]["hash"] if good_entries else _GENESIS_PREV
        )
        repair = {
            "seq": len(good_entries) + 1,
            "action": "unknown-outcome",
            "consumes_attempt": True,
            "label": "truncated-final-write",
            "payload_sha256": corrupt_digest,
            "ts": _now(),
        }
        repair["prev"] = last_good_hash
        repair["hash"] = _entry_digest(repair)

        temp_path = self._path.with_suffix(self._path.suffix + ".repair-tmp")
        with temp_path.open("w", encoding="utf-8") as handle:
            handle.write(self._header_line() + "\n")
            for entry in good_entries:
                handle.write(
                    json.dumps(entry, sort_keys=True, separators=(",", ":")) + "\n"
                )
            handle.write(
                json.dumps(repair, sort_keys=True, separators=(",", ":")) + "\n"
            )
            handle.flush()
            os.fsync(handle.fileno())

        if self.crash_point == "repair:after-temp-fsync":
            raise LedgerCrashInjected("interrupted after temp fsync")

        os.replace(temp_path, self._path)

        if self.crash_point == "repair:after-replace":
            raise LedgerCrashInjected("interrupted after atomic replace")

        # Best-effort directory fsync so the rename survives a power loss.
        try:
            dir_fd = os.open(str(self._path.parent), os.O_RDONLY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
        except OSError:
            pass
        self._entries = good_entries + [repair]
        # Cumulative: prior crash-repairs inside the good prefix are kept.
        self._repair_consumed = self._count_consumed(self._entries)

    def _header_line(self) -> str:
        return json.dumps(
            {
                "type": "header",
                "schema": LEDGER_SCHEMA,
                "authorization_id": self._authorization_id,
                "send_cap": self._send_cap,
            },
            sort_keys=True,
            separators=(",", ":"),
        )

    # -- introspection ----------------------------------------------------

    def refresh(self) -> None:
        """Re-read the on-disk state under the lock."""

        with self._locked():
            self._load_locked()

    @property
    def authorization_id(self) -> str:
        return self._authorization_id

    @property
    def path(self) -> Path:
        return self._path

    @property
    def send_cap(self) -> int:
        return self._send_cap

    @property
    def truncated_tail(self) -> bool:
        return self._repair_consumed > 0

    @staticmethod
    def _count_consumed(entries: list[dict[str, Any]]) -> int:
        """Count unknown-outcome entries that consume an attempt slot."""

        return sum(
            1
            for entry in entries
            if entry.get("action") == "unknown-outcome"
            and entry.get("consumes_attempt")
        )

    def attempts(self) -> int:
        """Consumed attempts: recorded attempts + crash-repair consumption."""

        return (
            sum(1 for entry in self._entries if entry["action"] == "attempt")
            + self._count_consumed(self._entries)
        )

    def remaining(self) -> int:
        return max(0, self._send_cap - self.attempts())

    def outcomes(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for entry in self._entries:
            if entry["action"] in (
                "succeeded",
                "auth-failure",
                "timeout",
                "malformed-response",
                "http-error",
                "unknown-outcome",
            ):
                counts[entry["action"]] = counts.get(entry["action"], 0) + 1
        return counts

    # -- mutation (always under the cross-process lock) -------------------

    def record_attempt(self, label: str, payload_sha256: str) -> None:
        """Consume one attempt slot, atomically across processes.

        The on-disk state is re-read under the lock before the cap
        decision, so two concurrent processes can never both consume a
        final slot, and a restart cannot restore a consumed balance.
        """

        with self._locked():
            self._load_locked()
            if self.attempts() >= self._send_cap:
                raise PhysicalSendCapExceeded(
                    f"send cap exhausted ({self.attempts()}/{self._send_cap} "
                    "attempts consumed); refusing further sends"
                )
            self._append_locked(
                {
                    "seq": len(self._entries) + 1,
                    "action": "attempt",
                    "label": label,
                    "payload_sha256": payload_sha256,
                    "ts": _now(),
                }
            )

    def record_outcome(
        self, label: str, payload_sha256: str, outcome: str
    ) -> None:
        if outcome not in (
            "succeeded",
            "auth-failure",
            "timeout",
            "malformed-response",
            "http-error",
            "unknown-outcome",
        ):
            raise ValueError(f"unknown outcome {outcome!r}")
        with self._locked():
            self._load_locked()
            self._append_locked(
                {
                    "seq": len(self._entries) + 1,
                    "action": outcome,
                    "label": label,
                    "payload_sha256": payload_sha256,
                    "ts": _now(),
                }
            )

    def _append_locked(self, entry: dict[str, Any]) -> None:
        previous_hash = (
            self._entries[-1]["hash"] if self._entries else _GENESIS_PREV
        )
        entry["prev"] = previous_hash
        entry["hash"] = _entry_digest(entry)
        line = json.dumps(entry, sort_keys=True, separators=(",", ":"))
        with self._path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        self._entries.append(entry)
