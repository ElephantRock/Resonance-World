"""Offline tests for the institutional resilience & curation qualification."""

from __future__ import annotations

from pathlib import Path

import pytest

import scripts.run_institutional_resilience_qualification as imrc


def test_grid_shape_and_determinism() -> None:
    chain_a = imrc.run_chain(0.15, 0.10, 4, 0)
    chain_b = imrc.run_chain(0.15, 0.10, 4, 0)
    assert chain_a == chain_b
    assert len(chain_a["per_generation"]["CURATED"]) == imrc.GENERATIONS


def test_generation1_identical_across_curated_uncurated() -> None:
    # by construction pools are identical in generation 1
    chain = imrc.run_chain(0.35, 0.25, 12, 3)
    g0_c = chain["per_generation"]["CURATED"][0]
    g0_u = chain["per_generation"]["UNCURATED"][0]
    assert g0_c == g0_u


def test_evaluator_validity_probes() -> None:
    oracle = imrc.run_chain(0.15, 0.10, 4, 0, member_oracle=True)
    corrupt = imrc.run_chain(0.15, 0.10, 4, 0, member_corrupt=True)
    assert all(
        v == 1.0 for gen in oracle["per_generation"].values() for v in gen
    )
    assert all(
        v == 0.0 for gen in corrupt["per_generation"].values() for v in gen
    )


def test_all_three_outcome_families_exist(tmp_path: Path) -> None:
    combos = {}
    for s in imrc.STALENESS:
        for c in imrc.CONTRADICTION:
            for sat in imrc.SATURATION:
                deltas = [
                    imrc.run_chain(s, c, sat, seed)["delta_resilience_gens2_5"]
                    for seed in range(imrc.SEEDS)
                ]
                import statistics
                mean = statistics.mean(deltas)
                combos[(s, c, sat)] = imrc.classify(mean)
    classes = set(combos.values())
    assert {"curation_wins", "curation_harms", "tie"} <= classes


def test_curation_cost_reported() -> None:
    chain = imrc.run_chain(0.35, 0.25, 12, 2)
    assert "retired_records" in chain["curation_cost"]
    assert chain["curation_cost"]["retired_records"] >= 0
    assert chain["curation_cost"]["policy_passes"] == imrc.GENERATIONS


def test_reset_and_frozen_controls_present() -> None:
    chain = imrc.run_chain(0.15, 0.10, 4, 1)
    assert "RESET" in chain["per_generation"]
    assert "FROZEN" in chain["per_generation"]


def test_committed_report_passes() -> None:
    import json
    report = json.loads(
        (
            Path("research/c3r_g2/evidence_g2_qualification_20261028")
            / "imrc-qualification-report.json"
        ).read_text(encoding="utf-8")
    )
    assert report["evaluator_validity"]["valid"] is True
    assert report["no_forced_sign"] is True
    assert report["chains"] == 135
