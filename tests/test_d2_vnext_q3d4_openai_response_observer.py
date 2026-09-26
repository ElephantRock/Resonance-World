from __future__ import annotations

import json

import d2_vnext_q3d4_openai_response_observer as observer


class FakeResponse:
    def __init__(self, body: bytes, *, consumed: bool = True) -> None:
        self.status_code = 200
        self.headers = {"content-type": "application/json; charset=utf-8"}
        self.is_stream_consumed = consumed
        self._body = body
        self.content_accesses = 0

    @property
    def content(self) -> bytes:
        self.content_accesses += 1
        if not self.is_stream_consumed:
            raise AssertionError("observer must not access unbuffered content")
        return self._body


class FakeClient:
    def __init__(self) -> None:
        self.calls = 0
        self.result = object()

    def _process_response(self, *, response: FakeResponse, **kwargs: object) -> object:
        self.calls += 1
        return self.result


def _body(secret: str) -> bytes:
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


def test_buffered_observer_preserves_result_and_retains_no_raw_content() -> None:
    secret = "SENSITIVE_SYNTHETIC_ASSISTANT_CONTENT"
    response = FakeResponse(_body(secret))
    client = FakeClient()
    recorder = observer.BufferedResponseRecorder()
    original = observer.instrument_openai_process_response(client, recorder=recorder)

    result = client._process_response(response=response, cast_to=dict, options=object())

    assert callable(original)
    assert result is client.result
    assert client.calls == 1
    assert response.content_accesses == 1
    rows = recorder.rows()
    assert len(rows) == 1
    row = rows[0]
    assert row["stream_consumed_before_observer"] is True
    assert row["json_decode_success"] is True
    assert row["choice_count"] == 1
    assert row["assistant_content_present"] is True
    assert row["assistant_content_length"] == len(secret)
    assert row["assistant_content_sha256"] is not None
    assert row["usage_total_tokens"] == 18
    assert row["observability_defects"] == []
    assert secret not in json.dumps(rows, sort_keys=True)


def test_unbuffered_response_fails_closed_without_touching_content() -> None:
    response = FakeResponse(b"{}", consumed=False)
    client = FakeClient()
    recorder = observer.BufferedResponseRecorder()
    observer.instrument_openai_process_response(client, recorder=recorder)

    result = client._process_response(response=response)

    assert result is client.result
    assert client.calls == 1
    assert response.content_accesses == 0
    rows = recorder.rows()
    assert rows[0]["observability_defects"] == [
        "response_not_buffered_before_openai_process_response"
    ]


def test_missing_response_is_recorded_without_changing_original_call() -> None:
    class NoResponseClient:
        def __init__(self) -> None:
            self.calls = 0
            self.result = object()

        def _process_response(self, *args: object, **kwargs: object) -> object:
            self.calls += 1
            return self.result

    client = NoResponseClient()
    recorder = observer.BufferedResponseRecorder()
    observer.instrument_openai_process_response(client, recorder=recorder)

    result = client._process_response(cast_to=dict)

    assert result is client.result
    assert client.calls == 1
    assert recorder.rows()[0]["observability_defects"] == [
        "openai_process_response_missing_httpx_response"
    ]


def test_factory_wrapper_calls_current_factory_once_and_returns_same_client() -> None:
    calls: list[tuple[tuple[object, ...], dict[str, object]]] = []
    request_client = FakeClient()

    class Agent:
        def _create_request_openai_client(self, *args: object, **kwargs: object) -> FakeClient:
            calls.append((args, kwargs))
            return request_client

    agent = Agent()
    recorder = observer.BufferedResponseRecorder()
    original_factory = observer.instrument_current_request_factory_after_q3d2(
        agent, recorder=recorder
    )

    result = agent._create_request_openai_client("x", reason="chat_completion_request")

    assert callable(original_factory)
    assert result is request_client
    assert calls == [(("x",), {"reason": "chat_completion_request"})]


def test_coverage_requires_one_buffered_row_per_observed_semantic_response() -> None:
    buffered = [
        {
            "response_index": 1,
            "observability_defects": [],
        }
    ]
    semantic = [
        {"semantic_response_observed": True},
        {"semantic_response_observed": False},
    ]
    assert observer.coverage_defects(buffered, semantic) == []
    defects = observer.coverage_defects([], semantic)
    assert defects == ["buffered_semantic_count_mismatch:buffered=0:observed_semantic=1"]
