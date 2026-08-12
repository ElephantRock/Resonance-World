eak
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
        "interpretation_boundary": (
            "CG-4M uses already-unblinded societies for exploratory design "
            "selection only. Any selected architecture must be frozen and "
            "tested on a genuinely new untouched cohort before a "
            "confirmatory claim."
        ),
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
