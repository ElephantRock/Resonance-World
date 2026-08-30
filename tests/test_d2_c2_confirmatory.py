from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import aggregate_d2_c2_confirmatory as aggregator  # noqa: E402
import d2_c2_confirmatory_sample_size as sample_size  # noqa: E402
import d2_c2_confirmatory_stats as stats  # noqa: E402
import evaluate_d2_c2_confirmatory as evaluator  # noqa: E402
import run_d2_c2_confirmatory as runner  # noqa: E402
from d2_calibration_r2_core import ACTIONS  # noqa: E402


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
        "plan_sha256": aggregator.file_sha256(
            Path("research/d2/D2_C2_CONFIRMATORY_PLAN.md")
        ),
        "request_plan_sha256": aggregator.file_sha256(
            Path("research/d2/D2_C2_CONFIRMATORY_REQUEST_PLAN.json")
        ),
        "cohort_lock_file_sha256": aggregator.file_sha256(
            Path("research/d2/d2-c2-confirmatory-cohort-lock.json")
        ),
        "shard_map_sha256": aggregator.file_sha256(
            Path("research/d2/D2_C2_SHARD_MAP.json")
        ),
    }


def _failed_row(index: int) -> dict[str, object]:
    return {
        "status": "failed",
        "pair_index": index,
        "pair_public_id": f"d2-c2-confirmatory-pair-{index:03d}",
        "failure_class": "synthetic_test_failure",
    }


def _shard_payload(shard_id: int) -> dict[str, object]:
    shard_map = aggregator.load_shard_map(
        Path("research/d2/D2_C2_SHARD_MAP.json")
    )
    start, end = shard_map[shard_id]
    rows = [_failed_row(index) for index in range(start, end + 1)]
    return {
        "schema": "d2-c2-confirmatory-provider-shard-v0.1",
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
            "schema": "d2-c2-confirmatory-cohort-lock-v0.1",
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
        path = root / f"d2-c2-confirmatory-provider-shard-{shard_id:02d}.json"
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
                sum(a == b for a, b in zip(actions, truth, strict=True))
                / len(truth)
            ),
            "evaluation_actions": actions,
            "logical_calls": logical_calls,
            "physical_attempts": logical_calls,
            "calls": [],
        }

    return {
        "status": "complete",
        "pair_index": index,
        "pair_public_id": f"d2-c2-confirmatory-pair-{index:03d}",
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
        "schema": "d2-c2-confirmatory-provider-output-v0.1",
        "status": "provider_campaign_complete_unclassified",
        "classification": None,
        "model": runner.MODEL,
        "temperature": runner.TEMPERATURE,
        "attempted_pairs": runner.PAIR_COUNT,
        "complete_pairs": complete_n,
        "failed_pairs": runner.PAIR_COUNT - complete_n,
        "cohort_lock": {
            "schema": "d2-c2-confirmatory-cohort-lock-v0.1",
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


def test_c2_cohort_lock_is_exact_and_disjoint():
    result = runner.verify_cohort_lock(
        Path("research/d2/d2-c2-confirmatory-cohort-lock.json")
    )
    assert result["pair_count"] == 360
    assert result["cohort_pairs_sha256"] == runner.EXPECTED_COHORT_SHA256
    assert result["all_source_destination_overlaps_zero"] is True
    assert result["all_development_evaluation_overlaps_zero"] is True


def test_c2_shard_map_covers_all_pairs_once():
    mapping = aggregator.load_shard_map(
        Path("research/d2/D2_C2_SHARD_MAP.json")
    )
    assert len(mapping) == 18
    union = [
        index
        for shard_id in range(18)
        for index in range(mapping[shard_id][0], mapping[shard_id][1] + 1)
    ]
    assert union == list(range(360))
    assert runner.load_shard_range(
        17, Path("research/d2/D2_C2_SHARD_MAP.json")
    ) == (340, 359)


def test_sample_size_record_matches_script():
    committed = json.loads(
        Path("research/d2/D2_C2_CONFIRMATORY_SAMPLE_SIZE.json").read_text()
    )
    assert sample_size.report() == committed
    assert committed["P2"]["required_n"] == 328
    assert committed["minimum_analyzable_pairs"] == 330


def test_serial_gatekeeping_s3(monkeypatch):
    monkeypatch.setattr(stats, "BOOTSTRAP_REPS", 100)
    arms = _arms(
        330,
        fresh=0.30,
        description=0.30,
        reproduced=0.58,
        source=0.60,
    )
    result = stats.evaluate_scores(*arms)
    assert result["classification"] == "D2-S3"
    assert result["P0"]["gate_pass"] is True
    assert result["P1"]["gate_pass"] is True
    assert result["P2"]["gate_pass"] is True


def test_serial_gatekeeping_s0(monkeypatch):
    monkeypatch.setattr(stats, "BOOTSTRAP_REPS", 10)
    arms = _arms(330, fresh=0.30, description=0.30, reproduced=0.58, source=0.35)
    result = stats.evaluate_scores(*arms)
    assert result["classification"] == "D2-S0"
    assert result["P1"]["gate_entered"] is False


def test_serial_gatekeeping_s1(monkeypatch):
    monkeypatch.setattr(stats, "BOOTSTRAP_REPS", 10)
    arms = _arms(330, fresh=0.30, description=0.30, reproduced=0.35, source=0.60)
    result = stats.evaluate_scores(*arms)
    assert result["classification"] == "D2-S1"
    assert result["P2"]["gate_entered"] is False


def test_serial_gatekeeping_s2(monkeypatch):
    monkeypatch.setattr(stats, "BOOTSTRAP_REPS", 10)
    arms = _arms(330, fresh=0.30, description=0.30, reproduced=0.52, source=0.60)
    result = stats.evaluate_scores(*arms)
    assert result["classification"] == "D2-S2"


def test_minimum_analyzable_n_is_s4():
    arms = _arms(329, fresh=0.30, description=0.30, reproduced=0.58, source=0.60)
    result = stats.evaluate_scores(*arms)
    assert result["classification"] == "D2-S4"
    assert result["analyzable_pairs"] == 329


def test_one_missing_shard_becomes_twenty_failed_attempts(tmp_path):
    _write_shards(tmp_path, missing={7})
    result = aggregator.aggregate(
        tmp_path,
        plan_path=Path("research/d2/D2_C2_CONFIRMATORY_PLAN.md"),
        request_plan_path=Path(
            "research/d2/D2_C2_CONFIRMATORY_REQUEST_PLAN.json"
        ),
        cohort_lock_path=Path(
            "research/d2/d2-c2-confirmatory-cohort-lock.json"
        ),
        shard_map_path=Path("research/d2/D2_C2_SHARD_MAP.json"),
    )
    assert result["aggregation_integrity"]["passed"] is True
    assert result["aggregation_integrity"]["missing_shards"] == [7]
    missing_rows = result["pair_records"][140:160]
    assert len(missing_rows) == 20
    assert all(row["status"] == "failed" for row in missing_rows)
    assert all(
        row["failure_class"] == "missing_shard_artifact"
        for row in missing_rows
    )


def test_two_missing_shards_cannot_exceed_320_complete(tmp_path):
    _write_shards(tmp_path, missing={7, 8})
    result = aggregator.aggregate(
        tmp_path,
        plan_path=Path("research/d2/D2_C2_CONFIRMATORY_PLAN.md"),
        request_plan_path=Path(
            "research/d2/D2_C2_CONFIRMATORY_REQUEST_PLAN.json"
        ),
        cohort_lock_path=Path(
            "research/d2/d2-c2-confirmatory-cohort-lock.json"
        ),
        shard_map_path=Path("research/d2/D2_C2_SHARD_MAP.json"),
    )
    assert len(result["aggregation_integrity"]["missing_shards"]) == 2
    assert result["complete_pairs"] <= 320


def test_duplicate_shard_artifact_fails_aggregation_integrity(tmp_path):
    _write_shards(tmp_path)
    duplicate = tmp_path / "d2-c2-confirmatory-provider-shard-00-copy.json"
    duplicate.write_text(json.dumps(_shard_payload(0), sort_keys=True))
    result = aggregator.aggregate(
        tmp_path,
        plan_path=Path("research/d2/D2_C2_CONFIRMATORY_PLAN.md"),
        request_plan_path=Path(
            "research/d2/D2_C2_CONFIRMATORY_REQUEST_PLAN.json"
        ),
        cohort_lock_path=Path(
            "research/d2/d2-c2-confirmatory-cohort-lock.json"
        ),
        shard_map_path=Path("research/d2/D2_C2_SHARD_MAP.json"),
    )
    assert result["aggregation_integrity"]["passed"] is False
    assert "shard_0_duplicate_artifacts" in result["aggregation_integrity"]["defects"]


def test_evaluator_is_deterministic_and_classifies_s3(tmp_path, monkeypatch):
    monkeypatch.setattr(stats, "BOOTSTRAP_REPS", 100)
    provider_path = tmp_path / "provider.json"
    provider_path.write_bytes(
        evaluator.canonical_bytes(_canonical_provider(complete_n=330))
    )
    kwargs = {
        "plan_path": Path("research/d2/D2_C2_CONFIRMATORY_PLAN.md"),
        "request_plan_path": Path(
            "research/d2/D2_C2_CONFIRMATORY_REQUEST_PLAN.json"
        ),
        "cohort_lock_path": Path(
            "research/d2/d2-c2-confirmatory-cohort-lock.json"
        ),
        "shard_map_path": Path("research/d2/D2_C2_SHARD_MAP.json"),
    }
    first = evaluator.evaluate(provider_path, **kwargs)
    second = evaluator.evaluate(provider_path, **kwargs)
    assert evaluator.canonical_bytes(first) == evaluator.canonical_bytes(second)
    assert first["classification"] == "D2-S3"
    assert first["integrity"]["passed"] is True
    assert first["analyzable_pairs"] == 330


def test_corrupt_aggregation_forces_s4(tmp_path, monkeypatch):
    monkeypatch.setattr(stats, "BOOTSTRAP_REPS", 10)
    provider = _canonical_provider(complete_n=330)
    provider["aggregation_integrity"]["passed"] = False
    provider["aggregation_integrity"]["defects"] = ["synthetic_corruption"]
    provider_path = tmp_path / "provider.json"
    provider_path.write_bytes(evaluator.canonical_bytes(provider))
    result = evaluator.evaluate(
        provider_path,
        plan_path=Path("research/d2/D2_C2_CONFIRMATORY_PLAN.md"),
        request_plan_path=Path(
            "research/d2/D2_C2_CONFIRMATORY_REQUEST_PLAN.json"
        ),
        cohort_lock_path=Path(
            "research/d2/d2-c2-confirmatory-cohort-lock.json"
        ),
        shard_map_path=Path("research/d2/D2_C2_SHARD_MAP.json"),
    )
    assert result["classification"] == "D2-S4"
    assert "aggregation_integrity" in result["integrity"]["global_defects"]
