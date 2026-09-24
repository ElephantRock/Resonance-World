#!/usr/bin/env python3
# ruff: noqa: E501
"""Execute one explicitly authorized D2-vNext-S2 scientific provider shard."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import d2_vnext_s2_acquisition_core as core
import d2_vnext_s2_hermes_client as transport
import materialize_d2_vnext_s2_source_acquisition as materializer
import run_d2d_source_acquisition as base

ISSUE = 279
PAIR_COUNT = 384
SHARD_COUNT = 24
MODEL = "glm-5.3"
TEMPERATURE = 0.8
MARKER_PATH = Path("research/d2_vnext_s2/RUN_D2_VNEXT_S2_SOURCE_ACQUISITION")
AUTH_ENV = "D2_VNEXT_S2_SCIENTIFIC_EXECUTION_AUTHORIZED"
AUTHORIZATION_STRING = (
    "D2_vNext_S2_exact_candidate_scientific_campaign_and_48000_send_cap_explicitly_authorized"
)
BEHAVIORAL_OBJECTIVE = (
    "Choose exactly one action from KAPPA, MICA, ORBIT, VELA for each four-feature "
    "integer case. Each Field owns a fixed hidden local policy belonging to the "
    "registered D2-vNext-S2 calibration schema."
)


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _s2_call_record(result: dict[str, Any], strategy: str) -> dict[str, Any]:
    """Persist scientific call evidence plus bounded #276 retry observability."""
    return {
        "model": result["model"],
        "temperature": result["temperature"],
        "request_id": result["request_id"],
        "prompt_sha256": result["prompt_sha256"],
        "response_sha256": result["response_sha256"],
        "strategy_sha256": hashlib.sha256(strategy.encode()).hexdigest(),
        "strategy_present": result["strategy_present"],
        "extra_key_count": result["extra_key_count"],
        "physical_attempts": len(result["attempts"]),
        "attempt_log": result["attempts"],
        "usage": result["usage"],
        "total_latency_ms": result["total_latency_ms"],
        "retry_used": result["retry_used"],
        "retry_eligible_after_first": result["retry_eligible_after_first"],
        "accepted_attempt_index": result["accepted_attempt_index"],
        "agent_invocation_count": result["agent_invocation_count"],
        "first_attempt_parse_valid": result["first_attempt_parse_valid"],
        "first_attempt_parse_diagnostic": result["first_attempt_parse_diagnostic"],
        "first_attempt_final_response_length": result[
            "first_attempt_final_response_length"
        ],
        "first_attempt_final_response_sha256": result[
            "first_attempt_final_response_sha256"
        ],
        "second_attempt_parse_valid": result["second_attempt_parse_valid"],
        "second_attempt_parse_diagnostic": result[
            "second_attempt_parse_diagnostic"
        ],
        "second_attempt_final_response_length": result[
            "second_attempt_final_response_length"
        ],
        "second_attempt_final_response_sha256": result[
            "second_attempt_final_response_sha256"
        ],
        "retry_prompt_sha256": result["retry_prompt_sha256"],
        "retry_raw_first_response_content_included": result[
            "retry_raw_first_response_content_included"
        ],
        "hermes_completed": result["hermes_completed"],
        "terminal_iteration_override_used": result[
            "terminal_iteration_override_used"
        ],
        "adapter_reason": result["adapter_reason"],
        "json_mode_compatibility_failure": result[
            "json_mode_compatibility_failure"
        ],
    }


@contextmanager
def _fresh_base_context() -> Iterator[None]:
    """Bind the historical arm logic to this fresh stratum for one shard only."""
    original = (
        base.core,
        base.materializer,
        base.EXPECTED_COHORT_SHA256,
        base.BEHAVIORAL_OBJECTIVE,
        base.MODEL,
        base.TEMPERATURE,
        base._call_record,
    )
    base.core = core
    base.materializer = materializer
    base.EXPECTED_COHORT_SHA256 = materializer.EXPECTED_COHORT_SHA256
    base.BEHAVIORAL_OBJECTIVE = BEHAVIORAL_OBJECTIVE
    base.MODEL = MODEL
    base.TEMPERATURE = TEMPERATURE
    base._call_record = _s2_call_record
    try:
        yield
    finally:
        (
            base.core,
            base.materializer,
            base.EXPECTED_COHORT_SHA256,
            base.BEHAVIORAL_OBJECTIVE,
            base.MODEL,
            base.TEMPERATURE,
            base._call_record,
        ) = original


def marker_record() -> dict[str, str]:
    if not MARKER_PATH.exists():
        raise RuntimeError("D2-vNext-S2 authorization marker is absent")
    lines = [line for line in MARKER_PATH.read_text().splitlines() if line]
    if len(lines) != 4 or any("=" not in line for line in lines):
        raise RuntimeError("D2-vNext-S2 authorization marker is malformed")
    fields = dict(line.split("=", 1) for line in lines)
    if set(fields) != {"candidate_sha", "issue", "authorization", "maximum_physical_sends_campaign"}:
        raise RuntimeError("D2-vNext-S2 authorization marker fields are invalid")
    candidate = fields["candidate_sha"]
    if len(candidate) != 40 or any(ch not in "0123456789abcdef" for ch in candidate):
        raise RuntimeError("D2-vNext-S2 candidate SHA is invalid")
    if fields["issue"] != str(ISSUE):
        raise RuntimeError("D2-vNext-S2 authorization issue is invalid")
    if fields["authorization"] != AUTHORIZATION_STRING:
        raise RuntimeError("D2-vNext-S2 authorization string is invalid")
    if fields["maximum_physical_sends_campaign"] != "48000":
        raise RuntimeError("D2-vNext-S2 campaign send-cap authorization is invalid")
    return fields


def assert_authorized() -> dict[str, str]:
    if os.environ.get(AUTH_ENV) != "1":
        raise RuntimeError("D2-vNext-S2 scientific/provider execution is not authorized")
    return marker_record()


def verify_cohort_lock(path: Path) -> dict[str, Any]:
    committed = json.loads(path.read_text())
    expected = materializer.build_cohort_lock()
    if committed != expected:
        raise AssertionError("D2-vNext-S2 committed cohort lock drift")
    if not materializer.EXPECTED_COHORT_SHA256:
        raise AssertionError("D2-vNext-S2 cohort hash is not prospectively pinned")
    if committed["cohort_pairs_sha256"] != materializer.EXPECTED_COHORT_SHA256:
        raise AssertionError("D2-vNext-S2 cohort hash pin mismatch")
    return expected


def load_shard_range(shard_id: int, path: Path) -> tuple[int, int, str]:
    data = json.loads(path.read_text())
    if data != materializer.build_shard_map():
        raise AssertionError("D2-vNext-S2 committed shard-map drift")
    if not 0 <= shard_id < SHARD_COUNT:
        raise AssertionError("unknown D2-vNext-S2 shard")
    row = data["shards"][shard_id]
    return int(row["start_pair"]), int(row["end_pair"]), str(row["schema_id"])


def _rename_pair(record: dict[str, Any]) -> dict[str, Any]:
    record = dict(record)
    public_id = record.get("pair_public_id")
    if isinstance(public_id, str) and public_id.startswith("d2d-"):
        record["pair_public_id"] = "d2-vnext-s2-" + public_id[len("d2d-") :]
    return record


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--shard-id", type=int, required=True)
    parser.add_argument("--output-dir", default="output/d2-vnext-s2-provider-shard")
    parser.add_argument(
        "--cohort-lock",
        default="research/d2_vnext_s2/d2-vnext-s2-source-acquisition-cohort-lock.json",
    )
    parser.add_argument("--shard-map", default="research/d2_vnext_s2/D2_VNEXT_S2_SHARD_MAP.json")
    parser.add_argument("--plan", default="research/d2_vnext_s2/PLAN.md")
    parser.add_argument("--request-plan", default="research/d2_vnext_s2/D2_VNEXT_S2_REQUEST_PLAN.json")
    parser.add_argument("--schema-suite", default="research/d2_vnext_s2/D2_VNEXT_S2_SCHEMA_SUITE.json")
    parser.add_argument("--sample-size", default="research/d2_vnext_s2/D2_VNEXT_S2_SAMPLE_SIZE.json")
    args = parser.parse_args()

    marker = assert_authorized()
    start_pair, end_pair, schema_id = load_shard_range(args.shard_id, Path(args.shard_map))
    lock_summary = verify_cohort_lock(Path(args.cohort_lock))
    key = os.environ.get("ZAI_API_KEY", "")
    if not key:
        raise RuntimeError("ZAI_API_KEY is required for authorized D2-vNext-S2 execution")

    budget = transport.new_shard_budget()
    ledger = transport.TransportLedger()
    workers = transport.ProviderWorkerTracker()
    client = transport.Client(key, budget, ledger)
    with transport.guarded_shard_transport(budget, ledger, workers), _fresh_base_context():
        pair_records = [
            _rename_pair(base.run_pair_safe(client, index))
            for index in range(start_pair, end_pair + 1)
        ]

    if workers.alive_after_drain != 0 or not workers.transport_hooks_restored:
        raise RuntimeError("D2-vNext-S2 provider workers/hooks did not close cleanly")
    if ledger.attribution_mismatches != 0:
        raise RuntimeError("D2-vNext-S2 logical attribution mismatch")

    complete = [row for row in pair_records if row["status"] == "complete"]
    failed = [row for row in pair_records if row["status"] != "complete"]
    output = {
        "schema": "d2-vnext-s2-source-acquisition-provider-shard-v0.1",
        "study_stream": "D2-vNext-S2",
        "fresh_namespace": core.NAMESPACE,
        "status": "provider_shard_complete_unclassified",
        "classification": None,
        "authorized_candidate_sha": marker["candidate_sha"],
        "authorization_scope": "exact_candidate_scientific_campaign_and_bounded_provider_execution",
        "authorization_marker_sha256": file_sha256(MARKER_PATH),
        "shard_id": args.shard_id,
        "schema_id": schema_id,
        "start_pair": start_pair,
        "end_pair": end_pair,
        "attempted_pairs": len(pair_records),
        "complete_pairs": len(complete),
        "failed_pairs": len(failed),
        "requested_model": MODEL,
        "effective_model_identity_observed": False,
        "effective_model": None,
        "temperature": TEMPERATURE,
        "thinking": "disabled",
        "response_format": {"type": "json_object"},
        "cohort_lock": lock_summary,
        "pair_records": pair_records,
        "transport_accounting": {
            "logical_calls_started": client.logical_calls_started,
            "logical_calls_completed": client.logical_calls_completed,
            "logical_call_failures": client.logical_call_failures,
            "format_regeneration_retries_used": client.retry_used_count,
            "terminal_iteration_overrides_used": client.terminal_iteration_override_count,
            "physical_provider_sends_observed": budget.total_sends,
            "maximum_physical_provider_sends_per_logical_call": transport.MAX_PHYSICAL_SENDS_PER_LOGICAL_CALL,
            "maximum_physical_provider_sends_per_shard": transport.MAX_PHYSICAL_SENDS_PER_SHARD,
            "provider_sends_blocked_by_budget": budget.blocked_budget,
            "unexpected_outbound_http_requests_blocked": budget.blocked_unexpected,
            "logical_attribution_mismatch_blocks": ledger.attribution_mismatches,
            "provider_workers_observed": workers.observed,
            "provider_workers_alive_after_drain": workers.alive_after_drain,
            "transport_hooks_restored_after_drain": workers.transport_hooks_restored,
            "allowed_endpoint_prefix": transport.BASE_URL,
        },
        "plan_sha256": file_sha256(Path(args.plan)),
        "request_plan_sha256": file_sha256(Path(args.request_plan)),
        "schema_suite_sha256": file_sha256(Path(args.schema_suite)),
        "sample_size_sha256": file_sha256(Path(args.sample_size)),
        "cohort_lock_file_sha256": file_sha256(Path(args.cohort_lock)),
        "shard_map_sha256": file_sha256(Path(args.shard_map)),
        "scientific_campaign_executed": True,
        "registry_promotion_authorized": False,
        "acceptance_action_authorized": False,
        "production_historical_substrate_enabled": False,
    }
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    output_path = out / f"d2-vnext-s2-provider-shard-{args.shard_id:02d}.json"
    output_path.write_bytes(canonical_bytes(output))
    manifest = {
        "schema": "d2-vnext-s2-source-acquisition-provider-shard-manifest-v0.1",
        "study_stream": "D2-vNext-S2",
        "shard_id": args.shard_id,
        "schema_id": schema_id,
        "provider_shard_output_sha256": file_sha256(output_path),
        "attempted_pairs": len(pair_records),
        "complete_pairs": len(complete),
        "failed_pairs": len(failed),
        "cohort_pairs_sha256": materializer.EXPECTED_COHORT_SHA256,
        "physical_provider_sends_observed": budget.total_sends,
        "classification": None,
        "registry_promotion_authorized": False,
        "production_historical_substrate_enabled": False,
    }
    (out / f"d2-vnext-s2-provider-shard-{args.shard_id:02d}-manifest.json").write_bytes(
        canonical_bytes(manifest)
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
