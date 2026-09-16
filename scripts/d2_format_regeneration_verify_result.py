#!/usr/bin/env python3
# ruff: noqa: E501
"""Verify the bounded #276 result before artifact upload."""
from __future__ import annotations

import json
import sys
from pathlib import Path

RESULT = Path("output/d2-format-regeneration-result.json")
ALLOWED = {"APPARATUS_FAILURE", "FAIL_JSON_MODE_COMPATIBILITY", "FAIL_STRUCTURED_CONTRACT", "FAIL_COMPLETION", "PASS"}


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: verify_result.py CANDIDATE_SHA")
    candidate = sys.argv[1]
    p = json.loads(RESULT.read_text())
    assert p["schema"] == "d2-format-regeneration-result-v0.1"
    assert p["issue"] == 276 and p["candidate_sha"] == candidate
    assert p["engineering_only"] is True
    assert p["fresh_namespace"] == "rw.d2-format-regeneration-retry.v1"
    assert p["registered_probe_count"] == 72 and p["attempted_probe_count"] == 72
    assert len(p["probes"]) == 72
    assert p["qualification_outcome"] in ALLOWED
    assert p["qualification_pass"] is (p["qualification_outcome"] == "PASS")
    assert 0 <= p["effective_completed_count"] <= 72
    assert 0 <= p["retry_used_count"] <= 72
    assert 0 <= p["retry_success_count"] <= p["retry_used_count"]
    assert 1 <= p["physical_provider_sends_observed_total"] <= 180
    assert p["retry_raw_first_response_content_allowed"] is False
    assert all(r["agent_invocation_count"] in {1, 2} for r in p["probes"])
    assert all(r["retry_used"] is (r["agent_invocation_count"] == 2) for r in p["probes"])
    assert all(not r["retry_raw_first_response_content_included"] for r in p["probes"])
    assert all(not r["retry_policy_violation"] for r in p["probes"] if p["qualification_outcome"] != "APPARATUS_FAILURE")
    outcome = p["qualification_outcome"]
    if outcome == "PASS":
        assert p["apparatus_failure"] is False
        assert p["effective_completed_count"] == 72
        assert p["terminal_exact_structured_parse_invalid_count"] == 0
        assert p["json_mode_compatibility_failure_count"] == 0
        assert p["unexpected_outbound_http_requests_blocked"] == 0
        assert p["provider_attempts_blocked_by_cap"] == 0
        assert p["logical_attribution_mismatch_blocks"] == 0
        assert p["provider_worker_threads_alive_after_drain"] == 0
        assert p["transport_hooks_restored_after_worker_drain"] is True
        assert all(r["final_response_length"] > 0 and r["exact_structured_parse_valid"] and r["effective_completed"] and r["exact_attributed_clean_transport"] for r in p["probes"])
    elif outcome == "APPARATUS_FAILURE":
        assert p["apparatus_failure"] is True
    elif outcome == "FAIL_JSON_MODE_COMPATIBILITY":
        assert p["apparatus_failure"] is False
        assert p["json_mode_compatibility_failure_count"] > 0
    elif outcome == "FAIL_STRUCTURED_CONTRACT":
        assert p["apparatus_failure"] is False
        assert p["json_mode_compatibility_failure_count"] == 0
        assert p["terminal_exact_structured_parse_invalid_count"] > 0
    elif outcome == "FAIL_COMPLETION":
        assert p["apparatus_failure"] is False
        assert p["json_mode_compatibility_failure_count"] == 0
        assert p["terminal_exact_structured_parse_invalid_count"] == 0
    for key in (
        "scientific_scoring_performed", "acceptance_action_authorized",
        "production_historical_substrate_enabled", "raw_credentials_persisted",
        "raw_provider_response_body_persisted", "raw_provider_error_body_or_message_persisted",
        "raw_final_response_content_persisted", "same_request_stream_rerun_allowed",
    ):
        assert p[key] is False
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
