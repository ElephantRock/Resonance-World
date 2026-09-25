from __future__ import annotations

import asyncio
import json
import sys
import types
from typing import Any

import d2_vnext_q3d3_http_observer as observer
import d2_vnext_s2_hermes_client as s2


class FakeRequest:
    def __init__(self, headers: dict[str, str]) -> None:
        self.headers = dict(headers)


class FakeResponse:
    def __init__(
        self,
        *,
        body: bytes,
        logical_index: int,
        status_code: int = 200,
        content_type: str = "application/json; charset=utf-8",
    ) -> None:
        self._body = body
        self.status_code = status_code
        self.headers = {"content-type": content_type}
        self.request = FakeRequest({s2.PROBE_ORIGIN_HEADER: str(logical_index)})
        self.read_calls = 0
        self.aread_calls = 0

    def read(self) -> bytes:
        self.read_calls += 1
        return self._body

    async def aread(self) -> bytes:
        self.aread_calls += 1
        return self._body


def _install_fake_httpx(monkeypatch: Any) -> None:
    module = types.ModuleType("httpx")
    module.Response = FakeResponse
    monkeypatch.setitem(sys.modules, "httpx", module)


def _payload(secret: str) -> bytes:
    return json.dumps(
        {
            "model": "glm-5.3",
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {"role": "assistant", "content": secret},
                }
            ],
            "usage": {
                "prompt_tokens": 11,
                "completion_tokens": 7,
                "total_tokens": 18,
            },
        },
        separators=(",", ":"),
    ).encode()


def test_http_observer_preserves_body_and_records_structure(monkeypatch: Any) -> None:
    _install_fake_httpx(monkeypatch)
    secret = "SENSITIVE_SYNTHETIC_ASSISTANT_CONTENT"
    response = FakeResponse(body=_payload(secret), logical_index=3)
    headers_before = dict(response.request.headers)
    recorder = observer.HTTPBodyRecorder()

    with observer.observe_http_response_reads(recorder):
        observed = response.read()

    assert observed is response._body
    assert response.read_calls == 1
    assert response.request.headers == headers_before
    rows = recorder.rows(3)
    assert len(rows) == 1
    row = rows[0]
    assert row["logical_send_index"] == 1
    assert row["http_status"] == 200
    assert row["json_decode_success"] is True
    assert row["choice_count"] == 1
    assert row["assistant_content_present"] is True
    assert row["assistant_content_type"] == "string"
    assert row["assistant_content_length"] == len(secret)
    assert row["assistant_content_sha256"] is not None
    assert row["usage_total_tokens"] == 18
    assert secret not in json.dumps(rows, sort_keys=True)


def test_http_observer_deduplicates_repeated_reads(monkeypatch: Any) -> None:
    _install_fake_httpx(monkeypatch)
    response = FakeResponse(body=b'{"choices":[]}', logical_index=0)
    recorder = observer.HTTPBodyRecorder()

    with observer.observe_http_response_reads(recorder):
        first = response.read()
        second = response.read()

    assert first == second == response._body
    assert response.read_calls == 2
    assert len(recorder.rows(0)) == 1


def test_http_observer_preserves_async_read(monkeypatch: Any) -> None:
    _install_fake_httpx(monkeypatch)
    response = FakeResponse(body=b'{"choices":[]}', logical_index=2)
    recorder = observer.HTTPBodyRecorder()

    async def run() -> bytes:
        with observer.observe_http_response_reads(recorder):
            return await response.aread()

    observed = asyncio.run(run())
    assert observed is response._body
    assert response.aread_calls == 1
    assert len(recorder.rows(2)) == 1


def test_http_transport_coverage_is_exact_and_fail_closed() -> None:
    transport_rows = [
        {
            "logical_send_index": 1,
            "http_status": 500,
            "transport_error_type": None,
        },
        {
            "logical_send_index": 2,
            "http_status": 200,
            "transport_error_type": None,
        },
    ]
    http_rows = [
        {"logical_send_index": 1, "http_status": 500},
        {"logical_send_index": 2, "http_status": 200},
    ]
    assert observer.http_transport_coverage_defects(transport_rows, http_rows) == []
    defects = observer.http_transport_coverage_defects(transport_rows, http_rows[:1])
    assert defects and defects[0].startswith("http_transport_sequence_mismatch")


def test_semantic_http_association_is_fail_closed() -> None:
    semantic_rows = [
        {
            "semantic_response_observed": True,
            "provider_sends": [
                {
                    "logical_send_index": 1,
                    "http_status": 200,
                    "transport_error_type": None,
                }
            ],
        }
    ]
    assert observer.semantic_http_association_defects(
        semantic_rows,
        [{"logical_send_index": 1, "http_status": 200}],
    ) == []
    defects = observer.semantic_http_association_defects(semantic_rows, [])
    assert defects == ["semantic_http_body_association_missing:[1]"]


def test_boundary_localizes_http_absence_before_sdk() -> None:
    classification = observer.classify_upstream_boundary(
        runtime_exception=False,
        http_body={"json_decode_success": True, "assistant_content_present": False},
        sdk_semantic={
            "semantic_response_observed": True,
            "assistant_content_present": False,
        },
        hermes_terminal_present=False,
        adapter_candidate_present=False,
        parse_valid=False,
        accepted_exact_completion=False,
    )
    assert classification == "http_body_content_absent"


def test_boundary_distinguishes_http_present_sdk_absent() -> None:
    classification = observer.classify_upstream_boundary(
        runtime_exception=False,
        http_body={"json_decode_success": True, "assistant_content_present": True},
        sdk_semantic={
            "semantic_response_observed": True,
            "assistant_content_present": False,
        },
        hermes_terminal_present=False,
        adapter_candidate_present=False,
        parse_valid=False,
        accepted_exact_completion=False,
    )
    assert classification == "http_body_content_present_sdk_content_absent"
