from __future__ import annotations

import pytest

from resonance_world.w9_calibration import (
    CalibrationObservation,
    CalibrationThresholds,
    build_calibration_report,
    spearman_rho,
)


def _observation(
    index: int,
    predicted: float,
    realized: float,
    *,
    conservative: float | None = None,
) -> CalibrationObservation:
    return CalibrationObservation(
        source_field_id=f"field-{index % 2}",
        agent_id=f"agent-{index:02d}",
        unavailable_agent_ids=frozenset(),
        predicted_loss_pp=predicted,
        conservative_budget_pp=predicted if conservative is None else conservative,
        realized_loss_pp=realized,
        evidence_refs=(f"holdout:{index}",),
    )


def test_spearman_uses_average_ranks_for_ties() -> None:
    predicted = (1.0, 1.0, 2.0, 3.0)
    realized = (1.0, 2.0, 2.0, 4.0)

    rho = spearman_rho(predicted, realized)

    assert rho == pytest.approx(0.8333333333333334)


def test_calibrated_report_passes_all_registered_gates() -> None:
    observations = tuple(
        _observation(
            index,
            predicted=value,
            realized=value + error,
            conservative=value + 0.4,
        )
        for index, (value, error) in enumerate(
            (
                (0.2, 0.1),
                (0.5, -0.1),
                (0.8, 0.2),
                (1.1, -0.1),
                (1.4, 0.1),
                (1.7, -0.2),
                (2.0, 0.1),
                (2.3, -0.1),
            )
        )
    )

    report = build_calibration_report(observations)

    assert report.label == "calibrated_source_cost_estimator"
    assert report.mae_pp == pytest.approx(0.125)
    assert report.signed_bias_pp == pytest.approx(0.0)
    assert report.spearman_rho > 0.98
    assert report.high_cost_count == 2
    assert report.high_cost_safe_rate == pytest.approx(1.0)
    assert report.calibration_slope is not None


def test_rank_informative_label_when_bias_gate_fails() -> None:
    observations = tuple(
        _observation(index, predicted=value, realized=value + 0.8, conservative=value + 1.0)
        for index, value in enumerate((0.2, 0.5, 0.8, 1.1, 1.4, 1.7, 2.0, 2.3))
    )

    report = build_calibration_report(observations)

    assert report.spearman_rho == pytest.approx(1.0)
    assert abs(report.signed_bias_pp) > 0.5
    assert report.label == "biased_but_rank_informative"


def test_uncalibrated_label_when_rank_order_fails() -> None:
    observations = tuple(
        _observation(index, predicted=predicted, realized=realized, conservative=3.0)
        for index, (predicted, realized) in enumerate(
            (
                (0.1, 2.0),
                (0.4, 1.7),
                (0.7, 1.4),
                (1.0, 1.1),
                (1.3, 0.8),
                (1.6, 0.5),
                (1.9, 0.2),
                (2.2, -0.1),
            )
        )
    )

    report = build_calibration_report(observations)

    assert report.spearman_rho == pytest.approx(-1.0)
    assert report.label == "uncalibrated_source_cost_estimator"


def test_high_cost_gate_uses_conservative_budget_prediction() -> None:
    observations = tuple(
        _observation(
            index,
            predicted=value,
            realized=value,
            conservative=(value - 1.1 if index >= 6 else value + 0.2),
        )
        for index, value in enumerate((0.2, 0.5, 0.8, 1.1, 1.4, 1.7, 2.0, 2.3))
    )

    report = build_calibration_report(observations)

    assert report.spearman_rho == pytest.approx(1.0)
    assert report.mae_pp == pytest.approx(0.0)
    assert report.high_cost_count == 2
    assert report.high_cost_safe_rate == pytest.approx(0.0)
    assert report.label == "biased_but_rank_informative"


def test_top_quartile_count_is_ceil_n_over_four() -> None:
    observations = tuple(
        _observation(index, predicted=float(index), realized=float(index), conservative=10.0)
        for index in range(9)
    )

    report = build_calibration_report(observations)

    assert report.high_cost_count == 3
    assert report.high_cost_safe_rate == pytest.approx(1.0)


def test_constant_predictions_are_not_rank_informative() -> None:
    observations = tuple(
        _observation(index, predicted=1.0, realized=float(index), conservative=10.0)
        for index in range(4)
    )

    report = build_calibration_report(observations)

    assert report.spearman_rho == pytest.approx(0.0)
    assert report.calibration_slope is None
    assert report.label == "uncalibrated_source_cost_estimator"


def test_custom_thresholds_are_applied_without_changing_observations() -> None:
    observations = tuple(
        _observation(index, predicted=value, realized=value + 0.4, conservative=value + 0.5)
        for index, value in enumerate((0.2, 0.5, 0.8, 1.1))
    )
    strict = CalibrationThresholds(max_abs_bias_pp=0.2)

    report = build_calibration_report(observations, thresholds=strict)

    assert report.label == "biased_but_rank_informative"
    assert report.thresholds is strict
    assert report.as_dict()["observation_count"] == 4


def test_calibration_requires_multiple_holdouts_and_provenance() -> None:
    one = _observation(0, predicted=0.5, realized=0.6)
    with pytest.raises(ValueError, match="at least two"):
        build_calibration_report((one,))

    with pytest.raises(ValueError, match="provenance"):
        CalibrationObservation(
            source_field_id="field-a",
            agent_id="agent-a",
            unavailable_agent_ids=frozenset(),
            predicted_loss_pp=0.5,
            conservative_budget_pp=0.8,
            realized_loss_pp=0.6,
            evidence_refs=(),
        )
