from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import aggregate_d2b_replication as aggregator  # noqa: E402
import d2_c2_confirmatory_stats as stats  # noqa: E402
import evaluate_d2b_replication as evaluator  # noqa: E402
import run_d2b_replication as runner  # noqa: E402
from d2_calibration_r2_core import ACTIONS  # noqa: E402

PLAN = Path("research/d2b/PLAN.md")
REQUEST = Path("research/d2b/D2B_REPLICATION_REQUEST_PLAN.json")
COHORT = Path("research/d2b/d2b-replication-cohort-lock.json")
SHARDS = Path("research/d2b/D2B_SHARD_MAP.json")
SAMPLE = Path("research/d2b/D2B_REPLICATION_SAMPLE_SIZE.json")


def _arms(
    n: int,
    *,
    fresh: float,
    description: float,
    reproduced: float,
    source: float,
):
    return (
        [fresh] * n,
        [description] * n,
        [reproduced] * n,
        [source] * n,
    )


def _hashes() -> dict[str, str]:
    return {
        "plan_sha256": aggregator.file_sha256(PLAN),
        "request_plan_sha256": aggregator.file_sha256(REQUEST),
        "cohort_lock_file_sha256": aggregator.file_sha256(COHORT),
        "shard_map_sha256": aggregator.file_sha256(SHARDS),
    }


def _failed_row(index: int) -> dict[str, object]:
    return {
        "status": "failed",
        "pair_index": index,
        "pair_public_id": f"d2b-replication-pair-{index:03d}",
        "failure_class": "synthetic_test_failure",
    }


def _shard_payload(shard_id: int) -> dict[str, object]:
    shard_map = aggregator.load_shard_map(SHARDS)
    start, end = shard_map[shard_id]
    rows = [_failed_row(index) for index in range(start, end + 1)]
    return {
        "schema": "d2b-replication-provider-shard-v0.1",
        "status": "provider_shard_complete_unclassified",
        "classification": None,
        "shard_id": shard_id,
        "start_pair": start,
        "end_pair": end,
        "attempted_pairs": len(rows),
        "complete_pairs": 0,
        "failed_pairs": len(rows),
        "model": runner.MODEL,
        "temperature": runner.TEMPERATURE,
        "cohort_lock": {
            "schema": "d2b-replication-cohort-lock-v0.1",
            "pair_count": runner.PAIR_COUNT,
            "cohort_pairs_sha256": runner.EXPECTED_COHORT_SHA256,
            "all_source_destination_overlaps_zero": True,
            "all_development_evaluation_overlaps_zero": True,
        },
        "pair_records": rows,
        "transport_accounting": {
            "logical_calls_started": 0,
            "logical_calls_completed": 0,
            "logical_call_failures": 0,
            "successful_physical_attempts": 0,
        },
        **_hashes(),
        "production_historical_substrate_enabled": False,
    }


def _write_shards(root: Path, *, missing: set[int] | None = None) -> None:
    missing = missing or set()
    for shard_id in range(18):
        if shard_id in missing:
            continue
        path = root / f"d2b-replication-provider-shard-{shard_id:02d}.json"
        path.write_text(json.dumps(_shard_payload(shard_id), sort_keys=True))


def _wrong_actions(truth: list[str]) -> list[str]:
    index = {action: i for i, action in enumerate(ACTIONS)}
    return [ACTIONS[(index[action] + 1) % len(ACTIONS)] for action in truth]


def _complete_pair(index: int) -> dict[str, object]:
    bundle = runner.case_bundle(index)
    eval_cases = bundle["eval_cases"]
    truth = [case["correct_action"] for case in eval_cases]
    wrong = _wrong_actions(truth)

    def arm(actions: list[str], logical_calls: int) -> dict[str, object]:
        return {
            "development_batch_scores": [],
            "runner_final_score": (
                sum(a == b for a, b in zip(actions, truth, strict=True)) / len(truth)
            ),
            "evaluation_actions": actions,
            "logical_calls": logical_calls,
            "physical_attempts": logical_calls,
            "calls": [],
        }

    return {
        "status": "complete",
        "pair_index": index,
        "pair_public_id": f"d2b-replication-pair-{index:03d}",
        "pair_lock_record": runner.pair_lock_record(index),
        "artifact": {},
        "artifact_audit": {"passed": True},
        "evaluation_case_ids": [case["case_id"] for case in eval_cases],
        "evaluation_truth": truth,
        "arms": {
            "fresh": arm(wrong, 4),
            "description_only": arm(wrong, 9),
            "reproduced": arm(truth, 9),
            "source_developed": arm(truth, 9),
        },
    }


def _canonical_provider(complete_n: int = 330) -> dict[str, object]:
    rows = [
        _complete_pair(index) if index < complete_n else _failed_row(index)
        for index in range(runner.PAIR_COUNT)
    ]
    return {
        "schema": "d2b-replication-provider-output-v0.1",
        "status": "provider_campaign_complete_unclassified",
        "classification": None,
        "model": runner.MODEL,
        "temperature": runner.TEMPERATURE,
        "attempted_pairs": runner.PAIR_COUNT,
        "complete_pairs": complete_n,
        "failed_pairs": runner.PAIR_COUNT - complete_n,
        "cohort_lock": {
            "schema": "d2b-replication-cohort-lock-v0.1",
            "pair_count": runner.PAIR_COUNT,
            "cohort_pairs_sha256": runner.EXPECTED_COHORT_SHA256,
            "all_source_destination_overlaps_zero": True,
            "all_development_evaluation_overlaps_zero": True,
        },
        "pair_records": rows,
        "aggregation_integrity": {
            "passed": True,
            "defects": [],
            "valid_shards": list(range(18)),
            "missing_shards": [],
            "invalid_shards": [],
        },
        "transport_accounting": {},
        **_hashes(),
        "production_historical_substrate_enabled": False,
    }


def _evaluate(provider_path: Path) -> dict[str, Any]:
    return evaluator.evaluate(
        provider_path,
        plan_path=PLAN,
        request_plan_path=REQUEST,
        cohort_lock_path=COHORT,
        shard_map_path=SHARDS,
    )


def test_d2b_cohort_lock_is_exact_and_disjoint():
    result = runner.verify_cohort_lock(COHORT)
    assert result["pair_count"] == 360
    assert result["cohort_pairs_sha256"] == runner.EXPECTED_COHORT_SHA256
    assert result["cohort_pairs_sha256"] == (
        "b4d8f39b9730de6869b6b3c3f9ceb4d16c76214b8eee9437c2bca62e85286b23"
    )
    assert result["all_source_destination_overlaps_zero"] is True
    assert result["all_development_evaluation_overlaps_zero"] is True


def test_d2b_shard_map_covers_all_pairs_once():
    mapping = aggregator.load_shard_map(SHARDS)
    assert len(mapping) == 18
    union = [
        index
        for shard_id in range(18)
        for index in range(mapping[shard_id][0], mapping[shard_id][1] + 1)
    ]
    assert union == list(range(360))
    assert runner.load_shard_range(17, SHARDS) == (340, 359)


def test_request_and_sample_size_contract_are_parent_frozen():
    request = json.loads(REQUEST.read_text())
    sample = json.loads(SAMPLE.read_text())
    assert request["model"] == "glm-5-turbo"
    assert request["temperature"] == 0.8
    assert request["thinking"] == "disabled"
    assert request["pair_count_attempted"] == 360
    assert request["minimum_analyzable_pairs"] == 330
    assert request["provider_shard_count"] == 18
    assert request["pairs_per_provider_shard"] == 20
    assert request["logical_calls_campaign_before_retries"] == 11160
    assert request["confirmatory_same_request_stream_rerun_allowed"] is False
    assert request["historical_substrate_enabled"] is False
    assert sample["P2"]["required_n"] == 328
    assert sample["minimum_analyzable_pairs"] == 330
    assert sample["target_power"] == 0.9
    assert "Inherited unchanged from D2-C2" in sample["planning_principle"]


def test_serial_gatekeeping_s3(monkeypatch):
    monkeypatch.setattr(stats, "BOOTSTRAP_REPS", 100)
    result = stats.evaluate_scores(
        *_arms(330, fresh=0.30, description=0.30, reproduced=0.58, source=0.60)
    )
    assert result["classification"] == "D2-S3"
    assert result["P0"]["gate_pass"] is True
    assert result["P1"]["gate_pass"] is True
    assert result["P2"]["gate_pass"] is True


def test_serial_gatekeeping_s0_s1_s2(monkeypatch):
    monkeypatch.setattr(stats, "BOOTSTRAP_REPS", 10)
    s0 = stats.evaluate_scores(
        *_arms(330, fresh=0.30, description=0.30, reproduced=0.58, source=0.35)
    )
    s1 = stats.evaluate_scores(
        *_arms(330, fresh=0.30, description=0.30, reproduced=0.35, source=0.60)
    )
    s2 = stats.evaluate_scores(
        *_arms(330, fresh=0.30, description=0.30, reproduced=0.52, source=0.60)
    )
    assert s0["classification"] == "D2-S0"
    assert s1["classification"] == "D2-S1"
    assert s2["classification"] == "D2-S2"


def test_minimum_analyzable_n_is_s4():
    result = stats.evaluate_scores(
        *_arms(329, fresh=0.30, description=0.30, reproduced=0.58, source=0.60)
    )
    assert result["classification"] == "D2-S4"
    assert result["analyzable_pairs"] == 329


def test_one_missing_shard_becomes_twenty_failed_attempts(tmp_path):
    _write_shards(tmp_path, missing={7})
    result = aggregator.aggregate(
        tmp_path,
        plan_path=PLAN,
        request_plan_path=REQUEST,
        cohort_lock_path=COHORT,
        shard_map_path=SHARDS,
    )
    assert result["aggregation_integrity"]["passed"] is True
    assert result["aggregation_integrity"]["missing_shards"] == [7]
    missing_rows = result["pair_records"][140:160]
    assert len(missing_rows) == 20
    assert all(row["status"] == "failed" for row in missing_rows)
    assert all(
        row["failure_class"] == "missing_shard_artifact" for row in missing_rows
    )


def test_duplicate_and_drifted_shards_fail_integrity(tmp_path):
    _write_shards(tmp_path)
    duplicate = tmp_path / "d2b-replication-provider-shard-00-copy.json"
    duplicate.write_text(json.dumps(_shard_payload(0), sort_keys=True))
    result = aggregator.aggregate(
        tmp_path,
        plan_path=PLAN,
        request_plan_path=REQUEST,
        cohort_lock_path=COHORT,
        shard_map_path=SHARDS,
    )
    assert result["aggregation_integrity"]["passed"] is False
    assert "shard_0_duplicate_artifacts" in result["aggregation_integrity"]["defects"]

    duplicate.unlink()
    shard = tmp_path / "d2b-replication-provider-shard-01.json"
    data = json.loads(shard.read_text())
    data["model"] = "wrong-model"
    shard.write_text(json.dumps(data, sort_keys=True))
    drift = aggregator.aggregate(
        tmp_path,
        plan_path=PLAN,
        request_plan_path=REQUEST,
        cohort_lock_path=COHORT,
        shard_map_path=SHARDS,
    )
    assert drift["aggregation_integrity"]["passed"] is False
    assert "shard_1:model_drift" in drift["aggregation_integrity"]["defects"]


def test_evaluator_is_deterministic_and_maps_s3_to_d2b_s3(tmp_path, monkeypatch):
    monkeypatch.setattr(stats, "BOOTSTRAP_REPS", 100)
    provider_path = tmp_path / "provider.json"
    provider_path.write_bytes(
        evaluator.canonical_bytes(_canonical_provider(complete_n=330))
    )
    first = _evaluate(provider_path)
    second = _evaluate(provider_path)
    assert evaluator.canonical_bytes(first) == evaluator.canonical_bytes(second)
    assert first["classification"] == "D2-S3"
    assert first["d2b_classification"] == "D2b-S3"
    assert first["integrity"]["passed"] is True
    assert first["analyzable_pairs"] == 330
    assert first["registry_promotion_authorized"] is False
    assert first["production_historical_substrate_enabled"] is False


def test_corrupt_or_preclassified_provider_forces_s4(tmp_path, monkeypatch):
    monkeypatch.setattr(stats, "BOOTSTRAP_REPS", 10)
    provider = _canonical_provider(complete_n=330)
    provider["classification"] = "D2-S3"
    provider_path = tmp_path / "provider.json"
    provider_path.write_bytes(evaluator.canonical_bytes(provider))
    result = _evaluate(provider_path)
    assert result["classification"] == "D2-S4"
    assert result["d2b_classification"] == "D2b-S4"
    assert "provider_must_not_classify" in result["integrity"]["global_defects"]
