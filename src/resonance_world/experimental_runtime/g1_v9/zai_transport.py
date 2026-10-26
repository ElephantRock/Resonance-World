"""Z.AI qualification transport: real sends, fail-closed, meter-enforced.

This is the only module permitted to perform physical provider sends for
the qualification probe, and it is **disabled by default**:

- construction requires a signed, `authorized=True`
  :class:`QualificationAuthorizationRecord` whose HMAC verifies under
  the operator-held ``authorization_key_provider`` and whose
  ``code_commit`` matches the **running operational commit resolved
  from the repository itself** — a forged record, a stale commit, or a
  caller-supplied mismatch cannot enable the transport;
- every physical send first consumes an attempt in the persistent
  ledger (fail-closed at the cap, timeouts counted as consumed), and
  the outcome is recorded afterwards; there are no retries and no
  replacements;
- redirects are refused (they could carry the Authorization header to
  another host) and the final response URL must equal the requested
  pinned endpoint;
- the credential never enters module state, logs, or errors: it is
  fetched from a caller-supplied ``credential_provider`` callable at
  send time only.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import subprocess
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from resonance_world.adapters import canonical_json_bytes, sha256_json

from .send_ledger import PersistentSendLedger

SCIENCE_ANCHOR_DIGEST = (
    "c843f5042589559becb7510871d13d91f7a1337a43f051b76be25d5fdb8f27b8"
)
#: The exact pinned provider endpoint. Any other URL - including a
#: redirect target - is refused before the credential leaves.
PINNED_ENDPOINT_URL = "https://api.z.ai/api/coding/paas/v4/chat/completions"
#: The only identities that may issue a live authorization.
AUTHORIZED_ISSUERS = frozenset({"operator"})


class TransportNotAuthorized(RuntimeError):
    """Raised when construction is attempted without a valid authorization."""


class TransportDisabled(RuntimeError):
    """Raised on any send through the disabled-by-default transport."""


class QualificationTransportError(RuntimeError):
    """Transport failure with a recorded outcome; never retried."""


class _RefuseRedirect(urllib.request.HTTPRedirectHandler):
    """A redirect handler that refuses every redirect.

    A redirect could carry the Authorization header to a different host,
    so redirects are treated as a hard transport failure instead.
    """

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise QualificationTransportError(
            f"provider redirect refused (HTTP {code} -> {newurl})"
        )


@dataclass(frozen=True, slots=True)
class QualificationAuthorizationRecord:
    """The operational authorization record for the qualification probe.

    ``authorized`` is false in every candidate emission; only an
    independent human authorization can produce a record with
    ``authorized=True``, and the transport constructor requires exactly
    that, bound to the running operational commit.
    """

    schema: str
    status: str
    science_anchor_digest: str
    code_commit: str
    authorization_id: str
    ledger_base_dir: str
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
    authorization_hmac: str = ""
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
        if len(commit) != 40 or any(c not in "0123456789abcdef" for c in commit):
            failures.append("code_commit must be a full 40-hex commit SHA")
        auth_id = self.authorization_id
        if len(auth_id) != 64 or any(c not in "0123456789abcdef" for c in auth_id):
            failures.append("authorization_id must be a full 64-hex digest")
        if self.provider != "zai":
            failures.append("provider must be 'zai'")
        if self.model != "glm-5.3":
            failures.append("model must be exactly 'glm-5.3'")
        if self.endpoint_url != PINNED_ENDPOINT_URL:
            failures.append(
                "endpoint_url must be exactly the pinned Z.AI endpoint "
                "(credential redirect to another host is refused)"
            )
        if self.send_cap != 8:
            failures.append("qualification send cap must be exactly 8")
        if self.max_output_tokens <= 0:
            failures.append("max_output_tokens must be positive")
        if not 0 < self.timeout_seconds <= 120:
            failures.append("timeout_seconds must lie in (0, 120]")
        if self.authorized is not True:
            failures.append("authorized must be true to enable the transport")
        if self.authorized_by not in AUTHORIZED_ISSUERS:
            failures.append(
                f"authorized_by must be one of the pinned issuers "
                f"{sorted(AUTHORIZED_ISSUERS)}"
            )
        if self.authorized and (
            len(self.authorization_hmac) != 64
            or any(c not in "0123456789abcdef" for c in self.authorization_hmac)
        ):
            failures.append(
                "authorized records require a 64-hex authorization_hmac"
            )
        try:
            from datetime import datetime

            datetime.fromisoformat(self.authorized_at)
        except (ValueError, TypeError):
            failures.append("authorized_at must be an ISO-8601 timestamp")
        return failures

    def canonical_authorization_bytes(
        self, authorization_key: bytes
    ) -> tuple[bytes, str]:
        """Return (canonical bytes, expected HMAC hex) under ``key``.

        The canonical record covers every field except the HMAC itself,
        serialized deterministically.
        """

        import dataclasses

        record_without_hmac = {
            key_: value
            for key_, value in dataclasses.asdict(self).items()
            if key_ != "authorization_hmac"
        }
        expected = hmac.new(
            authorization_key,
            canonical_json_bytes(record_without_hmac),
            hashlib.sha256,
        ).hexdigest()
        return (
            canonical_json_bytes(record_without_hmac),
            expected,
        )


@dataclass(frozen=True, slots=True)
class DisabledTransport:
    """The default transport: every send is refused before anything happens."""

    reason: str = "connection disabled by default; no authorized record bound"

    def send(self, label: str, payload: dict[str, Any]) -> dict[str, Any]:
        raise TransportDisabled(self.reason)


def disabled_transport() -> DisabledTransport:
    """Return the default disabled transport."""

    return DisabledTransport()


def resolve_running_commit(repo_root: Path) -> str:
    """Resolve the running operational commit from the repository itself."""

    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_root,
        capture_output=True,
        check=True,
    )
    return result.stdout.decode().strip()


class ZaiQualificationTransport:
    """One isolated, meter-enforced live-qualification transport."""

    def __init__(
        self,
        *,
        record: QualificationAuthorizationRecord,
        ledger: PersistentSendLedger,
        credential_provider: Callable[[], str],
        repo_root: Path,
        authorization_key_provider: Callable[[], bytes],
        ledger_base_dir: Path,
        http_post: Callable[[str, str, dict[str, Any], float], tuple[int, str]] | None = None,
    ) -> None:
        failures = record.validation_failures()
        if record.science_anchor_digest != SCIENCE_ANCHOR_DIGEST:
            failures.append("record is not bound to the frozen science anchor")
        if ledger.send_cap != record.send_cap:
            failures.append("ledger cap does not match the authorized send cap")
        if ledger.authorization_id != record.authorization_id:
            failures.append(
                "ledger is bound to a different authorization id than the record"
            )

        # One balance per authorization: the ledger file must sit at the
        # canonical path derived from the record's pinned ledger_base_dir
        # and authorization id - a second file with the same id cannot
        # start a fresh balance.
        from .send_ledger import qualification_ledger_path

        expected_path = qualification_ledger_path(
            record.ledger_base_dir, record.authorization_id
        )
        if ledger.path.resolve() != expected_path.resolve():
            failures.append(
                "ledger path is not the canonical custody path for this "
                "authorization id"
            )

        # The running operational commit is resolved from the repository
        # itself, before any credential is fetched - a record naming a
        # different commit is refused regardless of its other content.
        running_commit = resolve_running_commit(repo_root)
        if record.code_commit != running_commit:
            failures.append(
                "record code_commit does not match the running operational "
                f"commit ({running_commit})"
            )

        # Cryptographic issuer proof: the HMAC must verify under the
        # operator-held key, so a forged authorized record cannot enable
        # the transport even when constructed programmatically.
        if record.authorized:
            if authorization_key_provider is None:
                failures.append(
                    "an authorized record requires authorization_key_provider"
                )
            else:
                key = authorization_key_provider()
                _, expected_hmac = record.canonical_authorization_bytes(key)
                if record.authorization_hmac != expected_hmac:
                    failures.append("authorization signature does not verify")

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
        # Redirects are refused: a redirect could carry the Authorization
        # header to a different host. The response URL must also equal the
        # requested URL exactly.
        opener = urllib.request.build_opener(_RefuseRedirect)
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
            with opener.open(request, timeout=timeout_seconds) as response:
                final_url = response.geturl()
                if final_url != url:
                    raise QualificationTransportError(
                        "provider redirected to a different URL; refusing"
                    )
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
            raise QualificationTransportError(
                "provider send timed out (consumed)"
            ) from None
        except Exception as error:
            self._ledger.record_outcome(label, payload_sha, "unknown-outcome")
            # Hygiene: only the error CLASS is surfaced. The original
            # message could contain credentials or provider internals and
            # is deliberately not embedded here or in the ledger.
            raise QualificationTransportError(
                f"provider send failed with an unknown outcome "
                f"(consumed; error class withheld: {type(error).__name__})"
            ) from None

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
