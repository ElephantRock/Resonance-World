#!/usr/bin/env python3
"""Fresh hardened D2 General API transport requalification.

This wrapper reuses the hardened request/validation/read logic from
``preflight_d2_general_api.py`` while instrumenting the HTTPS handler so the
fresh execution can prove one initiated physical attempt per logical probe and
prove that redirects were not followed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import urllib.request
from pathlib import Path
from typing import Any

import preflight_d2_general_api as base

ISSUE = 206
MARKER_PATH = Path(
    "research/d2_general_api_requalification/RUN_D2_GENERAL_API_REQUALIFICATION"
)
REQUEST_PLAN_PATH = Path(
    "research/d2_general_api_requalification/REQUALIFICATION_REQUEST_PLAN.json"
)
AUTH_ENV = "D2_GENERAL_API_REQUALIFICATION_AUTHORIZED"
AUTHORIZATION_STRING = "D2_general_api_requalification_execution_explicitly_authorized"


class CountingHTTPSHandler(urllib.request.HTTPSHandler):
    """Count initiated HTTPS attempts at the handler boundary."""

    def __init__(self) -> None:
        super().__init__()
        self.attempts = 0

    def https_open(self, req: urllib.request.Request) -> Any:
        self.attempts += 1
        return super().https_open(req)


def sha256_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def materialized_plan() -> dict[str, Any]:
    payload = dict(base.materialized_plan())
    payload.update(
        {
            "schema": "d2-general-api-requalification-materialization-v0.1",
            "issue": ISSUE,
            "provider_execution_authorized": False,
            "redirect_policy": "reject_do_not_follow",
            "physical_attempt_accounting": "instrumented_https_handler",
            "redirect_history_must_be_verified": True,
            "one_physical_request_per_probe_must_be_verified": True,
            "hardened_transport_sha256": sha256_path(
                Path("scripts/preflight_d2_general_api.py")
            ),
            "requalification_wrapper_sha256": sha256_path(Path(__file__)),
            "historical_preflight_status": (
                "completed_response_level_pass_redirect_unverified"
            ),
            "historical_preflight_replacement_allowed": False,
            "production_historical_substrate_enabled": False,
        }
    )
    return payload


def build_counted_no_redirect_opener() -> tuple[Any, CountingHTTPSHandler]:
    counter = CountingHTTPSHandler()
    opener = urllib.request.build_opener(base.NoRedirectHandler(), counter)
    return opener, counter


def execute_probe(key: str, row: dict[str, Any]) -> dict[str, Any]:
    opener, counter = build_counted_no_redirect_opener()
    previous_opener = base.OPENER
    base.OPENER = opener
    try:
        result = dict(base.execute_one(key, row))
    finally:
        base.OPENER = previous_opener

    http_status = result.get("http_status")
    redirect_response_observed = bool(
        isinstance(http_status, int) and 300 <= http_status < 400
    )
    physical_ok = counter.attempts == 1
    redirect_history_verified = physical_ok

    base_contract_pass = bool(result.get("contract_pass"))
    result.update(
        {
            "base_response_contract_pass": base_contract_pass,
            "physical_attempts_initiated": counter.attempts,
            "one_physical_request_verified": physical_ok,
            "redirect_following_disabled": True,
            "redirects_followed": 0,
            "redirect_response_observed": redirect_response_observed,
            "redirect_history_verified": redirect_history_verified,
            "contract_pass": bool(
                base_contract_pass and physical_ok and not redirect_response_observed
            ),
        }
    )
    return result


def qualification_pass(rows: list[dict[str, Any]]) -> bool:
    return bool(
        rows
        and all(row.get("one_physical_request_verified") is True for row in rows)
        and all(row.get("redirect_history_verified") is True for row in rows)
        and all(row.get("redirects_followed") == 0 for row in rows)
        and base.qualification_pass(rows)
    )


def execute() -> dict[str, Any]:
    if os.environ.get(AUTH_ENV) != "1":
        raise RuntimeError("General API requalification execution is not authorized")
    if not MARKER_PATH.exists():
        raise RuntimeError("General API requalification execution marker is absent")
    key = os.environ.get("ZAI_API_KEY", "")
    if not key:
        raise RuntimeError("ZAI_API_KEY is required for authorized execution")

    rows = [execute_probe(key, row) for row in base.request_matrix()]
    one_physical = all(
        row.get("one_physical_request_verified") is True for row in rows
    )
    redirect_history = all(row.get("redirect_history_verified") is True for row in rows)
    qualified = qualification_pass(rows)
    return {
        "schema": "d2-general-api-requalification-result-v0.1",
        "engineering_only": True,
        "issue": ISSUE,
        "endpoint": base.ENDPOINT,
        "requested_model": base.MODEL,
        "request_count": len(rows),
        "results": rows,
        "redirect_history_verified": redirect_history,
        "one_physical_request_per_probe_verified": one_physical,
        "qualification_pass": qualified,
        "transport_qualified_for_future_prospective_design": qualified,
        "scientific_field_trajectory_executed": False,
        "scientific_scoring_performed": False,
        "replacement_d2d_data_allowed": False,
        "historical_preflight_replacement_allowed": False,
        "scientific_campaign_authorized": False,
        "registry_promotion_authorized": False,
        "production_historical_substrate_enabled": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    payload = execute() if args.execute else materialized_plan()
    encoded = base.canonical_bytes(payload)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(encoded)
    else:
        print(encoded.decode(), end="")


if __name__ == "__main__":
    main()
