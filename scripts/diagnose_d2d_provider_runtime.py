#!/usr/bin/env python3
"""Bounded engineering-only probe for the D2d provider/runtime failure."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ENDPOINT = "https://api.z.ai/api/coding/paas/v4/chat/completions"
MODEL = "glm-5-turbo"
TEMPERATURE = 0.8
MAX_TOKENS = 256
REQUEST_IDS = ("minimal_json", "d2d_shape_json", "d2d_shape_text")
ACTIONS = ("KAPPA", "MICA", "ORBIT", "VELA")


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def public_cases() -> list[dict[str, int]]:
    return [
        {"f0": 0, "f1": 1, "f2": 2, "f3": 3},
        {"f0": 7, "f1": 6, "f2": 5, "f3": 4},
        {"f0": 1, "f1": 3, "f2": 5, "f3": 7},
        {"f0": 6, "f1": 4, "f2": 2, "f3": 0},
        {"f0": 2, "f1": 5, "f2": 1, "f3": 6},
        {"f0": 5, "f1": 2, "f2": 6, "f3": 1},
        {"f0": 3, "f1": 7, "f2": 0, "f3": 4},
        {"f0": 4, "f1": 0, "f2": 7, "f3": 3},
    ]


def request_matrix() -> list[dict[str, Any]]:
    system = (
        "Return one JSON object with an actions array containing exactly 8 entries, "
        "each one of KAPPA, MICA, ORBIT, VELA. Do not use markdown."
    )
    minimal_user = "Return eight valid action tokens in JSON."
    d2d_user = "\n\n".join(
        [
            (
                "Objective: Choose exactly one action from KAPPA, MICA, ORBIT, VELA "
                "for each four-feature integer case."
            ),
            (
                "Task ecology: A Field has a fixed hidden local policy; infer nothing "
                "beyond the public cases in this engineering probe."
            ),
            "Phase: fresh_evaluation_1",
            "Cases to answer now:\n"
            + json.dumps(public_cases(), sort_keys=True, separators=(",", ":")),
            "These are engineering diagnostic cases. No correctness feedback will be provided.",
        ]
    )
    return [
        {
            "diagnostic_id": "minimal_json",
            "system": system,
            "user": minimal_user,
            "response_format": {"type": "json_object"},
        },
        {
            "diagnostic_id": "d2d_shape_json",
            "system": system,
            "user": d2d_user,
            "response_format": {"type": "json_object"},
        },
        {
            "diagnostic_id": "d2d_shape_text",
            "system": system,
            "user": d2d_user,
            "response_format": {"type": "text"},
        },
    ]


def request_body(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": row["system"]},
            {"role": "user", "content": row["user"]},
        ],
        "thinking": {"type": "disabled"},
        "do_sample": True,
        "temperature": TEMPERATURE,
        "max_tokens": MAX_TOKENS,
        "stream": False,
        "response_format": row["response_format"],
        "request_id": f"d2d-diag-{row['diagnostic_id']}-000001",
    }


def summarize_error_body(raw: str) -> dict[str, Any]:
    out: dict[str, Any] = {
        "body_sha256": sha256_text(raw),
        "body_length": len(raw),
        "provider_code": None,
        "provider_message_sha256": None,
        "provider_message_length": None,
    }
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return out
    if isinstance(payload, dict):
        code = payload.get("code")
        if isinstance(code, (str, int)):
            out["provider_code"] = str(code)
        message = payload.get("message")
        if isinstance(message, str):
            out["provider_message_sha256"] = sha256_text(message)
            out["provider_message_length"] = len(message)
    return out


def validate_success(raw: str, diagnostic_id: str) -> dict[str, Any]:
    result: dict[str, Any] = {
        "response_body_sha256": sha256_text(raw),
        "response_body_length": len(raw),
        "outer_json_valid": False,
        "model": None,
        "content_present": False,
        "content_sha256": None,
        "content_json_valid": None,
        "actions_shape_valid": None,
    }
    try:
        outer = json.loads(raw)
    except json.JSONDecodeError:
        return result
    result["outer_json_valid"] = True
    if isinstance(outer, dict):
        model = outer.get("model")
        result["model"] = model if isinstance(model, str) else None
        choices = outer.get("choices")
        if isinstance(choices, list) and len(choices) == 1:
            message = choices[0].get("message") if isinstance(choices[0], dict) else None
            content = message.get("content") if isinstance(message, dict) else None
            if isinstance(content, str):
                result["content_present"] = True
                result["content_sha256"] = sha256_text(content)
                if diagnostic_id.endswith("_text"):
                    result["content_json_valid"] = None
                    result["actions_shape_valid"] = None
                else:
                    try:
                        payload = json.loads(content)
                    except json.JSONDecodeError:
                        result["content_json_valid"] = False
                    else:
                        result["content_json_valid"] = True
                        actions = payload.get("actions") if isinstance(payload, dict) else None
                        result["actions_shape_valid"] = (
                            isinstance(actions, list)
                            and len(actions) == 8
                            and all(action in ACTIONS for action in actions)
                        )
    return result


def execute_one(key: str, row: dict[str, Any]) -> dict[str, Any]:
    body = request_body(row)
    request = Request(
        ENDPOINT,
        data=json.dumps(body, separators=(",", ":")).encode(),
        method="POST",
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Accept-Language": "en-US,en",
            "User-Agent": "resonance-world-d2d-provider-diagnostic/0.1",
        },
    )
    started = time.perf_counter()
    base = {
        "diagnostic_id": row["diagnostic_id"],
        "request_body_sha256": hashlib.sha256(canonical_bytes(body)).hexdigest(),
    }
    try:
        with urlopen(request, timeout=90.0) as response:
            status = int(getattr(response, "status", 200))
            raw = response.read().decode(errors="replace")
    except HTTPError as exc:
        raw = exc.read().decode(errors="replace")
        return {
            **base,
            "stage": "http_error",
            "http_status": int(exc.code),
            "latency_ms": round((time.perf_counter() - started) * 1000, 3),
            **summarize_error_body(raw),
        }
    except (URLError, TimeoutError) as exc:
        return {
            **base,
            "stage": "transport_exception",
            "exception_type": type(exc).__name__,
            "exception_message_sha256": sha256_text(str(exc)),
            "exception_message_length": len(str(exc)),
            "latency_ms": round((time.perf_counter() - started) * 1000, 3),
        }
    return {
        **base,
        "stage": "http_success",
        "http_status": status,
        "latency_ms": round((time.perf_counter() - started) * 1000, 3),
        **validate_success(raw, row["diagnostic_id"]),
    }


def materialized_plan() -> dict[str, Any]:
    rows = request_matrix()
    return {
        "schema": "d2d-provider-diagnostic-materialization-v0.1",
        "endpoint": ENDPOINT,
        "model": MODEL,
        "temperature": TEMPERATURE,
        "max_tokens": MAX_TOKENS,
        "request_count": len(rows),
        "request_ids": [row["diagnostic_id"] for row in rows],
        "request_body_sha256": {
            row["diagnostic_id"]: hashlib.sha256(canonical_bytes(request_body(row))).hexdigest()
            for row in rows
        },
        "provider_execution_authorized": False,
        "scientific_field_trajectory_executed": False,
        "registry_promotion_authorized": False,
        "production_historical_substrate_enabled": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--output", default="output/d2d-provider-diagnostic.json")
    args = parser.parse_args()

    if not args.execute:
        print(json.dumps(materialized_plan(), indent=2, sort_keys=True))
        return

    marker = Path("research/d2d_diag/RUN_D2D_PROVIDER_DIAGNOSTIC")
    if not marker.exists():
        raise RuntimeError("diagnostic execution marker is required")
    if os.environ.get("D2D_PROVIDER_DIAGNOSTIC_AUTHORIZED") != "1":
        raise RuntimeError("diagnostic execution environment authorization is required")
    key = os.environ.get("ZAI_API_KEY", "")
    if not key.strip():
        raise RuntimeError("ZAI_API_KEY is required")

    rows = [execute_one(key, row) for row in request_matrix()]
    output = {
        "schema": "d2d-provider-diagnostic-result-v0.1",
        "engineering_only": True,
        "request_count": len(rows),
        "results": rows,
        "scientific_field_trajectory_executed": False,
        "replacement_d2d_data_allowed": False,
        "registry_promotion_authorized": False,
        "production_historical_substrate_enabled": False,
    }
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_bytes(output))
    print(json.dumps(output, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
