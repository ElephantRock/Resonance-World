"""Live-transport qualification tests: fail-closed metering, no network.

Every test injects a fake ``http_post`` - no real network call exists
on any path. The tests prove the reviewer's round-4 and round-5
requirements plus the round-6 canonical-custody-path enforcement.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys as _sys
from pathlib import Path

import pytest

from resonance_world.experimental_runtime.g1_v9 import (
    PhysicalSendCapExceeded,
    build_authorization_candidate,
    qualification_ledger_path,
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

OPERATOR_KEY = b"operator-held-qualification-key"
REPO_ROOT = Path(__file__).resolve().parents[1]
ENDPOINT = "https://api.z.ai/api/coding/paas/v4/chat/completions"
AUTHORIZATION_ID = "a" * 64


def _git_head() -> str:
    return (
        subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=REPO_ROOT,
            capture_output=True,
            check=True,
        )
        .stdout.decode()
        .strip()
    )


def authorized_record(**overrides) -> QualificationAuthorizationRecord:
    """Build a valid authorized record signed under OPERATOR_KEY and
    bound to the running operational commit."""

    import hashlib
    import hmac

    values = dict(
        schema="g1-v9-qualification-authorization-v1",
        status="authorized",
        science_anchor_digest=SCIENCE_ANCHOR_DIGEST,
        code_commit=_git_head(),
        authorization_id=AUTHORIZATION_ID,
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
        authorization_hmac="",
        notes=(),
    )
    values.update(overrides)
    if not values["authorization_hmac"]:
        # Auto-sign under the operator key (HMAC, matching the transport's
        # canonical_authorization_bytes verification path) unless a
        # forged signature was injected explicitly by the test.
        without_hmac = {
            key: value for key, value in values.items() if key != "authorization_hmac"
        }
        values["authorization_hmac"] = hmac.new(
            OPERATOR_KEY,
            json.dumps(without_hmac, sort_keys=True, separators=(",", ":")).encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
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
    ledger = PersistentSendLedger(
        qualification_ledger_path(tmp_path, record.authorization_id),
        send_cap=record.send_cap,
        authorization_id=record.authorization_id,
    )
    credential = lambda: "test-key-not-a-secret"  # noqa: E731
    transport = ZaiQualificationTransport(
        record=record,
        ledger=ledger,
        credential_provider=credential,
        repo_root=REPO_ROOT,
        ledger_base_dir=tmp_path,
        authorization_key_provider=lambda: OPERATOR_KEY,
        http_post=fake_http,
    )
    return ledger, transport


# -- disabled by default --------------------------------------------------


def test_default_transport_is_disabled() -> None:
    with pytest.raises(TransportDisabled):
        disabled_transport().send("anything", {})


# -- authorization source trust ------------------------------------------


def test_transport_cannot_be_constructed_from_a_candidate_record(tmp_path) -> None:
    """The unauthorized candidate record can never enable the transport."""

    candidate = build_authorization_candidate(
        code_commit=_git_head(), endpoint_url=ENDPOINT
    )
    assert candidate.authorized is False
    failures = candidate.validation_failures()
    assert any("authorized must be true" in failure for failure in failures)

    ledger = PersistentSendLedger(
        tmp_path / "l.jsonl",
        send_cap=8,
        authorization_id=AUTHORIZATION_ID,
    )
    with pytest.raises(TransportNotAuthorized, match="authorized must be true"):
        ZaiQualificationTransport(
            record=candidate,
            ledger=ledger,
            credential_provider=lambda: "key",
            repo_root=REPO_ROOT,
            ledger_base_dir=tmp_path,
            authorization_key_provider=lambda: OPERATOR_KEY,
        )
    assert ledger.attempts() == 0


def test_forged_authorized_record_is_rejected(tmp_path) -> None:
    """P0: an authorized=True record with a forged (unsigned) HMAC is
    rejected cryptographically, not just shape-checked."""

    record = authorized_record(authorization_hmac="f" * 64)  # forged signature
    ledger = PersistentSendLedger(
        tmp_path / "l.jsonl", send_cap=8, authorization_id=AUTHORIZATION_ID
    )
    with pytest.raises(TransportNotAuthorized, match="signature does not verify"):
        ZaiQualificationTransport(
            record=record,
            ledger=ledger,
            credential_provider=lambda: "key",
            repo_root=REPO_ROOT,
            ledger_base_dir=tmp_path,
            authorization_key_provider=lambda: OPERATOR_KEY,
        )


def test_record_signed_under_a_different_key_is_rejected(tmp_path) -> None:
    """Re-signing under an attacker key yields a perfect-shape record that
    still fails verification under the operator key."""

    import dataclasses
    import hashlib
    import hmac as hmac_module

    attacker_key = b"attacker-key-not-the-operators"
    base = authorized_record()
    canonical = {
        key_: value
        for key_, value in dataclasses.asdict(base).items()
        if key_ != "authorization_hmac"
    }
    forged_hmac = hmac_module.new(
        attacker_key,
        json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    record = dataclasses.replace(base, authorization_hmac=forged_hmac)

    ledger = PersistentSendLedger(
        tmp_path / "l2.jsonl", send_cap=8, authorization_id=AUTHORIZATION_ID
    )
    with pytest.raises(TransportNotAuthorized, match="signature does not verify"):
        ZaiQualificationTransport(
            record=record,
            ledger=ledger,
            credential_provider=lambda: "key",
            repo_root=REPO_ROOT,
            ledger_base_dir=tmp_path,
            authorization_key_provider=lambda: OPERATOR_KEY,
        )


def test_transport_rejects_a_wrong_science_anchor(tmp_path) -> None:
    wrong_anchor = authorized_record(science_anchor_digest="b" * 64)
    ledger = PersistentSendLedger(
        tmp_path / "l.jsonl", send_cap=8, authorization_id=AUTHORIZATION_ID
    )
    with pytest.raises(TransportNotAuthorized, match="science anchor"):
        ZaiQualificationTransport(
            record=wrong_anchor,
            ledger=ledger,
            credential_provider=lambda: "key",
            repo_root=REPO_ROOT,
            ledger_base_dir=tmp_path,
            authorization_key_provider=lambda: OPERATOR_KEY,
        )


def test_transport_rejects_a_cap_other_than_eight(tmp_path) -> None:
    wrong_cap = authorized_record(send_cap=420)
    ledger = PersistentSendLedger(
        tmp_path / "l.jsonl", send_cap=8, authorization_id=AUTHORIZATION_ID
    )
    with pytest.raises(TransportNotAuthorized, match="exactly 8"):
        ZaiQualificationTransport(
            record=wrong_cap,
            ledger=ledger,
            credential_provider=lambda: "key",
            repo_root=REPO_ROOT,
            ledger_base_dir=tmp_path,
            authorization_key_provider=lambda: OPERATOR_KEY,
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
    record = authorized_record()
    ledger = PersistentSendLedger(
        qualification_ledger_path(tmp_path, record.authorization_id),
        send_cap=8,
        authorization_id=record.authorization_id,
    )
    transport = ZaiQualificationTransport(
        record=record,
        ledger=ledger,
        credential_provider=lambda: "key",
        repo_root=REPO_ROOT,
        ledger_base_dir=tmp_path,
        authorization_key_provider=lambda: OPERATOR_KEY,
        http_post=lambda url, key, body, timeout: (
            200,
            '{"choices":[{"message":{"content":"ok"}}]}',
        ),
    )
    for index in range(8):
        transport.send(f"probe-{index}", "ping")
    assert ledger.attempts() == 8

    # Process restart: a brand-new ledger/transport over the same file.
    restarted_ledger = PersistentSendLedger(
        qualification_ledger_path(tmp_path, record.authorization_id),
        send_cap=8,
        authorization_id=record.authorization_id,
    )
    restarted_transport = ZaiQualificationTransport(
        record=record,
        ledger=restarted_ledger,
        credential_provider=lambda: "key",
        repo_root=REPO_ROOT,
        ledger_base_dir=tmp_path,
        authorization_key_provider=lambda: OPERATOR_KEY,
        http_post=lambda url, key, body, timeout: (200, '{"choices":[]}'),
    )
    assert restarted_ledger.attempts() == 8
    with pytest.raises(PhysicalSendCapExceeded):
        restarted_transport.send("probe-9", "ping")
    assert restarted_ledger.attempts() == 8


def test_crashed_final_write_is_conservatively_consumed(tmp_path) -> None:
    record = authorized_record()
    store_path = qualification_ledger_path(tmp_path, record.authorization_id)
    ledger = PersistentSendLedger(store_path, send_cap=8, authorization_id=record.authorization_id)
    ledger.record_attempt("crash-probe", "deadbeef")
    with store_path.open("a", encoding="utf-8") as handle:
        handle.write('{"seq": 2, "action": "suc')  # crash mid-write

    reloaded = PersistentSendLedger(
        store_path, send_cap=8, authorization_id=record.authorization_id
    )
    assert reloaded.truncated_tail is True
    # The truncated write is conservatively consumed against the cap.
    assert reloaded.attempts() == 2
    assert 8 - reloaded.attempts() == 6


def test_ledger_rejects_a_broken_chain(tmp_path) -> None:
    record = authorized_record()
    store_path = qualification_ledger_path(tmp_path, record.authorization_id)
    ledger = PersistentSendLedger(store_path, send_cap=8, authorization_id=record.authorization_id)
    ledger.record_attempt("probe", "x")
    good_lines = store_path.read_text(encoding="utf-8").splitlines()
    # Tamper the first CONTENT entry's label, keeping the header and the
    # stored hash: history rewrite must be detected by the content digest.
    attempt = json.loads(good_lines[1])
    attempt["label"] = "rewritten-history"
    store_path.write_text(
        good_lines[0] + "\n" + json.dumps(attempt, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(LedgerCorrupted):
        PersistentSendLedger(store_path, send_cap=8, authorization_id=record.authorization_id)


# ---------------------------------------------------------------------------
# Review round 5: real concurrency, repeated crashes, redirect & hygiene
# ---------------------------------------------------------------------------

_CHILD_CONSUME = """
import sys
from resonance_world.experimental_runtime.g1_v9.send_ledger import (
    PersistentSendLedger, PhysicalSendCapExceeded,
)
ledger = PersistentSendLedger(sys.argv[1], send_cap=1,
                              authorization_id=sys.argv[2])
try:
    ledger.record_attempt("child", "payload")
    sys.exit(0)
except PhysicalSendCapExceeded:
    sys.exit(3)
"""


def test_two_processes_race_for_the_final_slot(tmp_path) -> None:
    """P0: two concurrent processes race for one slot; exactly one wins."""


    record = authorized_record()
    store_path = qualification_ledger_path(tmp_path, record.authorization_id)
    PersistentSendLedger(store_path, send_cap=1, authorization_id=record.authorization_id)
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")}
    procs = [
        subprocess.Popen(
            [
                _sys.executable,
                "-c",
                _CHILD_CONSUME,
                str(store_path),
                record.authorization_id,
            ],
            env=env,
        )
        for _ in range(2)
    ]
    codes = [proc.wait() for proc in procs]
    winners = sum(1 for code in codes if code == 0)
    assert winners == 1, codes

    final = PersistentSendLedger(store_path, send_cap=1, authorization_id=record.authorization_id)
    assert final.attempts() == 1


def test_double_truncation_accumulates_consumption_never_shrinks(tmp_path) -> None:
    """P0: two consecutive crashed writes keep consumption accumulating."""

    record = authorized_record()
    store_path = qualification_ledger_path(tmp_path, record.authorization_id)
    ledger = PersistentSendLedger(store_path, send_cap=8, authorization_id=record.authorization_id)
    ledger.record_attempt("first", "p1")
    with store_path.open("a", encoding="utf-8") as handle:
        handle.write('{"seq": 2, "action": "suc')  # first crash

    reloaded = PersistentSendLedger(
        store_path, send_cap=8, authorization_id=record.authorization_id
    )
    assert reloaded.truncated_tail is True
    consumed_after_first = reloaded.attempts()

    with store_path.open("a", encoding="utf-8") as handle:
        handle.write('{"seq": 9, "action": "har')  # second crash

    reloaded2 = PersistentSendLedger(
        store_path, send_cap=8, authorization_id=record.authorization_id
    )
    consumed_after_second = reloaded2.attempts()
    assert consumed_after_second >= consumed_after_first

    # Third and fourth opens: valid chain, balance never grows.
    balances = []
    for _ in range(2):
        again = PersistentSendLedger(
            store_path, send_cap=8, authorization_id=record.authorization_id
        )
        assert again.truncated_tail is True
        balances.append(again.attempts())
    assert balances[0] == balances[1] == consumed_after_second


def test_redirect_is_refused_by_the_transport_handler() -> None:
    from resonance_world.experimental_runtime.g1_v9.zai_transport import (
        _RefuseRedirect,
    )

    with pytest.raises(Exception, match="redirect refused"):
        _RefuseRedirect().redirect_request(
            req=None, fp=None, code=302, msg="moved", headers={}, newurl="https://evil.example/x",
        )


def test_unknown_failure_hides_the_original_message(tmp_path) -> None:
    ledger, transport = make_transport(
        tmp_path, fake_http=FakeHttp(["connection-error"])
    )
    with pytest.raises(Exception) as exc_info:
        transport.send("hygiene-probe", "ping")

    message = str(exc_info.value)
    assert "injected connection failure" not in message
    assert "withheld" in message
