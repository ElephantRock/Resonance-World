"""Exploratory post-unblinding failure analysis for CG-4.

This script does not modify the frozen CG-4 configuration or result and does not create
new confirmatory gates. It traces decision-level evidence use and runs diagnostic
variants on already-unblinded calibration and replication societies.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable

from resonance_world.context_graph_w3_endogenous import (
    CG4Mission,
    EndogenousField,
    LiveClaim,
    _compile_flat,
    _compile_graph,
    _compile_local,
    _eligible,
    _estimate_pair,
    _evaluate_pair_trials,
    _expected_success,
    _membership_candidates,
    _observation_bundles,
    _oracle_pair,
    build_endogenous_field,
)

Bundle = tuple[str, str, str, str, float, int, tuple[LiveClaim, ...]]
Pair = tuple[str, str]
Estimator = Callable[[tuple[LiveClaim, ...], CG4Mission], Pair | None]


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


def _build_fields(
    capsules_path: Path,
    field_ids: list[str],
    experiment: dict[str, Any],
) -> list[EndogenousField]:
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
    return list(best.values())


def _compile_repeat_event_graph(
    field: EndogenousField,
    mission: CG4Mission,
    *,
    budget: int,
    min_confidence: float,
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
        respect_temporal_order=True,
    )
    grouped: dict[tuple[str, str], list[Bundle]] = defaultdict(list)
    for bundle in _canonical_event_bundles(eligible, min_confidence=min_confidence):
        _event, _observer, agent_id, skill, *_rest = bundle
        if agent_id in candidates and skill in mission.required_skills:
            grouped[(agent_id, skill)].append(bundle)
    for rows in grouped.values():
        rows.sort(key=lambda item: (-item[4], -item[5], item[0], item[1]))

    keys = [
        (agent_id, skill)
        for skill in mission.required_skills
        for agent_id in sorted(candidates)
        if (agent_id, skill) in grouped
    ]
    used = {claim.source_id for claim in output}
    depth = 0
    while keys:
        added = False
        for key in keys:
            rows = grouped[key]
            if depth >= len(rows):
                continue
            claims = rows[depth][-1]
            new_claims = [claim for claim in claims if claim.source_id not in used]
            if len(output) + len(new_claims) > budget:
                continue
            output.extend(new_claims)
            used.update(claim.source_id for claim in new_claims)
            added = True
        if not added:
            break
        depth += 1

    if len(output) < budget:
        remaining = [claim for claim in eligible if claim.source_id not in used]
        remaining.sort(
            key=lambda claim: hashlib.sha256(
                f"cg4f-repeat-fill|{mission.mission_id}|{claim.source_id}".encode()
            ).digest()
        )
        output.extend(remaining[: budget - len(output)])
    return tuple(output[:budget])


def _estimate_pair_prior(
    context: tuple[LiveClaim, ...],
    mission: CG4Mission,
    *,
    min_confidence: float,
    alpha: float,
    beta: float,
) -> Pair | None:
    candidates = _membership_candidates(
        context,
        min_confidence=min_confidence,
        respect_temporal_order=True,
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
        return (alpha + successes) / (alpha + beta + total)

    best: tuple[float, str, str, str] | None = None
    for lead_id in sorted(candidates):
        for support_id in sorted(candidates):
            if lead_id == support_id:
                continue
            score = estimate(lead_id, mission.lead_skill) * estimate(
                support_id, mission.support_skill
            )
            candidate = (score, f"{lead_id}::{support_id}", lead_id, support_id)
            if best is None or candidate[:2] > best[:2]:
                best = candidate
    return None if best is None else (best[2], best[3])


def _context_stats(
    context: tuple[LiveClaim, ...],
    mission: CG4Mission,
    *,
    min_confidence: float,
) -> dict[str, Any]:
    candidates = _membership_candidates(
        context,
        min_confidence=min_confidence,
        respect_temporal_order=True,
    )
    bundles = _observation_bundles(context, min_confidence=min_confidence)
    complete_sources = {
        claim.source_id for bundle in bundles for claim in bundle[-1]
    }
    live_claims = [
        claim
        for claim in context
        if claim.source_class == "live_probe" and claim.confidence >= min_confidence
    ]
    role_stats: dict[str, dict[str, Any]] = {}
    for agent_id in sorted(candidates):
        for skill in mission.required_skills:
            rows = [
                bundle
                for bundle in bundles
                if bundle[2] == agent_id and bundle[3] == skill
            ]
            success_weight = 0.0
            total_weight = 0.0
            events: set[str] = set()
            outcomes: list[str] = []
            for event_id, _observer, _agent, _skill, confidence, _time, claims in rows:
                events.add(event_id)
                outcome = next(item.object for item in claims if item.predicate == "outcome")
                outcomes.append(outcome)
                total_weight += confidence
                if outcome == "success":
                    success_weight += confidence
            estimate = (
                (1.0 + success_weight) / (2.0 + total_weight)
                if total_weight
                else 0.5
            )
            role_stats[f"{agent_id}|{skill}"] = {
                "bundle_count": len(rows),
                "unique_events": len(events),
                "success_weight": success_weight,
                "total_weight": total_weight,
                "estimate": estimate,
                "outcomes": outcomes,
            }
    required = [
        bundle
        for bundle in bundles
        if bundle[2] in candidates and bundle[3] in mission.required_skills
    ]
    covered = {
        (bundle[2], bundle[3])
        for bundle in required
    }
    return {
        "context_claims": len(context),
        "candidate_count": len(candidates),
        "complete_bundle_count": len(bundles),
        "required_bundle_count": len(required),
        "covered_candidate_skill_cells": len(covered),
        "possible_candidate_skill_cells": len(candidates) * 2,
        "coverage_rate": len(covered) / (len(candidates) * 2) if candidates else 0.0,
        "eligible_live_probe_claims": len(live_claims),
        "orphan_live_probe_claims": sum(
            claim.source_id not in complete_sources for claim in live_claims
        ),
        "role_stats": role_stats,
    }


def _selected_role_evidence(
    stats: dict[str, Any],
    mission: CG4Mission,
    pair: Pair | None,
) -> dict[str, Any] | None:
    if pair is None:
        return None
    role_stats = stats["role_stats"]
    lead = role_stats.get(f"{pair[0]}|{mission.lead_skill}")
    support = role_stats.get(f"{pair[1]}|{mission.support_skill}")
    return {
        "lead": lead,
        "support": support,
        "zero_evidence_roles": sum(
            row is None or int(row["bundle_count"]) == 0 for row in (lead, support)
        ),
    }


def _decision_arm(
    field: EndogenousField,
    mission: CG4Mission,
    context: tuple[LiveClaim, ...],
    *,
    min_confidence: float,
    oracle_pair: Pair,
    oracle_expected: float,
    trials: int,
    estimator: Estimator,
) -> dict[str, Any]:
    pair = estimator(context, mission)
    invalid = pair is None or not set(pair).issubset(field.current_members)
    expected = 0.0 if invalid or pair is None else _expected_success(field, mission, pair)
    successes = _evaluate_pair_trials(field, mission, pair, trials=trials)
    stats = _context_stats(context, mission, min_confidence=min_confidence)
    return {
        "selected_pair": list(pair) if pair is not None else None,
        "invalid": invalid,
        "expected_success": expected,
        "realized_success_rate": successes / trials,
        "regret": oracle_expected - expected,
        "oracle_pair_match": pair == oracle_pair,
        "context": stats,
        "selected_role_evidence": _selected_role_evidence(stats, mission, pair),
    }


def _standard_estimator(min_confidence: float) -> Estimator:
    def estimate(context: tuple[LiveClaim, ...], mission: CG4Mission) -> Pair | None:
        return _estimate_pair(
            context,
            mission,
            min_confidence=min_confidence,
            respect_temporal_order=True,
        )

    return estimate


def _skeptical_estimator(min_confidence: float) -> Estimator:
    def estimate(context: tuple[LiveClaim, ...], mission: CG4Mission) -> Pair | None:
        return _estimate_pair_prior(
            context,
            mission,
            min_confidence=min_confidence,
            alpha=1.0,
            beta=2.0,
        )

    return estimate


def _trace_phase(
    fields: list[EndogenousField],
    missions: list[CG4Mission],
    *,
    budget: int,
    min_confidence: float,
    trials: int,
) -> list[dict[str, Any]]:
    traces: list[dict[str, Any]] = []
    standard = _standard_estimator(min_confidence)
    skeptical = _skeptical_estimator(min_confidence)
    for field in fields:
        for mission in missions:
            oracle_pair = _oracle_pair(field, mission)
            oracle_expected = _expected_success(field, mission, oracle_pair)
            graph = _compile_graph(
                field,
                mission,
                budget=budget,
                min_confidence=min_confidence,
                respect_temporal_order=True,
            )
            repeat_graph = _compile_repeat_event_graph(
                field,
                mission,
                budget=budget,
                min_confidence=min_confidence,
            )
            flat = _compile_flat(
                field,
                mission,
                budget=budget,
                min_confidence=min_confidence,
            )
            local = _compile_local(
                field,
                budget=budget,
                min_confidence=min_confidence,
            )
            full = tuple(_eligible(field.claims, min_confidence))
            arms = {
                "local_only": (local, standard),
                "pooled_flat": (flat, standard),
                "original_graph": (graph, standard),
                "repeat_event_graph": (repeat_graph, standard),
                "skeptical_prior_graph": (graph, skeptical),
                "repeat_event_skeptical": (repeat_graph, skeptical),
                "full_evidence": (full, standard),
                "full_evidence_skeptical": (full, skeptical),
            }
            rows = {
                arm: _decision_arm(
                    field,
                    mission,
                    context,
                    min_confidence=min_confidence,
                    oracle_pair=oracle_pair,
                    oracle_expected=oracle_expected,
                    trials=trials,
                    estimator=estimator,
                )
                for arm, (context, estimator) in arms.items()
            }
            traces.append(
                {
                    "field_id": field.field_id,
                    "mission_id": mission.mission_id,
                    "lead_skill": mission.lead_skill,
                    "support_skill": mission.support_skill,
                    "current_members": sorted(field.current_members),
                    "departed_members": sorted(field.departed_members),
                    "oracle_pair": list(oracle_pair),
                    "oracle_expected_success": oracle_expected,
                    "arms": rows,
                    "graph_minus_flat_expected": (
                        rows["original_graph"]["expected_success"]
                        - rows["pooled_flat"]["expected_success"]
                    ),
                }
            )
    return traces


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _aggregate(traces: list[dict[str, Any]]) -> dict[str, Any]:
    arm_names = list(traces[0]["arms"]) if traces else []
    arms: dict[str, Any] = {}
    for arm in arm_names:
        rows = [trace["arms"][arm] for trace in traces]
        arms[arm] = {
            "mean_expected_success": _mean([float(row["expected_success"]) for row in rows]),
            "mean_realized_success_rate": _mean(
                [float(row["realized_success_rate"]) for row in rows]
            ),
            "mean_regret": _mean([float(row["regret"]) for row in rows]),
            "oracle_pair_rate": _mean([float(row["oracle_pair_match"]) for row in rows]),
            "invalid_selection_rate": _mean([float(row["invalid"]) for row in rows]),
            "mean_complete_bundles": _mean(
                [float(row["context"]["complete_bundle_count"]) for row in rows]
            ),
            "mean_required_bundles": _mean(
                [float(row["context"]["required_bundle_count"]) for row in rows]
            ),
            "mean_coverage_rate": _mean(
                [float(row["context"]["coverage_rate"]) for row in rows]
            ),
            "mean_orphan_live_probe_claims": _mean(
                [float(row["context"]["orphan_live_probe_claims"]) for row in rows]
            ),
            "selected_zero_evidence_roles": sum(
                int(row["selected_role_evidence"]["zero_evidence_roles"])
                if row["selected_role_evidence"] is not None
                else 2
                for row in rows
            ),
        }
    graph_minus_flat = [float(trace["graph_minus_flat_expected"]) for trace in traces]
    return {
        "decision_count": len(traces),
        "arms": arms,
        "graph_vs_flat": {
            "mean_expected_difference": _mean(graph_minus_flat),
            "graph_better_decisions": sum(value > 1e-12 for value in graph_minus_flat),
            "flat_better_decisions": sum(value < -1e-12 for value in graph_minus_flat),
            "ties": sum(abs(value) <= 1e-12 for value in graph_minus_flat),
            "pair_disagreements": sum(
                trace["arms"]["original_graph"]["selected_pair"]
                != trace["arms"]["pooled_flat"]["selected_pair"]
                for trace in traces
            ),
        },
    }


def _budget_sweep(
    fields: list[EndogenousField],
    missions: list[CG4Mission],
    *,
    budgets: list[int],
    min_confidence: float,
) -> list[dict[str, Any]]:
    estimator = _standard_estimator(min_confidence)
    output = []
    for budget in budgets:
        graph_expected: list[float] = []
        flat_expected: list[float] = []
        graph_bundles: list[float] = []
        flat_bundles: list[float] = []
        for field in fields:
            for mission in missions:
                graph = _compile_graph(
                    field,
                    mission,
                    budget=budget,
                    min_confidence=min_confidence,
                    respect_temporal_order=True,
                )
                flat = _compile_flat(
                    field,
                    mission,
                    budget=budget,
                    min_confidence=min_confidence,
                )
                for context, expected_rows, bundle_rows in (
                    (graph, graph_expected, graph_bundles),
                    (flat, flat_expected, flat_bundles),
                ):
                    pair = estimator(context, mission)
                    expected = (
                        0.0
                        if pair is None or not set(pair).issubset(field.current_members)
                        else _expected_success(field, mission, pair)
                    )
                    expected_rows.append(expected)
                    bundle_rows.append(
                        float(
                            _context_stats(
                                context,
                                mission,
                                min_confidence=min_confidence,
                            )["complete_bundle_count"]
                        )
                    )
        output.append(
            {
                "budget": budget,
                "graph_mean_expected_success": _mean(graph_expected),
                "flat_mean_expected_success": _mean(flat_expected),
                "graph_minus_flat": _mean(graph_expected) - _mean(flat_expected),
                "graph_mean_complete_bundles": _mean(graph_bundles),
                "flat_mean_complete_bundles": _mean(flat_bundles),
            }
        )
    return output


def _phase_result(
    fields: list[EndogenousField],
    missions: list[CG4Mission],
    *,
    budget: int,
    budgets: list[int],
    min_confidence: float,
    trials: int,
) -> dict[str, Any]:
    traces = _trace_phase(
        fields,
        missions,
        budget=budget,
        min_confidence=min_confidence,
        trials=trials,
    )
    return {
        "summary": _aggregate(traces),
        "budget_sweep": _budget_sweep(
            fields,
            missions,
            budgets=budgets,
            min_confidence=min_confidence,
        ),
        "decisions": traces,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--analysis-config", type=Path, required=True)
    parser.add_argument("--cg4-config", type=Path, required=True)
    parser.add_argument("--cg4-result", type=Path, required=True)
    parser.add_argument("--calibration-capsules", type=Path, required=True)
    parser.add_argument("--evaluation-capsules", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)

    analysis = _read_json(args.analysis_config)
    config = _read_json(args.cg4_config)
    frozen_result = _read_json(args.cg4_result)
    if frozen_result.get("passed") is not False:
        raise ValueError("CG-4F requires the immutable failed CG-4 result")
    experiment = config["experiment"]
    calibration_hash = _sha256(args.calibration_capsules)
    evaluation_hash = _sha256(args.evaluation_capsules)
    expected_calibration_hash = frozen_result["sources"]["calibration"]["capsules_sha256"]
    expected_evaluation_hash = frozen_result["sources"]["evaluation"]["capsules_sha256"]
    if calibration_hash != expected_calibration_hash:
        raise ValueError("calibration capsule hash mismatch")
    if evaluation_hash != expected_evaluation_hash:
        raise ValueError("evaluation capsule hash mismatch")

    calibration_fields = _build_fields(
        args.calibration_capsules,
        list(config["sources"]["calibration"]["field_ids"]),
        experiment,
    )
    evaluation_fields = _build_fields(
        args.evaluation_capsules,
        list(config["sources"]["evaluation"]["field_ids"]),
        experiment,
    )
    budget = int(experiment["context_budget"])
    min_confidence = float(experiment["min_confidence"])
    trials = int(experiment["evaluation_trials_per_decision"])
    budgets = [int(value) for value in analysis["budget_sweep"]]

    result = {
        "version": "context-graph-cg4f-failure-analysis-result-v0.1",
        "status": "exploratory-post-unblinding",
        "confirmatory_claim": False,
        "analysis_config_version": analysis["version"],
        "source_cg4_version": config["version"],
        "scientific_boundary": analysis["scientific_boundary"],
        "source_integrity": {
            "calibration_capsules_sha256": calibration_hash,
            "evaluation_capsules_sha256": evaluation_hash,
            "cg4_config_sha256": _sha256(args.cg4_config),
            "cg4_result_sha256": _sha256(args.cg4_result),
        },
        "calibration": _phase_result(
            calibration_fields,
            _missions(list(experiment["calibration_missions"])),
            budget=budget,
            budgets=budgets,
            min_confidence=min_confidence,
            trials=trials,
        ),
        "evaluation": _phase_result(
            evaluation_fields,
            _missions(list(experiment["evaluation_missions"])),
            budget=budget,
            budgets=budgets,
            min_confidence=min_confidence,
            trials=trials,
        ),
    }
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if "practice_by_skill" in text:
        raise AssertionError("hidden capsule skill state leaked into CG-4F output")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text, encoding="utf-8")
    print(json.dumps({
        "calibration": result["calibration"]["summary"],
        "evaluation": result["evaluation"]["summary"],
        "evaluation_budget_sweep": result["evaluation"]["budget_sweep"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
