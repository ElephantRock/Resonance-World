dict[str, Any]) -> dict[str, Any]:
    band = float(config["effect_band"])
    w6_01_source = [float(route["w6_01"]["source_loss"]) for route in routes]
    w6_01_host = [float(route["w6_01"]["host_gain"]) for route in routes]
    drain = _effect_summary(routes, "w6_03", "persistent_source_loss", band)
    returned = _effect_summary(routes, "w6_04", "returned_learning_effect", band)
    pair = _effect_summary(routes, "w6_06", "effect", band)
    learned_vs_baseline = _mean(
        [float(route["w6_04"]["learned_home_minus_pre_move"]) for route in routes]
    )
    brain_circulation = (
        returned["effect"] > band
        and returned["positive_routes"] >= 2
        and learned_vs_baseline >= -band
    )
    return {
        "w6_01": {
            "mean_source_loss": _mean(w6_01_source),
            "mean_host_gain": _mean(w6_01_host),
            "mean_world_total_change": _mean(
                [float(route["w6_01"]["world_total_change"]) for route in routes]
            ),
            "source_loss_routes": sum(value > 0 for value in w6_01_source),
            "host_gain_routes": sum(value > 0 for value in w6_01_host),
        },
        "w6_02": {
            "exact_mode_parity": all(bool(route["w6_02"]["exact_match"]) for route in routes)
        },
        "w6_03": {
            **drain,
            "brain_drain": drain["effect"] > band and drain["positive_routes"] >= 2,
            "mean_immediate_source_loss": _mean(
                [float(route["w6_03"]["immediate_source_loss"]) for route in routes]
            ),
            "recovered_routes": sum(
                bool(route["w6_03"]["replacement"]["recovered"]) for route in routes
            ),
            "mean_replacement_latency_recovered": _mean(
                [
                    float(route["w6_03"]["replacement"]["latency"])
                    for route in routes
                    if route["w6_03"]["replacement"]["latency"] is not None
                ]
            ),
        },
        "w6_04": returned,
        "w6_05": {
            "brain_circulation": brain_circulation,
            "mean_learned_home_minus_pre_move": learned_vs_baseline,
            "returned_learning_effect": returned["effect"],
        },
        "w6_06": pair,
    }


def run_phase(
    candidates_path: str | Path,
    capsules_path: str | Path,
    config_path: str | Path,
    phase: str,
) -> dict[str, Any]:
    config = _read_json(config_path)
    if phase not in {"discovery", "replication"}:
        raise ValueError("phase must be discovery or replication")
    routes = _load_routes(candidates_path, capsules_path, config, phase)
    route_results = [_evaluate_route(route, config, phase) for route in routes]
    summary = _summarize(route_results, config)
    if not bool(summary["w6_02"]["exact_mode_parity"]):
        raise AssertionError("W6-02 mobility-mode leakage control failed")
    return {
        "phase": phase,
        "effect_band": float(config["effect_band"]),
        "routes": route_results,
        "summary": summary,
    }


def _replication_gate(
    discovery: dict[str, Any],
    replication: dict[str, Any],
) -> dict[str, Any]:
    band = float(discovery["effect_band"])
    gates: dict[str, Any] = {}
    for experiment in ("w6_03", "w6_04", "w6_06"):
        expected = str(discovery["summary"][experiment]["classification"])
        observed = str(replication["summary"][experiment]["classification"])
        if expected == "null":
            passed = observed == "null"
        elif expected == "positive":
            passed = (
                float(replication["summary"][experiment]["effect"]) > band
                and int(replication["summary"][experiment]["positive_routes"]) >= 2
            )
        else:
            passed = (
                float(replication["summary"][experiment]["effect"]) < -band
                and int(replication["summary"][experiment]["negative_routes"]) >= 2
            )
        gates[experiment] = {
            "discovery_classification": expected,
            "replication_classification": observed,
            "passed": passed,
        }
    gates["w6_02"] = {
        "passed": bool(replication["summary"]["w6_02"]["exact_mode_parity"])
    }
    return gates


def discover(
    candidates_path: str | Path,
    capsules_path: str | Path,
    config_path: str | Path,
    destination: str | Path,
) -> dict[str, Any]:
    result = run_phase(candidates_path, capsules_path, config_path, "discovery")
    destination = Path(destination)
    _write_json(destination / "w6-discovery.json", result)
    return result


def replicate(
    candidates_path: str | Path,
    capsules_path: str | Path,
    config_path: str | Path,
    discovery_path: str | Path,
    destination: str | Path,
) -> dict[str, Any]:
    discovery_result = _read_json(discovery_path)
    result = run_phase(candidates_path, capsules_path, config_path, "replication")
    result["experiment_gates"] = _replication_gate(discovery_result, result)
    result["replication_gate"] = all(
        bool(value["passed"]) for value in result["experiment_gates"].values()
    )
    destination = Path(destination)
    _write_json(destination / "w6-07-replication.json", result)
    return result


def synthesize(
    discovery_path: str | Path,
    replication_path: str | Path,
    destination: str | Path,
) -> dict[str, Any]:
    discovery_result = _read_json(discovery_path)
    replication_result = _read_json(replication_path)
    replicated = bool(replication_result["replication_gate"])
    discovery_circulation = bool(discovery_result["summary"]["w6_05"]["brain_circulation"])
    replication_circulation = bool(
        replication_result["summary"]["w6_05"]["brain_circulation"]
    )
    if replicated and discovery_circulation and replication_circulation:
        status = "w6_replicated_brain_circulation"
    elif replicated:
        status = "w6_primary_mobility_classifications_replicated"
    else:
        status = "w6_discovery_not_replicated"
    result = {
        "status": status,
        "replication_gate": replicated,
        "discovery": discovery_result["summary"],
        "replication": replication_result["summary"],
        "experiment_gates": replication_result["experiment_gates"],
    }
    destination = Path(destination)
    _write_json(destination / "w6-synthesis.json", result)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    discover_parser = subparsers.add_parser("discover")
    discover_parser.add_argument("candidates", type=Path)
    discover_parser.add_argument("capsules", type=Path)
    discover_parser.add_argument("config", type=Path)
    discover_parser.add_argument("output", type=Path)

    replicate_parser = subparsers.add_parser("replicate")
    replicate_parser.add_argument("candidates", type=Path)
    replicate_parser.add_argument("capsules", type=Path)
    replicate_parser.add_argument("config", type=Path)
    replicate_parser.add_argument("discovery", type=Path)
    replicate_parser.add_argument("output", type=Path)

    synthesize_parser = subparsers.add_parser("synthesize")
    synthesize_parser.add_argument("discovery", type=Path)
    synthesize_parser.add_argument("replication", type=Path)
    synthesize_parser.add_argument("output", type=Path)

    args = parser.parse_args(argv)
    if args.command == "discover":
        result = discover(args.candidates, args.capsules, args.config, args.output)
    elif args.command == "replicate":
        result = replicate(
            args.candidates,
            args.capsules,
            args.config,
            args.discovery,
            args.output,
        )
    else:
        result = synthesize(args.discovery, args.replication, args.output)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
