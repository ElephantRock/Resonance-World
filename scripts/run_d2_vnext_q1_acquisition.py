#!/usr/bin/env python3
# ruff: noqa: E501
"""Run one explicitly authorized D2-vNext-Q1 qualification shard.

The runner is construction-only until an exact-candidate Q1-A or Q1-B marker is
separately authorized. It reuses the S2 task/call mechanism and adds Q1 bounded
terminal-failure observability.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import d2_vnext_q1_acquisition_core as core
import d2_vnext_q1_hermes_client as transport
import materialize_d2_vnext_q1_acquisition as materializer
import run_d2_vnext_s2_source_acquisition as s2runner
import run_d2d_source_acquisition as base

ISSUE = 290
MODEL = "glm-5.3"
TEMPERATURE = 0.8

STAGE_CONFIG = {
    core.STAGE_A: {
        "marker": Path("research/d2_vnext_q1/RUN_D2_VNEXT_Q1_A"),
        "auth_env": "D2_VNEXT_Q1_A_EXECUTION_AUTHORIZED",
        "authorization": "D2_vNext_Q1_A_exact_candidate_acquisition_qualification_and_4608_send_cap_explicitly_authorized",
        "campaign_send_cap": 4608,
        "cohort_lock": Path("research/d2_vnext_q1/D2_VNEXT_Q1_A_COHORT_LOCK.json"),
        "shard_map": Path("research/d2_vnext_q1/D2_VNEXT_Q1_A_SHARD_MAP.json"),
    },
    core.STAGE_B: {
        "marker": Path("research/d2_vnext_q1/RUN_D2_VNEXT_Q1_B"),
        "auth_env": "D2_VNEXT_Q1_B_EXECUTION_AUTHORIZED",
        "authorization": "D2_vNext_Q1_B_exact_candidate_acquisition_qualification_and_27648_send_cap_explicitly_authorized",
        "campaign_send_cap": 27648,
        "cohort_lock": Path("research/d2_vnext_q1/D2_VNEXT_Q1_B_COHORT_LOCK.json"),
        "shard_map": Path("research/d2_vnext_q1/D2_VNEXT_Q1_B_SHARD_MAP.json"),
        "q1_a_closeout": Path("research/d2_vnext_q1/D2_VNEXT_Q1_A_QUALIFICATION_CLOSEOUT.json"),
    },
}


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class _StageCoreAdapter:
    def __init__(self, stage: str) -> None:
        self.stage = stage

    def __getattr__(self, name: str) -> Any:
        return getattr(core, name)

    def schema_and_local_index(self, pair_index: int) -> tuple[str, int]:
        return core.schema_and_local_index(self.stage, pair_index)


class _StageMaterializerAdapter:
    def __init__(self, stage: str) -> None:
        self.stage = stage
        self.EXPECTED_COHORT_SHA256 = materializer.EXPECTED_COHORT_SHA256[stage]

    def case_bundle(self, pair_index: int) -> dict[str, Any]:
        return materializer.case_bundle(self.stage, pair_index)

    def pair_lock_record(self, pair_index: int) -> dict[str, Any]:
        return materializer.pair_lock_record(self.stage, pair_index)


@contextmanager
def _stage_base_context(stage: str) -> Iterator[None]:
    original = (
        base.core,
        base.materializer,
        base.EXPECTED_COHORT_SHA256,
        base.BEHAVIORAL_OBJECTIVE,
        base.MODEL,
        base.TEMPERATURE,
        base._call_record,
    )
    stage_core = _StageCoreAdapter(stage)
    stage_materializer = _StageMaterializerAdapter(stage)
    base.core = stage_core
    base.materializer = stage_materializer
    base.EXPECTED_COHORT_SHA256 = stage_materializer.EXPECTED_COHORT_SHA256
    base.BEHAVIORAL_OBJECTIVE = s2runner.BEHAVIORAL_OBJECTIVE
    base.MODEL = MODEL
    base.TEMPERATURE = TEMPERATURE
    base._call_record = s2runner._s2_call_record
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


def _marker_record(stage: str) -> dict[str, str]:
    config = STAGE_CONFIG[stage]
    marker = config["marker"]
    assert isinstance(marker, Path)
    if not marker.exists():
        raise RuntimeError(f"D2-vNext-Q1 {stage} authorization marker is absent")
    lines = [line for line in marker.read_text().splitlines() if line]
    if any("=" not in line for line in lines):
        raise RuntimeError(f"D2-vNext-Q1 {stage} authorization marker is malformed")
    fields = dict(line.split("=", 1) for line in lines)
    required = {
        "candidate_sha",
        "issue",
        "authorization",
        "maximum_physical_sends_campaign",
    }
    if stage == core.STAGE_B:
        required.add("q1_a_result_sha256")
    if set(fields) != required:
        raise RuntimeError(f"D2-vNext-Q1 {stage} authorization marker fields are invalid")
    candidate = fields["candidate_sha"]
    if len(candidate) != 40 or any(ch not in "0123456789abcdef" for ch in candidate):
        raise RuntimeError("D2-vNext-Q1 candidate SHA is invalid")
    if fields["issue"] != str(ISSUE):
        raise RuntimeError("D2-vNext-Q1 authorization issue is invalid")
    if fields["authorization"] != config["authorization"]:
        raise RuntimeError("D2-vNext-Q1 authorization string is invalid")
    if fields["maximum_physical_sends_campaign"] != str(config["campaign_send_cap"]):
        raise RuntimeError("D2-vNext-Q1 campaign send-cap authorization is invalid")
    if stage == core.STAGE_B:
        closeout_path = config["q1_a_closeout"]
        assert isinstance(closeout_path, Path)
        if not closeout_path.exists():
            raise RuntimeError("Q1-B requires preserved Q1-A qualification closeout")
        closeout = json.loads(closeout_path.read_text())
        if closeout.get("classification") != "D2-vNext-Q1-A-PASS":
            raise RuntimeError("Q1-B requires frozen Q1-A PASS classification")
        if file_sha256(closeout_path) != fields["q1_a_result_sha256"]:
            raise RuntimeError("Q1-B Q1-A closeout hash authorization mismatch")
    return fields


def assert_authorized(stage: str) -> dict[str, str]:
    config = STAGE_CONFIG[stage]
    if os.environ.get(str(config["auth_env"])) != "1":
        raise RuntimeError(f"D2-vNext-Q1 {stage} provider execution is not authorized")
    return _marker_record(stage)


def verify_frozen_inputs(stage: str) -> tuple[dict[str, Any], dict[str, Any]]:
    config = STAGE_CONFIG[stage]
    lock_path = config["cohort_lock"]
    map_path = config["shard_map"]
    assert isinstance(lock_path, Path) and isinstance(map_path, Path)
    committed_lock = json.loads(lock_path.read_text())
    committed_map = json.loads(map_path.read_text())
    expected_lock = materializer.build_cohort_lock(stage)
    expected_map = materializer.build_shard_map(stage)
    if committed_lock != expected_lock:
        raise AssertionError(f"D2-vNext-Q1 {stage} committed cohort-lock drift")
    if committed_map != expected_map:
        raise AssertionError(f"D2-vNext-Q1 {stage} committed shard-map drift")
    if committed_lock["cohort_pairs_sha256"] != materializer.EXPECTED_COHORT_SHA256[stage]:
        raise AssertionError(f"D2-vNext-Q1 {stage} cohort hash pin mismatch")
    return committed_lock, committed_map


def _rename_pair(stage: str, record: dict[str, Any]) -> dict[str, Any]:
    record = dict(record)
    public_id = record.get("pair_public_id")
    if isinstance(public_id, str) and public_id.startswith("d2d-"):
        slug = stage.lower().replace("-", "")
        record["pair_public_id"] = f"d2-vnext-{slug}-" + public_id[len("d2d-") :]
    record["stage"] = stage
    return record


def run_pair_safe(client: transport.Client, stage: str, pair_index: int) -> dict[str, Any]:
    schema_id, local_index = core.schema_and_local_index(stage, pair_index)
    slug = stage.lower().replace("-", "")
    pair_public_id = f"d2-vnext-{slug}-{schema_id}-pair-{local_index:03d}"
    try:
        record = base.run_pair(client, pair_index)
        return _rename_pair(stage, record)
    except transport.Q1LogicalCallFailure as exc:
        terminal = dict(exc.evidence)
        terminal.update(
            {
                "pair_public_id": pair_public_id,
                "pair_index": pair_index,
                "schema_id": schema_id,
            }
        )
        transport.assert_failure_evidence_has_no_raw_content(terminal)
        return {
            "status": "failed",
            "stage": stage,
            "pair_index": pair_index,
            "schema_id": schema_id,
            "schema_pair_index": local_index,
            "pair_public_id": pair_public_id,
            "failure_class": "q1_logical_call_no_accepted_exact_completion",
            "error_type": "RuntimeError",
            "error_sha256": transport.TERMINAL_FAILURE_SHA256,
            "terminal_failure": terminal,
        }
    except Exception as exc:
        fingerprint = hashlib.sha256(
            f"{type(exc).__name__}:{str(exc)[:500]}".encode()
        ).hexdigest()
        return {
            "status": "failed",
            "stage": stage,
            "pair_index": pair_index,
            "schema_id": schema_id,
            "schema_pair_index": local_index,
            "pair_public_id": pair_public_id,
            "failure_class": "q1_pair_runtime_or_instrumentation_failure",
            "error_type": type(exc).__name__,
            "error_sha256": fingerprint,
            "terminal_failure": None,
        }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=core.STAGES, required=True)
    parser.add_argument("--shard-id", type=int, required=True)
    parser.add_argument("--output-dir", default="output/d2-vnext-q1-provider-shard")
    args = parser.parse_args()

    stage = args.stage
    marker = assert_authorized(stage)
    lock, shard_map = verify_frozen_inputs(stage)
    if not 0 <= args.shard_id < int(shard_map["shard_count"]):
        raise AssertionError("unknown D2-vNext-Q1 shard")
    shard = shard_map["shards"][args.shard_id]
    pair_indices = [int(value) for value in shard["pair_indices"]]
    if len(pair_indices) != 16:
        raise AssertionError("Q1 provider shard must contain 16 pairs")

    key = os.environ.get("ZAI_API_KEY", "")
    if not key:
        raise RuntimeError("ZAI_API_KEY is required for authorized D2-vNext-Q1 execution")

    budget = transport.new_shard_budget()
    ledger = transport.TransportLedger()
    workers = transport.ProviderWorkerTracker()
    client = transport.Client(key, budget, ledger)
    with transport.guarded_shard_transport(budget, ledger, workers), _stage_base_context(stage):
        pair_records = [run_pair_safe(client, stage, index) for index in pair_indices]

    if workers.alive_after_drain != 0 or not workers.transport_hooks_restored:
        raise RuntimeError("D2-vNext-Q1 provider workers/hooks did not close cleanly")
    if ledger.attribution_mismatches != 0:
        raise RuntimeError("D2-vNext-Q1 logical attribution mismatch")

    complete = [row for row in pair_records if row["status"] == "complete"]
    failed = [row for row in pair_records if row["status"] != "complete"]
    output = {
        "schema": "d2-vnext-q1-acquisition-provider-shard-v0.1",
        "study_stream": "D2-vNext-Q1",
        "stage": stage,
        "fresh_namespace": core.NAMESPACE,
        "status": "provider_shard_complete_unclassified",
        "classification": None,
        "authorized_candidate_sha": marker["candidate_sha"],
        "authorization_scope": f"exact_candidate_{stage}_acquisition_qualification_and_bounded_provider_execution",
        "authorization_marker_sha256": file_sha256(STAGE_CONFIG[stage]["marker"]),
        "shard_id": args.shard_id,
        "pair_indices": pair_indices,
        "schema_counts": shard["schema_counts"],
        "attempted_pairs": len(pair_records),
        "complete_pairs": len(complete),
        "failed_pairs": len(failed),
        "requested_model": MODEL,
        "effective_model_identity_observed": False,
        "effective_model": None,
        "temperature": TEMPERATURE,
        "thinking": "disabled",
        "response_format": {"type": "json_object"},
        "cohort_lock": lock,
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
        "cohort_lock_file_sha256": file_sha256(STAGE_CONFIG[stage]["cohort_lock"]),
        "shard_map_sha256": file_sha256(STAGE_CONFIG[stage]["shard_map"]),
        "qualification_campaign_executed": True,
        "scientific_effect_gates_authorized": False,
        "registry_promotion_authorized": False,
        "acceptance_action_authorized": False,
        "production_historical_substrate_enabled": False,
    }
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    slug = stage.lower().replace("-", "")
    output_path = out / f"d2-vnext-{slug}-provider-shard-{args.shard_id:02d}.json"
    output_path.write_bytes(canonical_bytes(output))
    manifest = {
        "schema": "d2-vnext-q1-acquisition-provider-shard-manifest-v0.1",
        "study_stream": "D2-vNext-Q1",
        "stage": stage,
        "shard_id": args.shard_id,
        "provider_shard_output_sha256": file_sha256(output_path),
        "attempted_pairs": len(pair_records),
        "complete_pairs": len(complete),
        "failed_pairs": len(failed),
        "cohort_pairs_sha256": materializer.EXPECTED_COHORT_SHA256[stage],
        "physical_provider_sends_observed": budget.total_sends,
        "classification": None,
        "scientific_effect_gates_authorized": False,
        "registry_promotion_authorized": False,
        "production_historical_substrate_enabled": False,
    }
    (out / f"d2-vnext-{slug}-provider-shard-{args.shard_id:02d}-manifest.json").write_bytes(
        canonical_bytes(manifest)
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
