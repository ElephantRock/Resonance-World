from __future__ import annotations

import json

import httpx

import d2_vnext_q3d3_http_observer as observer
import d2_vnext_s2_hermes_client as s2


def test_http_observer_preserves_body_and_records_structure() -> None:
    secret = "SENSITIVE_SYNTHETIC_ASSISTANT_CONTENT"
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        assert request.headers[s2.PROBE_ORIGIN_HEADER] == "3"
        return httpx.Response(
            200,
            json={
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
        )

    recorder = observer.HTTPBodyRecorder()
    client = httpx.Client(transport=httpx.MockTransport(handler))
    with observer.observe_http_response_reads(recorder):
        response = client.get(
            "https://api.z.ai/api/coding/paas/v4/chat/completions",
            headers={s2.PROBE_ORIGIN_HEADER: "3"},
        )
    assert calls == 1
    assert response.json()["choices"][0]["message"]["content"] == secret
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


def test_http_observer_deduplicates_repeated_reads() -> None:
    request = httpx.Request(
        "POST",
        "https://api.z.ai/api/coding/paas/v4/chat/completions",
        headers={s2.PROBE_ORIGIN_HEADER: "0"},
    )
    response = httpx.Response(200, json={"choices": []}, request=request)
    recorder = observer.HTTPBodyRecorder()
    with observer.observe_http_response_reads(recorder):
        first = response.read()
        second = response.read()
    assert first == second
    assert len(recorder.rows(0)) == 1


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
