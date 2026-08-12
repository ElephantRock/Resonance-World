"""Exploratory CG-4M measurement-sufficiency study.

CG-4M rebuilds the frozen CG-4 societies unchanged, then appends supplemental live
post-turnover probes without changing membership. It evaluates event reconciliation,
minimum independent-event support, conservative estimation, and bundle-aware
retrieval. This is post-unblinding exploratory analysis and creates no confirmatory
claim.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from resonance_world.context_graph_w3_endogenous import (
    CG4Mission,
    EndogenousField,
    LiveClaim,
    _expected_success,
    _membership_candidates,
    _observation_bundles,
    _oracle_pair,
    _uniform,
    build_endogenous_field,
)
from resonance_world.w4a_joint_learning import JointEnvironment

Bundle = tuple[str, str, str, str, float, int, tuple[LiveClaim, ...]]
Pair = tuple[str, str]
Cell = tuple[str, str]


@dataclass(frozen=True, slots=True)
class EstimatorSpec:
    name: str
    kind: str
    min_support: int
    fallback_score: float
    alpha: float = 1.0
    beta: float = 1.0
    z: float = 1.2815515655446004


@dataclass(frozen=True, slots=True)
class CellEvidence:
    successes: int
    events: int
    bundles: tuple[Bundle, ...]


@dataclass(frozen=True, slots=True)
class DecisionResult:
    expected_success: float
    oracle_expected_success: float
    regret: float
    selected_role_true_gap: float
    selected_single_success_roles: int
    selected_roles: int
    oracle_pair_match: int
    context_claims: int
    complete_bundles: int


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _missions(rows: list[dict[str, Any]]) -> list[CG4Mission]:
    return [
        CG4Mission(
            mission_id=str(row["mission_id"]),
            lead_skill=str(row["lead_skill"]),
            support_skill=str(row["support_skill"]),
        )
        for row in rows
    ]


def _estimators(config: dict[str, Any]) -> dict[str, EstimatorSpec]:
    output: dict[str, EstimatorSpec] = {}
    for row in config["measurement"]["estimators"]:
        spec = EstimatorSpec(
            name=str(row["name"]),
            kind=str(row["kind"]),
            min_support=int(row["min_support"]),
            fallback_score=float(row["fallback_score"]),
            alpha=float(row.get("alpha", 1.0)),
            beta=float(row.get("beta", 1.0)),
            z=float(row.get("z", 1.2815515655446004)),
        )
        output[spec.name] = spec
    return output


def _build_base_fields(
    capsules_path: Path,
    field_ids: list[str],
    cg4: dict[str, Any],
) -> list[EndogenousField]:
    experiment = cg4["experiment"]
    return [
        build_endogenous_field(
            capsules_path=capsules_path,
            field_id=field_id,
            initial_roster_size=int(experiment["initial_roster_size"]),
            turnover_count=int(experiment["turnover_count"]),
            probes_per_skill=int(experiment["probes_per_skill"]),
            skills_per_agent=int(experiment["skills_per_agent"]),
            noise_rate=float(experiment["observation_noise_rate"]),
            rumor_count=int(experiment["rumor_count"]),
        )
        for field_id in field_ids
    ]


def _canonical_event_bundles(
    claims: list[LiveClaim] | tuple[LiveClaim, ...],
    *,
    min_confidence: float,
) -> list[Bundle]:
    best: dict[str, Bundle] = {}
    for bundle in _observation_bundles(claims, min_confidence=min_confidence):
        event_id, observer, _agent, _skill, confidence, observed_at, _claims = bundle
        prior = best.get(event_id)
        candidate_key = (confidence, observed_at, observer)
        if prior is None or candidate_key > (prior[4], prior[5], prior[1]):
            best[event_id] = bundle
    return sorted(best.values(), key=lambda item: (item[5], item[0], item[1]))


def _event_diagnostics(field: EndogenousField, min_confidence: float) -> dict[str, int]:
    observer_bundles = _observation_bundles(field.claims, min_confidence=0.0)
    canonical = _canonical_event_bundles(field.claims, min_confidence=min_confidence)
    distinct_events = {row[0] for row in observer_bundles}
    return {
        "observer_complete_bundles": len(observer_bundles),
        "distinct_event_ids": len(distinct_events),
        "canonical_admissible_events": len(canonical),
        "duplicate_observer_bundles_collapsed": len(observer_bundles) - len(distinct_events),
    }


def _latest_active_membership_claims(
    field: EndogenousField,
    *,
    min_confidence: float,
) -> tuple[LiveClaim, ...]:
    latest: dict[str, LiveClaim] = {}
    for claim in field.claims:
        if claim.predicate != "membership_state" or claim.confidence < min_confidence:
            continue
        prior = latest.get(claim.subject)
        if prior is None or (claim.observed_at, claim.source_id) > (
            prior.observed_at,
            prior.source_id,
        ):
            latest[claim.subject] = claim
    rows = [
        claim
        for agent_id, claim in latest.items()
        if agent_id in field.current_members and claim.object == "active"
    ]
    return tuple(sorted(rows, key=lambda claim: (claim.subject, claim.source_id)))


def _scout_for(field: EndogenousField, agent_id: str, event_id: str) -> str:
    candidates = sorted(member for member in field.current_members if member != agent_id)
    if not candidates:
        return agent_id
    index = int.from_bytes(hashlib.sha256(event_id.encode()).digest()[:4], "big") % len(
        candidates
    )
    return candidates[index]


def _probe_claims(
    *,
    field: EndogenousField,
    event_id: str,
    agent_id: str,
    skill: str,
    observed_at: int,
    noise_rate: float,
) -> tuple[LiveClaim, ...]:
    environment = JointEnvironment()
    probability = environment.role_probability(field.states[agent_id], skill)
    success = _uniform("cg4m-live-probe", event_id) < probability
    scout = _scout_for(field, agent_id, event_id)
    noisy = _uniform("cg4m-observation-noise", event_id, scout) < noise_rate
    rows: list[LiveClaim] = []
    for observer, observed_success, confidence in (
        (agent_id, success, 0.95),
        (scout, not success if noisy else success, 0.45 if noisy else 0.85),
    ):
        outcome = "success" if observed_success else "failure"
        for predicate, value in (
            ("participant", agent_id),
            ("skill", skill),
            ("outcome", outcome),
        ):
            rows.append(
                LiveClaim(
                    field_id=field.field_id,
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
    return tuple(rows)


def _supplement_field(
    field: EndogenousField,
    *,
    target_events: int,
    min_confidence: float,
    noise_rate: float,
) -> tuple[EndogenousField, dict[str, int]]:
    if target_events <= 0:
        diagnostics = _event_diagnostics(field, min_confidence)
        diagnostics["supplemental_events_added"] = 0
        diagnostics["supplemental_claims_added"] = 0
        return field, diagnostics

    canonical = _canonical_event_bundles(field.claims, min_confidence=min_confidence)
    counts: dict[Cell, int] = defaultdict(int)
    for _event, _observer, agent_id, skill, _confidence, _time, _claims in canonical:
        if agent_id in field.current_members:
            counts[(agent_id, skill)] += 1

    skills = sorted(next(iter(field.states.values())).practice_by_skill)
    claims = list(field.claims)
    belief_rows = {owner: list(rows) for owner, rows in field.belief_snapshot.items()}
    observed_at = field.as_of + 1
    added_events = 0
    added_claims = 0
    for agent_id in sorted(field.current_members):
        for skill in skills:
            current = counts[(agent_id, skill)]
            for event_index in range(current, target_events):
                event_id = (
                    f"cg4m-probe:{field.field_id}:{agent_id}:{skill}:{event_index}"
                )
                rows = _probe_claims(
                    field=field,
                    event_id=event_id,
                    agent_id=agent_id,
                    skill=skill,
                    observed_at=observed_at,
                    noise_rate=noise_rate,
                )
                claims.extend(rows)
                for claim in rows:
                    belief_rows.setdefault(claim.observed_by, []).append(claim.source_id)
                observed_at += 1
                added_events += 1
                added_claims += len(rows)

    observer_groups: dict[tuple[str, str], dict[str, str]] = defaultdict(dict)
    for claim in claims:
        if claim.source_class == "live_probe":
            observer_groups[(claim.subject, claim.observed_by)][claim.predicate] = claim.object
    event_observers: dict[str, set[str]] = defaultdict(set)
    event_outcomes: dict[str, set[str]] = defaultdict(set)
    for (event_id, observer), values in observer_groups.items():
        event_observers[event_id].add(observer)
        if "outcome" in values:
            event_outcomes[event_id].add(values["outcome"])
    low_confidence = sum(claim.confidence < min_confidence for claim in claims)

    updated = EndogenousField(
        field_id=field.field_id,
        states=field.states,
        claims=tuple(claims),
        belief_snapshot={owner: tuple(rows) for owner, rows in sorted(belief_rows.items())},
        current_members=field.current_members,
        departed_members=field.departed_members,
        coordinator_id=field.coordinator_id,
        as_of=observed_at + 1,
        emitted_claims=len(claims),
        duplicate_observation_groups=sum(len(rows) > 1 for rows in event_observers.values()),
        conflicting_observation_groups=sum(len(rows) > 1 for rows in event_outcomes.values()),
        low_confidence_claims=low_confidence,
    )
    diagnostics = _event_diagnostics(updated, min_confidence)
    diagnostics["supplemental_events_added"] = added_events
    diagnostics["supplemental_claims_added"] = added_claims
    return updated, diagnostics


def _cell_evidence(
    claims: list[LiveClaim] | tuple[LiveClaim, ...],
    *,
    candidates: set[str],
    min_confidence: float,
) -> dict[Cell, CellEvidence]:
    grouped: dict[Cell, list[Bundle]] = defaultdict(list)
    successes: dict[Cell, int] = defaultdict(int)
    for bundle in _canonical_event_bundles(claims, min_confidence=min_confidence):
        _event, _observer, agent_id, skill, _confidence, _time, bundle_claims = bundle
        if agent_id not in candidates:
            continue
        grouped[(agent_id, skill)].append(bundle)
        outcome = next(claim.object for claim in bundle_claims if claim.predicate == "outcome")
        successes[(agent_id, skill)] += int(outcome == "success")
    return {
        cell: CellEvidence(
            successes=successes[cell],
            events=len(rows),
            bundles=tuple(sorted(rows, key=lambda item: (item[5], item[0], item[1]))),
        )
        for cell, rows in grouped.items()
    }


def _score(evidence: CellEvidence | None, estimator: EstimatorSpec) -> float:
    if evidence is None or evidence.events < estimator.min_support:
        return estimator.fallback_score
    successes = evidence.successes
    total = evidence.events
    if estimator.kind == "posterior_mean":
        return (estimator.alpha + successes) / (
            estimator.alpha + estimator.beta + total
        )
    if estimator.kind == "wilson_lower":
        phat = successes / total
        z2 = estimator.z * estimator.z
        denominator = 1.0 + z2 / total
        center = phat + z2 / (2.0 * total)
        radius = estimator.z * math.sqrt(
            phat * (1.0 - phat) / total + z2 / (4.0 * total * total)
        )
        return max(0.0, (center - radius) / denominator)
    raise ValueError(f"unsupported estimator kind: {estimator.kind}")


def _select_pair(
    candidates: set[str],
    mission: CG4Mission,
    evidence: dict[Cell, CellEvidence],
    estimator: EstimatorSpec,
) -> Pair | None:
    if len(candidates) < 2:
        return None
    best: tuple[float, str, str, str] | None = None
    for lead_id in sorted(candidates):
        for support_id in sorted(candidates):
            if lead_id == support_id:
                continue
            score = _score(evidence.get((lead_id, mission.lead_skill)), estimator) * _score(
                evidence.get((support_id, mission.support_skill)), estimator
            )
            row = (score, f"{lead_id}::{support_id}", lead_id, support_id)
            if best is None or row[:2] > best[:2]:
                best = row
    return None if best is None else (best[2], best[3])


def _pearson(xs: list[float], ys: list[float]) -> float:
    if len(xs) != len(ys) or len(xs) < 2:
        return 0.0
    mx = sum(xs) / len(xs)
    my = sum(ys) / len(ys)
    numerator = sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True))
    dx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    dy = math.sqrt(sum((y - my) ** 2 for y in ys))
    return numerator / (dx * dy) if dx and dy else 0.0


def _decision_metrics(
    field: EndogenousField,
    mission: CG4Mission,
    *,
    claims: tuple[LiveClaim, ...],
    estimator: EstimatorSpec,
    min_confidence: float,
) -> DecisionResult:
    candidates = _membership_candidates(
        claims,
        min_confidence=min_confidence,
        respect_temporal_order=True,
    )
    evidence = _cell_evidence(
        claims,
        candidates=candidates,
        min_confidence=min_confidence,
    )
    pair = _select_pair(candidates, mission, evidence, estimator)
    oracle = _oracle_pair(field, mission)
    oracle_expected = _expected_success(field, mission, oracle)
    if pair is None or not set(pair).issubset(field.current_members):
        expected = 0.0
        role_gap = sum(
            max(
                JointEnvironment().role_probability(field.states[agent], skill)
                for agent in field.current_members
            )
            for skill in mission.required_skills
        ) / 2.0
        single = 0
        match = 0
    else:
        expected = _expected_success(field, mission, pair)
        role_rows = (
            (pair[0], mission.lead_skill),
            (pair[1], mission.support_skill),
        )
        gaps = []
        single = 0
        environment = JointEnvironment()
        for agent_id, skill in role_rows:
            best_true = max(
                environment.role_probability(field.states[candidate], skill)
                for candidate in field.current_members
            )
            selected_true = environment.role_probability(field.states[agent_id], skill)
            gaps.append(best_true - selected_true)
            cell = evidence.get((agent_id, skill))
            if cell is not None and cell.events == 1 and cell.successes == 1:
                single += 1
        role_gap = sum(gaps) / len(gaps)
        match = int(pair == oracle)
    return DecisionResult(
        expected_success=expected,
        oracle_expected_success=oracle_expected,
        regret=oracle_expected - expected,
        selected_role_true_gap=role_gap,
        selected_single_success_roles=single,
        selected_roles=2,
        oracle_pair_match=match,
        context_claims=len(claims),
        complete_bundles=len(
            _canonical_event_bundles(claims, min_confidence=min_confidence)
        ),
    )


def _full_measurement_summary(
    fields: list[EndogenousField],
    missions: list[CG4Mission],
    *,
    estimator: EstimatorSpec,
    min_confidence: float,
) -> dict[str, Any]:
    results: list[DecisionResult] = []
    estimates: list[float] = []
    truths: list[float] = []
    per_field: dict[str, list[DecisionResult]] = defaultdict(list)
    environment = JointEnvironment()
    for field in fields:
        membership = _latest_active_membership_claims(
            field,
            min_confidence=min_confidence,
        )
        candidates = set(field.current_members)
        evidence = _cell_evidence(
            field.claims,
            candidates=candidates,
            min_confidence=min_confidence,
        )
        for mission in missions:
            context = tuple(membership) + tuple(
                claim
                for bundle in _canonical_event_bundles(
                    field.claims, min_confidence=min_confidence
                )
                for claim in bundle[-1]
            )
            result = _decision_metrics(
                field,
                mission,
                claims=context,
                estimator=estimator,
                min_confidence=min_confidence,
            )
            results.append(result)
            per_field[field.field_id].append(result)
            for skill in mission.required_skills:
                for agent_id in sorted(candidates):
                    estimates.append(_score(evidence.get((agent_id, skill)), estimator))
                    truths.append(environment.role_probability(field.states[agent_id], skill))

    def mean(name: str) -> float:
        return sum(getattr(row, name) for row in results) / len(results) if results else 0.0

    output = {
        "decisions": len(results),
        "estimate_truth_pearson": _pearson(estimates, truths),
        "mean_expected_success": mean("expected_success"),
        "mean_regret": mean("regret"),
        "mean_oracle_expected_success": mean("oracle_expected_success"),
        "oracle_gap": mean("regret"),
        "mean_selected_role_true_gap": mean("selected_role_true_gap"),
        "selected_single_success_rate": (
            sum(row.selected_single_success_roles for row in results)
            / sum(row.selected_roles for row in results)
            if results
            else 0.0
        ),
        "oracle_pair_rate": (
            sum(row.oracle_pair_match for row in results) / len(results) if results else 0.0
        ),
        "per_field": {},
    }
    for field_id, rows in sorted(per_field.items()):
        output["per_field"][field_id] = {
            "decisions": len(rows),
            "mean_expected_success": sum(row.expected_success for row in rows) / len(rows),
            "mean_regret": sum(row.regret for row in rows) / len(rows),
            "mean_selected_role_true_gap": sum(
                row.selected_role_true_gap for row in rows
            )
            / len(rows),
            "selected_single_success_rate": sum(
                row.selected_single_success_roles for row in rows
            )
            / sum(row.selected_roles for row in rows),
        }
    return output


def _bundle_flat_context(
    field: EndogenousField,
    mission: CG4Mission,
    *,
    budget: int,
    min_confidence: float,
) -> tuple[LiveClaim, ...]:
    membership = list(
        _latest_active_membership_claims(field, min_confidence=min_confidence)
    )
    output = membership[:budget]
    if len(output) >= budget:
        return tuple(output)
    bundles = [
        bundle
        for bundle in _canonical_event_bundles(
            field.claims, min_confidence=min_confidence
        )
        if bundle[2] in field.current_members and bundle[3] in mission.required_skills
    ]
    bundles.sort(
        key=lambda bundle: hashlib.sha256(
            f"cg4m-bundle-flat|{mission.mission_id}|{bundle[0]}".encode()
        ).digest()
    )
    for bundle in bundles:
        claims = bundle[-1]
        if len(output) + len(claims) > budget:
            break
        output.extend(claims)
    return tuple(output)


def _ranked_cell_bundles(
    field: EndogenousField,
    mission: CG4Mission,
    *,
    estimator: EstimatorSpec,
    min_confidence: float,
) -> dict[str, list[tuple[Cell, CellEvidence, float]]]:
    evidence = _cell_evidence(
        field.claims,
        candidates=set(field.current_members),
        min_confidence=min_confidence,
    )
    output: dict[str, list[tuple[Cell, CellEvidence, float]]] = {}
    for role, skill in (("lead", mission.lead_skill), ("support", mission.support_skill)):
        rows = []
        for agent_id in sorted(field.current_members):
            cell = (agent_id, skill)
            cell_evidence = evidence.get(cell, CellEvidence(0, 0, ()))
            rows.append((cell, cell_evidence, _score(cell_evidence, estimator)))
        rows.sort(key=lambda row: (-row[2], -row[1].events, row[0][0]))
        output[role] = rows
    return output


def _coverage_graph_context(
    field: EndogenousField,
    mission: CG4Mission,
    *,
    budget: int,
    estimator: EstimatorSpec,
    min_confidence: float,
    live_bundle_limit: int | None = None,
) -> tuple[LiveClaim, ...]:
    membership = list(
        _latest_active_membership_claims(field, min_confidence=min_confidence)
    )
    output = membership[:budget]
    if len(output) >= budget:
        return tuple(output)
    max_bundles = (budget - len(output)) // 3
    if live_bundle_limit is not None:
        max_bundles = min(max_bundles, live_bundle_limit)
    ranked = _ranked_cell_bundles(
        field,
        mission,
        estimator=estimator,
        min_confidence=min_confidence,
    )
    chosen: list[Bundle] = []
    used_events: set[str] = set()
    role_index = {"lead": 0, "support": 0}
    while len(chosen) < max_bundles:
        progress = False
        for role in ("lead", "support"):
            rows = ranked[role]
            while role_index[role] < len(rows):
                _cell, evidence, _score_value = rows[role_index[role]]
                role_index[role] += 1
                support = max(1, estimator.min_support)
                candidates = [
                    bundle for bundle in evidence.bundles[:support] if bundle[0] not in used_events
                ]
                if not candidates:
                    continue
                if len(chosen) + len(candidates) > max_bundles:
                    candidates = candidates[: max_bundles - len(chosen)]
                chosen.extend(candidates)
                used_events.update(bundle[0] for bundle in candidates)
                progress = True
                break
        if not progress:
            break
    if len(chosen) < max_bundles:
        residual = [
            bundle
            for role in ("lead", "support")
            for _cell, evidence, _score_value in ranked[role]
            for bundle in evidence.bundles
            if bundle[0] not in used_events
        ]
        residual.sort(key=lambda bundle: (bundle[5], bundle[0]), reverse=True)
        for bundle in residual:
            if len(chosen) >= max_bundles:
                break
            if bundle[0] in used_events:
                continue
            chosen.append(bundle)
            used_events.add(bundle[0])
    for bundle in chosen:
        output.extend(bundle[-1])
    return tuple(output[:budget])


def _hybrid_context(
    field: EndogenousField,
    mission: CG4Mission,
    *,
    budget: int,
    estimator: EstimatorSpec,
    min_confidence: float,
) -> tuple[LiveClaim, ...]:
    membership = list(
        _latest_active_membership_claims(field, min_confidence=min_confidence)
    )
    live_capacity = max(0, (budget - len(membership)) // 3)
    graph_limit = (2 * live_capacity) // 3
    graph = list(
        _coverage_graph_context(
            field,
            mission,
            budget=budget,
            estimator=estimator,
            min_confidence=min_confidence,
            live_bundle_limit=graph_limit,
        )
    )
    used_sources = {claim.source_id for claim in graph}
    flat = _bundle_flat_context(
        field,
        mission,
        budget=budget,
        min_confidence=min_confidence,
    )
    for claim in flat:
        if len(graph) >= budget:
            break
        if claim.source_id in used_sources:
            continue
        if claim.source_class == "live_probe":
            event_claims = [
                item
                for item in flat
                if item.subject == claim.subject and item.source_class == "live_probe"
            ]
            new = [item for item in event_claims if item.source_id not in used_sources]
            if len(new) != 3 or len(graph) + 3 > budget:
                continue
            graph.extend(new)
            used_sources.update(item.source_id for item in new)
        else:
            graph.append(claim)
            used_sources.add(claim.source_id)
    return tuple(graph[:budget])


def _retrieval_summary(
    fields: list[EndogenousField],
    missions: list[CG4Mission],
    *,
    arm: str,
    budget: int,
    estimator: EstimatorSpec,
    min_confidence: float,
) -> dict[str, Any]:
    results: list[DecisionResult] = []
    for field in fields:
        for mission in missions:
            if arm == "bundle_flat":
                context = _bundle_flat_context(
                    field,
                    mission,
                    budget=budget,
                    min_confidence=min_confidence,
                )
            elif arm == "coverage_graph":
                context = _coverage_graph_context(
                    field,
                    mission,
                    budget=budget,
                    estimator=estimator,
                    min_confidence=min_confidence,
                )
            elif arm == "hybrid_graph":
                context = _hybrid_context(
                    field,
                    mission,
                    budget=budget,
                    estimator=estimator,
                    min_confidence=min_confidence,
                )
            else:
                raise ValueError(f"unknown retrieval arm {arm}")
            results.append(
                _decision_metrics(
                    field,
                    mission,
                    claims=context,
                    estimator=estimator,
                    min_confidence=min_confidence,
                )
            )
    return {
        "decisions": len(results),
        "mean_expected_success": sum(row.expected_success for row in results) / len(results),
        "mean_regret": sum(row.regret for row in results) / len(results),
        "mean_selected_role_true_gap": sum(
            row.selected_role_true_gap for row in results
        )
        / len(results),
        "selected_single_success_rate": sum(
            row.selected_single_success_roles for row in results
        )
        / sum(row.selected_roles for row in results),
        "mean_context_claims": sum(row.context_claims for row in results) / len(results),
        "mean_complete_bundles": sum(row.complete_bundles for row in results) / len(results),
        "oracle_pair_rate": sum(row.oracle_pair_match for row in results) / len(results),
    }


def _parse_candidate(name: str, estimators: dict[str, EstimatorSpec]) -> tuple[int, EstimatorSpec]:
    target_text, estimator_name = name.split("+", 1)
    if not target_text.startswith("target"):
        raise ValueError(f"invalid candidate {name}")
    return int(target_text.removeprefix("target")), estimators[estimator_name]


def _measurement_qualifies(
    candidate: dict[str, Any],
    baseline: dict[str, Any],
) -> bool:
    return (
        candidate["selected_single_success_rate"] <= 0.10
        and baseline["mean_selected_role_true_gap"]
        - candidate["mean_selected_role_true_gap"]
        >= 0.03
        and candidate["mean_expected_success"] - baseline["mean_expected_success"] >= 0.02
    )


def _select_architecture(
    config: dict[str, Any],
    measurement: dict[str, dict[str, dict[str, Any]]],
    retrieval: dict[str, dict[str, dict[str, dict[str, Any]]]],
    estimators: dict[str, EstimatorSpec],
) -> dict[str, Any]:
    baseline_key = "target0+posterior_mean_min1"
    selected_measurement: str | None = None
    rejection_reasons: dict[str, list[str]] = {}
    for name in config["architecture_selection_rule"][
        "measurement_candidates_in_complexity_order"
    ]:
        target, estimator = _parse_candidate(name, estimators)
        key = f"target{target}+{estimator.name}"
        reasons = []
        for split in ("calibration", "evaluation"):
            if not _measurement_qualifies(
                measurement[split][key],
                measurement[split][baseline_key],
            ):
                reasons.append(split)
        rejection_reasons[key] = reasons
        if not reasons:
            selected_measurement = key
            break

    selected_retrieval: dict[str, Any] | None = None
    if selected_measurement is not None:
        for budget in config["retrieval"]["context_budgets_claims"]:
            budget_key = str(budget)
            flat_cal = retrieval["calibration"][selected_measurement][budget_key][
                "bundle_flat"
            ]["mean_expected_success"]
            flat_eval = retrieval["evaluation"][selected_measurement][budget_key][
                "bundle_flat"
            ]["mean_expected_success"]
            qualifying = []
            for arm in ("coverage_graph", "hybrid_graph"):
                cal = retrieval["calibration"][selected_measurement][budget_key][arm][
                    "mean_expected_success"
                ]
                ev = retrieval["evaluation"][selected_measurement][budget_key][arm][
                    "mean_expected_success"
                ]
                if cal >= flat_cal and ev >= flat_eval:
                    qualifying.append((arm, cal - flat_cal, ev - flat_eval))
            if qualifying:
                coverage = next((row for row in qualifying if row[0] == "coverage_graph"), None)
                best = coverage if coverage is not None else qualifying[0]
                selected_retrieval = {
                    "arm": best[0],
                    "budget": budget,
                    "calibration_lift_over_bundle_flat": best[1],
                    "evaluation_lift_over_bundle_flat": best[2],
                }
                break
    return {
        "measurement_candidate": selected_measurement,
        "retrieval_candidate": selected_retrieval,
        "measurement_rejections": rejection_reasons,
        "cg5_architecture_ready": (
            selected_measurement is not None and selected_retrieval is not None
        ),
        "selection_rule": "first complexity-ordered measurement candidate satisfying both splits; then smallest claim budget whose graph/hybrid does not underperform bundle-aware flat on either split",
    }


def _split_analysis(
    *,
    base_fields: list[EndogenousField],
    missions: list[CG4Mission],
    targets: list[int],
    estimators: dict[str, EstimatorSpec],
    config: dict[str, Any],
    min_confidence: float,
) -> tuple[
    dict[str, dict[str, Any]],
    dict[str, dict[str, dict[str, Any]]],
    dict[str, dict[str, int]],
]:
    measurement: dict[str, dict[str, Any]] = {}
    retrieval: dict[str, dict[str, dict[str, Any]]] = {}
    diagnostics: dict[str, dict[str, int]] = {}
    field_cache: dict[int, list[EndogenousField]] = {}
    noise_rate = float(
        config["measurement"]["supplemental_observer_policy"]["scout_noise_rate"]
    )
    for target in targets:
        fields = []
        totals: dict[str, int] = defaultdict(int)
        for field in base_fields:
            updated, field_diag = _supplement_field(
                field,
                target_events=target,
                min_confidence=min_confidence,
                noise_rate=noise_rate,
            )
            fields.append(updated)
            for key, value in field_diag.items():
                totals[key] += value
        field_cache[target] = fields
        diagnostics[f"target{target}"] = dict(totals)
        for estimator in estimators.values():
            key = f"target{target}+{estimator.name}"
            measurement[key] = _full_measurement_summary(
                fields,
                missions,
                estimator=estimator,
                min_confidence=min_confidence,
            )

    candidate_names = config["architecture_selection_rule"][
        "measurement_candidates_in_complexity_order"
    ]
    for candidate_name in candidate_names:
        target, estimator = _parse_candidate(candidate_name, estimators)
        key = f"target{target}+{estimator.name}"
        fields = field_cache[target]
        retrieval[key] = {}
        for budget in config["retrieval"]["context_budgets_claims"]:
            budget_key = str(budget)
            retrieval[key][budget_key] = {}
            for arm in config["retrieval"]["arms"]:
                retrieval[key][budget_key][arm] = _retrieval_summary(
                    fields,
                    missions,
                    arm=str(arm),
                    budget=int(budget),
                    estimator=estimator,
                    min_confidence=min_confidence,
                )
    return measurement, retrieval, diagnostics


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--cg4-config", type=Path, required=True)
    parser.add_argument("--cg4-result", type=Path, required=True)
    parser.add_argument("--cg4f-findings", type=Path, required=True)
    parser.add_argument("--calibration-capsules", type=Path, required=True)
    parser.add_argument("--evaluation-capsules", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    config = _read_json(args.config)
    cg4 = _read_json(args.cg4_config)
    cg4_result = _read_json(args.cg4_result)
    cg4f = _read_json(args.cg4f_findings)
    if config.get("confirmatory_claim") is not False:
        raise AssertionError("CG-4M must remain exploratory")
    if cg4_result.get("passed") is not False:
        raise AssertionError("frozen CG-4 failure status changed")
    if cg4f.get("confirmatory_claim") is not False:
        raise AssertionError("CG-4F boundary changed")

    calibration_source = cg4["sources"]["calibration"]
    evaluation_source = cg4["sources"]["evaluation"]
    if _sha256(args.calibration_capsules) != calibration_source["capsules_sha256"]:
        raise AssertionError("calibration capsule hash mismatch")
    if _sha256(args.evaluation_capsules) != evaluation_source["capsules_sha256"]:
        raise AssertionError("evaluation capsule hash mismatch")

    experiment = cg4["experiment"]
    min_confidence = float(experiment["min_confidence"])
    calibration_fields = _build_base_fields(
        args.calibration_capsules,
        [str(value) for value in calibration_source["field_ids"]],
        cg4,
    )
    evaluation_fields = _build_base_fields(
        args.evaluation_capsules,
        [str(value) for value in evaluation_source["field_ids"]],
        cg4,
    )
    calibration_missions = _missions(experiment["calibration_missions"])
    evaluation_missions = _missions(experiment["evaluation_missions"])
    estimators = _estimators(config)
    targets = [
        int(value)
        for value in config["measurement"][
            "target_independent_events_per_current_agent_skill"
        ]
    ]

    cal_measurement, cal_retrieval, cal_diagnostics = _split_analysis(
        base_fields=calibration_fields,
        missions=calibration_missions,
        targets=targets,
        estimators=estimators,
        config=config,
        min_confidence=min_confidence,
    )
    eval_measurement, eval_retrieval, eval_diagnostics = _split_analysis(
        base_fields=evaluation_fields,
        missions=evaluation_missions,
        targets=targets,
        estimators=estimators,
        config=config,
        min_confidence=min_confidence,
    )
    measurement = {
        "calibration": cal_measurement,
        "evaluation": eval_measurement,
    }
    retrieval = {
        "calibration": cal_retrieval,
        "evaluation": eval_retrieval,
    }
    selection = _select_architecture(config, measurement, retrieval, estimators)

    result = {
        "version": "context-graph-cg4m-measurement-sufficiency-result-v0.1",
        "status": "exploratory-post-unblinding-complete",
        "confirmatory_claim": False,
        "scientific_boundary": config["scientific_boundary"],
        "source_hashes": {
            "calibration_capsules_sha256": _sha256(args.calibration_capsules),
            "evaluation_capsules_sha256": _sha256(args.evaluation_capsules),
        },
        "frozen_cg4_status": "failed-and-unchanged",
        "measurement_matrix": measurement,
        "retrieval_matrix": retrieval,
        "event_diagnostics": {
            "calibration": cal_diagnostics,
            "evaluation": eval_diagnostics,
        },
        "architecture_selection": selection,
        "integrity": {
            "historical_outcome_rows_consumed": 0,
            "posthoc_imported_claims": 0,
            "belief_contamination_from_retrieval": 0,
            "outcome_law_graph_inputs": 0,
            "turnover_roster_changed_by_supplemental_probes": 0,
            "event_identity_reconciliation": True,
            "bundle_aware_flat_complete_units": True,
        },
        "interpretation_boundary": "CG-4M uses already-unblinded societies for exploratory design selection only. Any selected architecture must be frozen and tested on a genuinely new untouched cohort before a confirmatory claim.",
    }
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if "practice_by_skill" in text:
        raise AssertionError("private capability values leaked into CG-4M output")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text, encoding="utf-8")
    print(json.dumps({
        "architecture_selection": selection,
        "calibration_baseline": cal_measurement["target0+posterior_mean_min1"],
        "evaluation_baseline": eval_measurement["target0+posterior_mean_min1"],
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
