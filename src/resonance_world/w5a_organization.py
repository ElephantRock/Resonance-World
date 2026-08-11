"""Minimal organization-owned learning substrate for W5A.

Organization state may affect routing and role decisions, but the mission outcome
law never reads organization identity, age, history, or memory directly.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Literal

from .w4a_joint_learning import IndividualState, JointAction, JointEnvironment, JointMission

Strategy = Literal["specialist", "balanced", "continuity"]
STRATEGIES: tuple[Strategy, ...] = ("specialist", "balanced", "continuity")


def _uniform(*parts: object) -> float:
    payload = "|".join(str(part) for part in parts).encode()
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big") / 2**64


@dataclass(frozen=True, slots=True)
class OrganizationEpisode:
    mission_id: str
    context: str
    strategy: Strategy
    lead_agent_id: str
    support_agent_id: str
    success: bool


@dataclass(slots=True)
class OrganizationMemory:
    episodes: list[OrganizationEpisode] = field(default_factory=list)
    strategy_attempts: dict[str, dict[Strategy, int]] = field(default_factory=dict)
    strategy_successes: dict[str, dict[Strategy, int]] = field(default_factory=dict)
    last_successful_pair: dict[str, tuple[str, str]] = field(default_factory=dict)

    def observe(self, episode: OrganizationEpisode) -> None:
        self.episodes.append(episode)
        attempts = self.strategy_attempts.setdefault(
            episode.context, {strategy: 0 for strategy in STRATEGIES}
        )
        successes = self.strategy_successes.setdefault(
            episode.context, {strategy: 0 for strategy in STRATEGIES}
        )
        attempts[episode.strategy] += 1
        if episode.success:
            successes[episode.strategy] += 1
            self.last_successful_pair[episode.context] = (
                episode.lead_agent_id,
                episode.support_agent_id,
            )

    def best_strategy(self, context: str) -> Strategy | None:
        attempts = self.strategy_attempts.get(context)
        successes = self.strategy_successes.get(context)
        if not attempts or not successes or sum(attempts.values()) == 0:
            return None
        scored = []
        for strategy in STRATEGIES:
            count = attempts[strategy]
            if count == 0:
                continue
            scored.append((successes[strategy] / count, count, strategy))
        return max(scored)[2] if scored else None

    def snapshot(self) -> dict[str, object]:
        return {
            "episode_count": len(self.episodes),
            "last_successful_pair": dict(self.last_successful_pair),
            "strategy_attempts": self.strategy_attempts,
            "strategy_successes": self.strategy_successes,
        }


@dataclass(slots=True)
class OrganizationState:
    organization_id: str
    members: dict[str, IndividualState]
    memory: OrganizationMemory = field(default_factory=OrganizationMemory)

    def replace_members(self, members: list[IndividualState]) -> None:
        if len({member.agent_id for member in members}) != len(members):
            raise ValueError("organization roster requires unique agent ids")
        self.members = {member.agent_id: member for member in members}

    def reset_memory(self) -> None:
        self.memory = OrganizationMemory()


@dataclass(frozen=True, slots=True)
class OrganizationDecision:
    strategy: Strategy
    lead: IndividualState
    support: IndividualState
    lead_action: JointAction
    support_action: JointAction


@dataclass(frozen=True, slots=True)
class OrganizationController:
    def _default_strategy(self, organization_id: str, context: str) -> Strategy:
        index = int(_uniform("w5a-default", organization_id, context) * len(STRATEGIES))
        return STRATEGIES[min(index, len(STRATEGIES) - 1)]

    def _specialist_pair(
        self, members: list[IndividualState], mission: JointMission
    ) -> tuple[IndividualState, IndividualState]:
        lead = max(members, key=lambda item: (item.practice(mission.lead_skill), item.agent_id))
        support_pool = [item for item in members if item.agent_id != lead.agent_id]
        support = max(
            support_pool,
            key=lambda item: (item.practice(mission.support_skill), item.agent_id),
        )
        return lead, support

    def _balanced_pair(
        self, members: list[IndividualState], mission: JointMission
    ) -> tuple[IndividualState, IndividualState]:
        ranked = sorted(
            members,
            key=lambda item: (
                min(
                    item.practice(mission.lead_skill),
                    item.practice(mission.support_skill),
                ),
                item.agent_id,
            ),
            reverse=True,
        )
        first, second = ranked[:2]
        if first.practice(mission.lead_skill) >= second.practice(mission.lead_skill):
            return first, second
        return second, first

    def select(
        self,
        organization: OrganizationState,
        mission: JointMission,
    ) -> OrganizationDecision:
        members = list(organization.members.values())
        if len(members) < 2:
            raise ValueError("organization requires at least two members")
        strategy = organization.memory.best_strategy(mission.context)
        if strategy is None:
            strategy = self._default_strategy(organization.organization_id, mission.context)

        if strategy == "continuity":
            prior = organization.memory.last_successful_pair.get(mission.context)
            if prior and all(agent_id in organization.members for agent_id in prior):
                lead = organization.members[prior[0]]
                support = organization.members[prior[1]]
            else:
                lead, support = self._balanced_pair(members, mission)
        elif strategy == "balanced":
            lead, support = self._balanced_pair(members, mission)
        else:
            lead, support = self._specialist_pair(members, mission)

        return OrganizationDecision(
            strategy=strategy,
            lead=lead,
            support=support,
            lead_action=JointAction(lead.agent_id, "lead"),
            support_action=JointAction(support.agent_id, "support"),
        )


@dataclass(frozen=True, slots=True)
class OrganizationEnvironment:
    joint_environment: JointEnvironment = field(default_factory=JointEnvironment)

    def evaluate(
        self,
        first: IndividualState,
        second: IndividualState,
        mission: JointMission,
        first_action: JointAction,
        second_action: JointAction,
        *,
        seed: int,
    ) -> bool:
        return self.joint_environment.evaluate(
            first,
            second,
            mission,
            first_action,
            second_action,
            seed=seed,
        )


@dataclass(slots=True)
class OrganizationSession:
    controller: OrganizationController = field(default_factory=OrganizationController)
    environment: OrganizationEnvironment = field(default_factory=OrganizationEnvironment)

    def run_mission(
        self,
        organization: OrganizationState,
        mission: JointMission,
        *,
        seed: int,
    ) -> OrganizationEpisode:
        decision = self.controller.select(organization, mission)
        success = self.environment.evaluate(
            decision.lead,
            decision.support,
            mission,
            decision.lead_action,
            decision.support_action,
            seed=seed,
        )
        episode = OrganizationEpisode(
            mission_id=mission.mission_id,
            context=mission.context,
            strategy=decision.strategy,
            lead_agent_id=decision.lead.agent_id,
            support_agent_id=decision.support.agent_id,
            success=success,
        )
        organization.memory.observe(episode)
        return episode
