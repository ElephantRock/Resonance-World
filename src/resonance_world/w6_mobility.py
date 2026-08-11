"""World-side mobility lifecycle for W6.

Mobility changes operational availability and affiliation only. It does not grant a
success bonus, mutate Resonance Field, or silently transport pair/organization state.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Literal, Mapping

from .w4a_joint_learning import IndividualState

MobilityMode = Literal[
    "secondment",
    "temporary_migration",
    "permanent_migration",
    "return_migration",
]
MobilityStatus = Literal[
    "home",
    "seconded",
    "temporary_migrant",
    "permanent_migrant",
]


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


@dataclass(frozen=True, slots=True)
class PortableAgentState:
    """Agent-owned state allowed to move in an individual W6 contract."""

    agent_id: str
    home_field_id: str
    practice_by_skill: tuple[tuple[str, int], ...]
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.agent_id:
            raise ValueError("agent_id must be non-empty")
        if not self.home_field_id:
            raise ValueError("home_field_id must be non-empty")
        normalized: list[tuple[str, int]] = []
        seen: set[str] = set()
        for skill, count in self.practice_by_skill:
            if not skill or skill in seen:
                raise ValueError("practice skills must be unique and non-empty")
            if int(count) < 0:
                raise ValueError("practice counts must be non-negative")
            seen.add(skill)
            normalized.append((str(skill), int(count)))
        normalized.sort()
        refs = tuple(sorted({str(ref) for ref in self.evidence_refs if str(ref)}))
        object.__setattr__(self, "practice_by_skill", tuple(normalized))
        object.__setattr__(self, "evidence_refs", refs)

    @classmethod
    def from_individual(
        cls,
        state: IndividualState,
        *,
        home_field_id: str,
        evidence_refs: tuple[str, ...] = (),
    ) -> PortableAgentState:
        return cls(
            agent_id=state.agent_id,
            home_field_id=home_field_id,
            practice_by_skill=tuple(state.practice_by_skill.items()),
            evidence_refs=evidence_refs,
        )

    def to_individual(self) -> IndividualState:
        return IndividualState(
            agent_id=self.agent_id,
            practice_by_skill=dict(self.practice_by_skill),
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "agent_id": self.agent_id,
            "evidence_refs": list(self.evidence_refs),
            "home_field_id": self.home_field_id,
            "practice_by_skill": dict(self.practice_by_skill),
        }

    def digest(self) -> str:
        return _sha256(self.as_dict())

    def with_learning(
        self,
        practice_delta: Mapping[str, int],
        *,
        evidence_ref: str,
    ) -> PortableAgentState:
        if not evidence_ref:
            raise ValueError("returned learning requires an evidence_ref")
        current = dict(self.practice_by_skill)
        for skill, delta in practice_delta.items():
            delta = int(delta)
            if not skill or delta < 0:
                raise ValueError("learning deltas must be non-negative")
            current[str(skill)] = current.get(str(skill), 0) + delta
        return PortableAgentState(
            agent_id=self.agent_id,
            home_field_id=self.home_field_id,
            practice_by_skill=tuple(current.items()),
            evidence_refs=(*self.evidence_refs, evidence_ref),
        )

    def dominates(self, earlier: PortableAgentState) -> bool:
        if self.agent_id != earlier.agent_id or self.home_field_id != earlier.home_field_id:
            return False
        current = dict(self.practice_by_skill)
        previous = dict(earlier.practice_by_skill)
        skills = set(current) | set(previous)
        return all(current.get(skill, 0) >= previous.get(skill, 0) for skill in skills)


@dataclass(frozen=True, slots=True)
class MobilityContract:
    contract_id: str
    agent_id: str
    mode: MobilityMode
    origin_field_id: str
    destination_field_id: str
    evidence_ref: str

    def __post_init__(self) -> None:
        values = (
            self.contract_id,
            self.agent_id,
            self.origin_field_id,
            self.destination_field_id,
            self.evidence_ref,
        )
        if any(not value for value in values):
            raise ValueError("mobility contract identifiers/evidence must be non-empty")
        if self.origin_field_id == self.destination_field_id:
            raise ValueError("mobility requires distinct origin and destination Fields")


@dataclass(frozen=True, slots=True)
class MobilityEvent:
    sequence: int
    contract_id: str
    agent_id: str
    mode: MobilityMode
    origin_field_id: str
    destination_field_id: str
    home_affiliation_before: bool
    home_affiliation_after: bool
    state_before_sha256: str
    state_after_sha256: str
    evidence_ref: str

    def as_dict(self) -> dict[str, object]:
        return {
            "agent_id": self.agent_id,
            "contract_id": self.contract_id,
            "destination_field_id": self.destination_field_id,
            "evidence_ref": self.evidence_ref,
            "home_affiliation_after": self.home_affiliation_after,
            "home_affiliation_before": self.home_affiliation_before,
            "mode": self.mode,
            "origin_field_id": self.origin_field_id,
            "sequence": self.sequence,
            "state_after_sha256": self.state_after_sha256,
            "state_before_sha256": self.state_before_sha256,
        }


@dataclass(slots=True)
class MobilityRecord:
    portable_state: PortableAgentState
    current_field_id: str
    home_affiliation: bool = True
    status: MobilityStatus = "home"
    last_contract_id: str | None = None

    @property
    def agent_id(self) -> str:
        return self.portable_state.agent_id

    @property
    def home_field_id(self) -> str:
        return self.portable_state.home_field_id

    def as_dict(self) -> dict[str, object]:
        return {
            "agent_id": self.agent_id,
            "current_field_id": self.current_field_id,
            "home_affiliation": self.home_affiliation,
            "home_field_id": self.home_field_id,
            "last_contract_id": self.last_contract_id,
            "portable_state_sha256": self.portable_state.digest(),
            "status": self.status,
        }


@dataclass(slots=True)
class MobilityRegistry:
    """Auditable World-side location/affiliation ledger for portable agents."""

    _records: dict[str, MobilityRecord] = field(default_factory=dict)
    _events: list[MobilityEvent] = field(default_factory=list)
    _contract_ids: set[str] = field(default_factory=set)

    def register_home_agent(self, state: PortableAgentState) -> None:
        if state.agent_id in self._records:
            raise ValueError(f"agent already registered: {state.agent_id}")
        self._records[state.agent_id] = MobilityRecord(
            portable_state=state,
            current_field_id=state.home_field_id,
        )

    def record(self, agent_id: str) -> MobilityRecord:
        try:
            return self._records[agent_id]
        except KeyError as exc:
            raise KeyError(f"unknown mobile agent: {agent_id}") from exc

    def available_agents(self, field_id: str) -> tuple[str, ...]:
        return tuple(
            sorted(
                agent_id
                for agent_id, record in self._records.items()
                if record.current_field_id == field_id
            )
        )

    def events(self) -> tuple[MobilityEvent, ...]:
        return tuple(self._events)

    def execute(
        self,
        contract: MobilityContract,
        *,
        returned_state: PortableAgentState | None = None,
    ) -> MobilityEvent:
        if contract.contract_id in self._contract_ids:
            raise ValueError(f"contract already executed: {contract.contract_id}")
        record = self.record(contract.agent_id)
        if record.current_field_id != contract.origin_field_id:
            raise ValueError("contract origin does not match current operational Field")

        outbound = contract.mode != "return_migration"
        if outbound:
            if record.current_field_id != record.home_field_id:
                raise ValueError("outbound mobility must begin at the immutable home Field")
            if contract.destination_field_id == record.home_field_id:
                raise ValueError("outbound destination must differ from the home Field")
            if returned_state is not None:
                raise ValueError("returned_state is valid only for return migration")
        else:
            if record.current_field_id == record.home_field_id:
                raise ValueError("return migration requires an agent currently away from home")
            if contract.destination_field_id != record.home_field_id:
                raise ValueError("return migration destination must be the immutable home Field")
            if returned_state is not None:
                self._validate_returned_state(record.portable_state, returned_state)

        state_before = record.portable_state
        affiliation_before = record.home_affiliation
        state_after = returned_state if returned_state is not None else state_before

        record.portable_state = state_after
        record.current_field_id = contract.destination_field_id
        record.last_contract_id = contract.contract_id
        if contract.mode == "secondment":
            record.home_affiliation = True
            record.status = "seconded"
        elif contract.mode == "temporary_migration":
            record.home_affiliation = True
            record.status = "temporary_migrant"
        elif contract.mode == "permanent_migration":
            record.home_affiliation = False
            record.status = "permanent_migrant"
        else:
            record.home_affiliation = True
            record.status = "home"

        event = MobilityEvent(
            sequence=len(self._events) + 1,
            contract_id=contract.contract_id,
            agent_id=record.agent_id,
            mode=contract.mode,
            origin_field_id=contract.origin_field_id,
            destination_field_id=contract.destination_field_id,
            home_affiliation_before=affiliation_before,
            home_affiliation_after=record.home_affiliation,
            state_before_sha256=state_before.digest(),
            state_after_sha256=state_after.digest(),
            evidence_ref=contract.evidence_ref,
        )
        self._events.append(event)
        self._contract_ids.add(contract.contract_id)
        return event

    @staticmethod
    def _validate_returned_state(
        current: PortableAgentState,
        returned: PortableAgentState,
    ) -> None:
        if returned.agent_id != current.agent_id:
            raise ValueError("returned state changed agent identity")
        if returned.home_field_id != current.home_field_id:
            raise ValueError("returned state changed immutable home Field identity")
        if not returned.dominates(current):
            raise ValueError("returned learning cannot reduce agent-owned practice")
        if returned.digest() != current.digest() and not returned.evidence_refs:
            raise ValueError("changed returned state requires provenance evidence")

    def snapshot(self) -> dict[str, object]:
        return {
            "events": [event.as_dict() for event in self._events],
            "records": [
                record.as_dict()
                for _, record in sorted(self._records.items(), key=lambda item: item[0])
            ],
        }

    def digest(self) -> str:
        return _sha256(self.snapshot())
