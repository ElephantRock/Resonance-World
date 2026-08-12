"""Evaluator-only aggregate signal diagnostics for exploratory CG-4F.

The script reads already-unblinded private capsule state only to quantify aggregate
alignment between live-evidence estimates and the unchanged W4 role-probability law.
It never emits individual practice values or per-agent hidden capability records.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

from resonance_world.w4a_joint_learning import IndividualState, JointEnvironment


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _pearson(first: list[float], second: list[float]) -> float:
    if len(first) != len(second) or not first:
        return 0.0
    mean_first = _mean(first)
    mean_second = _mean(second)
    numerator = sum(
        (left - mean_first) * (right - mean_second)
        for left, right in zip(first, second, strict=True)
    )
    left_scale = math.sqrt(sum((value - mean_first) ** 2 for value in first))
    right_scale = math.sqrt(sum((value - mean_second) ** 2 for value in second))
    if left_scale == 0.0 or right_scale == 0.0:
        return 0.0
    return numerator / (left_scale * right_scale)


def _states(capsules_path: Path) -> dict[tuple[str, str], IndividualState]:
    states: dict[tuple[str, str], IndividualState] = {}
    for row in _read_jsonl(capsules_path):
        field_id = str(row["field_id"])
        agent_id = str(row["agent_id"])
        states[(field_id, agent_id)] = IndividualState(
            agent_id=agent_id,
            practice_by_skill={
                str(skill): int(value)
                for skill, value in dict(row["practice_by_skill"]).items()
            },
        )
    return states


def _arm_signal(
    decisions: list[dict[str, Any]],
    states: dict[tuple[str, str], IndividualState],
    arm: str,
) -> dict[str, Any]:
    environment = JointEnvironment()
    estimates: list[float] = []
    truths: list[float] = []
    observed_estimates: list[float] = []
    observed_truths: list[float] = []
    selected_estimates: list[float] = []
    selected_truths: list[float] = []
    best_truths: list[float] = []
    selected_single_success = 0
    selected_roles = 0
    selected_zero_evidence = 0
    selected_bundle_counts: list[int] = []
    selected_unique_events: list[int] = []

    for decision in decisions:
        field_id = str(decision["field_id"])
        lead_skill = str(decision["lead_skill"])
        support_skill = str(decision["support_skill"])
        current = [str(value) for value in decision["current_members"]]
        row = decision["arms"][arm]
        role_stats = row["context"]["role_stats"]
        pair = row["selected_pair"]

        for agent_id in current:
            for skill in (lead_skill, support_skill):
                key = f"{agent_id}|{skill}"
                stat = role_stats[key]
                estimate = float(stat["estimate"])
                truth = environment.role_probability(states[(field_id, agent_id)], skill)
                estimates.append(estimate)
                truths.append(truth)
                if int(stat["bundle_count"]) > 0:
                    observed_estimates.append(estimate)
                    observed_truths.append(truth)

        if pair is None:
            selected_zero_evidence += 2
            continue
        for agent_id, skill in ((str(pair[0]), lead_skill), (str(pair[1]), support_skill)):
            stat = role_stats[f"{agent_id}|{skill}"]
            bundle_count = int(stat["bundle_count"])
            unique_events = int(stat["unique_events"])
            estimate = float(stat["estimate"])
            truth = environment.role_probability(states[(field_id, agent_id)], skill)
            best_truth = max(
                environment.role_probability(states[(field_id, candidate)], skill)
                for candidate in current
            )
            selected_roles += 1
            selected_bundle_counts.append(bundle_count)
            selected_unique_events.append(unique_events)
            selected_estimates.append(estimate)
            selected_truths.append(truth)
            best_truths.append(best_truth)
            if bundle_count == 0:
                selected_zero_evidence += 1
            outcomes = list(stat["outcomes"])
            if bundle_count == 1 and unique_events == 1 and outcomes == ["success"]:
                selected_single_success += 1

    return {
        "candidate_skill_cells": len(estimates),
        "observed_candidate_skill_cells": len(observed_estimates),
        "estimate_truth_pearson_all_cells": _pearson(estimates, truths),
        "estimate_truth_pearson_observed_cells": _pearson(
            observed_estimates, observed_truths
        ),
        "selected_roles": selected_roles,
        "selected_zero_evidence_roles": selected_zero_evidence,
        "selected_single_success_roles": selected_single_success,
        "selected_single_success_rate": (
            selected_single_success / selected_roles if selected_roles else 0.0
        ),
        "selected_role_mean_estimate": _mean(selected_estimates),
        "selected_role_mean_true_probability": _mean(selected_truths),
        "best_available_role_mean_true_probability": _mean(best_truths),
        "selected_role_mean_true_gap": _mean(
            [
                best - selected
                for best, selected in zip(best_truths, selected_truths, strict=True)
            ]
        ),
        "selected_role_mean_bundle_count": _mean(
            [float(value) for value in selected_bundle_counts]
        ),
        "selected_role_mean_unique_events": _mean(
            [float(value) for value in selected_unique_events]
        ),
    }


def _phase(
    phase: dict[str, Any],
    states: dict[tuple[str, str], IndividualState],
) -> dict[str, Any]:
    decisions = list(phase["decisions"])
    summary = phase["summary"]["arms"]
    return {
        "original_graph": _arm_signal(decisions, states, "original_graph"),
        "full_evidence": _arm_signal(decisions, states, "full_evidence"),
        "pooled_flat_complete_bundle_mean": summary["pooled_flat"]["mean_complete_bundles"],
        "pooled_flat_selected_zero_evidence_roles": summary["pooled_flat"][
            "selected_zero_evidence_roles"
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--analysis-result", type=Path, required=True)
    parser.add_argument("--calibration-capsules", type=Path, required=True)
    parser.add_argument("--evaluation-capsules", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)

    analysis = _read_json(args.analysis_result)
    if analysis.get("status") != "exploratory-post-unblinding":
        raise ValueError("signal diagnostics require exploratory CG-4F output")
    calibration_states = _states(args.calibration_capsules)
    evaluation_states = _states(args.evaluation_capsules)
    result = {
        "version": "context-graph-cg4f-signal-diagnostics-v0.1",
        "status": "exploratory-post-unblinding-evaluator-only",
        "confirmatory_claim": False,
        "calibration": _phase(analysis["calibration"], calibration_states),
        "evaluation": _phase(analysis["evaluation"], evaluation_states),
        "interpretation_boundary": (
            "Private capsule practice is used only to compute aggregate evaluator diagnostics "
            "against the unchanged JointEnvironment role-probability law. No individual hidden "
            "practice values or per-agent evaluator capability records are emitted."
        ),
    }
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if "practice_by_skill" in text:
        raise AssertionError("hidden practice values leaked into aggregate diagnostics")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text, encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
