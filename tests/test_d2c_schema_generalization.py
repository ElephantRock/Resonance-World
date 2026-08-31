from __future__ import annotations

import json
import sys
from pathlib import Path
from statistics import NormalDist

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import d2c_schema_core as core  # noqa: E402
import materialize_d2c_schema_generalization as materializer  # noqa: E402

SCHEMA_SUITE = Path("research/d2c/D2C_SCHEMA_SUITE.json")
SAMPLE_SIZE = Path("research/d2c/D2C_SAMPLE_SIZE.json")
REQUEST_PLAN = Path("research/d2c/D2C_REQUEST_PLAN.json")


def test_schema_suite_is_three_new_g2_families():
    suite = json.loads(SCHEMA_SUITE.read_text())
    assert suite["governance_novelty"] == "G2_new_schema_same_abstract_operator"
    ids = [row["schema_id"] for row in suite["schemas"]]
    assert ids == list(core.SCHEMA_ORDER)
    assert all(row["legacy_d2_schema"] is False for row in suite["schemas"])
    assert suite["legacy_d2_threshold_schema_counted_as_test_schema"] is False
    assert suite["production_historical_substrate_enabled"] is False


def test_policy_selectors_and_latent_rules_are_schema_specific():
    parity = core.policy_for("parity_pair", 4_200_000)
    interval = core.policy_for("interval_pair", 4_400_000)
    order = core.policy_for("pairwise_order", 4_600_000)
    assert len(parity.selectors) == 2 and len(set(parity.selectors)) == 2
    assert len(interval.selectors) == 2 and len(set(interval.selectors)) == 2
    assert len(order.selectors) == 4 and set(order.selectors) == {0, 1, 2, 3}
    features = (0, 3, 4, 7)
    assert core.latent_bits(parity, features) in {(0, 0), (0, 1), (1, 0), (1, 1)}
    assert core.latent_bits(interval, features) in {(0, 0), (0, 1), (1, 0), (1, 1)}
    assert core.latent_bits(order, features) in {(0, 0), (0, 1), (1, 0), (1, 1)}


def test_balanced_generation_and_within_pair_disjointness():
    for global_index in (0, 179, 180, 359, 360, 539):
        bundle = materializer.case_bundle(global_index)
        assert len(bundle["source_cases"]) == 40
        assert len(bundle["destination_cases"]) == 40
        assert len(bundle["eval_cases"]) == 32
        for cases, expected_each in ((bundle["source_cases"], 10), (bundle["destination_cases"], 10), (bundle["eval_cases"], 8)):
            counts = {action: 0 for action in core.ACTIONS}
            for case in cases:
                counts[case["correct_action"]] += 1
            assert set(counts.values()) == {expected_each}
        assert bundle["source_features"].isdisjoint(bundle["destination_features"])
        assert (bundle["source_features"] | bundle["destination_features"]).isdisjoint(bundle["eval_features"])


def test_global_pair_index_blocks_are_exact():
    assert core.schema_and_local_index(0) == ("parity_pair", 0)
    assert core.schema_and_local_index(179) == ("parity_pair", 179)
    assert core.schema_and_local_index(180) == ("interval_pair", 0)
    assert core.schema_and_local_index(359) == ("interval_pair", 179)
    assert core.schema_and_local_index(360) == ("pairwise_order", 0)
    assert core.schema_and_local_index(539) == ("pairwise_order", 179)


def test_seed_namespaces_are_pairwise_and_predecessor_disjoint():
    namespaces = {
        schema_id: materializer.seed_namespace(core.SCHEMA_SEED_BASES[schema_id], core.PAIRS_PER_SCHEMA)
        for schema_id in core.SCHEMA_ORDER
    }
    ids = list(core.SCHEMA_ORDER)
    for i, left in enumerate(ids):
        for right in ids[i + 1 :]:
            assert namespaces[left].isdisjoint(namespaces[right])
    for namespace in namespaces.values():
        assert namespace.isdisjoint(materializer.seed_namespace(1_200_000, 360))
        assert namespace.isdisjoint(materializer.seed_namespace(2_200_000, 360))
        assert namespace.isdisjoint(materializer.seed_namespace(3_200_000, 360))


def test_materialized_cohort_and_shards_are_exact():
    cohort = materializer.build_cohort_lock()
    shards = materializer.build_shard_map()
    assert cohort["pair_count"] == 540
    assert cohort["pairs_per_schema"] == 180
    assert cohort["schema_pair_counts"] == {schema_id: 180 for schema_id in core.SCHEMA_ORDER}
    assert cohort["all_source_destination_overlaps_zero"] is True
    assert cohort["all_development_evaluation_overlaps_zero"] is True
    assert cohort["cross_schema_seed_overlap"] == 0
    assert cohort["predecessor_seed_namespace_overlap"] == {"D2-C1": 0, "D2-C2": 0, "D2b": 0}
    assert shards["shard_count"] == 27
    assert shards["shards_per_schema"] == 9
    assert all(row["schema_id"] == core.SCHEMA_ORDER[row["shard"] // 9] for row in shards["shards"])
    union = [index for row in shards["shards"] for index in range(row["start_pair"], row["end_pair"] + 1)]
    assert union == list(range(540))


def test_sample_size_contract_is_prospective_and_conservative():
    sample = json.loads(SAMPLE_SIZE.read_text())
    assert sample["planning_effects_are_conventional_not_observed_parent_effects"] is True
    assert sample["planning_sd"] == 0.4
    assert sample["normal_approx_required_analyzable_n"] == 138
    assert sample["minimum_analyzable_pairs_per_schema"] == 165
    assert sample["attempted_pairs_per_schema"] == 180
    z_alpha = NormalDist().inv_cdf(0.95)
    computed_min_power = NormalDist().cdf((165 ** 0.5) * 0.1 / 0.4 - z_alpha)
    assert abs(computed_min_power - sample["approx_power_at_minimum_n"]) < 1e-12


def test_request_plan_fixes_no_rerun_and_no_registry_mutation():
    request = json.loads(REQUEST_PLAN.read_text())
    assert request["pair_count_attempted"] == 540
    assert request["minimum_analyzable_pairs_per_schema"] == 165
    assert request["provider_shard_count"] == 27
    assert request["pairs_per_provider_shard"] == 20
    assert request["logical_calls_campaign_before_retries"] == 16740
    assert request["confirmatory_same_request_stream_rerun_allowed"] is False
    assert request["frozen_evaluator_is_sole_classifier"] is True
    assert request["registry_promotion_authorized"] is False
    assert request["historical_substrate_enabled"] is False


def test_substantive_run_marker_is_absent_during_scaffold():
    assert not Path("research/d2c/RUN_D2C_SCHEMA_GENERALIZATION").exists()
