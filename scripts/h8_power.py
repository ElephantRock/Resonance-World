#!/usr/bin/env python3
"""Prospective H8 paired-binary power calculation using exact McNemar rejection."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

N = 384
FAMILY_COUNT = 4
UNITS_PER_FAMILY = 96
DISCORDANCE = 0.60
PLANNING_RISK_DIFFERENCE = 0.15
ALPHA = 0.05 / 3.0
TARGET_POWER = 0.90


def binomial_pmf(k: int, n: int, p: float) -> float:
    return math.comb(n, k) * (p**k) * ((1.0 - p) ** (n - k))


def exact_two_sided_sign_p(k: int, n: int) -> float:
    """Two-sided exact binomial p-value for p=0.5, as used by exact McNemar."""
    if n == 0:
        return 1.0
    tail_k = min(k, n - k)
    lower = sum(math.comb(n, i) for i in range(tail_k + 1)) / (2.0**n)
    return min(1.0, 2.0 * lower)


def rejection_threshold(discordant_n: int, alpha: float) -> int | None:
    """Smallest treatment-win count that rejects in the positive direction."""
    for treatment_wins in range(discordant_n // 2 + 1, discordant_n + 1):
        if exact_two_sided_sign_p(treatment_wins, discordant_n) <= alpha:
            return treatment_wins
    return None


def exact_unconditional_power(
    n: int,
    discordance: float = DISCORDANCE,
    risk_difference: float = PLANNING_RISK_DIFFERENCE,
    alpha: float = ALPHA,
) -> float:
    """Integrate exact conditional McNemar power over the random discordant count."""
    treatment_only = (discordance + risk_difference) / 2.0
    control_only = (discordance - risk_difference) / 2.0
    if min(treatment_only, control_only) < 0.0:
        raise ValueError("risk difference incompatible with discordance")
    conditional_treatment_win = treatment_only / discordance
    power = 0.0
    for discordant_n in range(n + 1):
        p_discordant_n = binomial_pmf(discordant_n, n, discordance)
        threshold = rejection_threshold(discordant_n, alpha)
        if threshold is None:
            continue
        conditional_reject = sum(
            binomial_pmf(k, discordant_n, conditional_treatment_win)
            for k in range(threshold, discordant_n + 1)
        )
        power += p_discordant_n * conditional_reject
    return power


def report() -> dict[str, object]:
    power = exact_unconditional_power(N)
    if N != FAMILY_COUNT * UNITS_PER_FAMILY:
        raise AssertionError("H8 balanced-panel arithmetic drift")
    if power < TARGET_POWER:
        raise AssertionError("registered H8 panel no longer meets target planning power")
    return {
        "schema": "h8-power-v0.1",
        "paired_n": N,
        "family_count": FAMILY_COUNT,
        "units_per_family": UNITS_PER_FAMILY,
        "planning_alternative": {
            "paired_risk_difference": PLANNING_RISK_DIFFERENCE,
            "total_discordance_probability": DISCORDANCE,
            "two_sided_per_comparison_alpha": ALPHA,
            "interpretation": "planning alternative only; not a World SESOI or materiality threshold",
        },
        "method": "exact unconditional power integrating exact two-sided McNemar rejection over discordant-pair count",
        "estimated_power": power,
        "target_power": TARGET_POWER,
        "passes_target": power >= TARGET_POWER,
    }


def canonical_bytes(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    value = report()
    payload = canonical_bytes(value)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(payload)
    print(payload.decode().rstrip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
