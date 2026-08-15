from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import d2_confirmatory_stats as stats  # noqa: E402
import run_d2_confirmatory as runner  # noqa: E402


def _arms(n: int, *, fresh: float, description: float, reproduced: float, source: float):
    return (
        [fresh] * n,
        [description] * n,
        [reproduced] * n,
        [source] * n,
    )


def test_confirmatory_cohort_lock_is_exact_and_disjoint():
    lock_path = Path("research/d2/d2-confirmatory-cohort-lock.json")
    result = runner.verify_cohort_lock(lock_path)
    assert result["pair_count"] == 360
    assert result["cohort_pairs_sha256"] == runner.EXPECTED_COHORT_SHA256
    assert result["all_source_destination_overlaps_zero"] is True
    assert result["all_development_evaluation_overlaps_zero"] is True


def test_serial_gatekeeping_s3(monkeypatch):
    monkeypatch.setattr(stats, "BOOTSTRAP_REPS", 100)
    fresh, description, reproduced, source = _arms(
        330,
        fresh=0.30,
        description=0.30,
        reproduced=0.58,
        source=0.60,
    )
    result = stats.evaluate_scores(fresh, description, reproduced, source)
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
    assert result["P2"]["gate_entered"] is False


def test_serial_gatekeeping_s1(monkeypatch):
    monkeypatch.setattr(stats, "BOOTSTRAP_REPS", 10)
    arms = _arms(330, fresh=0.30, description=0.30, reproduced=0.35, source=0.60)
    result = stats.evaluate_scores(*arms)
    assert result["classification"] == "D2-S1"
    assert result["P0"]["gate_pass"] is True
    assert result["P1"]["gate_pass"] is False
    assert result["P2"]["gate_entered"] is False


def test_serial_gatekeeping_s2(monkeypatch):
    monkeypatch.setattr(stats, "BOOTSTRAP_REPS", 10)
    arms = _arms(330, fresh=0.30, description=0.30, reproduced=0.52, source=0.60)
    result = stats.evaluate_scores(*arms)
    assert result["classification"] == "D2-S2"
    assert result["P0"]["gate_pass"] is True
    assert result["P1"]["gate_pass"] is True
    assert result["P2"]["gate_pass"] is False


def test_minimum_analyzable_n_is_s4():
    arms = _arms(329, fresh=0.30, description=0.30, reproduced=0.58, source=0.60)
    result = stats.evaluate_scores(*arms)
    assert result["classification"] == "D2-S4"
    assert result["analyzable_pairs"] == 329


def test_confirmatory_request_contract_is_fixed():
    assert runner.PAIR_COUNT == 360
    assert runner.SOURCE_DEV_COUNT == 40
    assert runner.DEST_DEV_COUNT == 40
    assert runner.EVAL_COUNT == 32
    assert runner.MODEL == "glm-5-turbo"
    assert runner.TEMPERATURE == 0.8
    assert stats.MIN_ANALYZABLE == 330
    assert stats.P0_SESOI == 0.10
    assert stats.P1_SESOI == 0.10
    assert stats.FIDELITY_FRACTION == 0.90
