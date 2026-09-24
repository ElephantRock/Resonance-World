#!/usr/bin/env python3
# ruff: noqa: E501
"""Credential-free Q2 acquisition-qualification evaluator; no scientific-effect tests."""
from __future__ import annotations
import argparse,hashlib,json,math
from collections import Counter
from pathlib import Path
from typing import Any
import aggregate_d2_vnext_q2_acquisition as aggregator
import d2_vnext_q2_acquisition_core as core
import materialize_d2_vnext_q2_acquisition as materializer
EXPECTED_MODEL="glm-5.3";PRIMARY_ARMS=("fresh","developed_40","developed_80","developed_160");EXPECTED_CALLS={"fresh":4,"developed_40":9,"developed_80":14,"developed_160":24};EXPECTED_DEVELOPMENT_CASES={"fresh":0,"developed_40":40,"developed_80":80,"developed_160":160};ORACLE_CALLS=4;A_MIN_COMPLETE_PER_SCHEMA=12;FUTURE_MIN_ANALYZABLE=88;JOINT_CLEARANCE_TARGET=0.95;PER_SCHEMA_CLEARANCE_TARGET=0.9875;PER_SCHEMA_ALPHA=0.0125;MAX_FUTURE_TOTAL_ATTEMPTS=640
def canonical_bytes(v:Any)->bytes:return (json.dumps(v,sort_keys=True,separators=(",",":"))+"\n").encode()
def file_sha256(p:Path)->str:return hashlib.sha256(p.read_bytes()).hexdigest()
def score(truth,actions):return sum(a==b for a,b in zip(truth,actions,strict=True))/len(truth)
def validate_complete_pair(stage,record):
    defects=[];idx=int(record["pair_index"]);bundle=materializer.case_bundle(stage,idx);schema=str(bundle["schema_id"]);local=int(bundle["local_pair_index"])
    if record.get("stage")!=stage:defects.append("stage_mismatch")
    if record.get("schema_id")!=schema:defects.append("schema_id_mismatch")
    if int(record.get("schema_pair_index",-1))!=local:defects.append("schema_pair_index_mismatch")
    if record.get("pair_lock_record")!=materializer.pair_lock_record(stage,idx):defects.append("pair_lock_record_mismatch")
    truth=[c["correct_action"] for c in bundle["evaluation_cases"]]
    if record.get("evaluation_truth")!=truth:defects.append("evaluation_truth_mismatch")
    arms=record.get("arms")
    if not isinstance(arms,dict):return defects+["arms_missing"]
    for arm in PRIMARY_ARMS:
        p=arms.get(arm)
        if not isinstance(p,dict):defects.append(f"{arm}_missing");continue
        if p.get("development_cases")!=EXPECTED_DEVELOPMENT_CASES[arm]:defects.append(f"{arm}_development_cases_mismatch")
        calls=p.get("calls")
        if not isinstance(calls,list) or len(calls)!=EXPECTED_CALLS[arm]:defects.append(f"{arm}_call_records_mismatch")
        else:
            for i,c in enumerate(calls):
                try:aggregator._validate_complete_call(c)
                except Exception:defects.append(f"{arm}_call_{i}_invalid")
        actions=p.get("evaluation_actions")
        if not isinstance(actions,list):defects.append(f"{arm}_actions_missing")
        else:
            try:computed=score(truth,[str(x) for x in actions])
            except Exception:defects.append(f"{arm}_actions_invalid");continue
            if not isinstance(p.get("runner_final_score"),(int,float)) or abs(float(p["runner_final_score"])-computed)>1e-12:defects.append(f"{arm}_runner_score_mismatch")
    oracle=arms.get("oracle_instruction")
    if isinstance(oracle,dict) and oracle.get("status")=="complete_diagnostic":
        calls=oracle.get("calls")
        if not isinstance(calls,list) or len(calls)!=ORACLE_CALLS:defects.append("oracle_call_records_mismatch")
    elif not (isinstance(oracle,dict) and oracle.get("status")=="failed_diagnostic"):defects.append("oracle_status_invalid")
    return defects
def _validate_attempt(v):
    if not isinstance(v,dict):return False
    required={"runtime_exception","error_type","error_sha256","hermes_completed_flag_valid","hermes_completed","hermes_failed","hermes_partial","hermes_interrupted","hermes_error_present","api_calls","exact_structured_parse_valid","parse_diagnostic","physical_provider_sends_observed","exact_attributed_clean_transport","logical_attribution_integrity","effective_completed","terminal_iteration_override_used","adapter_reason"}
    return set(v)==required and type(v.get("api_calls")) is int
def validate_terminal_failure(record):
    if record.get("failure_class")!="q2_logical_call_no_accepted_exact_completion":return ["failure_not_bounded_logical_call_class"]
    t=record.get("terminal_failure")
    if not isinstance(t,dict):return ["terminal_failure_missing"]
    defects=[];required={"pair_public_id","pair_index","schema_id","arm","phase","logical_call_index","first_attempt","retry_eligible","retry_trigger_class","retry_used","second_attempt","accepted_exact_completion","terminal_error_type","terminal_error_sha256"}
    if set(t)!=required:defects.append("terminal_failure_shape")
    if not _validate_attempt(t.get("first_attempt")):defects.append("terminal_first_attempt_shape")
    used=t.get("retry_used");second=t.get("second_attempt");trigger=t.get("retry_trigger_class")
    if used is True and not _validate_attempt(second):defects.append("terminal_second_attempt_shape")
    if used is False and second is not None:defects.append("terminal_second_attempt_without_retry")
    if (trigger is None)!=(t.get("retry_eligible") is False):defects.append("terminal_retry_trigger_eligibility_mismatch")
    if used and trigger not in {"clean_nonempty_exact_parser_invalid","clean_terminal_empty"}:defects.append("terminal_retry_trigger_invalid")
    if t.get("accepted_exact_completion") is not False:defects.append("terminal_failure_marked_accepted")
    try:
        import d2_vnext_q2_hermes_client as client;client.assert_failure_evidence_has_no_raw_content(t)
    except Exception:defects.append("terminal_raw_content_or_schema_violation")
    return defects
def binomial_tail_at_least(k,n,p):
    if k<=0:return 1.0
    if k>n or p<=0:return 0.0
    if p>=1:return 1.0
    return min(1.0,max(0.0,sum(math.comb(n,j)*(p**j)*((1-p)**(n-j)) for j in range(k,n+1))))
def clopper_pearson_lower(successes,trials,alpha=PER_SCHEMA_ALPHA):
    if successes==0:return 0.0
    lo=0.0;hi=successes/trials
    for _ in range(100):
        mid=(lo+hi)/2
        if binomial_tail_at_least(successes,trials,mid)<alpha:lo=mid
        else:hi=mid
    return (lo+hi)/2
def required_future_attempts(p_lower):
    if p_lower<=0:return None
    for n in range(FUTURE_MIN_ANALYZABLE,MAX_FUTURE_TOTAL_ATTEMPTS+1):
        if binomial_tail_at_least(FUTURE_MIN_ANALYZABLE,n,p_lower)>=PER_SCHEMA_CLEARANCE_TARGET:return n
    return None
def evaluate(provider):
    gd=[];pd=[];od=[]
    if provider.get("schema")!="d2-vnext-q2-acquisition-provider-output-v0.1":gd.append("provider_schema_mismatch")
    if provider.get("study_stream")!="D2-vNext-Q2":gd.append("provider_stream_mismatch")
    stage=provider.get("stage")
    if stage not in core.STAGES:raise ValueError("unknown Q2 stage")
    if provider.get("status")!="provider_campaign_complete_unclassified" or provider.get("classification") is not None:gd.append("provider_status_mismatch")
    if provider.get("fresh_namespace")!=core.NAMESPACE:gd.append("fresh_namespace_mismatch")
    if provider.get("cohort_pairs_sha256")!=materializer.EXPECTED_COHORT_SHA256[stage]:gd.append("cohort_hash_mismatch")
    transport=provider.get("transport_integrity")
    if not isinstance(transport,dict) or transport.get("passed") is not True:gd.append("transport_integrity_failure")
    expected=core.pair_count(stage);records=provider.get("pair_records")
    if not isinstance(records,list) or len(records)!=expected:gd.append("pair_record_count_mismatch");records=records if isinstance(records,list) else []
    complete=Counter();failed=Counter()
    for r in records:
        idx=int(r["pair_index"]);schema,_=core.schema_and_local_index(stage,idx)
        if r.get("status")=="complete":
            defects=validate_complete_pair(stage,r)
            if defects:pd.append({"pair_index":idx,"defects":defects})
            else:complete[schema]+=1
        else:
            failed[schema]+=1;defects=validate_terminal_failure(r)
            if defects:od.append({"pair_index":idx,"defects":defects})
    rows={}
    for schema in core.SCHEMA_ORDER:
        invalid=sum(1 for x in pd if core.schema_and_local_index(stage,int(x["pair_index"]))[0]==schema);c=complete[schema];f=failed[schema]
        rows[schema]={"attempted_pairs":core.pairs_per_schema(stage),"complete_evaluator_analyzable_pairs":c,"failed_pairs":f,"invalid_complete_pairs":invalid,"completion_rate":c/core.pairs_per_schema(stage)}
    integrity=not gd and not pd and not od
    result={"schema":"d2-vnext-q2-acquisition-qualification-result-v0.1","study_stream":"D2-vNext-Q2","stage":stage,"status":"qualification_evaluated","integrity":{"passed":integrity,"global_defects":gd,"pair_defects":pd,"terminal_failure_observability_defects":od},"schema_results":rows,"scientific_effect_gates_computed":False,"q1_or_s2_data_pooled":False,"registry_promotion_authorized":False,"acceptance_action_authorized":False,"production_historical_substrate_enabled":False}
    if stage==core.STAGE_A:
        minimum=all(r["complete_evaluator_analyzable_pairs"]>=A_MIN_COMPLETE_PER_SCHEMA for r in rows.values());result["q2_a_continuation_gate"]={"minimum_complete_analyzable_pairs_per_schema":12,"minimum_screen_pass":minimum,"terminal_failure_observability_complete":not od,"transport_integrity_pass":isinstance(transport,dict) and transport.get("passed") is True,"pass":bool(integrity and minimum)}
        if not integrity:result["classification"]="D2-vNext-Q2-A0";result["classification_label"]="integrity_or_terminal_failure_observability_failure"
        elif not minimum:result["classification"]="D2-vNext-Q2-A1";result["classification_label"]="minimum_screen_completion_failure"
        else:result["classification"]="D2-vNext-Q2-A-PASS";result["classification_label"]="bounded_screen_pass_for_independent_q2_b_authorization_review"
        result["q2_b_provider_execution_authorized"]=False;return result
    lower={};required={}
    for schema,row in rows.items():
        p=clopper_pearson_lower(int(row["complete_evaluator_analyzable_pairs"]),int(row["attempted_pairs"]));lower[schema]=p;required[schema]=required_future_attempts(p);row["one_sided_exact_completion_lower_bound"]=p;row["lower_bound_alpha"]=PER_SCHEMA_ALPHA;row["future_attempts_required_for_88_at_q_0_9875"]=required[schema]
    finite=all(v is not None for v in required.values());total=sum(int(v) for v in required.values() if v is not None) if finite else None;feasible=bool(integrity and finite and total is not None and total<=MAX_FUTURE_TOTAL_ATTEMPTS)
    result["future_confirmatory_clearance_contract"]={"minimum_analyzable_pairs_per_schema":88,"joint_all_schema_clearance_target":0.95,"per_schema_clearance_target":0.9875,"per_schema_lower_bound_alpha":0.0125,"per_schema_lower_bounds":lower,"required_attempted_pairs_by_schema":required,"required_attempted_pairs_total":total,"maximum_allowed_attempted_pairs_total":640,"resource_feasible":feasible};result["exchangeability_review_required"]=True;result["exchangeability_review_status"]="pending_independent_review"
    if not integrity:result["classification"]="D2-vNext-Q2-B0";result["classification_label"]="integrity_or_terminal_failure_observability_failure"
    elif not feasible:result["classification"]="D2-vNext-Q2-B1";result["classification_label"]="future_confirmatory_resource_feasibility_failure"
    else:result["classification"]="D2-vNext-Q2-B2";result["classification_label"]="resource_feasible_pending_independent_exchangeability_review"
    return result
def main():
    ap=argparse.ArgumentParser();ap.add_argument("provider_output");ap.add_argument("--output-dir",default="output/d2-vnext-q2-evaluation");a=ap.parse_args();pp=Path(a.provider_output);result=evaluate(json.loads(pp.read_text()));result["provider_output_sha256"]=file_sha256(pp);out=Path(a.output_dir);out.mkdir(parents=True,exist_ok=True);slug=result["stage"].lower().replace("-","");rp=out/f"d2-vnext-{slug}-qualification-result.json";rp.write_bytes(canonical_bytes(result));manifest={"schema":"d2-vnext-q2-acquisition-qualification-manifest-v0.1","study_stream":"D2-vNext-Q2","stage":result["stage"],"classification":result["classification"],"classification_label":result["classification_label"],"result_sha256":file_sha256(rp),"provider_output_sha256":result["provider_output_sha256"],"scientific_effect_gates_computed":False,"provider_execution_authorized":False,"registry_promotion_authorized":False,"acceptance_action_authorized":False,"production_historical_substrate_enabled":False};(out/"evaluation-manifest.json").write_bytes(canonical_bytes(manifest));print(json.dumps(manifest,indent=2,sort_keys=True))
if __name__=="__main__":main()
