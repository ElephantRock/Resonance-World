#!/usr/bin/env python3
# ruff: noqa: E501
"""Fail-closed evaluator for Q3-D2 request-scoped structural localization."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

import evaluate_d2_vnext_q3d_diagnostic as q3e
import materialize_d2_vnext_q3d2_diagnostic as materializer


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _q3d_compatible_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Map Q3-D2 labels onto the already-locked Q3-D structural validator."""
    result = copy.deepcopy(payload)
    converted_pairs = []
    for pair in result.get("pair_records", []):
        if not isinstance(pair, dict):
            converted_pairs.append(pair)
            continue
        if pair.get("failure_class") == "q3d2_pair_runtime_or_instrumentation_failure":
            pair["failure_class"] = "q3d_pair_runtime_or_instrumentation_failure"
        rows = pair.pop("q3d2_observability_records", None)
        if isinstance(rows, list):
            converted = []
            for row in rows:
                if not isinstance(row, dict):
                    converted.append(row)
                    continue
                row["schema"] = "d2-vnext-q3d-structural-observability-record-v0.2"
                row["study_stream"] = "D2-vNext-Q3-D"
                row["stage"] = "Q3-D"
                converted.append(row)
            pair["q3d_observability_records"] = converted
        converted_pairs.append(pair)
    result["pair_records"] = converted_pairs
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("provider_output")
    parser.add_argument("--output-dir", default="output/d2-vnext-q3d2-evaluation")
    args = parser.parse_args()
    source = Path(args.provider_output)
    payload = json.loads(source.read_text())
    integrity = list(payload.get("integrity_defects", []))
    if int(payload.get("attempted_pairs", -1)) != 8:
        integrity.append("attempted_pair_count_mismatch")
    if int(payload.get("physical_provider_sends_observed", 0)) > materializer.MAX_PHYSICAL_SENDS_CAMPAIGN:
        integrity.append("campaign_send_cap_exceeded")

    compatible = _q3d_compatible_payload(payload)
    records, extraction_defects = q3e.observation_records(compatible)
    observability_defects = list(extraction_defects)
    for index, record in enumerate(records):
        observability_defects.extend(q3e.validate_record(record, index))
        if (
            record.get("retry_trigger_class") == q3e.CLEAN_EMPTY_TRIGGER
            and not q3e.frozen_clean_empty_target(record)
        ):
            observability_defects.append(
                f"record_{index}_frozen_clean_empty_trigger_predicate_mismatch"
            )

    targets = [record for record in records if q3e.frozen_clean_empty_target(record)]
    boundary_counts = Counter(str(record.get("boundary_classification")) for record in records)
    target_boundary_counts = Counter(
        str(record["agent_invocations"][0].get("boundary_classification"))
        for record in targets
    )

    if integrity:
        classification = "Q3-D2-INTEGRITY-FAIL"
        label = "integrity_failure"
    elif observability_defects or not records:
        classification = "Q3-D2-OBSERVABILITY-FAIL"
        label = "observability_failure"
    elif not targets:
        classification = "Q3-D2-NO-TARGET-EVENT"
        label = "no_clean_terminal_empty_target_event_observed"
    elif any(
        record["agent_invocations"][0].get("boundary_classification")
        == "unclassified_observability_defect"
        for record in targets
    ):
        classification = "Q3-D2-OBSERVABILITY-FAIL"
        label = "target_event_unclassified"
    else:
        classification = "Q3-D2-BOUNDARY-LOCALIZED"
        label = "request_scoped_terminal_empty_structural_boundary_localized"

    result = {
        "schema": "d2-vnext-q3d2-diagnostic-evaluation-v0.1",
        "study_stream": "D2-vNext-Q3-D2",
        "stage": "Q3-D2",
        "classification": classification,
        "classification_label": label,
        "provider_output_sha256": file_sha256(source),
        "attempted_pairs": payload.get("attempted_pairs"),
        "complete_pairs": payload.get("complete_pairs"),
        "failed_pairs": payload.get("failed_pairs"),
        "physical_provider_sends_observed": payload.get("physical_provider_sends_observed"),
        "maximum_physical_provider_sends_campaign": materializer.MAX_PHYSICAL_SENDS_CAMPAIGN,
        "observed_logical_call_records": len(records),
        "clean_terminal_empty_target_events": len(targets),
        "boundary_counts": dict(sorted(boundary_counts.items())),
        "target_event_boundary_counts": dict(sorted(target_boundary_counts.items())),
        "integrity_defects": sorted(set(integrity)),
        "observability_defects": sorted(set(observability_defects)),
        "causal_ceiling": (
            "Structural localization identifies the first observed content boundary only; "
            "it does not establish provider, model, Hermes, or adapter root cause."
        ),
        "diagnostic_only": True,
        "scientific_effect_gates_computed": False,
        "acceptance_action_authorized": False,
        "registry_promotion_authorized": False,
        "production_historical_substrate_enabled": False,
    }
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / "d2-vnext-q3d2-diagnostic-evaluation.json"
    path.write_bytes(canonical_bytes(result))
    manifest = {
        "schema": "d2-vnext-q3d2-diagnostic-evaluation-manifest-v0.1",
        "evaluation_result_sha256": file_sha256(path),
        "classification": classification,
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
