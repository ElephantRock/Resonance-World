#!/usr/bin/env python3
# ruff: noqa: E501
"""Aggregate Q1 provider shards without scientific-effect classification."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import d2_vnext_q1_acquisition_core as core
import materialize_d2_vnext_q1_acquisition as materializer

MAX_PHYSICAL_SENDS_PER_LOGICAL_CALL = 36
MAX_PHYSICAL_SENDS_PER_SHARD = 1152
CAMPAIGN_CAP = {core.STAGE_A: 4608, core.STAGE_B: 27648}
EXPECTED_MODEL = "glm-5.3"
EXPECTED_TEMPERATURE = 0.8


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _find_shard(root: Path, stage: str, shard_id: int) -> Path | None:
    slug = stage.lower().replace("-", "")
    rows = sorted(root.glob(f"**/d2-vnext-{slug}-provider-shard-{shard_id:02d}.json"))
    rows = [path for path in rows if "manifest" not in path.name]
    if not rows:
        return None
    if len(rows) != 1:
        raise AssertionError(f"multiple Q1 outputs for {stage} shard {shard_id}")
    return rows[0]


def _synthetic_failure(stage: str, pair_index: int, reason: str, shard_id: int) -> dict[str, Any]:
    schema_id, local_index = core.schema_and_local_index(stage, pair_index)
    slug = stage.lower().replace("-", "")
    return {
        "status": "failed",
        "stage": stage,
        "pair_index": pair_index,
        "schema_id": schema_id,
        "schema_pair_index": local_index,
        "pair_public_id": f"d2-vnext-{slug}-{schema_id}-pair-{local_index:03d}",
        "failure_class": reason,
        "error_type": None,
        "error_sha256": None,
        "terminal_failure": None,
        "registered_shard_id": shard_id,
    }


def _validate_complete_call(call: dict[str, Any]) -> None:
    if call.get("model") != EXPECTED_MODEL:
        raise AssertionError("Q1 complete call model mismatch")
    temperature = call.get("temperature")
    if isinstance(temperature, bool) or not isinstance(temperature, (int, float)):
        raise AssertionError("Q1 complete call temperature invalid")
    if abs(float(temperature) - EXPECTED_TEMPERATURE) > 1e-12:
        raise AssertionError("Q1 complete call temperature mismatch")
    if call.get("retry_raw_first_response_content_included") is not False:
        raise AssertionError("Q1 raw first-response propagation detected")
    used = call.get("retry_used")
    accepted = call.get("accepted_attempt_index")
    invocations = call.get("agent_invocation_count")
    if used not in {True, False} or accepted not in {1, 2}:
        raise AssertionError("Q1 retry observability invalid")
    if invocations != (2 if used else 1):
        raise AssertionError("Q1 invocation count inconsistent with retry flag")
    if accepted == 1:
        if used or call.get("first_attempt_parse_valid") is not True:
            raise AssertionError("Q1 accepted first attempt invalid")
    if accepted == 2:
        if not used or call.get("second_attempt_parse_valid") is not True:
            raise AssertionError("Q1 accepted retry invalid")
    if call.get("first_attempt_parse_valid") is True and used:
        raise AssertionError("Q1 exact-valid first attempt was retried")
    if used and call.get("retry_eligible_after_first") is not True:
        raise AssertionError("Q1 retry used without eligibility")
    physical = call.get("physical_attempts")
    attempts = call.get("attempt_log")
    if (
        type(physical) is not int
        or not 1 <= physical <= MAX_PHYSICAL_SENDS_PER_LOGICAL_CALL
        or not isinstance(attempts, list)
        or len(attempts) != physical
    ):
        raise AssertionError("Q1 per-logical physical-send accounting invalid")


def _validate_pair_records(records: list[dict[str, Any]]) -> None:
    for record in records:
        if record.get("status") != "complete":
            terminal = record.get("terminal_failure")
            if terminal is not None:
                forbidden = {
                    "raw_response_text",
                    "raw_first_response_text",
                    "raw_second_response_text",
                    "raw_provider_body",
                    "prompt_text",
                    "retry_prompt_text",
                    "final_response",
                }
                stack: list[Any] = [terminal]
                while stack:
                    value = stack.pop()
                    if isinstance(value, dict):
                        if forbidden & set(value):
                            raise AssertionError("Q1 raw content leaked into terminal failure")
                        stack.extend(value.values())
                    elif isinstance(value, list):
                        stack.extend(value)
            continue
        arms = record.get("arms")
        if not isinstance(arms, dict):
            raise AssertionError("Q1 complete pair arms missing")
        for payload in arms.values():
            if not isinstance(payload, dict) or payload.get("status") == "failed_diagnostic":
                continue
            calls = payload.get("calls")
            if not isinstance(calls, list):
                raise AssertionError("Q1 complete arm calls missing")
            for call in calls:
                if not isinstance(call, dict):
                    raise AssertionError("Q1 scientific call record invalid")
                _validate_complete_call(call)


def aggregate(root: Path, *, stage: str, shard_map_path: Path) -> dict[str, Any]:
    shard_map = json.loads(shard_map_path.read_text())
    if shard_map != materializer.build_shard_map(stage):
        raise AssertionError("D2-vNext-Q1 shard-map drift")
    all_records: list[dict[str, Any]] = []
    shard_inputs: list[dict[str, Any]] = []
    physical_total = 0
    authorized_candidate_sha: str | None = None
    transport_defects: list[dict[str, Any]] = []
    for expected in shard_map["shards"]:
        shard_id = int(expected["shard"])
        path = _find_shard(root, stage, shard_id)
        expected_indices = [int(value) for value in expected["pair_indices"]]
        if path is None:
            all_records.extend(
                _synthetic_failure(stage, pair_index, "missing_provider_shard", shard_id)
                for pair_index in expected_indices
            )
            shard_inputs.append({"shard_id": shard_id, "status": "missing", "sha256": None})
            transport_defects.append({"shard_id": shard_id, "defect": "missing_provider_shard"})
            continue
        try:
            payload = json.loads(path.read_text())
            if payload.get("schema") != "d2-vnext-q1-acquisition-provider-shard-v0.1":
                raise AssertionError("Q1 provider-shard schema mismatch")
            if payload.get("study_stream") != "D2-vNext-Q1" or payload.get("stage") != stage:
                raise AssertionError("Q1 provider-shard stream/stage mismatch")
            if payload.get("fresh_namespace") != core.NAMESPACE:
                raise AssertionError("Q1 provider-shard namespace mismatch")
            if payload.get("status") != "provider_shard_complete_unclassified" or payload.get("classification") is not None:
                raise AssertionError("Q1 provider-shard status/classification mismatch")
            if int(payload["shard_id"]) != shard_id:
                raise AssertionError("Q1 provider-shard id mismatch")
            if [int(value) for value in payload.get("pair_indices", [])] != expected_indices:
                raise AssertionError("Q1 provider-shard pair-index map mismatch")
            if payload.get("schema_counts") != expected["schema_counts"]:
                raise AssertionError("Q1 provider-shard schema balance mismatch")
            if payload.get("requested_model") != EXPECTED_MODEL:
                raise AssertionError("Q1 provider-shard requested-model mismatch")
            if payload.get("effective_model_identity_observed") is not False:
                raise AssertionError("unexpected Q1 effective-model identity claim")
            if payload.get("response_format") != {"type": "json_object"}:
                raise AssertionError("Q1 JSON-mode contract mismatch")
            candidate = payload.get("authorized_candidate_sha")
            if not isinstance(candidate, str) or len(candidate) != 40:
                raise AssertionError("Q1 authorized candidate SHA missing")
            if authorized_candidate_sha is None:
                authorized_candidate_sha = candidate
            elif candidate != authorized_candidate_sha:
                raise AssertionError("Q1 cross-shard candidate mismatch")
            cohort = payload.get("cohort_lock", {})
            if cohort.get("cohort_pairs_sha256") != materializer.EXPECTED_COHORT_SHA256[stage]:
                raise AssertionError("Q1 provider-shard cohort mismatch")
            accounting = payload.get("transport_accounting")
            if not isinstance(accounting, dict):
                raise AssertionError("Q1 provider-shard transport accounting missing")
            sends = accounting.get("physical_provider_sends_observed")
            if type(sends) is not int or not 0 <= sends <= MAX_PHYSICAL_SENDS_PER_SHARD:
                raise AssertionError("Q1 shard send count invalid")
            if accounting.get("maximum_physical_provider_sends_per_logical_call") != MAX_PHYSICAL_SENDS_PER_LOGICAL_CALL:
                raise AssertionError("Q1 per-logical send ceiling drift")
            if accounting.get("maximum_physical_provider_sends_per_shard") != MAX_PHYSICAL_SENDS_PER_SHARD:
                raise AssertionError("Q1 per-shard send ceiling drift")
            for key in (
                "provider_sends_blocked_by_budget",
                "unexpected_outbound_http_requests_blocked",
                "logical_attribution_mismatch_blocks",
                "provider_workers_alive_after_drain",
            ):
                if accounting.get(key) != 0:
                    raise AssertionError(f"Q1 transport integrity failure: {key}")
            if accounting.get("transport_hooks_restored_after_drain") is not True:
                raise AssertionError("Q1 transport hooks were not restored")
            records = payload.get("pair_records")
            if not isinstance(records, list) or [int(row["pair_index"]) for row in records] != expected_indices:
                raise AssertionError("Q1 provider-shard record coverage mismatch")
            _validate_pair_records(records)
            physical_total += sends
            all_records.extend(records)
            shard_inputs.append(
                {
                    "shard_id": shard_id,
                    "status": "loaded",
                    "sha256": file_sha256(path),
                    "physical_provider_sends_observed": sends,
                }
            )
        except Exception as exc:
            fingerprint = hashlib.sha256(
                f"{type(exc).__name__}:{str(exc)[:500]}".encode()
            ).hexdigest()
            all_records.extend(
                _synthetic_failure(stage, pair_index, "invalid_provider_shard", shard_id)
                for pair_index in expected_indices
            )
            shard_inputs.append(
                {
                    "shard_id": shard_id,
                    "status": "invalid",
                    "sha256": file_sha256(path),
                    "error_sha256": fingerprint,
                }
            )
            transport_defects.append({"shard_id": shard_id, "defect": "invalid_provider_shard", "error_sha256": fingerprint})
    all_records.sort(key=lambda row: int(row["pair_index"]))
    if [int(row["pair_index"]) for row in all_records] != list(range(core.pair_count(stage))):
        raise AssertionError("canonical Q1 provider coverage mismatch")
    if physical_total > CAMPAIGN_CAP[stage]:
        raise AssertionError("Q1 campaign physical-send topology ceiling exceeded")
    complete = [row for row in all_records if row.get("status") == "complete"]
    failed = [row for row in all_records if row.get("status") != "complete"]
    return {
        "schema": "d2-vnext-q1-acquisition-provider-output-v0.1",
        "study_stream": "D2-vNext-Q1",
        "stage": stage,
        "fresh_namespace": core.NAMESPACE,
        "status": "provider_campaign_complete_unclassified",
        "classification": None,
        "authorized_candidate_sha": authorized_candidate_sha,
        "attempted_pairs": core.pair_count(stage),
        "complete_pairs": len(complete),
        "failed_pairs": len(failed),
        "requested_model": EXPECTED_MODEL,
        "effective_model_identity_observed": False,
        "effective_model": None,
        "temperature": EXPECTED_TEMPERATURE,
        "thinking": "disabled",
        "response_format": {"type": "json_object"},
        "cohort_pairs_sha256": materializer.EXPECTED_COHORT_SHA256[stage],
        "physical_provider_sends_observed_total": physical_total,
        "maximum_physical_provider_sends_per_logical_call": MAX_PHYSICAL_SENDS_PER_LOGICAL_CALL,
        "maximum_physical_provider_sends_per_shard": MAX_PHYSICAL_SENDS_PER_SHARD,
        "maximum_physical_provider_sends_campaign": CAMPAIGN_CAP[stage],
        "transport_integrity": {"passed": not transport_defects, "defects": transport_defects},
        "pair_records": all_records,
        "shard_inputs": shard_inputs,
        "shard_map_sha256": file_sha256(shard_map_path),
        "scientific_effect_gates_authorized": False,
        "registry_promotion_authorized": False,
        "acceptance_action_authorized": False,
        "production_historical_substrate_enabled": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("provider_shards")
    parser.add_argument("--stage", choices=core.STAGES, required=True)
    parser.add_argument("--shard-map")
    parser.add_argument("--output-dir", default="output/d2-vnext-q1-canonical-provider")
    args = parser.parse_args()
    stage = args.stage
    default_map = (
        "research/d2_vnext_q1/D2_VNEXT_Q1_A_SHARD_MAP.json"
        if stage == core.STAGE_A
        else "research/d2_vnext_q1/D2_VNEXT_Q1_B_SHARD_MAP.json"
    )
    shard_map_path = Path(args.shard_map or default_map)
    output = aggregate(Path(args.provider_shards), stage=stage, shard_map_path=shard_map_path)
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    slug = stage.lower().replace("-", "")
    output_path = out / f"d2-vnext-{slug}-provider-output.json"
    output_path.write_bytes(canonical_bytes(output))
    manifest = {
        "schema": "d2-vnext-q1-acquisition-provider-output-manifest-v0.1",
        "study_stream": "D2-vNext-Q1",
        "stage": stage,
        "provider_output_sha256": file_sha256(output_path),
        "attempted_pairs": output["attempted_pairs"],
        "complete_pairs": output["complete_pairs"],
        "failed_pairs": output["failed_pairs"],
        "cohort_pairs_sha256": materializer.EXPECTED_COHORT_SHA256[stage],
        "physical_provider_sends_observed_total": output["physical_provider_sends_observed_total"],
        "transport_integrity_pass": output["transport_integrity"]["passed"],
        "classification": None,
        "scientific_effect_gates_authorized": False,
        "registry_promotion_authorized": False,
        "production_historical_substrate_enabled": False,
    }
    (out / "provider-output-manifest.json").write_bytes(canonical_bytes(manifest))
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
