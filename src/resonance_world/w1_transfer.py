ig_path)
    _, private = _index_rows(candidates, capsules)
    holdout = _filter_fields(candidates, list(config["discovery_holdout_fields"]))
    scores = _model_scores(holdout, model)

    w104_results = _evaluate_rows(
        holdout, private, config, "alias_a", "w1-04-discovery-holdout"
    )
    w104_by_key = {_candidate_key(row): row for row in w104_results}
    comparison = _selection_comparison(
        holdout,
        w104_by_key,
        scores,
        selected_per_field=int(config["selected_per_field"]),
        salt="w1-04-random-baseline",
    )
    predicted = [scores[_candidate_key(row)] for row in holdout]
    actual = [
        float(w104_by_key[_candidate_key(row)]["sampled_success_rate"])
        for row in holdout
    ]
    rank_correlation = _spearman(predicted, actual)
    gates = campaign_config["decision_gates"]
    w104_pass = (
        comparison["pooled_lift"] >= float(gates["w1_04_min_selected_lift"])
        and rank_correlation >= float(gates["w1_04_min_rank_correlation"])
    )
    w104 = {
        "comparison": comparison,
        "model_sha256": model["model_sha256"],
        "passed": w104_pass,
        "rank_correlation": rank_correlation,
    }

    shift_rows = []
    for family in ("alias_a", "shift_25", "shift_50"):
        results = _evaluate_rows(
            holdout, private, config, family, f"w1-05:{family}"
        )
        by_key = {_candidate_key(row): row for row in results}
        comp = _selection_comparison(
            holdout,
            by_key,
            scores,
            selected_per_field=int(config["selected_per_field"]),
            salt=f"w1-05:{family}:random",
        )
        shift_rows.append(
            {
                "confirmatory": bool(w104_pass),
                "family": family,
                "pooled_lift": comp["pooled_lift"],
                "positive_fields": comp["positive_fields"],
                "selected_agent_mean": comp["selected_agent_mean"],
                "random_group_mean": comp["random_group_mean"],
            }
        )

    selected_keys = set()
    for field_id, rows in _group_by_field(holdout).items():
        selected = sorted(
            rows,
            key=lambda row: (scores[_candidate_key(row)], str(row["agent_id"])),
            reverse=True,
        )[: int(config["selected_per_field"])]
        selected_keys.update(_candidate_key(row) for row in selected)
    adaptation_rows = [
        _adapt_agent(
            row,
            private[_candidate_key(row)],
            config,
            family_name=str(config["adaptation"]["family"]),
            trials=int(config["adaptation"]["trials"]),
        )
        for row in holdout
    ]
    selected_adaptation = [
        row
        for row in adaptation_rows
        if (row["field_id"], row["agent_id"]) in selected_keys
    ]
    random_expected = statistics.mean(
        row["sampled_success_rate"] for row in adaptation_rows
    )
    w106 = {
        "confirmatory": bool(w104_pass),
        "all_agent_mean_success": random_expected,
        "selected_mean_improvement": statistics.mean(
            row["improvement"] for row in selected_adaptation
        ),
        "selected_mean_latency": statistics.mean(
            row["latency_to_plus_0_06"] for row in selected_adaptation
        ),
        "selected_mean_success": statistics.mean(
            row["sampled_success_rate"] for row in selected_adaptation
        ),
    }

    destination = Path(destination)
    _write_jsonl(destination / "w1-04-results.jsonl", w104_results)
    _write_json(destination / "w1-04-decision.json", w104)
    _write_json(destination / "w1-05-domain-shift.json", shift_rows)
    _write_jsonl(destination / "w1-06-agent-adaptation.jsonl", adaptation_rows)
    _write_json(destination / "w1-06-summary.json", w106)
    summary = {
        "model_sha256": model["model_sha256"],
        "w1_04_passed": w104_pass,
        "w1_04_pooled_lift": comparison["pooled_lift"],
        "w1_04_rank_correlation": rank_correlation,
        "w1_05_confirmatory": bool(w104_pass),
        "w1_06_confirmatory": bool(w104_pass),
    }
    _write_json(destination / "discovery-summary.json", summary)
    return summary


def run_replication(
    candidates_path: str | Path,
    capsules_path: str | Path,
    config_path: str | Path,
    model_path: str | Path,
    campaign_config_path: str | Path,
    destination: str | Path,
) -> dict[str, Any]:
    """Execute W1-07 on unseen source Fields and destination family."""

    candidates = _read_jsonl(candidates_path)
    capsules = _read_jsonl(capsules_path)
    config = _read_json(config_path)
    model = _read_json(model_path)
    campaign_config = _read_json(campaign_config_path)
    _, private = _index_rows(candidates, capsules)
    replication = _filter_fields(candidates, list(config["replication_fields"]))
    scores = _model_scores(replication, model)
    results = _evaluate_rows(
        replication, private, config, "replication_b", "w1-07-unseen-replication"
    )
    by_key = {_candidate_key(row): row for row in results}
    comparison = _selection_comparison(
        replication,
        by_key,
        scores,
        selected_per_field=int(config["selected_per_field"]),
        salt="w1-07-random-baseline",
    )
    predicted = [scores[_candidate_key(row)] for row in replication]
    actual = [
        float(by_key[_candidate_key(row)]["sampled_success_rate"])
        for row in replication
    ]
    rank_correlation = _spearman(predicted, actual)
    gates = campaign_config["decision_gates"]
    passed = (
        comparison["pooled_lift"] >= float(gates["w1_07_min_selected_lift"])
        and comparison["positive_fields"] >= int(gates["w1_07_min_positive_fields"])
        and rank_correlation >= float(gates["w1_07_min_rank_correlation"])
    )
    summary = {
        "comparison": comparison,
        "model_sha256": model["model_sha256"],
        "passed": passed,
        "rank_correlation": rank_correlation,
        "replication_agent_count": len(replication),
    }
    destination = Path(destination)
    _write_jsonl(destination / "w1-07-results.jsonl", results)
    _write_json(destination / "w1-07-summary.json", summary)
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    train = sub.add_parser("train")
    train.add_argument("candidates", type=Path)
    train.add_argument("capsules", type=Path)
    train.add_argument("config", type=Path)
    train.add_argument("output", type=Path)

    holdout = sub.add_parser("holdout")
    holdout.add_argument("candidates", type=Path)
    holdout.add_argument("capsules", type=Path)
    holdout.add_argument("config", type=Path)
    holdout.add_argument("model", type=Path)
    holdout.add_argument("campaign_config", type=Path)
    holdout.add_argument("output", type=Path)

    replication = sub.add_parser("replicate")
    replication.add_argument("candidates", type=Path)
    replication.add_argument("capsules", type=Path)
    replication.add_argument("config", type=Path)
    replication.add_argument("model", type=Path)
    replication.add_argument("campaign_config", type=Path)
    replication.add_argument("output", type=Path)

    args = parser.parse_args(argv)
    if args.command == "train":
        result = run_training(args.candidates, args.capsules, args.config, args.output)
    elif args.command == "holdout":
        result = run_discovery_holdout(
            args.candidates,
            args.capsules,
            args.config,
            args.model,
            args.campaign_config,
            args.output,
        )
    else:
        result = run_replication(
            args.candidates,
            args.capsules,
            args.config,
            args.model,
            args.campaign_config,
            args.output,
        )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
