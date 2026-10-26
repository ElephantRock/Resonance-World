"""Direct research probe tests: the owner-approved, signature-free path.

The direct path skips HMAC/issuer/git-pin ceremony by explicit owner
decision (2026-10-26) but MUST keep the operational guarantees:

- the pinned Z.AI endpoint and glm-5.3 model;
- durable attempt consumption BEFORE the HTTP call (unknown outcomes
  count against the cap);
- no automatic retries;
- the eight-attempt cap that survives process reconstruction against
  the same custody directory (no balance reset);
- refusal of relative custody directories.

Every test injects a fake ``http_post`` - no real network call exists.
"""

from __future__ import annotations

import pytest

from resonance_world.experimental_runtime.g1_v9.send_ledger import (
    PhysicalSendCapExceeded,
)
from resonance_world.experimental_runtime.g1_v9.zai_transport import (
    PINNED_ENDPOINT_URL,
    QualificationTransportError,
    start_direct_probe,
)

OK_RESPONSE = (200, '{"choices":[{"message":{"content":"OK"}}]}')


class FakeHttp:
    def __init__(self, script):
        self._script = list(script)
        self.calls: list[dict] = []

    def __call__(self, url, api_key, body, timeout_seconds):
        self.calls.append({"url": url, "body": body})
        action = self._script.pop(0)
        if action == "timeout":
            raise TimeoutError("injected timeout")
        if action == "connection-error":
            raise ConnectionError("injected connection failure")
        return action


def test_direct_probe_consumes_attempt_and_uses_pinned_endpoint(tmp_path) -> None:
    fake = FakeHttp([OK_RESPONSE])
    transport = start_direct_probe(
        ledger_base_dir=tmp_path,
        credential_provider=lambda: "key",
        http_post=fake,
    )
    result = transport.send("connectivity", "Reply with exactly OK.")

    assert result["status"] == 200
    assert len(fake.calls) == 1
    assert fake.calls[0]["url"] == PINNED_ENDPOINT_URL
    assert fake.calls[0]["body"]["model"] == "glm-5.3"
    assert fake.calls[0]["body"]["max_tokens"] == 512
    assert transport.remaining == 7


def test_direct_probe_never_retries_and_consumes_unknown_outcome(tmp_path) -> None:
    fake = FakeHttp(["connection-error"])
    transport = start_direct_probe(
        ledger_base_dir=tmp_path,
        credential_provider=lambda: "key",
        http_post=fake,
    )
    with pytest.raises(QualificationTransportError, match="unknown outcome"):
        transport.send("connectivity", "ping")

    # Exactly one HTTP call: no automatic retry. The attempt is consumed.
    assert len(fake.calls) == 1
    assert transport.remaining == 7


def test_direct_probe_timeout_is_consumed_fail_closed(tmp_path) -> None:
    fake = FakeHttp(["timeout"])
    transport = start_direct_probe(
        ledger_base_dir=tmp_path,
        credential_provider=lambda: "key",
        http_post=fake,
    )
    with pytest.raises(QualificationTransportError, match="timed out"):
        transport.send("connectivity", "ping")

    assert transport.remaining == 7


def test_direct_probe_cap_survives_transport_reconstruction(tmp_path) -> None:
    """P0: recreating the transport against the same custody directory
    must NEVER reset the consumed balance."""

    first = start_direct_probe(
        ledger_base_dir=tmp_path,
        credential_provider=lambda: "key",
        http_post=FakeHttp([OK_RESPONSE] * 8),
    )
    for index in range(8):
        first.send(f"probe-{index}", "ping")
    assert first.remaining == 0

    # Fresh transport, same custody directory: the balance persists.
    second = start_direct_probe(
        ledger_base_dir=tmp_path,
        credential_provider=lambda: "key",
        http_post=FakeHttp([OK_RESPONSE]),
    )
    with pytest.raises(PhysicalSendCapExceeded, match="cap exhausted"):
        second.send("probe-9", "ping")
    assert second.remaining == 0


def test_direct_probe_refuses_relative_custody_dir() -> None:
    with pytest.raises(ValueError, match="absolute"):
        start_direct_probe(
            ledger_base_dir="relative/custody",
            credential_provider=lambda: "key",
        )
