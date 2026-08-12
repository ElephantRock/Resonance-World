"""CG-4 endogenous context-graph formation over live W3-derived societies.

Private W3 capsules define hidden individual skill state only. All evidence consumed by
CG-4 is emitted online from simulated membership changes and live role-probe outcomes.
No historical W3 tasks, outcomes, bids, pair edges, or relationship state are imported
as graph evidence.
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from .w4a_joint_learning import IndividualState, JointAction, JointEnvironment, JointMission

Arm = Literal[
    "local_only",
    "pooled_flat",
    "endogenous_graph",
    "shuffled_graph",
    "stale_graph",
    "conflicted_graph",
    "oracle",
]


@dataclass(frozen=True, slots=True)
class LiveClaim:
    field_id: str
    subject: str
    predicate: str
    object: str
    observed_by: str
    source_id: str
    source_class: str
    observed_at: int
    confidence: float = 1.0
    direct: bool = True

    def __post_init__(self) -> None:
        if not self.subject or not self.predicate or not self.object:
            raise ValueError("claim subject, predicate, and object must be non-empty")
        if not self.observed_by or not self.source_id or not self.source_class:
            raise ValueError("claim provenance must be non-empty")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("claim confidence must be between 0 and 1")


@dataclass(slots=True)
class OnlineEvidenceGraph:
    claims: list[LiveClaim] = field(default_factory=list)
    beliefs: dict[str, list[LiveClaim]] = field(default_factory=dict)
    ingest_count_history: list[int] = field(default_factory=list)

    def ingest(self, claim: LiveClaim) -> None:
        self.claims.append(claim)
        if claim.observed_by != "registry":
            self.beliefs.setdefault(claim.observed_by, []).append(claim)
        self.ingest_count_history.append(len(self.claims))

    def snapshot_beliefs(self) -> dict[str, tuple[str, ...]]:
        return {
            owner: tuple(item.source_id for item in rows)
            for owner, rows in sorted(self.beliefs.items())
        }


@dataclass(frozen=True, slots=True)
class CG4Mission:
    mission_id: str
    lead_skill: str
    support_skill: str

    def public(self, field_id: str) -> JointMission:
        return JointMission(
            mission_id=f"{field_id}:{self.mission_id}",
            context=self.mission_id,
            lead_skill=self.lead_skill,
            support_skill=self.support_skill,
        )

    @property
    def required_skills(self) -> tuple[str, str]:
        return self.lead_skill, self.support_skill


@dataclass(frozen=True, slots=True)
class EndogenousField:
    field_id: str
    states: dict[str, IndividualState]
    claims: tuple[LiveClaim, ...]
    belief_snapshot: dict[str, tuple[str, ...]]
    current_members: frozenset[str]
    departed_members: frozenset[str]
    coordinator_id: str
    as_of: int
    emitted_claims: int
    duplicate_observation_groups: int
    conflicting_observation_groups: int
    low_confidence_claims: int


@dataclass(frozen=True, slots=True)
class CG4Metrics:
    arm: Arm
    decisions: int
    successes: int
    trials: int
    expected_success_total: float
    oracle_expected_total: float
    regret_total: float
    oracle_pair_matches: int
    invalid_selections: int
    context_claims: int
    provenance_complete_claims: int

    @property
    def mission_success_rate(self) -> float:
        return self.successes / self.trials if self.trials else 0.0

    @property
    def mean_expected_success(self) -> float:
        return self.expected_success_total / self.decisions if self.decisions else 0.0

    @property
    def mean_oracle_expected_success(self) -> float:
        return self.oracle_expected_total / self.decisions if self.decisions else 0.0

    @property
    def mean_regret(self) -> float:
        return self.regret_total / self.decisions if self.decisions else 0.0

    @property
    def oracle_pair_rate(self) -> float:
        return self.oracle_pair_matches / self.decisions if self.decisions else 0.0

    @property
    def invalid_selection_rate(self) -> float:
        return self.invalid_selections / self.decisions if self.decisions else 0.0

    @property
    def mean_context_claims(self) -> float:
        return self.context_claims / self.decisions if self.decisions else 0.0

    @property
    def provenance_completeness(self) -> float:
        if not self.context_claims:
            return 1.0
        return self.provenance_complete_claims / self.context_claims


def _uniform(*parts: object) -> float:
    payload = "|".join(str(part) for part in parts).encode()
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big") / 2**64


def _read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in Path(path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _stable_roster(field_id: str, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        rows,
        key=lambda row: hashlib.sha256(
            f"cg4-roster|{field_id}|{row['agent_id']}".encode()
        ).digest(),
    )


def _probe_skills(
    field_id: str,
    agent_id: str,
    phase: str,
    skills: list[str],
    count: int,
) -> list[str]:
    return sorted(
        skills,
        key=lambda skill: hashlib.sha256(
            f"cg4-probe-skill|{phase}|{field_id}|{agent_id}|{skill}".encode()
        ).digest(),
    )[:count]


def _emit_membership(
    graph: OnlineEvidenceGraph,
    *,
    field_id: str,
    agent_id: str,
    state: Literal["active", "departed"],
    observed_at: int,
    source: str,
    confidence: float,
    direct: bool,
) -> None:
    graph.ingest(
        LiveClaim(
            field_id=field_id,
            subject=agent_id,
            predicate="membership_state",
            object=state,
            observed_by=source,
            source_id=f"membership:{field_id}:{observed_at}:{agent_id}:{source}",
            source_class="membership" if direct else "rumor",
            observed_at=observed_at,
            confidence=confidence,
            direct=direct,
        )
    )


def _emit_probe_observation(
    graph: OnlineEvidenceGraph,
    *,
    field_id: str,
    event_id: str,
    agent_id: str,
    skill: str,
    success: bool,
    observer: str,
    observed_at: int,
    confidence: float,
) -> None:
    outcome = "success" if success else "failure"
    for predicate, value in (
        ("participant", agent_id),
        ("skill", skill),
        ("outcome", outcome),
    ):
        graph.ingest(
            LiveClaim(
                field_id=field_id,
                subject=event_id,
                predicate=predicate,
                object=value,
                observed_by=observer,
                source_id=f"{event_id}:{observer}:{predicate}",
                source_class="live_probe",
                observed_at=observed_at,
                confidence=confidence,
                direct=True,
            )
        )


def _run_probe_phase(
    graph: OnlineEvidenceGraph,
    *,
    field_id: str,
    roster: list[IndividualState],
    phase: str,
    start_time: int,
    probes_per_skill: int,
    skills_per_agent: int,
    noise_rate: float,
    success_counts: dict[str, int],
) -> int:
    skills = sorted(roster[0].practice_by_skill)
    event_index = 0
    environment = JointEnvironment()
    for agent_index, state in enumerate(roster):
        selected_skills = _probe_skills(
            field_id,
            state.agent_id,
            phase,
            skills,
            skills_per_agent,
        )
        for skill in selected_skills:
            for repeat_index in range(probes_per_skill):
                event_id = f"probe:{field_id}:{phase}:{state.agent_id}:{skill}:{repeat_index}"
                observed_at = start_time + event_index
                probability = environment.role_probability(state, skill)
                success = _uniform("cg4-live-probe", event_id) < probability
                success_counts[state.agent_id] += int(success)
                scout = roster[(agent_index + event_index + 3) % len(roster)].agent_id
                _emit_probe_observation(
                    graph,
                    field_id=field_id,
                    event_id=event_id,
                    agent_id=state.agent_id,
                    skill=skill,
                    success=success,
                    observer=state.agent_id,
                    observed_at=observed_at,
                    confidence=0.95,
                )
                noisy = _uniform("cg4-observation-noise", event_id, scout) < noise_rate
                _emit_probe_observation(
                    graph,
                    field_id=field_id,
                    event_id=event_id,
                    agent_id=state.agent_id,
                    skill=skill,
                    success=not success if noisy else success,
                    observer=scout,
                    observed_at=observed_at,
                    confidence=0.45 if noisy else 0.85,
                )
                event_index += 1
    return start_time + event_index


def build_endogenous_field(
    *,
    capsules_path: str | Path,
    field_id: str,
    initial_roster_size: int,
    turnover_count: int,
    probes_per_skill: int,
    skills_per_agent: int,
    noise_rate: float,
    rumor_count: int,
) -> EndogenousField:
    rows = [
        row
        for row in _read_jsonl(capsules_path)
        if str(row["field_id"]) == field_id
    ]
    if len(rows) != 12:
        raise ValueError(f"{field_id} must contain exactly 12 capsule states")
    ordered = _stable_roster(field_id, rows)
    if initial_roster_size + turnover_count > len(ordered):
        raise ValueError("roster/turnover configuration exceeds available agents")
    initial_rows = ordered[:initial_roster_size]
    reserve_rows = ordered[initial_roster_size : initial_roster_size + turnover_count]
    states = {
        str(row["agent_id"]): IndividualState(
            agent_id=str(row["agent_id"]),
            practice_by_skill={
                str(skill): int(value)
                for skill, value in dict(row["practice_by_skill"]).items()
            },
        )
        for row in ordered
    }
    initial = [states[str(row["agent_id"])] for row in initial_rows]
    reserves = [states[str(row["agent_id"])] for row in reserve_rows]
    graph = OnlineEvidenceGraph()
    for state in initial:
        _emit_membership(
            graph,
            field_id=field_id,
            agent_id=state.agent_id,
            state="active",
            observed_at=0,
            source="registry",
            confidence=0.99,
            direct=True,
        )

    success_counts: dict[str, int] = defaultdict(int)
    next_time = _run_probe_phase(
        graph,
        field_id=field_id,
        roster=initial,
        phase="pre",
        start_time=1,
        probes_per_skill=probes_per_skill,
        skills_per_agent=skills_per_agent,
        noise_rate=noise_rate,
        success_counts=success_counts,
    )
    departure_order = sorted(
        initial,
        key=lambda state: (-success_counts[state.agent_id], state.agent_id),
    )
    departed = departure_order[:turnover_count]
    departed_ids = {state.agent_id for state in departed}
    retained = [state for state in initial if state.agent_id not in departed_ids]
    turnover_time = next_time + 1
    for state in departed:
        _emit_membership(
            graph,
            field_id=field_id,
            agent_id=state.agent_id,
            state="departed",
            observed_at=turnover_time,
            source="registry",
            confidence=0.99,
            direct=True,
        )
    for state in reserves:
        _emit_membership(
            graph,
            field_id=field_id,
            agent_id=state.agent_id,
            state="active",
            observed_at=turnover_time,
            source="registry",
            confidence=0.99,
            direct=True,
        )
    current = retained + reserves
    next_time = _run_probe_phase(
        graph,
        field_id=field_id,
        roster=current,
        phase="post",
        start_time=turnover_time + 1,
        probes_per_skill=probes_per_skill,
        skills_per_agent=skills_per_agent,
        noise_rate=noise_rate,
        success_counts=success_counts,
    )
    for state in departed[:rumor_count]:
        _emit_membership(
            graph,
            field_id=field_id,
            agent_id=state.agent_id,
            state="active",
            observed_at=next_time + 1,
            source="rumor",
            confidence=0.35,
            direct=False,
        )

    claims = tuple(graph.claims)
    observations: dict[tuple[str, str], dict[str, str]] = defaultdict(dict)
    for claim in claims:
        if claim.source_class == "live_probe":
            observations[(claim.subject, claim.observed_by)][claim.predicate] = claim.object
    event_observers: dict[str, set[str]] = defaultdict(set)
    event_outcomes: dict[str, set[str]] = defaultdict(set)
    for (event_id, observer), values in observations.items():
        event_observers[event_id].add(observer)
        if "outcome" in values:
            event_outcomes[event_id].add(values["outcome"])
    duplicate_groups = sum(len(values) > 1 for values in event_observers.values())
    conflict_groups = sum(len(values) > 1 for values in event_outcomes.values())
    low_confidence = sum(claim.confidence < 0.7 for claim in claims)
    if graph.ingest_count_history != list(range(1, len(claims) + 1)):
        raise AssertionError("online evidence store was not append-only")
    return EndogenousField(
        field_id=field_id,
        states=states,
        claims=claims,
        belief_snapshot=graph.snapshot_beliefs(),
        current_members=frozenset(state.agent_id for state in current),
        departed_members=frozenset(departed_ids),
        coordinator_id=sorted(state.agent_id for state in current)[0],
        as_of=next_time + 2,
        emitted_claims=len(claims),
        duplicate_observation_groups=duplicate_groups,
        conflicting_observation_groups=conflict_groups,
        low_confidence_claims=low_confidence,
    )


def _eligible(claims: tuple[LiveClaim, ...], min_confidence: float) -> list[LiveClaim]:
    return [claim for claim in claims if claim.confidence >= min_confidence]


def _membership_candidates(
    claims: list[LiveClaim] | tuple[LiveClaim, ...],
    *,
    min_confidence: float,
    respect_temporal_order: bool,
) -> set[str]:
    rows = [
        claim
        for claim in claims
        if claim.predicate == "membership_state" and claim.confidence >= min_confidence
    ]
    if not respect_temporal_order:
        return {claim.subject for claim in rows if claim.object == "active"}
    latest: dict[str, LiveClaim] = {}
    for claim in rows:
        prior = latest.get(claim.subject)
        if prior is None or (claim.observed_at, claim.source_id) > (
            prior.observed_at,
            prior.source_id,
        ):
            latest[claim.subject] = claim
    return {subject for subject, claim in latest.items() if claim.object == "active"}


def _observation_bundles(
    claims: list[LiveClaim] | tuple[LiveClaim, ...],
    *,
    min_confidence: float,
) -> list[tuple[str, str, str, str, float, int, tuple[LiveClaim, ...]]]:
    groups: dict[tuple[str, str], dict[str, LiveClaim]] = defaultdict(dict)
    for claim in claims:
        if claim.source_class == "live_probe" and claim.confidence >= min_confidence:
            groups[(claim.subject, claim.observed_by)][claim.predicate] = claim
    output = []
    for (event_id, observer), values in groups.items():
        if not {"participant", "skill", "outcome"}.issubset(values):
            continue
        bundle = tuple(values[key] for key in ("participant", "skill", "outcome"))
        output.append(
            (
                event_id,
                observer,
                values["participant"].object,
                values["skill"].object,
                min(item.confidence for item in bundle),
                max(item.observed_at for item in bundle),
                bundle,
            )
        )
    return output


def _compile_graph(
    field: EndogenousField,
    mission: CG4Mission,
    *,
    budget: int,
    min_confidence: float,
    respect_temporal_order: bool,
) -> tuple[LiveClaim, ...]:
    eligible = _eligible(field.claims, min_confidence)
    membership = [claim for claim in eligible if claim.predicate == "membership_state"]
    membership.sort(key=lambda claim: (claim.observed_at, claim.source_id))
    output = list(membership[-min(len(membership), budget) :])
    if len(output) >= budget:
        return tuple(output)
    candidates = _membership_candidates(
        membership,
        min_confidence=min_confidence,
        respect_temporal_order=respect_temporal_order,
    )
    bundles = _observation_bundles(eligible, min_confidence=min_confidence)
    best: dict[tuple[str, str], tuple[Any, ...]] = {}
    for bundle in sorted(bundles, key=lambda item: (-item[4], -item[5], item[0], item[1])):
        _event, _observer, agent_id, skill, *_rest = bundle
        if agent_id in candidates and skill in mission.required_skills:
            best.setdefault((agent_id, skill), bundle)
    priorities = [
        (agent_id, skill)
        for skill in mission.required_skills
        for agent_id in sorted(candidates)
        if (agent_id, skill) in best
    ]
    used_sources = {claim.source_id for claim in output}
    for key in priorities:
        bundle_claims = best[key][-1]
        if len(output) + len(bundle_claims) > budget:
            break
        for claim in bundle_claims:
            if claim.source_id not in used_sources:
                output.append(claim)
                used_sources.add(claim.source_id)
    if len(output) < budget:
        remaining = [claim for claim in eligible if claim.source_id not in used_sources]
        remaining.sort(
            key=lambda claim: hashlib.sha256(
                f"cg4-fill|{mission.mission_id}|{claim.source_id}".encode()
            ).digest()
        )
        output.extend(remaining[: budget - len(output)])
    return tuple(output[:budget])


def _compile_flat(
    field: EndogenousField,
    mission: CG4Mission,
    *,
    budget: int,
    min_confidence: float,
) -> tuple[LiveClaim, ...]:
    eligible = _eligible(field.claims, min_confidence)
    membership = [claim for claim in eligible if claim.predicate == "membership_state"]
    membership.sort(key=lambda claim: (claim.observed_at, claim.source_id))
    output = membership[-min(len(membership), budget) :]
    used = {claim.source_id for claim in output}
    remaining = [claim for claim in eligible if claim.source_id not in used]
    remaining.sort(
        key=lambda claim: hashlib.sha256(
            f"cg4-flat|{mission.mission_id}|{claim.source_id}".encode()
        ).digest()
    )
    output.extend(remaining[: budget - len(output)])
    return tuple(output[:budget])


def _compile_local(
    field: EndogenousField,
    *,
    budget: int,
    min_confidence: float,
) -> tuple[LiveClaim, ...]:
    eligible = _eligible(field.claims, min_confidence)
    membership = [claim for claim in eligible if claim.predicate == "membership_state"]
    local = [
        claim
        for claim in eligible
        if claim.source_class == "live_probe" and claim.observed_by == field.coordinator_id
    ]
    rows = membership + sorted(local, key=lambda claim: (-claim.observed_at, claim.source_id))
    return tuple(rows[:budget])


def _shuffle_identity(field: EndogenousField) -> EndogenousField:
    agent_ids = sorted(field.states)
    shift = max(1, len(agent_ids) // 3)
    mapping = {
        agent_id: agent_ids[(index + shift) % len(agent_ids)]
        for index, agent_id in enumerate(agent_ids)
    }
    claims = tuple(
        LiveClaim(
            field_id=claim.field_id,
            subject=mapping.get(claim.subject, claim.subject),
            predicate=claim.predicate,
            object=mapping.get(claim.object, claim.object),
            observed_by=claim.observed_by,
            source_id=claim.source_id,
            source_class=claim.source_class,
            observed_at=claim.observed_at,
            confidence=claim.confidence,
            direct=claim.direct,
        )
        for claim in field.claims
    )
    return EndogenousField(
        field_id=field.field_id,
        states=field.states,
        claims=claims,
        belief_snapshot=field.belief_snapshot,
        current_members=field.current_members,
        departed_members=field.departed_members,
        coordinator_id=field.coordinator_id,
        as_of=field.as_of,
        emitted_claims=field.emitted_claims,
        duplicate_observation_groups=field.duplicate_observation_groups,
        conflicting_observation_groups=field.conflicting_observation_groups,
        low_confidence_claims=field.low_confidence_claims,
    )


def _estimate_pair(
    context: tuple[LiveClaim, ...],
    mission: CG4Mission,
    *,
    min_confidence: float,
    respect_temporal_order: bool,
) -> tuple[str, str] | None:
    candidates = _membership_candidates(
        context,
        min_confidence=min_confidence,
        respect_temporal_order=respect_temporal_order,
    )
    if len(candidates) < 2:
        return None
    stats: dict[tuple[str, str], list[float]] = defaultdict(lambda: [0.0, 0.0])
    for _event, _observer, agent_id, skill, confidence, _time, bundle in _observation_bundles(
        context,
        min_confidence=min_confidence,
    ):
        if agent_id not in candidates:
            continue
        outcome = next(item.object for item in bundle if item.predicate == "outcome")
        stats[(agent_id, skill)][1] += confidence
        if outcome == "success":
            stats[(agent_id, skill)][0] += confidence

    def estimate(agent_id: str, skill: str) -> float:
        successes, total = stats.get((agent_id, skill), (0.0, 0.0))
        return (1.0 + successes) / (2.0 + total) if total else 0.5

    best: tuple[float, str, str, str] | None = None
    for lead_id in sorted(candidates):
        for support_id in sorted(candidates):
            if lead_id == support_id:
                continue
            score = estimate(lead_id, mission.lead_skill) * estimate(
                support_id,
                mission.support_skill,
            )
            candidate = (score, f"{lead_id}::{support_id}", lead_id, support_id)
            if best is None or candidate[:2] > best[:2]:
                best = candidate
    return None if best is None else (best[2], best[3])


def _expected_success(
    field: EndogenousField,
    mission: CG4Mission,
    pair: tuple[str, str],
) -> float:
    environment = JointEnvironment()
    public = mission.public(field.field_id)
    return environment.role_probability(
        field.states[pair[0]], public.lead_skill
    ) * environment.role_probability(field.states[pair[1]], public.support_skill)


def _oracle_pair(field: EndogenousField, mission: CG4Mission) -> tuple[str, str]:
    best: tuple[float, str, str, str] | None = None
    for lead_id in sorted(field.current_members):
        for support_id in sorted(field.current_members):
            if lead_id == support_id:
                continue
            score = _expected_success(field, mission, (lead_id, support_id))
            candidate = (score, f"{lead_id}::{support_id}", lead_id, support_id)
            if best is None or candidate[:2] > best[:2]:
                best = candidate
    if best is None:
        raise ValueError("field does not contain an oracle pair")
    return best[2], best[3]


def _evaluate_pair_trials(
    field: EndogenousField,
    mission: CG4Mission,
    pair: tuple[str, str] | None,
    *,
    trials: int,
) -> int:
    if pair is None or not set(pair).issubset(field.current_members):
        return 0
    environment = JointEnvironment()
    public = mission.public(field.field_id)
    first = field.states[pair[0]]
    second = field.states[pair[1]]
    return sum(
        environment.evaluate(
            first,
            second,
            public,
            JointAction(first.agent_id, "lead"),
            JointAction(second.agent_id, "support"),
            seed=trial,
        )
        for trial in range(trials)
    )


def evaluate_fields(
    fields: list[EndogenousField],
    missions: list[CG4Mission],
    *,
    context_budget: int,
    min_confidence: float,
    evaluation_trials: int,
) -> dict[Arm, CG4Metrics]:
    accumulators: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "decisions": 0,
            "successes": 0,
            "trials": 0,
            "expected_success_total": 0.0,
            "oracle_expected_total": 0.0,
            "regret_total": 0.0,
            "oracle_pair_matches": 0,
            "invalid_selections": 0,
            "context_claims": 0,
            "provenance_complete_claims": 0,
        }
    )
    for field in fields:
        shuffled = _shuffle_identity(field)
        beliefs_before = field.belief_snapshot
        for mission in missions:
            contexts: dict[Arm, tuple[LiveClaim, ...]] = {
                "local_only": _compile_local(
                    field,
                    budget=context_budget,
                    min_confidence=min_confidence,
                ),
                "pooled_flat": _compile_flat(
                    field,
                    mission,
                    budget=context_budget,
                    min_confidence=min_confidence,
                ),
                "endogenous_graph": _compile_graph(
                    field,
                    mission,
                    budget=context_budget,
                    min_confidence=min_confidence,
                    respect_temporal_order=True,
                ),
                "shuffled_graph": _compile_graph(
                    shuffled,
                    mission,
                    budget=context_budget,
                    min_confidence=min_confidence,
                    respect_temporal_order=True,
                ),
                "stale_graph": _compile_graph(
                    field,
                    mission,
                    budget=context_budget,
                    min_confidence=min_confidence,
                    respect_temporal_order=False,
                ),
                "conflicted_graph": _compile_graph(
                    field,
                    mission,
                    budget=context_budget,
                    min_confidence=0.0,
                    respect_temporal_order=True,
                ),
                "oracle": (),
            }
            oracle_pair = _oracle_pair(field, mission)
            oracle_expected = _expected_success(field, mission, oracle_pair)
            for arm, context in contexts.items():
                pair = (
                    oracle_pair
                    if arm == "oracle"
                    else _estimate_pair(
                        context,
                        mission,
                        min_confidence=(
                            0.0 if arm == "conflicted_graph" else min_confidence
                        ),
                        respect_temporal_order=arm != "stale_graph",
                    )
                )
                invalid = pair is None or not set(pair).issubset(field.current_members)
                expected = (
                    0.0
                    if invalid or pair is None
                    else _expected_success(field, mission, pair)
                )
                successes = _evaluate_pair_trials(
                    field,
                    mission,
                    pair,
                    trials=evaluation_trials,
                )
                row = accumulators[arm]
                row["decisions"] += 1
                row["successes"] += successes
                row["trials"] += evaluation_trials
                row["expected_success_total"] += expected
                row["oracle_expected_total"] += oracle_expected
                row["regret_total"] += oracle_expected - expected
                row["oracle_pair_matches"] += int(pair == oracle_pair)
                row["invalid_selections"] += int(invalid)
                row["context_claims"] += len(context)
                row["provenance_complete_claims"] += sum(
                    bool(claim.source_id and claim.source_class and claim.observed_by)
                    for claim in context
                )
        if field.belief_snapshot != beliefs_before:
            raise AssertionError("retrieval mutated agent-local belief state")
    return {
        arm: CG4Metrics(arm=arm, **values)  # type: ignore[arg-type]
        for arm, values in accumulators.items()
    }


def diagnostics(fields: list[EndogenousField]) -> dict[str, int]:
    return {
        "emitted_claims": sum(field.emitted_claims for field in fields),
        "duplicate_observation_groups": sum(
            field.duplicate_observation_groups for field in fields
        ),
        "conflicting_observation_groups": sum(
            field.conflicting_observation_groups for field in fields
        ),
        "low_confidence_claims": sum(field.low_confidence_claims for field in fields),
        "departed_members": sum(len(field.departed_members) for field in fields),
        "posthoc_imported_claims": 0,
        "historical_outcome_rows_consumed": 0,
    }


def metric_row(metrics: CG4Metrics) -> dict[str, object]:
    return {
        "arm": metrics.arm,
        "decisions": metrics.decisions,
        "successes": metrics.successes,
        "trials": metrics.trials,
        "mission_success_rate": metrics.mission_success_rate,
        "mean_expected_success": metrics.mean_expected_success,
        "mean_oracle_expected_success": metrics.mean_oracle_expected_success,
        "mean_regret": metrics.mean_regret,
        "oracle_pair_matches": metrics.oracle_pair_matches,
        "oracle_pair_rate": metrics.oracle_pair_rate,
        "invalid_selections": metrics.invalid_selections,
        "invalid_selection_rate": metrics.invalid_selection_rate,
        "context_claims": metrics.context_claims,
        "mean_context_claims": metrics.mean_context_claims,
        "provenance_completeness": metrics.provenance_completeness,
    }
