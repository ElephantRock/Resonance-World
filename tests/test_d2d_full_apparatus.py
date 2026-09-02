from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import aggregate_d2d_source_acquisition as aggregator  # noqa: E402
import d2d_acquisition_core as core  # noqa: E402
import d2d_acquisition_stats as stats  # noqa: E402
import evaluate_d2d_source_acquisition as evaluator  # noqa: E402
import materialize_d2d_source_acquisition as materializer  # noqa: E402
import run_d2d_source_acquisition as runner  # noqa: E402

COHORT = Path("research/d2d/d2d-source-acquisition-cohort-lock.json")
SHARDS = Path("research/d2d/D2D_SHARD_MAP.json")


def _wrong_actions(truth: list[str]) -> list[str]:
    indices = {action: i for i, action in enumerate(core.ACTIONS)}
    return [core.ACTIONS[(indices[action] + 1) % 4] for action in truth]


def _arm(actions: list[str], truth: list[str], development_cases: int) -> dict[str, Any]:
    return {
        "development_cases": development_cases,
        "runner_final_score": sum(
            action == expected
            for action, expected in zip(actions, truth, strict=True)
        )
        / len(truth),
        "evaluation_actions": actions,
    }


def _complete_pair(index: int, *, positive_control_40_fail: bool = False) -> dict[str, Any]:
    bundle = materializer.case_bundle(index)
    truth = [case["correct_action"] for case in bundle["evaluation_cases"]]
    wrong = _wrong_actions(truth)
    schema_id = bundle["schema_id"]
    d40 = (
        wrong
        if positive_control_40_fail and schema_id == "threshold_at_4"
        else truth
    )
    development = bundle["development_cases"]
    return {
        "status": "complete",
        "pair_index": index,
        "schema_id": schema_id,
        "schema_pair_index": bundle["local_pair_index"],
        "pair_public_id": f"d2d-{schema_id}-pair-{bundle['local_pair_index']:03d}",
        "pair_lock_record": materializer.pair_lock_record(index),
        "development_prefix_case_ids": {
            "developed_40": [case["case_id"] for case in development[:40]],
            "developed_80": [case["case_id"] for case in development[:80]],
            "developed_160": [case["case_id"] for case in development],
        },
        "evaluation_case_ids": [case["case_id"] for case in bundle["evaluation_cases"]],
        "evaluation_truth": truth,
        "arms": {
            "fresh": _arm(wrong, truth, 0),
            "developed_40": _arm(d40, truth, 40),
            "developed_80": _arm(truth, truth, 80),
            "developed_160": _arm(truth, truth, 160),
            "oracle_instruction": {
                "status": "complete_diagnostic",
                **_arm(truth, truth, 0),
            },
        },
    }


def _failed_pair(index: int) -> dict[str, Any]:
    schema_id, local = core.schema_and_local_index(index)
    return {
        "status": "failed",
        "pair_index": index,
        "schema_id": schema_id,
        "schema_pair_index": local,
        "pair_public_id": f"d2d-{schema_id}-pair-{local:03d}",
        "failure_class": "synthetic_test_failure",
    }


def _provider(
    complete_per_schema: int = 88,
    *,
    positive_control_40_fail: bool = False,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for index in range(384):
        _, local = core.schema_and_local_index(index)
        rows.append(
            _complete_pair(
                index,
                positive_control_40_fail=positive_control_40_fail,
            )
            if local < complete_per_schema
            else _failed_pair(index)
        )
    complete = sum(row["status"] == "complete" for row in rows)
    return {
        "schema": "d2d-source-acquisition-provider-output-v0.1",
        "status": "provider_campaign_complete_unclassified",
        "classification": None,
        "attempted_pairs": 384,
        "complete_pairs": complete,
        "failed_pairs": 384 - complete,
        "cohort_pairs_sha256": runner.EXPECTED_COHORT_SHA256,
        "pair_records": rows,
        "production_historical_substrate_enabled": False,
    }


def test_deterministic_cohort_hash_and_nested_prefixes() -> None:
    lock = materializer.build_cohort_lock()
    assert (
        lock["cohort_pairs_sha256"]
        == "a9c2077d4e76825d9ef1f6b245caf0231f5a4a3b1dc00cc0032793add8f9ea19"
    )
    assert lock["all_development_prefixes_nested"] is True
    assert lock["all_development_evaluation_overlaps_zero"] is True
    bundle = materializer.case_bundle(0)
    development = bundle["development_cases"]
    assert len(development[:40]) == 40
    assert development[:40] == development[:80][:40]
    assert development[:80] == development[:160][:80]
    assert not (
        core.features_set(development)
        & core.features_set(bundle["evaluation_cases"])
    )


def test_materialization_files_and_shard_safety() -> None:
    assert materializer.canonical_bytes(materializer.build_cohort_lock()) == COHORT.read_bytes()
    assert materializer.canonical_bytes(materializer.build_shard_map()) == SHARDS.read_bytes()
    mapping = aggregator.load_shard_map(SHARDS)
    assert mapping[0] == (0, 15, "threshold_at_4")
    assert mapping[23] == (368, 383, "pairwise_order")
    shard_map = json.loads(SHARDS.read_text())
    assert shard_map["missing_whole_shard_max_analyzable_in_affected_schema"] == 80
    assert shard_map["favorable_result_possible_with_missing_whole_shard"] is False


def test_primary_margin_is_strict() -> None:
    assert stats.paired_margin_test([0.30] * 88)["gate_pass"] is True
    assert stats.paired_margin_test([0.10] * 88)["gate_pass"] is False


def test_evaluator_selects_40_budget_when_all_calibration_gates_pass(
    monkeypatch,
) -> None:
    monkeypatch.setattr(stats, "BOOTSTRAP_REPS", 5)
    result = evaluator.evaluate(_provider())
    assert result["classification"] == "D2d-A5"
    assert result["common_confirmed_acquisition_budget"] == 40
    assert result["positive_control"]["continuity_pass"] is True
    assert result["registry_promotion_authorized"] is False
    assert result["production_historical_substrate_enabled"] is False


def test_positive_control_40_failure_prevents_envelope_interpretation(
    monkeypatch,
) -> None:
    monkeypatch.setattr(stats, "BOOTSTRAP_REPS", 5)
    result = evaluator.evaluate(_provider(positive_control_40_fail=True))
    assert result["classification"] == "D2d-A1"
    assert result["common_confirmed_acquisition_budget"] is None
    assert result["positive_control"]["continuity_pass"] is False


def test_missing_provider_shards_are_registered_failures(tmp_path: Path) -> None:
    output = aggregator.aggregate(tmp_path, shard_map_path=SHARDS)
    assert output["attempted_pairs"] == 384
    assert output["complete_pairs"] == 0
    assert output["failed_pairs"] == 384
    assert all(row["status"] == "missing" for row in output["shard_inputs"])


def test_execution_marker_absent_before_separate_authorization() -> None:
    assert not Path("research/d2d/RUN_D2D_SOURCE_ACQUISITION").exists()
