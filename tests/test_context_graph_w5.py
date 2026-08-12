from resonance_world.context_graph_w5 import (
    CG2Query,
    FieldEvidence,
    TemporalClaim,
    contradiction_diagnostics,
    evaluate_fields,
)


def _field() -> FieldEvidence:
    organization = "org-1"
    context_node = "orgctx:org-1:north-grid"
    procedure = "procedure:org-1:north-grid:continuity"
    departed = "agent-old"
    current = "agent-new"
    claims = (
        TemporalClaim(
            "field-1",
            context_node,
            "current_strategy",
            procedure,
            "decision-1",
            "organization_decision",
            13,
            valid_from=12,
        ),
        TemporalClaim(
            "field-1",
            procedure,
            "successful_lead",
            departed,
            "episode-1",
            "organization_episode",
            11,
        ),
        TemporalClaim(
            "field-1",
            departed,
            "member_of",
            organization,
            "membership-old",
            "organization_membership",
            0,
            valid_from=0,
            valid_until=12,
        ),
        TemporalClaim(
            "field-1",
            current,
            "member_of",
            organization,
            "membership-new",
            "organization_membership",
            12,
            valid_from=12,
        ),
        TemporalClaim(
            "field-1",
            departed,
            "successful_skill",
            "energy_storage",
            "field-task-1",
            "field_outcome",
            -1,
        ),
        TemporalClaim(
            "field-1",
            departed,
            "successful_skill",
            "water_systems",
            "field-task-2",
            "field_outcome",
            -1,
        ),
        TemporalClaim(
            "field-1",
            departed,
            "member_of",
            organization,
            "rumor-current",
            "rumor",
            13,
            valid_from=12,
            confidence=0.35,
            direct=False,
        ),
    )
    query = CG2Query(
        query_id="q-1",
        field_id="field-1",
        organization_id=organization,
        organization_context_node=context_node,
        context="north-grid",
        as_of=13,
        expected_departed_lead=departed,
        expected_skills=frozenset({"energy_storage", "water_systems"}),
    )
    return FieldEvidence(
        field_id="field-1",
        claims=claims,
        queries=(query,),
        canonical_current_members=frozenset({current}),
    )


def test_temporal_graph_recovers_departed_lineage_but_stale_state_does_not() -> None:
    metrics = evaluate_fields([_field()], context_budget=7, min_confidence=0.70)

    shared = metrics["shared_temporal_graph"]
    stale = metrics["stale_graph"]
    unfiltered = metrics["unfiltered_conflict_graph"]

    assert shared.recall == 1.0
    assert shared.exact_query_rate == 1.0
    assert shared.lead_accuracy == 1.0
    assert shared.false_positive_rate == 0.0
    assert stale.recall == 0.0
    assert unfiltered.recall == 0.0


def test_provenance_ablation_preserves_answers_but_destroys_auditability() -> None:
    metrics = evaluate_fields([_field()], context_budget=7, min_confidence=0.70)

    shared = metrics["shared_temporal_graph"]
    no_provenance = metrics["graph_without_provenance"]

    assert no_provenance.recall == shared.recall
    assert no_provenance.exact_query_rate == shared.exact_query_rate
    assert shared.provenance_completeness == 1.0
    assert no_provenance.provenance_completeness == 0.0


def test_low_confidence_current_membership_conflict_is_visible_and_filterable() -> None:
    diagnostics = contradiction_diagnostics([_field()], as_of=13, min_confidence=0.70)

    assert diagnostics == {
        "raw_false_current_membership_claims": 1,
        "filtered_false_current_membership_claims": 0,
    }
