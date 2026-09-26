from __future__ import annotations

import importlib.metadata
import json
from typing import Any

import pytest

try:
    if importlib.metadata.version("openai") != "2.21.0":
        pytest.skip("Q3-D4 exact-runtime test requires openai==2.21.0", allow_module_level=True)
    if importlib.metadata.version("httpx") != "0.28.1":
        pytest.skip("Q3-D4 exact-runtime test requires httpx==0.28.1", allow_module_level=True)
except importlib.metadata.PackageNotFoundError:
    pytest.skip("Q3-D4 exact-runtime dependencies are not installed", allow_module_level=True)

import httpx
from openai import OpenAI

import d2_vnext_q3d2_hermes_client as q3d2
import d2_vnext_q3d3_http_observer as q3d3
import d2_vnext_q3d4_openai_response_observer as q3d4
import d2_vnext_q3d_hermes_client as q3d


def _payload(secret: str) -> dict[str, Any]:
    return {
        "id": "chatcmpl-q3d4-test",
        "object": "chat.completion",
        "created": 1,
        "model": "glm-5.3",
        "choices": [
            {
                "index": 0,
                "finish_reason": "stop",
                "message": {"role": "assistant", "content": secret},
            }
        ],
        "usage": {
            "prompt_tokens": 11,
            "completion_tokens": 7,
            "total_tokens": 18,
        },
    }


def _client(secret: str, *, extra_headers: dict[str, str] | None = None) -> OpenAI:
    payload = _payload(secret)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload, request=request)

    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    return OpenAI(
        api_key="credential-free-test-key",
        base_url="https://mock.invalid/v1",
        http_client=http_client,
        default_headers=extra_headers,
    )


def _completion(client: OpenAI) -> Any:
    return client.chat.completions.create(
        model="glm-5.3",
        messages=[{"role": "user", "content": "synthetic"}],
        temperature=0.8,
        max_tokens=32,
        response_format={"type": "json_object"},
        extra_body={"thinking": {"type": "disabled"}},
    )


def test_q3d4_exact_openai_httpx_path_adds_no_response_read(monkeypatch: Any) -> None:
    secret = "SENSITIVE_EXACT_RUNTIME_CONTENT"
    original_read = httpx.Response.read
    reads = {"count": 0}

    def counted_read(response: httpx.Response) -> bytes:
        reads["count"] += 1
        return original_read(response)

    monkeypatch.setattr(httpx.Response, "read", counted_read)
    baseline_client = _client(secret)
    try:
        baseline = _completion(baseline_client)
        baseline_reads = reads["count"]
    finally:
        baseline_client.close()

    reads["count"] = 0
    observed_client = _client(secret)
    recorder = q3d4.BufferedResponseRecorder()
    q3d4.instrument_openai_process_response(observed_client, recorder=recorder)
    try:
        observed = _completion(observed_client)
        observed_reads = reads["count"]
    finally:
        observed_client.close()

    assert observed.model == baseline.model == "glm-5.3"
    assert observed.choices[0].message.content == baseline.choices[0].message.content == secret
    assert observed_reads == baseline_reads
    rows = recorder.rows()
    assert len(rows) == 1
    assert rows[0]["stream_consumed_before_observer"] is True
    assert rows[0]["assistant_content_present"] is True
    assert rows[0]["assistant_content_length"] == len(secret)
    assert rows[0]["observability_defects"] == []
    assert secret not in json.dumps(rows, sort_keys=True)


def test_q3d3_read_hook_is_reachable_in_exact_openai_httpx_path() -> None:
    secret = "SENSITIVE_Q3D3_FORENSIC_CONTENT"
    client = _client(
        secret,
        extra_headers={"X-Resonance-World-Logical-Index": "0"},
    )
    recorder = q3d3.HTTPBodyRecorder()
    try:
        with q3d3.observe_http_response_reads(recorder):
            result = _completion(client)
    finally:
        client.close()

    assert result.choices[0].message.content == secret
    rows = recorder.rows(0)
    assert len(rows) == 1
    assert rows[0]["assistant_content_present"] is True
    assert secret not in json.dumps(rows, sort_keys=True)


def test_pinned_hermes_interruptible_path_preserves_q3d2_and_q3d4_observers() -> None:
    from run_agent import AIAgent

    secret = "SENSITIVE_PINNED_HERMES_CONTENT"
    created_clients: list[OpenAI] = []

    def factory(*, reason: str) -> OpenAI:
        assert reason == "chat_completion_request"
        client = _client(secret)
        created_clients.append(client)
        return client

    def close_client(client: OpenAI, *, reason: str) -> None:
        assert reason == "request_complete"
        client.close()

    agent = object.__new__(AIAgent)
    agent.api_mode = "chat_completions"
    agent._interrupt_requested = False
    agent._create_request_openai_client = factory
    agent._close_request_openai_client = close_client

    semantic = q3d.SemanticRecorder()
    buffered = q3d4.BufferedResponseRecorder()
    q3d2.instrument_request_scoped_chat_completions(
        agent,
        agent_invocation_index=1,
        recorder=semantic,
    )
    q3d4.instrument_current_request_factory_after_q3d2(agent, recorder=buffered)

    result = AIAgent._interruptible_api_call(
        agent,
        {
            "model": "glm-5.3",
            "messages": [{"role": "user", "content": "synthetic"}],
            "temperature": 0.8,
            "max_tokens": 32,
            "response_format": {"type": "json_object"},
            "extra_body": {"thinking": {"type": "disabled"}},
        },
    )

    assert len(created_clients) == 1
    assert result.choices[0].message.content == secret
    semantic_rows = semantic.rows()
    buffered_rows = buffered.rows()
    assert len(semantic_rows) == 1
    assert len(buffered_rows) == 1
    assert semantic_rows[0]["assistant_content_present"] is True
    assert buffered_rows[0]["assistant_content_present"] is True
    assert q3d4.coverage_defects(buffered_rows, semantic_rows) == []
    combined = json.dumps({"semantic": semantic_rows, "buffered": buffered_rows}, sort_keys=True)
    assert secret not in combined
