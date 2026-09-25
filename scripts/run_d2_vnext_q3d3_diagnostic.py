#!/usr/bin/env python3
# ruff: noqa: E501
"""Run one separately authorized Q3-D3 upstream HTTP/SDK-boundary shard."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import d2_vnext_q3d2_hermes_client as semantic_observer
import d2_vnext_q3d3_diagnostic_core as core
import d2_vnext_q3d3_http_observer as http_observer
import d2_vnext_q3d_hermes_client as transport
import materialize_d2_vnext_q3d3_diagnostic as materializer
import run_d2_vnext_q2_acquisition as q2runner
import run_d2_vnext_s2_source_acquisition as s2runner
import run_d2d_source_acquisition as base

ISSUE = 306
MODEL = "glm-5.3"
TEMPERATURE = 0.8
MARKER_PATH = Path("research/d2_vnext_q3d3/RUN_D2_VNEXT_Q3D3")
AUTH_ENV = "D2_VNEXT_Q3D3_EXECUTION_AUTHORIZED"
AUTHORIZATION_STRING = (
    "D2_vNext_Q3_D3_exact_candidate_http_sdk_boundary_diagnostic_and_2304_send_cap_explicitly_authorized"
)
CAMPAIGN_SEND_CAP = 2304
COHORT_LOCK_PATH = Path("research/d2_vnext_q3d3/D2_VNEXT_Q3D3_COHORT_LOCK.json")
SHARD_MAP_PATH = Path("research/d2_vnext_q3d3/D2_VNEXT_Q3D3_SHARD_MAP.json")


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _q3d3_call_record(result: dict[str, Any], strategy: str) -> dict[str, Any]:
    return q2runner._q2_call_record(result, strategy)


@contextmanager
def _base_context() -> Iterator[None]:
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
    base.BEHAVIORAL_OBJECTIVE = s2runner.BEHAVIORAL_OBJECTIVE
    base.MODEL = MODEL
    base.TEMPERATURE = TEMPERATURE
    base._call_record = _q3d3_call_record
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
        raise RuntimeError("D2-vNext-Q3-D3 authorization marker is absent")
    lines = [line for line in MARKER_PATH.read_text().splitlines() if line]
    if any("=" not in line for line in lines):
        raise RuntimeError("Q3-D3 authorization marker malformed")
    fields = dict(line.split("=", 1) for line in lines)
    required = {
        "candidate_sha",
        "issue",
        "authorization",
        "maximum_physical_sends_campaign",
    }
    if set(fields) != required:
        raise RuntimeError("Q3-D3 authorization marker fields invalid")
    if (
        fields["issue"] != str(ISSUE)
        or fields["authorization"] != AUTHORIZATION_STRING
        or fields["maximum_physical_sends_campaign"] != str(CAMPAIGN_SEND_CAP)
    ):
        raise RuntimeError("Q3-D3 authorization marker mismatch")
    candidate = fields["candidate_sha"]
    if len(candidate) != 40 or any(ch not in "0123456789abcdef" for ch in candidate):
        raise RuntimeError("Q3-D3 candidate SHA invalid")
    return fields


def assert_authorized() -> dict[str, str]:
    if os.environ.get(AUTH_ENV) != "1":
        raise RuntimeError("D2-vNext-Q3-D3 provider execution is not authorized")
    return marker_record()


def verify_frozen_inputs() -> tuple[dict[str, Any], dict[str, Any]]:
    lock = json.loads(COHORT_LOCK_PATH.read_text())
    shard_map = json.loads(SHARD_MAP_PATH.read_text())
    if lock != materializer.build_cohort_lock():
        raise AssertionError("Q3-D3 committed cohort-lock drift")
    if shard_map != materializer.build_shard_map():
        raise AssertionError("Q3-D3 committed shard-map drift")
    if int(shard_map["maximum_physical_provider_sends_campaign"]) != CAMPAIGN_SEND_CAP:
        raise AssertionError("Q3-D3 campaign cap drift")
    return lock, shard_map


def _rename_pair(record: dict[str, Any]) -> dict[str, Any]:
    result = dict(record)
    pid = result.get("pair_public_id")
    if isinstance(pid, str) and pid.startswith("d2d-"):
        result["pair_public_id"] = "d2-vnext-q3d3-" + pid[len("d2d-") :]
    result["stage"] = core.STAGE
    return result


def _semantic_rows(record: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for invocation in record.get("agent_invocations", []):
        if isinstance(invocation, dict):
            semantic = invocation.get("semantic_completions", [])
            if isinstance(semantic, list):
                rows.extend(row for row in semantic if isinstance(row, dict))
    return rows


def _transport_rows(record: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        send
        for semantic in _semantic_rows(record)
        for send in semantic.get("provider_sends", [])
        if isinstance(send, dict)
    ]


def _invocation_http_rows(
    invocation: dict[str, Any],
    http_by_send: dict[int, dict[str, Any]],
) -> list[dict[str, Any]]:
    indices: list[int] = []
    for semantic in invocation.get("semantic_completions", []):
        if not isinstance(semantic, dict):
            continue
        for send in semantic.get("provider_sends", []):
            if isinstance(send, dict) and send.get("logical_send_index") is not None:
                indices.append(int(send["logical_send_index"]))
    return [copy.deepcopy(http_by_send[index]) for index in indices if index in http_by_send]


def _last_http_for_semantic(
    semantic: dict[str, Any] | None,
    http_by_send: dict[int, dict[str, Any]],
) -> dict[str, Any] | None:
    if semantic is None:
        return None
    response_indices = [
        int(send["logical_send_index"])
        for send in semantic.get("provider_sends", [])
        if isinstance(send, dict)
        and send.get("logical_send_index") is not None
        and send.get("http_status") is not None
        and send.get("transport_error_type") is None
    ]
    if not response_indices:
        return None
    return http_by_send.get(response_indices[-1])


def _augment_observation(
    observation: dict[str, Any],
    recorder: http_observer.HTTPBodyRecorder,
) -> dict[str, Any]:
    result = copy.deepcopy(observation)
    result["schema"] = "d2-vnext-q3d3-structural-observability-record-v0.1"
    result["study_stream"] = "D2-vNext-Q3-D3"
    result["stage"] = "Q3-D3"
    logical_index = int(result["logical_call_index"])
    http_rows = recorder.rows(logical_index)
    http_by_send = {int(row["logical_send_index"]): row for row in http_rows}
    semantic_rows = _semantic_rows(result)
    defects = list(result.get("observability_defects", []))
    defects.extend(http_observer.http_transport_coverage_defects(_transport_rows(result), http_rows))
    defects.extend(http_observer.semantic_http_association_defects(semantic_rows, http_rows))

    invocations = []
    for invocation in result.get("agent_invocations", []):
        inv = copy.deepcopy(invocation)
        semantic = [row for row in inv.get("semantic_completions", []) if isinstance(row, dict)]
        last_semantic = semantic[-1] if semantic else None
        last_http = _last_http_for_semantic(last_semantic, http_by_send)
        inv["http_body_records"] = _invocation_http_rows(inv, http_by_send)
        adapter = inv.get("adapter_snapshot", {})
        hermes = inv.get("hermes_terminal", {})
        inv["q3d3_boundary_classification"] = http_observer.classify_upstream_boundary(
            runtime_exception=inv.get("loop_termination_reason") == "runtime_exception",
            http_body=last_http,
            sdk_semantic=last_semantic,
            hermes_terminal_present=bool(hermes.get("present")),
            adapter_candidate_present=bool(adapter.get("candidate_present")),
            parse_valid=bool(adapter.get("exact_structured_parse_valid")),
            accepted_exact_completion=bool(adapter.get("accepted_exact_completion")),
        )
        invocations.append(inv)
    result["agent_invocations"] = invocations
    result["http_body_records"] = copy.deepcopy(http_rows)
    result["observability_defects"] = sorted(set(str(item) for item in defects))
    if result.get("accepted_exact_completion") is True:
        result["q3d3_boundary_classification"] = "accepted_exact_completion"
    elif invocations:
        result["q3d3_boundary_classification"] = str(
            invocations[-1]["q3d3_boundary_classification"]
        )
    else:
        result["q3d3_boundary_classification"] = "unclassified_observability_defect"
    http_observer.assert_no_raw_content(result)
    transport.assert_no_raw_content(result)
    return result


def _pair_observations(
    client: transport.Client,
    recorder: http_observer.HTTPBodyRecorder,
    start: int,
    *,
    pair_public_id: str,
    schema_id: str,
) -> list[dict[str, Any]]:
    rows = []
    for observation in client.observability_records[start:]:
        result = _augment_observation(observation, recorder)
        result["pair_public_id"] = pair_public_id
        result["schema_id"] = schema_id
        rows.append(result)
    return rows


def run_pair_safe(
    client: transport.Client,
    recorder: http_observer.HTTPBodyRecorder,
    pair_index: int,
) -> dict[str, Any]:
    schema_id, local_index = core.schema_and_local_index(pair_index)
    pid = f"d2-vnext-q3d3-{schema_id}-pair-{local_index:03d}"
    obs_start = len(client.observability_records)
    try:
        record = _rename_pair(base.run_pair(client, pair_index))
        record["q3d3_observability_records"] = _pair_observations(
            client, recorder, obs_start, pair_public_id=pid, schema_id=schema_id
        )
        return record
    except transport.Q3DLogicalCallFailure as exc:
        terminal = dict(exc.evidence)
        terminal.pop("q3d_observability", None)
        terminal.update({"pair_public_id": pid, "pair_index": pair_index, "schema_id": schema_id})
        transport.assert_no_raw_content(terminal)
        return {
            "status": "failed",
            "stage": core.STAGE,
            "pair_index": pair_index,
            "schema_id": schema_id,
            "schema_pair_index": local_index,
            "pair_public_id": pid,
            "failure_class": "q3d3_logical_call_no_accepted_exact_completion",
            "error_type": "RuntimeError",
            "error_sha256": transport.TERMINAL_FAILURE_SHA256,
            "terminal_failure": terminal,
            "q3d3_observability_records": _pair_observations(
                client, recorder, obs_start, pair_public_id=pid, schema_id=schema_id
            ),
        }
    except Exception as exc:
        fingerprint = hashlib.sha256(
            f"{type(exc).__name__}:{str(exc)[:500]}".encode()
        ).hexdigest()
        return {
            "status": "failed",
            "stage": core.STAGE,
            "pair_index": pair_index,
            "schema_id": schema_id,
            "schema_pair_index": local_index,
            "pair_public_id": pid,
            "failure_class": "q3d3_pair_runtime_or_instrumentation_failure",
            "error_type": type(exc).__name__,
            "error_sha256": fingerprint,
            "terminal_failure": None,
            "q3d3_observability_records": _pair_observations(
                client, recorder, obs_start, pair_public_id=pid, schema_id=schema_id
            ),
        }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--shard-id", type=int, required=True)
    parser.add_argument("--output-dir", default="output/d2-vnext-q3d3-provider-shard")
    args = parser.parse_args()
    marker = assert_authorized()
    lock, shard_map = verify_frozen_inputs()
    if not 0 <= args.shard_id < int(shard_map["shard_count"]):
        raise AssertionError("unknown Q3-D3 shard")
    shard = shard_map["shards"][args.shard_id]
    indices = [int(value) for value in shard["pair_indices"]]
    key = os.environ.get("ZAI_API_KEY", "")
    if not key:
        raise RuntimeError("ZAI_API_KEY is required for authorized Q3-D3 execution")
    budget = transport.new_shard_budget()
    ledger = transport.TransportLedger()
    workers = transport.ProviderWorkerTracker()
    client = transport.Client(key, budget, ledger)
    http_recorder = http_observer.HTTPBodyRecorder()
    with (
        transport.guarded_shard_transport(budget, ledger, workers),
        _base_context(),
        semantic_observer.activate_request_scoped_observer(),
        http_observer.observe_http_response_reads(http_recorder),
    ):
        records = [run_pair_safe(client, http_recorder, pair_index) for pair_index in indices]
    if workers.alive_after_drain != 0 or not workers.transport_hooks_restored:
        raise RuntimeError("Q3-D3 workers/hooks did not close cleanly")
    if ledger.attribution_mismatches != 0:
        raise RuntimeError("Q3-D3 attribution mismatch")
    complete = [row for row in records if row["status"] == "complete"]
    failed = [row for row in records if row["status"] != "complete"]
    output = {
        "schema": "d2-vnext-q3d3-provider-shard-v0.1",
        "study_stream": "D2-vNext-Q3-D3",
        "stage": core.STAGE,
        "fresh_namespace": core.NAMESPACE,
        "status": "provider_shard_complete_unclassified",
        "classification": None,
        "authorized_candidate_sha": marker["candidate_sha"],
        "authorization_scope": "exact_candidate_Q3_D3_http_sdk_boundary_diagnostic_and_bounded_provider_execution",
        "authorization_marker_sha256": file_sha256(MARKER_PATH),
        "shard_id": args.shard_id,
        "pair_indices": indices,
        "schema_counts": shard["schema_counts"],
        "attempted_pairs": len(records),
        "complete_pairs": len(complete),
        "failed_pairs": len(failed),
        "requested_model": MODEL,
        "temperature": TEMPERATURE,
        "thinking": "disabled",
        "response_format": {"type": "json_object"},
        "cohort_lock": lock,
        "pair_records": records,
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
            "http_body_records_observed": len(http_recorder.rows()),
        },
        "cohort_lock_file_sha256": file_sha256(COHORT_LOCK_PATH),
        "shard_map_sha256": file_sha256(SHARD_MAP_PATH),
        "diagnostic_campaign_executed": True,
        "scientific_effect_gates_authorized": False,
        "registry_promotion_authorized": False,
        "acceptance_action_authorized": False,
        "production_historical_substrate_enabled": False,
    }
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"d2-vnext-q3d3-provider-shard-{args.shard_id:02d}.json"
    path.write_bytes(canonical_bytes(output))
    manifest = {
        "schema": "d2-vnext-q3d3-provider-shard-manifest-v0.1",
        "study_stream": "D2-vNext-Q3-D3",
        "stage": core.STAGE,
        "shard_id": args.shard_id,
        "provider_shard_output_sha256": file_sha256(path),
        "attempted_pairs": len(records),
        "complete_pairs": len(complete),
        "failed_pairs": len(failed),
        "cohort_pairs_sha256": materializer.EXPECTED_COHORT_SHA256,
        "physical_provider_sends_observed": budget.total_sends,
        "classification": None,
        "scientific_effect_gates_authorized": False,
        "registry_promotion_authorized": False,
        "production_historical_substrate_enabled": False,
    }
    (out / f"d2-vnext-q3d3-provider-shard-{args.shard_id:02d}-manifest.json").write_bytes(
        canonical_bytes(manifest)
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
