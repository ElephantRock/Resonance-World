"""Deterministic W2 individual ecological recruitment laboratory."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
from pathlib import Path
from typing import Any


def _read_json(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain an object")
    return value


def _read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"{path} contains a non-object row")
            rows.append(value)
    return rows


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _sha256(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def _uniform(*parts: object) -> float:
    payload = "|".join(str(part) for part in parts).encode()
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big") / 2**64


def _key(row: dict[str, Any]) -> tuple[str, str]:
    return str(row["field_id"]), str(row["agent_id"])


def _index(
    candidates: list[dict[str, Any]], capsules: list[dict[str, Any]]
) -> dict[tuple[str, str], dict[str, Any]]:
    private = {_key(row): row for row in capsules}
    if len(private) != len(capsules):
        raise ValueError("duplicate capsule identity")
    if {_key(row) for row in candidates} != set(private):
        raise ValueError("candidate/capsule identities do not match")
    for candidate in candidates:
        if "practice_by_skill" in json.dumps(candidate, sort_keys=True):
            raise ValueError("private practice leaked into public W2 candidate")
    return private


def _fields(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(str(row["field_id"]), []).append(row)
    for field_rows in grouped.values():
        field_rows.sort(key=lambda item: str(item["agent_id"]))
    return grouped


def _filter_fields(rows: list[dict[str, Any]], allowed: list[str]) -> list[dict[str, Any]]:
    wanted = set(allowed)
    result = [row for row in rows if str(row["field_id"]) in wanted]
    found = {str(row["field_id"]) for row in result}
    if found != wanted:
        raise ValueError(f"missing expected fields: {sorted(wanted - found)}")
    return result


def _requirements(mission: dict[str, Any]) -> dict[str, float]:
    values = {str(key): float(value) for key, value in mission["requirements"].items()}
    if sum(values.values()) <= 0:
        raise ValueError("mission requirements must have positive total weight")
    return values


def _probability(
    practice: dict[str, float], requirements: dict[str, float], law: dict[str, Any]
) -> float:
    total = sum(requirements.values())
    signal = sum(
        (weight / total) * math.sqrt(max(0.0, practice.get(skill, 0.0)))
        for skill, weight in requirements.items()
    )
    return min(
        float(law["maximum_success_probability"]),
        float(law["base_success_probability"]) + float(law["practice_gain"]) * signal,
    )


def _sample(
    practice: dict[str, float],
    mission: dict[str, Any],
    law: dict[str, Any],
    *,
    trials: int,
    identity: str,
    salt: str,
) -> dict[str, float]:
    probability = _probability(practice, _requirements(mission), law)
    successes = sum(
        _uniform("resonance-world-w2", salt, identity, mission["mission"], trial) < probability
        for trial in range(trials)
    )
    return {
        "expected_success": probability,
        "sampled_success": successes / trials,
    }


def _general_score(candidate: dict[str, Any]) -> float:
    features = candidate["public_features"]
    experience = min(1.0, float(features["completed_tasks"]) / 12.0)
    return (
        0.35 * float(features["home_success_rate"])
        + 0.20 * float(features["bid_win_rate"])
        + 0.15 * float(features["mean_bid_confidence"])
        + 0.10 * float(features["skill_concentration"])
        + 0.10 * (1.0 - float(features["skill_entropy"]))
        + 0.10 * experience
    )


def _mission_fit(
    candidate: dict[str, Any], requirements: dict[str, float], config: dict[str, Any]
) -> float:
    profile = candidate["public_mission_profile"]
    dominant = profile.get("dominant_success_skill")
    secondary = profile.get("secondary_success_skill")
    dominant_weight = float(config["recruiter"]["dominant_fit_weight"])
    secondary_weight = float(config["recruiter"]["secondary_fit_weight"])
    return (
        dominant_weight * float(requirements.get(str(dominant), 0.0))
        + secondary_weight * float(requirements.get(str(secondary), 0.0))
    )


def _recruiter_score(
    candidate: dict[str, Any], mission: dict[str, Any], config: dict[str, Any], alpha: float
) -> float:
    return _general_score(candidate) + alpha * _mission_fit(
        candidate, _requirements(mission), config
    )


def _practice(capsule: dict[str, Any]) -> dict[str, float]:
    return {
        str(skill): float(value)
        for skill, value in dict(capsule["practice_by_skill"]).items()
    }


def _target_practice(requirements: dict[str, float], budget: float) -> dict[str, float]:
    total = sum(requirements.values())
    return {skill: budget * weight / total for skill, weight in requirements.items()}


def _utility(
    success: float, *, response_practice: float, config: dict[str, Any]
) -> float:
    utility = config["utility"]
    purpose = config["purpose_built"]
    deployment = float(purpose["deployment_compute_cost"])
    response_cost = response_practice * float(purpose["response_compute_cost_per_practice"])
    return (
        float(utility["success_weight"]) * success
        - float(utility["response_compute_weight"]) * (deployment + response_cost)
        - float(utility["latency_weight"]) * response_practice
    )


def _select(
    rows: list[dict[str, Any]],
    mission: dict[str, Any],
    config: dict[str, Any],
    recruiter: dict[str, Any],
) -> tuple[dict[str, Any], float]:
    alpha = float(recruiter["alpha"])
    ranked = sorted(
        rows,
        key=lambda row: (
            _recruiter_score(row, mission, config, alpha),
            str(row["agent_id"]),
        ),
        reverse=True,
    )
    selected = ranked[0]
    return selected, _recruiter_score(selected, mission, config, alpha)


def _mission_rows(config: dict[str, Any], family: str) -> list[dict[str, Any]]:
    rows = config["families"].get(family)
    if not isinstance(rows, list) or not rows:
        raise ValueError(f"missing mission family: {family}")
    return rows


def calibrate(
    candidates_path: str | Path,
    capsules_path: str | Path,
    missions_path: str | Path,
    destination: str | Path,
) -> dict[str, Any]:
    """Execute W2-01 and freeze the mission-conditioned recruiter."""

    candidates = _read_jsonl(candidates_path)
    capsules = _read_jsonl(capsules_path)
    config = _read_json(missions_path)
    private = _index(candidates, capsules)
    training = _filter_fields(candidates, list(config["training_fields"]))
    missions = _mission_rows(config, "calibration")
    trials = int(config["trials_per_mission"])

    alpha_results: list[dict[str, float]] = []
    for alpha_raw in config["recruiter"]["alpha_grid"]:
        alpha = float(alpha_raw)
        selected_success: list[float] = []
        for field_id, rows in sorted(_fields(training).items()):
            for mission in missions:
                recruiter = {"alpha": alpha}
                selected, _score = _select(rows, mission, config, recruiter)
                result = _sample(
                    _practice(private[_key(selected)]),
                    mission,
                    config["destination_law"],
                    trials=trials,
                    identity=f"{field_id}:{selected['agent_id']}",
                    salt=f"w2-01:{alpha}",
                )
                selected_success.append(result["sampled_success"])
        alpha_results.append(
            {"alpha": alpha, "selected_mean_success": statistics.mean(selected_success)}
        )

    best = max(alpha_results, key=lambda row: (row["selected_mean_success"], -row["alpha"]))
    alpha = float(best["alpha"])
    calibration_scores: list[float] = []
    for _field_id, rows in sorted(_fields(training).items()):
        for mission in missions:
            _selected, score = _select(rows, mission, config, {"alpha": alpha})
            calibration_scores.append(score)
    general_ceiling = max(_general_score(row) for row in training)
    supported_floor = min(calibration_scores)
    threshold = (
        (general_ceiling + supported_floor) / 2.0
        if supported_floor > general_ceiling
        else supported_floor * 0.95
    )
    recruiter = {
        "alpha": alpha,
        "calibration_agent_count": len(training),
        "calibration_fields": list(config["training_fields"]),
        "calibration_missions": [mission["mission"] for mission in missions],
        "frozen_before_discovery": True,
        "public_profile_only": True,
        "abstention_threshold": threshold,
        "alpha_grid_results": alpha_results,
    }
    recruiter["recruiter_sha256"] = _sha256(recruiter)
    destination = Path(destination)
    _write_json(destination / "w2-01-frozen-recruiter.json", recruiter)
    summary = {
        "alpha": alpha,
        "abstention_threshold": threshold,
        "recruiter_sha256": recruiter["recruiter_sha256"],
    }
    _write_json(destination / "w2-01-summary.json", summary)
    return summary


def _compare_discovery(
    rows: list[dict[str, Any]],
    private: dict[tuple[str, str], dict[str, Any]],
    missions: list[dict[str, Any]],
    config: dict[str, Any],
    recruiter: dict[str, Any],
    *,
    salt: str,
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    trials = int(config["trials_per_mission"])
    response_budget = float(config["purpose_built"]["response_practice_budget"])
    for field_id, field_rows in sorted(_fields(rows).items()):
        for mission in missions:
            selected, score = _select(field_rows, mission, config, recruiter)
            capsule = private[_key(selected)]
            requirements = _requirements(mission)
            recruited = _sample(
                _practice(capsule),
                mission,
                config["destination_law"],
                trials=trials,
                identity=f"recruited:{field_id}:{selected['agent_id']}",
                salt=salt,
            )
            fresh = _sample(
                {},
                mission,
                config["destination_law"],
                trials=trials,
                identity=f"fresh:{field_id}",
                salt=salt,
            )
            purpose_practice = _target_practice(requirements, response_budget)
            purpose = _sample(
                purpose_practice,
                mission,
                config["destination_law"],
                trials=trials,
                identity=f"purpose:{field_id}",
                salt=salt,
            )
            accumulated = sum(_practice(capsule).values())
            upper = _sample(
                _target_practice(requirements, accumulated),
                mission,
                config["destination_law"],
                trials=trials,
                identity=f"upper:{field_id}",
                salt=salt,
            )
            output.append(
                {
                    "field_id": field_id,
                    "mission": mission["mission"],
                    "recruited_agent_id": selected["agent_id"],
                    "recruiter_score": score,
                    "recruited_success": recruited["sampled_success"],
                    "fresh_success": fresh["sampled_success"],
                    "purpose_success": purpose["sampled_success"],
                    "upper_bound_success": upper["sampled_success"],
                    "recruited_utility": _utility(
                        recruited["sampled_success"], response_practice=0.0, config=config
                    ),
                    "fresh_utility": _utility(
                        fresh["sampled_success"], response_practice=0.0, config=config
                    ),
                    "purpose_utility": _utility(
                        purpose["sampled_success"],
                        response_practice=response_budget,
                        config=config,
                    ),
                    "upper_bound_utility": _utility(
                        upper["sampled_success"],
                        response_practice=accumulated,
                        config=config,
                    ),
                    "recruited_lifecycle_practice": accumulated,
                    "purpose_response_practice": response_budget,
                }
            )
    return output


def _field_lifts(rows: list[dict[str, Any]], baseline: str) -> dict[str, float]:
    values: dict[str, list[float]] = {}
    for row in rows:
        values.setdefault(str(row["field_id"]), []).append(
            float(row["recruited_success"]) - float(row[baseline])
        )
    return {field: statistics.mean(items) for field, items in values.items()}


def discover(
    candidates_path: str | Path,
    capsules_path: str | Path,
    missions_path: str | Path,
    campaign_path: str | Path,
    recruiter_path: str | Path,
    destination: str | Path,
) -> dict[str, Any]:
    """Execute W2-02 through W2-06 on held-out discovery Fields."""

    candidates = _read_jsonl(candidates_path)
    capsules = _read_jsonl(capsules_path)
    config = _read_json(missions_path)
    campaign = _read_json(campaign_path)
    recruiter = _read_json(recruiter_path)
    if not recruiter.get("frozen_before_discovery"):
        raise ValueError("recruiter was not frozen before discovery")
    private = _index(candidates, capsules)
    holdout = _filter_fields(candidates, list(config["discovery_holdout_fields"]))
    discovery_rows = _compare_discovery(
        holdout,
        private,
        _mission_rows(config, "discovery"),
        config,
        recruiter,
        salt="w2-discovery",
    )

    fresh_lifts = _field_lifts(discovery_rows, "fresh_success")
    purpose_lifts = _field_lifts(discovery_rows, "purpose_success")
    gates = campaign["decision_gates"]
    w202_lift = statistics.mean(fresh_lifts.values())
    w202_pass = (
        w202_lift >= float(gates["w2_02_min_completion_lift"])
        and sum(value > 0 for value in fresh_lifts.values())
        >= int(gates["w2_02_min_positive_fields"])
    )
    recruited_mean = statistics.mean(float(row["recruited_success"]) for row in discovery_rows)
    purpose_mean = statistics.mean(float(row["purpose_success"]) for row in discovery_rows)
    utility_delta = statistics.mean(
        float(row["recruited_utility"]) - float(row["purpose_utility"])
        for row in discovery_rows
    )
    w203_pass = (
        recruited_mean + float(gates["w2_03_noninferiority_margin"]) >= purpose_mean
        and utility_delta >= float(gates["w2_03_min_utility_delta"])
    )
    upper_delta = statistics.mean(
        float(row["upper_bound_success"]) - float(row["recruited_success"])
        for row in discovery_rows
    )

    abstention_rows: list[dict[str, Any]] = []
    threshold = float(recruiter["abstention_threshold"])
    trials = int(config["trials_per_mission"])
    for field_id, field_rows in sorted(_fields(holdout).items()):
        for mission in _mission_rows(config, "abstention"):
            selected, score = _select(field_rows, mission, config, recruiter)
            result = _sample(
                _practice(private[_key(selected)]),
                mission,
                config["destination_law"],
                trials=trials,
                identity=f"abstention:{field_id}:{selected['agent_id']}",
                salt="w2-05",
            )
            abstention_rows.append(
                {
                    "accepted": score >= threshold,
                    "field_id": field_id,
                    "mission": mission["mission"],
                    "recruiter_score": score,
                    "success": result["sampled_success"],
                    "supported": bool(mission.get("supported", True)),
                }
            )
    accepted = [row for row in abstention_rows if row["accepted"]]
    always_risk = statistics.mean(1.0 - float(row["success"]) for row in abstention_rows)
    selective_risk = (
        statistics.mean(1.0 - float(row["success"]) for row in accepted)
        if accepted
        else 1.0
    )
    supported = [row for row in abstention_rows if row["supported"]]
    supported_coverage = sum(bool(row["accepted"]) for row in supported) / len(supported)
    risk_reduction = always_risk - selective_risk
    w205_pass = (
        risk_reduction >= float(gates["w2_05_min_selective_risk_reduction"])
        and supported_coverage >= float(gates["w2_05_min_supported_coverage"])
    )

    drift_rows: list[dict[str, Any]] = []
    drift_missions = _mission_rows(config, "drift")
    for field_id, field_rows in sorted(_fields(holdout).items()):
        selected, _score = _select(field_rows, drift_missions[0], config, recruiter)
        practice = _practice(private[_key(selected)])
        phase_results = [
            _sample(
                practice,
                mission,
                config["destination_law"],
                trials=trials,
                identity=f"drift:{field_id}:{selected['agent_id']}",
                salt="w2-06",
            )["sampled_success"]
            for mission in drift_missions
        ]
        drift_rows.append(
            {
                "field_id": field_id,
                "recruited_agent_id": selected["agent_id"],
                "phase_success": phase_results,
                "final_minus_initial": phase_results[-1] - phase_results[0],
            }
        )

    summary = {
        "recruiter_sha256": recruiter["recruiter_sha256"],
        "w2_02": {
            "completion_lift": w202_lift,
            "field_lifts": fresh_lifts,
            "passed": w202_pass,
        },
        "w2_03": {
            "noninferiority_margin": float(gates["w2_03_noninferiority_margin"]),
            "passed": w203_pass,
            "purpose_mean_success": purpose_mean,
            "recruited_mean_success": recruited_mean,
            "utility_delta": utility_delta,
            "field_lifts": purpose_lifts,
        },
        "w2_04": {"upper_bound_minus_recruited_success": upper_delta},
        "w2_05": {
            "always_recruit_risk": always_risk,
            "passed": w205_pass,
            "risk_reduction": risk_reduction,
            "selective_risk": selective_risk,
            "supported_coverage": supported_coverage,
            "unsupported_false_recruitments": sum(
                row["accepted"] and not row["supported"] for row in abstention_rows
            ),
        },
        "w2_06": {
            "mean_final_minus_initial": statistics.mean(
                float(row["final_minus_initial"]) for row in drift_rows
            )
        },
        "discovery_passed": bool(w202_pass and w203_pass and w205_pass),
    }
    destination = Path(destination)
    _write_json(destination / "w2-discovery-summary.json", summary)
    _write_json(destination / "w2-02-04-comparisons.json", discovery_rows)
    _write_json(destination / "w2-05-abstention.json", abstention_rows)
    _write_json(destination / "w2-06-drift.json", drift_rows)
    return summary


def replicate(
    candidates_path: str | Path,
    capsules_path: str | Path,
    missions_path: str | Path,
    campaign_path: str | Path,
    recruiter_path: str | Path,
    destination: str | Path,
) -> dict[str, Any]:
    """Execute W2-07 on unseen Fields and an unseen higher-order mission family."""

    candidates = _read_jsonl(candidates_path)
    capsules = _read_jsonl(capsules_path)
    config = _read_json(missions_path)
    campaign = _read_json(campaign_path)
    recruiter = _read_json(recruiter_path)
    private = _index(candidates, capsules)
    replication = _filter_fields(candidates, list(config["replication_fields"]))
    rows = _compare_discovery(
        replication,
        private,
        _mission_rows(config, "replication"),
        config,
        recruiter,
        salt="w2-07",
    )
    threshold = float(recruiter["abstention_threshold"])
    accepted = [row for row in rows if float(row["recruiter_score"]) >= threshold]
    coverage = len(accepted) / len(rows)
    evaluated = accepted if accepted else rows
    fresh_lifts = _field_lifts(evaluated, "fresh_success")
    recruited_mean = statistics.mean(float(row["recruited_success"]) for row in evaluated)
    purpose_mean = statistics.mean(float(row["purpose_success"]) for row in evaluated)
    completion_lift = statistics.mean(fresh_lifts.values())
    gates = campaign["decision_gates"]
    noninferior = recruited_mean + float(gates["w2_07_noninferiority_margin"]) >= purpose_mean
    passed = (
        completion_lift >= float(gates["w2_07_min_completion_lift"])
        and noninferior
        and sum(value > 0 for value in fresh_lifts.values())
        >= int(gates["w2_07_min_positive_fields"])
        and coverage >= float(gates["w2_07_min_coverage"])
    )
    summary = {
        "completion_lift": completion_lift,
        "coverage": coverage,
        "field_lifts": fresh_lifts,
        "noninferior_to_purpose_built": noninferior,
        "passed": passed,
        "purpose_mean_success": purpose_mean,
        "recruited_mean_success": recruited_mean,
        "recruiter_sha256": recruiter["recruiter_sha256"],
    }
    destination = Path(destination)
    _write_json(destination / "w2-07-summary.json", summary)
    _write_json(destination / "w2-07-comparisons.json", rows)
    return summary


def synthesize(
    discovery_path: str | Path,
    replication_path: str | Path,
    destination: str | Path,
) -> dict[str, Any]:
    discovery = _read_json(discovery_path)
    replication = _read_json(replication_path)
    status = (
        "replicated_individual_ecological_recruitment"
        if discovery["discovery_passed"] and replication["passed"]
        else "individual_recruitment_not_replicated"
    )
    summary = {
        "status": status,
        "discovery": discovery,
        "replication": replication,
    }
    destination = Path(destination)
    _write_json(destination / "w2-summary.json", summary)
    lines = [
        "# W2 Individual Recruitment — Synthesis",
        "",
        f"Status: **{status}**",
        "",
        f"- W2-02 recruited-vs-fresh lift: **{discovery['w2_02']['completion_lift']:.4%}**",
        f"- W2-03 discovery pass: **{discovery['w2_03']['passed']}**",
        f"- W2-05 abstention pass: **{discovery['w2_05']['passed']}**",
        f"- W2-07 replication lift: **{replication['completion_lift']:.4%}**",
        f"- W2-07 coverage: **{replication['coverage']:.2%}**",
        f"- W2-07 pass: **{replication['passed']}**",
        "",
        "Interpretation is bounded to the deterministic skill-practice Field model.",
    ]
    (destination / "w2-summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    calibration = sub.add_parser("calibrate")
    calibration.add_argument("candidates")
    calibration.add_argument("capsules")
    calibration.add_argument("missions")
    calibration.add_argument("output")

    discovery = sub.add_parser("discover")
    discovery.add_argument("candidates")
    discovery.add_argument("capsules")
    discovery.add_argument("missions")
    discovery.add_argument("campaign")
    discovery.add_argument("recruiter")
    discovery.add_argument("output")

    replication = sub.add_parser("replicate")
    replication.add_argument("candidates")
    replication.add_argument("capsules")
    replication.add_argument("missions")
    replication.add_argument("campaign")
    replication.add_argument("recruiter")
    replication.add_argument("output")

    synthesis = sub.add_parser("synthesize")
    synthesis.add_argument("discovery")
    synthesis.add_argument("replication")
    synthesis.add_argument("output")

    args = parser.parse_args(argv)
    if args.command == "calibrate":
        result = calibrate(args.candidates, args.capsules, args.missions, args.output)
    elif args.command == "discover":
        result = discover(
            args.candidates,
            args.capsules,
            args.missions,
            args.campaign,
            args.recruiter,
            args.output,
        )
    elif args.command == "replicate":
        result = replicate(
            args.candidates,
            args.capsules,
            args.missions,
            args.campaign,
            args.recruiter,
            args.output,
        )
    else:
        result = synthesize(args.discovery, args.replication, args.output)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
