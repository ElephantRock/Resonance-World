"""Credential-free Q3-D3 observer for the HTTP-body -> SDK boundary.

The observer decorates ``httpx.Response.read`` / ``aread`` only. It calls the
original method exactly once, records bounded structural metadata from the bytes
already requested by HTTPX/OpenAI, and returns those exact bytes unchanged.
It does not create requests and does not authorize provider/model execution.
"""
from __future__ import annotations

import copy
import hashlib
import json
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import d2_vnext_q3d_hermes_client as q3d
import d2_vnext_s2_hermes_client as s2

FORBIDDEN_RAW_KEYS = q3d.FORBIDDEN_RAW_KEYS | {
    "body",
    "body_bytes",
    "body_text",
    "content_bytes",
    "content_text",
}


def _sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha_text(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _value_snapshot(value: Any) -> dict[str, Any]:
    if value is None:
        return {"present": False, "type": "null", "length": 0, "sha256": None}
    if isinstance(value, str):
        return {
            "present": bool(value),
            "type": "string",
            "length": len(value),
            "sha256": _sha_text(value) if value else None,
        }
    if isinstance(value, list):
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
        return {
            "present": bool(value),
            "type": "list",
            "length": len(value),
            "sha256": _sha_text(encoded) if value else None,
        }
    if isinstance(value, dict):
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
        return {
            "present": bool(value),
            "type": "object",
            "length": len(value),
            "sha256": _sha_text(encoded) if value else None,
        }
    encoded = str(value)
    return {
        "present": True,
        "type": "other",
        "length": len(encoded),
        "sha256": _sha_text(encoded),
    }


def _json_type(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, dict):
        return "object"
    if isinstance(value, list):
        return "array"
    if isinstance(value, str):
        return "string"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    return "other"


def _int_or_none(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        return int(value)
    except (TypeError, ValueError, OverflowError):
        return None


def assert_no_raw_content(value: Any) -> None:
    if isinstance(value, dict):
        overlap = FORBIDDEN_RAW_KEYS & set(value)
        if overlap:
            raise AssertionError(f"raw-content field leaked into Q3-D3 evidence: {sorted(overlap)}")
        for nested in value.values():
            assert_no_raw_content(nested)
    elif isinstance(value, list):
        for nested in value:
            assert_no_raw_content(nested)


def _origin_from_response(response: Any) -> int:
    request = getattr(response, "request", None)
    headers = getattr(request, "headers", None)
    raw = headers.get(s2.PROBE_ORIGIN_HEADER) if headers is not None else None
    try:
        origin = int(raw) if raw is not None else -1
    except (TypeError, ValueError):
        origin = -1
    if origin < 0:
        raise AssertionError("Q3-D3 HTTP response lacks valid logical-origin header")
    return origin


def http_body_structural_view(
    response: Any,
    body: bytes,
    *,
    logical_index: int,
    logical_send_index: int,
) -> dict[str, Any]:
    """Return a bounded structural view without retaining response bytes/text."""
    status = int(response.status_code)
    headers = getattr(response, "headers", {})
    raw_content_type = headers.get("content-type") if headers is not None else None
    media_type = (
        str(raw_content_type).split(";", 1)[0].strip().lower()
        if raw_content_type is not None
        else None
    )
    view: dict[str, Any] = {
        "logical_index": logical_index,
        "logical_send_index": logical_send_index,
        "http_status": status,
        "response_byte_length": len(body),
        "response_sha256": _sha_bytes(body) if body else None,
        "content_type_media_type": media_type,
        "json_decode_success": False,
        "json_top_level_type": "decode_failure",
        "top_level_has_choices": False,
        "choice_count": None,
        "first_choice_present": False,
        "finish_reason_present": False,
        "finish_reason": None,
        "assistant_message_present": False,
        "assistant_content_present": False,
        "assistant_content_type": "null",
        "assistant_content_length": 0,
        "assistant_content_sha256": None,
        "tool_calls_present": False,
        "tool_calls_count": 0,
        "effective_model_if_returned": None,
        "usage_prompt_tokens": None,
        "usage_completion_tokens": None,
        "usage_total_tokens": None,
    }
    try:
        payload = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError, TypeError, ValueError):
        assert_no_raw_content(view)
        return view

    view["json_decode_success"] = True
    view["json_top_level_type"] = _json_type(payload)
    if not isinstance(payload, dict):
        assert_no_raw_content(view)
        return view

    view["effective_model_if_returned"] = (
        str(payload.get("model")) if payload.get("model") is not None else None
    )
    choices = payload.get("choices")
    view["top_level_has_choices"] = "choices" in payload
    if isinstance(choices, list):
        view["choice_count"] = len(choices)
        first = choices[0] if choices else None
    else:
        first = None
    if isinstance(first, dict):
        view["first_choice_present"] = True
        finish_reason = first.get("finish_reason")
        view["finish_reason_present"] = finish_reason is not None
        view["finish_reason"] = str(finish_reason) if finish_reason is not None else None
        message = first.get("message")
    else:
        message = None
    if isinstance(message, dict):
        view["assistant_message_present"] = True
        content = message.get("content")
        snap = _value_snapshot(content)
        view["assistant_content_present"] = snap["present"]
        view["assistant_content_type"] = snap["type"]
        view["assistant_content_length"] = snap["length"]
        view["assistant_content_sha256"] = snap["sha256"]
        tool_calls = message.get("tool_calls")
        if isinstance(tool_calls, list):
            tool_count = len(tool_calls)
        else:
            tool_count = 1 if tool_calls else 0
        view["tool_calls_present"] = tool_count > 0
        view["tool_calls_count"] = tool_count
    usage = payload.get("usage")
    if isinstance(usage, dict):
        view["usage_prompt_tokens"] = _int_or_none(usage.get("prompt_tokens"))
        view["usage_completion_tokens"] = _int_or_none(usage.get("completion_tokens"))
        view["usage_total_tokens"] = _int_or_none(usage.get("total_tokens"))
    assert_no_raw_content(view)
    return view


class HTTPBodyRecorder:
    """Thread-safe, deduplicated structural recorder keyed by response identity."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._rows: list[dict[str, Any]] = []
        self._seen_response_ids: set[int] = set()
        self._next_send_index: dict[int, int] = {}

    def record(self, response: Any, body: bytes) -> None:
        response_id = id(response)
        logical_index = _origin_from_response(response)
        with self._lock:
            if response_id in self._seen_response_ids:
                return
            self._seen_response_ids.add(response_id)
            send_index = self._next_send_index.get(logical_index, 1)
            self._next_send_index[logical_index] = send_index + 1
        row = http_body_structural_view(
            response,
            body,
            logical_index=logical_index,
            logical_send_index=send_index,
        )
        with self._lock:
            self._rows.append(row)

    def rows(self, logical_index: int | None = None) -> list[dict[str, Any]]:
        with self._lock:
            rows = copy.deepcopy(self._rows)
        if logical_index is None:
            return rows
        return [row for row in rows if row["logical_index"] == logical_index]


@contextmanager
def observe_http_response_reads(recorder: HTTPBodyRecorder) -> Iterator[None]:
    """Observe bytes already read by HTTPX without causing an additional read/send."""
    import httpx

    original_read = httpx.Response.read
    original_aread = httpx.Response.aread

    def observed_read(response: Any) -> bytes:
        body = original_read(response)
        recorder.record(response, body)
        return body

    async def observed_aread(response: Any) -> bytes:
        body = await original_aread(response)
        recorder.record(response, body)
        return body

    httpx.Response.read = observed_read
    httpx.Response.aread = observed_aread
    try:
        yield
    finally:
        httpx.Response.read = original_read
        httpx.Response.aread = original_aread


def http_transport_coverage_defects(
    transport_rows: list[dict[str, Any]],
    http_rows: list[dict[str, Any]],
) -> list[str]:
    """Require one HTTP-body record for each response-bearing physical send."""
    expected = [
        (int(row["logical_send_index"]), int(row["http_status"]))
        for row in transport_rows
        if row.get("http_status") is not None and row.get("transport_error_type") is None
    ]
    observed = [
        (int(row["logical_send_index"]), int(row["http_status"]))
        for row in http_rows
    ]
    defects: list[str] = []
    if observed != expected:
        defects.append(f"http_transport_sequence_mismatch:expected={expected}:observed={observed}")
    if len({row[0] for row in observed}) != len(observed):
        defects.append("duplicate_http_logical_send_index")
    return defects


def semantic_http_association_defects(
    semantic_rows: list[dict[str, Any]],
    http_rows: list[dict[str, Any]],
) -> list[str]:
    """Check that every response-bearing semantic send has an HTTP structural record."""
    known = {int(row["logical_send_index"]) for row in http_rows}
    defects: list[str] = []
    for semantic in semantic_rows:
        sends = semantic.get("provider_sends")
        if not isinstance(sends, list):
            defects.append("semantic_provider_sends_not_list")
            continue
        response_sends = [
            int(row["logical_send_index"])
            for row in sends
            if row.get("http_status") is not None and row.get("transport_error_type") is None
        ]
        missing = [index for index in response_sends if index not in known]
        if missing:
            defects.append(f"semantic_http_body_association_missing:{missing}")
        if semantic.get("semantic_response_observed") is True and not response_sends:
            defects.append("observed_semantic_response_without_response_bearing_send")
    return defects


def classify_upstream_boundary(
    *,
    runtime_exception: bool,
    http_body: dict[str, Any] | None,
    sdk_semantic: dict[str, Any] | None,
    hermes_terminal_present: bool,
    adapter_candidate_present: bool,
    parse_valid: bool,
    accepted_exact_completion: bool,
) -> str:
    """Classify the first observed content disappearance across Q3-D3/Q3-D2 layers."""
    if runtime_exception:
        return "runtime_or_transport_failure"
    if http_body is None or not http_body.get("json_decode_success"):
        return "unclassified_observability_defect"
    if not bool(http_body.get("assistant_content_present")):
        return "http_body_content_absent"
    if sdk_semantic is None or not sdk_semantic.get("semantic_response_observed"):
        return "http_body_content_present_sdk_content_absent"
    if not bool(sdk_semantic.get("assistant_content_present")):
        return "http_body_content_present_sdk_content_absent"
    if not hermes_terminal_present:
        return "q3d2_semantic_present_hermes_terminal_absent"
    if hermes_terminal_present and not adapter_candidate_present:
        return "hermes_terminal_present_adapter_candidate_absent"
    if adapter_candidate_present and not parse_valid:
        return "adapter_candidate_nonempty_parse_invalid"
    if parse_valid and accepted_exact_completion:
        return "accepted_exact_completion"
    return "unclassified_observability_defect"
