"""Frozen sample-size calculations for D2-C2 confirmatory design."""
from __future__ import annotations

import math
import statistics

ALPHA_ONE_SIDED = 0.05
TARGET_POWER = 0.90
P0_SD_R2 = 0.26198929912716445
P1_SD_R2 = 0.2878685525920269
P2_90_SD_R2 = 0.3092419446924089
MIN_ANALYZABLE = 330
ATTEMPTED = 360

_NORMAL = statistics.NormalDist()
_Z_ALPHA = _NORMAL.inv_cdf(1.0 - ALPHA_ONE_SIDED)
_Z_TARGET = _NORMAL.inv_cdf(TARGET_POWER)


def required_n(sd: float, distance_above_null: float) -> int:
    raw = ((_Z_ALPHA + _Z_TARGET) * sd / distance_above_null) ** 2
    return math.ceil(raw)


def achieved_probability(n: int, sd: float, distance_above_null: float) -> float:
    standardized = math.sqrt(n) * distance_above_null / sd - _Z_ALPHA
    return _NORMAL.cdf(standardized)


def report() -> dict[str, object]:
    return {
        "schema": "d2-c2-confirmatory-sample-size-v0.1",
        "alpha_one_sided": ALPHA_ONE_SIDED,
        "target_power": TARGET_POWER,
        "planning_principle": "R2 variances only; R2 observed effects are not planning effects",
        "P0": {
            "r2_paired_sd": P0_SD_R2,
            "null_threshold": 0.10,
            "planning_alternative_mean": 0.20,
            "required_n": required_n(P0_SD_R2, 0.10),
        },
        "P1": {
            "r2_paired_sd": P1_SD_R2,
            "null_threshold": 0.10,
            "planning_alternative_mean": 0.20,
            "required_n": required_n(P1_SD_R2, 0.10),
        },
        "P2": {
            "contrast": "reproduced - 0.90 * source_developed",
            "r2_paired_sd": P2_90_SD_R2,
            "null_threshold": 0.0,
            "planning_true_fidelity_ratio": 1.0,
            "planning_source_accuracy": 0.50,
            "source_accuracy_provenance": "prospectively fixed R2 readiness floor",
            "required_n": required_n(P2_90_SD_R2, 0.05),
            "power_at_minimum_analyzable": achieved_probability(
                MIN_ANALYZABLE, P2_90_SD_R2, 0.05
            ),
            "power_at_attempted_if_all_complete": achieved_probability(
                ATTEMPTED, P2_90_SD_R2, 0.05
            ),
        },
        "minimum_analyzable_pairs": MIN_ANALYZABLE,
        "attempted_pairs": ATTEMPTED,
    }
