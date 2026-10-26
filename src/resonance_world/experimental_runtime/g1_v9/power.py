"""Statistical planning analysis for the G1 v9 scientific gate.

Pure planning arithmetic with explicitly declared assumptions. This
module is computed **before** any live results exist; it does not derive
the practical-effect threshold from scripted-policy behavior, and it
does not authorize execution. The independent world is the unit of
analysis.

Model: each world contributes one paired post-switch accuracy
difference D = post_accuracy_A - post_accuracy_B (proportions on [0,
1]). D is modeled as normal with mean ``true_delta`` and standard
deviation ``sigma_d`` composed of a world-level heterogeneity component
and the binomial noise of the paired post-switch decisions (``m``
decisions per arm):

    sigma_w = sqrt(2 * p_bar * (1 - p_bar) / m)
    sigma_d = sqrt(sigma_h ** 2 + sigma_w ** 2)
    SE      = sigma_d / sqrt(N)

Power for a two-sided test at ``alpha`` is
``P(|Z| > z_{1-alpha/2})`` under the alternative ``E[D] = true_delta``.

Intra-world decision correlation: decisions inside one world follow an
adapting policy over repeated contexts, so they may be positively
correlated. Planning therefore applies a design effect
``DEFF = 1 + (m - 1) * rho`` to the binomial component, with an
assumed intra-world correlation ``rho``; the effective per-arm
decision count is ``m / DEFF``. MDE values are scenario-specific
under declared rho assumptions - they are not general guarantees.
"""

from __future__ import annotations

import dataclasses
import math
from dataclasses import dataclass
from statistics import NormalDist


@dataclass(frozen=True, slots=True)
class PlanningAssumptions:
    """Declared planning assumptions (pinned in the freeze manifest)."""

    worlds: int
    decisions_per_arm_post: int
    mean_accuracy: float = 0.5
    world_heterogeneity_sd: float = 0.10
    decision_correlation_rho: float = 0.0
    alpha: float = 0.05

    def __post_init__(self) -> None:
        if self.worlds < 2:
            raise ValueError("worlds must be at least 2")
        if self.decisions_per_arm_post <= 0:
            raise ValueError("decisions_per_arm_post must be positive")
        for name in ("mean_accuracy", "world_heterogeneity_sd"):
            value = getattr(self, name)
            if value < 0 or value > 1:
                raise ValueError(f"{name} must lie in [0, 1]")
        if self.decision_correlation_rho < 0 or self.decision_correlation_rho >= 1:
            raise ValueError("decision_correlation_rho must lie in [0, 1)")
        if not 0 < self.alpha < 1:
            raise ValueError("alpha must lie in (0, 1)")

    @property
    def effective_decisions_per_arm(self) -> float:
        """Decisions per arm after the intra-world design effect."""

        deff = 1 + (self.decisions_per_arm_post - 1) * self.decision_correlation_rho
        return self.decisions_per_arm_post / deff

    @property
    def sigma_w(self) -> float:
        """Within-world binomial noise of the paired difference."""

        p = self.mean_accuracy
        return math.sqrt(2 * p * (1 - p) / self.effective_decisions_per_arm)

    @property
    def sigma_d(self) -> float:
        """Standard deviation of the per-world paired difference."""

        return math.sqrt(self.world_heterogeneity_sd**2 + self.sigma_w**2)

    @property
    def standard_error(self) -> float:
        """Standard error of the mean paired difference over the worlds."""

        return self.sigma_d / math.sqrt(self.worlds)


def _two_sided_power(standard_error: float, true_delta: float, alpha: float) -> float:
    if standard_error <= 0:
        return 1.0 if true_delta != 0 else alpha
    nd = NormalDist()
    z_alpha = nd.inv_cdf(1 - alpha / 2)
    shift = abs(true_delta) / standard_error
    return nd.cdf(-z_alpha - shift) + (1 - nd.cdf(z_alpha - shift))


def power(assumptions: PlanningAssumptions, true_delta: float) -> float:
    """Two-sided power to detect ``true_delta`` under the assumptions."""

    if true_delta < 0:
        raise ValueError("true_delta must be non-negative for planning")
    return _two_sided_power(assumptions.standard_error, true_delta, assumptions.alpha)


def minimum_detectable_delta(
    assumptions: PlanningAssumptions, target_power: float = 0.8
) -> float:
    """Smallest effect detected with ``target_power`` (bisection search)."""

    if not 0 < target_power < 1:
        raise ValueError("target_power must lie in (0, 1)")
    low, high = 0.0, 1.0
    if power(assumptions, high) < target_power:
        return high
    for _ in range(80):
        mid = (low + high) / 2
        if power(assumptions, mid) >= target_power:
            high = mid
        else:
            low = mid
    return high


def sensitivity_table(
    assumptions: PlanningAssumptions,
    *,
    heterogeneity_levels: tuple[float, ...] = (0.0, 0.05, 0.10, 0.15, 0.20),
    deltas: tuple[float, ...] = (0.05, 0.10, 0.15, 0.20, 0.30),
) -> list[dict[str, float]]:
    """Power for each (heterogeneity, true delta) planning scenario."""

    rows = []
    for heterogeneity in heterogeneity_levels:
        scenario = dataclasses.replace(
            assumptions, world_heterogeneity_sd=heterogeneity
        )
        row: dict[str, float] = {
            "world_heterogeneity_sd": heterogeneity,
            "sigma_d": round(scenario.sigma_d, 6),
            "mde_80": round(minimum_detectable_delta(scenario, 0.8), 6),
            "mde_90": round(minimum_detectable_delta(scenario, 0.9), 6),
        }
        for delta in deltas:
            row[f"power@{delta:.2f}"] = round(power(scenario, delta), 6)
        rows.append(row)
    return rows


def intra_world_correlation_table(
    assumptions: PlanningAssumptions,
    *,
    rho_levels: tuple[float, ...] = (0.0, 0.05, 0.10, 0.20),
) -> list[dict[str, float]]:
    """Sensitivity of the MDE to intra-world decision correlation.

    Each row reports the assumed rho, the resulting effective per-arm
    decision count, and the 80%-power MDE under the base heterogeneity.
    These are scenario values under declared assumptions - not an
    empirical estimate of the correlation, and not a general guarantee.
    """

    rows = []
    for rho in rho_levels:
        scenario = dataclasses.replace(assumptions, decision_correlation_rho=rho)
        rows.append(
            {
                "decision_correlation_rho": rho,
                "effective_decisions_per_arm": round(
                    scenario.effective_decisions_per_arm, 4
                ),
                "mde_80": round(minimum_detectable_delta(scenario, 0.8), 6),
            }
        )
    return rows
