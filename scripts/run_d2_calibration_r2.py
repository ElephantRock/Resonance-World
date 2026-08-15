p{pair_index:02d}",
        dev_cases=destination_cases,
        eval_cases=eval_cases,
        artifact=None,
        labeled=False,
    )
    fresh = run_fresh_arm(client, eval_cases=eval_cases)

    return {
        "pair_index": pair_index,
        "pair_public_id": f"d2-r2-pair-{pair_index:02d}",
        "private_policy_sha256": sha256(policy.private_record()),
        "source_destination_development_overlap": len(
            source_features & destination_features
        ),
        "development_evaluation_overlap": len(
            (source_features | destination_features) & eval_features
        ),
        "artifact": artifact,
        "artifact_audit": audit.as_dict(),
        "arms": {
            "fresh": fresh,
            "description_only": description,
            "reproduced": reproduced,
            "source_developed": source,
        },
    }


def run_sampling_characterization(client: Client) -> list[dict[str, Any]]:
    policy = policy_for(999100)
    cases = generate_balanced_cases(
        rng_seed=999101,
        count=8,
        prefix="r2-sampling",
        policy=policy,
    )
    records: list[dict[str, Any]] = []
    for temperature in SAMPLING_TEMPERATURES:
        for replicate in range(SAMPLING_REPLICATES):
            result = client.complete(
                phase=f"sampling/t{temperature}/r{replicate}",
                system=system_prompt(len(cases)),
                user=decision_user(
                    cases=cases,
                    prior_strategy="",
                    history=None,
                    labeled=False,
                    artifact=None,
                    phase="sampling_characterization",
                ),
                expected_actions=len(cases),
                temperature=temperature,
            )
            records.append(
                {
                    "temperature": temperature,
                    "replicate": replicate,
                    "valid": True,
                    "actions": list(result["actions"]),
                    "score": score_actions(cases, result["actions"]),
                    "physical_attempts": len(result["attempts"]),
                }
            )
    return records


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default="output/d2-calibration-r2")
    args = parser.parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    client = Client(os.environ.get("ZAI_API_KEY", ""))
    sampling_records = run_sampling_characterization(client)

    pair_records: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
        futures = {
            pool.submit(run_pair, client, index): index
            for index in range(PAIR_COUNT)
        }
        for future in as_completed(futures):
            pair_records.append(future.result())
    pair_records.sort(key=lambda row: row["pair_index"])

    summary = descriptive_summary(pair_records)
    readiness = development_readiness(pair_records)
    sampling = sampling_summary(sampling_records)

    overlaps_sd = sum(
        int(row["source_destination_development_overlap"]) for row in pair_records
    )
    overlaps_eval = sum(
        int(row["development_evaluation_overlap"]) for row in pair_records
    )
    all_audits = all(
        bool(row["artifact_audit"]["passed"]) for row in pair_records
    )
    equal_calls = all(
        row["arms"]["description_only"]["logical_calls"]
        == row["arms"]["reproduced"]["logical_calls"]
        for row in pair_records
    )
    expected_developed_calls = (
        SOURCE_DEV_COUNT // BATCH_SIZE + EVAL_COUNT // EVAL_CHUNK_SIZE
    )
    expected_fresh_calls = EVAL_COUNT // EVAL_CHUNK_SIZE
    developed_call_gate = all(
        row["arms"][arm]["logical_calls"] == expected_developed_calls
        for row in pair_records
        for arm in ("source_developed", "reproduced", "description_only")
    )
    fresh_call_gate = all(
        row["arms"]["fresh"]["logical_calls"] == expected_fresh_calls
        for row in pair_records
    )
    pair_logical = sum(
        int(arm["logical_calls"])
        for row in pair_records
        for arm in row["arms"].values()
    )
    sampling_logical = len(sampling_records)
    logical_total = pair_logical + sampling_logical
    physical_total = (
        sum(
            int(arm["physical_attempts"])
            for row in pair_records
            for arm in row["arms"].values()
        )
        + sum(int(row["physical_attempts"]) for row in sampling_records)
    )

    output = {
        "status": "completed_development_only_not_confirmatory",
        "revision": "D2-0 learnability revision 2",
        "model": MODEL,
        "temperature": TEMPERATURE,
        "pair_count": PAIR_COUNT,
        "source_development_cases": SOURCE_DEV_COUNT,
        "destination_development_cases": DEST_DEV_COUNT,
        "evaluation_cases": EVAL_COUNT,
        "batch_size": BATCH_SIZE,
        "evaluation_chunk_size": EVAL_CHUNK_SIZE,
        "pair_records": pair_records,
        "sampling_records": sampling_records,
        "production_historical_substrate_enabled": False,
        "confirmatory_holdout_created_or_used": False,
    }
    output_path = output_dir / "d2-0-r2-output.json"
    output_path.write_bytes(canonical_bytes(output))

    report = {
        "status": "completed_development_only_not_confirmatory",
        "revision": "D2-0 learnability revision 2",
        "created_at_utc": datetime.now(UTC).isoformat(),
        "model": MODEL,
        "temperature": TEMPERATURE,
        "chance_score": CHANCE_SCORE,
        "pair_count": PAIR_COUNT,
        "descriptive_summary": summary,
        "development_readiness": readiness,
        "sampling_summary": sampling,
        "integrity": {
            "source_destination_development_overlap_total": overlaps_sd,
            "development_evaluation_overlap_total": overlaps_eval,
            "all_artifact_audits_pass": all_audits,
            "description_reproduced_logical_calls_equal": equal_calls,
            "all_developed_arm_logical_calls_expected": developed_call_gate,
            "all_fresh_logical_calls_expected": fresh_call_gate,
            "evaluation_feedback_returned": False,
            "confirmatory_holdout_created_or_used": False,
        },
        "call_accounting": {
            "paired_panel_logical_calls": pair_logical,
            "sampling_logical_calls": sampling_logical,
            "logical_calls_total": logical_total,
            "physical_attempts_total": physical_total,
        },
        "handoff": (
            "eligible_for_confirmatory_design_freeze"
            if readiness["all_gates_pass"]
            else "revise_development_substrate_again"
        ),
        "confirmatory_evidence": False,
        "production_historical_substrate_enabled": False,
    }
    expected_logical_total = PAIR_COUNT * (
        3 * expected_developed_calls + expected_fresh_calls
    )
    expected_logical_total += len(SAMPLING_TEMPERATURES) * SAMPLING_REPLICATES
    assert logical_total == expected_logical_total
    assert overlaps_sd == 0
    assert overlaps_eval == 0
    assert all_audits
    assert equal_calls
    assert developed_call_gate
    assert fresh_call_gate

    report_path = output_dir / "d2-0-r2-report.json"
    report_path.write_bytes(canonical_bytes(report))

    manifest = {
        "schema": "d2-0-r2-development-calibration-manifest-v0.1",
        "development_only": True,
        "confirmatory_evidence": False,
        "revision": "D2-0 learnability revision 2",
        "model": MODEL,
        "temperature": TEMPERATURE,
        "logical_calls_total": logical_total,
        "physical_attempts_total": physical_total,
        "output_sha256": file_sha256(output_path),
        "report_sha256": file_sha256(report_path),
        "production_historical_substrate_enabled": False,
    }
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_bytes(canonical_bytes(manifest))

    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()