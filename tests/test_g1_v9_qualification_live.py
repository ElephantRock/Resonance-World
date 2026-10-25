"""Live-transport qualification tests: fail-closed metering, no network.

Every test injects a fake ``http_post`` — no real network call exists
on any path. The tests prove the reviewer's round-4 requirements:

- the four preflight failure classes (auth, timeout, malformed, cap)
  are actually injected and each consumes exactly one attempt with no
  retry;
- the persistent ledger survives process restart and refuses the
  ninth attempt;
- a crashed final ledger write is conservatively consumed;
- the transport cannot even be constructed without an authorized
  record bound to the frozen science anchor, and the disabled default
  refuses all sends.
"""

from __future__ import annotations

import json

import pytest

from resonance_world.experimental_runtime.g1_v9 import (
    PhysicalSendCapExceeded,
    build_authorization_candidate,
)
from resonance_world.experimental_runtime.g1_v9.send_ledger import (
    LedgerCorrupted,
    PersistentSendLedger,
)
from resonance_world.experimental_runtime.g1_v9.zai_transport import (
    SCIENCE_ANCHOR_DIGEST,
    QualificationAuthorizationRecord,
    TransportDisabled,
    TransportNotAuthorized,
    ZaiQualificationTransport,
    disabled_transport,
)

CODE_COMMIT = "374249adee81b9909646f54bc544d19cda1dd007"
ENDPOINT = "https://api.z.ai/api/coding/paas/v4/chat/completions"


def authorized_record(**overrides) -> QualificationAuthorizationRecord:
    values = dict(
        schema="g1-v9-qualification-authorization-v1",
        status="authorized",
        science_anchor_digest=SCIENCE_ANCHOR_DIGEST,
        code_commit=CODE_COMMIT,
        provider="zai",
        model="glm-5.3",
        endpoint_family="zai-coding-plan-chat-completions",
        endpoint_url=ENDPOINT,
        send_cap=8,
        max_output_tokens=512,
        timeout_seconds=30.0,
        authorized=True,
        authorized_by="operator",
        authorized_at="2026-10-25T12:00:00+00:00",
        notes=(),
    )
    values.update(overrides)
    return QualificationAuthorizationRecord(**values)


class FakeHttp:
    """Injected HTTP boundary: scripted responses, call accounting."""

    def __init__(self, script):
        self._script = list(script)
        self.calls: list[dict] = []

    def __call__(self, url, api_key, body, timeout_seconds):
        self.calls.append(
            {
                "url": url,
                "auth_header": api_key,
                "body": body,
                "timeout": timeout_seconds,
            }
        )
        action = self._script.pop(0)
        if action == "timeout":
            raise TimeoutError("injected timeout")
        if action == "connection-error":
            raise ConnectionError("injected connection failure")
        status, body_text = action
        return status, body_text


def make_transport(tmp_path, record=None, fake_http=None):
    record = record if record is not None else authorized_record()
    ledger = PersistentSendLedger(tmp_path / "send-ledger.jsonl", send_cap=record.send_cap)
    credential = lambda: "test-key-not-a-secret"  # noqa: E731
    transport = ZaiQualificationTransport(
        record=record,
        ledger=ledger,
        credential_provider=credential,
        http_post=fake_http,
    )
    return ledger, transport


# -- disabled by default --------------------------------------------------


def test_default_transport_is_disabled() -> None:
    with pytest.raises(TransportDisabled):
        disabled_transport().send("anything", {})


def test_transport_cannot_be_constructed_from_a_candidate_record(tmp_path) -> None:
    """The unauthorized candidate record can never enable the transport."""

    candidate = build_authorization_candidate(
        code_commit=CODE_COMMIT, endpoint_url=ENDPOINT
    )
    assert candidate.authorized is False
    failures = candidate.validation_failures()
    assert any("authorized must be true" in failure for failure in failures)

    ledger = PersistentSendLedger(tmp_path / "l.jsonl", send_cap=8)
    with pytest.raises(TransportNotAuthorized, match="authorized must be true"):
        ZaiQualificationTransport(
            record=candidate,
            ledger=ledger,
            credential_provider=lambda: "key",
        )
    assert ledger.attempts() == 0


def test_transport_rejects_a_wrong_science_anchor(tmp_path) -> None:
    wrong_anchor = authorized_record(
        science_anchor_digest="b" * 64,
    )
    ledger = PersistentSendLedger(tmp_path / "l.jsonl", send_cap=8)
    with pytest.raises(TransportNotAuthorized, match="science anchor"):
        ZaiQualificationTransport(
            record=wrong_anchor, ledger=ledger, credential_provider=lambda: "key"
        )


def test_transport_rejects_a_cap_other_than_eight(tmp_path) -> None:
    wrong_cap = authorized_record(send_cap=420)
    ledger = PersistentSendLedger(tmp_path / "l.jsonl", send_cap=8)
    with pytest.raises(TransportNotAuthorized, match="exactly 8"):
        ZaiQualificationTransport(
            record=wrong_cap, ledger=ledger, credential_provider=lambda: "key"
        )


# -- the four preflight failure classes, injected -------------------------


def test_auth_failure_consumes_one_attempt_and_does_not_retry(tmp_path) -> None:
    ledger, transport = make_transport(tmp_path)
    fake = FakeHttp([(401, '{"error": "unauthorized"}')])
    transport._http_post = fake

    with pytest.raises(Exception, match="authentication failed"):
        transport.send("auth-probe", "ping")

    assert len(fake.calls) == 1
    assert ledger.attempts() == 1
    assert ledger.outcomes() == {"auth-failure": 1}


def test_timeout_consumes_the_attempt_and_stops(tmp_path) -> None:
    ledger, transport = make_transport(tmp_path)
    fake = FakeHttp(["timeout"])
    transport._http_post = fake

    with pytest.raises(Exception, match="timed out"):
        transport.send("timeout-probe", "ping")

    assert len(fake.calls) == 1
    assert ledger.attempts() == 1
    assert ledger.outcomes() == {"timeout": 1}


def test_malformed_response_consumes_the_attempt(tmp_path) -> None:
    ledger, transport = make_transport(tmp_path)
    fake = FakeHttp([(200, "this is not json")])
    transport._http_post = fake

    with pytest.raises(Exception, match="malformed"):
        transport.send("malformed-probe", "ping")

    assert len(fake.calls) == 1
    assert ledger.attempts() == 1
    assert ledger.outcomes() == {"malformed-response": 1}


def test_unknown_outcome_is_consumed_fail_closed(tmp_path) -> None:
    ledger, transport = make_transport(tmp_path)
    fake = FakeHttp(["connection-error"])
    transport._http_post = fake

    with pytest.raises(Exception, match="unknown outcome"):
        transport.send("unknown-probe", "ping")

    # The attempt was consumed even though the outcome is unknown.
    assert ledger.attempts() == 1
    assert ledger.outcomes() == {"unknown-outcome": 1}
    assert transport.remaining == 7


# -- cap enforcement and restart -----------------------------------------


def test_ninth_attempt_is_refused_fail_closed(tmp_path) -> None:
    fake = FakeHttp([(200, '{"choices":[{"message":{"content":"ok"}}] }')] * 8)
    ledger, transport = make_transport(tmp_path, fake_http=fake)

    for index in range(8):
        transport.send(f"probe-{index}", "ping")
    assert ledger.attempts() == 8
    assert transport.remaining == 0

    with pytest.raises(PhysicalSendCapExceeded, match="cap exhausted"):
        transport.send("probe-9", "ping")
    assert len(fake.calls) == 8


def test_ledger_rebuild_refuses_after_restart(tmp_path) -> None:
    store_path = tmp_path / "send-ledger.jsonl"
    record = authorized_record()
    ledger = PersistentSendLedger(store_path, send_cap=8)
    transport = ZaiQualificationTransport(
        record=record,
        ledger=ledger,
        credential_provider=lambda: "key",
        http_post=lambda url, key, body, timeout: (
            200,
            '{"choices":[{"message":{"content":"ok"}}]}',
        ),
    )
    for index in range(8):
        transport.send(f"probe-{index}", "ping")
    assert ledger.attempts() == 8

    # Process restart: a brand-new ledger/transport over the same file.
    restarted_ledger = PersistentSendLedger(store_path, send_cap=8)
    restarted_transport = ZaiQualificationTransport(
        record=record, ledger=restarted_ledger, credential_provider=lambda: "key",
        http_post=lambda url, key, body, timeout: (200, '{"choices":[]}'),
    )
    assert restarted_ledger.attempts() == 8
    with pytest.raises(PhysicalSendCapExceeded):
        restarted_transport.send("probe-9", "ping")
    assert restarted_ledger.attempts() == 8


def test_crashed_final_write_is_conservatively_consumed(tmp_path) -> None:
    store_path = tmp_path / "send-ledger.jsonl"
    ledger = PersistentSendLedger(store_path, send_cap=8)
    ledger.record_attempt("crash-probe", "deadbeef")
    with store_path.open("a", encoding="utf-8") as handle:
        handle.write('{"seq": 2, "action": "suc')  # crash mid-write

    reloaded = PersistentSendLedger(store_path, send_cap=8)
    assert reloaded.truncated_tail is True
    # The truncated write is conservatively consumed against the cap.
    assert reloaded.attempts() == 2
    assert 8 - reloaded.attempts() == 6


def test_ledger_rejects_a_broken_chain(tmp_path) -> None:
    store_path = tmp_path / "send-ledger.jsonl"
    ledger = PersistentSendLedger(store_path, send_cap=8)
    ledger.record_attempt("probe", "x")
    good_lines = store_path.read_text(encoding="utf-8").splitlines()
    tampered = json.loads(good_lines[0])
    tampered["label"] = "rewritten-history"
    store_path.write_text(
        json.dumps(tampered, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(LedgerCorrupted):
        PersistentSendLedger(store_path, send_cap=8)