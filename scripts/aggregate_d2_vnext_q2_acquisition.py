#!/usr/bin/env python3
# ruff: noqa: E501
"""Aggregate Q2 provider shards without scientific-effect classification."""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
from typing import Any
import d2_vnext_q2_acquisition_core as core
import materialize_d2_vnext_q2_acquisition as materializer
MAX_PHYSICAL_SENDS_PER_LOGICAL_CALL=36;MAX_PHYSICAL_SENDS_PER_SHARD=1152;CAMPAIGN_CAP={core.STAGE_A:4608,core.STAGE_B:27648};EXPECTED_MODEL="glm-5.3";EXPECTED_TEMPERATURE=0.8
def canonical_bytes(v:Any)->bytes:return (json.dumps(v,sort_keys=True,separators=(",",":"))+"\n").encode()
def file_sha256(p:Path)->str:return hashlib.sha256(p.read_bytes()).hexdigest()
def _find_shard(root:Path,stage:str,shard_id:int):
    slug=stage.lower().replace("-","");rows=sorted(root.glob(f"**/d2-vnext-{slug}-provider-shard-{shard_id:02d}.json"));rows=[p for p in rows if "manifest" not in p.name]
    if not rows:return None
    if len(rows)!=1:raise AssertionError("multiple Q2 shard outputs")
    return rows[0]
def _synthetic_failure(stage,pair_index,reason,shard_id):
    schema_id,local=core.schema_and_local_index(stage,pair_index);slug=stage.lower().replace("-","")
    return {"status":"failed","stage":stage,"pair_index":pair_index,"schema_id":schema_id,"schema_pair_index":local,"pair_public_id":f"d2-vnext-{slug}-{schema_id}-pair-{local:03d}","failure_class":reason,"error_type":None,"error_sha256":None,"terminal_failure":None,"registered_shard_id":shard_id}
def _validate_complete_call(call):
    if call.get("model")!=EXPECTED_MODEL:raise AssertionError("Q2 complete call model mismatch")
    if abs(float(call.get("temperature"))-EXPECTED_TEMPERATURE)>1e-12:raise AssertionError("Q2 temperature mismatch")
    if call.get("retry_raw_first_response_content_included") is not False:raise AssertionError("Q2 raw content propagation")
    used=call.get("retry_used");accepted=call.get("accepted_attempt_index");inv=call.get("agent_invocation_count");trigger=call.get("retry_trigger_class")
    if used not in {True,False} or accepted not in {1,2}:raise AssertionError("Q2 retry observability invalid")
    if inv!=(2 if used else 1):raise AssertionError("Q2 invocation count invalid")
    if used and trigger not in {"clean_nonempty_exact_parser_invalid","clean_terminal_empty"}:raise AssertionError("Q2 retry trigger invalid")
    if not used and trigger is not None:raise AssertionError("Q2 trigger without retry")
    if accepted==1 and (used or call.get("first_attempt_parse_valid") is not True):raise AssertionError("Q2 accepted first invalid")
    if accepted==2 and (not used or call.get("second_attempt_parse_valid") is not True):raise AssertionError("Q2 accepted retry invalid")
    if used and call.get("retry_eligible_after_first") is not True:raise AssertionError("Q2 retry used without eligibility")
    if type(call.get("first_attempt_api_calls")) is not int:raise AssertionError("Q2 first api_calls missing")
    if used and type(call.get("second_attempt_api_calls")) is not int:raise AssertionError("Q2 second api_calls missing")
    physical=call.get("physical_attempts");attempts=call.get("attempt_log")
    if type(physical) is not int or not 1<=physical<=36 or not isinstance(attempts,list) or len(attempts)!=physical:raise AssertionError("Q2 physical accounting invalid")
def _validate_pair_records(records):
    for record in records:
        if record.get("status")!="complete":continue
        arms=record.get("arms")
        if not isinstance(arms,dict):raise AssertionError("Q2 arms missing")
        for payload in arms.values():
            if not isinstance(payload,dict) or payload.get("status")=="failed_diagnostic":continue
            calls=payload.get("calls")
            if not isinstance(calls,list):raise AssertionError("Q2 calls missing")
            for call in calls:_validate_complete_call(call)
def aggregate(root:Path,*,stage:str,shard_map_path:Path)->dict[str,Any]:
    shard_map=json.loads(shard_map_path.read_text())
    if shard_map!=materializer.build_shard_map(stage):raise AssertionError("Q2 shard-map drift")
    all_records=[];shard_inputs=[];physical_total=0;candidate=None;defects=[]
    for expected in shard_map["shards"]:
        sid=int(expected["shard"]);path=_find_shard(root,stage,sid);indices=[int(x) for x in expected["pair_indices"]]
        if path is None:
            all_records.extend(_synthetic_failure(stage,i,"missing_provider_shard",sid) for i in indices);shard_inputs.append({"shard_id":sid,"status":"missing","sha256":None});defects.append({"shard_id":sid,"defect":"missing_provider_shard"});continue
        try:
            p=json.loads(path.read_text())
            if p.get("schema")!="d2-vnext-q2-acquisition-provider-shard-v0.1" or p.get("study_stream")!="D2-vNext-Q2" or p.get("stage")!=stage:raise AssertionError("Q2 shard schema/stream mismatch")
            if p.get("fresh_namespace")!=core.NAMESPACE or p.get("status")!="provider_shard_complete_unclassified" or p.get("classification") is not None:raise AssertionError("Q2 shard status mismatch")
            if int(p["shard_id"])!=sid or [int(x) for x in p.get("pair_indices",[])]!=indices or p.get("schema_counts")!=expected["schema_counts"]:raise AssertionError("Q2 shard map mismatch")
            c=p.get("authorized_candidate_sha")
            if not isinstance(c,str) or len(c)!=40:raise AssertionError("Q2 candidate missing")
            candidate=c if candidate is None else candidate
            if c!=candidate:raise AssertionError("Q2 cross-shard candidate mismatch")
            accounting=p.get("transport_accounting",{});sends=accounting.get("physical_provider_sends_observed")
            if type(sends) is not int or not 0<=sends<=1152:raise AssertionError("Q2 send count invalid")
            for k in ("provider_sends_blocked_by_budget","unexpected_outbound_http_requests_blocked","logical_attribution_mismatch_blocks","provider_workers_alive_after_drain"):
                if accounting.get(k)!=0:raise AssertionError(f"Q2 transport failure: {k}")
            if accounting.get("transport_hooks_restored_after_drain") is not True:raise AssertionError("Q2 hooks not restored")
            records=p.get("pair_records")
            if not isinstance(records,list) or [int(r["pair_index"]) for r in records]!=indices:raise AssertionError("Q2 record coverage")
            _validate_pair_records(records);physical_total+=sends;all_records.extend(records);shard_inputs.append({"shard_id":sid,"status":"loaded","sha256":file_sha256(path),"physical_provider_sends_observed":sends})
        except Exception as exc:
            fp=hashlib.sha256(f"{type(exc).__name__}:{str(exc)[:500]}".encode()).hexdigest();all_records.extend(_synthetic_failure(stage,i,"invalid_provider_shard",sid) for i in indices);shard_inputs.append({"shard_id":sid,"status":"invalid","sha256":file_sha256(path),"error_sha256":fp});defects.append({"shard_id":sid,"defect":"invalid_provider_shard","error_sha256":fp})
    all_records.sort(key=lambda r:int(r["pair_index"]))
    if [int(r["pair_index"]) for r in all_records]!=list(range(core.pair_count(stage))):raise AssertionError("Q2 coverage mismatch")
    if physical_total>CAMPAIGN_CAP[stage]:raise AssertionError("Q2 campaign ceiling exceeded")
    complete=[r for r in all_records if r.get("status")=="complete"]
    return {"schema":"d2-vnext-q2-acquisition-provider-output-v0.1","study_stream":"D2-vNext-Q2","stage":stage,"fresh_namespace":core.NAMESPACE,"status":"provider_campaign_complete_unclassified","classification":None,"authorized_candidate_sha":candidate,"attempted_pairs":core.pair_count(stage),"complete_pairs":len(complete),"failed_pairs":len(all_records)-len(complete),"requested_model":EXPECTED_MODEL,"effective_model_identity_observed":False,"effective_model":None,"temperature":EXPECTED_TEMPERATURE,"thinking":"disabled","response_format":{"type":"json_object"},"cohort_pairs_sha256":materializer.EXPECTED_COHORT_SHA256[stage],"physical_provider_sends_observed_total":physical_total,"maximum_physical_provider_sends_per_logical_call":36,"maximum_physical_provider_sends_per_shard":1152,"maximum_physical_provider_sends_campaign":CAMPAIGN_CAP[stage],"transport_integrity":{"passed":not defects,"defects":defects},"pair_records":all_records,"shard_inputs":shard_inputs,"shard_map_sha256":file_sha256(shard_map_path),"scientific_effect_gates_authorized":False,"registry_promotion_authorized":False,"acceptance_action_authorized":False,"production_historical_substrate_enabled":False}
def main():
    ap=argparse.ArgumentParser();ap.add_argument("provider_shards");ap.add_argument("--stage",choices=core.STAGES,required=True);ap.add_argument("--shard-map");ap.add_argument("--output-dir",default="output/d2-vnext-q2-canonical-provider");a=ap.parse_args();default="research/d2_vnext_q2/D2_VNEXT_Q2_A_SHARD_MAP.json" if a.stage==core.STAGE_A else "research/d2_vnext_q2/D2_VNEXT_Q2_B_SHARD_MAP.json";outp=aggregate(Path(a.provider_shards),stage=a.stage,shard_map_path=Path(a.shard_map or default));out=Path(a.output_dir);out.mkdir(parents=True,exist_ok=True);slug=a.stage.lower().replace("-","");path=out/f"d2-vnext-{slug}-provider-output.json";path.write_bytes(canonical_bytes(outp));manifest={"schema":"d2-vnext-q2-acquisition-provider-output-manifest-v0.1","study_stream":"D2-vNext-Q2","stage":a.stage,"provider_output_sha256":file_sha256(path),"attempted_pairs":outp["attempted_pairs"],"complete_pairs":outp["complete_pairs"],"failed_pairs":outp["failed_pairs"],"cohort_pairs_sha256":materializer.EXPECTED_COHORT_SHA256[a.stage],"physical_provider_sends_observed_total":outp["physical_provider_sends_observed_total"],"transport_integrity_pass":outp["transport_integrity"]["passed"],"classification":None,"scientific_effect_gates_authorized":False,"registry_promotion_authorized":False,"production_historical_substrate_enabled":False};(out/"provider-output-manifest.json").write_bytes(canonical_bytes(manifest));print(json.dumps(manifest,indent=2,sort_keys=True))
if __name__=="__main__":main()
