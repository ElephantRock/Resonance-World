"""Transferable institutional model memory for PIANO Phase 5B.

The memory does not store a winning routing policy. It estimates which of two
structural outcome hypotheses is better supported by pre-turnover episodes, then
combines that posterior with the current roster to forecast both routing policies.
The hidden experimental regime is never read by this module.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from resonance_world import w5_institution as w5

_STRATEGIES = ("specialist", "balanced")
_HYPOTHESES = ("role_specific", "cross_coverage")


@dataclass(frozen=True, slots=True)
class TransferPosterior:
    role_specific: float
    cross_coverage: float
    evidence_episodes: int

    def __post_init__(self) -> None:
        if self.evidence_episodes < 0:
            raise ValueError("evidence_episodes must be non-negative")
        if not 0.0 <= self.role_specific <= 1.0:
            raise ValueError("role_specific posterior must lie in [0, 1]")
        if not 0.0 <= self.cross_coverage <= 1.0:
            raise ValueError("cross_coverage posterior must lie in [0, 1]")
        if abs(self.role_specific + self.cross_coverage - 1.0) > 1e-9:
            raise ValueError("transfer posterior must sum to one")

    def as_dict(self) -> dict[str, object]:
        return {
            "role_specific": self.role_specific,
            "cross_coverage": self.cross_coverage,
            "evidence_episodes": self.evidence_episodes,
        }


def neutral_posterior() -> TransferPosterior:
    return TransferPosterior(0.5, 0.5, 0)


def _safe_probability(value: float) -> float:
    return min(1.0 - 1e-9, max(1e-9, float(value)))


def structural_probabilities(
    environment: w5.InstitutionEnvironment,
    lead,
    support,
    mission,
) -> dict[str, float]:
    """Return generic role-specific and cross-coverage success predictions."""

    lead_lead = environment.joint.role_probability(lead, mission.public.lead_skill)
    lead_support = environment.joint.role_probability(lead, mission.public.support_skill)
    support_lead = environment.joint.role_probability(support, mission.public.lead_skill)
    support_support = environment.joint.role_probability(support, mission.public.support_skill)
    role_specific = lead_lead * support_support
    cross_coverage = math.sqrt(lead_lead * lead_support) * math.sqrt(
        support_lead * support_support
    )
    return {
        "role_specific": _safe_probability(role_specific),
        "cross_coverage": _safe_probability(cross_coverage),
    }


def fit_transfer_posterior(organization, mission) -> TransferPosterior:
    """Infer a two-hypothesis posterior from organization-owned formation episodes."""

    episodes = [
        episode
        for episode in organization.memory.episodes
        if episode.context == mission.public.context
        and episode.strategy in _STRATEGIES
    ]
    if not episodes:
        raise ValueError("transfer memory requires context-indexed formation episodes")

    environment = w5.InstitutionEnvironment()
    log_likelihood = {hypothesis: math.log(0.5) for hypothesis in _HYPOTHESES}
    for episode in episodes:
        if episode.lead_agent_id not in organization.members:
            raise ValueError("formation lead is absent from source organization")
        if episode.support_agent_id not in organization.members:
            raise ValueError("formation support is absent from source organization")
        predictions = structural_probabilities(
            environment,
            organization.members[episode.lead_agent_id],
            organization.members[episode.support_agent_id],
            mission,
        )
        for hypothesis in _HYPOTHESES:
            probability = predictions[hypothesis]
            log_likelihood[hypothesis] += math.log(
                probability if episode.success else 1.0 - probability
            )

    maximum = max(log_likelihood.values())
    weights = {
        hypothesis: math.exp(log_likelihood[hypothesis] - maximum)
        for hypothesis in _HYPOTHESES
    }
    normalizer = sum(weights.values())
    return TransferPosterior(
        role_specific=weights["role_specific"] / normalizer,
        cross_coverage=weights["cross_coverage"] / normalizer,
        evidence_episodes=len(episodes),
    )


def forecast_strategies(organization, mission, posterior: TransferPosterior) -> dict[str, float]:
    """Forecast each executable routing policy on the organization's current roster."""

    environment = w5.InstitutionEnvironment()
    result: dict[str, float] = {}
    for strategy in _STRATEGIES:
        decision = w5._forced_decision(organization, mission.public, strategy)
        structural = structural_probabilities(
            environment,
            decision.lead,
            decision.support,
            mission,
        )
        result[strategy] = (
            posterior.role_specific * structural["role_specific"]
            + posterior.cross_coverage * structural["cross_coverage"]
        )
    return result


def select_forecast_strategy(forecasts: dict[str, float]) -> str:
    if set(forecasts) != set(_STRATEGIES):
        raise ValueError("forecasts must contain the binary Phase-5B strategies")
    return max(
        _STRATEGIES,
        key=lambda strategy: (float(forecasts[strategy]), -_STRATEGIES.index(strategy)),
    )


def model_memory_payload(
    organization,
    mission,
    *,
    retained: bool,
) -> dict[str, object]:
    posterior = fit_transfer_posterior(organization, mission) if retained else neutral_posterior()
    forecasts = forecast_strategies(organization, mission, posterior)
    return {
        "structural_posterior": posterior.as_dict(),
        "current_roster_strategy_forecast": {
            strategy: float(forecasts[strategy]) for strategy in _STRATEGIES
        },
        "forecast_semantics": {
            "role_specific": (
                "success is explained by distinct lead-skill and support-skill role competence"
            ),
            "cross_coverage": (
                "success is explained by both selected members covering both mission skills"
            ),
        },
    }
