"""Bounded supported-product Hermes client for D2-vNext-S1 scientific calls."""

from __future__ import annotations

import hashlib
import json
import re
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import qualify_d2_coding_plan_hermes as engineering

BASE_URL = engineering.BASE_URL
PROVIDER = engineering.PROVIDER
API_MODE = engineering.API_MODE
MODEL = "glm-5.3"
TEMPERATURE = 0.8
MAX_TOKENS = 768
MAX_AGENT_ITERATIONS = 1
MAX_PHYSICAL_SENDS_PER_LOGICAL_CALL = 18
MAX_PHYSICAL_SENDS_PER_SHARD = 1000
_ALLOWED_URL_PREFIX = BASE_URL.rstrip("/") + "/"


class ScientificPhysicalSendBudgetExceeded(RuntimeError):
    """Raised before a physical provider send would exceed a registered ceiling."""


class ScientificUnexpectedOutboundRequest(RuntimeError):
    """Raised before an unregistered outbound HTTP request is transmitted."""


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _strict_json(text: str) -> Any:
    def reject_constant(value: str) -> None:
        raise ValueError(f"non-standard JSON constant prohibited: {value}")

    return json.loads(text, parse_constant=reject_constant)


class ShardPhysicalSendBudget:
    """Fail-closed process-wide physical-send accounting for one provider shard."""

    def __init__(self) -> None:
        self.max_total = MAX_PHYSICAL_SENDS_PER_SHARD
        self.max_per_logical = MAX_PHYSICAL_SENDS_PER_LOGICAL_CALL
        self.total = 0
        self.blocked_budget = 0
        self.blocked_unexpected = 0
        self.current_logical_call: str | None = None
        self.attempts: dict[str, list[dict[str, Any]]] = {}
        self._lock = threading.Lock()

    def begin_logical_call(self, logical_call_id: str) -> None:
        with self._lock:
            self.current_logical_call = logical_call_id
            self.attempts.setdefault(logical_call_id, [])

    def reserve(self, url: str) -> tuple[str, int]:
        with self._lock:
            logical = self.current_logical_call
            if logical is None:
                self.blocked_unexpected += 1
                raise ScientificUnexpectedOutboundRequest(
                    "outbound HTTP blocked outside a registered logical call"
                )
            if not str(url).startswith(_ALLOWED_URL_PREFIX):
                self.blocked_unexpected += 1
                raise ScientificUnexpectedOutboundRequest(
                    "unregistered outbound HTTP request blocked"
                )
            rows = self.attempts.setdefault(logical, [])
            if len(rows) >= self.max_per_logical or self.total >= self.max_total:
                self.blocked_budget += 1
                raise ScientificPhysicalSendBudgetExceeded(
                    "registered physical provider-send budget exhausted"
                )
            self.total += 1
            index = len(rows) + 1
            rows.append(
                {
                    "attempt": index,
                    "campaign_physical_send_index": self.total,
                    "http_status": None,
                    "transport_error_type": None,
                }
            )
            return logical, index - 1

    def record_response(self, logical: str, index: int, status_code: int) -> None:
        with self._lock:
            self.attempts[logical][index]["http_status"] = int(status_code)

    def record_transport_error(self, logical: str, index: int, exc: BaseException) -> None:
        with self._lock:
            self.attempts[logical][index]["transport_error_type"] = type(exc).__name__

    def attempts_for(self, logical_call_id: str) -> list[dict[str, Any]]:
        with self._lock:
            return [dict(row) for row in self.attempts.get(logical_call_id, [])]


@contextmanager
def enforce_shard_physical_send_budget(
    budget: ShardPhysicalSendBudget,
) -> Iterator[None]:
    """Guard every physical httpx send and reject non-Coding-Plan traffic."""
    import httpx

    original_sync = httpx.Client._send_single_request
    original_async = httpx.AsyncClient._send_single_request

    def guarded_sync(client: Any, request: Any) -> Any:
        logical, index = budget.reserve(str(request.url))
        try:
            response = original_sync(client, request)
        except Exception as exc:
            budget.record_transport_error(logical, index, exc)
            raise
        budget.record_response(logical, index, response.status_code)
        return response

    async def guarded_async(client: Any, request: Any) -> Any:
        logical, index = budget.reserve(str(request.url))
        try:
            response = await original_async(client, request)
        except Exception as exc:
            budget.record_transport_error(logical, index, exc)
            raise
        budget.record_response(logical, index, response.status_code)
        return response

    httpx.Client._send_single_request = guarded_sync
    httpx.AsyncClient._send_single_request = guarded_async
    try:
        yield
    finally:
        httpx.Client._send_single_request = original_sync
        httpx.AsyncClient._send_single_request = original_async


class Client:
    """One-shard scientific client routed strictly through pinned Hermes."""

    def __init__(self, key: str, budget: ShardPhysicalSendBudget) -> None:
        if not key.strip():
            raise RuntimeError("ZAI_API_KEY is required")
        engineering._assert_execution_environment()
        hermes_version, sdk_retries, httpx_version = engineering._validate_runtime_versions()
        if hermes_version != engineering.HERMES_VERSION:
            raise AssertionError("Hermes package drift")
        if sdk_retries != engineering.OPENAI_DEFAULT_MAX_RETRIES:
            raise AssertionError("OpenAI SDK retry-default drift")
        if httpx_version != engineering.HTTPX_VERSION:
            raise AssertionError("httpx version drift")
        self.budget = budget
        self.logical_calls_started = 0
        self.logical_calls_completed = 0
        self.logical_call_failures = 0
        self._counter = 0

    def _logical_id(self, phase: str) -> str:
        self._counter += 1
        safe = re.sub(r"[^a-zA-Z0-9_.-]+", "-", phase)[-72:]
        return f"d2-vnext-s1-{self._counter:04d}-{safe}"

    def _new_agent(self, system: str) -> Any:
        from run_agent import AIAgent

        agent = AIAgent(
            provider=PROVIDER,
            api_mode=API_MODE,
            model=MODEL,
            max_iterations=MAX_AGENT_ITERATIONS,
            enabled_toolsets=[],
            quiet_mode=True,
            save_trajectories=False,
            ephemeral_system_prompt=system,
            max_tokens=MAX_TOKENS,
            request_overrides={
                "temperature": TEMPERATURE,
                "extra_body": {"thinking": {"type": "disabled"}},
            },
            skip_context_files=True,
            skip_memory=True,
            persist_session=False,
            fallback_model=None,
        )
        if int(getattr(agent.client, "max_retries", -1)) != engineering.OPENAI_DEFAULT_MAX_RETRIES:
            raise AssertionError("runtime OpenAI client retry drift")
        if agent.tools != [] or agent.valid_tool_names:
            raise AssertionError("Hermes tool-disable contract drift")
        if agent._fallback_chain:
            raise AssertionError("provider fallback unexpectedly configured")
        if agent.model != MODEL or agent.provider != PROVIDER or agent.api_mode != API_MODE:
            raise AssertionError("Hermes provider/model/api-mode drift")
        if str(agent.client.base_url).rstrip("/") != BASE_URL:
            raise AssertionError("Hermes client base URL drift")
        if str(agent.base_url).rstrip("/") != BASE_URL:
            raise AssertionError("Hermes routed base URL drift")
        kwargs = agent._build_api_kwargs([{"role": "user", "content": "preflight"}])
        if float(kwargs.get("temperature", -1)) != TEMPERATURE:
            raise AssertionError("Hermes temperature override drift")
        extra_body = kwargs.get("extra_body")
        if extra_body != {"thinking": {"type": "disabled"}}:
            raise AssertionError("Hermes thinking-disable override drift")
        return agent

    def complete(
        self,
        *,
        phase: str,
        system: str,
        user: str,
        expected_actions: int,
        temperature: float,
    ) -> dict[str, Any]:
        if float(temperature) != TEMPERATURE:
            raise AssertionError("scientific temperature drift")
        logical_id = self._logical_id(phase)
        self.logical_calls_started += 1
        self.budget.begin_logical_call(logical_id)
        prompt_sha256 = hashlib.sha256(
            canonical_bytes({"system": system, "user": user})
        ).hexdigest()
        try:
            agent = self._new_agent(system)
            result = agent.run_conversation(user_message=user)
            api_calls = int(getattr(agent, "_api_call_count", 0))
            if api_calls != 1:
                raise RuntimeError(f"Hermes semantic API-call count drift: {api_calls}")
            final_response = str(result.get("final_response") or "")
            if (
                result.get("failed") is True
                or result.get("completed") is not True
                or bool(result.get("error"))
                or not final_response.strip()
            ):
                raise RuntimeError("Hermes returned a non-completed scientific logical call")
            payload = _strict_json(final_response)
            if not isinstance(payload, dict):
                raise ValueError("scientific response must be a JSON object")
            actions = payload.get("actions")
            if not isinstance(actions, list) or len(actions) != expected_actions:
                raise ValueError("scientific actions cardinality mismatch")
            if any(action not in {"KAPPA", "MICA", "ORBIT", "VELA"} for action in actions):
                raise ValueError("scientific response contains invalid action")
            strategy = payload.get("strategy")
            if strategy is not None and not isinstance(strategy, str):
                raise ValueError("scientific strategy must be a string when present")
            attempts = self.budget.attempts_for(logical_id)
            if not 1 <= len(attempts) <= MAX_PHYSICAL_SENDS_PER_LOGICAL_CALL:
                raise AssertionError("scientific physical-send count outside frozen bound")
            self.logical_calls_completed += 1
            response_sha256 = sha256_text(final_response)
            return {
                "actions": list(actions),
                "strategy": strategy,
                "model": MODEL,
                "effective_model_identity_observed": False,
                "effective_model": None,
                "temperature": TEMPERATURE,
                "thinking": "disabled",
                "request_id": logical_id,
                "prompt_sha256": prompt_sha256,
                "response_sha256": response_sha256,
                "strategy_present": strategy is not None,
                "extra_key_count": len(set(payload) - {"actions", "strategy"}),
                "attempts": attempts,
                "usage": {},
                "total_latency_ms": None,
                "hermes_api_calls": api_calls,
            }
        except Exception:
            self.logical_call_failures += 1
            raise
