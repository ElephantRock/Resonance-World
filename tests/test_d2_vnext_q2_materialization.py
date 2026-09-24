# ruff: noqa
from pathlib import Path
import d2_vnext_q2_acquisition_core as core
import materialize_d2_vnext_q2_acquisition as m
A="74ac69fc045c88e93ea08e86d031dcae23fa179bcba03d2b170526085e00b61b";B="7ccace45abe7df9eb510c72649d99650b7a5b26d66829a65c638d762ce765e53"
def test_sizes_hashes_and_topology():
    assert core.pair_count(core.STAGE_A)==64 and core.pair_count(core.STAGE_B)==384
    assert m.build_cohort_lock(core.STAGE_A)["cohort_pairs_sha256"]==A and m.build_cohort_lock(core.STAGE_B)["cohort_pairs_sha256"]==B
    for stage,shards,cap in ((core.STAGE_A,4,4608),(core.STAGE_B,24,27648)):
        sm=m.build_shard_map(stage);assert sm["shard_count"]==shards and sm["maximum_physical_provider_sends_campaign"]==cap
        assert all(x["schema_counts"]=={s:4 for s in core.SCHEMA_ORDER} for x in sm["shards"])
def test_freshness_and_markers():
    m.validate_cross_stage_seed_separation()
    for stage in core.STAGES:assert all(v==0 for v in m.build_cohort_lock(stage)["predecessor_seed_namespace_overlap"].values())
    root=Path(__file__).resolve().parents[1]/"research/d2_vnext_q2";assert not (root/"RUN_D2_VNEXT_Q2_A").exists() and not (root/"RUN_D2_VNEXT_Q2_B").exists()
def test_workflow_failure_classification_and_authorization_integrity():
    root=Path(__file__).resolve().parents[1]/".github/workflows"
    a=(root/"d2-vnext-q2-a-acquisition.yml").read_text();b=(root/"d2-vnext-q2-b-acquisition.yml").read_text()
    always="if: ${{ always() && needs.authorization-integrity.result == 'success' }}"
    assert always in a and "continue-on-error: true" in a and "git cat-file -e \"$candidate:$marker\"" in a
    assert always in b and "continue-on-error: true" in b and "git cat-file -e \"$candidate:$marker\"" in b
    assert 'test "$(git diff --name-only "$candidate" HEAD)" = "$marker"' in b
    assert "aggregate_d2_vnext_q2_acquisition.py output/provider-shards --stage Q2-B" in b
    assert "evaluate_d2_vnext_q2_acquisition.py output/canonical-provider/d2-vnext-q2b-provider-output.json" in b
    assert "execution-wave-index.json" in b
