"""Host-local, process-restart-safe C3R calibration reservation budget.

One Linux filesystem, one preexisting private 0700 directory, one 0600 file,
fcntl.flock and fsync. This is NOT a vendor-side spending limit, independent
receipt, multi-host lock, crash recovery mechanism or tamperproof custody.

No network, credentials, provider SDK, automatic reset or refund exists here.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import stat
from pathlib import Path
from typing import Any

from .c3r_g1_zai_transport import CODING_ENDPOINT, STANDARD_ENDPOINT

MAX_FILE_BYTES = 16 * 1024
ZERO = "0" * 64
MAX_CAMPAIGN_SENDS = 8


class CampaignBudgetRejected(RuntimeError):
    """Fail closed before attempting a provider send."""


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha(value: object) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _digest(value: object) -> bool:
    return type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _validate_args(
    *, campaign_id: str, endpoint: str, planned_digests: tuple[str, ...],
    maximum: int,
) -> None:
    if (type(campaign_id) is not str
            or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{7,79}", campaign_id) is None
            or endpoint not in (STANDARD_ENDPOINT, CODING_ENDPOINT)
            or type(maximum) is not int or not 1 <= maximum <= MAX_CAMPAIGN_SENDS
            or type(planned_digests) is not tuple or len(planned_digests) != 8
            or any(not _digest(x) for x in planned_digests)):
        raise ValueError("invalid prospectively locked host campaign parameters")


def _secure_file(path: Path) -> None:
    if not path.is_absolute() or path.is_symlink():
        raise CampaignBudgetRejected("budget must have an absolute nonsymlink path")
    try:
        parent = path.parent.stat()
    except OSError as exc:
        raise CampaignBudgetRejected("host budget parent is unavailable") from exc
    if (not stat.S_ISDIR(parent.st_mode)
            or parent.st_uid != os.geteuid()
            or parent.st_mode & 0o077):
        raise CampaignBudgetRejected("host budget directory must be owned/private")


def _validate_fd(path: Path, fd: int) -> None:
    record = os.fstat(fd)
    actual = path.lstat()
    if (not stat.S_ISREG(record.st_mode) or record.st_nlink != 1
            or (record.st_mode & 0o777) != 0o600
            or record.st_uid != os.geteuid()
            or (actual.st_dev, actual.st_ino) != (record.st_dev, record.st_ino)
            or record.st_size > MAX_FILE_BYTES):
        raise CampaignBudgetRejected("host budget file identity or mode violated")


def _read(fd: int) -> dict[str, Any]:
    os.lseek(fd, 0, os.SEEK_SET)
    payload = os.read(fd, MAX_FILE_BYTES + 1)
    if len(payload) > MAX_FILE_BYTES:
        raise CampaignBudgetRejected("host budget file too large")
    try:
        obj = json.loads(payload)
    except (ValueError, UnicodeError) as exc:
        raise CampaignBudgetRejected("host budget file corrupted") from exc
    if not isinstance(obj, dict):
        raise CampaignBudgetRejected("host budget must contain a JSON object")
    return obj


def _write(fd: int, record: dict[str, Any]) -> None:
    encoded = _canonical(record) + b"\n"
    if len(encoded) > MAX_FILE_BYTES:
        raise CampaignBudgetRejected("host budget state exceeds size limit")
    os.lseek(fd, 0, os.SEEK_SET)
    remaining = memoryview(encoded)
    while remaining:
        n = os.write(fd, remaining)
        if n <= 0:
            raise CampaignBudgetRejected("host budget write incomplete")
        remaining = remaining[n:]
    os.ftruncate(fd, len(encoded))
    os.fsync(fd)


class HostCampaignBudget:
    """A shared *host-local* pre-dispatch reservation register, not global spend."""

    def __init__(
        self, path: Path, *, campaign_id: str, endpoint: str,
        planned_digests: tuple[str, ...], maximum: int,
    ) -> None:
        _validate_args(
            campaign_id=campaign_id, endpoint=endpoint,
            planned_digests=planned_digests, maximum=maximum,
        )
        _secure_file(path)
        self.path = path
        self.campaign_id = campaign_id
        self.endpoint = endpoint
        self.maximum = maximum
        self.planned_digests = planned_digests
        self._expected_header = {
            "schema": "c3r-host-calibration-budget-v0.1",
            "campaign_id": campaign_id,
            "endpoint": endpoint,
            "maximum": maximum,
            "planned_request_digests": list(planned_digests),
        }

    def initialize(self) -> None:
        """Operator creates once. Repeated initialization NEVER resets quota."""
        flags = os.O_CREAT | os.O_EXCL | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0)
        fd = os.open(self.path, flags, 0o600)
        try:
            _validate_fd(self.path, fd)
            _write(fd, {**self._expected_header, "reservations": []})
            directory_fd = os.open(
                self.path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
            )
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        finally:
            os.close(fd)

    def _validated_state(self, value: dict[str, Any]) -> list[dict[str, Any]]:
        if (set(value) != set(self._expected_header) | {"reservations"}
                or any(value.get(k) != v for k, v in self._expected_header.items())):
            raise CampaignBudgetRejected("host campaign lock/header changed")
        entries = value.get("reservations")
        if not isinstance(entries, list) or len(entries) > self.maximum:
            raise CampaignBudgetRejected("host campaign send count invalid")
        prior = ZERO
        for i, entry in enumerate(entries):
            if (not isinstance(entry, dict)
                    or set(entry) != {
                        "ordinal", "request_sha256", "endpoint", "previous_sha256",
                        "entry_sha256",
                    }):
                raise CampaignBudgetRejected("malformed host reservation")
            expected = {
                "ordinal": i + 1,
                "request_sha256": self.planned_digests[i],
                "endpoint": self.endpoint,
                "previous_sha256": prior,
            }
            if any(entry.get(k) != v for k, v in expected.items()):
                raise CampaignBudgetRejected("host campaign request sequence mismatch")
            if entry.get("entry_sha256") != _sha({
                "campaign_id": self.campaign_id, **expected
            }):
                raise CampaignBudgetRejected("host reservation digest mismatch")
            prior = _sha(entry)
        return entries

    def inspect(self) -> dict[str, object]:
        """Reads a fully checked snapshot without releasing or resetting slots."""
        _secure_file(self.path)
        fd = os.open(
            self.path, os.O_RDWR | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_CLOEXEC", 0),
        )
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            _validate_fd(self.path, fd)
            record = _read(fd)
            entries = self._validated_state(record)
            return {
                "schema": "c3r-host-budget-check-v0.1",
                "campaign_id": self.campaign_id,
                "endpoint": self.endpoint,
                "maximum": self.maximum,
                "reserved": len(entries),
                "remaining": self.maximum - len(entries),
                "last_hash": _sha(entries[-1]) if entries else ZERO,
                "provider_sends_authenticated": False,
                "provider_billing_verified": False,
                "scientific_acceptance": False,
            }
        finally:
            os.close(fd)

    def reserve(self, *, request_digest: str, endpoint: str) -> int:
        """Reserve and fsync BEFORE dispatch; failures burn slots, no refunds."""
        if not _digest(request_digest) or endpoint != self.endpoint:
            raise CampaignBudgetRejected("unregistered provider body or endpoint")
        _secure_file(self.path)
        fd = os.open(
            self.path, os.O_RDWR | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_CLOEXEC", 0),
        )
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            _validate_fd(self.path, fd)
            record = _read(fd)
            entries = self._validated_state(record)
            index = len(entries)
            if index >= self.maximum:
                raise CampaignBudgetRejected("persistent campaign request cap exhausted")
            if request_digest != self.planned_digests[index]:
                raise CampaignBudgetRejected("next provider request differs from campaign lock")
            expected = {
                "ordinal": index + 1,
                "request_sha256": request_digest,
                "endpoint": endpoint,
                "previous_sha256": _sha(entries[-1]) if entries else ZERO,
            }
            entries.append({
                **expected, "entry_sha256": _sha({
                    "campaign_id": self.campaign_id, **expected
                }),
            })
            _write(fd, record)
            return index + 1
        finally:
            os.close(fd)



def main(argv: list[str] | None = None) -> int:
    """Offline create/inspect only. Never opens a network connection or spends."""
    from .c3r_g1_calibration_audit import _request_digest
    from .c3r_g1_multischema_calibration import make_calibration_plan

    parser = argparse.ArgumentParser(
        description="Prepare or inspect host-local G1 provider-call reservation cap"
    )
    parser.add_argument("operation", choices=("initialize", "inspect"))
    parser.add_argument("--path", required=True, type=Path)
    parser.add_argument("--campaign-id", required=True)
    parser.add_argument("--route", choices=("coding", "standard"), required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--max-tokens", type=int, required=True)
    parser.add_argument("--maximum", type=int, required=True)
    args = parser.parse_args(argv)

    try:
        endpoint = CODING_ENDPOINT if args.route == "coding" else STANDARD_ENDPOINT
        if not 1 <= args.max_tokens <= 512:
            raise ValueError("calibration transport output budget outside fixed cap")
        plan = make_calibration_plan()
        digests = tuple(
            _request_digest(x.prompt(), model=args.model, max_tokens=args.max_tokens)
            for x in plan
        )
        guard = HostCampaignBudget(
            args.path, campaign_id=args.campaign_id,
            endpoint=endpoint, planned_digests=digests,
            maximum=args.maximum,
        )
        if args.operation == "initialize":
            guard.initialize()
        result = guard.inspect()
    except (OSError, ValueError, CampaignBudgetRejected):
        result = {
            "schema": "c3r-host-budget-check-v0.1",
            "status": "rejected",
            "provider_sends_authenticated": False,
            "provider_billing_verified": False,
            "scientific_acceptance": False,
        }
        print(json.dumps(result, sort_keys=True, separators=(",", ":")))
        return 2
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
