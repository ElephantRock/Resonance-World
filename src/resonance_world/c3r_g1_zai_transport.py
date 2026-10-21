"""Opt-in, bounded Z.AI standard-API transport for the C3R G1 model port.

Not a Hermes/D2 client. Importing this module performs no network access.
All sends must be explicitly enabled and pre-reserved; no automatic retries,
redirects, arbitrary endpoints, or raw content logging are permitted.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from urllib.error import HTTPError
from urllib.request import (
    HTTPRedirectHandler,
    Request,
    build_opener,
)

from .c3r_g1_model_boundary import (
    ModelChoiceCompletion,
    ModelChoiceRequest,
)

STANDARD_ENDPOINT = "https://api.z.ai/api/paas/v4/chat/completions"
MAX_RESPONSE_BYTES = 64 * 1024
MAX_TOTAL_SENDS = 8


class ProviderBudgetExhausted(RuntimeError):
    """A new physical request is forbidden: all reservations are consumed."""


class ProviderTransportRejected(RuntimeError):
    """A provider response/transport failed without propagating its raw content."""


@dataclass(frozen=True, slots=True)
class TransportResponse:
    status: int
    body: bytes = field(repr=False)

    def __post_init__(self) -> None:
        if type(self.status) is not int or type(self.body) is not bytes:
            raise ValueError("transport response types must be exact")


# Injected transport allows offline CI tests. It must perform no more than ONE send.
Transport = Callable[[str, dict[str, str], bytes, float], TransportResponse]


class _DenyRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ProviderTransportRejected("redirects are forbidden")


def _single_https_post(
    url: str, headers: dict[str, str], body: bytes, timeout_seconds: float
) -> TransportResponse:
    """Exactly one HTTPS POST, no redirects, no SDK or retry machinery."""
    if url != STANDARD_ENDPOINT:
        raise ProviderTransportRejected("endpoint outside pinned allowlist")
    request = Request(url, data=body, headers=headers, method="POST")
    opener = build_opener(_DenyRedirects())
    try:
        with opener.open(request, timeout=timeout_seconds) as response:
            payload = response.read(MAX_RESPONSE_BYTES + 1)
            if len(payload) > MAX_RESPONSE_BYTES:
                raise ProviderTransportRejected("response exceeds fixed limit")
            return TransportResponse(status=response.status, body=payload)
    except HTTPError as exc:
        # Never read or persist the provider error body.
        return TransportResponse(status=exc.code, body=b"")


@dataclass(frozen=True, slots=True)
class PhysicalSendRecord:
    ordinal: int
    request_digest: str
    http_status: int | None
    failure_class: str | None


@dataclass(slots=True)
class PhysicalSendLedger:
    """Append-only in-process pre-send reservation ledger for ONE CLI process."""

    max_total_sends: int
    records: list[PhysicalSendRecord] = field(default_factory=list)

    def __post_init__(self) -> None:
        if (
            type(self.max_total_sends) is not int
            or not 1 <= self.max_total_sends <= MAX_TOTAL_SENDS
        ):
            raise ValueError("send budget must be a positive count within the fixed cap")

    @property
    def consumed(self) -> int:
        return len(self.records)

    def reserve(self, *, request_digest: str) -> int:
        """Reserve BEFORE dispatch; even ambiguous timeouts consume the slot."""
        if self.consumed >= self.max_total_sends:
            raise ProviderBudgetExhausted("physical send cap reached")
        ordinal = self.consumed + 1
        self.records.append(PhysicalSendRecord(ordinal, request_digest, None, "reserved"))
        return ordinal

    def finish(
        self, ordinal: int, *, http_status: int | None = None,
        failure_class: str | None = None
    ) -> None:
        if ordinal != self.consumed:
            raise RuntimeError("only the latest outstanding send can be closed")
        existing = self.records[ordinal - 1]
        if existing.failure_class != "reserved":
            raise RuntimeError("physical send reservation already closed")
        self.records[ordinal - 1] = PhysicalSendRecord(
            ordinal, existing.request_digest, http_status, failure_class
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": "c3r-physical-send-ledger-v0.1",
            "reserved": self.consumed,
            "maximum": self.max_total_sends,
            "entries": [
                {
                    "ordinal": row.ordinal,
                    "request_digest": row.request_digest,
                    "http_status": row.http_status,
                    "failure_class": row.failure_class,
                }
                for row in self.records
            ],
        }


def _usage(value: object) -> int | None:
    return value if type(value) is int and value >= 0 else None


@dataclass(slots=True)
class ZaiStandardModelPort:
    """Bounded adapter. Never reuse subscription Coding Plan credentials by default."""

    api_key: str = field(repr=False)
    model_id: str
    ledger: PhysicalSendLedger
    enabled: bool = False
    transport: Transport = _single_https_post
    timeout_seconds: float = 15.0
    max_tokens: int = 16

    def __post_init__(self) -> None:
        if not self.api_key.strip() or not self.model_id.strip():
            raise ValueError("API key and model must be explicitly supplied")
        if any(ch in self.model_id for ch in "\r\n"):
            raise ValueError("model id contains forbidden control characters")
        if not 0 < self.timeout_seconds <= 30:
            raise ValueError("per-call timeout must be bounded")
        if type(self.max_tokens) is not int or not 1 <= self.max_tokens <= 64:
            raise ValueError("response token limit must be between 1 and 64")

    def complete(self, request: ModelChoiceRequest) -> ModelChoiceCompletion:
        if not self.enabled:
            raise PermissionError("C3R provider dispatch is disabled by default")
        body = json.dumps(
            {
                "model": self.model_id,
                "messages": [{"role": "user", "content": request.prompt()}],
                "temperature": 0,
                "max_tokens": self.max_tokens,
                "stream": False,
            },
            sort_keys=True, separators=(",", ":"),
        ).encode("utf-8")
        digest = hashlib.sha256(body).hexdigest()
        ordinal = self.ledger.reserve(request_digest=digest)
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        try:
            response = self.transport(STANDARD_ENDPOINT, headers, body, self.timeout_seconds)
            if not isinstance(response, TransportResponse):
                raise ProviderTransportRejected("transport returned an invalid response type")
            if response.status != 200:
                self.ledger.finish(
                    ordinal, http_status=response.status, failure_class="HttpNon200"
                )
                raise ProviderTransportRejected("provider returned non-200")
            if len(response.body) > MAX_RESPONSE_BYTES:
                raise ProviderTransportRejected("response exceeds fixed limit")
            decoded = json.loads(response.body)
            if type(decoded) is not dict:
                raise ProviderTransportRejected("invalid provider payload shape")
            choices = decoded.get("choices")
            if not isinstance(choices, list) or len(choices) != 1:
                raise ProviderTransportRejected("missing or multiple model choices")
            message = choices[0].get("message") if type(choices[0]) is dict else None
            content = message.get("content") if type(message) is dict else None
            if not isinstance(content, str):
                raise ProviderTransportRejected("missing textual model answer")
            usage = decoded.get("usage")
            usage = usage if isinstance(usage, dict) else {}
            self.ledger.finish(ordinal, http_status=200)
            return ModelChoiceCompletion(
                output=content,
                model_id=self.model_id,
                physical_sends_reported=1,
                prompt_tokens_reported=_usage(usage.get("prompt_tokens")),
                completion_tokens_reported=_usage(usage.get("completion_tokens")),
            )
        except Exception as exc:
            if self.ledger.records[ordinal - 1].failure_class == "reserved":
                self.ledger.finish(ordinal, failure_class=type(exc).__name__)
            if isinstance(exc, ProviderTransportRejected):
                raise
            raise ProviderTransportRejected("provider transport/shape failure") from None
