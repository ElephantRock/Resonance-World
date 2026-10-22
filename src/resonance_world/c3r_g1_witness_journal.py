"""G1 witness-owned append-only *prototype* with signed event checkpoints.

Offline construction only. The append-only API and OS permissions are NOT
WORM storage: a filesystem owner or privileged operator can rewrite/remove it.
For scientific custody use a separately operated service, independently pinned
public keys, external pretrial publication and immutable remote retention.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from .c3r_g1_evaluator_receipts import ReceiptVerifier
from .c3r_g1_evaluator_transcript import audit_signed_transcript
from .c3r_g1_multischema import PublicCohort, V2Design
from .c3r_g1_witnessed_lock import WitnessVerifier, WitnessedLock

EVENT_FIELDS = frozenset({
    "schema", "run_id", "index", "prior_sha256", "kind",
    "payload", "witness_key_sha256", "signature",
})
ZERO_HASH = "0" * 64


def _canonical(value: object) -> bytes:
    return json.dumps(value, separators=(",", ":"), sort_keys=True).encode("utf-8")


def _sha(value: object) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _public_hex(key: Ed25519PrivateKey) -> str:
    return key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw,
    ).hex()


@dataclass(frozen=True, slots=True)
class JournalAudit:
    verdict: str
    errors: tuple[str, ...]
    event_count: int

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": "c3r-g1-witness-journal-audit-v0.1",
            "verdict": self.verdict,
            "errors": list(self.errors),
            "events_inspected": self.event_count,
            "witness_signature_chain_valid": self.verdict == "signed_structural_chain",
            "external_witness_custody_attested": False,
            "trusted_timestamp_attested": False,
            "immutable_remote_retention_attested": False,
            "private_grade_correctness_verified": False,
            "provider_sends_verified": False,
            "scientific_acceptance": False,
        }


def audit_witness_journal(
    events: object, cohort: PublicCohort, *,
    witness_public_hex: str, evaluator_public_hex: str,
    run_id: str, now_utc: datetime,
) -> JournalAudit:
    expected = cohort.design.logical_calls + 3
    if not isinstance(events, list) or len(events) != expected:
        return JournalAudit("rejected", ("journal_denominator_mismatch",), 0)
    try:
        witness = WitnessVerifier(witness_public_hex)
        public = bytes.fromhex(witness_public_hex)
        if len(public) != 32:
            raise ValueError("invalid pinned witness public key")
        key = Ed25519PublicKey.from_public_bytes(public)
        current = ZERO_HASH
        payloads = []
        for i, event in enumerate(events):
            if not isinstance(event, dict) or set(event) != EVENT_FIELDS:
                raise ValueError("unexpected event fields")
            if (event["schema"] != "c3r-g1-witness-event-v0.1"
                    or event["run_id"] != run_id
                    or type(event["index"]) is not int or event["index"] != i
                    or event["prior_sha256"] != current
                    or event["kind"] != ("enrollment" if i == 0 else "evaluator")
                    or event["witness_key_sha256"] != hashlib.sha256(public).hexdigest()
                    or not isinstance(event["payload"], dict)):
                raise ValueError("event identity/order/chain mismatch")
            signature = event["signature"]
            if not isinstance(signature, str) or len(signature) != 128:
                raise ValueError("malformed witness signature")
            key.verify(bytes.fromhex(signature), _canonical({
                k: v for k, v in event.items() if k != "signature"
            }))
            payloads.append(event["payload"])
            current = _sha(event)

        witness.verify(
            payloads[0], cohort, expected_run_id=run_id,
            expected_evaluator_public_key_hex=evaluator_public_hex, now_utc=now_utc,
        )
        verdict = audit_signed_transcript(
            payloads[1:], cohort, public_key_hex=evaluator_public_hex,
            expected_run_id=run_id,
        )
        if verdict.status != "signed_structurally_consistent":
            raise ValueError("incomplete or inconsistent evaluator transcript")
    except (ValueError, TypeError, KeyError, InvalidSignature):
        return JournalAudit("rejected", ("signature_lock_or_transcript_invalid",), len(events))
    return JournalAudit("signed_structural_chain", (), len(events))


class WitnessJournal:
    """One-run, exclusive-creation, append+fsync fixture. No resume on crash."""

    def __init__(
        self, path: Path, *, witness_seed: bytes, signed_lock: dict[str, object],
        cohort: PublicCohort, evaluator_public_hex: str,
        run_id: str, now_utc: datetime,
    ) -> None:
        if type(witness_seed) is not bytes or len(witness_seed) != 32:
            raise ValueError("witness signing seed must be 32 private bytes")
        self._key = Ed25519PrivateKey.from_private_bytes(witness_seed)
        self.public_key_hex = _public_hex(self._key)
        WitnessVerifier(self.public_key_hex).verify(
            signed_lock, cohort, expected_run_id=run_id,
            expected_evaluator_public_key_hex=evaluator_public_hex, now_utc=now_utc,
        )
        self._run_id = run_id
        self._cohort = cohort
        self._evaluator_public_hex = evaluator_public_hex
        self._now_utc = now_utc
        self._expected_dev = (
            cohort.design.units * 2 * cohort.design.development_per_family
        )
        self._expected_qual = cohort.design.heldout_triplets * 3
        self._verifier = ReceiptVerifier(evaluator_public_hex, expected_run_id=run_id)
        self._events: list[dict[str, object]] = []
        self._receipts: list[dict[str, object]] = []
        self._closed = False
        self._fd: int | None = None

        if not path.is_absolute() or path.is_symlink():
            raise ValueError("journal path must be absolute and not a symlink")
        parent = path.parent.stat()
        if (not stat.S_ISDIR(parent.st_mode)
                or parent.st_uid != os.geteuid()
                or parent.st_mode & 0o077):
            raise ValueError("journal parent must be owned and private (0700)")
        flags = (os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_APPEND
                 | getattr(os, "O_NOFOLLOW", 0))
        fd = os.open(path, flags, 0o600)
        self._fd = fd
        try:
            self._write_event("enrollment", signed_lock)
        except Exception:
            self.close()
            raise

    @property
    def event_count(self) -> int:
        return len(self._events)

    def _write_event(self, kind: str, payload: dict[str, object]) -> None:
        if self._closed or self._fd is None:
            raise ValueError("witness journal is closed")
        unsigned: dict[str, object] = {
            "schema": "c3r-g1-witness-event-v0.1",
            "run_id": self._run_id,
            "index": len(self._events),
            "prior_sha256": _sha(self._events[-1]) if self._events else ZERO_HASH,
            "kind": kind,
            "payload": json.loads(_canonical(payload)),
            "witness_key_sha256": hashlib.sha256(
                bytes.fromhex(self.public_key_hex)
            ).hexdigest(),
        }
        event: dict[str, object] = {
            **unsigned, "signature": self._key.sign(_canonical(unsigned)).hex(),
        }
        raw = _canonical(event) + b"\n"
        remaining = memoryview(raw)
        while remaining:
            written = os.write(self._fd, remaining)
            if written <= 0:
                raise OSError("witness journal append incomplete")
            remaining = remaining[written:]
        os.fsync(self._fd)
        self._events.append(event)

    def observe(self, receipt: dict[str, object]) -> None:
        if self._closed:
            raise ValueError("witness journal is closed")
        payload = self._verifier.verify_next(receipt)
        index = len(self._receipts)
        phase = (
            "accept_development" if index == 0
            else "development_feedback" if index <= self._expected_dev
            else "qualification_sealed"
            if index <= self._expected_dev + self._expected_qual
            else "final"
        )
        if index > self._expected_dev + self._expected_qual + 1:
            raise ValueError("unexpected post-final receipt")
        if not isinstance(payload, dict):
            raise ValueError("invalid evaluator payload")
        if index == 0:
            lock = self._events[0]["payload"]
            assert isinstance(lock, dict)
            if (payload.get("phase") != "accept_development"
                    or payload.get("target_commitment") != lock["target_commitment"]
                    or payload.get("public_cohort_digest") != self._cohort.digest
                    or payload.get("development_expected") != self._expected_dev
                    or payload.get("qualification_expected") != self._expected_qual):
                raise ValueError("evaluator readiness differs from witness commitment")
        elif phase == "development_feedback":
            if (payload.get("phase") != phase
                    or payload.get("development_received") != index
                    or type(payload.get("accepted")) is not bool):
                raise ValueError("invalid staged development receipt")
        elif phase == "qualification_sealed":
            if (set(payload) != {
                "schema", "phase", "task_id", "qualification_received",
            } or payload.get("phase") != phase
                    or payload.get("qualification_received")
                    != index - self._expected_dev):
                raise ValueError("early grade leakage or holdout sequence gap")
        else:
            if payload.get("schema") != "c3r-g1-evaluator-final-v0.1":
                raise ValueError("final evaluator closure missing")
            result = audit_signed_transcript(
                [*self._receipts, receipt], self._cohort,
                public_key_hex=self._evaluator_public_hex,
                expected_run_id=self._run_id,
            )
            if result.status != "signed_structurally_consistent":
                raise ValueError("inconsistent full transcript at journal closure")
        self._write_event("evaluator", receipt)
        self._receipts.append(json.loads(_canonical(receipt)))
        if phase == "final":
            self.close()

    def close(self) -> None:
        if self._fd is not None:
            os.close(self._fd)
            self._fd = None
        self._closed = True

    def __enter__(self) -> WitnessJournal:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()


class ReceiptSession(Protocol):
    @property
    def signed_receipts(self) -> tuple[dict[str, object], ...]: ...
    def ready(self) -> dict[str, Any]: ...
    def submit(self, request: dict[str, object]) -> dict[str, Any]: ...
    def finalize(self) -> dict[str, Any]: ...


class JournaledEvaluatorSession:
    """Offline wiring: journal each signed receipt BEFORE releasing its payload.

    Not an independent authority when held in the agent process. A real
    deployment must expose a witness-operated remote witness append API.
    """

    def __init__(self, signed_session: ReceiptSession, journal: WitnessJournal) -> None:
        self._session = signed_session
        self._journal = journal
        self._last = 0

    def _record_new(self) -> None:
        signed = self._session.signed_receipts
        if len(signed) != self._last + 1:
            raise ValueError("expected exactly one new evaluator receipt")
        self._journal.observe(signed[-1])
        self._last += 1

    def ready(self) -> dict[str, Any]:
        payload = self._session.ready()
        self._record_new()
        return payload

    def submit(self, request: dict[str, object]) -> dict[str, Any]:
        payload = self._session.submit(request)
        self._record_new()
        return payload

    def finalize(self) -> dict[str, Any]:
        payload = self._session.finalize()
        self._record_new()
        return payload


def main(argv: list[str] | None = None) -> int:
    """Read-only verification CLI; no keys other than independently pinned public."""
    parser = argparse.ArgumentParser(description="Audit a G1 witness event journal")
    parser.add_argument("journal", type=Path)
    parser.add_argument("--witness-public", type=Path, required=True)
    parser.add_argument("--evaluator-public", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--units", type=int, default=8)
    parser.add_argument("--development", type=int, default=6)
    parser.add_argument("--qualification", type=int, default=8)
    parser.add_argument("--public-seed", type=int, default=20261022)
    parser.add_argument("--model-id", default="offline-schema-fixture")
    args = parser.parse_args(argv)
    try:
        if (args.journal.stat().st_size > 5 * 1024 * 1024
                or args.witness_public.stat().st_size > 128
                or args.evaluator_public.stat().st_size > 128):
            raise ValueError("oversized input")
        cohort = V2Design(
            units=args.units,
            development_per_family=args.development,
            qualification_per_family=args.qualification,
            public_seed=args.public_seed,
            model_id=args.model_id,
        ).freeze()
        with args.journal.open(encoding="utf-8") as stream:
            lines = stream.readlines()
        if len(lines) > cohort.design.logical_calls + 3:
            raise ValueError("excess journal rows")
        events = [json.loads(line) for line in lines]
        witness_public = args.witness_public.read_text(encoding="ascii").strip()
        evaluator_public = args.evaluator_public.read_text(encoding="ascii").strip()
        audit = audit_witness_journal(
            events, cohort, witness_public_hex=witness_public,
            evaluator_public_hex=evaluator_public, run_id=args.run_id,
            now_utc=datetime.now(UTC),
        )
    except (OSError, ValueError, TypeError, KeyError, UnicodeError):
        audit = JournalAudit("rejected", ("invalid_input",), 0)
    print(json.dumps(audit.to_dict(), sort_keys=True, separators=(",", ":")))
    return 0 if audit.verdict == "signed_structural_chain" else 2


if __name__ == "__main__":
    raise SystemExit(main())
