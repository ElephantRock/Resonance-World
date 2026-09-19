# ruff: noqa: E501
"""Qualified bounded Hermes client for D2-vNext-S2 scientific calls.

This adapts the exact #251 terminal-completion semantics and #276 one-retry
format-regeneration rule to the fresh #279 scientific request stream.  Raw first
responses are used only in-memory for exact parsing and are never returned by this
client.
"""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import re
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from resonance_world import d2_terminal_adapter as adapter
from resonance_world.provider_send_guard import ProviderSendBudget, SendReservation

BASE_URL = "https://api.z.ai/api/coding/paas/v4"
PROVIDER = "zai"
API_MODE = "chat_completions"
MODEL = "glm-5.3"
TEMPERATURE = 0.8
MAX_TOKENS = 768
MAX_ITERATIONS = 2
MAX_AGENT_INVOCATIONS = 2
MAX_LOGICAL_CALLS_PER_SHARD = 880
MAX_PHYSICAL_SENDS_PER_LOGICAL_CALL = 36
MAX_PHYSICAL_SENDS_PER_SHARD = 2000
OPENAI_VERSION = "2.21.0"
HTTPX_VERSION = "0.28.1"
OPENAI_DEFAULT_MAX_RETRIES = 2
PROBE_ORIGIN_HEADER = "X-Resonance-World-Logical-Index"
COMPATIBILITY_STATUSES = frozenset({400, 404, 409, 415, 422})
PROVIDER_WORKER_TARGET_MODULE = "run_agent"
PROVIDER_WORKER_TARGET_NAME = "_call"
PROVIDER_WORKER_DRAIN_TIMEOUT_SECONDS = 60.0

SYSTEM_PROMPT = (
    'Scientific D2-vNext-S2 source-acquisition call. Return exactly one JSON object '
    'and no surrounding text. The object MUST contain "actions" as a JSON square-bracket '
    'array of exactly 8 strings. Each array position corresponds to the matching presented '
    'case in order. Never return actions as an object, map, string, keyed per-case record, '
    'or scalar. Each action value must be exactly KAPPA, MICA, ORBIT, or VELA. Optional '
    '"strategy" may be an ASCII string of at most 512 characters. No other top-level keys '
    'are permitted. Use this non-answer positional JSON skeleton only as syntax/position '
    'guidance: {"actions":["<ACTION_1>","<ACTION_2>","<ACTION_3>","<ACTION_4>",'
    '"<ACTION_5>","<ACTION_6>","<ACTION_7>","<ACTION_8>"]}. Replace every <ACTION_n> '
    'placeholder with one allowed action for the corresponding actual case; never emit '
    'placeholder text. Before emitting, silently verify: valid JSON object; only actions '
    'and optional strategy; actions is an array of exactly 8 allowed strings; no '
    'placeholder remains; no surrounding prose, Markdown, or fences. Return JSON only.'
)

FORBIDDEN_EXEMPLAR = (
    '{"actions":["KAPPA","MICA","ORBIT","VELA","KAPPA","MICA","ORBIT","VELA"]}'
)


class LogicalAttributionMismatch(RuntimeError):
    """Raised before transmission when request origin disagrees with logical context."""


class TransportLedger:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._rows = {index: [] for index in range(MAX_LOGICAL_CALLS_PER_SHARD)}
        self._attribution_mismatches = 0

    def record_attribution_mismatch(self) -> None:
        with self._lock:
            self._attribution_mismatches += 1

    @property
    def attribution_mismatches(self) -> int:
        with self._lock:
            return self._attribution_mismatches

    def begin(self, reservation: SendReservation, origin_logical_index: int) -> int:
        if origin_logical_index != reservation.logical_index:
            self.record_attribution_mismatch()
            raise LogicalAttributionMismatch(
                "request origin disagrees with provider-send reservation"
            )
        row = {
            "origin_logical_index": origin_logical_index,
            "logical_index": reservation.logical_index,
            "logical_send_index": reservation.logical_send_index,
            "total_send_index": reservation.total_send_index,
            "http_status": None,
            "transport_error_type": None,
        }
        with self._lock:
            rows = self._rows[reservation.logical_index]
            rows.append(row)
            return len(rows) - 1

    def response(self, reservation: SendReservation, row_index: int, status: int) -> None:
        with self._lock:
            self._rows[reservation.logical_index][row_index]["http_status"] = int(status)

    def error(self, reservation: SendReservation, row_index: int, exc: BaseException) -> None:
        with self._lock:
            self._rows[reservation.logical_index][row_index]["transport_error_type"] = type(exc).__name__

    def rows(self, logical_index: int) -> list[dict[str, Any]]:
        with self._lock:
            return [dict(row) for row in self._rows[logical_index]]


class ProviderWorkerTracker:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._threads: set[threading.Thread] = set()
        self._observed = 0
        self._alive_after_drain = 0
        self._transport_hooks_restored = False

    @staticmethod
    def is_provider_worker(thread: threading.Thread) -> bool:
        target = getattr(thread, "_target", None)
        return (
            getattr(target, "__module__", None) == PROVIDER_WORKER_TARGET_MODULE
            and getattr(target, "__name__", None) == PROVIDER_WORKER_TARGET_NAME
        )

    def observe_before_start(self, thread: threading.Thread) -> None:
        if self.is_provider_worker(thread):
            with self._lock:
                self._threads.add(thread)
                self._observed += 1

    @property
    def observed(self) -> int:
        with self._lock:
            return self._observed

    @property
    def alive_after_drain(self) -> int:
        with self._lock:
            return self._alive_after_drain

    @property
    def transport_hooks_restored(self) -> bool:
        with self._lock:
            return self._transport_hooks_restored

    def drain(self, timeout_seconds: float = PROVIDER_WORKER_DRAIN_TIMEOUT_SECONDS) -> int:
        deadline = time.monotonic() + timeout_seconds
        while True:
            with self._lock:
                alive = [thread for thread in self._threads if thread.is_alive()]
            if not alive:
                with self._lock:
                    self._alive_after_drain = 0
                return 0
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                with self._lock:
                    self._alive_after_drain = len(alive)
                return len(alive)
            for thread in alive:
                thread.join(timeout=min(0.2, remaining))

    def mark_transport_hooks_restored(self) -> None:
        with self._lock:
            self._transport_hooks_restored = True


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def bounded_parse_diagnostic(text: str) -> str:
    def reject_constant(value: str) -> None:
        raise ValueError(value)

    try:
        payload = json.loads(text, parse_constant=reject_constant)
    except (json.JSONDecodeError, TypeError, ValueError):
        return "json_decode_failure"
    if not isinstance(payload, dict):
        return "top_level_not_object"
    if not set(payload).issubset({"actions", "strategy"}):
        return "extra_keys"
    if "actions" not in payload:
        return "actions_missing"
    actions = payload["actions"]
    if not isinstance(actions, list):
        return "actions_not_list"
    if len(actions) != 8:
        return "wrong_action_count"
    if any(action not in adapter.ACTIONS for action in actions):
        return "invalid_action"
    strategy = payload.get("strategy", "")
    if not isinstance(strategy, str):
        return "strategy_not_string"
    if len(strategy) > adapter.MAX_STRATEGY_CHARS:
        return "strategy_too_long"
    try:
        strategy.encode("ascii")
    except UnicodeEncodeError:
        return "strategy_non_ascii"
    return "exact_valid"


def retry_user_prompt(original_user: str, diagnostic: str) -> str:
    eligible = {
        "json_decode_failure",
        "top_level_not_object",
        "extra_keys",
        "actions_missing",
        "actions_not_list",
        "wrong_action_count",
        "invalid_action",
        "strategy_not_string",
        "strategy_too_long",
        "strategy_non_ascii",
    }
    if diagnostic not in eligible:
        raise ValueError("retry diagnostic not eligible")
    return (
        original_user
        + "\n\nFormat-regeneration attempt: the prior attempt was rejected by the unchanged exact "
        + f"parser with bounded diagnostic class {diagnostic}. Raw prior response content "
        + "is not provided and must not be inferred, reconstructed, or repaired. Generate "
        + "a new answer independently for the original cases. Re-check the required "
        + "non-answer positional JSON skeleton contract silently before emitting. Return "
        + "JSON only."
    )


def _origin(request: Any, budget: ProviderSendBudget, ledger: TransportLedger) -> int:
    raw = request.headers.get(PROBE_ORIGIN_HEADER)
    try:
        origin = int(raw) if raw is not None else -1
    except (TypeError, ValueError):
        origin = -1
    registered = budget.current_logical_index()
    if (
        not 0 <= origin < MAX_LOGICAL_CALLS_PER_SHARD
        or registered is None
        or origin != registered
    ):
        ledger.record_attribution_mismatch()
        raise LogicalAttributionMismatch(
            "independent request origin does not match registered logical context"
        )
    return origin


@contextmanager
def guarded_shard_transport(
    budget: ProviderSendBudget,
    ledger: TransportLedger,
    workers: ProviderWorkerTracker,
) -> Iterator[None]:
    """Guard every physical send and propagate exact logical authority to Hermes workers."""
    import httpx

    original_sync = httpx.Client._send_single_request
    original_async = httpx.AsyncClient._send_single_request
    original_thread_start = threading.Thread.start

    def tracked_start(thread: threading.Thread, *args: object, **kwargs: object) -> object:
        inherited = budget.current_logical_index()
        workers.observe_before_start(thread)
        target = getattr(thread, "_target", None)
        if inherited is not None and target is not None:
            original_target = target

            def target_with_logical_context(
                *target_args: object, **target_kwargs: object
            ) -> object:
                with budget.logical_call(inherited):
                    return original_target(*target_args, **target_kwargs)

            thread._target = target_with_logical_context  # type: ignore[attr-defined]
        return original_thread_start(thread, *args, **kwargs)

    def capped_sync(client: Any, request: Any) -> Any:
        origin = _origin(request, budget, ledger)
        reservation = budget.reserve(str(request.url))
        row_index = ledger.begin(reservation, origin)
        try:
            response = original_sync(client, request)
        except Exception as exc:
            ledger.error(reservation, row_index, exc)
            raise
        ledger.response(reservation, row_index, response.status_code)
        return response

    async def capped_async(client: Any, request: Any) -> Any:
        origin = _origin(request, budget, ledger)
        reservation = budget.reserve(str(request.url))
        row_index = ledger.begin(reservation, origin)
        try:
            response = await original_async(client, request)
        except Exception as exc:
            ledger.error(reservation, row_index, exc)
            raise
        ledger.response(reservation, row_index, response.status_code)
        return response

    threading.Thread.start = tracked_start  # type: ignore[method-assign]
    httpx.Client._send_single_request = capped_sync
    httpx.AsyncClient._send_single_request = capped_async
    try:
        yield
    finally:
        alive = workers.drain()
        threading.Thread.start = original_thread_start  # type: ignore[method-assign]
        if alive == 0:
            httpx.Client._send_single_request = original_sync
            httpx.AsyncClient._send_single_request = original_async
            workers.mark_transport_hooks_restored()


def new_shard_budget() -> ProviderSendBudget:
    return ProviderSendBudget(
        allowed_url_prefix=BASE_URL,
        maximum_logical_calls=MAX_LOGICAL_CALLS_PER_SHARD,
        maximum_sends_per_logical_call=MAX_PHYSICAL_SENDS_PER_LOGICAL_CALL,
        maximum_sends_total=MAX_PHYSICAL_SENDS_PER_SHARD,
    )


def _runtime_versions() -> None:
    import httpx
    from openai._constants import DEFAULT_MAX_RETRIES

    versions = (
        importlib.metadata.version("hermes-agent"),
        importlib.metadata.version("openai"),
        importlib.metadata.version("httpx"),
        httpx.__version__,
        DEFAULT_MAX_RETRIES,
    )
    if versions != ("0.8.0", OPENAI_VERSION, HTTPX_VERSION, HTTPX_VERSION, 2):
        raise AssertionError("D2-vNext-S2 runtime version drift")


def _new_agent(logical_index: int) -> Any:
    from run_agent import AIAgent

    agent = AIAgent(
        provider=PROVIDER,
        api_mode=API_MODE,
        model=MODEL,
        max_iterations=MAX_ITERATIONS,
        enabled_toolsets=[],
        quiet_mode=True,
        save_trajectories=False,
        ephemeral_system_prompt=SYSTEM_PROMPT,
        max_tokens=MAX_TOKENS,
        request_overrides={
            "temperature": TEMPERATURE,
            "response_format": {"type": "json_object"},
            "extra_body": {"thinking": {"type": "disabled"}},
            "extra_headers": {PROBE_ORIGIN_HEADER: str(logical_index)},
        },
        skip_context_files=True,
        skip_memory=True,
        persist_session=False,
        fallback_model=None,
    )
    if int(getattr(agent.client, "max_retries", -1)) != OPENAI_DEFAULT_MAX_RETRIES:
        raise AssertionError("OpenAI client retry drift")
    if agent.tools != [] or agent.valid_tool_names or agent._fallback_chain:
        raise AssertionError("Hermes tool/fallback drift")
    if (agent.model, agent.provider, agent.api_mode) != (MODEL, PROVIDER, API_MODE):
        raise AssertionError("Hermes route drift")
    if (int(agent.max_iterations), int(agent.max_tokens)) != (MAX_ITERATIONS, MAX_TOKENS):
        raise AssertionError("Hermes profile drift")
    if str(agent.client.base_url).rstrip("/") != BASE_URL:
        raise AssertionError("Hermes client base URL drift")
    kwargs = agent._build_api_kwargs([{"role": "user", "content": "preflight"}])
    expected = {
        "temperature": TEMPERATURE,
        "response_format": {"type": "json_object"},
        "extra_body": {"thinking": {"type": "disabled"}},
        "extra_headers": {PROBE_ORIGIN_HEADER: str(logical_index)},
    }
    for key, value in expected.items():
        if kwargs.get(key) != value:
            raise AssertionError(f"Hermes request override drift: {key}")
    return agent


def _clean_attempts(rows: list[dict[str, Any]]) -> bool:
    return bool(rows) and all(
        row.get("http_status") == 200 and row.get("transport_error_type") is None
        for row in rows
    )


def _compatibility_failure(runtime_exception: bool, rows: list[dict[str, Any]]) -> bool:
    return bool(
        runtime_exception
        and rows
        and all(row.get("transport_error_type") is None for row in rows)
        and any(row.get("http_status") in COMPATIBILITY_STATUSES for row in rows)
    )


def _invoke(
    logical_index: int,
    user: str,
    budget: ProviderSendBudget,
    ledger: TransportLedger,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    before = len(ledger.rows(logical_index))
    agent: Any | None = None
    result: dict[str, Any] = {}
    final_text = ""
    runtime_exception = False
    error_type: str | None = None
    error_sha256: str | None = None
    try:
        agent = _new_agent(logical_index)
        result = agent.run_conversation(user_message=user)
        final = result.get("final_response")
        final_text = final if isinstance(final, str) else ""
    except Exception as exc:
        runtime_exception = True
        error_type = type(exc).__name__
        error_sha256 = sha256_text(f"{type(exc).__name__}:{str(exc)[:500]}")

    rows = ledger.rows(logical_index)[before:]
    api_calls = int(getattr(agent, "_api_call_count", 0) if agent is not None else 0)
    completed = result.get("completed")
    completed_valid = isinstance(completed, bool)
    diagnostic = bounded_parse_diagnostic(final_text)
    parse_valid, strategy = adapter.parse_response(final_text)
    if parse_valid != (diagnostic == "exact_valid"):
        raise AssertionError("exact parser/diagnostic divergence")
    view = {
        "completed": completed if completed_valid else None,
        "failed": result.get("failed") is True or runtime_exception,
        "partial": result.get("partial") is True,
        "interrupted": result.get("interrupted") is True,
        "error": "bounded-error-present" if (bool(result.get("error")) or runtime_exception) else None,
        "api_calls": api_calls,
        "final_response": "bounded-nonempty-response-sentinel" if final_text.strip() else "",
    }
    decision = adapter.evaluate_terminal_completion(
        view,
        max_iterations=MAX_ITERATIONS,
        parse_valid=parse_valid,
        logical_attribution_integrity=bool(rows)
        and all(
            row.get("origin_logical_index") == logical_index
            and row.get("logical_index") == logical_index
            for row in rows
        ),
        attempts=rows,
        physical_sends=len(rows),
        unexpected_outbound_blocks=budget.blocked_unexpected,
        provider_budget_blocks=budget.blocked_budget,
        attribution_mismatch_blocks=ledger.attribution_mismatches,
    )
    compatibility = _compatibility_failure(runtime_exception, rows)
    payload: dict[str, Any] | None = None
    if parse_valid:
        decoded = json.loads(final_text)
        payload = {
            "actions": list(decoded["actions"]),
            "strategy": decoded.get("strategy"),
        }
    bounded = {
        "runtime_exception": runtime_exception,
        "error_type": error_type,
        "error_sha256": error_sha256,
        "hermes_completed_flag_valid": completed_valid,
        "hermes_completed": completed is True,
        "hermes_failed": result.get("failed") is True,
        "hermes_partial": result.get("partial") is True,
        "hermes_interrupted": result.get("interrupted") is True,
        "hermes_error_present": bool(result.get("error")),
        "api_calls": api_calls,
        "final_response_length": len(final_text),
        "final_response_sha256": sha256_text(final_text) if final_text else None,
        "exact_structured_parse_valid": parse_valid,
        "parse_diagnostic": diagnostic,
        "placeholder_leak": "<ACTION_" in final_text,
        "strategy_length": len(strategy) if parse_valid else 0,
        "strategy_sha256": sha256_text(strategy) if parse_valid and strategy else None,
        "physical_provider_sends_observed": len(rows),
        "attempts": rows,
        "logical_attribution_integrity": bool(rows)
        and all(
            row.get("origin_logical_index") == logical_index
            and row.get("logical_index") == logical_index
            for row in rows
        ),
        "exact_attributed_clean_transport": _clean_attempts(rows),
        "json_mode_compatibility_failure": compatibility,
        "effective_completed": decision.effective_completed,
        "terminal_iteration_override_used": decision.terminal_iteration_override_used,
        "adapter_reason": decision.reason,
    }
    return bounded, payload


def retry_eligible(
    first: dict[str, Any], budget: ProviderSendBudget, ledger: TransportLedger
) -> bool:
    return bool(
        not first["runtime_exception"]
        and first["final_response_length"] > 0
        and not first["exact_structured_parse_valid"]
        and first["exact_attributed_clean_transport"]
        and first["logical_attribution_integrity"]
        and first["hermes_completed_flag_valid"]
        and not first["hermes_failed"]
        and not first["hermes_partial"]
        and not first["hermes_interrupted"]
        and not first["hermes_error_present"]
        and not first["json_mode_compatibility_failure"]
        and budget.blocked_unexpected == 0
        and budget.blocked_budget == 0
        and ledger.attribution_mismatches == 0
    )


class Client:
    """One-shard scientific client with exact #276-style bounded format regeneration."""

    def __init__(
        self,
        key: str,
        budget: ProviderSendBudget,
        ledger: TransportLedger,
    ) -> None:
        if not key.strip():
            raise RuntimeError("ZAI_API_KEY is required")
        if os.environ.get("GLM_BASE_URL", "").rstrip("/") != BASE_URL:
            raise RuntimeError("Coding Plan base URL drift")
        _runtime_versions()
        if FORBIDDEN_EXEMPLAR in SYSTEM_PROMPT:
            raise AssertionError("literal valid action exemplar prohibited")
        self.budget = budget
        self.ledger = ledger
        self.logical_calls_started = 0
        self.logical_calls_completed = 0
        self.logical_call_failures = 0
        self.retry_used_count = 0
        self.terminal_iteration_override_count = 0
        self._counter = 0

    def complete(
        self,
        *,
        phase: str,
        system: str,
        user: str,
        expected_actions: int,
        temperature: float,
    ) -> dict[str, Any]:
        del system  # scientific task content is in the user prompt; output contract is frozen above.
        if expected_actions != 8:
            raise AssertionError("D2-vNext-S2 exact action count drift")
        if float(temperature) != TEMPERATURE:
            raise AssertionError("D2-vNext-S2 temperature drift")
        logical_index = self._counter
        self._counter += 1
        if logical_index >= MAX_LOGICAL_CALLS_PER_SHARD:
            raise RuntimeError("registered logical-call topology exhausted")
        self.logical_calls_started += 1
        prompt_sha256 = hashlib.sha256(
            canonical_bytes({"system": SYSTEM_PROMPT, "user": user})
        ).hexdigest()
        second: dict[str, Any] | None = None
        second_payload: dict[str, Any] | None = None
        retry_prompt: str | None = None
        try:
            with self.budget.logical_call(logical_index):
                first, first_payload = _invoke(
                    logical_index, user, self.budget, self.ledger
                )
                eligible = retry_eligible(first, self.budget, self.ledger)
                if eligible:
                    retry_prompt = retry_user_prompt(user, str(first["parse_diagnostic"]))
                    second, second_payload = _invoke(
                        logical_index, retry_prompt, self.budget, self.ledger
                    )
                    self.retry_used_count += 1

            if first["exact_structured_parse_valid"] and first["effective_completed"]:
                accepted_index = 1
                accepted = first
                payload = first_payload
            elif (
                second is not None
                and second["exact_structured_parse_valid"]
                and second["effective_completed"]
            ):
                accepted_index = 2
                accepted = second
                payload = second_payload
            else:
                self.logical_call_failures += 1
                raise RuntimeError("D2-vNext-S2 logical call has no accepted exact completion")

            if payload is None:
                raise AssertionError("accepted exact response payload missing")
            if first["exact_structured_parse_valid"] and second is not None:
                raise AssertionError("valid first response was retried")
            if second is not None and not eligible:
                raise AssertionError("format-regeneration retry was not eligible")
            if accepted["terminal_iteration_override_used"]:
                self.terminal_iteration_override_count += 1
            all_attempts = self.ledger.rows(logical_index)
            if len(all_attempts) != self.budget.sends_for_logical_call(logical_index):
                raise AssertionError("provider-send ledger/accounting mismatch")
            self.logical_calls_completed += 1
            final_sha = accepted["final_response_sha256"]
            return {
                "actions": list(payload["actions"]),
                "strategy": payload.get("strategy"),
                "model": MODEL,
                "effective_model_identity_observed": False,
                "effective_model": None,
                "temperature": TEMPERATURE,
                "thinking": "disabled",
                "request_id": f"d2-vnext-s2-{logical_index:04d}-{re.sub(r'[^a-zA-Z0-9_.-]+', '-', phase)[-72:]}",
                "prompt_sha256": prompt_sha256,
                "response_sha256": final_sha,
                "strategy_present": payload.get("strategy") is not None,
                "extra_key_count": 0,
                "attempts": all_attempts,
                "usage": {},
                "total_latency_ms": None,
                "retry_used": second is not None,
                "retry_eligible_after_first": eligible,
                "accepted_attempt_index": accepted_index,
                "agent_invocation_count": 1 + int(second is not None),
                "first_attempt_parse_valid": first["exact_structured_parse_valid"],
                "first_attempt_parse_diagnostic": first["parse_diagnostic"],
                "first_attempt_final_response_length": first["final_response_length"],
                "first_attempt_final_response_sha256": first["final_response_sha256"],
                "second_attempt_parse_valid": (
                    second["exact_structured_parse_valid"] if second is not None else None
                ),
                "second_attempt_parse_diagnostic": (
                    second["parse_diagnostic"] if second is not None else None
                ),
                "second_attempt_final_response_length": (
                    second["final_response_length"] if second is not None else None
                ),
                "second_attempt_final_response_sha256": (
                    second["final_response_sha256"] if second is not None else None
                ),
                "retry_prompt_sha256": sha256_text(retry_prompt) if retry_prompt else None,
                "retry_raw_first_response_content_included": False,
                "hermes_completed": accepted["hermes_completed"],
                "terminal_iteration_override_used": accepted[
                    "terminal_iteration_override_used"
                ],
                "adapter_reason": accepted["adapter_reason"],
                "json_mode_compatibility_failure": bool(
                    first["json_mode_compatibility_failure"]
                    or (second and second["json_mode_compatibility_failure"])
                ),
            }
        except Exception:
            if self.logical_call_failures == 0 or self.logical_calls_completed + self.logical_call_failures < self.logical_calls_started:
                self.logical_call_failures += 1
            raise
