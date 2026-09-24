#!/usr/bin/env python3
# ruff: noqa: E501
from __future__ import annotations
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];R=ROOT/"research/d2_vnext_q2"
def load(n):return json.loads((R/n).read_text())
def main():
    c=load("D2_VNEXT_Q2_CONTRACT.json");r=load("D2_VNEXT_Q2_REQUEST_PLAN.json");o=load("D2_VNEXT_Q2_FAILURE_OBSERVABILITY_SCHEMA.json");a=load("D2_VNEXT_Q2_A_COHORT_LOCK.json");b=load("D2_VNEXT_Q2_B_COHORT_LOCK.json");am=load("D2_VNEXT_Q2_A_SHARD_MAP.json");bm=load("D2_VNEXT_Q2_B_SHARD_MAP.json")
    assert c["issue"]==293 and c["status"]=="construction_only_provider_execution_not_authorized" and c["governance"]["provider_execution_authorized"] is False
    assert c["predecessor"]["classification"]=="D2-vNext-Q1-A1" and c["predecessor"]["workflow_run_id"]==35998227643
    assert c["sole_mechanism_change"]["retry_eligibility_added"]=="strict_clean_terminal_empty_only" and c["sole_mechanism_change"]["max_agent_invocations_changed"] is False
    assert r["hermes_revision"]=="036cbdfa0a3158454a0a2a7a7388cf70353326b4" and r["requested_model"]=="glm-5.3" and r["max_agent_invocations_per_logical_call"]==2
    assert r["provider_execution_authorized"] is False and r["retry_raw_first_response_content_allowed"] is False
    assert a["cohort_pairs_sha256"]=="74ac69fc045c88e93ea08e86d031dcae23fa179bcba03d2b170526085e00b61b" and b["cohort_pairs_sha256"]=="7ccace45abe7df9eb510c72649d99650b7a5b26d66829a65c638d762ce765e53"
    for lock in (a,b):assert lock["cross_schema_seed_overlap"]==0 and all(v==0 for v in lock["predecessor_seed_namespace_overlap"].values())
    for m,count,cap in ((am,4,4608),(bm,24,27648)):
        assert m["shard_count"]==count and m["maximum_physical_provider_sends_campaign"]==cap and m["maximum_physical_provider_sends_per_shard"]==1152 and m["maximum_physical_provider_sends_per_logical_call"]==36
        assert all(x["schema_counts"]=={"threshold_at_4":4,"parity_pair":4,"interval_pair":4,"pairwise_order":4} for x in m["shards"])
    assert "api_calls" in o["required_attempt_fields"] and o["instrumentation_invariants"]["retry_eligibility_change"]=="clean_terminal_empty_only" and o["raw_response_content_allowed"] is False
    for marker in (R/"RUN_D2_VNEXT_Q2_A",R/"RUN_D2_VNEXT_Q2_B"):
        if marker.exists():raise AssertionError(f"Q2 construction marker present: {marker}")
    print("D2-vNext-Q2 contract validation PASS (credential-free; provider execution not authorized)")
if __name__=="__main__":main()
