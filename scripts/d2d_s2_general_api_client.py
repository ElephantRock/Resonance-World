"""Hardened no-retry General API client for the frozen D2d-S2 campaign."""

from __future__ import annotations

import hashlib
import http.client
import random
import threading
import time
import urllib.error
import urllib.request
from typing import Any

import preflight_d2_general_api as hardened

MODEL = "glm-5-turbo"
ENDPOINT = "https://api.z.ai/api/paas/v4/chat/completions"
MAX_TOKENS = 768
TIMEOUT_SECONDS = 90
BODY_READ_TIMEOUT_SECONDS = 90.0
MIN_REQUEST_INTERVAL_SECONDS = 0.35
ACTIONS = ("KAPPA", "MICA", "ORBIT", "VELA")


class CountingHTTPSHandler(urllib.request.HTTPSHandler):
    def __init__(self) -> None:
        super().__init__()
        self.attempts = 0

    def https_open(self, req: urllib.request.Request) -> Any:
        self.attempts += 1
        return super().https_open(req)


def payload_sha(value: Any) -> str:
    return hashlib.sha256(hardened.canonical_bytes(value)).hexdigest()


class Client:
    """One physical HTTPS attempt per logical scientific call; fail closed."""

    def __init__(self, key: str) -> None:
        if not key.strip():
            raise ValueError("ZAI_API_KEY is empty")
        self.key = key
        self.rng = random.Random(2026090608)
        self.rng_lock = threading.Lock()
        self.rate_lock = threading.Lock()
        self.counter_lock = threading.Lock()
        self.next_request_at = 0.0
        self.logical_calls_started = 0
        self.logical_calls_completed = 0
        self.logical_call_failures = 0
        self.physical_attempts_started = 0

    def _request_id(self, phase: str) -> str:
        with self.rng_lock:
            nonce = self.rng.getrandbits(64)
        safe = phase.replace("/", "-")[-40:]
        return f"d2d-s2-{safe}-{nonce:016x}"

    def _wait(self) -> None:
        with self.rate_lock:
            now = time.monotonic()
            wait = max(0.0, self.next_request_at - now)
            if wait:
                time.sleep(wait)
            self.next_request_at = (
                max(time.monotonic(), self.next_request_at) + MIN_REQUEST_INTERVAL_SECONDS
            )

    def complete(
        self,
        *,
        phase: str,
        system: str,
        user: str,
        expected_actions: int,
        temperature: float,
    ) -> dict[str, Any]:
        with self.counter_lock:
            self.logical_calls_started += 1
        request_id = self._request_id(phase)
        body_object = {
            "model": MODEL,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "thinking": {"type": "disabled"},
            "temperature": temperature,
            "max_tokens": MAX_TOKENS,
            "stream": False,
            "response_format": {"type": "json_object"},
        }
        body = hardened.canonical_bytes(body_object)
        request = urllib.request.Request(
            ENDPOINT,
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.key}",
                "Content-Type": "application/json",
                "Accept-Language": "en-US,en",
                "User-Agent": "resonance-world-d2d-s2/0.1",
            },
        )
        counter = CountingHTTPSHandler()
        opener = urllib.request.build_opener(hardened.NoRedirectHandler(), counter)
        self._wait()
        started = time.perf_counter()
        response_bytes: bytes | None = None
        http_status: int | None = None
        try:
            response = opener.open(request, timeout=TIMEOUT_SECONDS)
            with response:
                http_status = int(response.status)
                response_bytes, read_error = hardened.read_response_body(
                    response, timeout_seconds=BODY_READ_TIMEOUT_SECONDS
                )
            if read_error is not None or response_bytes is None:
                raise RuntimeError(f"response_read_failure:{read_error or 'unknown'}")
            if http_status != 200:
                raise RuntimeError(f"http_status:{http_status}")
            outer = hardened.strict_json_loads(response_bytes.decode("utf-8"))
            if not isinstance(outer, dict):
                raise ValueError("outer_json_shape")
            returned_model = outer.get("model")
            if returned_model != MODEL:
                raise ValueError("model_identity_mismatch")
            choices = outer.get("choices")
            if not isinstance(choices, list) or len(choices) != 1:
                raise ValueError("choice_shape")
            message = choices[0].get("message") if isinstance(choices[0], dict) else None
            text = message.get("content") if isinstance(message, dict) else None
            if not isinstance(text, str) or not text:
                raise ValueError("content_missing")
            payload = hardened.strict_json_loads(text)
            if not isinstance(payload, dict):
                raise ValueError("content_json_shape")
            actions = payload.get("actions")
            if not isinstance(actions, list) or len(actions) != expected_actions:
                raise ValueError("action_count")
            if not all(action in ACTIONS for action in actions):
                raise ValueError("action_vocabulary")
            strategy = payload.get("strategy")
            if strategy is not None and (
                not isinstance(strategy, str) or len(strategy) > 6000
            ):
                raise ValueError("strategy_shape")
            if counter.attempts != 1:
                raise RuntimeError("physical_attempt_count_mismatch")
            usage = outer.get("usage", {})
            attempt = {
                "attempt": 1,
                "request_id": request_id,
                "status": "ok",
                "http_status": 200,
                "physical_attempts_initiated": counter.attempts,
                "redirects_followed": 0,
                "redirect_history_verified": True,
                "request_body_sha256": hashlib.sha256(body).hexdigest(),
                "response_body_sha256": hashlib.sha256(response_bytes).hexdigest(),
                "response_body_length": len(response_bytes),
                "latency_ms": round((time.perf_counter() - started) * 1000.0, 3),
            }
            result = {
                "actions": list(actions),
                "strategy": strategy,
                "attempts": [attempt],
                "usage": {
                    "input_tokens": int(usage.get("prompt_tokens", 0)),
                    "output_tokens": int(usage.get("completion_tokens", 0)),
                },
                "model": returned_model,
                "temperature": temperature,
                "request_id": request_id,
                "prompt_sha256": hashlib.sha256((system + "\n" + user).encode()).hexdigest(),
                "response_sha256": payload_sha(payload),
                "extra_key_count": len(set(payload) - {"actions", "strategy"}),
                "strategy_present": strategy is not None,
                "total_latency_ms": round((time.perf_counter() - started) * 1000.0, 3),
            }
        except urllib.error.HTTPError as exc:
            http_status = int(exc.code)
            _, read_error = hardened.read_response_body(
                exc, timeout_seconds=BODY_READ_TIMEOUT_SECONDS
            )
            with self.counter_lock:
                self.physical_attempts_started += counter.attempts
                self.logical_call_failures += 1
            suffix = read_error or "body_read_ok"
            raise RuntimeError(f"provider_http_failure:{http_status}:{suffix}") from exc
        except (
            urllib.error.URLError,
            TimeoutError,
            OSError,
            http.client.HTTPException,
            ValueError,
            RuntimeError,
        ) as exc:
            with self.counter_lock:
                self.physical_attempts_started += counter.attempts
                self.logical_call_failures += 1
            raise RuntimeError(f"provider_call_failed:{type(exc).__name__}") from exc
        with self.counter_lock:
            self.physical_attempts_started += counter.attempts
            self.logical_calls_completed += 1
        return result
