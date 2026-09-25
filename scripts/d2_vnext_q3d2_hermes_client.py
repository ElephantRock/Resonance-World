"""Q3-D2 request-scoped semantic observability instrumentation.

This module does not create provider requests and does not authorize provider/model
execution. It only supplies the single request-scoped observer intervention used
by a separately authorized future Q3-D2 diagnostic.
"""
from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any

import d2_vnext_q3d_hermes_client as q3d

SemanticRecorder = q3d.SemanticRecorder


def _provider_send_slice(
    ledger: Any | None,
    logical_index: int | None,
    before: int,
) -> list[dict[str, Any]]:
    if ledger is None or logical_index is None:
        return []
    return q3d._transport_rows(ledger.rows(logical_index)[before:])


def _wrap_request_client(
    request_client: Any,
    *,
    agent_invocation_index: int,
    recorder: SemanticRecorder,
    logical_index: int | None,
    ledger: Any | None,
) -> None:
    """Decorate only the request-scoped chat-completion method in place."""
    chat = getattr(request_client, "chat", None)
    completions = getattr(chat, "completions", None)
    original_create = getattr(completions, "create", None)
    if not callable(original_create):
        raise AssertionError("Q3-D2 request client lacks chat.completions.create")

    def observed_create(*args: Any, **kwargs: Any) -> Any:
        semantic_index = recorder.reserve_index()
        before = (
            len(ledger.rows(logical_index))
            if ledger is not None and logical_index is not None
            else 0
        )
        try:
            response = original_create(*args, **kwargs)
        except Exception as exc:
            sends = _provider_send_slice(ledger, logical_index, before)
            recorder.append(
                q3d.provider_completion_error_view(
                    exc,
                    agent_invocation_index=agent_invocation_index,
                    semantic_response_index=semantic_index,
                    provider_sends=sends,
                )
            )
            raise

        sends = _provider_send_slice(ledger, logical_index, before)
        recorder.append(
            q3d.provider_completion_view(
                response,
                agent_invocation_index=agent_invocation_index,
                semantic_response_index=semantic_index,
                provider_sends=sends,
            )
        )
        return response

    completions.create = observed_create


def instrument_request_scoped_chat_completions(
    agent: Any,
    *,
    agent_invocation_index: int,
    recorder: SemanticRecorder,
    logical_index: int | None = None,
    ledger: Any | None = None,
) -> Callable[..., Any]:
    """Observe clients returned by Hermes' request-client factory.

    The original factory is called exactly once with unchanged arguments. The
    same request-client object is returned after only its completion method has
    been decorated.
    """
    original_factory = getattr(agent, "_create_request_openai_client", None)
    if not callable(original_factory):
        raise AssertionError("Q3-D2 requires Hermes request-client factory")

    def observed_factory(*args: Any, **kwargs: Any) -> Any:
        request_client = original_factory(*args, **kwargs)
        _wrap_request_client(
            request_client,
            agent_invocation_index=agent_invocation_index,
            recorder=recorder,
            logical_index=logical_index,
            ledger=ledger,
        )
        return request_client

    agent._create_request_openai_client = observed_factory
    return original_factory


@contextmanager
def activate_request_scoped_observer() -> Iterator[None]:
    """Temporarily route Q3-D's observer hook to the Q3-D2 request-scoped observer."""
    original = q3d.instrument_chat_completions
    q3d.instrument_chat_completions = instrument_request_scoped_chat_completions
    try:
        yield
    finally:
        q3d.instrument_chat_completions = original


def semantic_coverage_defects(
    api_calls: int,
    semantic_rows: list[dict[str, Any]],
) -> list[str]:
    """Return fail-closed structural coverage defects for one invocation."""
    defects: list[str] = []
    if api_calls < 0:
        defects.append("negative_hermes_api_call_count")
        return defects

    if len(semantic_rows) != api_calls:
        defects.append(
            "semantic_completion_count_mismatch:"
            f"api_calls={api_calls}:semantic_records={len(semantic_rows)}"
        )

    indices = [row.get("semantic_response_index") for row in semantic_rows]
    expected = list(range(1, len(semantic_rows) + 1))
    if indices != expected:
        defects.append("semantic_response_index_sequence_invalid")

    for row in semantic_rows:
        if row.get("semantic_response_observed") is True:
            if row.get("semantic_response_error_type") is not None:
                defects.append("observed_response_has_error_type")
        elif not row.get("semantic_response_error_type"):
            defects.append("unobserved_response_missing_error_type")

    return defects


def assert_semantic_coverage(
    api_calls: int,
    semantic_rows: list[dict[str, Any]],
) -> None:
    """Fail closed when Hermes API calls are not represented one-for-one."""
    defects = semantic_coverage_defects(api_calls, semantic_rows)
    if defects:
        raise AssertionError("Q3-D2 semantic coverage failure: " + ";".join(defects))
