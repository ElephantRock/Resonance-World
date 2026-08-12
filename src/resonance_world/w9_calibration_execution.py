f not rows:
        return {
            "mean_absolute_interaction_error_pp": 0.0,
            "mean_absolute_predicted_interaction_pp": 0.0,
            "mean_absolute_realized_interaction_pp": 0.0,
            "mean_predicted_interaction_pp": 0.0,
            "mean_realized_interaction_pp": 0.0,
            "observation_count": 0,
            "positive_realized_interaction_share": 0.0,
        }
    predicted = [float(row["predicted_interaction_pp"]) for row in rows]
    realized = [float(row["realized_interaction_pp"]) for row in rows]
    return {
        "mean_absolute_interaction_error_pp": statistics.mean(
            abs(a - b) for a, b in zip(predicted, realized, strict=True)
        ),
        "mean_absolute_predicted_interaction_pp": statistics.mean(abs(value) for value in predicted),
        "mean_absolute_realized_interaction_pp": statistics.mean(abs(value) for value in realized),
        "mean_predicted_interaction_pp": statistics.mean(predicted),
        "mean_realized_interaction_pp": statistics.mean(realized),
        "observation_count": len(rows),
        "positive_realized_interaction_share": statistics.mean(
            float(value > 0) for value in realized
        ),
    }


def evaluate_prediction_manifest(
    source_dir: str | Path,
    config: Mapping[str, Any],
    predictions: Mapping[str, Any],
    *,
    phase: str,
) -> dict[str, Any]:
    if str(predictions.get("version")) != PREDICTION_VERSION:
        raise ValueError("unsupported W9 prediction manifest version")
    if str(predictions.get("phase")) != phase:
        raise ValueError("prediction manifest phase mismatch")
    if str(predictions.get("field_sha")) != str(config["field_sha"]):
        raise ValueError("prediction manifest Field pin mismatch")
    if str(predictions.get("config_sha256")) != _sha256(config):
        raise ValueError("prediction manifest campaign config mismatch")

    manifest_copy = dict(predictions)
    manifest_sha = str(manifest_copy.pop("manifest_sha256", ""))
    if not manifest_sha or manifest_sha != _sha256(manifest_copy):
        raise ValueError("prediction manifest digest mismatch")

    expected_seeds = _expected_seeds(config, phase)
    population = load_population(source_dir, expected_seeds=expected_seeds)
    states_by_field = population.portable_by_field

    observations: list[CalibrationObservation] = []
    by_field: dict[str, list[CalibrationObservation]] = {}
    observation_rows: list[dict[str, Any]] = []
    for row in list(predictions["principal_observations"]):
        field_id = str(row["source_field_id"])
        agent_id = str(row["agent_id"])
        unavailable = frozenset(str(value) for value in row["unavailable_agent_ids"])
        realized = _realized_marginal_cost_pp(
            states_by_field[field_id],
            agent_id=agent_id,
            unavailable_agent_ids=unavailable,
            config=config,
        )
        observation = CalibrationObservation(
            source_field_id=field_id,
            agent_id=agent_id,
            unavailable_agent_ids=unavailable,
            predicted_loss_pp=float(row["predicted_loss_pp"]),
            conservative_budget_pp=float(row["conservative_budget_pp"]),
            realized_loss_pp=realized,
            evidence_refs=tuple(str(value) for value in row["evidence_refs"]),
        )
        observations.append(observation)
        by_field.setdefault(field_id, []).append(observation)
        observation_rows.append(
            {
                "agent_id": agent_id,
                "conservative_budget_pp": observation.conservative_budget_pp,
                "context_kind": str(row["context_kind"]),
                "evidence_refs": list(observation.evidence_refs),
                "prediction_error_pp": observation.prediction_error_pp,
                "predicted_loss_pp": observation.predicted_loss_pp,
                "realized_loss_pp": observation.realized_loss_pp,
                "source_field_id": field_id,
                "standard_error_pp": float(row["standard_error_pp"]),
                "unavailable_agent_ids": sorted(unavailable),
            }
        )

    thresholds = _thresholds(config)
    report = build_calibration_report(tuple(observations), thresholds=thresholds)
    field_reports = {
        field_id: build_calibration_report(tuple(rows), thresholds=thresholds).as_dict()
        for field_id, rows in sorted(by_field.items())
    }

    interaction_rows: list[dict[str, Any]] = []
    for row in list(predictions["pairwise_interactions"]):
        field_id = str(row["source_field_id"])
        agent_id = str(row["agent_id"])
        partner_id = str(row["conditioning_agent_id"])
        unconditional_realized = _realized_marginal_cost_pp(
            states_by_field[field_id],
            agent_id=agent_id,
            unavailable_agent_ids=frozenset(),
            config=config,
        )
        conditional_realized = _realized_marginal_cost_pp(
            states_by_field[field_id],
            agent_id=agent_id,
            unavailable_agent_ids=frozenset({partner_id}),
            config=config,
        )
        interaction_rows.append(
            {
                **dict(row),
                "conditional_realized_loss_pp": conditional_realized,
                "realized_interaction_pp": (
                    conditional_realized - unconditional_realized
                ),
                "unconditional_realized_loss_pp": unconditional_realized,
            }
        )

    result = {
        "agent_count": len(population.portable_by_id),
        "calibration": report.as_dict(),
        "field_calibration": field_reports,
        "field_count": len(population.portable_by_field),
        "field_sha": str(config["field_sha"]),
        "interaction_diagnostic": _interaction_summary(interaction_rows),
        "pairwise_interactions": interaction_rows,
        "phase": phase,
        "prediction_manifest_sha256": manifest_sha,
        "principal_observations": observation_rows,
        "seeds": expected_seeds,
        "version": RESULT_VERSION,
    }
    serialized = json.dumps(result, sort_keys=True)
    if "practice_by_skill" in serialized:
        raise AssertionError("private practice leaked into W9 calibration result")
    result["result_sha256"] = _sha256(result)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare = subparsers.add_parser("prepare")
    prepare.add_argument("--phase", required=True, choices=("discovery", "replication"))
    prepare.add_argument("--source-dir", required=True, type=Path)
    prepare.add_argument("--config", required=True, type=Path)
    prepare.add_argument("--output", required=True, type=Path)

    evaluate = subparsers.add_parser("evaluate")
    evaluate.add_argument("--phase", required=True, choices=("discovery", "replication"))
    evaluate.add_argument("--source-dir", required=True, type=Path)
    evaluate.add_argument("--config", required=True, type=Path)
    evaluate.add_argument("--predictions", required=True, type=Path)
    evaluate.add_argument("--output", required=True, type=Path)

    args = parser.parse_args(argv)
    config = _read_json(args.config)
    if not isinstance(config, dict):
        raise ValueError("W9 campaign config must be an object")

    if args.command == "prepare":
        result = build_prediction_manifest(args.source_dir, config, phase=args.phase)
    else:
        predictions = _read_json(args.predictions)
        if not isinstance(predictions, dict):
            raise ValueError("W9 prediction manifest must be an object")
        result = evaluate_prediction_manifest(
            args.source_dir,
            config,
            predictions,
            phase=args.phase,
        )
    _write_json(args.output, result)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
