#!/usr/bin/env python3
# ruff: noqa: E501
"""Aggregate four Q3-D provider shards into one canonical diagnostic payload."""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
from typing import Any
import materialize_d2_vnext_q3d_diagnostic as materializer


def canonical_bytes(v:Any)->bytes:return (json.dumps(v,sort_keys=True,separators=(",",":"))+"\n").encode()
def file_sha256(p:Path)->str:return hashlib.sha256(p.read_bytes()).hexdigest()

def main()->None:
    ap=argparse.ArgumentParser();ap.add_argument("input_dir");ap.add_argument("--output-dir",default="output/d2-vnext-q3d-canonical");a=ap.parse_args()
    root=Path(a.input_dir);paths=sorted(root.rglob("d2-vnext-q3d-provider-shard-??.json"));defects=[];shards=[]
    if len(paths)!=materializer.SHARD_COUNT:defects.append(f"expected_{materializer.SHARD_COUNT}_shards_got_{len(paths)}")
    for p in paths:
        try:row=json.loads(p.read_text())
        except Exception as exc:defects.append(f"unreadable_shard:{p.name}:{type(exc).__name__}");continue
        shards.append(row)
    ids=[x.get("shard_id") for x in shards]
    if sorted(ids)!=list(range(materializer.SHARD_COUNT)):defects.append("shard_id_coverage_mismatch")
    candidates={x.get("authorized_candidate_sha") for x in shards}
    if len(candidates)!=1:defects.append("candidate_identity_mismatch")
    sends=sum(int(x.get("transport_accounting",{}).get("physical_provider_sends_observed",0)) for x in shards)
    if sends>materializer.MAX_PHYSICAL_SENDS_CAMPAIGN:defects.append("campaign_send_cap_exceeded")
    for row in shards:
        acct=row.get("transport_accounting",{})
        if int(acct.get("physical_provider_sends_observed",0))>materializer.MAX_PHYSICAL_SENDS_PER_SHARD:defects.append(f"shard_{row.get('shard_id')}_send_cap_exceeded")
        if any(int(acct.get(k,0))!=0 for k in ("provider_sends_blocked_by_budget","unexpected_outbound_http_requests_blocked","logical_attribution_mismatch_blocks")):defects.append(f"shard_{row.get('shard_id')}_transport_integrity_defect")
        if int(acct.get("provider_workers_alive_after_drain",0))!=0 or acct.get("transport_hooks_restored_after_drain") is not True:defects.append(f"shard_{row.get('shard_id')}_worker_or_hook_defect")
    pairs=sorted((pair for row in shards for pair in row.get("pair_records",[])),key=lambda x:int(x.get("pair_index",-1)))
    if [int(x.get("pair_index",-1)) for x in pairs]!=list(range(16)):defects.append("pair_coverage_mismatch")
    canonical={"schema":"d2-vnext-q3d-canonical-provider-output-v0.1","study_stream":"D2-vNext-Q3-D","stage":"Q3-D","fresh_namespace":"rw.d2-vnext-q3d-terminal-boundary-diagnostic.v1","authorized_candidate_sha":next(iter(candidates)) if len(candidates)==1 else None,"cohort_pairs_sha256":materializer.EXPECTED_COHORT_SHA256,"attempted_pairs":len(pairs),"complete_pairs":sum(1 for x in pairs if x.get("status")=="complete"),"failed_pairs":sum(1 for x in pairs if x.get("status")!="complete"),"physical_provider_sends_observed":sends,"maximum_physical_provider_sends_campaign":materializer.MAX_PHYSICAL_SENDS_CAMPAIGN,"integrity_defects":sorted(set(defects)),"pair_records":pairs,"shard_summaries":[{"shard_id":x.get("shard_id"),"attempted_pairs":x.get("attempted_pairs"),"complete_pairs":x.get("complete_pairs"),"failed_pairs":x.get("failed_pairs"),"physical_provider_sends_observed":x.get("transport_accounting",{}).get("physical_provider_sends_observed")} for x in sorted(shards,key=lambda y:int(y.get("shard_id",-1)))],"scientific_effect_gates_authorized":False,"registry_promotion_authorized":False,"acceptance_action_authorized":False,"production_historical_substrate_enabled":False}
    out=Path(a.output_dir);out.mkdir(parents=True,exist_ok=True);path=out/"d2-vnext-q3d-provider-output.json";path.write_bytes(canonical_bytes(canonical));manifest={"schema":"d2-vnext-q3d-canonical-provider-manifest-v0.1","provider_output_sha256":file_sha256(path),"integrity_defects":canonical["integrity_defects"],"attempted_pairs":canonical["attempted_pairs"],"physical_provider_sends_observed":sends,"provider_execution_authorized":False,"scientific_effect_gates_authorized":False};(out/"manifest.json").write_bytes(canonical_bytes(manifest));print(json.dumps(manifest,indent=2,sort_keys=True))

if __name__=="__main__":main()
