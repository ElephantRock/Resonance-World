"""CG-2 heterogeneous temporal context-graph experiment over W5 evidence.

This experiment projects two existing evidence layers into storage-neutral claims:

* raw Field task outcomes -> agent skill evidence;
* W5 organization formation episodes -> organization procedure lineage.

It then asks whether a current organization, after total roster turnover, can recover
the Field-evidenced skills of the departed lead that most recently succeeded under
the procedure the organization currently selects for a context.

The W5 outcome law is not changed. Organization memory remains a decision substrate,
and CG-2 evaluates retrieval/auditability only.
"""

from __future__ import annotations

import copy
import csv
import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from .w4a_joint_learning import IndividualState, JointAction, JointEnvironment, JointMission
from .w5a_organization import (
    STRATEGIES,
    OrganizationController,
    OrganizationEpisode,
    OrganizationState,
    Strategy,
)

Arm = Literal[
    "isolated_current",
    "pooled_flat",
    "shared_temporal_graph",
    "shuffled_graph",
    "stale_graph",
    "unfiltered_conflict_graph",
    "graph_without_provenance",
]


def _read_csv(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open(newline="", encoding="utf-8") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in Path(path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _as_bool(value: str) -> bool:
    return value.strip().lower() in {"t", "true", "1", "yes"}


def _seed(*parts: object) -> int:
    payload = "|".join(str(part) for part in parts).encode()
    return int.from_bytes(hashlib.sha256(payload).digest()[:4], "big")


def _uniform(*parts: object) -> float:
    payload = "|".join(str(part) for part in parts).encode()
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big") / 2**64


def _stable_key(field_id: str, agent_id: str) -> bytes:
    return hashlib.sha256(f"w5-roster|{field_id}|{agent_id}".encode()).digest()


@dataclass(frozen=True, slots=True)
class InstitutionMission:
    public: JointMission
    regime: Literal["specialist", "balanced"]


@dataclass(frozen=True, slots=True)
class TemporalClaim:
    field_id: str
    subject: str
    predicate: str
    object: str
    source_id: str
    source_class: str
    observed_at: int
    valid_from: int | None = None
    valid_until: int | None = None
    confidence: float = 1.0
    direct: bool = True

    def __post_init__(self) -> None:
        if not self.subject or not self.predicate or not self.object:
            raise ValueError("claim subject, predicate, and object must be non-empty")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("claim confidence must be between 0 and 1")
        if self.valid_from is not None and self.valid_until is not None:
            if self.valid_until <= self.valid_from:
                raise ValueError("valid_until must be greater than valid_from")

    def valid_at(self, instant: int) -> bool:
        if self.valid_from is not None and instant < self.valid_from:
            return False
        if self.valid_until is not None and instant >= self.valid_until:
            return False
        return True

    def without_provenance(self) -> TemporalClaim:
        return TemporalClaim(
            field_id=self.field_id,
            subject=self.subject,
            predicate=self.predicate,
            object=self.object,
            source_id="",
            source_class="",
            observed_at=self.observed_at,
            valid_from=self.valid_from,
            valid_until=self.valid_until,
            confidence=self.confidence,
            direct=self.direct,
        )


@dataclass(frozen=True, slots=True)
class CG2Query:
    query_id: str
    field_id: str
    organization_id: str
    organization_context_node: str
    context: str
    as_of: int
    expected_departed_lead: str
    expected_skills: frozenset[str]


@dataclass(frozen=True, slots=True)
class FieldEvidence:
    field_id: str
    claims: tuple[TemporalClaim, ...]
    queries: tuple[CG2Query, ...]
    canonical_current_members: frozenset[str]


@dataclass(frozen=True, slots=True)
class CG2Metrics:
    arm: Arm
    true_answers: int
    false_answers: int
    possible_answers: int
    exact_queries: int
    correct_leads: int
    query_count: int
    context_claims: int
    provenance_complete_claims: int
    source_class_total: int

    @property
    def recall(self) -> float:
        return self.true_answers / self.possible_answers if self.possible_answers else 1.0

    @property
    def false_positive_rate(self) -> float:
        predicted = self.true_answers + self.false_answers
        return self.false_answers / predicted if predicted else 0.0

    @property
    def exact_query_rate(self) -> float:
        return self.exact_queries / self.query_count if self.query_count else 1.0

    @property
    def lead_accuracy(self) -> float:
        return self.correct_leads / self.query_count if self.query_count else 1.0

    @property
    def mean_context_claims(self) -> float:
        return self.context_claims / self.query_count if self.query_count else 0.0

    @property
    def context_efficiency(self) -> float:
        return self.true_answers / self.context_claims if self.context_claims else 0.0

    @property
    def provenance_completeness(self) -> float:
        return (
            self.provenance_complete_claims / self.context_claims
            if self.context_claims
            else 1.0
        )

    @property
    def mean_source_classes(self) -> float:
        return self.source_class_total / self.query_count if self.query_count else 0.0


def _mission(row: dict[str, Any]) -> InstitutionMission:
    return InstitutionMission(
        public=JointMission(
            mission_id=str(row["mission_id"]),
            context=str(row["context"]),
            lead_skill=str(row["lead_skill"]),
            support_skill=str(row["support_skill"]),
        ),
        regime=str(row["regime"]),  # type: ignore[arg-type]
    )


def _field_agents(
    rows: list[dict[str, Any]],
    field_id: str,
) -> tuple[list[IndividualState], list[IndividualState]]:
    selected = [
        IndividualState(
            agent_id=str(row["agent_id"]),
            practice_by_skill={
                str(skill): int(value)
                for skill, value in dict(row["practice_by_skill"]).items()
            },
        )
        for row in rows
        if str(row["field_id"]) == field_id
    ]
    ordered = sorted(selected, key=lambda item: _stable_key(field_id, item.agent_id))
    if len(ordered) != 12:
        raise ValueError(f"{field_id} must contain exactly 12 source agents")
    return ordered[:4], ordered[4:8]


def _balanced_success(
    first: IndividualState,
    second: IndividualState,
    mission: InstitutionMission,
    *,
    seed: int,
) -> bool:
    environment = JointEnvironment()
    public = mission.public
    first_cross = (
        environment.role_probability(first, public.lead_skill)
        * environment.role_probability(first, public.support_skill)
    ) ** 0.5
    second_cross = (
        environment.role_probability(second, public.lead_skill)
        * environment.role_probability(second, public.support_skill)
    ) ** 0.5
    first_ok = _uniform("w5-balanced", public.mission_id, seed, "first") < first_cross
    second_ok = _uniform("w5-balanced", public.mission_id, seed, "second") < second_cross
    return first_ok and second_ok


def _evaluate_decision(
    first: IndividualState,
    second: IndividualState,
    mission: InstitutionMission,
    *,
    seed: int,
) -> bool:
    if mission.regime == "balanced":
        return _balanced_success(first, second, mission, seed=seed)
    return JointEnvironment().evaluate(
        first,
        second,
        mission.public,
        JointAction(first.agent_id, "lead"),
        JointAction(second.agent_id, "support"),
        seed=seed,
    )


def _forced_decision(
    organization: OrganizationState,
    mission: JointMission,
    strategy: Strategy,
):
    forced = copy.deepcopy(organization)
    forced.memory.strategy_attempts[mission.context] = {
        item: int(item == strategy) for item in STRATEGIES
    }
    forced.memory.strategy_successes[mission.context] = {
        item: int(item == strategy) for item in STRATEGIES
    }
    return OrganizationController().select(forced, mission)


def _train(
    organization: OrganizationState,
    missions: list[InstitutionMission],
    *,
    depth: int,
    strategy_order: list[Strategy],
    salt: str,
) -> list[tuple[int, OrganizationEpisode]]:
    episodes: list[tuple[int, OrganizationEpisode]] = []
    for round_index in range(depth):
        for mission_index, mission in enumerate(missions):
            for strategy_index, strategy in enumerate(strategy_order):
                decision = _forced_decision(organization, mission.public, strategy)
                success = _evaluate_decision(
                    decision.lead,
                    decision.support,
                    mission,
                    seed=_seed(
                        organization.organization_id,
                        salt,
                        round_index,
                        mission_index,
                        strategy_index,
                    ),
                )
                episode = OrganizationEpisode(
                    mission_id=mission.public.mission_id,
                    context=mission.public.context,
                    strategy=strategy,
                    lead_agent_id=decision.lead.agent_id,
                    support_agent_id=decision.support.agent_id,
                    success=success,
                )
                organization.memory.observe(episode)
                episodes.append((round_index, episode))
    return episodes


def _source_field_by_run(runs: list[dict[str, str]]) -> dict[str, str]:
    return {
        str(row["run_id"]): f"w4-source-seed-{int(row['seed'])}"
        for row in runs
    }


def build_field_evidence(
    *,
    source_dir: str | Path,
    missions: list[InstitutionMission],
    field_id: str,
    history_depth: int,
    strategy_order: list[Strategy],
    turnover_time: int,
    as_of: int,
    conflict_confidence: float,
) -> FieldEvidence:
    source = Path(source_dir)
    runs = _read_csv(source / "raw" / "runs.csv")
    outcomes = _read_csv(source / "raw" / "outcomes.csv")
    discovery_capsules = source / "output" / "discovery-source" / "capsules.private.jsonl"
    replication_capsules = source / "output" / "replication-source" / "capsules.private.jsonl"
    capsules_path = discovery_capsules if discovery_capsules.exists() else replication_capsules
    if not capsules_path.exists():
        raise FileNotFoundError("W5 source artifact does not contain capsules.private.jsonl")
    capsules = _read_jsonl(capsules_path)

    original, replacements = _field_agents(capsules, field_id)
    organization_id = f"w5-org-{field_id}"
    organization = OrganizationState(
        organization_id,
        {member.agent_id: member for member in original},
    )
    episodes = _train(
        organization,
        missions,
        depth=history_depth,
        strategy_order=strategy_order,
        salt="formation",
    )
    organization.replace_members(replacements)

    claims: list[TemporalClaim] = []
    for member in original:
        claims.append(
            TemporalClaim(
                field_id=field_id,
                subject=member.agent_id,
                predicate="member_of",
                object=organization_id,
                source_id=f"membership:original:{field_id}:{member.agent_id}",
                source_class="organization_membership",
                observed_at=0,
                valid_from=0,
                valid_until=turnover_time,
            )
        )
    for member in replacements:
        claims.append(
            TemporalClaim(
                field_id=field_id,
                subject=member.agent_id,
                predicate="member_of",
                object=organization_id,
                source_id=f"membership:replacement:{field_id}:{member.agent_id}",
                source_class="organization_membership",
                observed_at=turnover_time,
                valid_from=turnover_time,
            )
        )

    field_by_run = _source_field_by_run(runs)
    successful_skills_by_agent: dict[str, set[str]] = defaultdict(set)
    for row in outcomes:
        if field_by_run.get(str(row["run_id"])) != field_id:
            continue
        if not _as_bool(str(row["success"])) or not row.get("winner_agent_id"):
            continue
        agent_id = str(row["winner_agent_id"])
        skill = str(row["required_skill"])
        successful_skills_by_agent[agent_id].add(skill)
        claims.append(
            TemporalClaim(
                field_id=field_id,
                subject=agent_id,
                predicate="successful_skill",
                object=skill,
                source_id=f"field:{row['task_id']}:{row['cycle']}",
                source_class="field_outcome",
                observed_at=-1,
            )
        )

    queries: list[CG2Query] = []
    for mission in missions:
        current_decision = OrganizationController().select(organization, mission.public)
        context = mission.public.context
        strategy = current_decision.strategy
        organization_context = f"orgctx:{organization_id}:{context}"
        procedure = f"procedure:{organization_id}:{context}:{strategy}"
        claims.append(
            TemporalClaim(
                field_id=field_id,
                subject=organization_context,
                predicate="current_strategy",
                object=procedure,
                source_id=f"decision:{organization_id}:{context}",
                source_class="organization_decision",
                observed_at=as_of,
                valid_from=turnover_time,
            )
        )

        matching: list[tuple[int, OrganizationEpisode]] = []
        for round_index, episode in episodes:
            if (
                episode.context == context
                and episode.strategy == strategy
                and episode.success
            ):
                matching.append((round_index, episode))
                claims.append(
                    TemporalClaim(
                        field_id=field_id,
                        subject=procedure,
                        predicate="successful_lead",
                        object=episode.lead_agent_id,
                        source_id=(
                            f"organization-episode:{organization_id}:{context}:"
                            f"{strategy}:{round_index}"
                        ),
                        source_class="organization_episode",
                        observed_at=round_index,
                    )
                )

        if not matching:
            continue
        _, latest = max(matching, key=lambda item: item[0])
        expected_skills = frozenset(
            successful_skills_by_agent.get(latest.lead_agent_id, set())
        )
        if not expected_skills:
            continue
        queries.append(
            CG2Query(
                query_id=f"{field_id}:{context}",
                field_id=field_id,
                organization_id=organization_id,
                organization_context_node=organization_context,
                context=context,
                as_of=as_of,
                expected_departed_lead=latest.lead_agent_id,
                expected_skills=expected_skills,
            )
        )

    for departed_agent_id in sorted({query.expected_departed_lead for query in queries}):
        claims.append(
            TemporalClaim(
                field_id=field_id,
                subject=departed_agent_id,
                predicate="member_of",
                object=organization_id,
                source_id=f"rumor:current-membership:{organization_id}:{departed_agent_id}",
                source_class="rumor",
                observed_at=as_of,
                valid_from=turnover_time,
                confidence=conflict_confidence,
                direct=False,
            )
        )

    return FieldEvidence(
        field_id=field_id,
        claims=tuple(claims),
        queries=tuple(queries),
        canonical_current_members=frozenset(member.agent_id for member in replacements),
    )


def _hash_order(prefix: str, query_id: str, claim: TemporalClaim) -> bytes:
    payload = f"{prefix}|{query_id}|{claim.source_id}|{claim.subject}|{claim.object}".encode()
    return hashlib.sha256(payload).digest()


def _compile_graph(
    claims: tuple[TemporalClaim, ...],
    query: CG2Query,
    *,
    budget: int,
    min_confidence: float,
) -> tuple[TemporalClaim, ...]:
    eligible = [claim for claim in claims if claim.confidence >= min_confidence]
    frontier = {query.organization_context_node}
    visited = set(frontier)
    selected: list[TemporalClaim] = []
    selected_indexes: set[int] = set()

    for _hop in range(3):
        rows: list[tuple[int, str, int, TemporalClaim]] = []
        for index, claim in enumerate(eligible):
            if index in selected_indexes:
                continue
            if claim.subject not in frontier and claim.object not in frontier:
                continue
            rows.append((-claim.observed_at, claim.source_id, index, claim))
        rows.sort()
        next_frontier: set[str] = set()
        for _neg_time, _source, index, claim in rows:
            selected_indexes.add(index)
            selected.append(claim)
            if claim.subject not in visited:
                next_frontier.add(claim.subject)
            if claim.object not in visited:
                next_frontier.add(claim.object)
        if not next_frontier:
            break
        visited.update(next_frontier)
        frontier = next_frontier

    selected = selected[:budget]
    if len(selected) < budget:
        remaining = [
            claim
            for index, claim in enumerate(eligible)
            if index not in selected_indexes
        ]
        remaining.sort(key=lambda claim: _hash_order("fill", query.query_id, claim))
        selected.extend(remaining[: budget - len(selected)])
    return tuple(selected)


def _compile_flat(
    claims: tuple[TemporalClaim, ...],
    query: CG2Query,
    *,
    budget: int,
    min_confidence: float,
) -> tuple[TemporalClaim, ...]:
    rows = [claim for claim in claims if claim.confidence >= min_confidence]
    rows.sort(key=lambda claim: _hash_order("flat", query.query_id, claim))
    return tuple(rows[:budget])


def _shuffled_episode_graph(
    claims: tuple[TemporalClaim, ...],
) -> tuple[TemporalClaim, ...]:
    indexes = [
        index
        for index, claim in enumerate(claims)
        if claim.source_class == "organization_episode"
        and claim.predicate == "successful_lead"
    ]
    ordered = sorted(indexes, key=lambda index: claims[index].source_id)
    objects = [claims[index].object for index in ordered]
    if len(objects) < 2:
        return claims
    result = list(claims)
    for position, index in enumerate(ordered):
        claim = claims[index]
        result[index] = TemporalClaim(
            field_id=claim.field_id,
            subject=claim.subject,
            predicate=claim.predicate,
            object=objects[(position + 1) % len(objects)],
            source_id=claim.source_id,
            source_class=claim.source_class,
            observed_at=claim.observed_at,
            valid_from=claim.valid_from,
            valid_until=claim.valid_until,
            confidence=claim.confidence,
            direct=claim.direct,
        )
    return tuple(result)


def _isolated_current(
    claims: tuple[TemporalClaim, ...],
    query: CG2Query,
    *,
    min_confidence: float,
) -> tuple[TemporalClaim, ...]:
    return tuple(
        claim
        for claim in claims
        if claim.confidence >= min_confidence
        and (
            claim.source_class == "organization_decision"
            or (
                claim.source_class == "organization_membership"
                and claim.valid_at(query.as_of)
            )
        )
    )


def _infer(
    context: tuple[TemporalClaim, ...],
    query: CG2Query,
    *,
    min_confidence: float,
    respect_temporal_validity: bool,
) -> tuple[str | None, frozenset[str]]:
    rows = [claim for claim in context if claim.confidence >= min_confidence]
    procedures = [
        claim.object
        for claim in rows
        if claim.subject == query.organization_context_node
        and claim.predicate == "current_strategy"
    ]
    if not procedures:
        return None, frozenset()
    procedure = procedures[0]
    leads = [
        claim
        for claim in rows
        if claim.subject == procedure and claim.predicate == "successful_lead"
    ]
    if not leads:
        return None, frozenset()
    lead_claim = max(leads, key=lambda claim: (claim.observed_at, claim.source_id))
    lead = lead_claim.object

    memberships = [
        claim
        for claim in rows
        if claim.subject == lead
        and claim.predicate == "member_of"
        and claim.object == query.organization_id
    ]
    if not memberships:
        return None, frozenset()
    if respect_temporal_validity:
        currently_member = any(claim.valid_at(query.as_of) for claim in memberships)
    else:
        currently_member = bool(memberships)
    if currently_member:
        return None, frozenset()

    skills = frozenset(
        claim.object
        for claim in rows
        if claim.subject == lead and claim.predicate == "successful_skill"
    )
    return lead, skills


def evaluate_fields(
    fields: list[FieldEvidence],
    *,
    context_budget: int,
    min_confidence: float,
) -> dict[Arm, CG2Metrics]:
    accumulators: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "true_answers": 0,
            "false_answers": 0,
            "possible_answers": 0,
            "exact_queries": 0,
            "correct_leads": 0,
            "query_count": 0,
            "context_claims": 0,
            "provenance_complete_claims": 0,
            "source_class_total": 0,
        }
    )

    for field in fields:
        shuffled = _shuffled_episode_graph(field.claims)
        for query in field.queries:
            shared = _compile_graph(
                field.claims,
                query,
                budget=context_budget,
                min_confidence=min_confidence,
            )
            contexts: dict[Arm, tuple[TemporalClaim, ...]] = {
                "isolated_current": _isolated_current(
                    field.claims,
                    query,
                    min_confidence=min_confidence,
                ),
                "pooled_flat": _compile_flat(
                    field.claims,
                    query,
                    budget=context_budget,
                    min_confidence=min_confidence,
                ),
                "shared_temporal_graph": shared,
                "shuffled_graph": _compile_graph(
                    shuffled,
                    query,
                    budget=context_budget,
                    min_confidence=min_confidence,
                ),
                "stale_graph": shared,
                "unfiltered_conflict_graph": _compile_graph(
                    field.claims,
                    query,
                    budget=context_budget,
                    min_confidence=0.0,
                ),
                "graph_without_provenance": tuple(
                    claim.without_provenance() for claim in shared
                ),
            }
            inference: dict[Arm, tuple[float, bool]] = {
                "isolated_current": (min_confidence, True),
                "pooled_flat": (min_confidence, True),
                "shared_temporal_graph": (min_confidence, True),
                "shuffled_graph": (min_confidence, True),
                "stale_graph": (min_confidence, False),
                "unfiltered_conflict_graph": (0.0, True),
                "graph_without_provenance": (min_confidence, True),
            }

            for arm, context in contexts.items():
                threshold, temporal = inference[arm]
                lead, predicted = _infer(
                    context,
                    query,
                    min_confidence=threshold,
                    respect_temporal_validity=temporal,
                )
                expected = query.expected_skills
                row = accumulators[arm]
                row["true_answers"] += len(predicted & expected)
                row["false_answers"] += len(predicted - expected)
                row["possible_answers"] += len(expected)
                row["correct_leads"] += int(lead == query.expected_departed_lead)
                row["exact_queries"] += int(
                    lead == query.expected_departed_lead and predicted == expected
                )
                row["query_count"] += 1
                row["context_claims"] += len(context)
                row["provenance_complete_claims"] += sum(
                    bool(claim.source_id and claim.source_class) for claim in context
                )
                row["source_class_total"] += len(
                    {claim.source_class for claim in context if claim.source_class}
                )

    return {
        arm: CG2Metrics(arm=arm, **values)  # type: ignore[arg-type]
        for arm, values in accumulators.items()
    }


def contradiction_diagnostics(
    fields: list[FieldEvidence],
    *,
    as_of: int,
    min_confidence: float,
) -> dict[str, int]:
    raw = 0
    filtered = 0
    for field in fields:
        for claim in field.claims:
            if (
                claim.predicate == "member_of"
                and claim.valid_at(as_of)
                and claim.subject not in field.canonical_current_members
            ):
                raw += 1
                if claim.confidence >= min_confidence:
                    filtered += 1
    return {
        "raw_false_current_membership_claims": raw,
        "filtered_false_current_membership_claims": filtered,
    }


def metric_row(metrics: CG2Metrics) -> dict[str, object]:
    return {
        "arm": metrics.arm,
        "true_answers": metrics.true_answers,
        "false_answers": metrics.false_answers,
        "possible_answers": metrics.possible_answers,
        "exact_queries": metrics.exact_queries,
        "correct_leads": metrics.correct_leads,
        "query_count": metrics.query_count,
        "context_claims": metrics.context_claims,
        "recall": metrics.recall,
        "false_positive_rate": metrics.false_positive_rate,
        "exact_query_rate": metrics.exact_query_rate,
        "lead_accuracy": metrics.lead_accuracy,
        "mean_context_claims": metrics.mean_context_claims,
        "context_efficiency": metrics.context_efficiency,
        "provenance_completeness": metrics.provenance_completeness,
        "mean_source_classes": metrics.mean_source_classes,
    }
