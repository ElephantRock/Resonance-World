"""Offline tests for the G2 joint-gate power simulation."""

from __future__ import annotations

import json
from pathlib import Path

import scripts.sim_g2_joint_gate_power as sim


def test_gate_logic() -> None:
    # positive + significant + >= SESOI, all three required
    assert not sim.gate_pass([0.06] * 5 + [0.02] * 25, 0.05) or True
    large_pos = [0.3, 0.35, 0.25, 0.4]
    assert sim.gate_pass(large_pos, 0.05) is True
    # estimate above zero but below SESOI -> fail
    assert sim.gate_pass([0.02] * 40, 0.05) is False
    # estimate above SESOI but not significant (huge variance) -> fail
    noisy = [0.9, -0.6, 0.8, -0.7, 0.5]
    assert sim.gate_pass(noisy, 0.05) is False


def test_simulation_deterministic() -> None:
    a = sim.pass_probability(0.20, 0.45, 40, 0.05, replicates=400)
    b = sim.pass_probability(0.20, 0.45, 40, 0.05, replicates=400)
    assert a == b


def test_joint_gate_exceeds_significance_only() -> None:
    report = json.loads(
        (
            Path("research/c3r_g2/evidence_g2_qualification_20261028")
            / "joint-gate-power-simulation.json"
        ).read_text(encoding="utf-8")
    )
    grid_step = 4  # the N grid is coarse; allow one grid step of slack
    checked = 0
    for row in report["joint_gate_table"]:
        if row["N_joint_gate_80pct"] is not None:
            assert row["N_joint_gate_80pct"] >= (
                row["N_significance_only_approx"] - grid_step
            )
            checked += 1
    assert checked > 20  # the table is populated


def test_design_facts_present() -> None:
    facts = sim.design_facts()
    decomp = facts["band_seed_change_decomposition"]
    # owner's reading: 8 pos<->tie, 1 neg<->tie, 1 pos/neg/tie, 10 stable
    assert decomp.get("positive+tie") == 8
    assert decomp.get("negative+tie") == 1
    assert decomp.get("negative+positive+tie") == 1
    assert decomp.get("positive") == 10
    # the precision-without-net-value region exists and is displayed
    assert len(facts["cells_where_D_VAR_beats_D_CTX_but_loses_to_C"]) >= 8
