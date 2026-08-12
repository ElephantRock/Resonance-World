"""Exploratory CG-6 adaptive evidence-acquisition calibration.

CG-6 calibration reuses the already-unblinded CG-5 source cohort. It changes only
which supplemental live probe events are acquired before the frozen CG-5 estimator
and coverage retriever are applied. Evaluator capability is used only after policy
execution for diagnostics and expected-outcome scoring.
"""

from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import math
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from experiments.context_graph.run_cg4m_measurement_sufficiency import (
    CellEvidence,
    EstimatorSpec,
    _bundle_flat_context,
    _canonical_event_bundles,
    _cell_evidence,
    _coverage_graph_context,
    _pearson,
    _probe_claims,
    _score,
    _select_pair,
)
from resonance_world.context_graph_w3_endogenous import (
    CG4Mission,
    EndogenousField,
    LiveClaim,
    _expected_success,
    _membership_candidates,
    _oracle_pair,
    build_endogenous_field,
)
from resonance_world.w4a_joint_learning import JointEnvironment

Cell = tuple[str, str]
Pair = tuple[str, str]


@dataclass(frozen=True, slots=True)
class ProbeEvent:
    cell: Cell
    event_index: int
    event_id: str
    observed_at: int
    claims: tuple[LiveClaim, ...]


@dataclass(frozen=True, slots=True)
class PolicyMetrics:
    policy: str
    budget: int | None
    fields: int
    decisions: int
    mean_graph_expected_success: float
    mean_flat_expected_success: float
    mean_oracle_expected_success: float
    mean_graph_regret: float
    mean_selected_role_true_gap: float
    estimate_truth_pearson: float
    mean_supplemental_probe_events: float
    total_supplemental_probe_events: int
    probe_cost_fraction_vs_fixed_six: float
    graph_lift_over_cost_matched_flat: float
    positive_field_graph_lift_count: int
    decision_quality_gain_over_passive_per_probe: float


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def missions(config: dict[str, Any]) -> list[CG4Mission]:
    return [
        CG4Mission(
            mission_id=str(row["mission_id"]),
            lead_skill=str(row["lead_skill"]),
            support_skill=str(row["support_skill"]),
        )
        for row in config["missions"]
    ]


def estimator(config: dict[str, Any]) -> EstimatorSpec:
    row = config["estimator"]
    return EstimatorSpec(
        name=str(row["name"]),
        kind=str(row["kind"]),
        min_support=int(row["minimum_independent_event_support"]),
        fallback_score=float(row["fallback_score"]),
        z=float(row["z"]),
    )


def base_field(capsules: Path, field_id: str, config: dict[str, Any]) -> EndogenousField:
    row = config["society"]
    return build_endogenous_field(
        capsules_path=capsules,
        field_id=field_id,
        initial_roster_size=int(row["initial_roster_size"]),
        turnover_count=int(row["turnover_count"]),
        probes_per_skill=int(row["initial_probes_per_skill"]),
        skills_per_agent=int(row["initial_skills_per_agent"]),
        noise_rate=float(row["observation_noise_rate"]),
        rumor_count=int(row["rumor_count"]),
    )


def current_counts(field: EndogenousField, min_confidence: float) -> dict[Cell, int]:
    counts: dict[Cell, int] = defaultdict(int)
    for bundle in _canonical_event_bundles(field.claims, min_confidence=min_confidence):
        _event, _observer, agent_id, skill, _confidence, _time, _claims = bundle
        if agent_id in field.current_members:
            counts[(agent_id, skill)] += 1
    return dict(counts)


def supplemental_table(
    field: EndogenousField,
    *,
    max_events: int,
    min_confidence: float,
    noise_rate: float,
) -> tuple[dict[Cell, tuple[ProbeEvent, ...]], tuple[ProbeEvent, ...]]:
    counts = current_counts(field, min_confidence)
    skills = sorted(next(iter(field.states.values())).practice_by_skill)
    by_cell: dict[Cell, list[ProbeEvent]] = defaultdict(list)
    ordered: list[ProbeEvent] = []
    observed_at = field.as_of + 1
    for agent_id in sorted(field.current_members):
        for skill in skills:
            cell = (agent_id, skill)
            for event_index in range(counts.get(cell, 0), max_events):
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
                event = ProbeEvent(
                    cell=cell,
                    event_index=event_index,
                    event_id=event_id,
                    observed_at=observed_at,
                    claims=rows,
                )
                by_cell[cell].append(event)
                ordered.append(event)
                observed_at += 1
    return (
        {cell: tuple(rows) for cell, rows in sorted(by_cell.items())},
        tuple(ordered),
    )


def materialize(field: EndogenousField, events: list[ProbeEvent]) -> EndogenousField:
    selected = sorted(events, key=lambda row: (row.observed_at, row.event_id))
    claims = list(field.claims)
    belief_rows = {owner: list(rows) for owner, rows in field.belief_snapshot.items()}
    for event in selected:
        claims.extend(event.claims)
        for claim in event.claims:
            belief_rows.setdefault(claim.observed_by, []).append(claim.source_id)

    observers: dict[str, set[str]] = defaultdict(set)
    outcomes: dict[str, set[str]] = defaultdict(set)
    for claim in claims:
        if claim.source_class != "live_probe":
            continue
        observers[claim.subject].add(claim.observed_by)
        if claim.predicate == "outcome":
            outcomes[claim.subject].add(claim.object)
    as_of = max([field.as_of, *(row.observed_at + 1 for row in selected)])
    return EndogenousField(
        field_id=field.field_id,
        states=field.states,
        claims=tuple(claims),
        belief_snapshot={owner: tuple(rows) for owner, rows in sorted(belief_rows.items())},
        current_members=field.current_members,
        departed_members=field.departed_members,
        coordinator_id=field.coordinator_id,
        as_of=as_of,
        emitted_claims=len(claims),
        duplicate_observation_groups=sum(len(rows) > 1 for rows in observers.values()),
        conflicting_observation_groups=sum(len(rows) > 1 for rows in outcomes.values()),
        low_confidence_claims=sum(claim.confidence < 0.7 for claim in claims),
    )


def wilson_interval(evidence: CellEvidence | None, z: float) -> tuple[float, float]:
    if evidence is None or evidence.events == 0:
        return 0.0, 1.0
    total = evidence.events
    phat = evidence.successes / total
    z2 = z * z
    denominator = 1.0 + z2 / total
    center = phat + z2 / (2.0 * total)
    radius = z * math.sqrt(
        phat * (1.0 - phat) / total + z2 / (4.0 * total * total)
    )
    return (
        max(0.0, (center - radius) / denominator),
        min(1.0, (center + radius) / denominator),
    )


def next_events(
    table: dict[Cell, tuple[ProbeEvent, ...]],
    selected_ids: set[str],
) -> dict[Cell, ProbeEvent]:
    output: dict[Cell, ProbeEvent] = {}
    for cell, rows in table.items():
        for row in rows:
            if row.event_id not in selected_ids:
                output[cell] = row
                break
    return output


def tie_key(field_id: str, policy: str, cell: Cell) -> bytes:
    payload = f"cg6-acquire|{field_id}|{policy}|{cell[0]}|{cell[1]}".encode()
    return hashlib.sha256(payload).digest()


def selected_role_counts(
    candidates: set[str],
    mission_rows: list[CG4Mission],
    evidence: dict[Cell, CellEvidence],
    spec: EstimatorSpec,
) -> dict[Cell, int]:
    output: dict[Cell, int] = defaultdict(int)
    for mission in mission_rows:
        pair = _select_pair(candidates, mission, evidence, spec)
        if pair is None:
            continue
        lead_cell = (pair[0], mission.lead_skill)
        support_cell = (pair[1], mission.support_skill)
        if evidence.get(lead_cell, CellEvidence(0, 0, ())).events >= spec.min_support:
            output[lead_cell] += 1
        if evidence.get(support_cell, CellEvidence(0, 0, ())).events >= spec.min_support:
            output[support_cell] += 1
    return dict(output)


def plausible_counts(
    candidates: set[str],
    mission_rows: list[CG4Mission],
    evidence: dict[Cell, CellEvidence],
    spec: EstimatorSpec,
    *,
    ambiguity_margin: float,
) -> dict[Cell, int]:
    output: dict[Cell, int] = defaultdict(int)
    for mission in mission_rows:
        for skill in mission.required_skills:
            best = max(
                _score(evidence.get((agent_id, skill)), spec)
                for agent_id in candidates
            )
            for agent_id in candidates:
                cell = (agent_id, skill)
                _lower, upper = wilson_interval(evidence.get(cell), spec.z)
                if upper >= best - ambiguity_margin:
                    output[cell] += 1
    return dict(output)


def choose_cell(
    *,
    policy: str,
    field: EndogenousField,
    claims: list[LiveClaim],
    available: dict[Cell, ProbeEvent],
    mission_rows: list[CG4Mission],
    spec: EstimatorSpec,
    min_confidence: float,
    weights: dict[str, float],
) -> Cell:
    candidates = set(field.current_members)
    evidence = _cell_evidence(
        claims,
        candidates=candidates,
        min_confidence=min_confidence,
    )
    if policy == "uniform_round_robin":
        return min(
            available,
            key=lambda cell: (
                evidence.get(cell, CellEvidence(0, 0, ())).events,
                tie_key(field.field_id, policy, cell),
            ),
        )

    if policy == "uncertainty_only":
        scored: list[tuple[float, bytes, Cell]] = []
        for cell in available:
            row = evidence.get(cell, CellEvidence(0, 0, ()))
            lower, upper = wilson_interval(row, spec.z)
            deficit = max(0, spec.min_support - row.events) / max(1, spec.min_support)
            priority = (upper - lower) + weights["support_deficit_bonus"] * deficit
            scored.append((priority, tie_key(field.field_id, policy, cell), cell))
        return max(scored)[2]

    if policy != "decision_adaptive":
        raise ValueError(f"unknown acquisition policy: {policy}")

    selected = selected_role_counts(candidates, mission_rows, evidence, spec)
    plausible = plausible_counts(
        candidates,
        mission_rows,
        evidence,
        spec,
        ambiguity_margin=weights["ambiguity_margin"],
    )
    scored = []
    for cell in available:
        row = evidence.get(cell, CellEvidence(0, 0, ()))
        lower, upper = wilson_interval(row, spec.z)
        width = upper - lower
        deficit = max(0, spec.min_support - row.events) / max(1, spec.min_support)
        multiplier = (
            1.0
            + weights["selected_role_bonus"] * selected.get(cell, 0)
            + weights["plausible_challenger_bonus"] * plausible.get(cell, 0)
        )
        priority = width * multiplier + weights["support_deficit_bonus"] * deficit
        scored.append((priority, tie_key(field.field_id, policy, cell), cell))
    return max(scored)[2]


def acquire(
    field: EndogenousField,
    *,
    policy: str,
    budget: int | None,
    mission_rows: list[CG4Mission],
    spec: EstimatorSpec,
    min_confidence: float,
    max_events: int,
    noise_rate: float,
    weights: dict[str, float],
) -> tuple[EndogenousField, list[ProbeEvent], dict[str, Any]]:
    table, ordered = supplemental_table(
        field,
        max_events=max_events,
        min_confidence=min_confidence,
        noise_rate=noise_rate,
    )
    if policy == "fixed_six_replay":
        measured = materialize(field, list(ordered))
        return measured, list(ordered), {"selection_sequence": "full-fixed-six-order"}
    if policy == "passive":
        return field, [], {"selection_sequence": []}
    if budget is None:
        raise ValueError("budget is required for adaptive acquisition policies")

    selected: list[ProbeEvent] = []
    selected_ids: set[str] = set()
    claims = list(field.claims)
    sequence: list[dict[str, Any]] = []
    while len(selected) < budget:
        available = next_events(table, selected_ids)
        if not available:
            break
        cell = choose_cell(
            policy=policy,
            field=field,
            claims=claims,
            available=available,
            mission_rows=mission_rows,
            spec=spec,
            min_confidence=min_confidence,
            weights=weights,
        )
        event = available[cell]
        selected.append(event)
        selected_ids.add(event.event_id)
        claims.extend(event.claims)
        sequence.append(
            {
                "step": len(selected),
                "agent_id": cell[0],
                "skill": cell[1],
                "event_index": event.event_index,
            }
        )
    measured = materialize(field, selected)
    return measured, selected, {"selection_sequence": sequence}


def pair_from_context(
    context: tuple[LiveClaim, ...],
    mission: CG4Mission,
    spec: EstimatorSpec,
    min_confidence: float,
) -> tuple[Pair | None, dict[Cell, CellEvidence]]:
    candidates = _membership_candidates(
        context,
        min_confidence=min_confidence,
        respect_temporal_order=True,
    )
    evidence = _cell_evidence(
        context,
        candidates=candidates,
        min_confidence=min_confidence,
    )
    return _select_pair(candidates, mission, evidence, spec), evidence


def role_gap(
    field: EndogenousField,
    mission: CG4Mission,
    pair: Pair | None,
) -> float:
    if pair is None or not set(pair).issubset(field.current_members):
        return 1.0
    environment = JointEnvironment()
    gaps = []
    for agent_id, skill in ((pair[0], mission.lead_skill), (pair[1], mission.support_skill)):
        best = max(
            environment.role_probability(field.states[candidate], skill)
            for candidate in field.current_members
        )
        selected = environment.role_probability(field.states[agent_id], skill)
        gaps.append(best - selected)
    return sum(gaps) / len(gaps)


def evaluate_measured_field(
    field: EndogenousField,
    mission_rows: list[CG4Mission],
    *,
    spec: EstimatorSpec,
    min_confidence: float,
    context_budget: int,
) -> dict[str, Any]:
    graph_expected = 0.0
    flat_expected = 0.0
    oracle_expected = 0.0
    gap = 0.0
    environment = JointEnvironment()
    estimates: list[float] = []
    truths: list[float] = []
    full_evidence = _cell_evidence(
        field.claims,
        candidates=set(field.current_members),
        min_confidence=min_confidence,
    )
    skills = sorted(next(iter(field.states.values())).practice_by_skill)
    for agent_id in sorted(field.current_members):
        for skill in skills:
            estimates.append(_score(full_evidence.get((agent_id, skill)), spec))
            truths.append(environment.role_probability(field.states[agent_id], skill))

    for mission in mission_rows:
        graph = _coverage_graph_context(
            field,
            mission,
            budget=context_budget,
            estimator=spec,
            min_confidence=min_confidence,
        )
        flat = _bundle_flat_context(
            field,
            mission,
            budget=context_budget,
            min_confidence=min_confidence,
        )
        graph_pair, _graph_evidence = pair_from_context(
            graph, mission, spec, min_confidence
        )
        flat_pair, _flat_evidence = pair_from_context(flat, mission, spec, min_confidence)
        oracle = _oracle_pair(field, mission)
        graph_expected += (
            _expected_success(field, mission, graph_pair)
            if graph_pair is not None and set(graph_pair).issubset(field.current_members)
            else 0.0
        )
        flat_expected += (
            _expected_success(field, mission, flat_pair)
            if flat_pair is not None and set(flat_pair).issubset(field.current_members)
            else 0.0
        )
        oracle_expected += _expected_success(field, mission, oracle)
        gap += role_gap(field, mission, graph_pair)

    count = len(mission_rows)
    return {
        "graph_expected_success": graph_expected / count,
        "flat_expected_success": flat_expected / count,
        "oracle_expected_success": oracle_expected / count,
        "graph_regret": (oracle_expected - graph_expected) / count,
        "selected_role_true_gap": gap / count,
        "estimate_truth_pairs": list(zip(estimates, truths, strict=True)),
        "graph_minus_flat": (graph_expected - flat_expected) / count,
    }


def evaluate_policy(
    base_fields: list[EndogenousField],
    *,
    policy: str,
    budget: int | None,
    mission_rows: list[CG4Mission],
    spec: EstimatorSpec,
    min_confidence: float,
    context_budget: int,
    max_events: int,
    noise_rate: float,
    weights: dict[str, float],
    fixed_six_mean_cost: float | None,
    passive_graph_expected: float | None,
) -> tuple[PolicyMetrics, dict[str, Any]]:
    field_rows: dict[str, dict[str, Any]] = {}
    estimate_values: list[float] = []
    truth_values: list[float] = []
    total_events = 0
    sequences: dict[str, Any] = {}
    for base in base_fields:
        measured, events, acquisition_diag = acquire(
            base,
            policy=policy,
            budget=budget,
            mission_rows=mission_rows,
            spec=spec,
            min_confidence=min_confidence,
            max_events=max_events,
            noise_rate=noise_rate,
            weights=weights,
        )
        row = evaluate_measured_field(
            measured,
            mission_rows,
            spec=spec,
            min_confidence=min_confidence,
            context_budget=context_budget,
        )
        field_rows[base.field_id] = {
            key: value for key, value in row.items() if key != "estimate_truth_pairs"
        }
        for estimate_value, truth_value in row["estimate_truth_pairs"]:
            estimate_values.append(float(estimate_value))
            truth_values.append(float(truth_value))
        total_events += len(events)
        sequences[base.field_id] = acquisition_diag["selection_sequence"]

    field_count = len(base_fields)
    decisions = field_count * len(mission_rows)
    mean_cost = total_events / field_count if field_count else 0.0

    def mean(name: str) -> float:
        return (
            sum(float(row[name]) for row in field_rows.values()) / field_count
            if field_count
            else 0.0
        )

    graph_expected = mean("graph_expected_success")
    flat_expected = mean("flat_expected_success")
    cost_fraction = (
        mean_cost / fixed_six_mean_cost
        if fixed_six_mean_cost not in (None, 0.0)
        else 1.0
    )
    gain_per_probe = 0.0
    if passive_graph_expected is not None and mean_cost > 0:
        gain_per_probe = (graph_expected - passive_graph_expected) / mean_cost
    metrics = PolicyMetrics(
        policy=policy,
        budget=budget,
        fields=field_count,
        decisions=decisions,
        mean_graph_expected_success=graph_expected,
        mean_flat_expected_success=flat_expected,
        mean_oracle_expected_success=mean("oracle_expected_success"),
        mean_graph_regret=mean("graph_regret"),
        mean_selected_role_true_gap=mean("selected_role_true_gap"),
        estimate_truth_pearson=_pearson(estimate_values, truth_values),
        mean_supplemental_probe_events=mean_cost,
        total_supplemental_probe_events=total_events,
        probe_cost_fraction_vs_fixed_six=cost_fraction,
        graph_lift_over_cost_matched_flat=graph_expected - flat_expected,
        positive_field_graph_lift_count=sum(
            float(row["graph_minus_flat"]) > 0 for row in field_rows.values()
        ),
        decision_quality_gain_over_passive_per_probe=gain_per_probe,
    )
    return metrics, {"fields": field_rows, "selection_sequences": sequences}


def select_candidate(
    policy_metrics: dict[str, PolicyMetrics],
    config: dict[str, Any],
) -> dict[str, Any]:
    fixed = policy_metrics["fixed_six_replay"]
    rule = config["selection_rule"]
    checks: dict[str, dict[str, bool]] = {}
    selected: str | None = None
    for budget in [int(value) for value in rule["complexity_order"]]:
        name = f"decision_adaptive_{budget}"
        row = policy_metrics[name]
        retention = (
            row.mean_graph_expected_success / fixed.mean_graph_expected_success
            if fixed.mean_graph_expected_success
            else 0.0
        )
        loss = fixed.mean_graph_expected_success - row.mean_graph_expected_success
        role_gap_increase = (
            row.mean_selected_role_true_gap - fixed.mean_selected_role_true_gap
        )
        candidate_checks = {
            "expected_success_retention": retention
            >= float(rule["required_expected_success_retention_vs_fixed_six"]),
            "absolute_expected_success_loss": loss
            <= float(rule["maximum_absolute_expected_success_loss_vs_fixed_six"]),
            "graph_lift_over_cost_matched_flat": row.graph_lift_over_cost_matched_flat
            >= float(rule["minimum_graph_lift_over_cost_matched_flat"]),
            "positive_field_graph_lift_count": row.positive_field_graph_lift_count
            >= int(rule["minimum_positive_field_graph_lift_count"]),
            "selected_role_true_gap_increase": role_gap_increase
            <= float(rule["maximum_selected_role_true_gap_increase_vs_fixed_six"]),
            "probe_cost_fraction": row.probe_cost_fraction_vs_fixed_six
            <= float(rule["maximum_probe_cost_fraction_vs_fixed_six"]),
        }
        checks[name] = candidate_checks
        if selected is None and all(candidate_checks.values()):
            selected = name
    return {
        "selected": selected,
        "checks": checks,
        "selection_passed": selected is not None,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--capsules", type=Path, required=True)
    parser.add_argument("--source-summary", type=Path, required=True)
    parser.add_argument("--cg5-result", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    config = read_json(args.config)
    source_summary = read_json(args.source_summary)
    cg5_result = read_json(args.cg5_result)
    expected_sha = str(config["frozen_predecessor"]["cg5_capsules_sha256"])
    actual_sha = sha256(args.capsules)
    if actual_sha != expected_sha:
        raise AssertionError(f"CG-5 capsule hash mismatch: {actual_sha}")
    if source_summary.get("capsule_sha256") != expected_sha:
        raise AssertionError("source summary capsule hash mismatch")

    mission_rows = missions(config)
    spec = estimator(config)
    society = config["society"]
    min_confidence = float(society["min_confidence"])
    max_events = int(society["maximum_events_per_current_agent_skill"])
    noise_rate = float(society["observer_noise_rate"])
    context_budget = int(config["context"]["claim_budget_cap"])
    weights = {
        key: float(value)
        for key, value in config["acquisition"]["decision_adaptive_weights"].items()
    }
    field_ids = [f"w3-source-seed-{int(seed)}" for seed in source_summary["seeds"]]
    base_fields = [base_field(args.capsules, field_id, config) for field_id in field_ids]

    passive, passive_detail = evaluate_policy(
        base_fields,
        policy="passive",
        budget=0,
        mission_rows=mission_rows,
        spec=spec,
        min_confidence=min_confidence,
        context_budget=context_budget,
        max_events=max_events,
        noise_rate=noise_rate,
        weights=weights,
        fixed_six_mean_cost=None,
        passive_graph_expected=None,
    )
    fixed, fixed_detail = evaluate_policy(
        base_fields,
        policy="fixed_six_replay",
        budget=None,
        mission_rows=mission_rows,
        spec=spec,
        min_confidence=min_confidence,
        context_budget=context_budget,
        max_events=max_events,
        noise_rate=noise_rate,
        weights=weights,
        fixed_six_mean_cost=None,
        passive_graph_expected=passive.mean_graph_expected_success,
    )
    fixed = PolicyMetrics(
        **{
            **asdict(fixed),
            "probe_cost_fraction_vs_fixed_six": 1.0,
        }
    )

    policy_metrics: dict[str, PolicyMetrics] = {
        "passive": passive,
        "fixed_six_replay": fixed,
    }
    policy_details: dict[str, Any] = {
        "passive": passive_detail,
        "fixed_six_replay": fixed_detail,
    }
    for budget in [int(value) for value in config["acquisition"]["budget_candidates"]]:
        for policy in [str(value) for value in config["acquisition"]["policies"]]:
            name = f"{policy}_{budget}"
            row, detail = evaluate_policy(
                base_fields,
                policy=policy,
                budget=budget,
                mission_rows=mission_rows,
                spec=spec,
                min_confidence=min_confidence,
                context_budget=context_budget,
                max_events=max_events,
                noise_rate=noise_rate,
                weights=weights,
                fixed_six_mean_cost=fixed.mean_supplemental_probe_events,
                passive_graph_expected=passive.mean_graph_expected_success,
            )
            policy_metrics[name] = row
            policy_details[name] = detail

    selection = select_candidate(policy_metrics, config)
    cg5_expected = float(
        cg5_result["metrics"]["revised_coverage_graph"]["mean_expected_success"]
    )
    cg5_flat = float(cg5_result["metrics"]["bundle_flat_active"]["mean_expected_success"])
    cg5_events = int(cg5_result["diagnostics"]["supplemental_probe_events"])
    replay = {
        "expected_success_delta_vs_cg5": fixed.mean_graph_expected_success - cg5_expected,
        "flat_expected_success_delta_vs_cg5": fixed.mean_flat_expected_success - cg5_flat,
        "supplemental_event_delta_vs_cg5": fixed.total_supplemental_probe_events - cg5_events,
        "exact_event_count_replay": fixed.total_supplemental_probe_events == cg5_events,
        "expected_success_replay_within_1e_12": abs(
            fixed.mean_graph_expected_success - cg5_expected
        )
        <= 1e-12,
        "flat_replay_within_1e_12": abs(fixed.mean_flat_expected_success - cg5_flat)
        <= 1e-12,
    }

    forbidden = {
        "graph",
        "context_graph",
        "evidence",
        "claims",
        "relationship_state",
        "organization_memory",
    }
    outcome_law_graph_inputs = len(
        forbidden.intersection(inspect.signature(JointEnvironment.evaluate).parameters)
    )
    integrity = {
        **config["integrity"],
        "belief_contamination_from_retrieval": 0,
        "outcome_law_graph_inputs": outcome_law_graph_inputs,
        "capsules_sha256": actual_sha,
        "cg5_fixed_six_replay": replay,
    }
    result = {
        "version": "context-graph-cg6-adaptive-acquisition-calibration-result-v0.1",
        "config_version": config["version"],
        "status": "exploratory-calibration-complete",
        "confirmatory_claim": False,
        "field_ids": field_ids,
        "metrics": {name: asdict(row) for name, row in policy_metrics.items()},
        "selection": selection,
        "integrity": integrity,
        "interpretation_boundary": config["interpretation_boundary"],
        "details": policy_details,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "selection": selection,
        "fixed_six_replay": replay,
        "selected_metrics": (
            None
            if selection["selected"] is None
            else asdict(policy_metrics[str(selection["selected"])])
        ),
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
