"""Frozen per-schema statistics for D2c schema-generalization evaluation."""

from __future__ import annotations

import math
import random
import statistics
from typing import Any

ALPHA = 0.05
P0_SESOI = 0.10
P1_SESOI = 0.10
FIDELITY_FRACTION = 0.90
MIN_ANALYZABLE_PER_SCHEMA = 165
BOOTSTRAP_REPS = 50_000
BOOTSTRAP_SEED = 2026090101

_NORMAL = statistics.NormalDist()
_Z_ONE_SIDED = _NORMAL.inv_cdf(1.0 - ALPHA)


def _mean(values: list[float]) -> float:
    return statistics.fmean(values)


def _sd(values: list[float]) -> float:
    return statistics.stdev(values)


def normal_test(values: list[float], threshold: float) -> dict[str, float]:
    n = len(values)
    if n < 2:
        raise ValueError("at least two paired observations required")
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
    }


def _quantile(sorted_values: list[float], probability: float) -> float:
    if not sorted_values:
        raise ValueError("empty bootstrap values")
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
    *,
    seed: int,
) -> dict[str, Any]:
    n = len(source)
    if not (n == len(fresh) == len(description) == len(reproduced)):
        raise ValueError("arm length mismatch")
    rng = random.Random(seed)
    metrics: dict[str, list[float]] = {
        "p0_source_minus_fresh": [],
        "p1_reproduced_minus_description": [],
        "p2_90": [],
        "raw_reproduced_minus_source": [],
        "fidelity_ratio": [],
    }
    for _ in range(BOOTSTRAP_REPS):
        indices = [rng.randrange(n) for _j in range(n)]
        mf = sum(fresh[i] for i in indices) / n
        md = sum(description[i] for i in indices) / n
        mr = sum(reproduced[i] for i in indices) / n
        ms = sum(source[i] for i in indices) / n
        metrics["p0_source_minus_fresh"].append(ms - mf)
        metrics["p1_reproduced_minus_description"].append(mr - md)
        metrics["p2_90"].append(mr - FIDELITY_FRACTION * ms)
        metrics["raw_reproduced_minus_source"].append(mr - ms)
        metrics["fidelity_ratio"].append(mr / ms if ms > 0 else math.nan)
    out: dict[str, Any] = {
        "replicates": BOOTSTRAP_REPS,
        "seed": seed,
        "interval": "paired percentile 95%",
        "metrics": {},
    }
    for name, values in metrics.items():
        finite = sorted(v for v in values if math.isfinite(v))
        out["metrics"][name] = {
            "lower_2_5": _quantile(finite, 0.025),
            "median": _quantile(finite, 0.5),
            "upper_97_5": _quantile(finite, 0.975),
        }
    return out


def evaluate_schema_scores(
    fresh: list[float],
    description: list[float],
    reproduced: list[float],
    source: list[float],
    *,
    bootstrap_seed_offset: int = 0,
) -> dict[str, Any]:
    n = len(source)
    if not (n == len(fresh) == len(description) == len(reproduced)):
        raise ValueError("arm length mismatch")
    if n < MIN_ANALYZABLE_PER_SCHEMA:
        return {
            "minimum_n_pass": False,
            "analyzable_pairs": n,
            "minimum_analyzable_pairs": MIN_ANALYZABLE_PER_SCHEMA,
            "P0": None,
            "P1": None,
            "P2": None,
            "all_gates_pass": False,
            "bootstrap_sensitivity": None,
        }

    p0_values = [s - f for s, f in zip(source, fresh, strict=True)]
    p1_values = [r - d for r, d in zip(reproduced, description, strict=True)]
    p2_values = [r - FIDELITY_FRACTION * s for r, s in zip(reproduced, source, strict=True)]
    raw_values = [r - s for r, s in zip(reproduced, source, strict=True)]

    p0 = normal_test(p0_values, P0_SESOI)
    p1 = normal_test(p1_values, P1_SESOI)
    p2 = normal_test(p2_values, 0.0)

    p0_pass = p0["one_sided_95_lower"] > P0_SESOI
    p1_pass = p0_pass and p1["one_sided_95_lower"] > P1_SESOI
    p2_pass = p1_pass and p2["one_sided_95_lower"] > 0.0

    mean_fresh = _mean(fresh)
    mean_description = _mean(description)
    mean_reproduced = _mean(reproduced)
    mean_source = _mean(source)
    fidelity_ratio = mean_reproduced / mean_source if mean_source > 0 else math.nan

    return {
        "minimum_n_pass": True,
        "analyzable_pairs": n,
        "minimum_analyzable_pairs": MIN_ANALYZABLE_PER_SCHEMA,
        "alpha_one_sided": ALPHA,
        "gatekeeping_order": ["P0", "P1", "P2"],
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
            "aggregate_fidelity_ratio": fidelity_ratio,
            "raw_reproduced_minus_source_mean": _mean(raw_values),
            "raw_reproduced_minus_source_sd": _sd(raw_values),
        },
        "all_gates_pass": p0_pass and p1_pass and p2_pass,
        "bootstrap_sensitivity": bootstrap_sensitivity(
            fresh,
            description,
            reproduced,
            source,
            seed=BOOTSTRAP_SEED + bootstrap_seed_offset,
        ),
    }
