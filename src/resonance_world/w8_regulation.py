"""World-side regulatory primitives for W8.

Regulation changes allocation, timing, payments, coordination rights and budget
trajectories only. It never mutates portable competence and is never a direct input
to mission-success laws.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Literal

from .w6_mobility import PortableAgentState
from .w7_competition import TalentContract

DutyPhase = Literal["external", "home"]
BudgetMode = Literal["neutral", "compounding"]


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
class SourceReserveRule:
    """Maximum simultaneously external service rights per source Field."""

    max_active_external_per_field: int

    def __post_init__(self) -> None:
        if self.max_active_external_per_field < 0:
            raise ValueError("source-reserve cap must be non-negative")

    def allows(self, *, active_count: int) -> bool:
        if active_count < 0:
            raise ValueError("active_count must be non-negative")
        return active_count < self.max_active_external_per_field


@dataclass(frozen=True, slots=True)
class CirculationSchedule:
    """Deterministic external/home duty cycle with no capability semantics."""

    external_windows: int
    home_windows: int

    def __post_init__(self) -> None:
        if self.external_windows <= 0 or self.home_windows <= 0:
            raise ValueError("circulation duty-cycle windows must be positive")

    @property
    def cycle_length(self) -> int:
        return self.external_windows + self.home_windows

    def phase(self, window_index: int) -> DutyPhase:
        if window_index < 0:
            raise ValueError("window_index must be non-negative")
        offset = window_index % self.cycle_length
        return "external" if offset < self.external_windows else "home"

    def external_share(self) -> float:
        return self.external_windows / self.cycle_length


@dataclass(frozen=True, slots=True)
class SourceDividendPolicy:
    """Contract-price share returned to the source as non-targeted development budget."""

    basis_points: int

    def __post_init__(self) -> None:
        if not 0 <= self.basis_points <= 10_000:
            raise ValueError("dividend basis points must lie in [0, 10000]")

    def dividend(self, contract_price: int) -> int:
        if contract_price < 0:
            raise ValueError("contract price must be non-negative")
        return contract_price * self.basis_points // 10_000


@dataclass(frozen=True, slots=True)
class ReplacementGrant:
    """Field-owned development budget with no target-agent or target-skill instruction."""

    source_field_id: str
    amount: int
    source_contract_id: str
    evidence_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.source_field_id or not self.source_contract_id:
            raise ValueError("replacement grant identifiers must be non-empty")
        if self.amount < 0:
            raise ValueError("replacement grant amount must be non-negative")
        refs = tuple(sorted({str(ref) for ref in self.evidence_refs if str(ref)}))
        if not refs:
            raise ValueError("replacement grant requires provenance evidence")
        object.__setattr__(self, "evidence_refs", refs)

    def as_dict(self) -> dict[str, object]:
        return {
            "amount": self.amount,
            "evidence_refs": list(self.evidence_refs),
            "source_contract_id": self.source_contract_id,
            "source_field_id": self.source_field_id,
        }


@dataclass(slots=True)
class SourceDividendLedger:
    policy: SourceDividendPolicy
    _balances: dict[str, int] = field(default_factory=dict)
    _grants: list[ReplacementGrant] = field(default_factory=list)

    def credit(
        self,
        contract: TalentContract,
        state: PortableAgentState,
    ) -> ReplacementGrant:
        if contract.agent_id != state.agent_id:
            raise ValueError("contract/state identity mismatch")
        amount = self.policy.dividend(contract.price)
        grant = ReplacementGrant(
            source_field_id=state.home_field_id,
            amount=amount,
            source_contract_id=contract.contract_id,
            evidence_refs=contract.evidence_refs,
        )
        self._balances[state.home_field_id] = self._balances.get(state.home_field_id, 0) + amount
        self._grants.append(grant)
        return grant

    def balance(self, source_field_id: str) -> int:
        return self._balances.get(source_field_id, 0)

    def grants(self) -> tuple[ReplacementGrant, ...]:
        return tuple(self._grants)

    def snapshot(self) -> dict[str, object]:
        return {
            "balances": dict(sorted(self._balances.items())),
            "grants": [grant.as_dict() for grant in self._grants],
            "policy_basis_points": self.policy.basis_points,
        }


@dataclass(frozen=True, slots=True)
class RegulatedServiceRight:
    """Auditable external service right; stores only an immutable state digest."""

    contract_id: str
    organization_id: str
    agent_id: str
    source_field_id: str
    window_id: str
    state_sha256: str
    evidence_refs: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "agent_id": self.agent_id,
            "contract_id": self.contract_id,
            "evidence_refs": list(self.evidence_refs),
            "organization_id": self.organization_id,
            "source_field_id": self.source_field_id,
            "state_sha256": self.state_sha256,
            "window_id": self.window_id,
        }


@dataclass(slots=True)
class RegulatedServiceLedger:
    """Source-cap enforcement over already-priced W7 contracts."""

    reserve_rule: SourceReserveRule
    _rights: dict[str, RegulatedServiceRight] = field(default_factory=dict)
    _active_by_source: dict[str, set[str]] = field(default_factory=dict)

    def grant(
        self,
        contract: TalentContract,
        state: PortableAgentState,
    ) -> RegulatedServiceRight:
        if contract.contract_id in self._rights:
            raise ValueError(f"service right already registered: {contract.contract_id}")
        if contract.agent_id != state.agent_id:
            raise ValueError("contract/state identity mismatch")
        active = self._active_by_source.setdefault(state.home_field_id, set())
        if not self.reserve_rule.allows(active_count=len(active)):
            raise ValueError(f"source reserve exhausted: {state.home_field_id}")
        right = RegulatedServiceRight(
            contract_id=contract.contract_id,
            organization_id=contract.organization_id,
            agent_id=contract.agent_id,
            source_field_id=state.home_field_id,
            window_id=contract.window_id,
            state_sha256=state.digest(),
            evidence_refs=contract.evidence_refs,
        )
        self._rights[contract.contract_id] = right
        active.add(contract.contract_id)
        return right

    def release(self, contract_id: str) -> RegulatedServiceRight:
        try:
            right = self._rights.pop(contract_id)
        except KeyError as exc:
            raise KeyError(f"unknown active service right: {contract_id}") from exc
        self._active_by_source[right.source_field_id].remove(contract_id)
        return right

    def active_count(self, source_field_id: str) -> int:
        return len(self._active_by_source.get(source_field_id, set()))

    def rights(self) -> tuple[RegulatedServiceRight, ...]:
        return tuple(self._rights[key] for key in sorted(self._rights))

    def snapshot(self) -> dict[str, object]:
        return {
            "reserve_cap": self.reserve_rule.max_active_external_per_field,
            "rights": [right.as_dict() for right in self.rights()],
        }

    def digest(self) -> str:
        return _sha256(self.snapshot())


@dataclass(frozen=True, slots=True)
class CoalitionSubtask:
    organization_id: str
    agent_id: str
    skill: str
    role: str

    def __post_init__(self) -> None:
        if not all((self.organization_id, self.agent_id, self.skill, self.role)):
            raise ValueError("coalition subtask fields must be non-empty")


@dataclass(frozen=True, slots=True)
class CoalitionCoordinationContract:
    """Mission-bounded coordination rights without state/ownership merger."""

    contract_id: str
    mission_id: str
    window_id: str
    subtasks: tuple[CoalitionSubtask, ...]
    message_bandwidth_bits: int
    evidence_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.contract_id or not self.mission_id or not self.window_id:
            raise ValueError("coordination contract identifiers must be non-empty")
        if self.message_bandwidth_bits < 0:
            raise ValueError("message bandwidth must be non-negative")
        organizations = {item.organization_id for item in self.subtasks}
        agents = [item.agent_id for item in self.subtasks]
        if len(organizations) < 2:
            raise ValueError("coalition coordination requires at least two organizations")
        if len(agents) != len(set(agents)):
            raise ValueError("an agent cannot own two coalition subtasks")
        refs = tuple(sorted({str(ref) for ref in self.evidence_refs if str(ref)}))
        if not refs:
            raise ValueError("coordination contract requires provenance evidence")
        object.__setattr__(self, "evidence_refs", refs)

    def as_dict(self) -> dict[str, object]:
        return {
            "contract_id": self.contract_id,
            "evidence_refs": list(self.evidence_refs),
            "message_bandwidth_bits": self.message_bandwidth_bits,
            "mission_id": self.mission_id,
            "subtasks": [
                {
                    "agent_id": item.agent_id,
                    "organization_id": item.organization_id,
                    "role": item.role,
                    "skill": item.skill,
                }
                for item in self.subtasks
            ],
            "window_id": self.window_id,
        }


@dataclass(frozen=True, slots=True)
class CoalitionCoordinationPolicy:
    max_message_bandwidth_bits: int
    max_subtasks: int

    def __post_init__(self) -> None:
        if self.max_message_bandwidth_bits < 0 or self.max_subtasks < 2:
            raise ValueError("invalid coalition coordination limits")

    def validate(self, contract: CoalitionCoordinationContract) -> None:
        if contract.message_bandwidth_bits > self.max_message_bandwidth_bits:
            raise ValueError("coalition communication budget exceeded")
        if len(contract.subtasks) > self.max_subtasks:
            raise ValueError("coalition subtask budget exceeded")


@dataclass(frozen=True, slots=True)
class BudgetUpdatePolicy:
    """Explicit economic feedback law for W8 long-horizon experiments."""

    mode: BudgetMode
    base_budget: int
    reward_per_success: int = 0
    max_budget: int = 10_000

    def __post_init__(self) -> None:
        if self.mode not in {"neutral", "compounding"}:
            raise ValueError(f"unsupported budget mode: {self.mode}")
        if self.base_budget < 0 or self.reward_per_success < 0 or self.max_budget < 0:
            raise ValueError("budget parameters must be non-negative")
        if self.base_budget > self.max_budget:
            raise ValueError("base budget exceeds max budget")
        if self.mode == "neutral" and self.reward_per_success != 0:
            raise ValueError("neutral budget mode cannot reward success")

    def next_budget(self, *, current_budget: int, spend: int, successes: int) -> int:
        if min(current_budget, spend, successes) < 0:
            raise ValueError("budget update inputs must be non-negative")
        if self.mode == "neutral":
            return self.base_budget
        return min(
            self.max_budget,
            max(0, current_budget - spend + successes * self.reward_per_success),
        )


@dataclass(frozen=True, slots=True)
class BenchmarkAssignment:
    mission_id: str
    agent_id: str
    expected_success: float

    def __post_init__(self) -> None:
        if not self.mission_id or not self.agent_id:
            raise ValueError("benchmark assignment identifiers must be non-empty")
        if not 0 <= self.expected_success <= 1:
            raise ValueError("expected success must lie in [0, 1]")


@dataclass(frozen=True, slots=True)
class CapabilityStockObservation:
    """Ownership-invariant benchmark stock; each living agent may be counted once."""

    assignments: tuple[BenchmarkAssignment, ...]
    living_agent_ids: frozenset[str]
    cumulative_development_compute: float

    def __post_init__(self) -> None:
        if self.cumulative_development_compute < 0:
            raise ValueError("development compute must be non-negative")
        agents = [item.agent_id for item in self.assignments]
        missions = [item.mission_id for item in self.assignments]
        if len(agents) != len(set(agents)):
            raise ValueError("capability stock cannot double-count an agent")
        if len(missions) != len(set(missions)):
            raise ValueError("benchmark mission may be assigned only once")
        unknown = set(agents) - set(self.living_agent_ids)
        if unknown:
            raise ValueError(f"benchmark assignment references non-living agents: {sorted(unknown)}")

    @property
    def stock(self) -> float:
        return sum(item.expected_success for item in self.assignments)

    @property
    def compute_normalized_stock(self) -> float | None:
        if self.cumulative_development_compute == 0:
            return None
        return self.stock / self.cumulative_development_compute


@dataclass(frozen=True, slots=True)
class RegulatoryCharter:
    """Serializable W8 institutional rule set; contains no agent competence."""

    reserve_rule: SourceReserveRule
    circulation_schedule: CirculationSchedule
    dividend_policy: SourceDividendPolicy
    coordination_policy: CoalitionCoordinationPolicy
    budget_policy: BudgetUpdatePolicy

    def snapshot(self) -> dict[str, object]:
        value = {
            "budget_policy": {
                "base_budget": self.budget_policy.base_budget,
                "max_budget": self.budget_policy.max_budget,
                "mode": self.budget_policy.mode,
                "reward_per_success": self.budget_policy.reward_per_success,
            },
            "circulation_schedule": {
                "external_windows": self.circulation_schedule.external_windows,
                "home_windows": self.circulation_schedule.home_windows,
            },
            "coordination_policy": {
                "max_message_bandwidth_bits": self.coordination_policy.max_message_bandwidth_bits,
                "max_subtasks": self.coordination_policy.max_subtasks,
            },
            "dividend_basis_points": self.dividend_policy.basis_points,
            "source_reserve_cap": self.reserve_rule.max_active_external_per_field,
        }
        serialized = json.dumps(value, sort_keys=True)
        forbidden = ("practice_by_skill", "partner_models", "pair_memories", "organization_memory")
        if any(token in serialized for token in forbidden):
            raise AssertionError("capability or memory leaked into regulatory charter")
        return value

    def digest(self) -> str:
        return _sha256(self.snapshot())
