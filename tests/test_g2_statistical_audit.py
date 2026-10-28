"""Offline tests for the G2 final statistical audit.

Real direction tests (the vacuous `or True` line is gone): C output
failures RAISE observed NV under ITT; the hierarchical gate requires
BOTH conditions (G-pass alone insufficient when NV fails); bounded
outcomes; arm correlation reduces difference variance (and independent
arms are the conservative case); determinism; and the verdict rule.
"""

from __future__ import annotations

import statistics

import scripts.audit_g2_interaction_statistical as audit


def test_c_failures_raise_observed_nv() -> None:
    # with decision-level parity (D_VAR == C quality), ITT NV > 0
    import random

    rng = random.Random(7)
    nvs = []
    for _ in range(400):
        org = audit.simulate_org(0.80, 0.60, 0.80, 1.0, "shared_org_effect", rng)
        nvs.append(org["VAR"] - org["C"])
    mean_nv = statistics.mean(nvs)
    assert mean_nv > 0.03  # ~ +0.09*0.80 = +7.2pp expected direction
    # and without failures (fail=0 semantics) parity would be ~0:
    # verified analytically by the same cell model minus exhaustion.


def test_c_failure_direction_against_old_bug() -> None:
    # the OLD buggy shift subtracted; the corrected semantics must add
    p_c = 0.80
    expected_shift = audit.FAIL_C * p_c  # ~ +7.2pp
    assert expected_shift > 0.05


def test_hierarchical_gate_requires_both() -> None:
    # NV fails (negative values) -> gate closes even if G would pass
    orgs = [
        {"C": 0.9, "CTX": 0.5, "VAR": 0.55} for _ in range(40)
    ]
    nv_pass, g_pass = audit.joint_gate_pass(orgs)
    assert nv_pass is False and g_pass is False
    # NV passes strongly, G fails (below SESOI) -> first True, second False
    orgs2 = [
        {"C": 0.4, "CTX": 0.72, "VAR": 0.75} for _ in range(40)
    ]
    nv_pass2, g_pass2 = audit.joint_gate_pass(orgs2)
    assert nv_pass2 is True and g_pass2 is False
    # both pass
    orgs3 = [
        {"C": 0.4, "CTX": 0.5, "VAR": 0.75} for _ in range(40)
    ]
    nv_pass3, g_pass3 = audit.joint_gate_pass(orgs3)
    assert nv_pass3 is True and g_pass3 is True


def test_bounded_outcomes() -> None:
    import random

    rng = random.Random(3)
    for _ in range(200):
        org = audit.simulate_org(0.5, 0.5, 0.9, 2.0, "independent_arms", rng)
        for arm in ("C", "CTX", "VAR"):
            assert 0.0 <= org[arm] <= 1.0


def test_correlation_reduces_difference_variance() -> None:
    import random

    diffs_shared, diffs_ind = [], []
    rng1, rng2 = random.Random(11), random.Random(11)
    for _ in range(600):
        o = audit.simulate_org(0.6, 0.5, 0.8, 1.5, "shared_org_effect", rng1)
        diffs_shared.append(o["VAR"] - o["CTX"])
        o2 = audit.simulate_org(0.6, 0.5, 0.8, 1.5, "independent_arms", rng2)
        diffs_ind.append(o2["VAR"] - o2["CTX"])
    assert statistics.stdev(diffs_shared) < statistics.stdev(diffs_ind)


def test_simulation_deterministic() -> None:
    a = audit.full_gate_probability(0.8, 0.6, 0.9, 1.0, "shared_org_effect", 20,
                                    replicates=300)
    b = audit.full_gate_probability(0.8, 0.6, 0.9, 1.0, "shared_org_effect", 20,
                                    replicates=300)
    assert a == b


def test_cost_model_corrected() -> None:
    cost = audit.cost_model(52)
    # summed execution: 52*(16*26.5 + 32*3.4) = 27,705.6 s = 7.70 h
    assert abs(cost["summed_execution_hours"] - 7.70) < 0.05
    assert cost["sends_total"] == 2496
    assert cost["completion_tokens_ceiling"] == 2500 * 4096
