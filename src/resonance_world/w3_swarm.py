"""Deterministic W3 two-agent swarm recruitment laboratory."""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path
from typing import Any

from .w3_swarm_core import (
    _field_deltas,
    _fields,
    _filter_fields,
    _index_private,
    _mean_delta,
    _mission_rows,
    _read_json,
    _read_jsonl,
    _select_pair,
    _sha256,
    _write_json,
)
from .w3_swarm_evaluation import _discover_rows, _evaluate_pair, _resilience


def calibrate(
    candidates_path: str | Path,
    capsules_path: str | Path,
    pair_edges_path: str | Path,
    pair_state_path: str | Path,
    missions_path: str | Path,
    destination: str | Path,
) -> dict[str, Any]:
    """Execute W3-01 and freeze the relationship-aware swarm recruiter."""

    candidates = _read_jsonl(candidates_path)
    capsules = _read_jsonl(capsules_path)
    pair_edges = _read_jsonl(pair_edges_path)
    pair_state = _read_jsonl(pair_state_path)
    config = _read_json(missions_path)
    private_agents, public_pairs, private_pairs = _index_private(
        candidates, capsules, pair_edges, pair_state
    )
    training = _filter_fields(candidates, list(config["training_fields"]))
    missions = _mission_rows(config, "calibration")

    beta_results: list[dict[str, float]] = []
    for beta_raw in config["recruiter"]["beta_grid"]:
        beta = float(beta_raw)
        successes: list[float] = []
        for _field_id, field_rows in sorted(_fields(training).items()):
            for mission in missions:
                first, second, _score = _select_pair(
                    field_rows, public_pairs, mission, config, beta
                )
                successes.append(
                    _evaluate_pair(
                        first,
                        second,
                        mission,
                        private_agents,
                        private_pairs,
                        config,
                        salt="w3-01",
                    )
                )
        beta_results.append(
            {"beta": beta, "selected_mean_success": statistics.mean(successes)}
        )
    best = max(beta_results, key=lambda row: (row["selected_mean_success"], -row["beta"]))
    recruiter = {
        "beta": float(best["beta"]),
        "beta_grid_results": beta_results,
        "calibration_fields": list(config["training_fields"]),
        "calibration_missions": [mission["mission"] for mission in missions],
        "frozen_before_discovery": True,
        "public_pair_evidence_only": True,
    }
    recruiter["recruiter_sha256"] = _sha256(recruiter)
    destination = Path(destination)
    _write_json(destination / "w3-01-frozen-swarm-recruiter.json", recruiter)
    summary = {
        "beta": recruiter["beta"],
        "recruiter_sha256": recruiter["recruiter_sha256"],
    }
    _write_json(destination / "w3-01-summary.json", summary)
    return summary


def discover(
    candidates_path: str | Path,
    capsules_path: str | Path,
    pair_edges_path: str | Path,
    pair_state_path: str | Path,
    missions_path: str | Path,
    campaign_path: str | Path,
    recruiter_path: str | Path,
    destination: str | Path,
) -> dict[str, Any]:
    """Execute W3-02 through W3-06 on held-out discovery Fields."""

    candidates = _read_jsonl(candidates_path)
    capsules = _read_jsonl(capsules_path)
    pair_edges = _read_jsonl(pair_edges_path)
    pair_state = _read_jsonl(pair_state_path)
    config = _read_json(missions_path)
    campaign = _read_json(campaign_path)
    recruiter = _read_json(recruiter_path)
    if not recruiter.get("frozen_before_discovery"):
        raise ValueError("swarm recruiter was not frozen before discovery")
    private_agents, public_pairs, private_pairs = _index_private(
        candidates, capsules, pair_edges, pair_state
    )
    holdout = _filter_fields(candidates, list(config["discovery_holdout_fields"]))
    rows = _discover_rows(
        holdout,
        private_agents,
        public_pairs,
        private_pairs,
        _mission_rows(config, "discovery"),
        config,
        recruiter,
        salt="w3-discovery",
    )
    w3_02 = _mean_delta(rows, "swarm_success", "individual_success")
    w3_03 = _mean_delta(rows, "swarm_success", "assembled_success")
    w3_04 = _mean_delta(rows, "swarm_success", "shuffled_success")
    w3_05 = _mean_delta(rows, "oracle_success", "swarm_success")
    resilience = _resilience(
        rows,
        holdout,
        private_agents,
        public_pairs,
        private_pairs,
        config,
        recruiter,
    )
    thresholds = campaign["thresholds"]
    summary = {
        "recruiter_sha256": recruiter["recruiter_sha256"],
        "w3_02_field_lifts": _field_deltas(rows, "individual_success"),
        "w3_02_swarm_vs_individual_lift": w3_02,
        "w3_02_gate": w3_02 >= float(thresholds["minimum_swarm_vs_individual_lift"]),
        "w3_03_swarm_vs_assembled_lift": w3_03,
        "w3_03_gate": w3_03 >= float(thresholds["minimum_relationship_capital"]),
        "w3_04_swarm_vs_shuffled_lift": w3_04,
        "w3_04_gate": w3_04 >= float(thresholds["minimum_shuffle_ablation_lift"]),
        "w3_05_oracle_advantage": w3_05,
        "w3_06": resilience,
        "w3_06_gate": resilience["intact_vs_best_individual"]
        >= float(thresholds["minimum_drift_swarm_advantage"]),
    }
    summary["discovery_gate"] = bool(
        summary["w3_02_gate"]
        and summary["w3_03_gate"]
        and summary["w3_04_gate"]
        and summary["w3_06_gate"]
    )
    destination = Path(destination)
    _write_json(destination / "w3-discovery-rows.json", rows)
    _write_json(destination / "w3-discovery-summary.json", summary)
    return summary


def replicate(
    candidates_path: str | Path,
    capsules_path: str | Path,
    pair_edges_path: str | Path,
    pair_state_path: str | Path,
    missions_path: str | Path,
    campaign_path: str | Path,
    recruiter_path: str | Path,
    destination: str | Path,
) -> dict[str, Any]:
    """Execute W3-07 on unseen Fields without retuning."""

    candidates = _read_jsonl(candidates_path)
    capsules = _read_jsonl(capsules_path)
    pair_edges = _read_jsonl(pair_edges_path)
    pair_state = _read_jsonl(pair_state_path)
    config = _read_json(missions_path)
    campaign = _read_json(campaign_path)
    recruiter = _read_json(recruiter_path)
    private_agents, public_pairs, private_pairs = _index_private(
        candidates, capsules, pair_edges, pair_state
    )
    rows = _discover_rows(
        candidates,
        private_agents,
        public_pairs,
        private_pairs,
        _mission_rows(config, "replication"),
        config,
        recruiter,
        salt="w3-replication",
    )
    thresholds = campaign["thresholds"]
    swarm_individual = _mean_delta(rows, "swarm_success", "individual_success")
    swarm_assembled = _mean_delta(rows, "swarm_success", "assembled_success")
    swarm_shuffled = _mean_delta(rows, "swarm_success", "shuffled_success")
    field_lifts = _field_deltas(rows, "individual_success")
    summary = {
        "field_lifts": field_lifts,
        "positive_fields": sum(value > 0 for value in field_lifts.values()),
        "recruiter_sha256": recruiter["recruiter_sha256"],
        "swarm_vs_assembled_lift": swarm_assembled,
        "swarm_vs_individual_lift": swarm_individual,
        "swarm_vs_shuffled_lift": swarm_shuffled,
    }
    summary["replication_gate"] = bool(
        swarm_individual >= float(thresholds["minimum_replication_individual_lift"])
        and swarm_assembled >= float(thresholds["minimum_replication_relationship_capital"])
        and swarm_shuffled >= float(thresholds["minimum_replication_shuffle_lift"])
        and summary["positive_fields"] == len(field_lifts)
    )
    destination = Path(destination)
    _write_json(destination / "w3-07-rows.json", rows)
    _write_json(destination / "w3-07-summary.json", summary)
    return summary


def synthesize(
    recruiter_path: str | Path,
    discovery_path: str | Path,
    replication_path: str | Path,
    destination: str | Path,
) -> dict[str, Any]:
    recruiter = _read_json(recruiter_path)
    discovery = _read_json(discovery_path)
    replication = _read_json(replication_path)
    status = (
        "replicated_transferable_relationship_capital"
        if discovery["discovery_gate"] and replication["replication_gate"]
        else "w3_relationship_capital_not_replicated"
    )
    summary = {
        "discovery": discovery,
        "frozen_recruiter": recruiter,
        "replication": replication,
        "status": status,
    }
    _write_json(Path(destination) / "w3-campaign-summary.json", summary)
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    calibrate_parser = subparsers.add_parser("calibrate")
    for name in ("candidates", "capsules", "pair_edges", "pair_state", "missions", "output"):
        calibrate_parser.add_argument(name, type=Path)

    discover_parser = subparsers.add_parser("discover")
    for name in (
        "candidates",
        "capsules",
        "pair_edges",
        "pair_state",
        "missions",
        "campaign",
        "recruiter",
        "output",
    ):
        discover_parser.add_argument(name, type=Path)

    replicate_parser = subparsers.add_parser("replicate")
    for name in (
        "candidates",
        "capsules",
        "pair_edges",
        "pair_state",
        "missions",
        "campaign",
        "recruiter",
        "output",
    ):
        replicate_parser.add_argument(name, type=Path)

    synthesize_parser = subparsers.add_parser("synthesize")
    for name in ("recruiter", "discovery", "replication", "output"):
        synthesize_parser.add_argument(name, type=Path)

    args = parser.parse_args(argv)
    if args.command == "calibrate":
        result = calibrate(
            args.candidates,
            args.capsules,
            args.pair_edges,
            args.pair_state,
            args.missions,
            args.output,
        )
    elif args.command == "discover":
        result = discover(
            args.candidates,
            args.capsules,
            args.pair_edges,
            args.pair_state,
            args.missions,
            args.campaign,
            args.recruiter,
            args.output,
        )
    elif args.command == "replicate":
        result = replicate(
            args.candidates,
            args.capsules,
            args.pair_edges,
            args.pair_state,
            args.missions,
            args.campaign,
            args.recruiter,
            args.output,
        )
    else:
        result = synthesize(args.recruiter, args.discovery, args.replication, args.output)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
