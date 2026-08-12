"""World-side W9 criticality accounting primitives.

The module prices external service rights by predicted marginal source loss. It stores
only public-evidence counterfactual estimates and immutable state digests; it does not
expose a new capability channel to mission-success laws.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field

from .w6_mobility import PortableAgentState
from .w7_competition import TalentContract

DEFAULT_CONSERVATIVE_Z = 1.645


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _normalized_refs(values: tuple[str, ...]) -> tuple[str, ...]:
    refs = tuple(sorted({str(value) for value in values if str(value)}))
    if not refs:
        raise ValueError("public evidence references must be non-empty")
    return refs


def _normalized_agent_ids(values: frozenset[str]) -> frozenset[str]:
    normalized = frozenset(str(value) for value in values if str(value))
    if len(normalized) != len(values):
        raise ValueError("unavailable-agent identifiers must be non-empty")
    return normalized


@dataclass(frozen=True, slots=True)
class MissionStratumValue:
    """Public-evidence estimate for one preregistered source mission stratum."""

    stratum_id: str
    weight: float
    expected_success: float

    def __post_init__(self) -> None:
        if not self.stratum_id:
            raise ValueError("stratum_id must be non-empty")
        if not 0 <= self.weight <= 1:
            raise ValueError("stratum weight must lie in [0, 1]")
        if not 0 <= self.expected_success <= 1:
            raise ValueError("expected success must lie in [0, 1]")

    def as_dict(self) -> dict[str, object]:
        return {
            "expected_success": self.expected_success,
            "stratum_id": self.stratum_id,
            "weight": self.weight,
        }


@dataclass(frozen=True, slots=True)
class SourceValueEstimate:
    """Estimated source value for one explicit unavailable-agent context."""

    source_field_id: str
    unavailable_agent_ids: frozenset[str]
    strata: tuple[MissionStratumValue, ...]
    evidence_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.source_field_id:
            raise ValueError("source_field_id must be non-empty")
        object.__setattr__(
            self,
            "unavailable_agent_ids",
            _normalized_agent_ids(self.unavailable_agent_ids),
        )
        object.__setattr__(self, "evidence_refs", _normalized_refs(self.evidence_refs))
        if not self.strata:
            raise ValueError("source value estimate requires mission strata")
        ids = [item.stratum_id for item in self.strata]
        if len(ids) != len(set(ids)):
            raise ValueError("mission stratum identifiers must be unique")
        if abs(sum(item.weight for item in self.strata) - 1.0) > 1e-9:
            raise ValueError("mission stratum weights must sum to one")

    @property
    def weighted_value(self) -> float:
        return sum(item.weight * item.expected_success for item in self.strata)

    @property
    def stratum_signature(self) -> tuple[tuple[str, float], ...]:
        return tuple(sorted((item.stratum_id, item.weight) for item in self.strata))

    def as_dict(self) -> dict[str, object]:
        return {
            "evidence_refs": list(self.evidence_refs),
            "source_field_id": self.source_field_id,
            "strata": [item.as_dict() for item in self.strata],
            "unavailable_agent_ids": sorted(self.unavailable_agent_ids),
            "weighted_value": self.weighted_value,
        }


@dataclass(frozen=True, slots=True)
class MarginalSourceCostEstimate:
    """Contextual source-loss estimate for making one additional agent unavailable."""

    source_field_id: str
    agent_id: str
    already_unavailable_agent_ids: frozenset[str]
    estimated_loss_pp: float
    standard_error_pp: float
    evidence_refs: tuple[str, ...]
    conservative_z: float = DEFAULT_CONSERVATIVE_Z

    def __post_init__(self) -> None:
        if not self.source_field_id or not self.agent_id:
            raise ValueError("source and agent identifiers must be non-empty")
        object.__setattr__(
            self,
            "already_unavailable_agent_ids",
            _normalized_agent_ids(self.already_unavailable_agent_ids),
        )
        if self.agent_id in self.already_unavailable_agent_ids:
            raise ValueError("candidate agent is already unavailable")
        if self.standard_error_pp < 0:
            raise ValueError("standard error must be non-negative")
        if self.conservative_z < 0:
            raise ValueError("conservative z-score must be non-negative")
        object.__setattr__(self, "evidence_refs", _normalized_refs(self.evidence_refs))

    @property
    def budget_cost_pp(self) -> float:
        quoted = self.estimated_loss_pp + self.conservative_z * self.standard_error_pp
        return max(0.0, quoted)

    @classmethod
    def from_counterfactuals(
        cls,
        *,
        before: SourceValueEstimate,
        after: SourceValueEstimate,
        agent_id: str,
        standard_error_pp: float,
        conservative_z: float = DEFAULT_CONSERVATIVE_Z,
    ) -> MarginalSourceCostEstimate:
        if before.source_field_id != after.source_field_id:
            raise ValueError("counterfactuals must refer to the same source Field")
        if before.stratum_signature != after.stratum_signature:
            raise ValueError("counterfactuals must use identical mission strata and weights")
        expected_after = before.unavailable_agent_ids | {agent_id}
        if after.unavailable_agent_ids != expected_after:
            raise ValueError("after counterfactual must add exactly the candidate agent")
        refs = tuple(sorted(set(before.evidence_refs) | set(after.evidence_refs)))
        return cls(
            source_field_id=before.source_field_id,
            agent_id=agent_id,
            already_unavailable_agent_ids=before.unavailable_agent_ids,
            estimated_loss_pp=(before.weighted_value - after.weighted_value) * 100.0,
            standard_error_pp=standard_error_pp,
            evidence_refs=refs,
            conservative_z=conservative_z,
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "agent_id": self.agent_id,
            "already_unavailable_agent_ids": sorted(self.already_unavailable_agent_ids),
            "budget_cost_pp": self.budget_cost_pp,
            "conservative_z": self.conservative_z,
            "estimated_loss_pp": self.estimated_loss_pp,
            "evidence_refs": list(self.evidence_refs),
            "source_field_id": self.source_field_id,
            "standard_error_pp": self.standard_error_pp,
        }


def marginal_interaction_pp(
    *,
    unconditional: MarginalSourceCostEstimate,
    conditional: MarginalSourceCostEstimate,
) -> float:
    """Return I(a,b): how much agent a's marginal cost changes after other absences."""

    if unconditional.source_field_id != conditional.source_field_id:
        raise ValueError("interaction estimates must refer to the same source Field")
    if unconditional.agent_id != conditional.agent_id:
        raise ValueError("interaction estimates must refer to the same candidate agent")
    if unconditional.already_unavailable_agent_ids:
        raise ValueError("unconditional interaction estimate must use an empty context")
    if not conditional.already_unavailable_agent_ids:
        raise ValueError("conditional interaction estimate must include another absence")
    return conditional.estimated_loss_pp - unconditional.estimated_loss_pp


@dataclass(frozen=True, slots=True)
class SourceCostBudgetRule:
    """Maximum conservative marginal source loss per simultaneously unavailable set."""

    max_budget_pp: float = 2.0
    conservative_z: float = DEFAULT_CONSERVATIVE_Z

    def __post_init__(self) -> None:
        if self.max_budget_pp < 0:
            raise ValueError("source-cost budget must be non-negative")
        if self.conservative_z < 0:
            raise ValueError("conservative z-score must be non-negative")

    def allows(
        self,
        *,
        current_budget_pp: float,
        estimate: MarginalSourceCostEstimate,
    ) -> bool:
        if current_budget_pp < 0:
            raise ValueError("current source-cost budget must be non-negative")
        if abs(estimate.conservative_z - self.conservative_z) > 1e-12:
            raise ValueError("estimate uses a different conservative z-score")
        return current_budget_pp + estimate.budget_cost_pp <= self.max_budget_pp + 1e-12


@dataclass(frozen=True, slots=True)
class CriticalityServiceRight:
    """Auditable W9 service right priced against one exact source-unavailability set."""

    contract_id: str
    organization_id: str
    agent_id: str
    source_field_id: str
    window_id: str
    quote_context_agent_ids: frozenset[str]
    source_cost_pp: float
    state_sha256: str
    evidence_refs: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "agent_id": self.agent_id,
            "contract_id": self.contract_id,
            "evidence_refs": list(self.evidence_refs),
            "organization_id": self.organization_id,
            "quote_context_agent_ids": sorted(self.quote_context_agent_ids),
            "source_cost_pp": self.source_cost_pp,
            "source_field_id": self.source_field_id,
            "state_sha256": self.state_sha256,
            "window_id": self.window_id,
        }


@dataclass(slots=True)
class CriticalityAwareServiceLedger:
    """Enforce contextual source-loss budgets over already-priced W7 contracts."""

    budget_rule: SourceCostBudgetRule = field(default_factory=SourceCostBudgetRule)
    _rights: dict[str, CriticalityServiceRight] = field(default_factory=dict)
    _active_agents_by_source: dict[str, set[str]] = field(default_factory=dict)
    _budget_by_source: dict[str, float] = field(default_factory=dict)

    def grant(
        self,
        contract: TalentContract,
        state: PortableAgentState,
        estimate: MarginalSourceCostEstimate,
    ) -> CriticalityServiceRight:
        if contract.contract_id in self._rights:
            raise ValueError(f"service right already registered: {contract.contract_id}")
        if contract.agent_id != state.agent_id or estimate.agent_id != state.agent_id:
            raise ValueError("contract, state, and source-cost estimate identity mismatch")
        if estimate.source_field_id != state.home_field_id:
            raise ValueError("source-cost estimate refers to a different source Field")

        active = self._active_agents_by_source.setdefault(state.home_field_id, set())
        if state.agent_id in active:
            raise ValueError(f"agent already unavailable: {state.agent_id}")
        expected_context = frozenset(active)
        if estimate.already_unavailable_agent_ids != expected_context:
            raise ValueError("source-cost quote is stale; recompute the quote for current absences")

        current_budget = self._budget_by_source.get(state.home_field_id, 0.0)
        if not self.budget_rule.allows(
            current_budget_pp=current_budget,
            estimate=estimate,
        ):
            raise ValueError(f"source-cost budget exhausted: {state.home_field_id}")

        right = CriticalityServiceRight(
            contract_id=contract.contract_id,
            organization_id=contract.organization_id,
            agent_id=state.agent_id,
            source_field_id=state.home_field_id,
            window_id=contract.window_id,
            quote_context_agent_ids=estimate.already_unavailable_agent_ids,
            source_cost_pp=estimate.budget_cost_pp,
            state_sha256=state.digest(),
            evidence_refs=tuple(
                sorted(set(contract.evidence_refs) | set(estimate.evidence_refs))
            ),
        )
        self._rights[contract.contract_id] = right
        active.add(state.agent_id)
        self._budget_by_source[state.home_field_id] = current_budget + right.source_cost_pp
        return right

    def release(self, contract_id: str) -> CriticalityServiceRight:
        try:
            right = self._rights.pop(contract_id)
        except KeyError as exc:
            raise KeyError(f"unknown active service right: {contract_id}") from exc
        self._active_agents_by_source[right.source_field_id].remove(right.agent_id)
        remaining = self._budget_by_source.get(right.source_field_id, 0.0) - right.source_cost_pp
        self._budget_by_source[right.source_field_id] = max(0.0, remaining)
        return right

    def active_agent_ids(self, source_field_id: str) -> frozenset[str]:
        return frozenset(self._active_agents_by_source.get(source_field_id, set()))

    def budget_used_pp(self, source_field_id: str) -> float:
        return self._budget_by_source.get(source_field_id, 0.0)

    def rights(self) -> tuple[CriticalityServiceRight, ...]:
        return tuple(self._rights[key] for key in sorted(self._rights))

    def snapshot(self) -> dict[str, object]:
        value = {
            "budget_rule": {
                "conservative_z": self.budget_rule.conservative_z,
                "max_budget_pp": self.budget_rule.max_budget_pp,
            },
            "budget_used_pp": dict(sorted(self._budget_by_source.items())),
            "rights": [right.as_dict() for right in self.rights()],
        }
        serialized = json.dumps(value, sort_keys=True)
        forbidden = (
            "practice_by_skill",
            "partner_models",
            "pair_memories",
            "organization_memory",
        )
        if any(token in serialized for token in forbidden):
            raise AssertionError("capability or memory leaked into criticality ledger")
        return value

    def digest(self) -> str:
        return _sha256(self.snapshot())
