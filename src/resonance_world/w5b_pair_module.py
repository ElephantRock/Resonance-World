"""First-class transport container for validated W4 pair state.

A PairModule may restore existing individual and relationship state, but it never
changes the environment success law and never relabels old partner-specific state
onto a replacement partner.
"""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from typing import Any

from .w4a_joint_learning import (
    GeneralTeamworkModel,
    IndividualState,
    JointEpisode,
    PartnerModel,
    RelationshipStateStore,
    SharedPairMemory,
)


def _pair_key(first: str, second: str) -> tuple[str, str]:
    return tuple(sorted((first, second)))  # type: ignore[return-value]


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def _clone_individual(value: IndividualState) -> IndividualState:
    return IndividualState(value.agent_id, dict(value.practice_by_skill))


@dataclass(frozen=True, slots=True)
class ModuleMember:
    agent_id: str
    source_field_id: str
    practice_by_skill: tuple[tuple[str, int], ...]

    @classmethod
    def from_state(cls, value: IndividualState, source_field_id: str) -> ModuleMember:
        return cls(
            value.agent_id,
            source_field_id,
            tuple(sorted((str(k), int(v)) for k, v in value.practice_by_skill.items())),
        )

    def instantiate(self) -> IndividualState:
        return IndividualState(self.agent_id, dict(self.practice_by_skill))

    def to_dict(self) -> dict[str, object]:
        return {
            "agent_id": self.agent_id,
            "practice_by_skill": dict(self.practice_by_skill),
            "source_field_id": self.source_field_id,
        }


@dataclass(frozen=True, slots=True)
class PairRelationshipCapsule:
    partner_models: tuple[dict[str, object], ...]
    teamwork_models: tuple[dict[str, object], ...]
    pair_memory: dict[str, object] | None

    def to_dict(self) -> dict[str, object]:
        return {
            "pair_memory": copy.deepcopy(self.pair_memory),
            "partner_models": copy.deepcopy(list(self.partner_models)),
            "teamwork_models": copy.deepcopy(list(self.teamwork_models)),
        }


@dataclass(frozen=True, slots=True)
class PairModule:
    module_id: str
    member_a: ModuleMember
    member_b: ModuleMember
    relationship: PairRelationshipCapsule
    formation_evidence: tuple[str, ...] = ()
    capability_profile: tuple[tuple[str, float], ...] = ()
    provenance: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.member_a.agent_id == self.member_b.agent_id:
            raise ValueError("pair module requires two distinct members")
        if not self.module_id:
            raise ValueError("module_id is required")

    def to_dict(self) -> dict[str, object]:
        members = sorted(
            [self.member_a.to_dict(), self.member_b.to_dict()],
            key=lambda row: str(row["agent_id"]),
        )
        return {
            "capability_profile": dict(self.capability_profile),
            "formation_evidence": list(self.formation_evidence),
            "members": members,
            "module_id": self.module_id,
            "provenance": list(self.provenance),
            "relationship": self.relationship.to_dict(),
        }

    def canonical_bytes(self) -> bytes:
        return _canonical(self.to_dict())

    def content_sha256(self) -> str:
        return hashlib.sha256(self.canonical_bytes()).hexdigest()


@dataclass(slots=True)
class PairInstance:
    first: IndividualState
    second: IndividualState
    relationships: RelationshipStateStore
    retention_mode: str
    retained_state: tuple[str, ...]

    @property
    def member_ids(self) -> tuple[str, str]:
        return _pair_key(self.first.agent_id, self.second.agent_id)


def _capture_relationship(
    first: str,
    second: str,
    relationships: RelationshipStateStore,
) -> PairRelationshipCapsule:
    partner_rows: list[dict[str, object]] = []
    for owner, partner in ((first, second), (second, first)):
        model = relationships.partner_models.get((owner, partner))
        if model is not None:
            partner_rows.append(copy.deepcopy(model.as_dict()))

    teamwork_rows: list[dict[str, object]] = []
    for agent_id in sorted((first, second)):
        model = relationships.teamwork_models.get(agent_id)
        if model is not None:
            teamwork_rows.append(copy.deepcopy(model.as_dict()))

    memory = relationships.pair_memories.get(_pair_key(first, second))
    memory_row = copy.deepcopy(memory.as_dict()) if memory is not None else None
    return PairRelationshipCapsule(
        tuple(sorted(partner_rows, key=lambda row: str(row["owner_agent_id"]))),
        tuple(sorted(teamwork_rows, key=lambda row: str(row["owner_agent_id"]))),
        memory_row,
    )


def capture_pair(
    module_id: str,
    first: IndividualState,
    second: IndividualState,
    relationships: RelationshipStateStore,
    *,
    source_field_ids: tuple[str, str],
    formation_evidence: tuple[str, ...] = (),
    capability_profile: dict[str, float] | None = None,
    provenance: tuple[str, ...] = (),
) -> PairModule:
    if len(source_field_ids) != 2:
        raise ValueError("source_field_ids must contain exactly two entries")
    return PairModule(
        module_id=module_id,
        member_a=ModuleMember.from_state(first, source_field_ids[0]),
        member_b=ModuleMember.from_state(second, source_field_ids[1]),
        relationship=_capture_relationship(first.agent_id, second.agent_id, relationships),
        formation_evidence=tuple(formation_evidence),
        capability_profile=tuple(sorted((capability_profile or {}).items())),
        provenance=tuple(provenance),
    )


def _restore_partner_model(row: dict[str, Any]) -> PartnerModel:
    model = PartnerModel(str(row["owner_agent_id"]), str(row["partner_agent_id"]))
    model.role_counts_by_context = {
        str(context): {
            "lead": int(counts["lead"]),
            "support": int(counts["support"]),
        }
        for context, counts in dict(row["role_counts_by_context"]).items()
    }
    return model


def _restore_teamwork_model(row: dict[str, Any]) -> GeneralTeamworkModel:
    model = GeneralTeamworkModel(str(row["owner_agent_id"]))
    model.successful_roles_by_context = copy.deepcopy(
        dict(row["successful_roles_by_context"])
    )
    model.collision_failures_by_context = {
        str(k): int(v) for k, v in dict(row["collision_failures_by_context"]).items()
    }
    model.episode_counts_by_context = {
        str(k): int(v) for k, v in dict(row["episode_counts_by_context"]).items()
    }
    return model


def _restore_pair_memory(row: dict[str, Any]) -> SharedPairMemory:
    memory = SharedPairMemory(str(row["agent_a"]), str(row["agent_b"]))
    for item in list(row["episodes"]):
        episode = dict(item)
        memory.append(
            JointEpisode(
                mission_id=str(episode["mission_id"]),
                context=str(episode["context"]),
                agent_a=str(episode["agent_a"]),
                action_a=str(episode["action_a"]),  # type: ignore[arg-type]
                agent_b=str(episode["agent_b"]),
                action_b=str(episode["action_b"]),  # type: ignore[arg-type]
                success=bool(episode["success"]),
            )
        )
    return memory


def _restore_relationships(module: PairModule) -> RelationshipStateStore:
    store = RelationshipStateStore()
    for row in module.relationship.partner_models:
        model = _restore_partner_model(row)
        store.partner_models[(model.owner_agent_id, model.partner_agent_id)] = model
    for row in module.relationship.teamwork_models:
        model = _restore_teamwork_model(row)
        store.teamwork_models[model.owner_agent_id] = model
    if module.relationship.pair_memory is not None:
        memory = _restore_pair_memory(module.relationship.pair_memory)
        store.pair_memories[_pair_key(memory.agent_a, memory.agent_b)] = memory
    return store


def instantiate_intact(module: PairModule) -> PairInstance:
    return PairInstance(
        module.member_a.instantiate(),
        module.member_b.instantiate(),
        _restore_relationships(module),
        "intact",
        ("partner_models", "general_teamwork", "pair_memory"),
    )


def instantiate_with_reset(module: PairModule) -> PairInstance:
    return PairInstance(
        module.member_a.instantiate(),
        module.member_b.instantiate(),
        RelationshipStateStore(),
        "relationship_reset",
        (),
    )


def replace_member(
    module: PairModule,
    retiring_agent_id: str,
    replacement: IndividualState,
) -> PairInstance:
    if retiring_agent_id not in {
        module.member_a.agent_id,
        module.member_b.agent_id,
    }:
        raise ValueError("retiring agent is not a module member")
    survivor_member = (
        module.member_b
        if retiring_agent_id == module.member_a.agent_id
        else module.member_a
    )
    if replacement.agent_id == survivor_member.agent_id:
        raise ValueError("replacement must be distinct from survivor")

    relationships = RelationshipStateStore()
    for row in module.relationship.teamwork_models:
        if str(row["owner_agent_id"]) == survivor_member.agent_id:
            model = _restore_teamwork_model(row)
            relationships.teamwork_models[model.owner_agent_id] = model

    return PairInstance(
        survivor_member.instantiate(),
        _clone_individual(replacement),
        relationships,
        "member_replaced",
        ("survivor_general_teamwork",),
    )
