"""Matched-run non-interference checks for World observation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True, slots=True)
class FieldRunObservation:
    """Behavioral and overhead snapshot from one matched Field run."""

    field_id: str
    checkpoint_id: str
    state_hashes: Mapping[str, str]
    emergence_metrics: Mapping[str, float]
    total_runtime_seconds: float
    world_instrumentation_seconds: float = 0.0

    def __post_init__(self) -> None:
        if not self.field_id or not self.checkpoint_id:
            raise ValueError("field_id and checkpoint_id are required")
        if self.total_runtime_seconds <= 0:
            raise ValueError("total_runtime_seconds must be positive")
        if self.world_instrumentation_seconds < 0:
            raise ValueError("world_instrumentation_seconds must be non-negative")


@dataclass(frozen=True, slots=True)
class NonInterferenceReport:
    """Result of comparing isolated and World-observed matched runs."""

    behavior_identical: bool
    hashes_identical: bool
    metrics_within_tolerance: bool
    overhead_within_bound: bool
    differing_hashes: tuple[str, ...]
    metric_deltas: tuple[tuple[str, float], ...]
    overhead_ratio: float

    @property
    def passed(self) -> bool:
        return self.behavior_identical and self.overhead_within_bound


def compare_observations(
    control: FieldRunObservation,
    observed: FieldRunObservation,
    *,
    metric_tolerance: float = 0.0,
    max_overhead_ratio: float = 0.05,
) -> NonInterferenceReport:
    """Compare matched runs while treating Field state as authoritative.

    State hashes are exact. Emergence metrics may use a caller-supplied tolerance
    for floating-point export differences. Instrumentation overhead is measured as
    World instrumentation time divided by the observed run's total runtime.
    """

    if metric_tolerance < 0:
        raise ValueError("metric_tolerance must be non-negative")
    if not 0.0 <= max_overhead_ratio <= 1.0:
        raise ValueError("max_overhead_ratio must be between 0 and 1")

    differing_hashes = tuple(
        sorted(
            key
            for key in set(control.state_hashes) | set(observed.state_hashes)
            if control.state_hashes.get(key) != observed.state_hashes.get(key)
        )
    )

    metric_deltas = []
    for key in sorted(set(control.emergence_metrics) | set(observed.emergence_metrics)):
        left = control.emergence_metrics.get(key)
        right = observed.emergence_metrics.get(key)
        if left is None or right is None:
            metric_deltas.append((key, float("inf")))
        else:
            metric_deltas.append((key, abs(float(left) - float(right))))

    metrics_within_tolerance = all(
        delta <= metric_tolerance for _, delta in metric_deltas
    )
    hashes_identical = not differing_hashes
    overhead_ratio = observed.world_instrumentation_seconds / observed.total_runtime_seconds
    overhead_within_bound = overhead_ratio <= max_overhead_ratio

    return NonInterferenceReport(
        behavior_identical=hashes_identical and metrics_within_tolerance,
        hashes_identical=hashes_identical,
        metrics_within_tolerance=metrics_within_tolerance,
        overhead_within_bound=overhead_within_bound,
        differing_hashes=differing_hashes,
        metric_deltas=tuple(metric_deltas),
        overhead_ratio=overhead_ratio,
    )
