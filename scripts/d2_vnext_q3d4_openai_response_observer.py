"""Credential-free Q3-D4 observer at OpenAI's buffered-response boundary.

Q3-D4 observes an already-buffered ``httpx.Response`` immediately before the
OpenAI SDK parses it. It never calls ``read``/``aread`` and never persists raw
response or assistant content. The module does not authorize provider/model
execution.
"""
from __future__ import annotations

import copy
import hashlib
import json
import threading
from collections.abc import Callable
from typing import Any

FORBIDDEN_RAW_KEYS = {
    "raw_response_text",
    "raw_provider_body",
    "response_body",
    "body",
    "body_bytes",
    "body_text",
    "raw_content",
    "assistant_content",
    "content_bytes",
    "content_text",
    "prompt_text",
    "retry_prompt_text",
    "final_response",
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
            raise AssertionError(f"raw-content field leaked into Q3-D4 evidence: {sorted(overlap)}")
        for nested in value.values():
            assert_no_raw_content(nested)
    elif isinstance(value, list):
        for nested in value:
            assert_no_raw_content(nested)


def buffered_response_structural_view(
    response: Any,
    *,
    response_index: int,
) -> dict[str, Any]:
    """Return bounded structure from already-buffered response bytes only."""
    status = getattr(response, "status_code", None)
    headers = getattr(response, "headers", {})
    raw_content_type = headers.get("content-type") if headers is not None else None
    media_type = (
        str(raw_content_type).split(";", 1)[0].strip().lower()
        if raw_content_type is not None
        else None
    )
    consumed = getattr(response, "is_stream_consumed", None) is True
    view: dict[str, Any] = {
        "response_index": response_index,
        "http_status": int(status) if status is not None else None,
        "content_type_media_type": media_type,
        "stream_consumed_before_observer": consumed,
        "response_byte_length": None,
        "response_sha256": None,
        "json_decode_success": False,
        "json_top_level_type": "unobserved",
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
        "observability_defects": [],
    }
    if not consumed:
        view["observability_defects"].append("response_not_buffered_before_openai_process_response")
        assert_no_raw_content(view)
        return view

    try:
        body = response.content
    except Exception as exc:
        view["observability_defects"].append(
            f"buffered_response_content_unavailable:{type(exc).__name__}"
        )
        assert_no_raw_content(view)
        return view
    if not isinstance(body, bytes):
        view["observability_defects"].append(
            f"buffered_response_content_not_bytes:{type(body).__name__}"
        )
        assert_no_raw_content(view)
        return view

    view["response_byte_length"] = len(body)
    view["response_sha256"] = _sha_bytes(body) if body else None
    try:
        payload = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError, TypeError, ValueError):
        view["json_top_level_type"] = "decode_failure"
        assert_no_raw_content(view)
        return view

    view["json_decode_success"] = True
    view["json_top_level_type"] = _json_type(payload)
    if not isinstance(payload, dict):
        assert_no_raw_content(view)
        return view

    model = payload.get("model")
    view["effective_model_if_returned"] = str(model) if model is not None else None
    choices = payload.get("choices")
    view["top_level_has_choices"] = "choices" in payload
    first: Any = None
    if isinstance(choices, list):
        view["choice_count"] = len(choices)
        first = choices[0] if choices else None
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
        snap = _value_snapshot(message.get("content"))
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


class BufferedResponseRecorder:
    """Thread-safe Q3-D4 structural recorder shared across request clients."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._rows: list[dict[str, Any]] = []
        self._next_index = 1

    def record(self, response: Any) -> dict[str, Any]:
        with self._lock:
            index = self._next_index
            self._next_index += 1
        row = buffered_response_structural_view(response, response_index=index)
        with self._lock:
            self._rows.append(copy.deepcopy(row))
        return row

    def append_defect(self, defect: str) -> None:
        with self._lock:
            index = self._next_index
            self._next_index += 1
            self._rows.append(
                {
                    "response_index": index,
                    "http_status": None,
                    "content_type_media_type": None,
                    "stream_consumed_before_observer": False,
                    "response_byte_length": None,
                    "response_sha256": None,
                    "json_decode_success": False,
                    "json_top_level_type": "unobserved",
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
                    "observability_defects": [defect],
                }
            )

    def rows(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = copy.deepcopy(self._rows)
        assert_no_raw_content(rows)
        return rows


def _extract_httpx_response(args: tuple[Any, ...], kwargs: dict[str, Any]) -> Any | None:
    response = kwargs.get("response")
    if response is not None:
        return response
    for value in args:
        if (
            hasattr(value, "status_code")
            and hasattr(value, "headers")
            and hasattr(value, "is_stream_consumed")
        ):
            return value
    return None


def instrument_openai_process_response(
    request_client: Any,
    *,
    recorder: BufferedResponseRecorder,
) -> Callable[..., Any]:
    """Decorate one request-scoped OpenAI client's `_process_response` method."""
    original = getattr(request_client, "_process_response", None)
    if not callable(original):
        raise AssertionError("Q3-D4 request client lacks callable _process_response")

    def observed_process_response(*args: Any, **kwargs: Any) -> Any:
        response = _extract_httpx_response(args, kwargs)
        if response is None:
            recorder.append_defect("openai_process_response_missing_httpx_response")
        else:
            recorder.record(response)
        return original(*args, **kwargs)

    request_client._process_response = observed_process_response
    return original


def instrument_current_request_factory_after_q3d2(
    agent: Any,
    *,
    recorder: BufferedResponseRecorder,
) -> Callable[..., Any]:
    """Compose Q3-D4 after the already-qualified Q3-D2 request factory wrapper.

    Call this only after Q3-D2 has instrumented ``agent._create_request_openai_client``.
    The current factory is called exactly once with unchanged args/kwargs. The same
    request-client object is returned after adding only the Q3-D4 `_process_response`
    observer.
    """
    original_factory = getattr(agent, "_create_request_openai_client", None)
    if not callable(original_factory):
        raise AssertionError("Q3-D4 requires Hermes request-client factory")

    def observed_factory(*args: Any, **kwargs: Any) -> Any:
        request_client = original_factory(*args, **kwargs)
        instrument_openai_process_response(request_client, recorder=recorder)
        return request_client

    agent._create_request_openai_client = observed_factory
    return original_factory


def coverage_defects(
    buffered_rows: list[dict[str, Any]],
    semantic_rows: list[dict[str, Any]],
) -> list[str]:
    """Require one buffered response record for each observed semantic response."""
    defects: list[str] = []
    expected = sum(1 for row in semantic_rows if row.get("semantic_response_observed") is True)
    if len(buffered_rows) != expected:
        defects.append(
            "buffered_semantic_count_mismatch:"
            f"buffered={len(buffered_rows)}:observed_semantic={expected}"
        )
    indices = [row.get("response_index") for row in buffered_rows]
    if indices != list(range(1, len(buffered_rows) + 1)):
        defects.append("buffered_response_index_sequence_invalid")
    for index, row in enumerate(buffered_rows, start=1):
        embedded = row.get("observability_defects")
        if not isinstance(embedded, list):
            defects.append(f"buffered_{index}_observability_defects_not_list")
        elif embedded:
            defects.extend(f"buffered_{index}:{item}" for item in embedded)
    return defects
