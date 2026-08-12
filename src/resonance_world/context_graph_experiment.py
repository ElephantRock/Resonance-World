"""Experimental context-graph substrate for Resonance World.

This module is intentionally isolated from the production World control plane.
It models three distinct epistemic layers:

1. ``WorldGraph``: hidden canonical facts used only as experimental ground truth.
2. ``EvidenceGraph``: provenance-bearing claims collected across agents.
3. ``BeliefGraph``: agent-local beliefs populated only by explicit perception.

The context compiler may read the evidence graph to assemble decision context, but it
never writes into an agent belief graph. This preserves information asymmetry and
keeps graph access from silently becoming omniscience.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Literal

ContextPolicy = Literal["isolated", "shared_evidence"]


@dataclass(frozen=True, slots=True, order=True)
class WorldFact:
    subject: str
    predicate: str
    object: str


@dataclass(slots=True)
class WorldGraph:
    """Hidden canonical state used only for experiment scoring."""

    facts: set[WorldFact] = field(default_factory=set)

    def add(self, fact: WorldFact) -> None:
        self.facts.add(fact)

    def objects(self, subject: str, predicate: str) -> set[str]:
        return {
            fact.object
            for fact in self.facts
            if fact.subject == subject and fact.predicate == predicate
        }

    def shared_objects(self, left: str, right: str, predicate: str) -> set[str]:
        return self.objects(left, predicate) & self.objects(right, predicate)


@dataclass(frozen=True, slots=True)
class EvidenceClaim:
    """A claim plus the minimum provenance required for audit and reconciliation."""

    subject: str
    predicate: str
    object: str
    source_id: str
    observed_by: str
    confidence: float
    direct: bool
    observed_at: str | None = None
    valid_from: str | None = None
    valid_until: str | None = None

    def __post_init__(self) -> None:
        if not self.subject or not self.predicate or not self.object:
            raise ValueError("claim subject, predicate, and object must be non-empty")
        if not self.source_id or not self.observed_by:
            raise ValueError("claim provenance requires source_id and observed_by")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("claim confidence must be between 0 and 1")

    @property
    def fact(self) -> WorldFact:
        return WorldFact(self.subject, self.predicate, self.object)


@dataclass(slots=True)
class EvidenceGraph:
    """Append-only evidence graph; claims are not silently collapsed into truth."""

    claims: list[EvidenceClaim] = field(default_factory=list)

    def add(self, claim: EvidenceClaim) -> None:
        self.claims.append(claim)

    def _eligible(
        self,
        claim: EvidenceClaim,
        *,
        min_confidence: float,
        allowed_observers: set[str] | None,
    ) -> bool:
        if claim.confidence < min_confidence:
            return False
        if allowed_observers is not None and claim.observed_by not in allowed_observers:
            return False
        return True

    def subgraph(
        self,
        seeds: Iterable[str],
        *,
        max_hops: int,
        min_confidence: float = 0.0,
        allowed_observers: set[str] | None = None,
    ) -> tuple[EvidenceClaim, ...]:
        if max_hops < 0:
            raise ValueError("max_hops must be non-negative")
        frontier = set(seeds)
        visited = set(frontier)
        selected: list[EvidenceClaim] = []
        selected_ids: set[int] = set()

        for _ in range(max_hops):
            next_frontier: set[str] = set()
            for index, claim in enumerate(self.claims):
                if index in selected_ids:
                    continue
                if not self._eligible(
                    claim,
                    min_confidence=min_confidence,
                    allowed_observers=allowed_observers,
                ):
                    continue
                if claim.subject not in frontier and claim.object not in frontier:
                    continue
                selected.append(claim)
                selected_ids.add(index)
                if claim.subject not in visited:
                    next_frontier.add(claim.subject)
                if claim.object not in visited:
                    next_frontier.add(claim.object)
            if not next_frontier:
                break
            visited.update(next_frontier)
            frontier = next_frontier
        return tuple(selected)

    def contradictions(
        self,
        *,
        min_confidence: float = 0.0,
    ) -> dict[tuple[str, str], tuple[str, ...]]:
        values: dict[tuple[str, str], set[str]] = {}
        for claim in self.claims:
            if claim.confidence < min_confidence:
                continue
            values.setdefault((claim.subject, claim.predicate), set()).add(claim.object)
        return {
            key: tuple(sorted(objects))
            for key, objects in values.items()
            if len(objects) > 1
        }

    def provenance_completeness(
        self,
        claims: Iterable[EvidenceClaim] | None = None,
    ) -> float:
        rows = list(self.claims if claims is None else claims)
        if not rows:
            return 1.0
        complete = sum(bool(row.source_id and row.observed_by) for row in rows)
        return complete / len(rows)


@dataclass(frozen=True, slots=True)
class Belief:
    fact: WorldFact
    confidence: float
    source_id: str
    acquired_via: Literal["direct", "communication", "adopted"]


@dataclass(slots=True)
class BeliefGraph:
    """Agent-local epistemic state. Shared evidence access does not mutate it."""

    agent_id: str
    beliefs: dict[WorldFact, Belief] = field(default_factory=dict)

    def observe(self, claim: EvidenceClaim) -> None:
        if claim.observed_by != self.agent_id:
            raise ValueError("direct observation must match belief-graph owner")
        self.beliefs[claim.fact] = Belief(
            fact=claim.fact,
            confidence=claim.confidence,
            source_id=claim.source_id,
            acquired_via="direct",
        )

    def snapshot(self) -> tuple[Belief, ...]:
        return tuple(sorted(self.beliefs.values(), key=lambda item: item.fact))


@dataclass(frozen=True, slots=True)
class ContextCompiler:
    """Compile bounded evidence without rewriting agent-local belief state."""

    evidence: EvidenceGraph

    def compile(
        self,
        *,
        agent_id: str,
        seeds: Iterable[str],
        policy: ContextPolicy,
        max_hops: int = 2,
        min_confidence: float = 0.0,
    ) -> tuple[EvidenceClaim, ...]:
        observers = {agent_id} if policy == "isolated" else None
        return self.evidence.subgraph(
            seeds,
            max_hops=max_hops,
            min_confidence=min_confidence,
            allowed_observers=observers,
        )


@dataclass(frozen=True, slots=True)
class SharedDependencyQuery:
    query_id: str
    agent_id: str
    left: str
    right: str
    predicate: str


@dataclass(frozen=True, slots=True)
class ConditionMetrics:
    policy: ContextPolicy
    true_answers: int
    false_answers: int
    possible_answers: int
    exact_queries: int
    query_count: int
    cross_agent_answers: int
    provenance_completeness: float

    @property
    def recall(self) -> float:
        return self.true_answers / self.possible_answers if self.possible_answers else 1.0

    @property
    def false_positive_rate(self) -> float:
        total = self.true_answers + self.false_answers
        return self.false_answers / total if total else 0.0

    @property
    def exact_query_rate(self) -> float:
        return self.exact_queries / self.query_count if self.query_count else 1.0


@dataclass(slots=True)
class ContextGraphExperiment:
    """Small deterministic harness for comparing isolated vs graph-conditioned context."""

    world: WorldGraph = field(default_factory=WorldGraph)
    evidence: EvidenceGraph = field(default_factory=EvidenceGraph)
    beliefs: dict[str, BeliefGraph] = field(default_factory=dict)

    def ingest(self, claim: EvidenceClaim) -> None:
        self.evidence.add(claim)
        graph = self.beliefs.setdefault(claim.observed_by, BeliefGraph(claim.observed_by))
        graph.observe(claim)

    def belief_snapshot(self) -> dict[str, tuple[Belief, ...]]:
        return {
            agent_id: graph.snapshot()
            for agent_id, graph in sorted(self.beliefs.items())
        }

    def _infer_shared_objects(
        self,
        claims: Iterable[EvidenceClaim],
        query: SharedDependencyQuery,
    ) -> set[str]:
        left_objects = {
            claim.object
            for claim in claims
            if claim.subject == query.left and claim.predicate == query.predicate
        }
        right_objects = {
            claim.object
            for claim in claims
            if claim.subject == query.right and claim.predicate == query.predicate
        }
        return left_objects & right_objects

    def evaluate(
        self,
        queries: Iterable[SharedDependencyQuery],
        *,
        policy: ContextPolicy,
        max_hops: int = 2,
        min_confidence: float = 0.0,
    ) -> ConditionMetrics:
        compiler = ContextCompiler(self.evidence)
        query_rows = list(queries)
        true_answers = 0
        false_answers = 0
        possible_answers = 0
        exact_queries = 0
        cross_agent_answers = 0
        context_claims: list[EvidenceClaim] = []

        for query in query_rows:
            context = compiler.compile(
                agent_id=query.agent_id,
                seeds=(query.left, query.right),
                policy=policy,
                max_hops=max_hops,
                min_confidence=min_confidence,
            )
            context_claims.extend(context)
            predicted = self._infer_shared_objects(context, query)
            expected = self.world.shared_objects(
                query.left,
                query.right,
                query.predicate,
            )
            true_answers += len(predicted & expected)
            false_answers += len(predicted - expected)
            possible_answers += len(expected)
            exact_queries += int(predicted == expected)

            for answer in predicted & expected:
                observers = {
                    claim.observed_by
                    for claim in context
                    if claim.object == answer
                    and claim.predicate == query.predicate
                    and claim.subject in {query.left, query.right}
                }
                cross_agent_answers += int(len(observers) > 1)

        return ConditionMetrics(
            policy=policy,
            true_answers=true_answers,
            false_answers=false_answers,
            possible_answers=possible_answers,
            exact_queries=exact_queries,
            query_count=len(query_rows),
            cross_agent_answers=cross_agent_answers,
            provenance_completeness=self.evidence.provenance_completeness(context_claims),
        )
