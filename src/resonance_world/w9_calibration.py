"""Preregistered W9-00B calibration metrics for marginal source-cost estimates."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

CalibrationLabel = Literal[
    "calibrated_source_cost_estimator",
    "biased_but_rank_informative",
    "uncalibrated_source_cost_estimator",
]


@dataclass(frozen=True, slots=True)
class CalibrationThresholds:
    max_mae_pp: float = 1.0
    max_abs_bias_pp: float = 0.5
    min_spearman_rho: float = 0.60
    min_high_cost_safe_rate: float = 0.90
    max_high_cost_underprediction_pp: float = 1.0

    def __post_init__(self) -> None:
        if self.max_mae_pp < 0 or self.max_abs_bias_pp < 0:
            raise ValueError("calibration error thresholds must be non-negative")
        if not -1 <= self.min_spearman_rho <= 1:
            raise ValueError("Spearman threshold must lie in [-1, 1]")
        if not 0 <= self.min_high_cost_safe_rate <= 1:
            raise ValueError("high-cost safe-rate threshold must lie in [0, 1]")
        if self.max_high_cost_underprediction_pp < 0:
            raise ValueError("underprediction tolerance must be non-negative")


@dataclass(frozen=True, slots=True)
class CalibrationObservation:
    """One holdout removal with prediction fixed before realized evaluation."""

    source_field_id: str
    agent_id: str
    unavailable_agent_ids: frozenset[str]
    predicted_loss_pp: float
    conservative_budget_pp: float
    realized_loss_pp: float
    evidence_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.source_field_id or not self.agent_id:
            raise ValueError("calibration identifiers must be non-empty")
        if self.agent_id in self.unavailable_agent_ids:
            raise ValueError("candidate agent cannot already be unavailable")
        if self.conservative_budget_pp < 0:
            raise ValueError("conservative budget prediction must be non-negative")
        refs = tuple(sorted({str(ref) for ref in self.evidence_refs if str(ref)}))
        if not refs:
            raise ValueError("calibration observation requires provenance evidence")
        object.__setattr__(self, "evidence_refs", refs)

    @property
    def prediction_error_pp(self) -> float:
        return self.predicted_loss_pp - self.realized_loss_pp

    def safe_for_high_cost_gate(self, tolerance_pp: float) -> bool:
        if tolerance_pp < 0:
            raise ValueError("underprediction tolerance must be non-negative")
        return self.realized_loss_pp - self.conservative_budget_pp <= tolerance_pp

    def sort_key(self) -> tuple[object, ...]:
        return (
            -self.realized_loss_pp,
            self.source_field_id,
            self.agent_id,
            tuple(sorted(self.unavailable_agent_ids)),
        )


@dataclass(frozen=True, slots=True)
class CalibrationReport:
    observations: tuple[CalibrationObservation, ...]
    thresholds: CalibrationThresholds
    mae_pp: float
    signed_bias_pp: float
    calibration_slope: float | None
    calibration_intercept: float
    spearman_rho: float
    high_cost_count: int
    high_cost_safe_rate: float
    label: CalibrationLabel

    def as_dict(self) -> dict[str, object]:
        return {
            "calibration_intercept": self.calibration_intercept,
            "calibration_slope": self.calibration_slope,
            "high_cost_count": self.high_cost_count,
            "high_cost_safe_rate": self.high_cost_safe_rate,
            "label": self.label,
            "mae_pp": self.mae_pp,
            "observation_count": len(self.observations),
            "signed_bias_pp": self.signed_bias_pp,
            "spearman_rho": self.spearman_rho,
            "thresholds": {
                "max_abs_bias_pp": self.thresholds.max_abs_bias_pp,
                "max_high_cost_underprediction_pp": (
                    self.thresholds.max_high_cost_underprediction_pp
                ),
                "max_mae_pp": self.thresholds.max_mae_pp,
                "min_high_cost_safe_rate": self.thresholds.min_high_cost_safe_rate,
                "min_spearman_rho": self.thresholds.min_spearman_rho,
            },
        }


def _average_ranks(values: tuple[float, ...]) -> tuple[float, ...]:
    ordered = sorted(enumerate(values), key=lambda item: (item[1], item[0]))
    ranks = [0.0] * len(values)
    index = 0
    while index < len(ordered):
        end = index + 1
        while end < len(ordered) and ordered[end][1] == ordered[index][1]:
            end += 1
        average_rank = ((index + 1) + end) / 2.0
        for offset in range(index, end):
            ranks[ordered[offset][0]] = average_rank
        index = end
    return tuple(ranks)


def _pearson(x: tuple[float, ...], y: tuple[float, ...]) -> float:
    if len(x) != len(y) or len(x) < 2:
        raise ValueError("correlation requires at least two paired observations")
    mean_x = sum(x) / len(x)
    mean_y = sum(y) / len(y)
    centered_x = tuple(value - mean_x for value in x)
    centered_y = tuple(value - mean_y for value in y)
    sum_sq_x = sum(value * value for value in centered_x)
    sum_sq_y = sum(value * value for value in centered_y)
    if sum_sq_x == 0 or sum_sq_y == 0:
        return 0.0
    covariance = sum(a * b for a, b in zip(centered_x, centered_y, strict=True))
    return covariance / math.sqrt(sum_sq_x * sum_sq_y)


def spearman_rho(predicted: tuple[float, ...], realized: tuple[float, ...]) -> float:
    """Spearman rank correlation with average ranks for exact ties."""

    return _pearson(_average_ranks(predicted), _average_ranks(realized))


def _calibration_line(
    predicted: tuple[float, ...],
    realized: tuple[float, ...],
) -> tuple[float | None, float]:
    mean_predicted = sum(predicted) / len(predicted)
    mean_realized = sum(realized) / len(realized)
    variance = sum((value - mean_predicted) ** 2 for value in predicted)
    if variance == 0:
        return None, mean_realized
    covariance = sum(
        (x - mean_predicted) * (y - mean_realized)
        for x, y in zip(predicted, realized, strict=True)
    )
    slope = covariance / variance
    intercept = mean_realized - slope * mean_predicted
    return slope, intercept


def _top_quartile(
    observations: tuple[CalibrationObservation, ...],
) -> tuple[CalibrationObservation, ...]:
    """Select the top ceil(n/4) realized-cost observations with deterministic ties."""

    count = max(1, math.ceil(len(observations) / 4))
    return tuple(sorted(observations, key=CalibrationObservation.sort_key)[:count])


def build_calibration_report(
    observations: tuple[CalibrationObservation, ...],
    *,
    thresholds: CalibrationThresholds | None = None,
) -> CalibrationReport:
    if len(observations) < 2:
        raise ValueError("calibration requires at least two holdout observations")
    thresholds = thresholds or CalibrationThresholds()
    predicted = tuple(item.predicted_loss_pp for item in observations)
    realized = tuple(item.realized_loss_pp for item in observations)
    errors = tuple(item.prediction_error_pp for item in observations)

    mae = sum(abs(value) for value in errors) / len(errors)
    bias = sum(errors) / len(errors)
    rho = spearman_rho(predicted, realized)
    slope, intercept = _calibration_line(predicted, realized)

    high_cost = _top_quartile(observations)
    safe_count = sum(
        item.safe_for_high_cost_gate(thresholds.max_high_cost_underprediction_pp)
        for item in high_cost
    )
    safe_rate = safe_count / len(high_cost)

    if rho < thresholds.min_spearman_rho:
        label: CalibrationLabel = "uncalibrated_source_cost_estimator"
    elif (
        mae <= thresholds.max_mae_pp
        and abs(bias) <= thresholds.max_abs_bias_pp
        and safe_rate >= thresholds.min_high_cost_safe_rate
    ):
        label = "calibrated_source_cost_estimator"
    else:
        label = "biased_but_rank_informative"

    return CalibrationReport(
        observations=observations,
        thresholds=thresholds,
        mae_pp=mae,
        signed_bias_pp=bias,
        calibration_slope=slope,
        calibration_intercept=intercept,
        spearman_rho=rho,
        high_cost_count=len(high_cost),
        high_cost_safe_rate=safe_rate,
        label=label,
    )
