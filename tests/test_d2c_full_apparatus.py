from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import aggregate_d2c_schema_generalization as aggregator  # noqa: E402
import d2c_schema_core as core  # noqa: E402
import d2c_schema_stats as stats  # noqa: E402
import evaluate_d2c_schema_generalization as evaluator  # noqa: E402
import run_d2c_schema_generalization as runner  # noqa: E402

PLAN = Path("research/d2c/PLAN.md")
REQUEST = Path("research/d2c/D2C_REQUEST_PLAN.json")
SCHEMA_SUITE = Path("research/d2c/D2C_SCHEMA_SUITE.json")
SAMPLE = Path("research/d2c/D2C_SAMPLE_SIZE.json")
COHORT = Path("research/d2c/d2c-schema-cohort-lock.json")
SHARDS = Path("research/d2c/D2C_SHARD_MAP.json")


def _hashes() -> dict[str, str]:
    return {
        "plan_sha256": aggregator.file_sha256(PLAN),
        "request_plan_sha256": aggregator.file_sha256(REQUEST),
        "schema_suite_sha256": aggregator.file_sha256(SCHEMA_SUITE),
        "sample_size_sha256": aggregator.file_sha256(SAMPLE),
        "cohort_lock_file_sha256": aggregator.file_sha256(COHORT),
        "shard_map_sha256": aggregator.file_sha256(SHARDS),
    }


def _failed_row(index: int) -> dict[str, object]:
    schema_id, local = core.schema_and_local_index(index)
    return {
        "status": "failed",
        "pair_index": index,
        "schema_id": schema_id,
        "schema_pair_index": local,
        "pair_public_id": f"d2c-{schema_id}-pair-{local:03d}",
        "failure_class": "synthetic_test_failure",
    }


def _wrong_actions(truth: list[str]) -> list[str]:
    ix = {action: i for i, action in enumerate(core.ACTIONS)}
    return [core.ACTIONS[(ix[action] + 1) % 4] for action in truth]


def _complete_pair(index: int) -> dict[str, object]:
    bundle = runner.case_bundle(index)
    truth = [case["correct_action"] for case in bundle["eval_cases"]]
    wrong = _wrong_actions(truth)
    schema_id, local = core.schema_and_local_index(index)

    def arm(actions: list[str], calls: int) -> dict[str, object]:
        return {
            "development_batch_scores": [],
            "runner_final_score": sum(a == b for a, b in zip(actions, truth, strict=True))
            / len(truth),
            "evaluation_actions": actions,
            "logical_calls": calls,
            "physical_attempts": calls,
            "calls": [],
        }

    return {
        "status": "complete",
        "pair_index": index,
        "schema_id": schema_id,
        "schema_pair_index": local,
        "pair_public_id": f"d2c-{schema_id}-pair-{local:03d}",
        "pair_lock_record": runner.pair_lock_record(index),
        "artifact": {},
        "artifact_audit": {"passed": True},
        "evaluation_case_ids": [case["case_id"] for case in bundle["eval_cases"]],
        "evaluation_truth": truth,
        "arms": {
            "fresh": arm(wrong, 4),
            "description_only": arm(wrong, 9),
            "reproduced": arm(truth, 9),
            "source_developed": arm(truth, 9),
        },
    }


def _provider(complete_by_schema: dict[str, int] | None = None) -> dict[str, Any]:
    complete_by_schema = complete_by_schema or {schema_id: 165 for schema_id in core.SCHEMA_ORDER}
    rows = []
    for index in range(540):
        schema_id, local = core.schema_and_local_index(index)
        rows.append(
            _complete_pair(index) if local < complete_by_schema[schema_id] else _failed_row(index)
        )
    complete = sum(row["status"] == "complete" for row in rows)
    return {
        "schema": "d2c-schema-generalization-provider-output-v0.1",
        "status": "provider_campaign_complete_unclassified",
        "classification": None,
        "model": "glm-5-turbo",
        "temperature": 0.8,
        "attempted_pairs": 540,
        "complete_pairs": complete,
        "failed_pairs": 540 - complete,
        "schema_counts": {},
        "cohort_lock": {
            "schema": "d2c-schema-generalization-cohort-lock-v0.1",
            "pair_count": 540,
            "pairs_per_schema": 180,
            "cohort_pairs_sha256": runner.EXPECTED_COHORT_SHA256,
            "all_source_destination_overlaps_zero": True,
            "all_development_evaluation_overlaps_zero": True,
        },
        "pair_records": rows,
        "aggregation_integrity": {
            "passed": True,
            "defects": [],
            "valid_shards": list(range(27)),
            "missing_shards": [],
            "invalid_shards": [],
        },
        "transport_accounting": {},
        **_hashes(),
        "production_historical_substrate_enabled": False,
    }


def _evaluate(path: Path) -> dict[str, Any]:
    return evaluator.evaluate(
        path,
        plan_path=PLAN,
        request_plan_path=REQUEST,
        schema_suite_path=SCHEMA_SUITE,
        sample_size_path=SAMPLE,
        cohort_lock_path=COHORT,
        shard_map_path=SHARDS,
    )


def test_cohort_hash_and_runner_contract_are_exact():
    summary = runner.verify_cohort_lock(COHORT)
    assert (
        summary["cohort_pairs_sha256"]
        == "559a4420a1d592d85fa350d087a8d4b945f4bf882a683c660a77cf9fdb6b9c04"
    )
    assert summary["pair_count"] == 540
    assert runner.load_shard_range(0, SHARDS) == (0, 19, "parity_pair")
    assert runner.load_shard_range(26, SHARDS) == (520, 539, "pairwise_order")


def test_artifact_is_schema_public_but_private_policy_safe():
    bundle = runner.case_bundle(0)
    artifact = runner.build_artifact(0, "parity_pair", 0.5)
    text = json.dumps(artifact, sort_keys=True)
    assert "parity_pair" in text
    assert bundle["policy"].truth_token not in text
    assert str(bundle["pair_seed"]) not in text
    assert all(case["case_id"] not in text for case in bundle["source_cases"])


def test_per_schema_stats_pass_and_fail(monkeypatch):
    monkeypatch.setattr(stats, "BOOTSTRAP_REPS", 20)
    n = 165
    passed = stats.evaluate_schema_scores([0.2] * n, [0.2] * n, [0.6] * n, [0.6] * n)
    failed_p0 = stats.evaluate_schema_scores([0.5] * n, [0.2] * n, [0.6] * n, [0.55] * n)
    assert passed["all_gates_pass"] is True
    assert failed_p0["P0"]["gate_pass"] is False
    assert (
        stats.evaluate_schema_scores([0.2] * 164, [0.2] * 164, [0.6] * 164, [0.6] * 164)[
            "minimum_n_pass"
        ]
        is False
    )


def test_program_classifier_requires_all_three_schemas():
    base = {
        "minimum_n_pass": True,
        "P0": {"gate_pass": True},
        "P1": {"gate_pass": True},
        "P2": {"gate_pass": True},
    }
    all_pass = {schema_id: dict(base) for schema_id in core.SCHEMA_ORDER}
    assert evaluator._classify(all_pass, True)[0] == "D2c-S4"
    p0 = {k: dict(v) for k, v in all_pass.items()}
    p0["parity_pair"] = {**base, "P0": {"gate_pass": False}}
    assert evaluator._classify(p0, True)[0] == "D2c-S1"
    p1 = {k: dict(v) for k, v in all_pass.items()}
    p1["interval_pair"] = {**base, "P1": {"gate_pass": False}}
    assert evaluator._classify(p1, True)[0] == "D2c-S2"
    p2 = {k: dict(v) for k, v in all_pass.items()}
    p2["pairwise_order"] = {**base, "P2": {"gate_pass": False}}
    assert evaluator._classify(p2, True)[0] == "D2c-S3"
    assert evaluator._classify(all_pass, False)[0] == "D2c-S0"


def test_evaluator_s4_with_165_analyzable_each(monkeypatch, tmp_path):
    monkeypatch.setattr(stats, "BOOTSTRAP_REPS", 10)
    path = tmp_path / "provider.json"
    path.write_text(json.dumps(_provider(), sort_keys=True))
    result = _evaluate(path)
    assert result["classification"] == "D2c-S4"
    assert result["analyzable_pairs_by_schema"] == {
        schema_id: 165 for schema_id in core.SCHEMA_ORDER
    }
    assert result["registry_promotion_authorized"] is False
    assert result["production_historical_substrate_enabled"] is False


def test_one_schema_below_minimum_forces_s0(monkeypatch, tmp_path):
    monkeypatch.setattr(stats, "BOOTSTRAP_REPS", 5)
    path = tmp_path / "provider.json"
    path.write_text(
        json.dumps(
            _provider({"parity_pair": 164, "interval_pair": 165, "pairwise_order": 165}),
            sort_keys=True,
        )
    )
    result = _evaluate(path)
    assert result["classification"] == "D2c-S0"
    assert result["analyzable_pairs_by_schema"]["parity_pair"] == 164


def test_missing_full_shard_leaves_schema_max_160(tmp_path):
    mapping = aggregator.load_shard_map(SHARDS)
    assert mapping[0] == (0, 19, "parity_pair")
    # No shard files: aggregator must represent all 540 attempted pairs as registered failures.
    output = aggregator.aggregate(
        tmp_path,
        plan_path=PLAN,
        request_plan_path=REQUEST,
        schema_suite_path=SCHEMA_SUITE,
        sample_size_path=SAMPLE,
        cohort_lock_path=COHORT,
        shard_map_path=SHARDS,
    )
    assert output["attempted_pairs"] == 540
    assert output["complete_pairs"] == 0
    assert output["failed_pairs"] == 540
    assert output["aggregation_integrity"]["missing_shards"] == list(range(27))


def test_execution_marker_absent_before_explicit_authorization():
    assert not Path("research/d2c/RUN_D2C_SCHEMA_GENERALIZATION").exists()
