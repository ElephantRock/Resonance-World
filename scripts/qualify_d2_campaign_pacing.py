#!/usr/bin/env python3
"""Bounded engineering-only qualification of D2 General API request pacing."""

from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import os
import statistics
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import preflight_d2_general_api as base

ISSUE = 210
ENDPOINT = "https://api.z.ai/api/paas/v4/chat/completions"
MODEL = "glm-5-turbo"
TEMPERATURE = 0.8
MAX_TOKENS = 768
TIMEOUT_SECONDS = 90
BODY_READ_TIMEOUT_SECONDS = 90.0
EXPECTED_ACTIONS = 8
ACTIONS = ("KAPPA", "MICA", "ORBIT", "VELA")
PLAN_PATH = Path("research/d2_campaign_pacing/PACING_REQUEST_PLAN.json")
MARKER_PATH = Path("research/d2_campaign_pacing/RUN_D2_CAMPAIGN_PACING_QUALIFICATION")
AUTH_ENV = "D2_CAMPAIGN_PACING_AUTHORIZED"
AUTHORIZATION_STRING = "D2_campaign_pacing_execution_explicitly_authorized"

PROFILES: tuple[dict[str, Any], ...] = (
    {
        "id": "baseline_serial_5s",
        "calls": 3,
        "max_concurrency": 1,
        "minimum_start_interval_seconds": 5.0,
    },
    {
        "id": "serial_2s",
        "calls": 6,
        "max_concurrency": 1,
        "minimum_start_interval_seconds": 2.0,
    },
    {
        "id": "serial_1s",
        "calls": 6,
        "max_concurrency": 1,
        "minimum_start_interval_seconds": 1.0,
    },
    {
        "id": "concurrency2_1s",
        "calls": 8,
        "max_concurrency": 2,
        "minimum_start_interval_seconds": 1.0,
    },
    {
        "id": "concurrency4_035s",
        "calls": 8,
        "max_concurrency": 4,
        "minimum_start_interval_seconds": 0.35,
    },
)


class CountingHTTPSHandler(urllib.request.HTTPSHandler):
    """Count initiated HTTPS attempts at the handler boundary."""

    def __init__(self) -> None:
        super().__init__()
        self.attempts = 0

    def https_open(self, req: urllib.request.Request) -> Any:
        self.attempts += 1
        return super().https_open(req)


class StartGate:
    """Serialize request starts while allowing bounded in-flight concurrency."""

    def __init__(self, interval_seconds: float) -> None:
        self.interval_seconds = interval_seconds
        self.lock = threading.Lock()
        self.next_start = 0.0
        self.origin = time.monotonic()

    def wait_for_slot(self) -> float:
        with self.lock:
            now = time.monotonic()
            wait = max(0.0, self.next_start - now)
            if wait:
                time.sleep(wait)
            started = time.monotonic()
            self.next_start = started + self.interval_seconds
            return started - self.origin


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def marker_record() -> dict[str, str]:
    if not MARKER_PATH.exists():
        raise RuntimeError("D2 campaign pacing authorization marker is absent")
    lines = [line for line in MARKER_PATH.read_text().splitlines() if line]
    if len(lines) != 3 or any("=" not in line for line in lines):
        raise RuntimeError("D2 campaign pacing authorization marker is malformed")
    fields = dict(line.split("=", 1) for line in lines)
    if set(fields) != {"candidate_sha", "issue", "authorization"}:
        raise RuntimeError("D2 campaign pacing authorization marker fields are invalid")
    candidate = fields["candidate_sha"]
    if len(candidate) != 40 or any(ch not in "0123456789abcdef" for ch in candidate):
        raise RuntimeError("D2 campaign pacing candidate SHA is invalid")
    if fields["issue"] != str(ISSUE):
        raise RuntimeError("D2 campaign pacing authorization issue is invalid")
    if fields["authorization"] != AUTHORIZATION_STRING:
        raise RuntimeError("D2 campaign pacing authorization string is invalid")
    return fields


def synthetic_cases() -> list[dict[str, int]]:
    return [
        {"f0": 0, "f1": 1, "f2": 2, "f3": 3},
        {"f0": 7, "f1": 6, "f2": 5, "f3": 4},
        {"f0": 1, "f1": 3, "f2": 5, "f3": 7},
        {"f0": 6, "f1": 4, "f2": 2, "f3": 0},
        {"f0": 2, "f1": 2, "f2": 6, "f3": 6},
        {"f0": 5, "f1": 1, "f2": 5, "f3": 1},
        {"f0": 3, "f1": 7, "f2": 0, "f3": 4},
        {"f0": 4, "f1": 0, "f2": 7, "f3": 3},
    ]


def representative_body() -> dict[str, Any]:
    feedback = [
        {
            "case": case,
            "chosen_action": ACTIONS[index % len(ACTIONS)],
            "correct": bool(index % 2),
        }
        for index, case in enumerate(synthetic_cases())
    ]
    strategy = "transport-only synthetic strategy state;" + ("S" * 2048)
    user = "\n\n".join(
        [
            "ENGINEERING ONLY. This is not a registered scientific task and will not be scored.",
            "Synthetic prior strategy:\n" + strategy,
            "Synthetic bounded feedback:\n"
            + json.dumps(feedback, sort_keys=True, separators=(",", ":")),
            "Synthetic cases to answer:\n"
            + json.dumps(synthetic_cases(), sort_keys=True, separators=(",", ":")),
            "Return KAPPA for every case. No scientific inference may use this output.",
        ]
    )
    return {
        "model": MODEL,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Return one JSON object with an actions array containing exactly 8 entries, "
                    "each one of KAPPA, MICA, ORBIT, VELA. You may include strategy as a string. "
                    "Do not use markdown."
                ),
            },
            {"role": "user", "content": user},
        ],
        "thinking": {"type": "disabled"},
        "temperature": TEMPERATURE,
        "max_tokens": MAX_TOKENS,
        "stream": False,
        "response_format": {"type": "json_object"},
    }


def apparatus_hashes() -> dict[str, str]:
    return {
        "hardened_transport_sha256": sha256_path(Path("scripts/preflight_d2_general_api.py")),
        "qualification_runner_sha256": sha256_path(Path(__file__)),
        "request_plan_sha256": sha256_path(PLAN_PATH),
    }


def materialized_plan() -> dict[str, Any]:
    request_body = representative_body()
    return {
        "schema": "d2-campaign-pacing-materialization-v0.1",
        "issue": ISSUE,
        "engineering_only": True,
        "provider_execution_authorized": False,
        "endpoint": ENDPOINT,
        "model": MODEL,
        "request_body_sha256": sha256_bytes(canonical_bytes(request_body)),
        "request_body_bytes": len(canonical_bytes(request_body)),
        "profiles": [dict(profile) for profile in PROFILES],
        "request_count_maximum": sum(int(profile["calls"]) for profile in PROFILES),
        "max_attempts_per_logical_call": 1,
        "redirect_policy": "reject_do_not_follow",
        "physical_attempt_accounting": "instrumented_https_handler_per_call",
        "scientific_campaign_authorized": False,
        "scientific_scoring_performed": False,
        "registry_promotion_authorized": False,
        "production_historical_substrate_enabled": False,
        **apparatus_hashes(),
    }


def _failure_result(
    *,
    profile_id: str,
    call_index: int,
    started_offset_seconds: float,
    started: float,
    body: bytes,
    counter: CountingHTTPSHandler,
    stage: str,
    http_status: int | None,
    error_type: str | None = None,
    error_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "profile_id": profile_id,
        "call_index": call_index,
        "started_offset_seconds": round(started_offset_seconds, 6),
        "stage": stage,
        "http_status": http_status,
        "latency_ms": round((time.perf_counter() - started) * 1000.0, 3),
        "request_body_sha256": sha256_bytes(body),
        "physical_attempts_initiated": counter.attempts,
        "one_physical_request_verified": counter.attempts == 1,
        "redirect_following_disabled": True,
        "redirects_followed": 0,
        "redirect_history_verified": counter.attempts == 1,
        "contract_pass": False,
    }
    if error_type is not None:
        result["error_type"] = error_type
    if error_summary:
        result.update(error_summary)
    return result


def execute_single(
    key: str,
    profile_id: str,
    call_index: int,
    gate: StartGate,
) -> dict[str, Any]:
    started_offset_seconds = gate.wait_for_slot()
    body_object = representative_body()
    body = canonical_bytes(body_object)
    request = urllib.request.Request(
        ENDPOINT,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Accept-Language": "en-US,en",
            "User-Agent": "resonance-world-d2-pacing/0.1",
        },
    )
    counter = CountingHTTPSHandler()
    opener = urllib.request.build_opener(base.NoRedirectHandler(), counter)
    started = time.perf_counter()
    try:
        response = opener.open(request, timeout=TIMEOUT_SECONDS)
    except urllib.error.HTTPError as exc:
        status = int(exc.code)
        raw_bytes, read_error = base.read_response_body(
            exc, timeout_seconds=BODY_READ_TIMEOUT_SECONDS
        )
        summary: dict[str, Any] = {}
        if raw_bytes is not None:
            raw = raw_bytes.decode("utf-8", errors="replace")
            summary = base.summarize_error_body(raw)
        if read_error is not None:
            summary["response_read_error_type"] = read_error
        return _failure_result(
            profile_id=profile_id,
            call_index=call_index,
            started_offset_seconds=started_offset_seconds,
            started=started,
            body=body,
            counter=counter,
            stage="http_error",
            http_status=status,
            error_summary=summary,
        )
    except TimeoutError as exc:
        return _failure_result(
            profile_id=profile_id,
            call_index=call_index,
            started_offset_seconds=started_offset_seconds,
            started=started,
            body=body,
            counter=counter,
            stage="timeout_error",
            http_status=None,
            error_type=type(exc).__name__,
        )
    except urllib.error.URLError as exc:
        return _failure_result(
            profile_id=profile_id,
            call_index=call_index,
            started_offset_seconds=started_offset_seconds,
            started=started,
            body=body,
            counter=counter,
            stage="network_error",
            http_status=None,
            error_type=type(exc.reason).__name__,
        )
    except (OSError, http.client.HTTPException) as exc:
        return _failure_result(
            profile_id=profile_id,
            call_index=call_index,
            started_offset_seconds=started_offset_seconds,
            started=started,
            body=body,
            counter=counter,
            stage="open_transport_error",
            http_status=None,
            error_type=type(exc).__name__,
        )

    with response:
        status = int(response.status)
        raw_bytes, read_error = base.read_response_body(
            response, timeout_seconds=BODY_READ_TIMEOUT_SECONDS
        )
    if read_error is not None or raw_bytes is None:
        return _failure_result(
            profile_id=profile_id,
            call_index=call_index,
            started_offset_seconds=started_offset_seconds,
            started=started,
            body=body,
            counter=counter,
            stage="response_body_read_error",
            http_status=status,
            error_type=read_error or "unknown",
        )

    raw = raw_bytes.decode("utf-8", errors="replace")
    validated = base.validate_success(raw, "general_d2_shape_json")
    redirect_response_observed = 300 <= status < 400
    physical_ok = counter.attempts == 1
    contract_pass = bool(
        status == 200
        and validated.get("contract_pass")
        and physical_ok
        and not redirect_response_observed
    )
    return {
        "profile_id": profile_id,
        "call_index": call_index,
        "started_offset_seconds": round(started_offset_seconds, 6),
        "stage": "http_success",
        "http_status": status,
        "latency_ms": round((time.perf_counter() - started) * 1000.0, 3),
        "request_body_sha256": sha256_bytes(body),
        "response_body_sha256": sha256_bytes(raw_bytes),
        "response_body_length": len(raw_bytes),
        "returned_model": validated.get("returned_model"),
        "model_exact_match": validated.get("model_exact_match"),
        "content_present": validated.get("content_present"),
        "content_json_valid": validated.get("content_json_valid"),
        "actions_shape_valid": validated.get("actions_shape_valid"),
        "physical_attempts_initiated": counter.attempts,
        "one_physical_request_verified": physical_ok,
        "redirect_following_disabled": True,
        "redirects_followed": 0,
        "redirect_response_observed": redirect_response_observed,
        "redirect_history_verified": physical_ok,
        "contract_pass": contract_pass,
    }


def execute_profile(key: str, profile: dict[str, Any]) -> dict[str, Any]:
    profile_id = str(profile["id"])
    calls = int(profile["calls"])
    max_concurrency = int(profile["max_concurrency"])
    interval = float(profile["minimum_start_interval_seconds"])
    gate = StartGate(interval)
    with ThreadPoolExecutor(max_workers=max_concurrency) as pool:
        futures = [
            pool.submit(execute_single, key, profile_id, index, gate)
            for index in range(calls)
        ]
        rows = [future.result() for future in futures]
    rows.sort(key=lambda row: int(row["call_index"]))
    starts = sorted(float(row["started_offset_seconds"]) for row in rows)
    observed_intervals = [
        round(starts[index] - starts[index - 1], 6)
        for index in range(1, len(starts))
    ]
    statuses: dict[str, int] = {}
    for row in rows:
        key_status = "none" if row["http_status"] is None else str(row["http_status"])
        statuses[key_status] = statuses.get(key_status, 0) + 1
    latencies = [float(row["latency_ms"]) for row in rows]
    profile_pass = bool(
        len(rows) == calls
        and all(row.get("http_status") == 200 for row in rows)
        and all(row.get("contract_pass") is True for row in rows)
        and all(row.get("one_physical_request_verified") is True for row in rows)
        and all(row.get("redirects_followed") == 0 for row in rows)
        and all(row.get("http_status") != 429 for row in rows)
    )
    return {
        "profile_id": profile_id,
        "calls": calls,
        "max_concurrency": max_concurrency,
        "minimum_start_interval_seconds": interval,
        "minimum_observed_start_interval_seconds": (
            min(observed_intervals) if observed_intervals else None
        ),
        "status_counts": statuses,
        "http_429_count": statuses.get("429", 0),
        "latency_ms": {
            "minimum": round(min(latencies), 3),
            "median": round(statistics.median(latencies), 3),
            "maximum": round(max(latencies), 3),
        },
        "profile_pass": profile_pass,
        "results": rows,
    }


def recommended_profile(profile_results: list[dict[str, Any]]) -> str | None:
    recommendation: str | None = None
    for result in profile_results:
        if result.get("profile_pass") is not True:
            break
        recommendation = str(result["profile_id"])
    return recommendation


def execute() -> dict[str, Any]:
    if os.environ.get(AUTH_ENV) != "1":
        raise RuntimeError("D2 campaign pacing execution is not authorized")
    marker = marker_record()
    key = os.environ.get("ZAI_API_KEY", "")
    if not key:
        raise RuntimeError("ZAI_API_KEY is required for authorized D2 pacing execution")
    request_plan = json.loads(PLAN_PATH.read_text())
    if request_plan.get("issue") != ISSUE:
        raise RuntimeError("D2 pacing request plan issue mismatch")
    if request_plan.get("provider_execution_authorized") is not False:
        raise RuntimeError("frozen D2 pacing request plan authorization state drift")

    profile_results = [execute_profile(key, dict(profile)) for profile in PROFILES]
    recommendation = recommended_profile(profile_results)
    return {
        "schema": "d2-campaign-pacing-qualification-result-v0.1",
        "issue": ISSUE,
        "engineering_only": True,
        "authorized_candidate_sha": marker["candidate_sha"],
        "authorization_marker_sha256": sha256_path(MARKER_PATH),
        **apparatus_hashes(),
        "endpoint": ENDPOINT,
        "requested_model": MODEL,
        "request_body_sha256": sha256_bytes(canonical_bytes(representative_body())),
        "request_count_maximum": sum(int(profile["calls"]) for profile in PROFILES),
        "request_count_executed": sum(int(result["calls"]) for result in profile_results),
        "profiles": profile_results,
        "recommended_profile": recommendation,
        "campaign_pacing_qualified": recommendation is not None,
        "provider_policy_cause_established": False,
        "scientific_field_trajectory_executed": False,
        "scientific_scoring_performed": False,
        "scientific_campaign_authorized": False,
        "replacement_d2d_s2_data_allowed": False,
        "registry_promotion_authorized": False,
        "production_historical_substrate_enabled": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    payload = execute() if args.execute else materialized_plan()
    encoded = canonical_bytes(payload)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(encoded)
    else:
        print(encoded.decode(), end="")


if __name__ == "__main__":
    main()
