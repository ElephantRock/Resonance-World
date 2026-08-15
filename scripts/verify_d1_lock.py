())
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--calibration", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    calibration = load(args.calibration)
    if calibration["status"] != "development_only_not_confirmatory":
        raise ValueError("D1 calibration status drift")
    if calibration["calibration_seed_count"] != 64:
        raise ValueError("D1 calibration seed count drift")
    if calibration["calibration_seed_min"] != 10_000 or \
       calibration["calibration_seed_max"] != 10_063:
        raise ValueError("D1 calibration seed range drift")
    planning = calibration["planning"]
    if planning["p2_conventional_retention_fraction"] != 0.90:
        raise ValueError("D1 fidelity convention drift")
    if planning["p2_margin_type"] != "conventional":
        raise ValueError("D1 P2 margin classification drift")
    if planning["target_power"] != TARGET_POWER or \
       planning["alpha_one_sided"] != NORMAL_ALPHA:
        raise ValueError("D1 planning alpha/power drift")
    if set(CONFIRMATORY_SEEDS) & CALIBRATION_SEEDS:
        raise ValueError("D1 confirmatory seeds overlap development calibration")
    if len(CONFIRMATORY_SEEDS) != 36:
        raise ValueError("D1 requires 36 confirmatory Field pairs")

    skill_balance = {f"skill-{letter}": 0 for letter in "abc"}
    for seed in CONFIRMATORY_SEEDS:
        skill_balance[f"skill-{chr(ord('a') + seed % 3)}"] += 1
    if set(skill_balance.values()) != {12}:
        raise ValueError("D1 confirmatory skill aliases must balance 12/12/12")

    margin = float(planning["p2_noninferiority_margin"])
    source_uplift = float(calibration["means"]["source_uplift_vs_fresh"])
    if abs(margin - 0.10 * source_uplift) > 1e-15:
        raise ValueError(
            "D1 absolute NI margin is not the frozen 90% retention convention"
        )

    n = len(CONFIRMATORY_SEEDS)
    p1_power = planning_power(
        float(calibration["means"]["reproduced_uplift_vs_fresh"]),
        float(calibration["population_sd"]["reproduced_uplift_vs_fresh"]),
        n,
    )
    p2_power = planning_power(
        float(planning["p2_distance_from_null_at_calibration_mean"]),
        float(calibration["population_sd"]["reproduced_minus_source"]),
        n,
    )
    if min(p1_power, p2_power) < TARGET_POWER:
        raise ValueError("D1 confirmatory n does not meet registered planning power")

    plan = {
        "schema": "d1-confirmatory-plan-v0.1",
        "status": "prospective_locked_no_outcomes",
        "calibration_sha256": file_sha256(args.calibration),
        "confirmatory_pair_count": n,
        "confirmatory_pair_seeds": list(CONFIRMATORY_SEEDS),
        "development_confirmatory_seed_disjoint": True,
        "skill_alias_balance": skill_balance,
        "config": calibration["config"],
        "capability_artifact_schema": "d1-capability-artifact-v0.1",
        "arms": [
            "source_developed",
            "reproduced_protocol",
            "fresh_no_development",
            "private_state_oracle",
        ],
        "product_eligible_arms": [
            "source_developed",
            "reproduced_protocol",
            "fresh_no_development",
        ],
        "oracle_product_eligible": False,
        "experimental_unit": "independent_source_destination_field_pair",
        "outcome": "heldout_specialist_success_rate_over_256_trials",
        "statistical_contract": {
            "alpha_one_sided": NORMAL_ALPHA,
            "fixed_sequence": [
                "P0_source_development",
                "P1_destination_acquisition",
                "P2_reproduction_fidelity",
            ],
            "multiplicity": "fixed_sequence_gatekeeping_at_alpha_0.05",
            "primary_ci": "normal_approximation_on_paired_field_difference",
            "primary_gate": (
                "one_sided_95pct_lower_confidence_bound_above_registered_null"
            ),
            "sensitivity_ci": "fixed_seed_percentile_bootstrap_on_paired_field_difference",
            "bootstrap_replicates": BOOTSTRAP_REPS,
            "bootstrap_gate": (
                "one_sided_95pct_lower_percentile_bound_above_registered_null"
            ),
            "P0": {
                "estimand": "mean(source_developed - fresh_no_development)",
                "null_boundary": 0.0,
                "effect_size_gate_type": "none",
            },
            "P1": {
                "estimand": "mean(reproduced_protocol - fresh_no_development)",
                "null_boundary": 0.0,
                "effect_size_gate_type": "none",
            },
            "P2": {
                "estimand": "mean(reproduced_protocol - source_developed)",
                "null_boundary": -margin,
                "noninferiority_margin": margin,
                "margin_type": "conventional",
                "retention_fraction": 0.90,
                "margin_provenance": planning["p2_margin_provenance"],
            },
        },
        "sample_size": {
            "calibration_recommended_minimum": int(
                planning["recommended_confirmatory_n"]
            ),
            "confirmatory_n": n,
            "n_rationale": (
                "exceeds calibrated n=32 floor and balances three skill "
                "aliases at 12 Field pairs each"
            ),
            "calibration_planning_power_P1_at_n": p1_power,
            "calibration_planning_power_P2_at_n": p2_power,
            "target_power": TARGET_POWER,
        },
        "stopping_rule": "fixed_all_36_pairs_no_early_stopping",
        "missing_policy": "any_missing_or_duplicate_pair_is_integrity_failure_D1-S4",
        "freshness": {
            "agent_identities": "fresh_and_disjoint_by_pair_and_environment",
            "source_destination_environment_seeds": "distinct",
            "confirmatory_vs_calibration_seeds": "disjoint",
            "evaluation_trials": "phase_and_pair_scoped_fresh_deterministic_draws",
        },
        "export_integrity": {
            "destination_receives_only_capability_artifact_contract": True,
            "forbidden": [
                "source agent identity",
                "source/environment seed",
                "private practice state",
                "source conversation state",
                "evaluator truth",
                "evaluation answers",
            ],
        },
        "classification": {
            "D1-S0": "source_capability_not_established",
            "D1-S1": "destination_acquisition_not_established",
            "D1-S2": "reproduction_fidelity_not_established",
            "D1-S3": "capability_reproduction_supported",
            "D1-S4": "integrity_failure_unclassifiable",
        },
        "replication_requirement": (
            "D1-S3 is initial discovery support only; a separately "
            "preregistered fresh D1b cohort is required before "
            "internally_replicated registry status"
        ),
        "claim_ceiling": (
            "controlled_deterministic_individual_specialist_substrate_only"
        ),
        "production_historical_substrate_enabled": False,
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    plan_path = args.output_dir / "d1-confirmatory-plan.json"
    plan_path.write_bytes(canonical_bytes(plan))
    report = {
        "schema": "d1-lock-report-v0.1",
        "calibration_sha256": file_sha256(args.calibration),
        "plan_sha256": file_sha256(plan_path),
        "confirmatory_pair_count": n,
        "skill_alias_balance": skill_balance,
        "development_confirmatory_seed_disjoint": True,
        "p2_noninferiority_margin": margin,
        "p2_margin_type": "conventional",
        "calibration_planning_power_P1_at_n": p1_power,
        "calibration_planning_power_P2_at_n": p2_power,
        "confirmatory_execution_authorized": False,
        "production_historical_substrate_enabled": False,
    }
    report_path = args.output_dir / "d1-lock-report.json"
    report_path.write_bytes(canonical_bytes(report))
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
