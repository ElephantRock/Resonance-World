"""Frozen statistical helpers for D2d source capability acquisition."""

from __future__ import annotations

import math
import random
import statistics
from typing import Any

Z_ONE_SIDED_95 = 1.6448536269514722
BOOTSTRAP_REPS = 50_000


def normal_cdf(value: float) -> float:
    return 0.5 * math.erfc(-value / math.sqrt(2.0))


def paired_margin_test(
    values: list[float], *, threshold: float = 0.1
) -> dict[str, float | bool]:
    n = len(values)
    if n < 2:
        raise ValueError("paired margin test requires at least two observations")
    mean = statistics.fmean(values)
    sample_sd = statistics.stdev(values)
    standard_error = sample_sd / math.sqrt(n)
    if standard_error == 0.0:
        z = math.inf if mean > threshold else (-math.inf if mean < threshold else 0.0)
        p = 0.0 if mean > threshold else (1.0 if mean < threshold else 0.5)
        lower = mean
    else:
        z = (mean - threshold) / standard_error
        p = 1.0 - normal_cdf(z)
        lower = mean - Z_ONE_SIDED_95 * standard_error
    return {
        "n": float(n),
        "mean": mean,
        "sample_sd": sample_sd,
        "standard_error": standard_error,
        "threshold": threshold,
        "z": z,
        "one_sided_p": p,
        "one_sided_95_lower": lower,
        "gate_pass": bool(lower > threshold),
    }


def percentile(sorted_values: list[float], q: float) -> float:
    if not sorted_values:
        return float("nan")
    if len(sorted_values) == 1:
        return sorted_values[0]
    position = (len(sorted_values) - 1) * q
    low = math.floor(position)
    high = math.ceil(position)
    if low == high:
        return sorted_values[low]
    fraction = position - low
    return sorted_values[low] * (1.0 - fraction) + sorted_values[high] * fraction


def paired_bootstrap(
    differences_by_budget: dict[int, list[float]],
    *,
    seed: int,
    replicates: int | None = None,
) -> dict[str, Any]:
    reps = BOOTSTRAP_REPS if replicates is None else replicates
    lengths = {len(values) for values in differences_by_budget.values()}
    if len(lengths) != 1:
        raise ValueError("D2d bootstrap vectors must have identical lengths")
    n = next(iter(lengths), 0)
    if n == 0:
        return {
            "replicates": reps,
            "seed": seed,
            "interval": "paired percentile 95%",
            "metrics": {},
        }
    rng = random.Random(seed)
    draws: dict[int, list[float]] = {
        budget: [] for budget in sorted(differences_by_budget)
    }
    for _ in range(reps):
        indices = [rng.randrange(n) for _ in range(n)]
        for budget, values in differences_by_budget.items():
            draws[budget].append(sum(values[index] for index in indices) / n)
    metrics: dict[str, Any] = {}
    for budget, values in draws.items():
        values.sort()
        metrics[f"developed_{budget}_minus_fresh"] = {
            "lower_2_5": percentile(values, 0.025),
            "median": percentile(values, 0.5),
            "upper_97_5": percentile(values, 0.975),
        }
    return {
        "replicates": reps,
        "seed": seed,
        "interval": "paired percentile 95%",
        "metrics": metrics,
    }
