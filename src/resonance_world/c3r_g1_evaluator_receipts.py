"""Ed25519 receipt chains for C3R evaluator messages (engineering prototype).

The *public* verifier can authenticate an evaluator key and reject changed,
missing, reordered or replayed receipts in a single run. It cannot attest
independent key ownership, external timestamps, or experimental validity.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from collections.abc import Mapping
from typing import Any, Protocol

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

ZERO_DIGEST = "0" * 64
_RECEIPT_FIELDS = frozenset({
    "schema", "run_id", "sequence", "prior_sha256", "payload",
    "public_key_sha256", "signature",
})


def _json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha(value: object) -> str:
    return hashlib.sha256(_json(value)).hexdigest()


def _valid_run_id(value: object) -> bool:
    return (
        isinstance(value, str)
        and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{7,79}", value) is not None
    )


class ReceiptSigner:
    """Use only in the evaluator-owned process, never agent-side."""

    def __init__(self, private_seed: bytes, *, run_id: str) -> None:
        if not isinstance(private_seed, bytes) or len(private_seed) != 32:
            raise ValueError("Ed25519 private seed must contain exactly 32 bytes")
        if not _valid_run_id(run_id):
            raise ValueError("receipt run ID is invalid")
        self._key = Ed25519PrivateKey.from_private_bytes(private_seed)
        self._run_id = run_id
        self._sequence = 0
        self._prior_digest = ZERO_DIGEST

    @property
    def public_key_hex(self) -> str:
        from cryptography.hazmat.primitives import serialization

        return self._key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        ).hex()

    def seal(self, payload: Mapping[str, object]) -> dict[str, object]:
        if not isinstance(payload, dict):
            raise ValueError("receipt payload must be a JSON object")
        self._sequence += 1
        unsigned = {
            "schema": "c3r-g1-ed25519-receipt-v0.1",
            "run_id": self._run_id,
            "sequence": self._sequence,
            "prior_sha256": self._prior_digest,
            "public_key_sha256": hashlib.sha256(
                bytes.fromhex(self.public_key_hex)
            ).hexdigest(),
            "payload": payload,
        }
        signature = self._key.sign(_json(unsigned)).hex()
        envelope = {**unsigned, "signature": signature}
        self._prior_digest = _sha(envelope)
        return envelope


class ReceiptVerifier:
    """Read-only verifier for a single expected run and pinned public key."""

    def __init__(self, public_key_hex: str, *, expected_run_id: str) -> None:
        if not _valid_run_id(expected_run_id):
            raise ValueError("expected receipt run ID is invalid")
        if not isinstance(public_key_hex, str) or not re.fullmatch(
            r"[0-9a-fA-F]{64}", public_key_hex
        ):
            raise ValueError("public key must be 32 raw bytes as hex")
        self._public_bytes = bytes.fromhex(public_key_hex)
        self._key = Ed25519PublicKey.from_public_bytes(self._public_bytes)
        self._expected_run_id = expected_run_id
        self._sequence = 0
        self._prior_digest = ZERO_DIGEST

    def verify_next(self, candidate: object) -> dict[str, Any]:
        if not isinstance(candidate, dict) or set(candidate) != _RECEIPT_FIELDS:
            raise ValueError("signed evaluator receipt has unexpected fields")
        if candidate["schema"] != "c3r-g1-ed25519-receipt-v0.1":
            raise ValueError("receipt protocol version mismatch")
        if candidate["run_id"] != self._expected_run_id:
            raise ValueError("evaluator run ID mismatch or replay")
        if (type(candidate["sequence"]) is not int
                or candidate["sequence"] != self._sequence + 1
                or candidate["prior_sha256"] != self._prior_digest):
            raise ValueError("evaluator receipt sequence or chain mismatch")
        if candidate["public_key_sha256"] != hashlib.sha256(
            self._public_bytes
        ).hexdigest():
            raise ValueError("evaluator public key fingerprint mismatch")
        if not isinstance(candidate["payload"], dict):
            raise ValueError("signed payload is not an object")
        signature = candidate["signature"]
        if not isinstance(signature, str) or not re.fullmatch(
            r"[0-9a-fA-F]{128}", signature
        ):
            raise ValueError("malformed evaluator signature")
        unsigned = {key: candidate[key] for key in candidate if key != "signature"}
        try:
            self._key.verify(bytes.fromhex(signature), _json(unsigned))
        except (InvalidSignature, ValueError) as exc:
            raise ValueError("evaluator signature verification failed") from exc
        # Mutate chain state only after signature and lineage verification.
        self._sequence += 1
        self._prior_digest = _sha(candidate)
        return candidate["payload"]


class ReceiptSessionPort(Protocol):
    def ready(self) -> dict[str, Any]: ...
    def submit(self, request: dict[str, object]) -> dict[str, Any]: ...
    def finalize(self) -> dict[str, Any]: ...


class VerifiedEvaluatorSession:
    """Adapter: exposes only verified payloads to SealedPilotRunner."""

    def __init__(self, transport: ReceiptSessionPort, verifier: ReceiptVerifier) -> None:
        self._transport = transport
        self._verifier = verifier
        self._started = False
        self._ended = False
        self._receipts: list[dict[str, object]] = []

    @property
    def signed_receipts(self) -> tuple[dict[str, object], ...]:
        """Capture only already verified envelopes; not an immutable evidence store."""
        return tuple(copy.deepcopy(self._receipts))

    def _consume(self, envelope: dict[str, Any]) -> dict[str, Any]:
        payload = self._verifier.verify_next(envelope)
        self._receipts.append(copy.deepcopy(envelope))
        return payload

    def ready(self) -> dict[str, Any]:
        if self._started:
            raise ValueError("signed evaluator can only start once")
        self._started = True
        return self._consume(self._transport.ready())

    def submit(self, request: dict[str, object]) -> dict[str, Any]:
        if not self._started or self._ended:
            raise ValueError("signed evaluator is not accepting submissions")
        return self._consume(self._transport.submit(request))

    def finalize(self) -> dict[str, Any]:
        if not self._started or self._ended:
            raise ValueError("signed evaluator cannot finalize now")
        self._ended = True
        return self._consume(self._transport.finalize())
