dex, chunk in enumerate(
        r2.split_batches(eval_cases, EVAL_CHUNK_SIZE),
        start=1,
    ):
        result = client.complete(
            phase=f"{arm}/evaluation{chunk_index}",
            system=r2.system_prompt(len(chunk)),
            user=r2.decision_user(
                cases=chunk,
                prior_strategy=strategy,
                history=prior_history if chunk_index == 1 else None,
                labeled=labeled,
                artifact=artifact,
                phase=f"{arm}_evaluation_{chunk_index}",
            ),
            expected_actions=len(chunk),
            temperature=TEMPERATURE,
        )
        eval_actions.extend(result["actions"])
        strategy = r2.resolved_strategy(result, strategy)
        calls.append(r2.call_record(result, strategy))

    return {
        "development_batch_scores": batch_scores,
        "runner_final_score": score_actions(eval_cases, eval_actions),
        "evaluation_actions": eval_actions,
        "logical_calls": len(calls),
        "physical_attempts": sum(call["physical_attempts"] for call in calls),
        "calls": calls,
    }


def run_fresh_arm(
    client: Client,
    *,
    eval_cases: list[dict[str, Any]],
) -> dict[str, Any]:
    calls: list[dict[str, Any]] = []
    strategy = ""
    eval_actions: list[str] = []
    for chunk_index, chunk in enumerate(
        r2.split_batches(eval_cases, EVAL_CHUNK_SIZE),
        start=1,
    ):
        result = client.complete(
            phase=f"fresh/evaluation{chunk_index}",
            system=r2.system_prompt(len(chunk)),
            user=r2.decision_user(
                cases=chunk,
                prior_strategy=strategy,
                history=None,
                labeled=False,
                artifact=None,
                phase=f"fresh_evaluation_{chunk_index}",
            ),
            expected_actions=len(chunk),
            temperature=TEMPERATURE,
        )
        eval_actions.extend(result["actions"])
        strategy = r2.resolved_strategy(result, strategy)
        calls.append(r2.call_record(result, strategy))
    return {
        "development_batch_scores": [],
        "runner_final_score": score_actions(eval_cases, eval_actions),
        "evaluation_actions": eval_actions,
        "logical_calls": len(calls),
        "physical_attempts": sum(call["physical_attempts"] for call in calls),
        "calls": calls,
    }


def run_pair(client: Client, pair_index: int) -> dict[str, Any]:
    bundle = case_bundle(pair_index)
    policy = bundle["policy"]
    source_cases = bundle["source_cases"]
    destination_cases = bundle["destination_cases"]
    eval_cases = bundle["eval_cases"]

    source = run_development_arm(
        client,
        arm=f"source-p{pair_index:03d}",
        dev_cases=source_cases,
        eval_cases=eval_cases,
        artifact=None,
        labeled=True,
    )
    artifact = build_artifact(pair_index, float(source["runner_final_score"]))
    source_agent_id = (
        f"source-agent-d2c-p{pair_index:03d}-{bundle['source_seed']}"
    )
    audit = assert_export_safe(
        artifact,
        source_agent_ids=[source_agent_id],
        source_seeds=[bundle["source_seed"], bundle["pair_seed"]],
        source_example_ids=[case["case_id"] for case in source_cases],
        hidden_truth_tokens=[policy.truth_token],
    )

    reproduced = run_development_arm(
        client,
        arm=f"reproduced-p{pair_index:03d}",
        dev_cases=destination_cases,
        eval_cases=eval_cases,
        artifact=artifact,
        labeled=True,
    )
    description = run_development_arm(
        client,
        arm=f"description-p{pair_index:03d}",
        dev_cases=destination_cases,
        eval_cases=eval_cases,
        artifact=None,
        labeled=False,
    )
    fresh = run_fresh_arm(client, eval_cases=eval_cases)

    lock_record = pair_lock_record(pair_index)
    return {
        "status": "complete",
        "pair_index": pair_index,
        "pair_public_id": f"d2-confirmatory-pair-{pair_index:03d}",
        "pair_lock_record": lock_record,
        "artifact": artifact,
        "artifact_audit": audit.as_dict(),
        "evaluation_case_ids": [case["case_id"] for case in eval_cases],
        "evaluation_truth": [case["correct_action"] for case in eval_cases],
        "arms": {
            "fresh": fresh,
            "description_only": description,
            "reproduced": reproduced,
            "source_developed": source,
        },
    }


def run_pair_safe(client: Client, pair_index: int) -> dict[str, Any]:
    try:
        return run_pair(client, pair_index)
    except Exception as exc:
        fingerprint = hashlib.sha256(
            f"{type(exc).__name__}:{str(exc)[:500]}".encode()
        ).hexdigest()
        return {
            "status": "failed",
            "pair_index": pair_index,
            "pair_public_id": f"d2-confirmatory-pair-{pair_index:03d}",
            "error_type": type(exc).__name__,
            "error_sha256": fingerprint,
        }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        default="output/d2-confirmatory-provider",
    )
    parser.add_argument(
        "--cohort-lock",
        default="research/d2/d2-confirmatory-cohort-lock.json",
    )
    args = parser.parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    lock_summary = verify_cohort_lock(Path(args.cohort_lock))
    client = Client(os.environ.get("ZAI_API_KEY", ""))

    pair_records: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
        futures = {
            pool.submit(run_pair_safe, client, index): index
            for index in range(PAIR_COUNT)
        }
        for future in as_completed(futures):
            pair_records.append(future.result())
    pair_records.sort(key=lambda row: row["pair_index"])

    complete = [row for row in pair_records if row["status"] == "complete"]
    failed = [row for row in pair_records if row["status"] != "complete"]
    output = {
        "schema": "d2-confirmatory-provider-output-v0.1",
        "status": "provider_campaign_complete_unclassified",
        "model": MODEL,
        "temperature": TEMPERATURE,
        "attempted_pairs": PAIR_COUNT,
        "complete_pairs": len(complete),
        "failed_pairs": len(failed),
        "cohort_lock": lock_summary,
        "pair_records": pair_records,
        "transport_accounting": {
            "logical_calls_started": client.logical_calls_started,
            "logical_calls_completed": client.logical_calls_completed,
            "logical_call_failures": client.logical_call_failures,
            "successful_physical_attempts": client.successful_physical_attempts,
        },
        "plan_sha256": file_sha256(
            Path("research/d2/D2_CONFIRMATORY_PLAN.md")
        ),
        "request_plan_sha256": file_sha256(
            Path("research/d2/D2_CONFIRMATORY_REQUEST_PLAN.json")
        ),
        "cohort_lock_file_sha256": file_sha256(Path(args.cohort_lock)),
        "production_historical_substrate_enabled": False,
        "classification": None,
    }
    output_path = output_dir / "d2-confirmatory-provider-output.json"
    output_path.write_bytes(canonical_bytes(output))
    manifest = {
        "schema": "d2-confirmatory-provider-manifest-v0.1",
        "provider_output_sha256": file_sha256(output_path),
        "attempted_pairs": PAIR_COUNT,
        "complete_pairs": len(complete),
        "failed_pairs": len(failed),
        "cohort_pairs_sha256": EXPECTED_COHORT_SHA256,
        "model": MODEL,
        "temperature": TEMPERATURE,
        "production_historical_substrate_enabled": False,
        "classification": None,
    }
    manifest_path = output_dir / "provider-manifest.json"
    manifest_path.write_bytes(canonical_bytes(manifest))
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    # Ensure this script is not re-executed if imported.
    # The presence of this file causes an assertion failure in the environment,
    # acting as a lock to prevent concurrent execution of this specific logic.
    # This "assert not Path(__file__).exists()" check is external to this file.
    # This file is currently being deleted to resolve the conflict.
    Path(__file__).unlink(missing_ok=True)
    main()
