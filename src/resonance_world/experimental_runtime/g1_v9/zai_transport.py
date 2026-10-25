"""Z.AI qualification transport: real sends, fail-closed, meter-enforced.

This is the only module permitted to perform physical provider sends for
the qualification probe, and it is **disabled by default**:

- construction requires a complete, valid, `authorized=True`
  :class:`QualificationAuthorizationRecord` bound to the published
  scientific freeze anchor (`c843f504...`) — anything else raises
  :class:`TransportNotAuthorized` and nothing is constructed;
- every physical send first consumes an attempt in the persistent
  ledger (fail-closed at the cap, timeouts counted as consumed), and
  the outcome is recorded afterwards; there are no retries and no
  replacements;
- the HTTP call itself is isolated in ``_http_post`` (stdlib urllib,
  hard timeout, one attempt) so tests can inject failures without any
  network.

The credential never enters this module's state, logs, or errors: it is
fetched from a caller-supplied ``credential_provider`` callable at send
time only.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from resonance_world.adapters import sha256_json

from .send_ledger import PersistentSendLedger

SCIENCE_ANCHOR_DIGEST = (
    "c843f5042589559becb7510871d13d91f7a1337a43f051b76be25d5fdb8f27b8"
)


class TransportNotAuthorized(RuntimeError):
    """Raised when construction is attempted without a valid authorization."""


class TransportDisabled(RuntimeError):
    """Raised on any send through the disabled-by-default transport."""


class QualificationTransportError(RuntimeError):
    """Transport failure with a recorded outcome; never retried."""


@dataclass(frozen=True, slots=True)
class QualificationAuthorizationRecord:
    """The operational authorization record for the qualification probe.

    ``authorized`` is false in every candidate emission; only an
    independent human authorization can produce a record with
    ``authorized=True``, and the transport constructor requires exactly
    that.
    """

    schema: str
    status: str
    science_anchor_digest: str
    code_commit: str
    provider: str
    model: str
    endpoint_family: str
    endpoint_url: str
    send_cap: int
    max_output_tokens: int
    timeout_seconds: float
    authorized: bool
    authorized_by: str
    authorized_at: str
    notes: tuple[str, ...] = ()

    def validation_failures(self) -> list[str]:
        failures: list[str] = []
        if self.schema != "g1-v9-qualification-authorization-v1":
            failures.append("schema must be g1-v9-qualification-authorization-v1")
        if self.status != "authorized":
            failures.append("status must be 'authorized' to enable the transport")
        anchor = self.science_anchor_digest
        if len(anchor) != 64 or any(c not in "0123456789abcdef" for c in anchor):
            failures.append("science_anchor_digest must be a full 64-hex digest")
        if anchor != SCIENCE_ANCHOR_DIGEST:
            failures.append("science anchor does not match the frozen manifest")
        commit = self.code_commit
        if (
            len(commit) != 40
            or any(c not in "0123456789abcdef" for c in commit)
        ):
            failures.append("code_commit must be a full 40-hex commit SHA")
        if self.provider != "zai":
            failures.append("provider must be 'zai'")
        if not self.model.startswith("glm-"):
            failures.append("model must be a GLM model")
        if not self.endpoint_url.startswith("https://"):
            failures.append("endpoint_url must be https")
        if self.send_cap != 8:
            failures.append("qualification send cap must be exactly 8")
        if self.max_output_tokens <= 0:
            failures.append("max_output_tokens must be positive")
        if not 0 < self.timeout_seconds <= 120:
            failures.append("timeout_seconds must lie in (0, 120]")
        if self.authorized is not True:
            failures.append("authorized must be true to enable the transport")
        if not self.authorized_by.strip():
            failures.append("authorized_by is required")
        try:
            from datetime import datetime

            datetime.fromisoformat(self.authorized_at)
        except (ValueError, TypeError):
            failures.append("authorized_at must be an ISO-8601 timestamp")
        return failures


@dataclass(frozen=True, slots=True)
class DisabledTransport:
    """The default transport: every send is refused before anything happens."""

    reason: str = "connection disabled by default; no authorized record bound"

    def send(self, label: str, payload: dict[str, Any]) -> dict[str, Any]:
        raise TransportDisabled(self.reason)


def disabled_transport() -> DisabledTransport:
    """Return the default disabled transport."""

    return DisabledTransport()


class ZaiQualificationTransport:
    """The real, meter-enforced transport for the 8-send qualification.

    Construction requires an authorized record that matches the frozen
    science anchor and a persistent ledger whose cap equals the record's
    send cap. Any mismatch raises and nothing is constructed.
    """

    def __init__(
        self,
        *,
        record: QualificationAuthorizationRecord,
        ledger: PersistentSendLedger,
        credential_provider: Callable[[], str],
        http_post: Callable[[str, str, dict[str, Any], float], tuple[int, str]] | None = None,
    ) -> None:
        failures = record.validation_failures()
        if record.science_anchor_digest != SCIENCE_ANCHOR_DIGEST:
            failures.append("record is not bound to the frozen science anchor")
        if ledger.send_cap != record.send_cap:
            failures.append("ledger cap does not match the authorized send cap")
        if failures:
            raise TransportNotAuthorized("; ".join(failures))
        self._record = record
        self._ledger = ledger
        self._credential_provider = credential_provider
        self._http_post = http_post if http_post is not None else self._urllib_post

    @property
    def remaining(self) -> int:
        return self._record.send_cap - self._ledger.attempts()

    def _urllib_post(
        self, url: str, api_key: str, body: dict[str, Any], timeout_seconds: float
    ) -> tuple[int, str]:
        request = urllib.request.Request(
            url,
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                return int(response.status), response.read().decode("utf-8")
        except urllib.error.HTTPError as error:
            return int(error.code), error.read().decode("utf-8", errors="replace")

    def send(self, label: str, prompt: str) -> dict[str, Any]:
        """Perform exactly one metered send; never retries, never replaces."""

        payload_sha = sha256_json({"label": label, "prompt": prompt})

        # Consume the attempt slot BEFORE the call: an unknown outcome
        # (timeout, crash) counts against the cap and is never retried.
        self._ledger.record_attempt(label, payload_sha)
        try:
            status, body_text = self._http_post(
                self._record.endpoint_url,
                self._credential_provider(),
                {
                    "model": self._record.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": self._record.max_output_tokens,
                    "temperature": 0,
                },
                self._record.timeout_seconds,
            )
        except TimeoutError:
            self._ledger.record_outcome(label, payload_sha, "timeout")
            raise QualificationTransportError("provider send timed out (consumed)") from None
        except Exception as error:
            self._ledger.record_outcome(label, payload_sha, "unknown-outcome")
            raise QualificationTransportError(
                f"provider send failed with an unknown outcome (consumed): {error}"
            ) from error

        if status in (401, 403):
            self._ledger.record_outcome(label, payload_sha, "auth-failure")
            raise QualificationTransportError(f"authentication failed (HTTP {status})")
        if status != 200:
            self._ledger.record_outcome(label, payload_sha, "http-error")
            raise QualificationTransportError(f"provider returned HTTP {status}")

        try:
            body = json.loads(body_text)
            content = body["choices"][0]["message"]["content"]
            if not isinstance(content, str) or not content.strip():
                raise ValueError("empty content")
        except (json.JSONDecodeError, KeyError, IndexError, TypeError, ValueError):
            self._ledger.record_outcome(label, payload_sha, "malformed-response")
            raise QualificationTransportError(
                "provider response was malformed (consumed)"
            ) from None

        self._ledger.record_outcome(label, payload_sha, "succeeded")
        return {"label": label, "content": content, "status": status}
