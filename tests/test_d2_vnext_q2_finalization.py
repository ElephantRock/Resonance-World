# ruff: noqa
import finalize_d2_vnext_q2_b_qualification as f
P="a"*64;E="b"*64
def result():return {"schema":"d2-vnext-q2-acquisition-qualification-result-v0.1","stage":"Q2-B","classification":"D2-vNext-Q2-B2","provider_output_sha256":P,"future_confirmatory_clearance_contract":{"resource_feasible":True}}
def review(verdict="PASS"):return {"schema":"d2-vnext-q2-b-exchangeability-review-v0.1","study_stream":"D2-vNext-Q2","provider_output_sha256":P,"q2_b_evaluation_result_sha256":E,"reviewer":"r","review_timestamp_utc":"2026-09-24T00:00:00Z","reviewed_completion_by_schema":True,"reviewed_completion_by_shard":True,"reviewed_completion_by_execution_wave":True,"reviewed_transport_and_runtime_metadata":True,"scientific_effect_inputs_consulted":False,"verdict":verdict,"rationale":"acquisition-only"}
def test_finalization_ceiling():
    x=f.finalize(result(),review());assert x["classification"]=="D2-vNext-Q2-B-PASS" and x["future_confirmatory_provider_execution_authorized"] is False and x["scientific_effect_gates_computed"] is False
