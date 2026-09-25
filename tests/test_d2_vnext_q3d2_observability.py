from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

import d2_vnext_q3d2_hermes_client as client


def _response(content: str = "structured"):
    message = SimpleNamespace(content=content, tool_calls=[])
    choice = SimpleNamespace(message=message, finish_reason="stop")
    usage = SimpleNamespace(prompt_tokens=5, completion_tokens=3, total_tokens=8)
    return SimpleNamespace(model="glm-5.3", choices=[choice], usage=usage)


class FakeLedger:
    def __init__(self) -> None:
        self._rows: dict[int, list[dict]] = {}

    def rows(self, logical_index: int) -> list[dict]:
        return list(self._rows.get(logical_index, []))

    def record_success(self, logical_index: int) -> None:
        rows = self._rows.setdefault(logical_index, [])
        rows.append(
            {
                "logical_send_index": len(rows) + 1,
                "total_send_index": len(rows) + 1,
                "http_status": 200,
                "transport_error_type": None,
            }
        )


class FakeHermesAgent:
    def __init__(self, factory):
        self._create_request_openai_client = factory
        self._api_call_count = 0

    def _interruptible_api_call(self, api_kwargs: dict):
        self._api_call_count += 1
        request_client = self._create_request_openai_client(
            reason="chat_completion_request"
        )
        return request_client.chat.completions.create(**api_kwargs)


def _request_client(create):
    return SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create))
    )


def test_request_scoped_path_preserves_factory_request_and_response_identity() -> None:
    ledger = FakeLedger()
    response = _response()
    calls: list[tuple] = []
    created: list[dict] = []

    def create(**kwargs):
        calls.append(((), dict(kwargs)))
        ledger.record_success(7)
        return response

    def factory(*args, **kwargs):
        created.append({"args": args, "kwargs": dict(kwargs)})
        return _request_client(create)

    agent = FakeHermesAgent(factory)
    recorder = client.SemanticRecorder()
    original_factory = client.instrument_request_scoped_chat_completions(
        agent,
        agent_invocation_index=1,
        recorder=recorder,
        logical_index=7,
        ledger=ledger,
    )

    kwargs = {"model": "glm-5.3", "messages": [{"role": "user", "content": "x"}]}
    returned = agent._interruptible_api_call(kwargs)

    assert returned is response
    assert original_factory is factory
    assert created == [
        {"args": (), "kwargs": {"reason": "chat_completion_request"}}
    ]
    assert calls == [((), kwargs)]
    assert agent._api_call_count == 1

    rows = recorder.rows()
    client.assert_semantic_coverage(agent._api_call_count, rows)
    assert len(rows) == 1
    assert rows[0]["provider_sends"] == [
        {
            "logical_send_index": 1,
            "total_send_index": 1,
            "http_status": 200,
            "transport_error_type": None,
        }
    ]


def test_each_request_scoped_client_is_instrumented() -> None:
    responses = [_response("one"), _response("two")]
    factory_calls = {"n": 0}

    def factory(*, reason: str):
        index = factory_calls["n"]
        factory_calls["n"] += 1

        def create(**kwargs):
            assert kwargs["model"] == "glm-5.3"
            return responses[index]

        return _request_client(create)

    agent = FakeHermesAgent(factory)
    recorder = client.SemanticRecorder()
    client.instrument_request_scoped_chat_completions(
        agent,
        agent_invocation_index=1,
        recorder=recorder,
    )

    first = agent._interruptible_api_call({"model": "glm-5.3"})
    second = agent._interruptible_api_call({"model": "glm-5.3"})

    assert first is responses[0]
    assert second is responses[1]
    assert factory_calls["n"] == 2
    client.assert_semantic_coverage(2, recorder.rows())


def test_request_exception_is_recorded_and_reraised_unchanged() -> None:
    sentinel = RuntimeError("synthetic request failure")

    def create(**kwargs):
        assert kwargs == {"model": "glm-5.3"}
        raise sentinel

    agent = FakeHermesAgent(lambda **kwargs: _request_client(create))
    recorder = client.SemanticRecorder()
    client.instrument_request_scoped_chat_completions(
        agent,
        agent_invocation_index=2,
        recorder=recorder,
    )

    with pytest.raises(RuntimeError) as caught:
        agent._interruptible_api_call({"model": "glm-5.3"})

    assert caught.value is sentinel
    rows = recorder.rows()
    client.assert_semantic_coverage(1, rows)
    assert rows[0]["semantic_response_observed"] is False
    assert rows[0]["semantic_response_error_type"] == "RuntimeError"


def test_structural_record_retains_no_raw_content() -> None:
    raw = "sensitive-provider-content"
    response = _response(raw)
    agent = FakeHermesAgent(
        lambda **kwargs: _request_client(lambda **request_kwargs: response)
    )
    recorder = client.SemanticRecorder()
    client.instrument_request_scoped_chat_completions(
        agent,
        agent_invocation_index=1,
        recorder=recorder,
    )

    assert agent._interruptible_api_call({"model": "glm-5.3"}) is response
    encoded = json.dumps(recorder.rows(), sort_keys=True)

    assert raw not in encoded
    assert len(recorder.rows()[0]["assistant_content_sha256"]) == 64


def test_positive_api_call_count_with_zero_semantic_records_fails_closed() -> None:
    defects = client.semantic_coverage_defects(2, [])
    assert defects == [
        "semantic_completion_count_mismatch:api_calls=2:semantic_records=0"
    ]
    with pytest.raises(AssertionError, match="semantic coverage failure"):
        client.assert_semantic_coverage(2, [])


def test_semantic_indices_must_be_contiguous() -> None:
    rows = [
        {
            "semantic_response_index": 2,
            "semantic_response_observed": True,
            "semantic_response_error_type": None,
        }
    ]
    assert client.semantic_coverage_defects(1, rows) == [
        "semantic_response_index_sequence_invalid"
    ]
