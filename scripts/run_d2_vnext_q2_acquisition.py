#!/usr/bin/env python3
# ruff: noqa: E501
"""Run one explicitly authorized D2-vNext-Q2 acquisition-qualification shard."""
from __future__ import annotations
import argparse,hashlib,json,os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any
import d2_vnext_q2_acquisition_core as core
import d2_vnext_q2_hermes_client as transport
import materialize_d2_vnext_q2_acquisition as materializer
import run_d2_vnext_s2_source_acquisition as s2runner
import run_d2d_source_acquisition as base
ISSUE=293;MODEL="glm-5.3";TEMPERATURE=0.8
STAGE_CONFIG={
 core.STAGE_A:{"marker":Path("research/d2_vnext_q2/RUN_D2_VNEXT_Q2_A"),"auth_env":"D2_VNEXT_Q2_A_EXECUTION_AUTHORIZED","authorization":"D2_vNext_Q2_A_exact_candidate_acquisition_qualification_and_4608_send_cap_explicitly_authorized","campaign_send_cap":4608,"cohort_lock":Path("research/d2_vnext_q2/D2_VNEXT_Q2_A_COHORT_LOCK.json"),"shard_map":Path("research/d2_vnext_q2/D2_VNEXT_Q2_A_SHARD_MAP.json")},
 core.STAGE_B:{"marker":Path("research/d2_vnext_q2/RUN_D2_VNEXT_Q2_B"),"auth_env":"D2_VNEXT_Q2_B_EXECUTION_AUTHORIZED","authorization":"D2_vNext_Q2_B_exact_candidate_acquisition_qualification_and_27648_send_cap_explicitly_authorized","campaign_send_cap":27648,"cohort_lock":Path("research/d2_vnext_q2/D2_VNEXT_Q2_B_COHORT_LOCK.json"),"shard_map":Path("research/d2_vnext_q2/D2_VNEXT_Q2_B_SHARD_MAP.json"),"q2_a_closeout":Path("research/d2_vnext_q2/D2_VNEXT_Q2_A_QUALIFICATION_CLOSEOUT.json")}}
def canonical_bytes(v:Any)->bytes:return (json.dumps(v,sort_keys=True,separators=(",",":"))+"\n").encode()
def file_sha256(p:Path)->str:return hashlib.sha256(p.read_bytes()).hexdigest()
def _q2_call_record(result:dict[str,Any],strategy:str)->dict[str,Any]:
    row=s2runner._s2_call_record(result,strategy)
    row.update({"retry_trigger_class":result["retry_trigger_class"],"first_attempt_api_calls":result["first_attempt_api_calls"],"second_attempt_api_calls":result["second_attempt_api_calls"]})
    return row
class _StageCoreAdapter:
    def __init__(self,stage:str):self.stage=stage
    def __getattr__(self,name:str)->Any:return getattr(core,name)
    def schema_and_local_index(self,pair_index:int)->tuple[str,int]:return core.schema_and_local_index(self.stage,pair_index)
class _StageMaterializerAdapter:
    def __init__(self,stage:str):self.stage=stage;self.EXPECTED_COHORT_SHA256=materializer.EXPECTED_COHORT_SHA256[stage]
    def case_bundle(self,pair_index:int)->dict[str,Any]:return materializer.case_bundle(self.stage,pair_index)
    def pair_lock_record(self,pair_index:int)->dict[str,Any]:return materializer.pair_lock_record(self.stage,pair_index)
@contextmanager
def _stage_base_context(stage:str)->Iterator[None]:
    original=(base.core,base.materializer,base.EXPECTED_COHORT_SHA256,base.BEHAVIORAL_OBJECTIVE,base.MODEL,base.TEMPERATURE,base._call_record)
    stage_core=_StageCoreAdapter(stage);stage_materializer=_StageMaterializerAdapter(stage)
    base.core=stage_core;base.materializer=stage_materializer;base.EXPECTED_COHORT_SHA256=stage_materializer.EXPECTED_COHORT_SHA256;base.BEHAVIORAL_OBJECTIVE=s2runner.BEHAVIORAL_OBJECTIVE;base.MODEL=MODEL;base.TEMPERATURE=TEMPERATURE;base._call_record=_q2_call_record
    try:yield
    finally:(base.core,base.materializer,base.EXPECTED_COHORT_SHA256,base.BEHAVIORAL_OBJECTIVE,base.MODEL,base.TEMPERATURE,base._call_record)=original
def _marker_record(stage:str)->dict[str,str]:
    c=STAGE_CONFIG[stage];marker=c["marker"]
    if not marker.exists():raise RuntimeError(f"D2-vNext-Q2 {stage} authorization marker is absent")
    lines=[x for x in marker.read_text().splitlines() if x]
    if any("=" not in x for x in lines):raise RuntimeError("Q2 authorization marker malformed")
    f=dict(x.split("=",1) for x in lines);required={"candidate_sha","issue","authorization","maximum_physical_sends_campaign"}
    if stage==core.STAGE_B:required.add("q2_a_result_sha256")
    if set(f)!=required:raise RuntimeError("Q2 authorization marker fields invalid")
    if f["issue"]!=str(ISSUE) or f["authorization"]!=c["authorization"] or f["maximum_physical_sends_campaign"]!=str(c["campaign_send_cap"]):raise RuntimeError("Q2 authorization marker mismatch")
    candidate=f["candidate_sha"]
    if len(candidate)!=40 or any(ch not in "0123456789abcdef" for ch in candidate):raise RuntimeError("Q2 candidate SHA invalid")
    if stage==core.STAGE_B:
        p=c["q2_a_closeout"]
        if not p.exists():raise RuntimeError("Q2-B requires Q2-A closeout")
        closeout=json.loads(p.read_text())
        if closeout.get("classification")!="D2-vNext-Q2-A-PASS":raise RuntimeError("Q2-B requires frozen Q2-A PASS")
        if file_sha256(p)!=f["q2_a_result_sha256"]:raise RuntimeError("Q2-B closeout hash mismatch")
    return f
def assert_authorized(stage:str)->dict[str,str]:
    c=STAGE_CONFIG[stage]
    if os.environ.get(c["auth_env"])!="1":raise RuntimeError(f"D2-vNext-Q2 {stage} provider execution is not authorized")
    return _marker_record(stage)
def verify_frozen_inputs(stage:str):
    c=STAGE_CONFIG[stage];lp=c["cohort_lock"];mp=c["shard_map"]
    lock=json.loads(lp.read_text());m=json.loads(mp.read_text())
    if lock!=materializer.build_cohort_lock(stage):raise AssertionError("Q2 committed cohort-lock drift")
    if m!=materializer.build_shard_map(stage):raise AssertionError("Q2 committed shard-map drift")
    return lock,m
def _rename_pair(stage:str,record:dict[str,Any])->dict[str,Any]:
    record=dict(record);pid=record.get("pair_public_id");slug=stage.lower().replace("-","")
    if isinstance(pid,str) and pid.startswith("d2d-"):record["pair_public_id"]=f"d2-vnext-{slug}-"+pid[len("d2d-"):]
    record["stage"]=stage;return record
def run_pair_safe(client:transport.Client,stage:str,pair_index:int)->dict[str,Any]:
    schema_id,local_index=core.schema_and_local_index(stage,pair_index);slug=stage.lower().replace("-","");pid=f"d2-vnext-{slug}-{schema_id}-pair-{local_index:03d}"
    try:return _rename_pair(stage,base.run_pair(client,pair_index))
    except transport.Q2LogicalCallFailure as exc:
        terminal=dict(exc.evidence);terminal.update({"pair_public_id":pid,"pair_index":pair_index,"schema_id":schema_id});transport.assert_failure_evidence_has_no_raw_content(terminal)
        return {"status":"failed","stage":stage,"pair_index":pair_index,"schema_id":schema_id,"schema_pair_index":local_index,"pair_public_id":pid,"failure_class":"q2_logical_call_no_accepted_exact_completion","error_type":"RuntimeError","error_sha256":transport.TERMINAL_FAILURE_SHA256,"terminal_failure":terminal}
    except Exception as exc:
        fp=hashlib.sha256(f"{type(exc).__name__}:{str(exc)[:500]}".encode()).hexdigest()
        return {"status":"failed","stage":stage,"pair_index":pair_index,"schema_id":schema_id,"schema_pair_index":local_index,"pair_public_id":pid,"failure_class":"q2_pair_runtime_or_instrumentation_failure","error_type":type(exc).__name__,"error_sha256":fp,"terminal_failure":None}
def main():
    ap=argparse.ArgumentParser();ap.add_argument("--stage",choices=core.STAGES,required=True);ap.add_argument("--shard-id",type=int,required=True);ap.add_argument("--output-dir",default="output/d2-vnext-q2-provider-shard");a=ap.parse_args();stage=a.stage
    marker=assert_authorized(stage);lock,shard_map=verify_frozen_inputs(stage)
    if not 0<=a.shard_id<int(shard_map["shard_count"]):raise AssertionError("unknown Q2 shard")
    shard=shard_map["shards"][a.shard_id];indices=[int(x) for x in shard["pair_indices"]]
    key=os.environ.get("ZAI_API_KEY","")
    if not key:raise RuntimeError("ZAI_API_KEY is required for authorized Q2 execution")
    budget=transport.new_shard_budget();ledger=transport.TransportLedger();workers=transport.ProviderWorkerTracker();client=transport.Client(key,budget,ledger)
    with transport.guarded_shard_transport(budget,ledger,workers),_stage_base_context(stage):records=[run_pair_safe(client,stage,i) for i in indices]
    if workers.alive_after_drain!=0 or not workers.transport_hooks_restored:raise RuntimeError("Q2 workers/hooks did not close cleanly")
    if ledger.attribution_mismatches!=0:raise RuntimeError("Q2 attribution mismatch")
    complete=[r for r in records if r["status"]=="complete"];failed=[r for r in records if r["status"]!="complete"]
    output={"schema":"d2-vnext-q2-acquisition-provider-shard-v0.1","study_stream":"D2-vNext-Q2","stage":stage,"fresh_namespace":core.NAMESPACE,"status":"provider_shard_complete_unclassified","classification":None,"authorized_candidate_sha":marker["candidate_sha"],"authorization_scope":f"exact_candidate_{stage}_acquisition_qualification_and_bounded_provider_execution","authorization_marker_sha256":file_sha256(STAGE_CONFIG[stage]["marker"]),"shard_id":a.shard_id,"pair_indices":indices,"schema_counts":shard["schema_counts"],"attempted_pairs":len(records),"complete_pairs":len(complete),"failed_pairs":len(failed),"requested_model":MODEL,"effective_model_identity_observed":False,"effective_model":None,"temperature":TEMPERATURE,"thinking":"disabled","response_format":{"type":"json_object"},"cohort_lock":lock,"pair_records":records,"transport_accounting":{"logical_calls_started":client.logical_calls_started,"logical_calls_completed":client.logical_calls_completed,"logical_call_failures":client.logical_call_failures,"format_regeneration_retries_used":client.retry_used_count,"terminal_iteration_overrides_used":client.terminal_iteration_override_count,"physical_provider_sends_observed":budget.total_sends,"maximum_physical_provider_sends_per_logical_call":transport.MAX_PHYSICAL_SENDS_PER_LOGICAL_CALL,"maximum_physical_provider_sends_per_shard":transport.MAX_PHYSICAL_SENDS_PER_SHARD,"provider_sends_blocked_by_budget":budget.blocked_budget,"unexpected_outbound_http_requests_blocked":budget.blocked_unexpected,"logical_attribution_mismatch_blocks":ledger.attribution_mismatches,"provider_workers_observed":workers.observed,"provider_workers_alive_after_drain":workers.alive_after_drain,"transport_hooks_restored_after_drain":workers.transport_hooks_restored,"allowed_endpoint_prefix":transport.BASE_URL},"cohort_lock_file_sha256":file_sha256(STAGE_CONFIG[stage]["cohort_lock"]),"shard_map_sha256":file_sha256(STAGE_CONFIG[stage]["shard_map"]),"qualification_campaign_executed":True,"scientific_effect_gates_authorized":False,"registry_promotion_authorized":False,"acceptance_action_authorized":False,"production_historical_substrate_enabled":False}
    out=Path(a.output_dir);out.mkdir(parents=True,exist_ok=True);slug=stage.lower().replace("-","");path=out/f"d2-vnext-{slug}-provider-shard-{a.shard_id:02d}.json";path.write_bytes(canonical_bytes(output))
    manifest={"schema":"d2-vnext-q2-acquisition-provider-shard-manifest-v0.1","study_stream":"D2-vNext-Q2","stage":stage,"shard_id":a.shard_id,"provider_shard_output_sha256":file_sha256(path),"attempted_pairs":len(records),"complete_pairs":len(complete),"failed_pairs":len(failed),"cohort_pairs_sha256":materializer.EXPECTED_COHORT_SHA256[stage],"physical_provider_sends_observed":budget.total_sends,"classification":None,"scientific_effect_gates_authorized":False,"registry_promotion_authorized":False,"production_historical_substrate_enabled":False}
    (out/f"d2-vnext-{slug}-provider-shard-{a.shard_id:02d}-manifest.json").write_bytes(canonical_bytes(manifest));print(json.dumps(manifest,indent=2,sort_keys=True))
if __name__=="__main__":main()
