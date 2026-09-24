#!/usr/bin/env python3
# ruff: noqa: E501
"""Fail-closed evaluator for Q3-D structural terminal-boundary localization."""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

ALLOWED_BOUNDARIES = {
    "provider_content_absent",
    "provider_content_present_hermes_terminal_absent",
    "hermes_terminal_present_adapter_candidate_absent",
    "adapter_candidate_nonempty_parse_invalid",
    "accepted_exact_completion",
    "runtime_or_transport_failure",
    "unclassified_observability_defect",
}
CLEAN_EMPTY_TRIGGER = "clean_terminal_empty"
MAX_ITERATIONS = 2
FORBIDDEN_RAW_KEYS = {
    "raw_response_text",
    "raw_first_response_text",
    "raw_second_response_text",
    "raw_provider_body",
    "prompt_text",
    "retry_prompt_text",
    "final_response",
    "assistant_content",
    "response_body",
    "raw_content",
}
REQUIRED_RECORD_FIELDS = {
    "schema", "study_stream", "stage", "pair_public_id", "schema_id", "arm", "phase", "logical_call_index", "physical_provider_sends_observed", "agent_invocations", "retry_eligible_after_first", "retry_trigger_class", "retry_used", "accepted_attempt_index", "accepted_exact_completion", "boundary_classification", "observability_defects",
}
REQUIRED_INVOCATION_FIELDS = {
    "agent_invocation_index", "api_calls", "hermes_completed_flag_valid", "hermes_completed", "hermes_failed", "hermes_partial", "hermes_interrupted", "hermes_error_present", "loop_termination_reason", "terminal_iteration_override_used", "physical_provider_sends_observed", "exact_attributed_clean_transport", "logical_attribution_integrity", "json_mode_compatibility_failure", "semantic_completions", "hermes_terminal", "adapter_snapshot", "boundary_classification",
}
REQUIRED_SEMANTIC_FIELDS = {
    "agent_invocation_index", "semantic_response_index", "semantic_response_observed", "semantic_response_error_type", "effective_model_if_returned", "choice_count", "finish_reason_present", "finish_reason", "assistant_message_present", "assistant_content_present", "assistant_content_type", "assistant_content_length", "assistant_content_sha256", "tool_calls_present", "tool_calls_count", "usage_prompt_tokens", "usage_completion_tokens", "usage_total_tokens", "provider_sends",
}
REQUIRED_ADAPTER_FIELDS = {
    "candidate_source", "candidate_present", "candidate_type", "candidate_length", "candidate_sha256", "candidate_matches_hermes_terminal", "adapter_reason", "parse_diagnostic", "exact_structured_parse_valid", "accepted_exact_completion",
}
REQUIRED_SNAPSHOT_FIELDS = {"present", "type", "length", "sha256"}
REQUIRED_SEND_FIELDS = {"logical_send_index", "total_send_index", "http_status", "transport_error_type"}


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _raw_content_keys(value: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        found |= FORBIDDEN_RAW_KEYS & set(value)
        for nested in value.values():
            found |= _raw_content_keys(nested)
    elif isinstance(value, list):
        for nested in value:
            found |= _raw_content_keys(nested)
    return found


def observation_records(payload: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    records: list[dict[str, Any]] = []
    defects: list[str] = []
    seen: set[tuple[str, int]] = set()
    for pair_index, pair in enumerate(payload.get("pair_records", [])):
        if not isinstance(pair, dict):
            defects.append(f"pair_{pair_index}_not_object")
            continue
        if pair.get("failure_class") == "q3d_pair_runtime_or_instrumentation_failure":
            defects.append(f"pair_{pair_index}_runtime_or_instrumentation_failure")
        pair_public_id = pair.get("pair_public_id")
        schema_id = pair.get("schema_id")
        rows = pair.get("q3d_observability_records")
        if not isinstance(rows, list):
            defects.append(f"pair_{pair_index}_observability_records_missing")
            continue
        for row_index, row in enumerate(rows):
            if not isinstance(row, dict):
                defects.append(f"pair_{pair_index}_record_{row_index}_not_object")
                continue
            logical_index = row.get("logical_call_index")
            if not isinstance(logical_index, int):
                defects.append(f"pair_{pair_index}_record_{row_index}_logical_index_invalid")
                continue
            key = (str(pair_public_id), logical_index)
            if key in seen:
                defects.append(f"pair_{pair_index}_duplicate_logical_index_{logical_index}")
                continue
            seen.add(key)
            if row.get("pair_public_id") != pair_public_id:
                defects.append(f"pair_{pair_index}_record_{row_index}_pair_identity_mismatch")
            if row.get("schema_id") != schema_id:
                defects.append(f"pair_{pair_index}_record_{row_index}_schema_identity_mismatch")
            records.append(row)
    return records, defects


def validate_record(record: dict[str, Any], index: int) -> list[str]:
    defects: list[str] = []
    missing = sorted(REQUIRED_RECORD_FIELDS - set(record))
    if missing:
        return [f"record_{index}_missing:{','.join(missing)}"]
    if record.get("schema") != "d2-vnext-q3d-structural-observability-record-v0.2":
        defects.append(f"record_{index}_schema_mismatch")
    if record.get("study_stream") != "D2-vNext-Q3-D" or record.get("stage") != "Q3-D":
        defects.append(f"record_{index}_stream_or_stage_mismatch")
    if record.get("schema_id") != "pairwise_order":
        defects.append(f"record_{index}_schema_id_mismatch")
    raw_keys = _raw_content_keys(record)
    if raw_keys:
        defects.append(f"record_{index}_raw_content_keys:{','.join(sorted(raw_keys))}")
    if record.get("boundary_classification") not in ALLOWED_BOUNDARIES:
        defects.append(f"record_{index}_invalid_boundary")
    embedded_defects = record.get("observability_defects")
    if not isinstance(embedded_defects, list):
        defects.append(f"record_{index}_observability_defects_not_list")
    elif embedded_defects:
        defects.extend(f"record_{index}_embedded:{str(item)[:120]}" for item in embedded_defects)
    invocations = record.get("agent_invocations")
    if not isinstance(invocations, list) or not 1 <= len(invocations) <= 2:
        defects.append(f"record_{index}_invocations_invalid")
        return defects
    expected_indices = list(range(1, len(invocations) + 1))
    observed_indices = [inv.get("agent_invocation_index") if isinstance(inv, dict) else None for inv in invocations]
    if observed_indices != expected_indices:
        defects.append(f"record_{index}_invocation_indices_mismatch")
    send_total = 0
    for invocation_index, invocation in enumerate(invocations, start=1):
        prefix = f"record_{index}_invocation_{invocation_index}"
        if not isinstance(invocation, dict):
            defects.append(f"{prefix}_not_object")
            continue
        inv_missing = sorted(REQUIRED_INVOCATION_FIELDS - set(invocation))
        if inv_missing:
            defects.append(f"{prefix}_missing:{','.join(inv_missing)}")
            continue
        if invocation.get("boundary_classification") not in ALLOWED_BOUNDARIES:
            defects.append(f"{prefix}_invalid_boundary")
        semantic = invocation.get("semantic_completions")
        if not isinstance(semantic, list):
            defects.append(f"{prefix}_semantic_not_list")
            semantic = []
        api_calls = int(invocation.get("api_calls", -1))
        if len(semantic) != api_calls:
            defects.append(f"{prefix}_semantic_count_{len(semantic)}_api_calls_{api_calls}")
        semantic_send_total = 0
        for semantic_index, event in enumerate(semantic, start=1):
            eprefix = f"{prefix}_semantic_{semantic_index}"
            if not isinstance(event, dict):
                defects.append(f"{eprefix}_not_object")
                continue
            event_missing = sorted(REQUIRED_SEMANTIC_FIELDS - set(event))
            if event_missing:
                defects.append(f"{eprefix}_missing:{','.join(event_missing)}")
                continue
            if event.get("agent_invocation_index") != invocation_index:
                defects.append(f"{eprefix}_invocation_mismatch")
            if event.get("semantic_response_index") != semantic_index:
                defects.append(f"{eprefix}_index_mismatch")
            sends = event.get("provider_sends")
            if not isinstance(sends, list):
                defects.append(f"{eprefix}_provider_sends_not_list")
                sends = []
            semantic_send_total += len(sends)
            for send_index, send in enumerate(sends, start=1):
                if not isinstance(send, dict):
                    defects.append(f"{eprefix}_send_{send_index}_not_object")
                    continue
                send_missing = sorted(REQUIRED_SEND_FIELDS - set(send))
                if send_missing:
                    defects.append(f"{eprefix}_send_{send_index}_missing:{','.join(send_missing)}")
        if semantic_send_total != int(invocation.get("physical_provider_sends_observed", -1)):
            defects.append(f"{prefix}_transport_association_mismatch")
        send_total += max(0, int(invocation.get("physical_provider_sends_observed", 0)))
        hermes_terminal = invocation.get("hermes_terminal")
        if not isinstance(hermes_terminal, dict):
            defects.append(f"{prefix}_hermes_terminal_not_object")
        elif REQUIRED_SNAPSHOT_FIELDS - set(hermes_terminal):
            defects.append(f"{prefix}_hermes_terminal_incomplete")
        adapter = invocation.get("adapter_snapshot")
        if not isinstance(adapter, dict):
            defects.append(f"{prefix}_adapter_not_object")
        else:
            adapter_missing = sorted(REQUIRED_ADAPTER_FIELDS - set(adapter))
            if adapter_missing:
                defects.append(f"{prefix}_adapter_missing:{','.join(adapter_missing)}")
            if isinstance(hermes_terminal, dict) and hermes_terminal.get("type") == "string" and adapter.get("candidate_matches_hermes_terminal") is not True:
                defects.append(f"{prefix}_adapter_identity_mismatch")
    if send_total != int(record.get("physical_provider_sends_observed", -1)):
        defects.append(f"record_{index}_physical_send_sum_mismatch")
    retry_used = bool(record.get("retry_used"))
    if retry_used != (len(invocations) == 2):
        defects.append(f"record_{index}_retry_invocation_count_mismatch")
    if record.get("retry_eligible_after_first") != (record.get("retry_trigger_class") is not None):
        defects.append(f"record_{index}_retry_eligibility_mismatch")
    if retry_used and record.get("retry_trigger_class") is None:
        defects.append(f"record_{index}_retry_without_trigger")
    accepted_index = record.get("accepted_attempt_index")
    if bool(record.get("accepted_exact_completion")) != (accepted_index in (1, 2)):
        defects.append(f"record_{index}_accepted_index_mismatch")
    return defects


def frozen_clean_empty_target(record: dict[str, Any]) -> bool:
    if record.get("retry_trigger_class") != CLEAN_EMPTY_TRIGGER:
        return False
    invocations = record.get("agent_invocations")
    if not isinstance(invocations, list) or not invocations:
        return False
    first = invocations[0]
    if not isinstance(first, dict):
        return False
    adapter = first.get("adapter_snapshot")
    if not isinstance(adapter, dict):
        return False
    return bool(
        record.get("retry_eligible_after_first") is True
        and record.get("retry_used") is True
        and first.get("api_calls") == MAX_ITERATIONS
        and first.get("hermes_completed_flag_valid") is True
        and first.get("hermes_completed") is False
        and first.get("hermes_failed") is False
        and first.get("hermes_partial") is False
        and first.get("hermes_interrupted") is False
        and first.get("hermes_error_present") is False
        and first.get("json_mode_compatibility_failure") is False
        and int(first.get("physical_provider_sends_observed", 0)) > 0
        and first.get("exact_attributed_clean_transport") is True
        and first.get("logical_attribution_integrity") is True
        and adapter.get("candidate_present") is False
        and int(adapter.get("candidate_length", -1)) == 0
        and adapter.get("adapter_reason") == "final_response_empty"
        and adapter.get("exact_structured_parse_valid") is False
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("provider_output")
    parser.add_argument("--output-dir", default="output/d2-vnext-q3d-evaluation")
    args = parser.parse_args()
    source = Path(args.provider_output)
    payload = json.loads(source.read_text())
    integrity = list(payload.get("integrity_defects", []))
    if int(payload.get("attempted_pairs", -1)) != 16:
        integrity.append("attempted_pair_count_mismatch")
    if int(payload.get("physical_provider_sends_observed", 0)) > 4608:
        integrity.append("campaign_send_cap_exceeded")
    records, extraction_defects = observation_records(payload)
    observability_defects = list(extraction_defects)
    for index, record in enumerate(records):
        observability_defects.extend(validate_record(record, index))
        if record.get("retry_trigger_class") == CLEAN_EMPTY_TRIGGER and not frozen_clean_empty_target(record):
            observability_defects.append(f"record_{index}_frozen_clean_empty_trigger_predicate_mismatch")
    targets = [record for record in records if frozen_clean_empty_target(record)]
    boundary_counts = Counter(str(record.get("boundary_classification")) for record in records)
    target_boundary_counts = Counter(str(record["agent_invocations"][0].get("boundary_classification")) for record in targets)
    if integrity:
        classification = "Q3-D-INTEGRITY-FAIL"; label = "integrity_failure"
    elif observability_defects or not records:
        classification = "Q3-D-OBSERVABILITY-FAIL"; label = "observability_failure"
    elif not targets:
        classification = "Q3-D-NO-TARGET-EVENT"; label = "no_clean_terminal_empty_target_event_observed"
    elif any(record["agent_invocations"][0].get("boundary_classification") == "unclassified_observability_defect" for record in targets):
        classification = "Q3-D-OBSERVABILITY-FAIL"; label = "target_event_unclassified"
    else:
        classification = "Q3-D-BOUNDARY-LOCALIZED"; label = "terminal_empty_structural_boundary_localized"
    result = {"schema": "d2-vnext-q3d-diagnostic-evaluation-v0.2", "study_stream": "D2-vNext-Q3-D", "stage": "Q3-D", "classification": classification, "classification_label": label, "provider_output_sha256": file_sha256(source), "attempted_pairs": payload.get("attempted_pairs"), "complete_pairs": payload.get("complete_pairs"), "failed_pairs": payload.get("failed_pairs"), "physical_provider_sends_observed": payload.get("physical_provider_sends_observed"), "maximum_physical_provider_sends_campaign": 4608, "observed_logical_call_records": len(records), "clean_terminal_empty_target_events": len(targets), "boundary_counts": dict(sorted(boundary_counts.items())), "target_event_boundary_counts": dict(sorted(target_boundary_counts.items())), "integrity_defects": sorted(set(integrity)), "observability_defects": sorted(set(observability_defects)), "causal_ceiling": "Structural localization identifies the first observed content boundary only; it does not establish provider, model, Hermes, or adapter root cause.", "provider_execution_authorized": False, "scientific_effect_gates_computed": False, "acceptance_action_authorized": False, "registry_promotion_authorized": False, "production_historical_substrate_enabled": False}
    out = Path(args.output_dir); out.mkdir(parents=True, exist_ok=True); path = out / "d2-vnext-q3d-diagnostic-evaluation.json"; path.write_bytes(canonical_bytes(result))
    manifest = {"schema": "d2-vnext-q3d-diagnostic-evaluation-manifest-v0.2", "classification": classification, "classification_label": label, "result_sha256": file_sha256(path), "provider_output_sha256": result["provider_output_sha256"], "scientific_effect_gates_computed": False, "provider_execution_authorized": False, "acceptance_action_authorized": False, "registry_promotion_authorized": False, "production_historical_substrate_enabled": False}
    (out / "manifest.json").write_bytes(canonical_bytes(manifest)); print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
