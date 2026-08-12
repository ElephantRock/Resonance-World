"""CG-3 decision-causality experiment over W5 source evidence.

CG-3 asks whether graph-conditioned evidence improves an actual downstream
partner-selection decision. The context policy may change which lead/support
pair is chosen; the W4 JointEnvironment outcome law is unchanged and receives
no graph, provenance, confidence, or temporal state.

Evidence is built from W5 source artifacts:
* raw successful Field outcomes -> aggregated agent/skill evidence;
* W5 turnover roster construction -> time-bounded availability evidence;
* registered mission specs -> decision/skill anchors.

Canonical current availability and individual practice remain evaluator-owned.
Decision policies receive only compiled evidence.
"""

from __future__ import annotations

import csv
import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from .w4a_joint_learning import IndividualState, JointAction, JointEnvironment, JointMission

Arm = Literal[
    "local_only",
    "pooled_flat",
    "temporal_graph",
    "shuffled_graph",
    "stale_graph",
    "conflicted_graph",
    "oracle",
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


def _stable_key(field_id: str, agent_id: str) -> bytes:
    return hashlib.sha256(f"w5-roster|{field_id}|{agent_id}".encode()).digest()


@dataclass(frozen=True, slots=True)
class DecisionClaim:
    field_id: str
    subject: str
    predicate: str
    object: str
    source_id: str
    source_class: str
    observed_at: int
    strength: int = 1
    valid_from: int | None = None
    valid_until: int | None = None
    confidence: float = 1.0
    direct: bool = True

    def __post_init__(self) -> None:
        if not self.subject or not self.predicate or not self.object:
            raise ValueError("claim subject, predicate, and object must be non-empty")
        if not self.source_id or not self.source_class:
            raise ValueError("CG-3 claims require provenance")
        if self.strength < 1:
            raise ValueError("claim strength must be positive")
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


@dataclass(frozen=True, slots=True)
class DecisionCase:
    decision_id: str
    field_id: str
    decision_node: str
    field_node: str
    mission: JointMission
    as_of: int


@dataclass(frozen=True, slots=True)
class FieldDecisionEvidence:
    field_id: str
    claims: tuple[DecisionClaim, ...]
    cases: tuple[DecisionCase, ...]
    states: dict[str, IndividualState]
    current_agents: frozenset[str]
    departed_agents: frozenset[str]


@dataclass(frozen=True, slots=True)
class DecisionMetrics:
    arm: Arm
    successes: int
    trials: int
    decisions: int
    oracle_pair_matches: int
    invalid_selections: int
    context_claims: int
    provenance_complete_claims: int
    expected_success_sum: float
    oracle_expected_success_sum: float
    regret_sum: float

    @property
    def mission_success_rate(self) -> float:
        return self.successes / self.trials if self.trials else 0.0

    @property
    def oracle_pair_rate(self) -> float:
        return self.oracle_pair_matches / self.decisions if self.decisions else 1.0

    @property
    def invalid_selection_rate(self) -> float:
        return self.invalid_selections / self.decisions if self.decisions else 0.0

    @property
    def mean_context_claims(self) -> float:
        return self.context_claims / self.decisions if self.decisions else 0.0

    @property
    def provenance_completeness(self) -> float:
        return (
            self.provenance_complete_claims / self.context_claims
            if self.context_claims
            else 1.0
        )

    @property
    def mean_expected_success(self) -> float:
        return self.expected_success_sum / self.decisions if self.decisions else 0.0

    @property
    def mean_oracle_expected_success(self) -> float:
        return self.oracle_expected_success_sum / self.decisions if self.decisions else 0.0

    @property
    def mean_regret(self) -> float:
        return self.regret_sum / self.decisions if self.decisions else 0.0


def _capsules_path(source: Path) -> Path:
    options = [
        source / "output" / "discovery-source" / "capsules.private.jsonl",
        source / "output" / "replication-source" / "capsules.private.jsonl",
    ]
    for path in options:
        if path.exists():
            return path
    raise FileNotFoundError("W5 source artifact does not contain capsules.private.jsonl")


def _field_agents(capsules: list[dict[str, Any]], field_id: str) -> list[IndividualState]:
    selected = [
        IndividualState(
            agent_id=str(row["agent_id"]),
            practice_by_skill={
                str(skill): int(value)
                for skill, value in dict(row["practice_by_skill"]).items()
            },
        )
        for row in capsules
        if str(row["field_id"]) == field_id
    ]
    ordered = sorted(selected, key=lambda item: _stable_key(field_id, item.agent_id))
    if len(ordered) != 12:
        raise ValueError(f"{field_id} must contain exactly 12 source agents")
    return ordered


def _source_field_by_run(runs: list[dict[str, str]]) -> dict[str, str]:
    return {
        str(row["run_id"]): f"w4-source-seed-{int(row['seed'])}"
        for row in runs
    }


def build_field_decision_evidence(
    *,
    source_dir: str | Path,
    mission_rows: list[dict[str, Any]],
    field_id: str,
    turnover_time: int,
    as_of: int,
    conflict_confidence: float,
    rumor_count: int,
) -> FieldDecisionEvidence:
    source = Path(source_dir)
    runs = _read_csv(source / "raw" / "runs.csv")
    outcomes = _read_csv(source / "raw" / "outcomes.csv")
    capsules = _read_jsonl(_capsules_path(source))
    agents = _field_agents(capsules, field_id)
    states = {agent.agent_id: agent for agent in agents}
    departed = agents[:4]
    current = agents[4:8]

    field_by_run = _source_field_by_run(runs)
    successful_counts: dict[tuple[str, str], int] = defaultdict(int)
    latest_cycle: dict[tuple[str, str], int] = defaultdict(lambda: -1)
    for row in outcomes:
        if field_by_run.get(str(row["run_id"])) != field_id:
            continue
        if not _as_bool(str(row["success"])) or not row.get("winner_agent_id"):
            continue
        key = (str(row["winner_agent_id"]), str(row["required_skill"]))
        successful_counts[key] += 1
        latest_cycle[key] = max(latest_cycle[key], int(row["cycle"]))

    claims: list[DecisionClaim] = []
    field_node = f"field:{field_id}"
    for member in departed:
        claims.append(
            DecisionClaim(
                field_id=field_id,
                subject=member.agent_id,
                predicate="available_in",
                object=field_node,
                source_id=f"availability:departed:{field_id}:{member.agent_id}",
                source_class="availability",
                observed_at=0,
                valid_from=0,
                valid_until=turnover_time,
            )
        )
    for member in current:
        claims.append(
            DecisionClaim(
                field_id=field_id,
                subject=member.agent_id,
                predicate="available_in",
                object=field_node,
                source_id=f"availability:current:{field_id}:{member.agent_id}",
                source_class="availability",
                observed_at=turnover_time,
                valid_from=turnover_time,
            )
        )

    for (agent_id, skill), count in sorted(successful_counts.items()):
        claims.append(
            DecisionClaim(
                field_id=field_id,
                subject=agent_id,
                predicate="demonstrated_skill",
                object=f"skill:{skill}",
                source_id=f"field-outcomes:{field_id}:{agent_id}:{skill}",
                source_class="field_outcome_summary",
                observed_at=latest_cycle[(agent_id, skill)],
                strength=count,
            )
        )

    missions = [
        JointMission(
            mission_id=str(row["mission_id"]),
            context=str(row["context"]),
            lead_skill=str(row["lead_skill"]),
            support_skill=str(row["support_skill"]),
        )
        for row in mission_rows
    ]
    required_skills = {mission.lead_skill for mission in missions} | {
        mission.support_skill for mission in missions
    }
    departed_ranked = sorted(
        departed,
        key=lambda member: (
            sum(
                successful_counts.get((member.agent_id, skill), 0)
                for skill in required_skills
            ),
            member.agent_id,
        ),
        reverse=True,
    )
    for member in departed_ranked[:rumor_count]:
        claims.append(
            DecisionClaim(
                field_id=field_id,
                subject=member.agent_id,
                predicate="available_in",
                object=field_node,
                source_id=f"rumor:availability:{field_id}:{member.agent_id}",
                source_class="rumor",
                observed_at=as_of,
                valid_from=turnover_time,
                confidence=conflict_confidence,
                direct=False,
            )
        )

    cases: list[DecisionCase] = []
    for mission in missions:
        decision_node = f"decision:{field_id}:{mission.mission_id}"
        claims.extend(
            [
                DecisionClaim(
                    field_id=field_id,
                    subject=decision_node,
                    predicate="recruits_from",
                    object=field_node,
                    source_id=f"mission:{mission.mission_id}:field",
                    source_class="decision_requirement",
                    observed_at=as_of,
                    valid_from=turnover_time,
                ),
                DecisionClaim(
                    field_id=field_id,
                    subject=decision_node,
                    predicate="needs_lead_skill",
                    object=f"skill:{mission.lead_skill}",
                    source_id=f"mission:{mission.mission_id}:lead",
                    source_class="decision_requirement",
                    observed_at=as_of,
                    valid_from=turnover_time,
                ),
                DecisionClaim(
                    field_id=field_id,
                    subject=decision_node,
                    predicate="needs_support_skill",
                    object=f"skill:{mission.support_skill}",
                    source_id=f"mission:{mission.mission_id}:support",
                    source_class="decision_requirement",
                    observed_at=as_of,
                    valid_from=turnover_time,
                ),
            ]
        )
        cases.append(
            DecisionCase(
                decision_id=f"{field_id}:{mission.mission_id}",
                field_id=field_id,
                decision_node=decision_node,
                field_node=field_node,
                mission=mission,
                as_of=as_of,
            )
        )

    return FieldDecisionEvidence(
        field_id=field_id,
        claims=tuple(claims),
        cases=tuple(cases),
        states=states,
        current_agents=frozenset(member.agent_id for member in current),
        departed_agents=frozenset(member.agent_id for member in departed),
    )


def _hash_order(prefix: str, case_id: str, claim: DecisionClaim) -> bytes:
    payload = (
        f"{prefix}|{case_id}|{claim.source_id}|{claim.subject}|"
        f"{claim.predicate}|{claim.object}"
    ).encode()
    return hashlib.sha256(payload).digest()


def _compile_graph(
    claims: tuple[DecisionClaim, ...],
    case: DecisionCase,
    *,
    budget: int,
    min_confidence: float,
) -> tuple[DecisionClaim, ...]:
    eligible = [claim for claim in claims if claim.confidence >= min_confidence]
    frontier = {case.decision_node}
    visited = set(frontier)
    selected: list[DecisionClaim] = []
    selected_ids: set[str] = set()

    for hop in range(2):
        rows: list[DecisionClaim] = []
        for claim in eligible:
            if claim.source_id in selected_ids:
                continue
            if claim.source_class == "decision_requirement" and claim.subject != case.decision_node:
                continue
            if claim.subject not in frontier and claim.object not in frontier:
                continue
            rows.append(claim)
        rows.sort(
            key=lambda claim: (
                0 if claim.source_class == "decision_requirement" else 1,
                0 if claim.source_class == "availability" else 1,
                _hash_order(f"graph-{hop}", case.decision_id, claim),
            )
        )
        next_frontier: set[str] = set()
        for claim in rows:
            if len(selected) >= budget:
                break
            selected.append(claim)
            selected_ids.add(claim.source_id)
            if claim.subject not in visited:
                next_frontier.add(claim.subject)
            if claim.object not in visited:
                next_frontier.add(claim.object)
        if len(selected) >= budget or not next_frontier:
            break
        visited.update(next_frontier)
        frontier = next_frontier

    if len(selected) < budget:
        remaining = [
            claim
            for claim in eligible
            if claim.source_id not in selected_ids
            and not (
                claim.source_class == "decision_requirement"
                and claim.subject != case.decision_node
            )
        ]
        remaining.sort(key=lambda claim: _hash_order("graph-fill", case.decision_id, claim))
        selected.extend(remaining[: budget - len(selected)])
    return tuple(selected)


def _compile_flat(
    claims: tuple[DecisionClaim, ...],
    case: DecisionCase,
    *,
    budget: int,
    min_confidence: float,
) -> tuple[DecisionClaim, ...]:
    rows = [claim for claim in claims if claim.confidence >= min_confidence]
    rows.sort(key=lambda claim: _hash_order("flat", case.decision_id, claim))
    return tuple(rows[:budget])


def _compile_local(
    claims: tuple[DecisionClaim, ...],
    case: DecisionCase,
    *,
    min_confidence: float,
) -> tuple[DecisionClaim, ...]:
    return tuple(
        claim
        for claim in claims
        if claim.confidence >= min_confidence
        and (
            (claim.source_class == "decision_requirement" and claim.subject == case.decision_node)
            or (claim.source_class == "availability" and claim.valid_at(case.as_of))
        )
    )


def _shuffle_skill_edges(claims: tuple[DecisionClaim, ...]) -> tuple[DecisionClaim, ...]:
    indexes = [
        index
        for index, claim in enumerate(claims)
        if claim.source_class == "field_outcome_summary"
        and claim.predicate == "demonstrated_skill"
    ]
    ordered = sorted(indexes, key=lambda index: claims[index].source_id)
    objects = [claims[index].object for index in ordered]
    if len(objects) < 2:
        return claims
    result = list(claims)
    shift = max(1, len(objects) // 3)
    for position, index in enumerate(ordered):
        claim = claims[index]
        result[index] = DecisionClaim(
            field_id=claim.field_id,
            subject=claim.subject,
            predicate=claim.predicate,
            object=objects[(position + shift) % len(objects)],
            source_id=claim.source_id,
            source_class=claim.source_class,
            observed_at=claim.observed_at,
            strength=claim.strength,
            valid_from=claim.valid_from,
            valid_until=claim.valid_until,
            confidence=claim.confidence,
            direct=claim.direct,
        )
    return tuple(result)


def _skill_strength(
    context: tuple[DecisionClaim, ...], agent_id: str, skill: str
) -> int:
    node = f"skill:{skill}"
    return sum(
        claim.strength
        for claim in context
        if claim.subject == agent_id
        and claim.predicate == "demonstrated_skill"
        and claim.object == node
    )


def _select_pair(
    context: tuple[DecisionClaim, ...],
    case: DecisionCase,
    *,
    min_confidence: float,
    respect_temporal_validity: bool,
) -> tuple[str, str] | None:
    availability = [
        claim
        for claim in context
        if claim.confidence >= min_confidence
        and claim.predicate == "available_in"
        and claim.object == case.field_node
        and (not respect_temporal_validity or claim.valid_at(case.as_of))
    ]
    candidates = sorted({claim.subject for claim in availability})
    if len(candidates) < 2:
        return None

    scored: list[tuple[int, int, int, str, str]] = []
    for lead in candidates:
        for support in candidates:
            if lead == support:
                continue
            lead_score = _skill_strength(context, lead, case.mission.lead_skill)
            support_score = _skill_strength(context, support, case.mission.support_skill)
            scored.append((lead_score + support_score, lead_score, support_score, lead, support))
    if not scored:
        return None
    _, _, _, lead, support = max(scored)
    return lead, support


def _expected_success(
    states: dict[str, IndividualState], pair: tuple[str, str], mission: JointMission
) -> float:
    environment = JointEnvironment()
    lead, support = pair
    return (
        environment.role_probability(states[lead], mission.lead_skill)
        * environment.role_probability(states[support], mission.support_skill)
    )


def _oracle_pair(field: FieldDecisionEvidence, case: DecisionCase) -> tuple[str, str]:
    candidates = sorted(field.current_agents)
    scored = [
        (_expected_success(field.states, (lead, support), case.mission), lead, support)
        for lead in candidates
        for support in candidates
        if lead != support
    ]
    _, lead, support = max(scored)
    return lead, support


def _trial_success(
    field: FieldDecisionEvidence,
    case: DecisionCase,
    pair: tuple[str, str],
    *,
    trial: int,
) -> bool:
    lead, support = pair
    return JointEnvironment().evaluate(
        field.states[lead],
        field.states[support],
        case.mission,
        JointAction(lead, "lead"),
        JointAction(support, "support"),
        seed=_seed("cg3", case.field_id, case.mission.mission_id, trial),
    )


def evaluate_fields(
    fields: list[FieldDecisionEvidence],
    *,
    context_budget: int,
    min_confidence: float,
    evaluation_trials: int,
) -> dict[Arm, DecisionMetrics]:
    accumulators: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "successes": 0,
            "trials": 0,
            "decisions": 0,
            "oracle_pair_matches": 0,
            "invalid_selections": 0,
            "context_claims": 0,
            "provenance_complete_claims": 0,
            "expected_success_sum": 0.0,
            "oracle_expected_success_sum": 0.0,
            "regret_sum": 0.0,
        }
    )

    for field in fields:
        shuffled = _shuffle_skill_edges(field.claims)
        for case in field.cases:
            shared = _compile_graph(
                field.claims,
                case,
                budget=context_budget,
                min_confidence=min_confidence,
            )
            contexts: dict[Arm, tuple[DecisionClaim, ...] | None] = {
                "local_only": _compile_local(
                    field.claims, case, min_confidence=min_confidence
                ),
                "pooled_flat": _compile_flat(
                    field.claims,
                    case,
                    budget=context_budget,
                    min_confidence=min_confidence,
                ),
                "temporal_graph": shared,
                "shuffled_graph": _compile_graph(
                    shuffled,
                    case,
                    budget=context_budget,
                    min_confidence=min_confidence,
                ),
                "stale_graph": shared,
                "conflicted_graph": _compile_graph(
                    field.claims,
                    case,
                    budget=context_budget,
                    min_confidence=0.0,
                ),
                "oracle": None,
            }
            inference: dict[Arm, tuple[float, bool]] = {
                "local_only": (min_confidence, True),
                "pooled_flat": (min_confidence, True),
                "temporal_graph": (min_confidence, True),
                "shuffled_graph": (min_confidence, True),
                "stale_graph": (min_confidence, False),
                "conflicted_graph": (0.0, True),
                "oracle": (min_confidence, True),
            }

            oracle = _oracle_pair(field, case)
            oracle_expected = _expected_success(field.states, oracle, case.mission)

            for arm, context in contexts.items():
                if arm == "oracle":
                    pair = oracle
                else:
                    threshold, temporal = inference[arm]
                    assert context is not None
                    pair = _select_pair(
                        context,
                        case,
                        min_confidence=threshold,
                        respect_temporal_validity=temporal,
                    )

                row = accumulators[arm]
                row["decisions"] += 1
                row["trials"] += evaluation_trials
                row["oracle_expected_success_sum"] += oracle_expected

                if context is not None:
                    row["context_claims"] += len(context)
                    row["provenance_complete_claims"] += sum(
                        bool(claim.source_id and claim.source_class) for claim in context
                    )

                valid = (
                    pair is not None
                    and pair[0] in field.current_agents
                    and pair[1] in field.current_agents
                    and pair[0] != pair[1]
                )
                if not valid:
                    row["invalid_selections"] += 1
                    row["regret_sum"] += oracle_expected
                    continue

                assert pair is not None
                chosen_expected = _expected_success(field.states, pair, case.mission)
                row["expected_success_sum"] += chosen_expected
                row["regret_sum"] += max(0.0, oracle_expected - chosen_expected)
                row["oracle_pair_matches"] += int(pair == oracle)
                row["successes"] += sum(
                    _trial_success(field, case, pair, trial=trial)
                    for trial in range(evaluation_trials)
                )

    return {
        arm: DecisionMetrics(arm=arm, **values)  # type: ignore[arg-type]
        for arm, values in accumulators.items()
    }


def metric_row(metrics: DecisionMetrics) -> dict[str, object]:
    return {
        "arm": metrics.arm,
        "successes": metrics.successes,
        "trials": metrics.trials,
        "decisions": metrics.decisions,
        "mission_success_rate": metrics.mission_success_rate,
        "oracle_pair_matches": metrics.oracle_pair_matches,
        "oracle_pair_rate": metrics.oracle_pair_rate,
        "invalid_selections": metrics.invalid_selections,
        "invalid_selection_rate": metrics.invalid_selection_rate,
        "context_claims": metrics.context_claims,
        "mean_context_claims": metrics.mean_context_claims,
        "provenance_completeness": metrics.provenance_completeness,
        "mean_expected_success": metrics.mean_expected_success,
        "mean_oracle_expected_success": metrics.mean_oracle_expected_success,
        "mean_regret": metrics.mean_regret,
    }
