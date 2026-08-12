from __future__ import annotations

import inspect

import pytest

from resonance_world.w4a_joint_learning import JointEnvironment
from resonance_world.w6_mobility import PortableAgentState
from resonance_world.w7_competition import TalentContract
from resonance_world.w9_criticality import (
    CriticalityAwareServiceLedger,
    MarginalSourceCostEstimate,
    MissionStratumValue,
    SourceCostBudgetRule,
    SourceValueEstimate,
    marginal_interaction_pp,
)


def _state(agent_id: str, field_id: str = "field-a") -> PortableAgentState:
    return PortableAgentState(
        agent_id=agent_id,
        home_field_id=field_id,
        practice_by_skill=(("energy_storage", 4), ("mobility", 2)),
        evidence_refs=(f"evidence:{agent_id}",),
    )


def _contract(
    agent_id: str,
    *,
    organization_id: str = "org-alpha",
) -> TalentContract:
    return TalentContract(
        contract_id=f"contract:w9:{agent_id}",
        offer_id=f"offer:w9:{organization_id}:{agent_id}",
        organization_id=organization_id,
        agent_id=agent_id,
        window_id="w1",
        price=80,
        evidence_refs=(f"public:{agent_id}",),
    )


def _value(
    *,
    unavailable: frozenset[str] = frozenset(),
    energy: float = 0.8,
    mobility: float = 0.6,
    field_id: str = "field-a",
) -> SourceValueEstimate:
    return SourceValueEstimate(
        source_field_id=field_id,
        unavailable_agent_ids=unavailable,
        strata=(
            MissionStratumValue("energy", 0.75, energy),
            MissionStratumValue("mobility", 0.25, mobility),
        ),
        evidence_refs=("public:history",),
    )


def _estimate(
    agent_id: str,
    *,
    unavailable: frozenset[str] = frozenset(),
    loss_pp: float = 0.6,
    se_pp: float = 0.1,
) -> MarginalSourceCostEstimate:
    return MarginalSourceCostEstimate(
        source_field_id="field-a",
        agent_id=agent_id,
        already_unavailable_agent_ids=unavailable,
        estimated_loss_pp=loss_pp,
        standard_error_pp=se_pp,
        evidence_refs=("public:history",),
    )


def test_counterfactual_estimate_uses_weighted_contextual_source_value() -> None:
    before = _value()
    after = _value(
        unavailable=frozenset({"agent-a"}),
        energy=0.78,
        mobility=0.58,
    )

    estimate = MarginalSourceCostEstimate.from_counterfactuals(
        before=before,
        after=after,
        agent_id="agent-a",
        standard_error_pp=0.2,
    )

    assert before.weighted_value == pytest.approx(0.75)
    assert after.weighted_value == pytest.approx(0.73)
    assert estimate.estimated_loss_pp == pytest.approx(2.0)
    assert estimate.already_unavailable_agent_ids == frozenset()
    assert estimate.budget_cost_pp == pytest.approx(2.0 + 1.645 * 0.2)


def test_uncertainty_is_conservative_and_negative_loss_cannot_create_budget() -> None:
    certain = _estimate("agent-a", loss_pp=0.5, se_pp=0.0)
    uncertain = _estimate("agent-a", loss_pp=0.5, se_pp=0.4)
    negative = _estimate("agent-a", loss_pp=-1.0, se_pp=0.1)

    assert uncertain.budget_cost_pp > certain.budget_cost_pp
    assert certain.budget_cost_pp == pytest.approx(0.5)
    assert negative.budget_cost_pp == pytest.approx(0.0)


def test_set_valued_quotes_must_be_recomputed_after_each_grant() -> None:
    ledger = CriticalityAwareServiceLedger(SourceCostBudgetRule(max_budget_pp=2.0))
    state_a = _state("agent-a")
    state_b = _state("agent-b")

    ledger.grant(_contract("agent-a"), state_a, _estimate("agent-a", loss_pp=0.5))

    stale = _estimate("agent-b", loss_pp=0.5)
    with pytest.raises(ValueError, match="stale; recompute"):
        ledger.grant(
            _contract("agent-b", organization_id="org-beta"),
            state_b,
            stale,
        )

    contextual = _estimate(
        "agent-b",
        unavailable=frozenset({"agent-a"}),
        loss_pp=0.5,
    )
    ledger.grant(
        _contract("agent-b", organization_id="org-beta"),
        state_b,
        contextual,
    )

    assert ledger.active_agent_ids("field-a") == frozenset({"agent-a", "agent-b"})


def test_source_cost_budget_rejects_excess_conservative_loss() -> None:
    ledger = CriticalityAwareServiceLedger(SourceCostBudgetRule(max_budget_pp=2.0))
    state_a = _state("agent-a")
    state_b = _state("agent-b")

    first = _estimate("agent-a", loss_pp=0.8, se_pp=0.1)
    ledger.grant(_contract("agent-a"), state_a, first)

    second = _estimate(
        "agent-b",
        unavailable=frozenset({"agent-a"}),
        loss_pp=1.0,
        se_pp=0.1,
    )
    with pytest.raises(ValueError, match="source-cost budget exhausted"):
        ledger.grant(
            _contract("agent-b", organization_id="org-beta"),
            state_b,
            second,
        )

    assert ledger.budget_used_pp("field-a") == pytest.approx(first.budget_cost_pp)


def test_service_rights_do_not_mutate_portable_agent_state() -> None:
    ledger = CriticalityAwareServiceLedger()
    state = _state("agent-a")
    before = state.digest()

    right = ledger.grant(_contract("agent-a"), state, _estimate("agent-a"))

    assert state.digest() == before
    assert right.state_sha256 == before
    assert ledger.release(right.contract_id) == right
    assert state.digest() == before
    assert ledger.active_agent_ids("field-a") == frozenset()
    assert ledger.budget_used_pp("field-a") == pytest.approx(0.0)


def test_counterfactuals_require_same_strata_and_exact_added_agent_context() -> None:
    before = _value(unavailable=frozenset({"agent-b"}))
    wrong_context = _value(unavailable=frozenset({"agent-a"}))

    with pytest.raises(ValueError, match="add exactly the candidate"):
        MarginalSourceCostEstimate.from_counterfactuals(
            before=before,
            after=wrong_context,
            agent_id="agent-a",
            standard_error_pp=0.1,
        )

    changed_weights = SourceValueEstimate(
        source_field_id="field-a",
        unavailable_agent_ids=frozenset({"agent-a", "agent-b"}),
        strata=(
            MissionStratumValue("energy", 0.5, 0.75),
            MissionStratumValue("mobility", 0.5, 0.55),
        ),
        evidence_refs=("public:history",),
    )
    with pytest.raises(ValueError, match="identical mission strata and weights"):
        MarginalSourceCostEstimate.from_counterfactuals(
            before=before,
            after=changed_weights,
            agent_id="agent-a",
            standard_error_pp=0.1,
        )


def test_pairwise_interaction_measures_context_dependence() -> None:
    unconditional = _estimate("agent-a", loss_pp=0.4)
    conditional = _estimate(
        "agent-a",
        unavailable=frozenset({"agent-b"}),
        loss_pp=1.3,
    )

    assert marginal_interaction_pp(
        unconditional=unconditional,
        conditional=conditional,
    ) == pytest.approx(0.9)

    with pytest.raises(ValueError, match="same candidate"):
        marginal_interaction_pp(
            unconditional=unconditional,
            conditional=_estimate(
                "agent-c",
                unavailable=frozenset({"agent-b"}),
                loss_pp=1.3,
            ),
        )


def test_criticality_ledger_serialization_contains_no_private_competence_or_memory() -> None:
    ledger = CriticalityAwareServiceLedger()
    ledger.grant(_contract("agent-a"), _state("agent-a"), _estimate("agent-a"))

    serialized = str(ledger.snapshot())
    assert "practice_by_skill" not in serialized
    assert "partner_models" not in serialized
    assert "pair_memories" not in serialized
    assert "organization_memory" not in serialized
    assert ledger.digest()


def test_joint_environment_still_has_no_w9_regulatory_input_channel() -> None:
    parameters = set(inspect.signature(JointEnvironment.evaluate).parameters)
    forbidden = {
        "budget",
        "criticality",
        "lease",
        "marginal_source_cost",
        "regulation",
        "source_cost",
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
