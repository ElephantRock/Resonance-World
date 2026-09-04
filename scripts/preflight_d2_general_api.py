#!/usr/bin/env python3
"""Materialize or execute the bounded D2 General API engineering preflight."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

ENDPOINT = "https://api.z.ai/api/paas/v4/chat/completions"
MODEL = "glm-5-turbo"
TEMPERATURE = 0.8
MAX_TOKENS = 256
TIMEOUT_SECONDS = 90
ACTIONS = ("KAPPA", "MICA", "ORBIT", "VELA")
REQUEST_IDS = (
    "general_minimal_text",
    "general_minimal_json",
    "general_d2_shape_json",
)
PLAN_PATH = Path("research/d2_general_api_preflight/PREFLIGHT_REQUEST_PLAN.json")
MARKER_PATH = Path("research/d2_general_api_preflight/RUN_D2_GENERAL_API_PREFLIGHT")


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_text(value: str) -> str:
    return sha256_bytes(value.encode())


def d2_shape_cases() -> list[dict[str, int]]:
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


def request_matrix() -> list[dict[str, Any]]:
    common = {
        "model": MODEL,
        "temperature": TEMPERATURE,
        "thinking": {"type": "disabled"},
        "stream": False,
        "max_tokens": MAX_TOKENS,
    }
    return [
        {
            "diagnostic_id": "general_minimal_text",
            "body": {
                **common,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "This is an engineering transport probe. "
                            "Follow the user instruction exactly."
                        ),
                    },
                    {"role": "user", "content": "Reply with exactly the text OK."},
                ],
            },
        },
        {
            "diagnostic_id": "general_minimal_json",
            "body": {
                **common,
                "response_format": {"type": "json_object"},
                "messages": [
                    {
                        "role": "system",
                        "content": "Return exactly one JSON object and no markdown.",
                    },
                    {
                        "role": "user",
                        "content": 'Return a JSON object with one key status whose value is "ok".',
                    },
                ],
            },
        },
        {
            "diagnostic_id": "general_d2_shape_json",
            "body": {
                **common,
                "response_format": {"type": "json_object"},
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "Return one JSON object with an actions array containing exactly "
                            "8 entries, each one of KAPPA, MICA, ORBIT, VELA. "
                            "Do not use markdown."
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            "This is an engineering transport-shape probe, not a task-solving "
                            "benchmark. Return KAPPA for every case. Cases:\n"
                            + json.dumps(
                                d2_shape_cases(),
                                sort_keys=True,
                                separators=(",", ":"),
                            )
                        ),
                    },
                ],
            },
        },
    ]


def materialized_plan() -> dict[str, Any]:
    rows = request_matrix()
    return {
        "schema": "d2-general-api-preflight-materialization-v0.1",
        "engineering_only": True,
        "provider_execution_authorized": False,
        "endpoint": ENDPOINT,
        "model": MODEL,
        "request_count": len(rows),
        "request_ids": [row["diagnostic_id"] for row in rows],
        "request_body_sha256": {
            row["diagnostic_id"]: sha256_bytes(canonical_bytes(row["body"])) for row in rows
        },
        "max_attempts_per_request": 1,
        "scientific_field_trajectory_executed": False,
        "scientific_scoring_performed": False,
        "registry_promotion_authorized": False,
        "production_historical_substrate_enabled": False,
    }


def summarize_error_body(raw: str) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "response_body_length": len(raw.encode()),
        "response_body_sha256": sha256_text(raw),
    }
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return summary
    if not isinstance(parsed, dict):
        return summary
    error = parsed.get("error", parsed)
    if not isinstance(error, dict):
        return summary
    code = error.get("code")
    if code is not None:
        summary["provider_code"] = str(code)[:80]
    message = error.get("message")
    if isinstance(message, str):
        summary["provider_message_length"] = len(message)
        summary["provider_message_sha256"] = sha256_text(message)
    return summary


def validate_success(raw: str, diagnostic_id: str) -> dict[str, Any]:
    result: dict[str, Any] = {
        "outer_json_valid": False,
        "returned_model": None,
        "model_exact_match": False,
        "content_present": False,
        "content_sha256": sha256_text(""),
        "content_length": 0,
        "content_json_valid": None,
        "actions_shape_valid": None,
        "contract_pass": False,
    }
    try:
        outer = json.loads(raw)
    except json.JSONDecodeError:
        return result
    if not isinstance(outer, dict):
        return result
    result["outer_json_valid"] = True
    returned_model = outer.get("model")
    if isinstance(returned_model, str):
        result["returned_model"] = returned_model
        result["model_exact_match"] = returned_model == MODEL
    content = ""
    choices = outer.get("choices")
    if isinstance(choices, list) and choices and isinstance(choices[0], dict):
        message = choices[0].get("message")
        if isinstance(message, dict) and isinstance(message.get("content"), str):
            content = message["content"]
    result["content_present"] = bool(content)
    result["content_sha256"] = sha256_text(content)
    result["content_length"] = len(content.encode())

    if diagnostic_id == "general_minimal_text":
        result["contract_pass"] = bool(
            result["model_exact_match"] and result["content_present"]
        )
        return result

    result["content_json_valid"] = False
    if content:
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, dict):
            result["content_json_valid"] = True
            if diagnostic_id == "general_d2_shape_json":
                actions = parsed.get("actions")
                result["actions_shape_valid"] = bool(
                    isinstance(actions, list)
                    and len(actions) == 8
                    and all(action in ACTIONS for action in actions)
                )
    if diagnostic_id == "general_minimal_json":
        result["contract_pass"] = bool(
            result["model_exact_match"]
            and result["content_present"]
            and result["content_json_valid"]
        )
    else:
        result["contract_pass"] = bool(
            result["model_exact_match"]
            and result["content_present"]
            and result["content_json_valid"]
            and result["actions_shape_valid"]
        )
    return result


def execute_one(key: str, row: dict[str, Any]) -> dict[str, Any]:
    diagnostic_id = str(row["diagnostic_id"])
    body = canonical_bytes(row["body"])
    request = urllib.request.Request(
        ENDPOINT,
        data=body,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            raw_bytes = response.read()
            status = int(response.status)
    except urllib.error.HTTPError as exc:
        raw_bytes = exc.read()
        latency_ms = (time.perf_counter() - started) * 1000.0
        raw = raw_bytes.decode("utf-8", errors="replace")
        return {
            "diagnostic_id": diagnostic_id,
            "stage": "http_error",
            "http_status": int(exc.code),
            "latency_ms": round(latency_ms, 3),
            "request_body_sha256": sha256_bytes(body),
            **summarize_error_body(raw),
            "contract_pass": False,
        }
    except urllib.error.URLError as exc:
        latency_ms = (time.perf_counter() - started) * 1000.0
        return {
            "diagnostic_id": diagnostic_id,
            "stage": "network_error",
            "http_status": None,
            "latency_ms": round(latency_ms, 3),
            "request_body_sha256": sha256_bytes(body),
            "network_error_type": type(exc.reason).__name__,
            "contract_pass": False,
        }

    latency_ms = (time.perf_counter() - started) * 1000.0
    raw = raw_bytes.decode("utf-8", errors="replace")
    validated = validate_success(raw, diagnostic_id)
    return {
        "diagnostic_id": diagnostic_id,
        "stage": "http_success",
        "http_status": status,
        "latency_ms": round(latency_ms, 3),
        "request_body_sha256": sha256_bytes(body),
        "response_body_length": len(raw_bytes),
        "response_body_sha256": sha256_bytes(raw_bytes),
        **validated,
    }


def execute() -> dict[str, Any]:
    if os.environ.get("D2_GENERAL_API_PREFLIGHT_AUTHORIZED") != "1":
        raise RuntimeError("general API preflight execution is not authorized")
    if not MARKER_PATH.exists():
        raise RuntimeError("general API preflight execution marker is absent")
    key = os.environ.get("ZAI_API_KEY", "")
    if not key:
        raise RuntimeError("ZAI_API_KEY is required for authorized execution")
    rows = [execute_one(key, row) for row in request_matrix()]
    return {
        "schema": "d2-general-api-preflight-result-v0.1",
        "engineering_only": True,
        "endpoint": ENDPOINT,
        "requested_model": MODEL,
        "request_count": len(rows),
        "results": rows,
        "qualification_pass": all(bool(row.get("contract_pass")) for row in rows),
        "scientific_field_trajectory_executed": False,
        "scientific_scoring_performed": False,
        "replacement_d2d_data_allowed": False,
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
