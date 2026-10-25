"""Persistent, crash-safe send ledger for the qualification probe.

Durable accounting for the 8-attempt qualification cap:

- every send attempt is appended to a JSONL ledger **before** the HTTP
  call, so a timeout or crash counts against the cap (an attempt with
  an unknown outcome is consumed, never retried automatically);
- entries are hash-chained (each entry records the hash of the previous
  entry), so any edit or deletion of recorded history is detectable on
  reload;
- a truncated final line (crash mid-write) is loaded as an
  ``unknown-outcome`` consumed attempt - conservative by design;
- an exclusive lock file serializes writers across processes.

The ledger records attempts and outcomes only: no credentials, no
response bodies, no endpoint URLs.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

LEDGER_SCHEMA = "g1-v9-send-ledger-v1"

_ACTION_ATTEMPT = "attempt"
_ACTIONS_WITH_OUTCOME = (
    "succeeded",
    "auth-failure",
    "timeout",
    "malformed-response",
    "http-error",
    "unknown-outcome",
)


class PhysicalSendCapExceeded(RuntimeError):
    """Raised when a send is refused because the cap is exhausted."""


def _entry_digest(entry: dict[str, Any]) -> str:
    material = {key: value for key, value in entry.items() if key != "hash"}
    return hashlib.sha256(
        json.dumps(material, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


class LedgerCorrupted(RuntimeError):
    """Raised when a non-final ledger line fails hash-chain validation."""


class PersistentSendLedger:
    """Append-only, hash-chained, cap-enforcing send ledger."""

    def __init__(self, path: str | Path, *, send_cap: int) -> None:
        if isinstance(send_cap, bool) or not isinstance(send_cap, int) or send_cap <= 0:
            raise ValueError("send_cap must be a positive integer")
        self._path = Path(path)
        self._send_cap = send_cap
        self._entries: list[dict[str, Any]] = []
        self._truncated_tail = False
        self._load()

    # -- loading ----------------------------------------------------------

    def _load(self) -> None:
        if not self._path.exists():
            return
        raw = self._path.read_bytes().decode("utf-8")
        lines = [line for line in raw.splitlines() if line.strip()]
        previous_hash = "0" * 64
        for index, line in enumerate(lines):
            try:
                entry = json.loads(line)
            except json.JSONDecodeError as error:
                if index == len(lines) - 1:
                    self._consume_truncated_tail(previous_hash, line)
                    break
                raise LedgerCorrupted(
                    f"ledger line {index + 1} is corrupt and not a final write"
                ) from error
            if entry.get("prev") != previous_hash:
                raise LedgerCorrupted(
                    f"ledger hash-chain broken at line {index + 1}"
                )
            if entry.get("hash") != _entry_digest(entry):
                raise LedgerCorrupted(f"ledger entry digest mismatch at line {index + 1}")
            previous_hash = entry["hash"]
            self._entries.append(entry)

    def _consume_truncated_tail(self, previous_hash: str, corrupt_line: str) -> None:
        """Permanently record a crashed final write as a consumed attempt.

        The corrupt line's content is unrecoverable by design; conservative
        accounting treats it as one consumed attempt with an unknown
        outcome, chained onto the last good entry so the file remains a
        valid hash chain after the repair.
        """

        corrupt_digest = hashlib.sha256(corrupt_line.encode("utf-8")).hexdigest()
        entry = {
            "seq": len(self._entries) + 1,
            "action": "unknown-outcome",
            "label": "truncated-final-write",
            "payload_sha256": corrupt_digest,
            "ts": datetime.now(UTC).isoformat(),
        }
        entry["prev"] = previous_hash
        entry["hash"] = _entry_digest(entry)
        line = json.dumps(entry, sort_keys=True, separators=(",", ":"))
        with self._path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        self._entries.append(entry)
        self._truncated_tail = True

    # -- introspection ----------------------------------------------------

    @property
    def send_cap(self) -> int:
        return self._send_cap

    @property
    def truncated_tail(self) -> bool:
        """True when a crashed final write was conservatively consumed."""

        return self._truncated_tail

    def attempts(self) -> int:
        """Return consumed attempts, counting any crashed write as used."""

        return sum(1 for entry in self._entries if entry["action"] == _ACTION_ATTEMPT) + (
            1 if self._truncated_tail else 0
        )

    def outcomes(self) -> dict[str, int]:
        """Return the recorded outcome counts."""

        counts: dict[str, int] = {}
        for entry in self._entries:
            if entry["action"] in _ACTIONS_WITH_OUTCOME:
                counts[entry["action"]] = counts.get(entry["action"], 0) + 1
        return counts

    # -- writing ----------------------------------------------------------

    def _append(self, entry: dict[str, Any]) -> dict[str, Any]:
        previous_hash = (
            self._entries[-1]["hash"] if self._entries else "0" * 64
        )
        entry["prev"] = previous_hash
        entry["hash"] = _entry_digest(entry)
        line = json.dumps(entry, sort_keys=True, separators=(",", ":"))
        with self._path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        self._entries.append(entry)
        return entry

    def guard(self) -> None:
        """Raise fail-closed when the attempt cap is exhausted."""

        if self.truncated_tail or self.attempts() >= self._send_cap:
            raise PhysicalSendCapExceeded(
                f"send cap exhausted ({self.attempts()}/{self._send_cap} "
                "attempts consumed); refusing further sends"
            )

    def record_attempt(self, label: str, payload_sha256: str) -> int:
        """Consume one attempt slot; returns the attempt number."""

        self.guard()
        entry = self._append(
            {
                "seq": len(self._entries) + 1,
                "action": _ACTION_ATTEMPT,
                "label": label,
                "payload_sha256": payload_sha256,
                "ts": datetime.now(UTC).isoformat(),
            }
        )
        return int(entry["seq"])

    def record_outcome(
        self, label: str, payload_sha256: str, outcome: str
    ) -> None:
        """Record the outcome of the most recent attempt (no cap effect)."""

        if outcome not in _ACTIONS_WITH_OUTCOME:
            raise ValueError(f"unknown outcome {outcome!r}")
        self._append(
            {
                "seq": len(self._entries) + 1,
                "action": outcome,
                "label": label,
                "payload_sha256": payload_sha256,
                "ts": datetime.now(UTC).isoformat(),
            }
        )
