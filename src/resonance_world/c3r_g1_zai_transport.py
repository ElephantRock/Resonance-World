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
from typing import TYPE_CHECKING, Literal
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

if TYPE_CHECKING:
    from .c3r_g1_host_campaign_budget import HostCampaignBudget

STANDARD_ENDPOINT = "https://api.z.ai/api/paas/v4/chat/completions"
CODING_ENDPOINT = "https://api.z.ai/api/coding/paas/v4/chat/completions"
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
MAX_TOTAL_SENDS = 8
# Upper bound for the explicitly configurable generation budget. The Z.AI
# endpoint may impose a lower live limit; 1M is context, not output capacity.
MAX_GENERATION_TOKENS = 131_072
DEFAULT_GENERATION_TOKENS = 16_384


class ProviderBudgetExhausted(RuntimeError):
    """A new physical request is forbidden: all reservations are consumed."""


class ProviderTransportRejected(RuntimeError):
    """A provider response/transport failed without propagating its raw content."""


class ProviderCircuitOpen(RuntimeError):
    """Transport failure: no more network sends permitted in this process."""


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
    if url not in (STANDARD_ENDPOINT, CODING_ENDPOINT):
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
    timeout_seconds: float = 180.0
    max_tokens: int = DEFAULT_GENERATION_TOKENS
    route: Literal["standard", "coding"] = "standard"
    campaign_budget: HostCampaignBudget | None = None
    halted: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if self.route not in ("standard", "coding"):
            raise ValueError("provider route must be standard or coding")
        if not self.api_key.strip() or not self.model_id.strip():
            raise ValueError("API key and model must be explicitly supplied")
        if any(ch in self.model_id for ch in "\r\n"):
            raise ValueError("model id contains forbidden control characters")
        if not 0 < self.timeout_seconds <= 300:
            raise ValueError("per-call timeout must be bounded")
        if (type(self.max_tokens) is not int
                or not 1 <= self.max_tokens <= MAX_GENERATION_TOKENS):
            raise ValueError("generation token limit must be in supported configuration range")

    def complete(self, request: ModelChoiceRequest) -> ModelChoiceCompletion:
        return self.complete_prompt(request.prompt())

    def complete_prompt(self, prompt: str) -> ModelChoiceCompletion:
        """One bounded raw-public-task prompt, with the SAME physical ledger.

        Enables technical schema calibration without fabricating an
        arithmetic ModelChoiceRequest for text-transform tasks.
        No provider send occurs unless the port was explicitly enabled.
        """
        if (not isinstance(prompt, str) or not prompt.strip()
                or len(prompt.encode("utf-8")) > 8192
                or chr(0) in prompt):
            raise ValueError("public calibration prompt must be bounded text")
        if not self.enabled:
            raise PermissionError("C3R provider dispatch is disabled by default")
        if self.halted:
            raise ProviderCircuitOpen("C3R provider circuit remains closed to new sends")
        params: dict[str, object] = {
            "model": self.model_id,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
            "max_tokens": self.max_tokens,
            "stream": False,
        }
        # GLM-5.3 always reasons. A 16-token cap previously exhausted the
        # output budget before generating any final answer (8/8 blanks).
        if self.model_id in ("glm-5.3", "glm-5.3-flash"):
            params["thinking"] = {"type": "enabled"}
            params["reasoning_effort"] = "low"
        body = json.dumps(
            params,
            sort_keys=True, separators=(",", ":"),
        ).encode("utf-8")
        digest = hashlib.sha256(body).hexdigest()
        endpoint = CODING_ENDPOINT if self.route == "coding" else STANDARD_ENDPOINT
        # Optional host-wide shared reservation is synchronized and fsynced
        # BEFORE dispatch and before the process-local reservation. In a
        # restarted process it cannot silently reset the same campaign cap.
        # Vendor-side monetary/spending safeguards are still mandatory.
        if self.campaign_budget is not None:
            if self.ledger.consumed >= self.ledger.max_total_sends:
                self.halted = True
                raise ProviderBudgetExhausted("local send budget exhausted")
            try:
                self.campaign_budget.reserve(
                    request_digest=digest, endpoint=endpoint
                )
            except Exception:
                self.halted = True
                raise ProviderBudgetExhausted(
                    "shared campaign reservation rejected before dispatch"
                ) from None
        ordinal = self.ledger.reserve(request_digest=digest)
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        try:
            response = self.transport(endpoint, headers, body, self.timeout_seconds)
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
            details = usage.get("completion_tokens_details")
            details = details if isinstance(details, dict) else {}
            raw_finish_reason = choices[0].get("finish_reason")
            if raw_finish_reason in ("stop", "length", "tool_calls", "content_filter"):
                finish_reason = raw_finish_reason
            else:
                # Never preserve arbitrary provider text from metadata.
                finish_reason = "other" if isinstance(raw_finish_reason, str) else None
            reasoning = message.get("reasoning_content")
            completion_tokens = _usage(usage.get("completion_tokens"))
            completion = ModelChoiceCompletion(
                output=content,
                model_id=self.model_id,
                physical_sends_reported=1,
                prompt_tokens_reported=_usage(usage.get("prompt_tokens")),
                completion_tokens_reported=completion_tokens,
                finish_reason=finish_reason,
                reasoning_present=bool(reasoning) if reasoning is not None else None,
                reasoning_tokens_reported=_usage(details.get("reasoning_tokens")),
            )
            # A truncated *empty* final answer cannot produce a graded action.
            # Fail closed now, before seven more identical reasoning-only calls.
            budget_exhausted_without_answer = not content and (
                finish_reason == "length" or completion_tokens == self.max_tokens
            )
            if budget_exhausted_without_answer:
                self.halted = True
                self.ledger.finish(
                    ordinal, http_status=200, failure_class="EmptyFinalOutputLengthCap"
                )
            else:
                self.ledger.finish(ordinal, http_status=200)
            return completion
        except Exception as exc:
            # A failed send/response is terminal for this short technical run.
            # The G1 runner still counts remaining logical tasks as failed,
            # but cannot transmit additional requests using this port.
            self.halted = True
            if self.ledger.records[ordinal - 1].failure_class == "reserved":
                self.ledger.finish(ordinal, failure_class=type(exc).__name__)
            if isinstance(exc, ProviderTransportRejected):
                raise
            raise ProviderTransportRejected("provider transport/shape failure") from None
