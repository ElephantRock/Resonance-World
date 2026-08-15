#!/usr/bin/env python3
"""Run development-only D1-0 calibration and prospective power planning."""
from __future__ import annotations

import argparse
import json
import math
import statistics
from pathlib import Path
from statistics import NormalDist

from d1_capability_core import canonical_bytes, mean, pstdev, run_field_pair

CALIBRATION_SEEDS = tuple(range(10_000, 10_064))
DEFAULT_CONFIG = {
    "population_size": 8,
    "cycles": 96,
    "target_share": 0.60,
    "exploration_rate": 0.30,
    "base_success": 0.30,
    "practice_gain": 0.11,
    "maximum_success": 0.92,
    "failure_learning": 0.20,
    "selection_trials": 64,
    "evaluation_trials": 256,
}


def planned_n(effect: float, sd: float, *, alpha: float = 0.05, power: float = 0.90) -> int:
    if effect <= 0:
        return 10_000
    z_alpha = NormalDist().inv_cdf(1.0 - alpha)
    z_power = NormalDist().inv_cdf(power)
    raw = ((z_alpha + z_power) * sd / effect) ** 2 if sd > 0 else 1.0
    return max(32, math.ceil(raw))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    rows = [run_field_pair(seed, DEFAULT_CONFIG) for seed in CALIBRATION_SEEDS]
    if any(row["forbidden_private_export_keys_found"] for row in rows):
        raise AssertionError("private state leaked into capability artifact")
    if not all(row["source_destination_identity_disjoint"] for row in rows):
        raise AssertionError("source and destination identities must be disjoint")

    source = [row["scores"]["source_developed"] for row in rows]
    reproduced = [row["scores"]["reproduced_protocol"] for row in rows]
    fresh = [row["scores"]["fresh_no_development"] for row in rows]
    oracle = [row["scores"]["private_state_oracle"] for row in rows]
    source_uplift = [a - b for a, b in zip(source, fresh, strict=True)]
    reproduced_uplift = [a - b for a, b in zip(reproduced, fresh, strict=True)]
    reproduction_gap = [a - b for a, b in zip(reproduced, source, strict=True)]

    conventional_retention_fraction = 0.90
    ni_margin = (1.0 - conventional_retention_fraction) * mean(source_uplift)
    p1_n = planned_n(mean(reproduced_uplift), pstdev(reproduced_uplift))
    p2_distance_from_null = mean(reproduction_gap) + ni_margin
    p2_n = planned_n(p2_distance_from_null, pstdev(reproduction_gap))
    confirmatory_n = max(p1_n, p2_n)

    report = {
        "schema": "d1-calibration-v0.1",
        "status": "development_only_not_confirmatory",
        "calibration_seed_count": len(CALIBRATION_SEEDS),
        "calibration_seed_min": min(CALIBRATION_SEEDS),
        "calibration_seed_max": max(CALIBRATION_SEEDS),
        "config": DEFAULT_CONFIG,
        "means": {
            "source_developed": mean(source),
            "reproduced_protocol": mean(reproduced),
            "fresh_no_development": mean(fresh),
            "private_state_oracle": mean(oracle),
            "source_uplift_vs_fresh": mean(source_uplift),
            "reproduced_uplift_vs_fresh": mean(reproduced_uplift),
            "reproduced_minus_source": mean(reproduction_gap),
        },
        "population_sd": {
            "source_uplift_vs_fresh": pstdev(source_uplift),
            "reproduced_uplift_vs_fresh": pstdev(reproduced_uplift),
            "reproduced_minus_source": pstdev(reproduction_gap),
        },
        "planning": {
            "alpha_one_sided": 0.05,
            "target_power": 0.90,
            "minimum_n_floor": 32,
            "p1_planned_n": p1_n,
            "p2_planned_n": p2_n,
            "recommended_confirmatory_n": confirmatory_n,
            "p1_planning_effect": mean(reproduced_uplift),
            "p1_planning_effect_type": "calibration_estimate_not_SESOI",
            "p2_conventional_retention_fraction": conventional_retention_fraction,
            "p2_noninferiority_margin": ni_margin,
            "p2_margin_type": "conventional",
            "p2_margin_provenance": "10% of D1-0 calibrated source-developed uplift; 90% reproduction-fidelity product convention, not natural materiality",
            "p2_distance_from_null_at_calibration_mean": p2_distance_from_null,
        },
        "integrity": {
            "source_destination_identity_disjoint": True,
            "forbidden_private_state_export_absent": True,
            "artifact_schema": "d1-capability-artifact-v0.1",
        },
        "artifact_bytes_mean": statistics.mean(
            row["capability_artifact_bytes"] for row in rows
        ),
        "rows": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(canonical_bytes(report))
    print(
        json.dumps(
            {
                key: report[key]
                for key in ("means", "population_sd", "planning", "integrity")
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
