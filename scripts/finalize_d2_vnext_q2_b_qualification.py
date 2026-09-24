#!/usr/bin/env python3
# ruff: noqa: E501
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
from typing import Any
def canonical_bytes(v:Any)->bytes:return (json.dumps(v,sort_keys=True,separators=(",",":"))+"\n").encode()
def file_sha256(p:Path)->str:return hashlib.sha256(p.read_bytes()).hexdigest()
def finalize(result,review):
    if result.get("schema")!="d2-vnext-q2-acquisition-qualification-result-v0.1" or result.get("stage")!="Q2-B" or result.get("classification")!="D2-vNext-Q2-B2":raise ValueError("Q2-B finalization requires B2")
    required={"schema","study_stream","provider_output_sha256","q2_b_evaluation_result_sha256","reviewer","review_timestamp_utc","reviewed_completion_by_schema","reviewed_completion_by_shard","reviewed_completion_by_execution_wave","reviewed_transport_and_runtime_metadata","scientific_effect_inputs_consulted","verdict","rationale"}
    if set(review)!=required or review.get("schema")!="d2-vnext-q2-b-exchangeability-review-v0.1":raise ValueError("Q2-B review schema mismatch")
    if review.get("provider_output_sha256")!=result.get("provider_output_sha256"):raise ValueError("Q2-B review provider hash mismatch")
    if review.get("scientific_effect_inputs_consulted") is not False:raise ValueError("scientific-effect inputs prohibited")
    for k in ("reviewed_completion_by_schema","reviewed_completion_by_shard","reviewed_completion_by_execution_wave","reviewed_transport_and_runtime_metadata"):
        if review.get(k) is not True:raise ValueError(f"Q2-B review dimension missing: {k}")
    verdict=review.get("verdict")
    if verdict not in {"PASS","INCONCLUSIVE_NONEXCHANGEABLE"}:raise ValueError("Q2-B verdict invalid")
    final={"schema":"d2-vnext-q2-b-final-qualification-v0.1","study_stream":"D2-vNext-Q2","stage":"Q2-B","provider_output_sha256":result["provider_output_sha256"],"evaluation_classification":result["classification"],"future_confirmatory_clearance_contract":result["future_confirmatory_clearance_contract"],"exchangeability_review":review,"scientific_effect_gates_computed":False,"registry_promotion_authorized":False,"acceptance_action_authorized":False,"future_confirmatory_provider_execution_authorized":False,"production_historical_substrate_enabled":False}
    final["classification"]="D2-vNext-Q2-B-PASS" if verdict=="PASS" else "D2-vNext-Q2-B-INCONCLUSIVE_NONEXCHANGEABLE";return final
def main():
    ap=argparse.ArgumentParser();ap.add_argument("evaluation_result");ap.add_argument("exchangeability_review");ap.add_argument("--output-dir",default="output/d2-vnext-q2-b-final");a=ap.parse_args();rp=Path(a.evaluation_result);vp=Path(a.exchangeability_review);result=json.loads(rp.read_text());review=json.loads(vp.read_text())
    if review.get("q2_b_evaluation_result_sha256")!=file_sha256(rp):raise ValueError("Q2-B evaluation hash mismatch")
    final=finalize(result,review);final["q2_b_evaluation_result_sha256"]=file_sha256(rp);final["exchangeability_review_sha256"]=file_sha256(vp);out=Path(a.output_dir);out.mkdir(parents=True,exist_ok=True);p=out/"D2_VNEXT_Q2_B_FINAL_QUALIFICATION.json";p.write_bytes(canonical_bytes(final));print(json.dumps({"classification":final["classification"],"result_sha256":file_sha256(p)},indent=2))
if __name__=="__main__":main()
