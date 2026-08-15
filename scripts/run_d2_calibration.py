olicy)
    system = system_prompt(len(cases))
    user = decision_user(
        cases=cases,
        prior_strategy="",
        history=None,
        labeled=False,
        artifact=None,
        phase="sampling_characterization",
    )
    raw: list[dict[str, Any]] = []
    retry_reasons: dict[str, int] = {}
    for temperature in SAMPLING_TEMPERATURES:
        for replicate in range(SAMPLING_REPLICATES):
            result = client.complete(
                phase=f"sampling/{temperature}/{replicate}",
                system=system,
                user=user,
                expected_actions=len(cases),
                temperature=temperature,
            )
            actions = list(result["payload"]["actions"])
            for attempt in result["attempts"][:-1]:
                status = str(attempt["status"])
                retry_reasons[status] = retry_reasons.get(status, 0) + 1
            raw.append(
                {
                    "temperature": temperature,
                    "replicate": replicate,
                    "valid": True,
                    "actions": actions,
                    "score": score_actions(cases, actions),
                    "physical_attempts": len(result["attempts"]),
                }
            )
    summary = sampling_summary(raw)
    total_logical = len(SAMPLING_TEMPERATURES) * SAMPLING_REPLICATES
    total_physical = sum(int(item["physical_attempts"]) for item in summary.values())
    return {
        "suite_schema": "d2-0-sampling-characterization-v0.1",
        "model": MODEL,
        "temperatures": list(SAMPLING_TEMPERATURES),
        "replicates_per_temperature": SAMPLING_REPLICATES,
        "case_count": len(cases),
        "public_case_batch_sha256": public_payload_sha(
            [public_case(case) for case in cases]
        ),
        "summary": summary,
        "logical_calls": total_logical,
        "physical_attempts": total_physical,
        "retry_frequency": (total_physical - total_logical) / total_physical,
        "retry_reasons": retry_reasons,
        "confirmatory_setting_selected": False,
    }


def aggregate(pair_records: list[dict[str, Any]], sampling: dict[str, Any]) -> dict[str, Any]:
    descriptive = descriptive_summary(pair_records)
    development_logical = sum(
        int(arm["logical_calls"])
        for pair in pair_records
        for arm in pair["arms"].values()
    )
    development_physical = sum(
        int(arm["physical_attempts"])
        for pair in pair_records
        for arm in pair["arms"].values()
    )
    total_logical = development_logical + int(sampling["logical_calls"])
    total_physical = development_physical + int(sampling["physical_attempts"])
    retry_reasons: dict[str, int] = dict(sampling["retry_reasons"])
    for pair in pair_records:
        for arm in pair["arms"].values():
            for call in arm["calls"]:
                for attempt in call["attempt_log"][:-1]:
                    status = str(attempt["status"])
                    retry_reasons[status] = retry_reasons.get(status, 0) + 1
    return {
        "schema": "d2-0-calibration-report-v0.1",
        "status": "completed_development_only_not_confirmatory",
        "model": MODEL,
        "development_temperature": TEMPERATURE,
        "pair_count": PAIR_COUNT,
        "development_episodes_per_developed_arm": SOURCE_DEV_COUNT,
        "evaluation_cases_per_pair": EVAL_COUNT,
        "descriptive": descriptive,
        "source_learning_curves": [
            pair["arms"]["source_developed"]["development_batch_scores"]
            + [pair["arms"]["source_developed"]["final_score"]]
            for pair in pair_records
        ],
        "reproduced_learning_curves": [
            pair["arms"]["reproduced"]["development_batch_scores"]
            + [pair["arms"]["reproduced"]["final_score"]]
            for pair in pair_records
        ],
        "description_only_learning_curves": [
            pair["arms"]["description_only"]["development_batch_scores"]
            + [pair["arms"]["description_only"]["final_score"]]
            for pair in pair_records
        ],
        "sampling_characterization": sampling,
        "integrity": {
            "source_destination_development_overlap_total": sum(
                pair["development_example_overlap_count"] for pair in pair_records
            ),
            "development_evaluation_overlap_total": sum(
                pair["evaluation_development_overlap_count"] for pair in pair_records
            ),
            "all_artifact_audits_pass": all(
                pair["artifact_audit"]["passed"] for pair in pair_records
            ),
            "description_reproduced_logical_calls_equal": all(
                pair["arms"]["description_only"]["logical_calls"]
                == pair["arms"]["reproduced"]["logical_calls"]
                for pair in pair_records
            ),
            "production_historical_substrate_enabled": False,
        },
        "call_accounting": {
            "logical_calls_total": total_logical,
            "physical_attempts_total": total_physical,
            "retry_frequency": (total_physical - total_logical) / total_physical,
            "retry_reasons": retry_reasons,
        },
        "power_inputs": {
            "paired_difference_sd_p0": descriptive["paired_contrasts"][
                "p0_source_minus_fresh"
            ]["sample_sd"],
            "paired_difference_sd_p1": descriptive["paired_contrasts"][
                "p1_reproduced_minus_description"
            ]["sample_sd"],
            "paired_difference_sd_p2": descriptive["paired_contrasts"][
                "p2_reproduced_minus_source"
            ]["sample_sd"],
            "note": (
                "Development-only empirical variance inputs; "
                "not confirmatory thresholds or final N."
            ),
        },
        "confirmatory_outcomes_included": False,
        "confirmatory_holdout_created_or_used": False,
        "production_historical_substrate_enabled": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    key = os.environ.get("ZAI_API_KEY", "")
    if not key:
        raise SystemExit("ZAI_API_KEY required for D2-0 calibration")
    args.output_dir.mkdir(parents=True, exist_ok=True)

    client = Client(key)
    sampling = run_sampling_characterization(client)

    completed: dict[int, dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
        futures = {
            pool.submit(run_pair, client, index): index for index in range(PAIR_COUNT)
        }
        for future in as_completed(futures):
            index = futures[future]
            completed[index] = future.result()
            print(
                f"D2_CALIBRATION_PROGRESS {len(completed)}/{PAIR_COUNT} pair={index}",
                flush=True,
            )
    pairs = [completed[index] for index in range(PAIR_COUNT)]
    report = aggregate(pairs, sampling)

    output = {
        "schema": "d2-0-calibration-output-v0.1",
        "report": report,
        "pairs": pairs,
        "production_historical_substrate_enabled": False,
    }
    output_path = args.output_dir / "d2-0-calibration-output.json"
    output_path.write_bytes(canonical_bytes(output))
    report_path = args.output_dir / "d2-0-calibration-report.json"
    report_path.write_bytes(canonical_bytes(report))
    manifest = {
        "schema": "d2-0-calibration-manifest-v0.1",
        "output_sha256": hashlib.sha256(output_path.read_bytes()).hexdigest(),
        "report_sha256": hashlib.sha256(report_path.read_bytes()).hexdigest(),
        "model": MODEL,
        "development_temperature": TEMPERATURE,
        "pair_count": PAIR_COUNT,
        "development_only": True,
        "confirmatory_evidence": False,
        "production_historical_substrate_enabled": False,
    }
    (args.output_dir / "manifest.json").write_bytes(canonical_bytes(manifest))
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
