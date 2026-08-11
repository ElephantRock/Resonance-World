from __future__ import annotations

import inspect

import pytest

from resonance_world.w4a_joint_learning import JointEnvironment
from resonance_world.w6_mobility import PortableAgentState
from resonance_world.w7_competition import TalentContract
from resonance_world.w8_regulation import (
    BenchmarkAssignment,
    BudgetUpdatePolicy,
    CapabilityStockObservation,
    CirculationSchedule,
    CoalitionCoordinationContract,
    CoalitionCoordinationPolicy,
    CoalitionSubtask,
    RegulatedServiceLedger,
    RegulatoryCharter,
    SourceDividendLedger,
    SourceDividendPolicy,
    SourceReserveRule,
)


def _state(agent_id: str, field_id: str = "field-a") -> PortableAgentState:
    return PortableAgentState(
        agent_id=agent_id,
        home_field_id=field_id,
        practice_by_skill=(("energy_storage", 4), ("mobility", 2)),
        evidence_refs=(f"evidence:{agent_id}",),
    )


def _contract(agent_id: str, *, organization_id: str = "org-alpha", price: int = 80) -> TalentContract:
    return TalentContract(
        contract_id=f"contract:w1:{agent_id}",
        offer_id=f"offer:w1:{organization_id}:{agent_id}",
        organization_id=organization_id,
        agent_id=agent_id,
        window_id="w1",
        price=price,
        evidence_refs=(f"public:{agent_id}",),
    )


def test_source_reserve_caps_active_external_rights_without_mutating_agent_state() -> None:
    rule = SourceReserveRule(max_active_external_per_field=2)
    ledger = RegulatedServiceLedger(rule)
    states = [_state(f"agent-{idx}") for idx in range(3)]
    before = [state.digest() for state in states]

    ledger.grant(_contract("agent-0"), states[0])
    ledger.grant(_contract("agent-1", organization_id="org-beta"), states[1])
    with pytest.raises(ValueError, match="source reserve exhausted"):
        ledger.grant(_contract("agent-2", organization_id="org-gamma"), states[2])

    assert ledger.active_count("field-a") == 2
    assert [state.digest() for state in states] == before

    ledger.release("contract:w1:agent-0")
    ledger.grant(_contract("agent-2", organization_id="org-gamma"), states[2])
    assert ledger.active_count("field-a") == 2
    assert [state.digest() for state in states] == before


def test_circulation_schedules_expose_4_to_2_and_3_to_3_duty_cycles() -> None:
    four_two = CirculationSchedule(external_windows=4, home_windows=2)
    three_three = CirculationSchedule(external_windows=3, home_windows=3)

    assert [four_two.phase(idx) for idx in range(6)] == [
        "external",
        "external",
        "external",
        "external",
        "home",
        "home",
    ]
    assert [three_three.phase(idx) for idx in range(6)] == [
        "external",
        "external",
        "external",
        "home",
        "home",
        "home",
    ]
    assert four_two.external_share() == pytest.approx(2 / 3)
    assert three_three.external_share() == pytest.approx(0.5)


def test_source_dividend_creates_non_targeted_field_budget_only() -> None:
    policy = SourceDividendPolicy(basis_points=5_000)
    ledger = SourceDividendLedger(policy)
    state = _state("agent-0")
    before = state.digest()

    grant = ledger.credit(_contract("agent-0", price=81), state)

    assert grant.amount == 40
    assert grant.source_field_id == "field-a"
    assert ledger.balance("field-a") == 40
    assert state.digest() == before
    payload = grant.as_dict()
    assert "skill" not in str(payload).lower()
    assert "target" not in str(payload).lower()


def test_coordination_contract_grants_bounded_rights_without_state_payload() -> None:
    contract = CoalitionCoordinationContract(
        contract_id="coalition:w1:m1",
        mission_id="m1",
        window_id="w1",
        subtasks=(
            CoalitionSubtask("org-alpha", "agent-a", "energy_storage", "lead"),
            CoalitionSubtask("org-beta", "agent-b", "public_health", "support"),
        ),
        message_bandwidth_bits=1,
        evidence_refs=("coalition-evidence",),
    )
    policy = CoalitionCoordinationPolicy(max_message_bandwidth_bits=1, max_subtasks=2)
    policy.validate(contract)

    payload = contract.as_dict()
    serialized = str(payload)
    assert "practice_by_skill" not in serialized
    assert "pair_memory" not in serialized
    assert "organization_memory" not in serialized

    too_wide = CoalitionCoordinationContract(
        contract_id="coalition:w1:m2",
        mission_id="m2",
        window_id="w1",
        subtasks=contract.subtasks,
        message_bandwidth_bits=2,
        evidence_refs=("coalition-evidence",),
    )
    with pytest.raises(ValueError, match="communication budget exceeded"):
        policy.validate(too_wide)


def test_budget_feedback_is_explicit_and_separable() -> None:
    neutral = BudgetUpdatePolicy(mode="neutral", base_budget=220)
    compounding = BudgetUpdatePolicy(
        mode="compounding",
        base_budget=220,
        reward_per_success=10,
        max_budget=500,
    )

    assert neutral.next_budget(current_budget=400, spend=180, successes=9) == 220
    assert compounding.next_budget(current_budget=220, spend=100, successes=12) == 240
    assert compounding.next_budget(current_budget=490, spend=0, successes=12) == 500


def test_capability_stock_counts_each_living_agent_once() -> None:
    observation = CapabilityStockObservation(
        assignments=(
            BenchmarkAssignment("m1", "agent-a", 0.7),
            BenchmarkAssignment("m2", "agent-b", 0.6),
        ),
        living_agent_ids=frozenset({"agent-a", "agent-b", "agent-c"}),
        cumulative_development_compute=13.0,
    )
    assert observation.stock == pytest.approx(1.3)
    assert observation.compute_normalized_stock == pytest.approx(0.1)

    with pytest.raises(ValueError, match="double-count"):
        CapabilityStockObservation(
            assignments=(
                BenchmarkAssignment("m1", "agent-a", 0.7),
                BenchmarkAssignment("m2", "agent-a", 0.5),
            ),
            living_agent_ids=frozenset({"agent-a"}),
            cumulative_development_compute=1.0,
        )


def test_regulatory_charter_contains_rules_not_competence_or_memory() -> None:
    charter = RegulatoryCharter(
        reserve_rule=SourceReserveRule(2),
        circulation_schedule=CirculationSchedule(4, 2),
        dividend_policy=SourceDividendPolicy(5_000),
        coordination_policy=CoalitionCoordinationPolicy(1, 2),
        budget_policy=BudgetUpdatePolicy(mode="neutral", base_budget=220),
    )
    payload = charter.snapshot()
    serialized = str(payload)

    assert payload["source_reserve_cap"] == 2
    assert "practice_by_skill" not in serialized
    assert "partner_models" not in serialized
    assert "pair_memories" not in serialized


def test_joint_environment_has_no_regulatory_input_channel() -> None:
    parameters = set(inspect.signature(JointEnvironment.evaluate).parameters)
    forbidden = {
        "budget",
        "charter",
        "coalition",
        "contract",
        "dividend",
        "price",
        "regulation",
        "reserve",
    }
    assert parameters.isdisjoint(forbidden)
    assert parameters == {
        "self",
        "first",
        "second",
        "mission",
        "first_action",
        "second_action",
        "seed",
    }
