#!/usr/bin/env python3
# ruff: noqa
"""Bounded post-execution authority verifier for #270."""
import json,sys
from pathlib import Path

p=json.loads(Path("output/d2-canonical-json-prompt-result.json").read_text())
outcome=p["qualification_outcome"]
assert p["schema"]=="d2-canonical-json-prompt-result-v0.1" and p["issue"]==270 and p["candidate_sha"]==sys.argv[1]
assert p["fresh_namespace"]=="rw.d2-canonical-json-prompt.v1"
assert p["request_intervention"]=={"response_format":{"type":"json_object"}}
assert p["prompt_intervention"]=="canonical_json_exemplar_and_explicit_array_positional_constraints"
assert p["system_prompt_sha256"]=="fb35b51c6a6243543cb628a66607ca77f06fbdcc504c923d3c3b2c342eeab7f7"
assert p["parser_intervention"]=="none_unchanged_exact_eight_action_contract"
assert p["terminal_adapter_git_blob_sha"]=="ba16d2eb4b7255437c8ab224e91d5ed093897990"
assert p["registered_probe_count"]==p["attempted_probe_count"]==72
assert 0<=p["effective_completed_count"]<=72 and 0<=p["physical_provider_sends_observed_total"]<=180
assert outcome in {"PASS","FAIL_STRUCTURED_CONTRACT","FAIL_JSON_MODE_COMPATIBILITY","FAIL_COMPLETION","APPARATUS_FAILURE"}
assert p["qualification_pass"] is (outcome=="PASS")
if outcome=="PASS":
    assert p["effective_completed_count"]==72
    assert p["exact_structured_parse_invalid_count"]==0
    assert p["json_mode_compatibility_failure_count"]==0
    assert p["apparatus_failure"] is False
    assert p["unexpected_outbound_http_requests_blocked"]==0
    assert p["provider_attempts_blocked_by_cap"]==0
    assert p["logical_attribution_mismatch_blocks"]==0
    assert p["provider_worker_threads_alive_after_drain"]==0
    assert p["transport_hooks_restored_after_worker_drain"] is True
    assert all(r["final_response_length"]>0 and r["exact_structured_parse_valid"] and r["exact_attributed_clean_transport"] for r in p["probes"])
for k in ("scientific_scoring_performed","acceptance_action_authorized","production_historical_substrate_enabled","raw_credentials_persisted","raw_provider_response_body_persisted","raw_provider_error_body_or_message_persisted","raw_final_response_content_persisted","same_request_stream_rerun_allowed"):
    assert p[k] is False
