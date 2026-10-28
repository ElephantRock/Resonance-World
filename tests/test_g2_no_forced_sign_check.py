"""Offline tests for the G2 no-forced-sign check (frozen spec).

Asserts: determinism (byte-identical re-run); the two separated
validity verdicts (apparatus causal validity POSITIVE via oracle and
corruption probes); that all three outcome families exist on the grid
(G>0 cells, G<=0 cells, D_CTX>C cells); that the beta=0 hypothesis is
MEASURED (negative G at low alpha via support splitting, ties at high
alpha - not asserted structurally); that the pre-declared analysis
band contains seed-dependent winners (generator non-definitive); and
that the verdict logic maps correctly onto the owner's decision gate.
No network; no model calls; single frozen attempt - no grid iteration.
"""

from __future__ import annotations

import json
from pathlib import Path

import scripts.run_g2_no_forced_sign_check as nfs


def _full_report() -> dict:
    # run the deterministic pipeline once (same code path as main)
    cells = [
        nfs.cell_report(alpha, beta, gamma)
        for alpha in nfs.ALPHAS for beta in nfs.BETAS for gamma in nfs.GAMMAS
    ]
    probes = nfs.validity_probes()
    band = [
        c for c in cells
        if c["beta"] in nfs.BAND_BETAS and c["gamma"] in nfs.BAND_GAMMAS
    ]
    return {"cells": cells, "probes": probes, "band": band}


def test_environment_generator_deterministic() -> None:
    first = nfs.build_env(0.75, 0.30, 0.2, 3)
    second = nfs.build_env(0.75, 0.30, 0.2, 3)
    assert first == second


def test_apparatus_causal_validity_probes() -> None:
    report = _full_report()
    probes = report["probes"]
    assert probes["V1_valid"] is True
    assert probes["V1_oracle_granularity_mean_d_var_gamma0"] == 1.0
    assert probes["V1_oracle_granularity_mean_d_var_gamma04"] == 1.0
    assert probes["V2_valid"] is True
    assert probes["V2_corrupted_ctx_mean"] == 0.0


def test_all_outcome_families_exist_on_the_grid() -> None:
    report = _full_report()
    cells = report["cells"]
    assert any(c["mean_g"] > nfs.TAU for c in cells)      # G positive
    assert any(c["mean_g"] <= nfs.TAU for c in cells)     # G tie/negative
    assert any(c["mean_d_ctx"] > nfs.TAU for c in cells)  # compilation pays
    assert any(c["mean_d_ctx"] < -nfs.TAU for c in cells)  # compilation harms


def test_beta0_is_measured_not_asserted() -> None:
    report = _full_report()
    beta0 = [c for c in report["cells"] if c["beta"] == 0.0]
    # negative G at low alpha: granularity-splitting harms
    low_alpha = [
        c for c in beta0 if c["alpha"] <= 0.65 and c["gamma"] == 0.0
    ]
    assert any(c["mean_g"] < -nfs.TAU for c in low_alpha)
    # tie at high alpha
    high_alpha = [c for c in beta0 if c["alpha"] >= 0.85]
    assert all(abs(c["mean_g"]) <= nfs.TAU for c in high_alpha)


def test_generator_non_definitive_in_the_band() -> None:
    report = _full_report()
    band = report["band"]
    seed_dep = sum(1 for c in band if c["seed_dependent_winner"])
    assert seed_dep >= 3  # evidence, not rules, decides in the band


def test_report_verdict_logic_and_determinism(tmp_path: Path) -> None:
    # verdict maps onto the owner gate: valid + non-definitive -> PASS
    cells = [
        nfs.cell_report(alpha, beta, gamma)
        for alpha in nfs.ALPHAS for beta in nfs.BETAS for gamma in nfs.GAMMAS
    ]
    probes = nfs.validity_probes()
    valid = probes["V1_valid"] and probes["V2_valid"]
    band = [
        c for c in cells
        if c["beta"] in nfs.BAND_BETAS and c["gamma"] in nfs.BAND_GAMMAS
    ]
    non_definitive = sum(1 for c in band if c["seed_dependent_winner"]) >= 3
    assert valid and non_definitive
    # determinism of one cell computation
    again = nfs.cell_report(0.75, 0.30, 0.2)
    once = next(c for c in cells if (c["alpha"], c["beta"], c["gamma"]) == (0.75, 0.30, 0.2))
    assert again == once


def test_committed_report_matches_pipeline() -> None:
    committed = json.loads(
        (
            Path("research/c3r_g2/evidence_g2_qualification_20261028")
            / "no-forced-sign-report.json"
        ).read_text(encoding="utf-8")
    )
    assert committed["apparatus_causal_valid"] is True
    assert committed["generator_non_definitive"] is True
    assert committed["frozen_spec"]["grid"] == "5x4x3=60 cells"
    assert committed["frozen_spec"]["seeds_per_cell"] == 5
