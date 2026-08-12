from types import SimpleNamespace

import pytest

from resonance_world import w9_integrated as integrated
from resonance_world import w9_integrated_execution as execution


def _fake_arm(bits):
    c = int(bits["C"])
    l = int(bits["L"])
    p = int(bits["P"])
    return {
        "mean_organization_success_pct": 70.0 + c + 2 * l + 3 * p,
        "mean_source_loss_pp": 4.0 - 0.5 * c - 1.0 * l - 1.5 * p,
        "organization_outcome_inequality_sd_pp": 1.0,
    }


def test_registered_aliases_keep_k_none_duplicates_explicit():
    aliases = integrated._registered_aliases()
    assert aliases["full_C+L+P+K"] == aliases["leave_one_out_K"] == "C1L1P1"
    assert aliases["leave_one_out_C"] == aliases["leave_two_out_C_K"] == "C0L1P1"
    assert aliases["leasing_only"] == "C0L1P0"
    assert aliases["substitution_only"] == "C0L0P1"
    assert aliases["leasing_plus_substitution"] == "C0L1P1"


def test_additive_factorial_has_zero_pairwise_interactions():
    arms = {}
    for c in (False, True):
        for l in (False, True):
            for p in (False, True):
                bits = {"C": c, "L": l, "P": p}
                arms[integrated._bits_key(bits)] = _fake_arm(bits)
    interactions = integrated._factorial_interactions(arms)
    for key in ("C:L", "C:P", "L:P"):
        assert interactions[key]["organization_interaction_pp"] == pytest.approx(0.0)
        assert interactions[key]["source_loss_interaction_pp"] == pytest.approx(0.0)
    for key in ("C:K", "L:K", "P:K"):
        assert interactions[key]["structurally_zero_because_K_none"] is True


def test_empty_upstream_eligibility_selects_w7_and_cannot_claim_source_reduction(monkeypatch):
    def fake_arm(_base, _portfolio, _config, *, phase, bits):
        del phase
        return _fake_arm(bits)

    monkeypatch.setattr(execution, "_arm_result", fake_arm)
    monkeypatch.setattr(execution, "_w8_comparator", lambda *args, **kwargs: {"comparator": True})
    population = SimpleNamespace(
        portable_by_id={"a": object(), "b": object()},
        portable_by_field={"f": (object(), object())},
    )
    config = {
        "upstream_eligibility": {"C": False, "L": False, "P": False, "K": []},
        "effect_band_pp": 2.0,
        "source_loss_bound_pp": 2.0,
        "required_source_loss_reduction_fraction": 0.50,
        "organization_inequality_worsening_bound_pp": 2.0,
    }
    result = execution.run_w9_05_execution(
        population,
        population,
        config,
        {},
        phase="discovery",
    )
    assert result["selected_mechanisms"] == []
    assert result["selected_regime"] == result["W7_unrestricted"]
    assert result["structural_status"] == "no_upstream_eligible_w9_mechanisms"
    assert result["gates"]["source_loss_at_most_2pp"] is False
    assert result["gates"]["source_loss_reduction_at_least_50pct"] is False
    assert result["integrated_static_gate"] is False
