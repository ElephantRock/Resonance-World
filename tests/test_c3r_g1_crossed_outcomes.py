"""Negative and accounting controls; never send a model request."""

from __future__ import annotations

from dataclasses import replace

import pytest

from resonance_world.c3r_g1_crossed_plan import make_plan
from resonance_world.c3r_g1_crossed_outcomes import AttemptOutcome, audit_outcomes


def _all_accepted() -> tuple[AttemptOutcome, ...]:
    return tuple(AttemptOutcome(s.unit_id, s.task_id, s.stage, s.arm,
                                "accepted", "A", True)
                 for s in make_plan().schedule)


def test_all_accepted_yields_full_denominators_not_scientific_acceptance() -> None:
    report = audit_outcomes(make_plan(), outcomes=_all_accepted())
    assert report["prescribed_logical_attempts"] == 40
    assert report["logical_status_counts"]["accepted"] == 40
    assert report["source_units_with_two_accepted_development_actions"] == 8
    assert report["complete_accepted_qualification_triplets"] == 8
    assert report["scientific_acceptance"] is False
    assert report["provider_execution_verified"] is False
    assert report["target_cell_stratification_available"] is False
    assert report["overall"]["learned_minus_fresh"]["diff_lower"] == 0
    assert report["overall"]["learned_minus_fresh"]["diff_upper"] == 0
    assert report["family"]["arithmetic"]["prescribed_units"] == 4
    assert report["family"]["text"]["prescribed_units"] == 4


def test_unresolved_is_not_silently_discarded_or_called_wrong() -> None:
    plan = make_plan()
    rows = list(_all_accepted())
    index = next(i for i, s in enumerate(plan.schedule)
                 if s.stage == "qualification" and s.arm == "fresh")
    rows[index] = replace(rows[index], status="provider_error", action=None, correct=None)
    report = audit_outcomes(plan, outcomes=tuple(rows))
    assert report["prescribed_logical_attempts"] == 40
    assert report["logical_status_counts"]["provider_error"] == 1
    assert report["complete_accepted_qualification_triplets"] == 7
    fresh = report["overall"]["arms"]["fresh"]
    assert fresh["prescribed"] == 8
    assert fresh["accepted"] == 7
    assert fresh["reported_incorrect"] == 0
    assert fresh["unresolved"] == 1
    assert fresh["rate_lower_if_unresolved_incorrect"] == 7 / 8
    assert fresh["rate_upper_if_unresolved_correct"] == 1.0
    pair = report["overall"]["learned_minus_fresh"]
    assert pair["diff_lower"] == 0
    assert pair["diff_upper"] == 1 / 8
    assert pair["requires_missingness_assumptions_for_point_estimate"] is True


def test_single_missing_or_duplicate_attempt_rejected() -> None:
    base = _all_accepted()
    for bad in (base[:-1], (*base[:-1], base[0]),
                (*base[:-1], replace(base[-1], task_id="unplanned"))):
        with pytest.raises(ValueError, match="exactly 40 unique"):
            audit_outcomes(make_plan(), outcomes=bad)


def test_invalid_scores_actions_and_spurious_success_rejected() -> None:
    base = _all_accepted()
    for changed in (replace(base[0], action="A/B"),
                    replace(base[0], correct=1),
                    replace(base[0], correct=None)):
        with pytest.raises(ValueError, match="accepted attempts"):
            audit_outcomes(make_plan(), outcomes=(changed, *base[1:]))
    for changed in (replace(base[0], status="not_sent"),
                    replace(base[0], status="invalid_format", correct=None),
                    replace(base[0], status="provider_error", action=None)):
        with pytest.raises(ValueError, match="unresolved attempts"):
            audit_outcomes(make_plan(), outcomes=(changed, *base[1:]))
    with pytest.raises(ValueError, match="invalid attempt status"):
        audit_outcomes(make_plan(), outcomes=(replace(base[0], status="magic"), *base[1:]))


def test_gaps_in_development_are_visible_without_reducing_unit_count() -> None:
    base = list(_all_accepted())
    base[0] = replace(base[0], status="not_sent", action=None, correct=None)
    report = audit_outcomes(make_plan(), outcomes=tuple(base))
    assert report["source_units_with_two_accepted_development_actions"] == 7
    assert report["complete_accepted_qualification_triplets"] == 8
    assert report["logical_status_counts"]["not_sent"] == 1
    assert report["overall"]["arms"]["learned"]["prescribed"] == 8
