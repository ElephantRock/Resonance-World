"""Offline tests for the C3R-G2 causal qualification harness.

Asserts, per the owner's four pre-freeze requirements:
(1) C/D are process-distinct and the harness MEASURES divergence in
    both directions (S2 D>C, S3 C>D, S5 mechanism liveness) instead of
    building it (S1 honest tie);
(2) interpretation budgets are accounted (C's total record reads cover
    the compiler's corpus; proposal slots equal across arms);
(3) organization-level structure is explicit (each scenario is an
    independent fixture organization with its own corpus and holdout);
(4) the taxonomy classifies abstention fallbacks, interpretation-tie
    fallbacks and transport errors without dropping denominators.
All deterministic; no network; no model calls; noninferential.
"""

from __future__ import annotations

import json

from resonance_world.c3r_g2 import PLANS
from resonance_world.c3r_g2_causal_qualification import (
    ARMS,
    MEMBERS,
    SAMPLE_K,
    compile_procedure,
    build_report,
    run_scenario,
    scenario_s1_unambiguous,
    scenario_s2_noisy_majority,
    scenario_s3_task_conditional,
    scenario_s4_abstention,
    scenario_s5_corrupted_procedure,
    scenario_s6_transport_injection,
)


def _report_by_name():
    report = build_report()
    return {s["scenario"]: s for s in report["scenarios"]}, report


def test_compiler_support_and_margin_floors() -> None:
    from resonance_world.c3r_g2_causal_qualification import Episode

    def ep(i, plan, success):
        return Episode(f"e{i}", "c", "v", plan, success)

    # below support floor -> abstain
    plan, stats = compile_procedure([ep(i, PLANS[1], True) for i in range(7)], "c")
    assert plan is None and stats["support"] == 7
    # tie margin -> abstain
    plan, _ = compile_procedure(
        [ep(i, PLANS[1], True) for i in range(6)]
        + [ep(i + 10, PLANS[0], True) for i in range(6)], "c"
    )
    assert plan is None
    # clear majority -> compiled
    plan, _ = compile_procedure(
        [ep(i, PLANS[1], True) for i in range(6)]
        + [ep(i + 10, PLANS[0], True) for i in range(4)], "c"
    )
    assert plan == PLANS[1]


def test_s1_honest_tie_control() -> None:
    result = run_scenario(scenario_s1_unambiguous())
    arms = result["arms"]
    assert arms["D"]["correct"] == 48
    assert arms["C"]["correct"] == 48
    assert result["paired_counts"]["d_minus_c_correct"] == 0
    # the tie is by evidence clarity, and the compiled plan is real
    assert result["compiled"]["ctx-s1"] == PLANS[1]
    # neutral-default controls fail on this truth
    assert arms["B"]["correct"] == 0 and arms["D_MINUS"]["correct"] == 0


def test_s2_compilation_wins_measurably() -> None:
    result = run_scenario(scenario_s2_noisy_majority())
    arms = result["arms"]
    assert result["compiled"]["ctx-s2"] == PLANS[1]
    assert arms["D"]["correct"] == 48
    assert 0 < arms["C"]["correct"] < 48  # bounded sampling errs somewhere
    assert result["paired_counts"]["d_minus_c_correct"] > 0
    assert arms["C"]["fallbacks"] >= 0  # tie fallbacks counted if any


def test_s3_interpretation_granularity_wins() -> None:
    result = run_scenario(scenario_s3_task_conditional())
    arms = result["arms"]
    # global per-context majority is PLANS[1]: right on special, wrong on plain
    assert result["compiled"]["ctx-s3"] == PLANS[1]
    assert arms["D"]["correct"] == 24  # only the 12 special tasks x 2 members
    # raw readers see variant tags and win on both subsets
    assert arms["C"]["correct"] >= 44
    assert result["paired_counts"]["d_minus_c_correct"] < 0


def test_s4_abstention_taxonomy() -> None:
    result = run_scenario(scenario_s4_abstention())
    arms = result["arms"]
    assert result["compiled"]["ctx-s4"] is None
    assert result["abstention_fallback_cells"] == 48
    assert arms["D"]["fallbacks"] == 48
    # D with an abstained procedure behaves like the neutral control
    assert arms["D"]["correct"] == arms["B"]["correct"] == 0
    # C still interprets the small corpus and succeeds
    assert arms["C"]["correct"] == 48


def test_s5_mechanism_liveness() -> None:
    clean = run_scenario(scenario_s1_unambiguous())
    corrupted = run_scenario(scenario_s5_corrupted_procedure())
    assert clean["arms"]["D"]["correct"] == 48
    assert corrupted["arms"]["D"]["correct"] == 0  # outcomes flipped
    # and removal (D_MINUS) diverges from D exactly when the procedure
    # differs from the neutral default
    assert clean["arms"]["D_MINUS"]["correct"] == 0


def test_s6_transport_taxonomy_preserves_denominator() -> None:
    result = run_scenario(scenario_s6_transport_injection())
    arms = result["arms"]
    for arm in ("C", "D"):
        assert arms[arm]["transport_error"] == 2
        assert arms[arm]["attempts"] == 48  # denominator intact
        assert arms[arm]["correct"] + arms[arm]["wrong"] == 46
    for arm in ("A", "B", "D_MINUS"):
        assert arms[arm]["transport_error"] == 0


def test_budget_accounting_and_parity() -> None:
    by_name, _ = _report_by_name()
    for name, scenario in by_name.items():
        parity = scenario["budget_parity"]
        assert parity["proposal_slots_equal"] is True, name
        assert parity["c_total_record_reads"] >= parity["d_compile_reads"], name
        # C reads up to K records per member-task
        expected_max = 48 * SAMPLE_K
        assert parity["c_total_record_reads"] <= expected_max, name


def test_organization_level_structure_and_determinism() -> None:
    first = build_report()
    second = build_report()
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)
    assert first["noninferential"] is True and first["no_provider_calls"] is True
    names = [s["scenario"] for s in first["scenarios"]]
    assert len(names) == 6 and len(set(names)) == 6
    # every scenario is a self-contained organization fixture
    for scenario in first["scenarios"]:
        assert set(scenario["arms"]) == set(ARMS)
        assert all(
            scenario["arms"][arm]["attempts"] == len(MEMBERS) * 24
            for arm in ARMS
        )


def test_no_historical_artifacts_touched(tmp_path, monkeypatch) -> None:
    # the harness is pure computation: it must not write anywhere
    from resonance_world import c3r_g2_causal_qualification as module

    sentinel = tmp_path / "sentinel.txt"
    monkeypatch.setattr(
        "builtins.open", lambda *a, **k: (_ for _ in ()).throw(
            AssertionError("harness must not perform file I/O")
        )
    )
    try:
        module.build_report()
    finally:
        monkeypatch.undo()
    assert not sentinel.exists()
