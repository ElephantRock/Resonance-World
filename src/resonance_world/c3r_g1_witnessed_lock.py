"""Prospective witness-signed admission lock for C3R G1 (offline prototype).

A witnessed lock pins the evaluator signing identity, public task cohort,
hidden-target commitment, and unique run ID *before* model work begins.
This does not supply a trusted timestamp, independent operator, or evidence
that the signer had legitimate authority: trust in the witness public key
must originate entirely outside the model/evaluator process.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from .c3r_g1_evaluator_receipts import _valid_run_id
from .c3r_g1_multischema import PublicCohort

LOCK_FIELDS = frozenset({
    "schema", "run_id", "public_cohort_digest", "evaluator_public_key_hex",
    "target_commitment", "issued_at_utc", "expires_at_utc", "witness_signature",
})


def _canonical(payload: object) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _hex(value: object, length: int) -> bool:
    return isinstance(value, str) and re.fullmatch(
        rf"[0-9a-f]{{{length}}}", value
    ) is not None


def _parse_clock(value: object) -> datetime:
    if not isinstance(value, str) or re.fullmatch(
        r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", value
    ) is None:
        raise ValueError("witness time must be UTC RFC3339 seconds")
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    except ValueError as exc:
        raise ValueError("invalid UTC witness time") from exc


def _lock_body(record: dict[str, object]) -> dict[str, object]:
    return {name: value for name, value in record.items()
            if name != "witness_signature"}


@dataclass(frozen=True, slots=True)
class WitnessedLock:
    """Immutable verified fields; no mutable nested enrollment payload."""

    run_id: str
    public_cohort_digest: str
    evaluator_public_key: str
    target_commitment: str
    issued_at_utc: str
    expires_at_utc: str

    def require_ready(self, ready: object) -> None:
        if not isinstance(ready, dict) or (
            ready.get("schema") != "c3r-g1-evaluator-v0.1"
            or ready.get("phase") != "accept_development"
            or ready.get("public_cohort_digest") != self.public_cohort_digest
            or ready.get("target_commitment") != self.target_commitment
        ):
            raise ValueError("evaluator ready does not match preregistered witness lock")


class WitnessSigner:
    """Simulation-only witness; in research the witness owns this key separately."""

    def __init__(self, private_seed: bytes) -> None:
        if not isinstance(private_seed, bytes) or len(private_seed) != 32:
            raise ValueError("witness seed requires exactly 32 bytes")
        self._private = Ed25519PrivateKey.from_private_bytes(private_seed)

    @property
    def public_key_hex(self) -> str:
        from cryptography.hazmat.primitives import serialization

        return self._private.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        ).hex()

    def sign_lock(
        self, *, run_id: str, cohort: PublicCohort,
        evaluator_public_key_hex: str, target_commitment: str,
        issued_at_utc: str, expires_at_utc: str,
    ) -> dict[str, object]:
        if not _valid_run_id(run_id):
            raise ValueError("invalid prospective run ID")
        if not _hex(evaluator_public_key_hex, 64) or not _hex(
            target_commitment, 64
        ):
            raise ValueError("invalid evaluator identity or target commitment")
        start = _parse_clock(issued_at_utc)
        end = _parse_clock(expires_at_utc)
        if not start < end <= start + timedelta(days=30):
            raise ValueError("witness lock validity must be within 30 days")
        body: dict[str, object] = {
            "schema": "c3r-g1-witnessed-lock-v0.1",
            "run_id": run_id,
            "public_cohort_digest": cohort.digest,
            "evaluator_public_key_hex": evaluator_public_key_hex,
            "target_commitment": target_commitment,
            "issued_at_utc": issued_at_utc,
            "expires_at_utc": expires_at_utc,
        }
        return {
            **body, "witness_signature": self._private.sign(
                _canonical(body)
            ).hex(),
        }


class WitnessVerifier:
    """Trust pin supplied out-of-band; local UTC freshness is not trusted time."""

    def __init__(self, pinned_witness_public_key_hex: str) -> None:
        if not _hex(pinned_witness_public_key_hex, 64):
            raise ValueError("witness verifier needs externally pinned public key")
        self._key = Ed25519PublicKey.from_public_bytes(
            bytes.fromhex(pinned_witness_public_key_hex)
        )

    def verify(
        self, candidate: object, cohort: PublicCohort, *,
        expected_run_id: str, expected_evaluator_public_key_hex: str,
        now_utc: datetime,
    ) -> WitnessedLock:
        if not isinstance(candidate, dict) or set(candidate) != LOCK_FIELDS:
            raise ValueError("witness enrollment has missing or extra fields")
        if (candidate["schema"] != "c3r-g1-witnessed-lock-v0.1"
                or candidate["run_id"] != expected_run_id
                or not _valid_run_id(candidate["run_id"])
                or candidate["public_cohort_digest"] != cohort.digest
                or candidate["evaluator_public_key_hex"]
                != expected_evaluator_public_key_hex
                or not _hex(candidate["evaluator_public_key_hex"], 64)
                or not _hex(candidate["target_commitment"], 64)):
            raise ValueError("witness lock does not pin expected experiment identities")
        start = _parse_clock(candidate["issued_at_utc"])
        end = _parse_clock(candidate["expires_at_utc"])
        if (now_utc.tzinfo is None or now_utc.utcoffset() != timedelta()
                or not start <= now_utc <= end
                or not start < end <= start + timedelta(days=30)):
            raise ValueError("witness lock expired, future dated or invalid clock")
        signature = candidate["witness_signature"]
        if not _hex(signature, 128):
            raise ValueError("witness signature malformed")
        try:
            self._key.verify(bytes.fromhex(signature), _canonical(
                _lock_body(candidate)
            ))
        except (InvalidSignature, ValueError) as exc:
            raise ValueError("witness signature mismatch") from exc
        return WitnessedLock(
            run_id=expected_run_id,
            public_cohort_digest=cohort.digest,
            evaluator_public_key=expected_evaluator_public_key_hex,
            target_commitment=candidate["target_commitment"],
            issued_at_utc=candidate["issued_at_utc"],
            expires_at_utc=candidate["expires_at_utc"],
        )


class WitnessedEvaluatorSession:
    """Requires a verified witness lock at startup, then delegates all receipts."""

    def __init__(self, signed_session: Any, lock: WitnessedLock) -> None:
        self._session = signed_session
        self._lock = lock
        self._started = False

    def ready(self) -> dict[str, Any]:
        if self._started:
            raise ValueError("witnessed evaluator session already started")
        self._started = True
        signed_ready = self._session.ready()
        self._lock.require_ready(signed_ready)
        return signed_ready

    def submit(self, request: dict[str, object]) -> dict[str, Any]:
        if not self._started:
            raise ValueError("witnessed evaluator not admitted")
        return self._session.submit(request)

    def finalize(self) -> dict[str, Any]:
        if not self._started:
            raise ValueError("witnessed evaluator not admitted")
        return self._session.finalize()
