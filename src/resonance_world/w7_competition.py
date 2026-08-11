"""World-side competition and coopetition substrate for W7.

Market state allocates scarce service rights. It never changes intrinsic agent
practice and is never a direct input to mission success laws.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field

from .w5a_organization import OrganizationState
from .w6_mobility import PortableAgentState


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
class TalentOffer:
    """Public-evidence bid for one agent in one market window."""

    offer_id: str
    organization_id: str
    agent_id: str
    window_id: str
    bid: int
    evidence_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        identifiers = (
            self.offer_id,
            self.organization_id,
            self.agent_id,
            self.window_id,
        )
        if any(not value for value in identifiers):
            raise ValueError("offer identifiers must be non-empty")
        if self.bid <= 0:
            raise ValueError("offer bid must be positive")
        refs = tuple(sorted({str(ref) for ref in self.evidence_refs if str(ref)}))
        if not refs:
            raise ValueError("offer requires public evidence provenance")
        object.__setattr__(self, "evidence_refs", refs)

    def as_dict(self) -> dict[str, object]:
        return {
            "agent_id": self.agent_id,
            "bid": self.bid,
            "evidence_refs": list(self.evidence_refs),
            "offer_id": self.offer_id,
            "organization_id": self.organization_id,
            "window_id": self.window_id,
        }


@dataclass(frozen=True, slots=True)
class TalentContract:
    contract_id: str
    offer_id: str
    organization_id: str
    agent_id: str
    window_id: str
    price: int
    evidence_refs: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "agent_id": self.agent_id,
            "contract_id": self.contract_id,
            "evidence_refs": list(self.evidence_refs),
            "offer_id": self.offer_id,
            "organization_id": self.organization_id,
            "price": self.price,
            "window_id": self.window_id,
        }


@dataclass(slots=True)
class OrganizationAccount:
    organization: OrganizationState
    initial_budget: int
    balance: int

    @classmethod
    def open(cls, organization: OrganizationState, budget: int) -> OrganizationAccount:
        if not organization.organization_id:
            raise ValueError("organization_id must be non-empty")
        if budget < 0:
            raise ValueError("organization budget must be non-negative")
        return cls(organization=organization, initial_budget=budget, balance=budget)

    def as_dict(self) -> dict[str, object]:
        return {
            "balance": self.balance,
            "initial_budget": self.initial_budget,
            "organization_id": self.organization.organization_id,
        }


@dataclass(frozen=True, slots=True)
class CooperationAgreement:
    """Mission-bounded sharing of already contracted individual service rights."""

    agreement_id: str
    window_id: str
    mission_id: str
    contributions: tuple[tuple[str, str], ...]
    evidence_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.agreement_id or not self.window_id or not self.mission_id:
            raise ValueError("cooperation agreement identifiers must be non-empty")
        normalized: list[tuple[str, str]] = []
        seen_agents: set[str] = set()
        organizations: set[str] = set()
        for organization_id, agent_id in self.contributions:
            if not organization_id or not agent_id:
                raise ValueError("coalition contributions must identify organization and agent")
            if agent_id in seen_agents:
                raise ValueError("an agent cannot be contributed twice to one coalition")
            seen_agents.add(agent_id)
            organizations.add(organization_id)
            normalized.append((organization_id, agent_id))
        if len(organizations) < 2:
            raise ValueError("cooperation requires at least two distinct organizations")
        refs = tuple(sorted({str(ref) for ref in self.evidence_refs if str(ref)}))
        if not refs:
            raise ValueError("cooperation agreement requires provenance evidence")
        object.__setattr__(self, "contributions", tuple(sorted(normalized)))
        object.__setattr__(self, "evidence_refs", refs)

    def as_dict(self) -> dict[str, object]:
        return {
            "agreement_id": self.agreement_id,
            "contributions": [
                {"agent_id": agent_id, "organization_id": organization_id}
                for organization_id, agent_id in self.contributions
            ],
            "evidence_refs": list(self.evidence_refs),
            "mission_id": self.mission_id,
            "window_id": self.window_id,
        }


@dataclass(frozen=True, slots=True)
class CoalitionDeployment:
    agreement: CooperationAgreement
    members: tuple[PortableAgentState, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "agreement": self.agreement.as_dict(),
            "member_state_sha256": [member.digest() for member in self.members],
        }


@dataclass(slots=True)
class TalentMarket:
    """Deterministic exclusive-service market with an auditable ledger."""

    _agents: dict[str, PortableAgentState] = field(default_factory=dict)
    _accounts: dict[str, OrganizationAccount] = field(default_factory=dict)
    _offers: dict[str, TalentOffer] = field(default_factory=dict)
    _contracts: dict[tuple[str, str], TalentContract] = field(default_factory=dict)
    _agreements: dict[str, CooperationAgreement] = field(default_factory=dict)
    _settled_windows: set[str] = field(default_factory=set)

    def register_agent(self, state: PortableAgentState) -> None:
        if state.agent_id in self._agents:
            raise ValueError(f"agent already registered: {state.agent_id}")
        self._agents[state.agent_id] = state

    def register_organization(self, organization: OrganizationState, *, budget: int) -> None:
        organization_id = organization.organization_id
        if organization_id in self._accounts:
            raise ValueError(f"organization already registered: {organization_id}")
        self._accounts[organization_id] = OrganizationAccount.open(organization, budget)

    def submit_offer(self, offer: TalentOffer) -> None:
        if offer.offer_id in self._offers:
            raise ValueError(f"offer already exists: {offer.offer_id}")
        if offer.organization_id not in self._accounts:
            raise ValueError(f"unknown organization: {offer.organization_id}")
        if offer.agent_id not in self._agents:
            raise ValueError(f"unknown agent: {offer.agent_id}")
        if offer.window_id in self._settled_windows:
            raise ValueError(f"market window already settled: {offer.window_id}")
        if offer.bid > self._accounts[offer.organization_id].initial_budget:
            raise ValueError("offer exceeds organization's frozen window budget")
        self._offers[offer.offer_id] = offer

    def settle(self, window_id: str) -> tuple[TalentContract, ...]:
        if not window_id:
            raise ValueError("window_id must be non-empty")
        if window_id in self._settled_windows:
            raise ValueError(f"market window already settled: {window_id}")

        by_agent: dict[str, list[TalentOffer]] = {}
        for offer in self._offers.values():
            if offer.window_id == window_id:
                by_agent.setdefault(offer.agent_id, []).append(offer)

        awarded: list[TalentContract] = []
        for agent_id in sorted(by_agent):
            ranked = sorted(
                by_agent[agent_id],
                key=lambda offer: (-offer.bid, offer.organization_id, offer.offer_id),
            )
            winner = next(
                (
                    offer
                    for offer in ranked
                    if self._accounts[offer.organization_id].balance >= offer.bid
                ),
                None,
            )
            if winner is None:
                continue
            key = (window_id, agent_id)
            if key in self._contracts:
                raise AssertionError("exclusive service right already exists")
            account = self._accounts[winner.organization_id]
            account.balance -= winner.bid
            contract = TalentContract(
                contract_id=f"contract:{window_id}:{agent_id}",
                offer_id=winner.offer_id,
                organization_id=winner.organization_id,
                agent_id=agent_id,
                window_id=window_id,
                price=winner.bid,
                evidence_refs=winner.evidence_refs,
            )
            self._contracts[key] = contract
            awarded.append(contract)

        self._settled_windows.add(window_id)
        return tuple(awarded)

    def account(self, organization_id: str) -> OrganizationAccount:
        try:
            return self._accounts[organization_id]
        except KeyError as exc:
            raise KeyError(f"unknown organization: {organization_id}") from exc

    def contract(self, window_id: str, agent_id: str) -> TalentContract | None:
        return self._contracts.get((window_id, agent_id))

    def contracted_agents(
        self,
        organization_id: str,
        window_id: str,
    ) -> tuple[PortableAgentState, ...]:
        return tuple(
            self._agents[contract.agent_id]
            for contract in sorted(
                self._contracts.values(),
                key=lambda item: (item.window_id, item.agent_id),
            )
            if contract.organization_id == organization_id and contract.window_id == window_id
        )

    def prepare_coalition(self, agreement: CooperationAgreement) -> CoalitionDeployment:
        if agreement.agreement_id in self._agreements:
            raise ValueError(f"agreement already used: {agreement.agreement_id}")
        members: list[PortableAgentState] = []
        for organization_id, agent_id in agreement.contributions:
            contract = self.contract(agreement.window_id, agent_id)
            if contract is None:
                raise ValueError(f"agent is not contracted in window: {agent_id}")
            if contract.organization_id != organization_id:
                raise ValueError("coalition contribution is not owned by contributing organization")
            members.append(self._agents[agent_id])
        self._agreements[agreement.agreement_id] = agreement
        return CoalitionDeployment(agreement=agreement, members=tuple(members))

    def snapshot(self) -> dict[str, object]:
        return {
            "accounts": [
                self._accounts[organization_id].as_dict()
                for organization_id in sorted(self._accounts)
            ],
            "agreements": [
                self._agreements[agreement_id].as_dict()
                for agreement_id in sorted(self._agreements)
            ],
            "agents": [
                {
                    "agent_id": agent_id,
                    "state_sha256": self._agents[agent_id].digest(),
                }
                for agent_id in sorted(self._agents)
            ],
            "contracts": [
                contract.as_dict()
                for _, contract in sorted(self._contracts.items(), key=lambda item: item[0])
            ],
            "offers": [
                self._offers[offer_id].as_dict() for offer_id in sorted(self._offers)
            ],
            "settled_windows": sorted(self._settled_windows),
        }

    def digest(self) -> str:
        return _sha256(self.snapshot())
