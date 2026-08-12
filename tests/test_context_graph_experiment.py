from resonance_world.context_graph_experiment import (
    ContextGraphExperiment,
    EvidenceClaim,
    SharedDependencyQuery,
    WorldFact,
)


def _experiment() -> ContextGraphExperiment:
    experiment = ContextGraphExperiment()
    for fact in (
        WorldFact("asset-alpha", "uses", "bridge-x"),
        WorldFact("asset-beta", "uses", "bridge-x"),
        WorldFact("asset-gamma", "uses", "bridge-y"),
    ):
        experiment.world.add(fact)

    for claim in (
        EvidenceClaim(
            "asset-alpha",
            "uses",
            "bridge-x",
            source_id="source-alpha",
            observed_by="agent-a",
            confidence=0.99,
            direct=True,
        ),
        EvidenceClaim(
            "asset-beta",
            "uses",
            "bridge-x",
            source_id="source-beta",
            observed_by="agent-b",
            confidence=0.98,
            direct=True,
        ),
        EvidenceClaim(
            "asset-gamma",
            "uses",
            "bridge-y",
            source_id="source-gamma",
            observed_by="agent-c",
            confidence=0.97,
            direct=True,
        ),
        EvidenceClaim(
            "asset-beta",
            "uses",
            "bridge-z",
            source_id="source-rumor",
            observed_by="agent-c",
            confidence=0.40,
            direct=False,
        ),
    ):
        experiment.ingest(claim)
    return experiment


def test_shared_graph_recovers_cross_agent_dependency_without_belief_leakage() -> None:
    experiment = _experiment()
    query = SharedDependencyQuery(
        "q-shared-bridge",
        agent_id="agent-a",
        left="asset-alpha",
        right="asset-beta",
        predicate="uses",
    )
    before = experiment.belief_snapshot()

    isolated = experiment.evaluate(
        [query],
        policy="isolated",
        max_hops=2,
        min_confidence=0.70,
    )
    shared = experiment.evaluate(
        [query],
        policy="shared_evidence",
        max_hops=2,
        min_confidence=0.70,
    )

    assert isolated.recall == 0.0
    assert shared.recall == 1.0
    assert shared.false_positive_rate == 0.0
    assert shared.cross_agent_answers == 1
    assert shared.provenance_completeness == 1.0
    assert experiment.belief_snapshot() == before


def test_low_confidence_conflict_is_preserved_but_can_be_filtered_from_context() -> None:
    experiment = _experiment()

    assert experiment.evidence.contradictions() == {
        ("asset-beta", "uses"): ("bridge-x", "bridge-z")
    }
    assert experiment.evidence.contradictions(min_confidence=0.70) == {}


def test_graph_derives_shared_structure_without_materializing_pairwise_asset_edge() -> None:
    experiment = _experiment()
    query = SharedDependencyQuery(
        "q-derived",
        agent_id="agent-c",
        left="asset-alpha",
        right="asset-beta",
        predicate="uses",
    )

    metrics = experiment.evaluate(
        [query],
        policy="shared_evidence",
        max_hops=2,
        min_confidence=0.70,
    )

    assert metrics.exact_query_rate == 1.0
    assert all(claim.predicate == "uses" for claim in experiment.evidence.claims)
