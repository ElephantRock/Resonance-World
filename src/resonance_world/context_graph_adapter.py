"""Observer-only adapter from Resonance World evidence to ContextGraph.

This module is intentionally one-way: Resonance World may depend on the standalone
``resonance_contextgraph`` package, but ContextGraph must never import Resonance World.
Only observed evidence and public mission/query state cross the boundary. Hidden
capability, evaluator truth, oracle state, agent belief mutation, participant decision
state, and environment outcome laws do not.

The v0.1.0 production integration is an Observatory substrate only. No World actor or
organization consumes ContextGraph output through this module in the Observatory phase.
The adapter uses structural producer protocols rather than importing the historical
World ContextGraph implementation, keeping the graduated runtime independent from the
scientific compatibility fixtures retained on the research branch.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from typing import Protocol
from urllib.parse import quote

from resonance_contextgraph import (
    BalancedRoundRobin,
    CheckpointObservation,
    CompiledContext,
    ContextCompiler,
    ContextRequest,
    EventReconciler,
    EvidenceClaim,
    EvidenceStore,
    MeasurementCell,
    MissionSpec,
    PairStabilityStopper,
    StopDecision,
    checkpoint_observation,
    group_cell_evidence,
)
from resonance_contextgraph import EstimatorSpec as ContextEstimatorSpec

Cell = tuple[str, str]
Pair = tuple[str, str] | None
_TRANSPORT_NAMESPACE = "rw-contextgraph-delivery:v1"


class ObservedClaim(Protocol):
    """Minimum producer-side observation shape accepted by the adapter."""

    field_id: str
    subject: str
    predicate: str
    object: str
    observed_by: str
    source_id: str
    source_class: str
    observed_at: int
    confidence: float
    direct: bool


class PublicMission(Protocol):
    """Minimum public mission shape accepted by the adapter."""

    mission_id: str
    lead_skill: str
    support_skill: str


def _transport_claim_id(source_id: str, delivery: int) -> str:
    """Return an injective World transport identity for one source delivery.

    Producer ``source_id`` values remain opaque provenance. They never occupy the
    ``claim_id`` namespace: every delivery, including the first, receives a namespaced
    identity derived from an escaped source ID and its per-source delivery ordinal.
    URL quoting with no safe delimiter characters makes ``(source_id, delivery)`` pairs
    unambiguous even when producer IDs contain strings resembling transport suffixes.
    """
    if delivery < 0:
        raise ValueError("delivery must be non-negative")
    escaped_source = quote(source_id, safe="")
    return f"{_TRANSPORT_NAMESPACE}:{escaped_source}:{delivery}"


def to_evidence_claim(
    claim: ObservedClaim,
    *,
    delivery: int,
) -> EvidenceClaim:
    """Map one observed delivery to the standalone storage contract.

    ``delivery`` is intentionally mandatory. A raw producer ``source_id`` can legitimately
    recur, so a stateless mapper cannot infer a collision-free transport identity. Batch
    callers should prefer :func:`build_evidence_store`, which allocates per-source delivery
    ordinals deterministically; streaming callers must maintain the equivalent ordinal.
    """
    return EvidenceClaim(
        claim_id=_transport_claim_id(claim.source_id, delivery),
        scope_id=claim.field_id,
        subject=claim.subject,
        predicate=claim.predicate,
        object=claim.object,
        observed_by=claim.observed_by,
        source_id=claim.source_id,
        source_class=claim.source_class,
        observed_at=claim.observed_at,
        confidence=claim.confidence,
        direct=claim.direct,
    )


def build_evidence_store(claims: Iterable[ObservedClaim]) -> EvidenceStore:
    """Build an append-only store while preserving repeated-delivery order."""
    store = EvidenceStore()
    deliveries: dict[str, int] = defaultdict(int)
    for claim in claims:
        delivery = deliveries[claim.source_id]
        store.ingest(to_evidence_claim(claim, delivery=delivery))
        deliveries[claim.source_id] += 1
    return store


def to_mission_spec(mission: PublicMission) -> MissionSpec:
    return MissionSpec(
        mission_id=mission.mission_id,
        lead_skill=mission.lead_skill,
        support_skill=mission.support_skill,
    )


def validated_estimator() -> ContextEstimatorSpec:
    """Return the estimator validated by the frozen CG-5/CG-11 replay."""
    return ContextEstimatorSpec(
        kind="wilson_lower",
        min_support=3,
        fallback_score=0.35,
        z=1.2815515655446004,
    )


def _compiler_for_claims(
    claims: Iterable[ObservedClaim],
    *,
    estimator: ContextEstimatorSpec,
) -> tuple[EvidenceStore, ContextCompiler]:
    store = build_evidence_store(claims)
    return store, ContextCompiler(store, estimator=estimator)


def compile_live_context(
    *,
    claims: Iterable[ObservedClaim],
    field_id: str,
    as_of: int,
    mission: PublicMission,
    claim_budget: int = 48,
    min_confidence: float = 0.7,
    estimator: ContextEstimatorSpec | None = None,
) -> CompiledContext:
    """Compile an evaluator-side World context without exposing hidden state."""
    spec = estimator or validated_estimator()
    _store, compiler = _compiler_for_claims(claims, estimator=spec)
    return compiler.compile(
        ContextRequest(
            scope_id=field_id,
            mission=to_mission_spec(mission),
            as_of=as_of,
            claim_budget=claim_budget,
            min_confidence=min_confidence,
        )
    )


def pair_from_live_context(
    *,
    claims: Iterable[ObservedClaim],
    field_id: str,
    as_of: int,
    mission: PublicMission,
    claim_budget: int = 48,
    min_confidence: float = 0.7,
    estimator: ContextEstimatorSpec | None = None,
) -> tuple[Pair, CompiledContext]:
    spec = estimator or validated_estimator()
    context = compile_live_context(
        claims=claims,
        field_id=field_id,
        as_of=as_of,
        mission=mission,
        claim_budget=claim_budget,
        min_confidence=min_confidence,
        estimator=spec,
    )
    return context.best_pair(spec), context


def checkpoint_from_live_contexts(
    *,
    claims: Iterable[ObservedClaim],
    field_id: str,
    as_of: int,
    missions: Iterable[PublicMission],
    supplemental_budget: int,
    claim_budget: int = 48,
    min_confidence: float = 0.7,
    estimator: ContextEstimatorSpec | None = None,
) -> CheckpointObservation:
    """Build the complete executed CG-11 stopping observable."""
    spec = estimator or validated_estimator()
    store, compiler = _compiler_for_claims(claims, estimator=spec)
    latest_membership = store.latest_membership(
        scope_id=field_id,
        as_of=as_of,
        min_confidence=min_confidence,
    )
    candidates = {
        claim.subject
        for claim in latest_membership.values()
        if claim.object == "active"
    }
    admissible_claims = store.claims(
        scope_id=field_id,
        as_of=as_of,
        min_confidence=min_confidence,
    )
    events = EventReconciler().reconcile(
        admissible_claims,
        min_confidence=min_confidence,
    )
    full_evidence = group_cell_evidence(events, candidates=candidates)
    contexts = tuple(
        compiler.compile(
            ContextRequest(
                scope_id=field_id,
                mission=to_mission_spec(mission),
                as_of=as_of,
                claim_budget=claim_budget,
                min_confidence=min_confidence,
            )
        )
        for mission in missions
    )
    return checkpoint_observation(
        budget=supplemental_budget,
        contexts=contexts,
        full_evidence=full_evidence,
        estimator=spec,
    )


def next_balanced_cell(
    *,
    field_id: str,
    available: Iterable[Cell],
    reconciled_event_counts: Mapping[Cell, int],
) -> Cell:
    """Choose the next balanced measurement cell from observable counts only."""
    cells = tuple(
        MeasurementCell(
            agent_id=agent_id,
            skill=skill,
            reconciled_event_count=int(reconciled_event_counts.get((agent_id, skill), 0)),
        )
        for agent_id, skill in available
    )
    chosen = BalancedRoundRobin().choose(field_id, cells)
    return chosen.agent_id, chosen.skill


def choose_stopping_point(
    history: Iterable[CheckpointObservation],
    *,
    checkpoints: tuple[int, ...] = (48, 60, 72, 96, 120, 144, 168),
    minimum_budget: int = 60,
    hard_cap: int = 168,
) -> StopDecision:
    """Apply the executed CG-11 rule to complete checkpoint observations only.

    Production callers must provide the full ``CheckpointObservation`` generated from
    observable contexts/evidence. Legacy ``(budget, pair_vector)`` tuples are rejected so
    missing selected-role support or score-margin measurements cannot be synthesized as
    zero-valued observations that accidentally satisfy the executed stopping criterion.
    """
    observations = tuple(history)
    if not observations:
        raise ValueError("stopping history cannot be empty")
    if any(not isinstance(row, CheckpointObservation) for row in observations):
        raise TypeError("stopping history requires complete CheckpointObservation values")
    return PairStabilityStopper(
        checkpoints=checkpoints,
        minimum_budget=minimum_budget,
        hard_cap=hard_cap,
    ).choose(observations)
