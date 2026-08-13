from __future__ import annotations

import json

import pytest

from resonance_world.o1_reconstruction import (
    claims_to_event_ledger,
    reconstruct_products,
)


def _event_claims(
    *,
    scope_id: str,
    event_id: str,
    observed_at: int,
    source_class: str,
    fields: dict[str, str],
) -> list[dict[str, object]]:
    return [
        {
            "scope_id": scope_id,
            "subject": event_id,
            "predicate": predicate,
            "object": object_value,
            "source_class": source_class,
            "observed_at": observed_at,
        }
        for predicate, object_value in fields.items()
    ]


def _synthetic_claims() -> list[dict[str, object]]:
    claims: list[dict[str, object]] = []
    claims += _event_claims(
        scope_id="o0:communication-0:7001",
        event_id="episode-1",
        observed_at=1,
        source_class="world_observation",
        fields={
            "event_type": "joint_episode",
            "context": "test-context",
            "lead_skill": "planning",
            "support_skill": "verification",
            "participant_a": "agent-a",
            "action_a": "lead",
            "participant_b": "agent-b",
            "action_b": "support",
            "outcome": "success",
        },
    )
    claims += _event_claims(
        scope_id="o1:A:attested:test",
        event_id="authority-1",
        observed_at=1,
        source_class="world_authority_observation",
        fields={
            "event_type": "authority_resolution",
            "organization_id": "org-test",
            "arm": "attested",
            "scenario_id": "scenario-1",
            "agent_id": "agent-c",
            "role_id": "role-1",
            "notice_1_id": "notice-1",
            "notice_1_action": "OBSERVE",
            "notice_2_id": "notice-2",
            "notice_2_action": "SLEEP",
            "verified_notice_id": "notice-1",
            "rejected_notice_id": "notice-2",
            "controller_action": "OBSERVE",
            "intended_action": "OBSERVE",
            "speech_action": "OBSERVE",
            "policy_result": "allow",
            "outcome_status": "succeeded",
            "grounded_success": "true",
            "action_request_id": "request-1",
            "correlation_id": "correlation-1",
        },
    )
    for ordinal, generation, members, predecessor in (
        (1, "generation-0", ["member-a", "member-b"], ""),
        (2, "generation-1", ["member-c", "member-d"], "generation-0"),
    ):
        claims += _event_claims(
            scope_id="o1:T:unit-1",
            event_id=f"org-test:{generation}",
            observed_at=ordinal,
            source_class="world_organization_observation",
            fields={
                "event_type": "organization_generation",
                "organization_id": "org-test",
                "generation_id": generation,
                "predecessor_generation_id": predecessor,
                "member_ids": json.dumps(members, separators=(",", ":")),
                "source_field_id": "source-test",
            },
        )
    for ordinal, arm, strategy, successes in (
        (3, "model_reset", "balanced", 1),
        (5, "model_retained", "specialist", 2),
    ):
        memory_id = f"org-test:{arm}:memory-summary"
        claims += _event_claims(
            scope_id="o1:T:unit-1",
            event_id=memory_id,
            observed_at=ordinal,
            source_class="world_institutional_state_observation",
            fields={
                "event_type": "institutional_memory_summary",
                "organization_id": "org-test",
                "generation_id": "generation-1",
                "arm": arm,
                "evidence_episodes": "2",
                "role_specific_posterior": "0.6",
                "cross_coverage_posterior": "0.4",
                "forecast_specialist": "0.7",
                "forecast_balanced": "0.3",
                "forecast_preferred_strategy": strategy,
            },
        )
        claims += _event_claims(
            scope_id="o1:T:unit-1",
            event_id=f"org-test:{arm}:decision",
            observed_at=ordinal + 1,
            source_class="world_execution_observation",
            fields={
                "event_type": "post_turnover_decision",
                "organization_id": "org-test",
                "generation_id": "generation-1",
                "unit_id": "unit-1",
                "arm": arm,
                "context": "unit-1",
                "lead_skill": "skill-a",
                "support_skill": "skill-b",
                "member_ids": '["member-c","member-d"]',
                "memory_source_ref": memory_id,
                "forecast_preferred_strategy": strategy,
                "chosen_strategy": strategy,
                "intended_strategy": strategy,
                "speech_strategy": strategy,
                "lead_member_id": "member-c",
                "support_member_id": "member-d",
                "evaluation_trials": "2",
                "success_count": str(successes),
                "grounded_success": str(successes == 2).lower(),
                "acknowledgement": f"trials=2; successes={successes}",
            },
        )
    claims += _event_claims(
        scope_id="o1:S:source-test",
        event_id="source-test:agent-s",
        observed_at=1,
        source_class="world_public_source_observation",
        fields={
            "event_type": "source_agent_public_record",
            "source_id": "source-test",
            "agent_id": "agent-s",
            "source_evidence_sha256": "abc",
            "dominant_success_skill": "skill-a",
            "secondary_success_skill": "skill-b",
        },
    )
    claims += _event_claims(
        scope_id="o1:S:w9-06:selected",
        event_id="contract:00:org-test:agent-s",
        observed_at=1,
        source_class="world_market_observation",
        fields={
            "event_type": "contract_service_right",
            "cycle": "0",
            "organization_id": "org-test",
            "agent_id": "agent-s",
            "source_id": "source-test",
            "price": "50",
            "lead_skill": "skill-a",
            "support_skill": "skill-b",
        },
    )
    claims += _event_claims(
        scope_id="o1:S:w9-06:selected",
        event_id="service:0:org-test",
        observed_at=1,
        source_class="world_service_observation",
        fields={
            "event_type": "organization_service_cycle",
            "cycle": "0",
            "organization_id": "org-test",
            "lead_skill": "skill-a",
            "support_skill": "skill-b",
            "lead_agent_id": "agent-s",
            "support_agent_id": "agent-t",
            "attempt_count": "2",
            "success_count": "1",
            "failure_count": "1",
        },
    )
    claims += _event_claims(
        scope_id="o1:S:w9-06:selected",
        event_id="service-summary:org-test",
        observed_at=2,
        source_class="world_service_observation",
        fields={
            "event_type": "organization_service_summary",
            "organization_id": "org-test",
            "attempt_count": "2",
            "success_count": "1",
            "failure_count": "1",
        },
    )
    claims += _event_claims(
        scope_id="o1:S:w9-06:selected",
        event_id="observable-accounting",
        observed_at=3,
        source_class="world_accounting_observation",
        fields={
            "event_type": "observable_accounting_summary",
            "external_agent_cycle_exposures": "1",
            "incremental_source_development_compute": "0.0",
            "mission_execution_compute": "2.0",
            "organization_coordination_compute": "1.0",
            "world_regulatory_estimation_compute": "1.0",
        },
    )
    return claims


def test_registered_reconstruction_products_are_deterministic_and_typed() -> None:
    products = reconstruct_products(_synthetic_claims())
    assert len(products["authority-ledger.json"]["records"]) == 1
    lineage = products["organization-lineage.json"]["organizations"]
    assert len(lineage) == 1
    assert lineage[0]["turnover_fraction"] == 1.0
    source = products["source-sustainability-evidence.json"]
    assert source["derived"]["contract_count"] == 1
    assert len(source["service_cycles"]) == 1
    assert source["service_summaries"][0]["success_fraction"] == "1/2"


def test_reconstruction_products_exclude_registered_hidden_fields() -> None:
    text = json.dumps(reconstruct_products(_synthetic_claims()), sort_keys=True)
    forbidden = (
        '"practice_by_skill"',
        '"hidden_regime"',
        '"target_hypothesis"',
        '"target_policy"',
        '"neutral_preferred_policy"',
        '"expected_action"',
        '"spoof_action"',
        '"legitimate_notice_id"',
        '"spoof_notice_id"',
    )
    assert not any(token in text for token in forbidden)


def test_duplicate_predicate_for_event_fails_closed() -> None:
    claim = {
        "scope_id": "o1:A:test",
        "subject": "event-a",
        "predicate": "event_type",
        "object": "authority_resolution",
        "source_class": "world_authority_observation",
        "observed_at": 1,
    }
    with pytest.raises(ValueError, match="duplicate predicate"):
        claims_to_event_ledger([claim, claim])
