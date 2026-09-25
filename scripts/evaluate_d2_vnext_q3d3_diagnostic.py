#!/usr/bin/env python3
# ruff: noqa: E501
"""Fail-closed evaluator for Q3-D3 HTTP-body -> SDK structural localization."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

import d2_vnext_q3d3_http_observer as http_observer
import evaluate_d2_vnext_q3d_diagnostic as q3e
import materialize_d2_vnext_q3d3_diagnostic as materializer

ALLOWED_Q3D3_BOUNDARIES = {
    "http_body_content_absent",
    "http_body_content_present_sdk_content_absent",
    "q3d2_semantic_present_hermes_terminal_absent",
    "hermes_terminal_present_adapter_candidate_absent",
    "adapter_candidate_nonempty_parse_invalid",
    "accepted_exact_completion",
    "runtime_or_transport_failure",
    "unclassified_observability_defect",
}


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _records(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for pair in payload.get("pair_records", []):
        if not isinstance(pair, dict):
            continue
        observations = pair.get("q3d3_observability_records", [])
        if isinstance(observations, list):
            rows.extend(row for row in observations if isinstance(row, dict))
    return rows


def _q3d_compatible_record(record: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(record)
    result["schema"] = "d2-vnext-q3d-structural-observability-record-v0.2"
    result["study_stream"] = "D2-vNext-Q3-D"
    result["stage"] = "Q3-D"
    result.pop("http_body_records", None)
    result.pop("q3d3_boundary_classification", None)
    for invocation in result.get("agent_invocations", []):
        if isinstance(invocation, dict):
            invocation.pop("http_body_records", None)
            invocation.pop("q3d3_boundary_classification", None)
    return result


def _q3d3_record_defects(record: dict[str, Any], index: int) -> list[str]:
    defects: list[str] = []
    try:
        http_observer.assert_no_raw_content(record)
    except AssertionError:
        defects.append(f"record_{index}_raw_content_leak")
    embedded = record.get("observability_defects")
    if not isinstance(embedded, list):
        defects.append(f"record_{index}_observability_defects_not_list")
    elif embedded:
        defects.extend(f"record_{index}_embedded:{item}" for item in embedded)
    http_rows = record.get("http_body_records")
    if not isinstance(http_rows, list):
        defects.append(f"record_{index}_http_body_records_not_list")
        http_rows = []
    logical_index = record.get("logical_call_index")
    if any(row.get("logical_index") != logical_index for row in http_rows if isinstance(row, dict)):
        defects.append(f"record_{index}_http_logical_index_mismatch")
    send_indices = [
        int(row["logical_send_index"])
        for row in http_rows
        if isinstance(row, dict) and row.get("logical_send_index") is not None
    ]
    if len(send_indices) != len(set(send_indices)):
        defects.append(f"record_{index}_duplicate_http_send_index")
    for invocation in record.get("agent_invocations", []):
        if not isinstance(invocation, dict):
            defects.append(f"record_{index}_invocation_not_object")
            continue
        boundary = invocation.get("q3d3_boundary_classification")
        if boundary not in ALLOWED_Q3D3_BOUNDARIES:
            defects.append(f"record_{index}_invalid_q3d3_boundary:{boundary}")
        inv_http = invocation.get("http_body_records")
        if not isinstance(inv_http, list):
            defects.append(f"record_{index}_invocation_http_rows_not_list")
            continue
        semantic = invocation.get("semantic_completions")
        if not isinstance(semantic, list):
            defects.append(f"record_{index}_semantic_rows_not_list")
            continue
        defects.extend(
            f"record_{index}_{item}"
            for item in http_observer.semantic_http_association_defects(semantic, inv_http)
        )
    record_boundary = record.get("q3d3_boundary_classification")
    if record_boundary not in ALLOWED_Q3D3_BOUNDARIES:
        defects.append(f"record_{index}_invalid_record_q3d3_boundary:{record_boundary}")
    return defects


def evaluate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    integrity = list(payload.get("integrity_defects", []))
    if int(payload.get("attempted_pairs", -1)) != 8:
        integrity.append("attempted_pair_count_mismatch")
    if int(payload.get("physical_provider_sends_observed", 0)) > materializer.MAX_PHYSICAL_SENDS_CAMPAIGN:
        integrity.append("campaign_send_cap_exceeded")
    if payload.get("cohort_pairs_sha256") != materializer.EXPECTED_COHORT_SHA256:
        integrity.append("cohort_commitment_mismatch")

    records = _records(payload)
    observability_defects: list[str] = []
    compatible_records: list[dict[str, Any]] = []
    for index, record in enumerate(records):
        compatible = _q3d_compatible_record(record)
        compatible_records.append(compatible)
        observability_defects.extend(q3e.validate_record(compatible, index))
        observability_defects.extend(_q3d3_record_defects(record, index))
        if (
            compatible.get("retry_trigger_class") == q3e.CLEAN_EMPTY_TRIGGER
            and not q3e.frozen_clean_empty_target(compatible)
        ):
            observability_defects.append(
                f"record_{index}_frozen_clean_empty_trigger_predicate_mismatch"
            )

    targets = [
        (raw, compatible)
        for raw, compatible in zip(records, compatible_records, strict=True)
        if q3e.frozen_clean_empty_target(compatible)
    ]
    boundary_counts = Counter(str(record.get("q3d3_boundary_classification")) for record in records)
    target_boundary_counts = Counter(
        str(raw["agent_invocations"][0].get("q3d3_boundary_classification"))
        for raw, _ in targets
    )

    if integrity:
        classification = "Q3-D3-INTEGRITY-FAIL"
        label = "integrity_failure"
    elif observability_defects or not records:
        classification = "Q3-D3-OBSERVABILITY-FAIL"
        label = "observability_failure"
    elif not targets:
        classification = "Q3-D3-NO-TARGET-EVENT"
        label = "no_clean_terminal_empty_target_event_observed"
    elif any(
        raw["agent_invocations"][0].get("q3d3_boundary_classification")
        == "unclassified_observability_defect"
        for raw, _ in targets
    ):
        classification = "Q3-D3-OBSERVABILITY-FAIL"
        label = "target_event_unclassified"
    else:
        classification = "Q3-D3-BOUNDARY-LOCALIZED"
        label = "http_body_to_sdk_terminal_empty_structural_boundary_localized"

    return {
        "schema": "d2-vnext-q3d3-diagnostic-evaluation-v0.1",
        "study_stream": "D2-vNext-Q3-D3",
        "stage": "Q3-D3",
        "classification": classification,
        "classification_label": label,
        "attempted_pairs": payload.get("attempted_pairs"),
        "complete_pairs": payload.get("complete_pairs"),
        "failed_pairs": payload.get("failed_pairs"),
        "physical_provider_sends_observed": payload.get("physical_provider_sends_observed"),
        "maximum_physical_provider_sends_campaign": materializer.MAX_PHYSICAL_SENDS_CAMPAIGN,
        "observed_logical_call_records": len(records),
        "clean_terminal_empty_target_events": len(targets),
        "boundary_counts": dict(sorted(boundary_counts.items())),
        "target_event_boundary_counts": dict(sorted(target_boundary_counts.items())),
        "integrity_defects": sorted(set(str(item) for item in integrity)),
        "observability_defects": sorted(set(observability_defects)),
        "causal_ceiling": (
            "Q3-D3 identifies the first observed structural content boundary between the "
            "post-HTTPX-read response body, the SDK object structural view, Hermes terminalization, "
            "and the unchanged adapter. It does not establish model/provider root cause or raw-wire "
            "semantics before HTTPX response-body processing."
        ),
        "diagnostic_only": True,
        "scientific_effect_gates_computed": False,
        "acceptance_action_authorized": False,
        "registry_promotion_authorized": False,
        "production_historical_substrate_enabled": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("provider_output")
    parser.add_argument("--output-dir", default="output/d2-vnext-q3d3-evaluation")
    args = parser.parse_args()
    source = Path(args.provider_output)
    payload = json.loads(source.read_text())
    result = evaluate_payload(payload)
    result["provider_output_sha256"] = file_sha256(source)
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / "d2-vnext-q3d3-diagnostic-evaluation.json"
    path.write_bytes(canonical_bytes(result))
    manifest = {
        "schema": "d2-vnext-q3d3-diagnostic-evaluation-manifest-v0.1",
        "evaluation_result_sha256": file_sha256(path),
        "classification": result["classification"],
        "provider_output_sha256": result["provider_output_sha256"],
        "scientific_effect_gates_computed": False,
        "acceptance_action_authorized": False,
        "registry_promotion_authorized": False,
        "production_historical_substrate_enabled": False,
    }
    (out / "manifest.json").write_bytes(canonical_bytes(manifest))
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
