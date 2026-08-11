"""Minimal joint-learning substrate for W4A and W4A.1.

Relationship and teamwork state may affect agent decisions, but the environment
outcome law never reads relationship age, partner history, teamwork history, or
shared pair memory directly.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from typing import Literal

Role = Literal["lead", "support"]


def _pair_key(first: str, second: str) -> tuple[str, str]:
    return tuple(sorted((first, second)))  # type: ignore[return-value]


def _uniform(*parts: object) -> float:
    payload = "|".join(str(part) for part in parts).encode()
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big") / 2**64


def _other(role: Role) -> Role:
    return "support" if role == "lead" else "lead"


@dataclass(frozen=True, slots=True)
class IndividualState:
    agent_id: str
    practice_by_skill: dict[str, int]

    def practice(self, skill: str) -> int:
        return max(0, int(self.practice_by_skill.get(skill, 0)))


@dataclass(frozen=True, slots=True)
class CommunicationPolicy:
    """Explicit communication budget shared by every comparison condition."""

    bandwidth_bits: int = 0

    def __post_init__(self) -> None:
        if self.bandwidth_bits < 0:
            raise ValueError("bandwidth_bits must be non-negative")


@dataclass(frozen=True, slots=True)
class JointMission:
    mission_id: str
    context: str
    lead_skill: str
    support_skill: str


@dataclass(frozen=True, slots=True)
class JointAction:
    agent_id: str
    role: Role


@dataclass(frozen=True, slots=True)
class JointEpisode:
    mission_id: str
    context: str
    agent_a: str
    action_a: Role
    agent_b: str
    action_b: Role
    success: bool

    def role_for(self, agent_id: str) -> Role:
        if agent_id == self.agent_a:
            return self.action_a
        if agent_id == self.agent_b:
            return self.action_b
        raise KeyError(agent_id)


@dataclass(slots=True)
class PartnerModel:
    """An agent-owned prediction model indexed by partner identity and context."""

    owner_agent_id: str
    partner_agent_id: str
    role_counts_by_context: dict[str, dict[Role, int]] = field(default_factory=dict)

    def observe(self, context: str, partner_role: Role) -> None:
        counts = self.role_counts_by_context.setdefault(context, {"lead": 0, "support": 0})
        counts[partner_role] += 1

    def predict(self, context: str) -> Role | None:
        counts = self.role_counts_by_context.get(context)
        if not counts or sum(counts.values()) == 0:
            return None
        if counts["lead"] == counts["support"]:
            return None
        return "lead" if counts["lead"] > counts["support"] else "support"

    def as_dict(self) -> dict[str, object]:
        return {
            "owner_agent_id": self.owner_agent_id,
            "partner_agent_id": self.partner_agent_id,
            "role_counts_by_context": self.role_counts_by_context,
        }


@dataclass(slots=True)
class GeneralTeamworkModel:
    """Agent-owned teamwork experience that is independent of partner identity."""

    owner_agent_id: str
    successful_roles_by_context: dict[str, dict[Role, int]] = field(default_factory=dict)
    collision_failures_by_context: dict[str, int] = field(default_factory=dict)
    episode_counts_by_context: dict[str, int] = field(default_factory=dict)

    def observe(self, context: str, own_role: Role, partner_role: Role, success: bool) -> None:
        self.episode_counts_by_context[context] = self.episode_counts_by_context.get(context, 0) + 1
        if success:
            counts = self.successful_roles_by_context.setdefault(
                context, {"lead": 0, "support": 0}
            )
            counts[own_role] += 1
        elif own_role == partner_role:
            self.collision_failures_by_context[context] = (
                self.collision_failures_by_context.get(context, 0) + 1
            )

    def successful_role(self, context: str) -> Role | None:
        counts = self.successful_roles_by_context.get(context)
        if not counts or sum(counts.values()) == 0:
            return None
        if counts["lead"] == counts["support"]:
            return None
        return "lead" if counts["lead"] > counts["support"] else "support"

    def learned_collision_convention(self, context: str) -> bool:
        return self.collision_failures_by_context.get(context, 0) > 0

    def as_dict(self) -> dict[str, object]:
        return {
            "collision_failures_by_context": self.collision_failures_by_context,
            "episode_counts_by_context": self.episode_counts_by_context,
            "owner_agent_id": self.owner_agent_id,
            "successful_roles_by_context": self.successful_roles_by_context,
        }


@dataclass(slots=True)
class SharedPairMemory:
    """Pair-owned episodic memory, distinct from either agent's competence."""

    agent_a: str
    agent_b: str
    episodes: list[JointEpisode] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.agent_a, self.agent_b = _pair_key(self.agent_a, self.agent_b)

    def append(self, episode: JointEpisode) -> None:
        if _pair_key(episode.agent_a, episode.agent_b) != (self.agent_a, self.agent_b):
            raise ValueError("episode pair does not match shared memory owner")
        self.episodes.append(episode)

    def last_for_context(self, context: str) -> JointEpisode | None:
        return next(
            (episode for episode in reversed(self.episodes) if episode.context == context),
            None,
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "agent_a": self.agent_a,
            "agent_b": self.agent_b,
            "episodes": [
                {
                    "mission_id": item.mission_id,
                    "context": item.context,
                    "agent_a": item.agent_a,
                    "action_a": item.action_a,
                    "agent_b": item.agent_b,
                    "action_b": item.action_b,
                    "success": item.success,
                }
                for item in self.episodes
            ],
        }


@dataclass(slots=True)
class RelationshipStateStore:
    """Persistent coordination state that intentionally excludes individual practice."""

    partner_models: dict[tuple[str, str], PartnerModel] = field(default_factory=dict)
    teamwork_models: dict[str, GeneralTeamworkModel] = field(default_factory=dict)
    pair_memories: dict[tuple[str, str], SharedPairMemory] = field(default_factory=dict)

    def partner_model(self, owner: str, partner: str) -> PartnerModel:
        key = (owner, partner)
        if key not in self.partner_models:
            self.partner_models[key] = PartnerModel(owner, partner)
        return self.partner_models[key]

    def teamwork_model(self, owner: str) -> GeneralTeamworkModel:
        if owner not in self.teamwork_models:
            self.teamwork_models[owner] = GeneralTeamworkModel(owner)
        return self.teamwork_models[owner]

    def pair_memory(self, first: str, second: str) -> SharedPairMemory:
        key = _pair_key(first, second)
        if key not in self.pair_memories:
            self.pair_memories[key] = SharedPairMemory(*key)
        return self.pair_memories[key]

    def record(self, episode: JointEpisode) -> None:
        self.partner_model(episode.agent_a, episode.agent_b).observe(
            episode.context, episode.action_b
        )
        self.partner_model(episode.agent_b, episode.agent_a).observe(
            episode.context, episode.action_a
        )
        self.teamwork_model(episode.agent_a).observe(
            episode.context, episode.action_a, episode.action_b, episode.success
        )
        self.teamwork_model(episode.agent_b).observe(
            episode.context, episode.action_b, episode.action_a, episode.success
        )
        self.pair_memory(episode.agent_a, episode.agent_b).append(episode)

    def reset_partner_models(self, first: str, second: str) -> None:
        self.partner_models.pop((first, second), None)
        self.partner_models.pop((second, first), None)

    def reset_general_teamwork(self, agent_id: str) -> None:
        self.teamwork_models.pop(agent_id, None)

    def clear_pair_memory(self, first: str, second: str) -> None:
        self.pair_memories.pop(_pair_key(first, second), None)

    def snapshot(self) -> dict[str, object]:
        partner_models = [
            model.as_dict()
            for _, model in sorted(self.partner_models.items(), key=lambda item: item[0])
        ]
        teamwork_models = [
            model.as_dict()
            for _, model in sorted(self.teamwork_models.items(), key=lambda item: item[0])
        ]
        pair_memories = [
            memory.as_dict()
            for _, memory in sorted(self.pair_memories.items(), key=lambda item: item[0])
        ]
        value = {
            "pair_memories": pair_memories,
            "partner_models": partner_models,
            "teamwork_models": teamwork_models,
        }
        if "practice_by_skill" in json.dumps(value, sort_keys=True):
            raise AssertionError("individual practice leaked into coordination-state snapshot")
        return value


@dataclass(frozen=True, slots=True)
class JointEnvironment:
    """Pure outcome law with no relationship or teamwork-state input."""

    base_success_probability: float = 0.35
    practice_gain: float = 0.16
    maximum_role_success: float = 0.94

    def __post_init__(self) -> None:
        if not 0 <= self.base_success_probability <= self.maximum_role_success <= 1:
            raise ValueError("invalid success probability bounds")
        if self.practice_gain < 0:
            raise ValueError("practice_gain must be non-negative")

    def role_probability(self, state: IndividualState, skill: str) -> float:
        return min(
            self.maximum_role_success,
            self.base_success_probability + self.practice_gain * math.sqrt(state.practice(skill)),
        )

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
        if first_action.agent_id != first.agent_id or second_action.agent_id != second.agent_id:
            raise ValueError("action identity does not match individual state")
        if first_action.role == second_action.role:
            return False

        role_state = {
            first_action.role: first,
            second_action.role: second,
        }
        lead_probability = self.role_probability(role_state["lead"], mission.lead_skill)
        support_probability = self.role_probability(role_state["support"], mission.support_skill)
        lead_ok = _uniform("w4a", mission.mission_id, seed, "lead") < lead_probability
        support_ok = _uniform("w4a", mission.mission_id, seed, "support") < support_probability
        return lead_ok and support_ok


@dataclass(frozen=True, slots=True)
class JointController:
    """Generic decision policy that may read learned coordination state."""

    def preferred_role(self, state: IndividualState, mission: JointMission) -> Role:
        lead = state.practice(mission.lead_skill)
        support = state.practice(mission.support_skill)
        if lead != support:
            return "lead" if lead > support else "support"
        return "lead" if _uniform("w4a-role", state.agent_id, mission.context) < 0.5 else "support"

    def choose_action(
        self,
        state: IndividualState,
        partner: IndividualState,
        mission: JointMission,
        relationships: RelationshipStateStore,
        communication: CommunicationPolicy,
        *,
        partner_message: Role | None = None,
    ) -> JointAction:
        preferred = self.preferred_role(state, mission)
        memory = relationships.pair_memory(state.agent_id, partner.agent_id)
        prior = memory.last_for_context(mission.context)

        if prior is not None:
            own_prior = prior.role_for(state.agent_id)
            partner_prior = prior.role_for(partner.agent_id)
            if prior.success:
                return JointAction(state.agent_id, own_prior)
            if own_prior == partner_prior:
                role = own_prior if state.agent_id < partner.agent_id else _other(own_prior)
                return JointAction(state.agent_id, role)

        prediction = relationships.partner_model(state.agent_id, partner.agent_id).predict(
            mission.context
        )
        if prediction == preferred:
            role = preferred if state.agent_id < partner.agent_id else _other(preferred)
            return JointAction(state.agent_id, role)

        teamwork = relationships.teamwork_model(state.agent_id)
        general_role = teamwork.successful_role(mission.context)
        if general_role is not None:
            return JointAction(state.agent_id, general_role)

        if (
            communication.bandwidth_bits >= 1
            and partner_message == preferred
            and teamwork.learned_collision_convention(mission.context)
        ):
            role = preferred if state.agent_id < partner.agent_id else _other(preferred)
            return JointAction(state.agent_id, role)

        return JointAction(state.agent_id, preferred)


@dataclass(slots=True)
class JointLearningSession:
    environment: JointEnvironment
    controller: JointController
    relationships: RelationshipStateStore
    communication: CommunicationPolicy

    def run_episode(
        self,
        first: IndividualState,
        second: IndividualState,
        mission: JointMission,
        *,
        seed: int,
    ) -> JointEpisode:
        first_message = self.controller.preferred_role(first, mission)
        second_message = self.controller.preferred_role(second, mission)
        first_action = self.controller.choose_action(
            first,
            second,
            mission,
            self.relationships,
            self.communication,
            partner_message=second_message,
        )
        second_action = self.controller.choose_action(
            second,
            first,
            mission,
            self.relationships,
            self.communication,
            partner_message=first_message,
        )
        success = self.environment.evaluate(
            first,
            second,
            mission,
            first_action,
            second_action,
            seed=seed,
        )
        episode = JointEpisode(
            mission_id=mission.mission_id,
            context=mission.context,
            agent_a=first.agent_id,
            action_a=first_action.role,
            agent_b=second.agent_id,
            action_b=second_action.role,
            success=success,
        )
        self.relationships.record(episode)
        return episode
