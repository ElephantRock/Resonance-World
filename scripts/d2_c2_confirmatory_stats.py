"""Pure frozen statistics for D2-C2 confirmatory evaluation."""
from __future__ import annotations

import math
import random
import statistics
from typing import Any

ALPHA = 0.05
P0_SESOI = 0.10
P1_SESOI = 0.10
FIDELITY_FRACTION = 0.90
MIN_ANALYZABLE = 330
BOOTSTRAP_REPS = 50_000
BOOTSTRAP_SEED = 2026081516

_NORMAL = statistics.NormalDist()
_Z_ONE_SIDED = _NORMAL.inv_cdf(1.0 - ALPHA)
_Z_TWO_SIDED = _NORMAL.inv_cdf(1.0 - ALPHA / 2.0)


def _mean(values: list[float]) -> float:
    return statistics.fmean(values)


def _sd(values: list[float]) -> float:
    return statistics.stdev(values)


def normal_test(values: list[float], threshold: float) -> dict[str, float]:
    """Large-sample paired normal test of mean(values) > threshold."""
    n = len(values)
    if n < 2:
        raise ValueError("at least two observations required")
    mean = _mean(values)
    sd = _sd(values)
    se = sd / math.sqrt(n)
    if se == 0.0:
        z = math.inf if mean > threshold else -math.inf if mean < threshold else 0.0
    else:
        z = (mean - threshold) / se
    p = 1.0 - _NORMAL.cdf(z)
    return {
        "n": float(n),
        "mean": mean,
        "sample_sd": sd,
        "standard_error": se,
        "threshold": threshold,
        "z": z,
        "one_sided_p": p,
        "one_sided_95_lower": mean - _Z_ONE_SIDED * se,
        "two_sided_95_lower": mean - _Z_TWO_SIDED * se,
        "two_sided_95_upper": mean + _Z_TWO_SIDED * se,
    }


def holm_adjust(p_values: dict[str, float]) -> dict[str, float]:
    """Holm adjusted p-values for diagnostics."""
    ordered = sorted(p_values.items(), key=lambda item: item[1])
    m = len(ordered)
    adjusted: dict[str, float] = {}
    running = 0.0
    for rank, (name, p_value) in enumerate(ordered, start=1):
        candidate = min(1.0, (m - rank + 1) * p_value)
        running = max(running, candidate)
        adjusted[name] = running
    return adjusted


def _quantile(sorted_values: list[float], probability: float) -> float:
    if not sorted_values:
        raise ValueError("empty values")
    position = (len(sorted_values) - 1) * probability
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return sorted_values[lower]
    weight = position - lower
    return sorted_values[lower] * (1.0 - weight) + sorted_values[upper] * weight


def bootstrap_sensitivity(
    fresh: list[float],
    description: list[float],
    reproduced: list[float],
    source: list[float],
) -> dict[str, Any]:
    """Deterministic paired percentile bootstrap sensitivity analysis."""
    n = len(source)
    if not (n == len(fresh) == len(description) == len(reproduced)):
        raise ValueError("arm length mismatch")
    rng = random.Random(BOOTSTRAP_SEED)
    metrics: dict[str, list[float]] = {
        "p0_source_minus_fresh": [],
        "p1_reproduced_minus_description": [],
        "p2_raw_reproduced_minus_source": [],
        "p2_90": [],
        "fidelity_ratio": [],
    }
    for _ in range(BOOTSTRAP_REPS):
        sum_fresh = 0.0
        sum_description = 0.0
        sum_reproduced = 0.0
        sum_source = 0.0
        for _j in range(n):
            index = rng.randrange(n)
            sum_fresh += fresh[index]
            sum_description += description[index]
            sum_reproduced += reproduced[index]
            sum_source += source[index]
        mean_fresh = sum_fresh / n
        mean_description = sum_description / n
        mean_reproduced = sum_reproduced / n
        mean_source = sum_source / n
        metrics["p0_source_minus_fresh"].append(mean_source - mean_fresh)
        metrics["p1_reproduced_minus_description"].append(
            mean_reproduced - mean_description
        )
        metrics["p2_raw_reproduced_minus_source"].append(
            mean_reproduced - mean_source
        )
        metrics["p2_90"].append(
            mean_reproduced - FIDELITY_FRACTION * mean_source
        )
        ratio = mean_reproduced / mean_source if mean_source > 0.0 else math.nan
        metrics["fidelity_ratio"].append(ratio)

    result: dict[str, Any] = {
        "replicates": BOOTSTRAP_REPS,
        "seed": BOOTSTRAP_SEED,
        "interval": "paired percentile 95%",
        "metrics": {},
    }
    for name, values in metrics.items():
        finite = sorted(value for value in values if math.isfinite(value))
        result["metrics"][name] = {
            "lower_2_5": _quantile(finite, 0.025),
            "median": _quantile(finite, 0.5),
            "upper_97_5": _quantile(finite, 0.975),
        }
    return result


def evaluate_scores(
    fresh: list[float],
    description: list[float],
    reproduced: list[float],
    source: list[float],
) -> dict[str, Any]:
    """Apply the frozen D2 serial gatekeeping contract to C2."""
    n = len(source)
    if not (n == len(fresh) == len(description) == len(reproduced)):
        raise ValueError("arm length mismatch")
    if n < MIN_ANALYZABLE:
        return {
            "classification": "D2-S4",
            "classification_label": "scientifically_unclassifiable_minimum_n",
            "analyzable_pairs": n,
            "minimum_analyzable_pairs": MIN_ANALYZABLE,
        }

    p0_values = [s - f for s, f in zip(source, fresh, strict=True)]
    p1_values = [r - d for r, d in zip(reproduced, description, strict=True)]
    p2_raw_values = [r - s for r, s in zip(reproduced, source, strict=True)]
    p2_90_values = [
        r - FIDELITY_FRACTION * s
        for r, s in zip(reproduced, source, strict=True)
    ]

    p0 = normal_test(p0_values, P0_SESOI)
    p1 = normal_test(p1_values, P1_SESOI)
    p2 = normal_test(p2_90_values, 0.0)
    raw_p_values = {
        "P0": p0["one_sided_p"],
        "P1": p1["one_sided_p"],
        "P2": p2["one_sided_p"],
    }
    adjusted = holm_adjust(raw_p_values)

    p0_pass = p0["one_sided_95_lower"] > P0_SESOI
    p1_pass = p0_pass and p1["one_sided_95_lower"] > P1_SESOI
    p2_pass = p1_pass and p2["one_sided_95_lower"] > 0.0

    if not p0_pass:
        classification = "D2-S0"
        label = "source_model_mediated_capability_development_not_established"
    elif not p1_pass:
        classification = "D2-S1"
        label = "destination_reproduction_beyond_description_not_established"
    elif not p2_pass:
        classification = "D2-S2"
        label = "destination_reproduction_established_fidelity_not_established"
    else:
        classification = "D2-S3"
        label = "stochastic_model_mediated_capability_reproduction_supported"

    mean_fresh = _mean(fresh)
    mean_description = _mean(description)
    mean_reproduced = _mean(reproduced)
    mean_source = _mean(source)
    ratio = mean_reproduced / mean_source if mean_source > 0.0 else math.nan

    return {
        "classification": classification,
        "classification_label": label,
        "analyzable_pairs": n,
        "minimum_analyzable_pairs": MIN_ANALYZABLE,
        "alpha_one_sided": ALPHA,
        "gatekeeping_order": ["P0", "P1", "P2"],
        "threshold_provenance": {
            "P0": "conventional_materiality_10pp",
            "P1": "conventional_materiality_10pp",
            "P2": "conventional_fidelity_90_percent_source_accuracy",
        },
        "arm_means": {
            "fresh": mean_fresh,
            "description_only": mean_description,
            "reproduced": mean_reproduced,
            "source_developed": mean_source,
        },
        "P0": {**p0, "gate_pass": p0_pass},
        "P1": {**p1, "gate_entered": p0_pass, "gate_pass": p1_pass},
        "P2": {
            **p2,
            "gate_entered": p0_pass and p1_pass,
            "gate_pass": p2_pass,
            "fidelity_fraction": FIDELITY_FRACTION,
            "aggregate_fidelity_ratio": ratio,
            "raw_reproduced_minus_source_mean": _mean(p2_raw_values),
            "raw_reproduced_minus_source_sd": _sd(p2_raw_values),
        },
        "raw_p_values": raw_p_values,
        "holm_adjusted_p_values_diagnostic": adjusted,
        "bootstrap_sensitivity": bootstrap_sensitivity(
            fresh,
            description,
            reproduced,
            source,
        ),
    }
