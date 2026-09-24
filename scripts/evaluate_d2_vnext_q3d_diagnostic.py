#!/usr/bin/env python3
# ruff: noqa: E501
"""Fail-closed evaluator for Q3-D structural terminal-boundary localization."""
from __future__ import annotations
import argparse,hashlib,json
from collections import Counter
from pathlib import Path
from typing import Any,Iterator

ALLOWED_BOUNDARIES={"provider_content_absent","provider_content_present_hermes_terminal_absent","hermes_terminal_present_adapter_candidate_absent","adapter_candidate_nonempty_parse_invalid","accepted_exact_completion","runtime_or_transport_failure","unclassified_observability_defect"}
REQUIRED_ATTEMPT_FIELDS={"agent_invocation_index","api_calls","loop_termination_reason","provider_semantic_completions","terminal_adapter","boundary_classification","exact_attributed_clean_transport","logical_attribution_integrity","adapter_reason","exact_structured_parse_valid","parse_diagnostic"}

def canonical_bytes(v:Any)->bytes:return (json.dumps(v,sort_keys=True,separators=(",",":"))+"\n").encode()
def file_sha256(p:Path)->str:return hashlib.sha256(p.read_bytes()).hexdigest()

def walk(value:Any)->Iterator[dict[str,Any]]:
    if isinstance(value,dict):
        yield value
        for nested in value.values():yield from walk(nested)
    elif isinstance(value,list):
        for nested in value:yield from walk(nested)

def attempt_records(payload:dict[str,Any])->list[dict[str,Any]]:
    found=[];seen=set()
    for node in walk(payload.get("pair_records",[])):
        if "q3d_observability" in node and isinstance(node["q3d_observability"],dict):
            obs=node["q3d_observability"]
            for key in ("first_attempt","second_attempt"):
                attempt=obs.get(key)
                if isinstance(attempt,dict):
                    token=id(attempt)
                    if token not in seen:seen.add(token);found.append(attempt)
        if "first_attempt" in node and "retry_trigger_class" in node and "terminal_error_sha256" in node:
            for key in ("first_attempt","second_attempt"):
                attempt=node.get(key)
                if isinstance(attempt,dict):
                    token=id(attempt)
                    if token not in seen:seen.add(token);found.append(attempt)
    return found

def main()->None:
    ap=argparse.ArgumentParser();ap.add_argument("provider_output");ap.add_argument("--output-dir",default="output/d2-vnext-q3d-evaluation");a=ap.parse_args();src=Path(a.provider_output);payload=json.loads(src.read_text())
    integrity=list(payload.get("integrity_defects",[]))
    if int(payload.get("attempted_pairs",-1))!=16:integrity.append("attempted_pair_count_mismatch")
    if int(payload.get("physical_provider_sends_observed",0))>4608:integrity.append("campaign_send_cap_exceeded")
    attempts=attempt_records(payload);obs_defects=[];target=[];boundary_counts=Counter()
    for i,attempt in enumerate(attempts):
        missing=sorted(REQUIRED_ATTEMPT_FIELDS-set(attempt))
        if missing:obs_defects.append(f"attempt_{i}_missing:{','.join(missing)}");continue
        boundary=str(attempt.get("boundary_classification"))
        if boundary not in ALLOWED_BOUNDARIES:obs_defects.append(f"attempt_{i}_invalid_boundary")
        if not isinstance(attempt.get("provider_semantic_completions"),list):obs_defects.append(f"attempt_{i}_provider_semantic_not_list")
        if not isinstance(attempt.get("terminal_adapter"),dict):obs_defects.append(f"attempt_{i}_terminal_adapter_not_object")
        boundary_counts[boundary]+=1
        clean_empty=bool(not attempt.get("runtime_exception") and attempt.get("adapter_reason")=="final_response_empty" and int(attempt.get("final_response_length",-1))==0 and attempt.get("exact_attributed_clean_transport") is True and attempt.get("logical_attribution_integrity") is True)
        if clean_empty:target.append(attempt)
    target_boundaries=Counter(str(x.get("boundary_classification")) for x in target)
    if integrity:classification="Q3-D-INTEGRITY-FAIL";label="integrity_failure"
    elif obs_defects or not attempts:classification="Q3-D-OBSERVABILITY-FAIL";label="observability_failure"
    elif not target:classification="Q3-D-NO-TARGET-EVENT";label="no_clean_terminal_empty_target_event_observed"
    elif any(str(x.get("boundary_classification"))=="unclassified_observability_defect" for x in target):classification="Q3-D-OBSERVABILITY-FAIL";label="target_event_unclassified"
    else:classification="Q3-D-BOUNDARY-LOCALIZED";label="terminal_empty_structural_boundary_localized"
    result={"schema":"d2-vnext-q3d-diagnostic-evaluation-v0.1","study_stream":"D2-vNext-Q3-D","stage":"Q3-D","classification":classification,"classification_label":label,"provider_output_sha256":file_sha256(src),"attempted_pairs":payload.get("attempted_pairs"),"complete_pairs":payload.get("complete_pairs"),"failed_pairs":payload.get("failed_pairs"),"physical_provider_sends_observed":payload.get("physical_provider_sends_observed"),"maximum_physical_provider_sends_campaign":4608,"observed_attempt_records":len(attempts),"clean_terminal_empty_target_events":len(target),"boundary_counts":dict(sorted(boundary_counts.items())),"target_event_boundary_counts":dict(sorted(target_boundaries.items())),"integrity_defects":sorted(set(integrity)),"observability_defects":sorted(set(obs_defects)),"causal_ceiling":"Structural localization identifies the first observed content boundary only; it does not establish provider, model, Hermes, or adapter root cause.","provider_execution_authorized":False,"scientific_effect_gates_computed":False,"acceptance_action_authorized":False,"registry_promotion_authorized":False,"production_historical_substrate_enabled":False}
    out=Path(a.output_dir);out.mkdir(parents=True,exist_ok=True);path=out/"d2-vnext-q3d-diagnostic-evaluation.json";path.write_bytes(canonical_bytes(result));manifest={"schema":"d2-vnext-q3d-diagnostic-evaluation-manifest-v0.1","classification":classification,"classification_label":label,"result_sha256":file_sha256(path),"provider_output_sha256":result["provider_output_sha256"],"scientific_effect_gates_computed":False,"provider_execution_authorized":False,"acceptance_action_authorized":False,"registry_promotion_authorized":False,"production_historical_substrate_enabled":False};(out/"manifest.json").write_bytes(canonical_bytes(manifest));print(json.dumps(manifest,indent=2,sort_keys=True))

if __name__=="__main__":main()
