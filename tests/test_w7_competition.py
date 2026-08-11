from __future__ import annotations

import inspect
import json

import pytest

from resonance_world.w4a_joint_learning import IndividualState, JointEnvironment
from resonance_world.w5a_organization import OrganizationEnvironment, OrganizationMemory, OrganizationState
from resonance_world.w6_mobility import PortableAgentState
from resonance_world.w7_competition import CooperationAgreement, TalentMarket, TalentOffer


def _agent(agent_id: str, home: str, water: int, energy: int) -> PortableAgentState:
    return PortableAgentState.from_individual(
        IndividualState(agent_id, {"water_systems": water, "energy_storage": energy}),
        home_field_id=home,
        evidence_refs=(f"field://{home}/{agent_id}",),
    )


def _organization(organization_id: str) -> OrganizationState:
    member = IndividualState(f"incumbent-{organization_id}", {"water_systems": 1})
    memory = OrganizationMemory()
    return OrganizationState(organization_id, {member.agent_id: member}, memory)


def _offer(
    offer_id: str,
    organization_id: str,
    agent_id: str,
    bid: int,
    *,
    window: str = "window-1",
) -> TalentOffer:
    return TalentOffer(
        offer_id=offer_id,
        organization_id=organization_id,
        agent_id=agent_id,
        window_id=window,
        bid=bid,
        evidence_refs=(f"public://recruitment/{agent_id}",),
    )


def _market() -> tuple[TalentMarket, OrganizationState, OrganizationState]:
    market = TalentMarket()
    alpha = _organization("org-alpha")
    beta = _organization("org-beta")
    market.register_organization(alpha, budget=100)
    market.register_organization(beta, budget=100)
    market.register_agent(_agent("agent-1", "field-a", 5, 2))
    market.register_agent(_agent("agent-2", "field-b", 2, 5))
    return market, alpha, beta


def test_competing_organizations_receive_one_exclusive_contract() -> None:
    market, _, _ = _market()
    market.submit_offer(_offer("alpha-1", "org-alpha", "agent-1", 50))
    market.submit_offer(_offer("beta-1", "org-beta", "agent-1", 60))

    contracts = market.settle("window-1")

    assert len(contracts) == 1
    assert contracts[0].organization_id == "org-beta"
    assert contracts[0].price == 60
    assert market.contract("window-1", "agent-1") == contracts[0]
    assert market.account("org-alpha").balance == 100
    assert market.account("org-beta").balance == 40


def test_ties_break_deterministically_by_organization_then_offer() -> None:
    first, _, _ = _market()
    second, _, _ = _market()
    for market in (first, second):
        market.submit_offer(_offer("zeta", "org-beta", "agent-1", 60))
        market.submit_offer(_offer("omega", "org-alpha", "agent-1", 60))
        market.submit_offer(_offer("alpha", "org-alpha", "agent-1", 60))

    first_contract = first.settle("window-1")[0]
    second_contract = second.settle("window-1")[0]

    assert first_contract.organization_id == "org-alpha"
    assert first_contract.offer_id == "alpha"
    assert first_contract == second_contract
    assert first.digest() == second.digest()


def test_budget_constraint_prevents_overspend_across_multiple_awards() -> None:
    market, _, _ = _market()
    market.submit_offer(_offer("alpha-agent-1", "org-alpha", "agent-1", 70))
    market.submit_offer(_offer("alpha-agent-2", "org-alpha", "agent-2", 70))
    market.submit_offer(_offer("beta-agent-2", "org-beta", "agent-2", 60))

    contracts = market.settle("window-1")

    assert {(contract.agent_id, contract.organization_id) for contract in contracts} == {
        ("agent-1", "org-alpha"),
        ("agent-2", "org-beta"),
    }
    assert market.account("org-alpha").balance == 30
    assert market.account("org-beta").balance == 40


def test_offer_above_frozen_budget_is_rejected() -> None:
    market, _, _ = _market()
    with pytest.raises(ValueError, match="exceeds organization's frozen"):
        market.submit_offer(_offer("too-large", "org-alpha", "agent-1", 101))


def test_market_settlement_changes_rights_and_budget_not_agent_or_org_memory() -> None:
    market, alpha, beta = _market()
    agent_before = {
        agent.agent_id: agent.digest()
        for agent in (
            market._agents["agent-1"],  # noqa: SLF001 - invariant inspection
            market._agents["agent-2"],  # noqa: SLF001 - invariant inspection
        )
    }
    alpha_memory_before = json.dumps(alpha.memory.snapshot(), sort_keys=True)
    beta_memory_before = json.dumps(beta.memory.snapshot(), sort_keys=True)

    market.submit_offer(_offer("alpha-1", "org-alpha", "agent-1", 50))
    market.submit_offer(_offer("beta-1", "org-beta", "agent-1", 60))
    market.settle("window-1")

    assert market._agents["agent-1"].digest() == agent_before["agent-1"]  # noqa: SLF001
    assert market._agents["agent-2"].digest() == agent_before["agent-2"]  # noqa: SLF001
    assert json.dumps(alpha.memory.snapshot(), sort_keys=True) == alpha_memory_before
    assert json.dumps(beta.memory.snapshot(), sort_keys=True) == beta_memory_before


def test_coalition_uses_contracted_members_without_transferring_ownership_or_memory() -> None:
    market, alpha, beta = _market()
    market.submit_offer(_offer("alpha-1", "org-alpha", "agent-1", 55))
    market.submit_offer(_offer("beta-2", "org-beta", "agent-2", 55))
    market.settle("window-1")
    alpha_memory_before = json.dumps(alpha.memory.snapshot(), sort_keys=True)
    beta_memory_before = json.dumps(beta.memory.snapshot(), sort_keys=True)
    balances_before = {
        "org-alpha": market.account("org-alpha").balance,
        "org-beta": market.account("org-beta").balance,
    }

    deployment = market.prepare_coalition(
        CooperationAgreement(
            agreement_id="coalition-1",
            window_id="window-1",
            mission_id="mission-shared",
            contributions=(("org-alpha", "agent-1"), ("org-beta", "agent-2")),
            evidence_refs=("world://coalition/coalition-1",),
        )
    )

    assert tuple(member.agent_id for member in deployment.members) == ("agent-1", "agent-2")
    assert market.contract("window-1", "agent-1").organization_id == "org-alpha"  # type: ignore[union-attr]
    assert market.contract("window-1", "agent-2").organization_id == "org-beta"  # type: ignore[union-attr]
    assert market.account("org-alpha").balance == balances_before["org-alpha"]
    assert market.account("org-beta").balance == balances_before["org-beta"]
    assert json.dumps(alpha.memory.snapshot(), sort_keys=True) == alpha_memory_before
    assert json.dumps(beta.memory.snapshot(), sort_keys=True) == beta_memory_before


def test_invalid_coalition_ownership_and_duplicate_contribution_are_rejected() -> None:
    market, _, _ = _market()
    market.submit_offer(_offer("alpha-1", "org-alpha", "agent-1", 55))
    market.submit_offer(_offer("beta-2", "org-beta", "agent-2", 55))
    market.settle("window-1")

    with pytest.raises(ValueError, match="not owned"):
        market.prepare_coalition(
            CooperationAgreement(
                agreement_id="wrong-owner",
                window_id="window-1",
                mission_id="mission-shared",
                contributions=(("org-beta", "agent-1"), ("org-alpha", "agent-2")),
                evidence_refs=("world://coalition/wrong-owner",),
            )
        )

    with pytest.raises(ValueError, match="contributed twice"):
        CooperationAgreement(
            agreement_id="duplicate",
            window_id="window-1",
            mission_id="mission-shared",
            contributions=(("org-alpha", "agent-1"), ("org-beta", "agent-1")),
            evidence_refs=("world://coalition/duplicate",),
        )


def test_public_offer_schema_has_no_private_practice_channel() -> None:
    parameters = set(inspect.signature(TalentOffer).parameters)
    forbidden = {
        "practice_by_skill",
        "private_state",
        "portable_state",
        "home_reputation",
        "organization_memory",
    }
    assert not parameters & forbidden
    payload = json.dumps(_offer("offer-1", "org-alpha", "agent-1", 50).as_dict())
    assert "practice_by_skill" not in payload


def test_mission_outcome_laws_remain_market_and_coalition_blind() -> None:
    forbidden = {
        "bid",
        "budget",
        "coalition",
        "competition",
        "contract",
        "market",
        "organization_count",
        "price",
        "rival",
    }
    organization_parameters = set(inspect.signature(OrganizationEnvironment.evaluate).parameters)
    joint_parameters = set(inspect.signature(JointEnvironment.evaluate).parameters)
    assert not organization_parameters & forbidden
    assert not joint_parameters & forbidden


def test_window_cannot_be_settled_twice_and_late_offers_are_rejected() -> None:
    market, _, _ = _market()
    market.submit_offer(_offer("alpha-1", "org-alpha", "agent-1", 50))
    market.settle("window-1")

    with pytest.raises(ValueError, match="already settled"):
        market.settle("window-1")
    with pytest.raises(ValueError, match="already settled"):
        market.submit_offer(_offer("late", "org-beta", "agent-2", 50))
