"""Dependency-inverted adapter from Resonance World evidence to ContextGraph.

This module is intentionally one-way: Resonance World may depend on the standalone
``resonance_contextgraph`` package, but ContextGraph must never import Resonance World.
Only observed evidence and public mission/query state cross the boundary. Hidden
capability, evaluator truth, oracle state, and environment outcome laws do not.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping

from resonance_contextgraph import (
    BalancedRoundRobin,
    CheckpointObservation,
    CompiledContext,
    ContextCompiler,
    ContextRequest,
    EvidenceClaim,
    EvidenceStore,
    EventReconciler,
    MeasurementCell,
    MissionSpec,
    PairStabilityStopper,
    StopDecision,
    checkpoint_observation,
    group_cell_evidence,
)
from resonance_contextgraph import EstimatorSpec as ContextEstimatorSpec

from .context_graph_w3_endogenous import CG4Mission, LiveClaim

Cell = tuple[str, str]
Pair = tuple[str, str] | None


def to_evidence_claim(
    claim: LiveClaim,
    *,
    claim_id: str | None = None,
) -> EvidenceClaim:
    """Map one observed World claim to the standalone storage contract.

    ``source_id`` remains the original provenance identifier. ``claim_id`` is a
    transport/storage identity and may carry a deterministic delivery suffix when the
    frozen World stream repeats the same source identity in append order.
    """
    return EvidenceClaim(
        claim_id=claim_id or claim.source_id,
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


def build_evidence_store(claims: Iterable[LiveClaim]) -> EvidenceStore:
    """Build an append-only store while preserving repeated delivery order.

    The frozen W3 generator can emit the same ``source_id`` twice when a participant is
    also selected as the scout for one event. ContextGraph requires unique claim IDs,
    so repeated deliveries receive deterministic ``#delivery:N`` transport IDs while
    retaining the unchanged World ``source_id`` as provenance.
    """
    store = EvidenceStore()
    deliveries: dict[str, int] = defaultdict(int)
    for claim in claims:
        delivery = deliveries[claim.source_id]
        claim_id = (
            claim.source_id
            if delivery == 0
            else f"{claim.source_id}#delivery:{delivery}"
        )
        store.ingest(to_evidence_claim(claim, claim_id=claim_id))
        deliveries[claim.source_id] += 1
    return store


def to_mission_spec(mission: CG4Mission) -> MissionSpec:
    return MissionSpec(
        mission_id=mission.mission_id,
        lead_skill=mission.lead_skill,
        support_skill=mission.support_skill,
    )


def validated_estimator() -> ContextEstimatorSpec:
    """Return the estimator frozen for CG-5/CG-11 runtime semantics."""
    return ContextEstimatorSpec(
        kind="wilson_lower",
        min_support=3,
        fallback_score=0.35,
        z=1.2815515655446004,
    )


def _compiler_for_claims(
    claims: Iterable[LiveClaim],
    *,
    estimator: ContextEstimatorSpec,
) -> tuple[EvidenceStore, ContextCompiler]:
    store = build_evidence_store(claims)
    return store, ContextCompiler(store, estimator=estimator)


def compile_live_context(
    *,
    claims: Iterable[LiveClaim],
    field_id: str,
    as_of: int,
    mission: CG4Mission,
    claim_budget: int = 48,
    min_confidence: float = 0.7,
    estimator: ContextEstimatorSpec | None = None,
) -> CompiledContext:
    """Compile a World mission context without exposing evaluator state."""
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
    claims: Iterable[LiveClaim],
    field_id: str,
    as_of: int,
    mission: CG4Mission,
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
    claims: Iterable[LiveClaim],
    field_id: str,
    as_of: int,
    missions: Iterable[CG4Mission],
    supplemental_budget: int,
    claim_budget: int = 48,
    min_confidence: float = 0.7,
    estimator: ContextEstimatorSpec | None = None,
) -> CheckpointObservation:
    """Build the complete executed CG-11 stopping observable.

    The frozen evaluator computed pair stability, selected-role support, and selected
    score margin. The non-negative margin threshold can delay a stop even when the
    pair vector is stable, so all three observables are preserved here.
    """
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
    history: Iterable[CheckpointObservation | tuple[int, tuple[str, ...]]],
    *,
    checkpoints: tuple[int, ...] = (48, 60, 72, 96, 120, 144, 168),
    minimum_budget: int = 60,
    hard_cap: int = 168,
) -> StopDecision:
    """Apply the executed CG-11 observable stopping rule."""
    observations = tuple(
        row
        if isinstance(row, CheckpointObservation)
        else CheckpointObservation(budget=row[0], pair_vector=row[1])
        for row in history
    )
    if not observations:
        raise ValueError("stopping history cannot be empty")
    return PairStabilityStopper(
        checkpoints=checkpoints,
        minimum_budget=minimum_budget,
        hard_cap=hard_cap,
    ).choose(observations)
