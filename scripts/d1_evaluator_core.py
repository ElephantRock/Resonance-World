"""Frozen deterministic D1 confirmatory evaluator."""
from __future__ import annotations

import hashlib
import json
import math
import random
import statistics
from pathlib import Path
from statistics import NormalDist
from typing import Any

BOOTSTRAP_REPS = 100_000
BOOTSTRAP_SEEDS = {
    "P0_source_development": 110_701,
    "P1_destination_acquisition": 110_702,
    "P2_reproduction_fidelity": 110_703,
}


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def percentile(sorted_values: list[float], probability: float) -> float:
    if not sorted_values:
        raise ValueError("percentile requires values")
    position = probability * (len(sorted_values) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return sorted_values[lower]
    weight = position - lower
    return sorted_values[lower] * (1.0 - weight) + sorted_values[upper] * weight


def bootstrap_mean_bounds(values: list[float], *, seed: int) -> dict[str, float]:
    rng = random.Random(seed)
    n = len(values)
    means: list[float] = []
    for _ in range(BOOTSTRAP_REPS):
        means.append(sum(values[rng.randrange(n)] for _ in range(n)) / n)
    means.sort()
    return {
        "lower_one_sided_95": percentile(means, 0.05),
        "lower_two_sided_95": percentile(means, 0.025),
        "upper_two_sided_95": percentile(means, 0.975),
    }


def summarize(values: list[float], *, name: str, null_boundary: float) -> dict[str, Any]:
    n = len(values)
    estimate = statistics.mean(values)
    sd = statistics.stdev(values) if n > 1 else 0.0
    se = sd / math.sqrt(n) if n else math.inf
    z95 = NormalDist().inv_cdf(0.95)
    z975 = NormalDist().inv_cdf(0.975)
    if se == 0.0:
        one_sided_lcb = estimate
        ci = [estimate, estimate]
        p = 0.0 if estimate > null_boundary else 1.0
    else:
        one_sided_lcb = estimate - z95 * se
        ci = [estimate - z975 * se, estimate + z975 * se]
        z = (estimate - null_boundary) / se
        p = 1.0 - NormalDist().cdf(z)
    boot = bootstrap_mean_bounds(values, seed=BOOTSTRAP_SEEDS[name])
    passed = one_sided_lcb > null_boundary and boot["lower_one_sided_95"] > null_boundary
    return {
        "estimand": name,
        "paired_n": n,
        "estimate": estimate,
        "sample_sd": sd,
        "standard_error": se,
        "null_boundary": null_boundary,
        "normal_one_sided_95_lower_bound": one_sided_lcb,
        "normal_two_sided_95_ci": ci,
        "normal_approx_one_sided_p": p,
        "bootstrap_replicates": BOOTSTRAP_REPS,
        "bootstrap_seed": BOOTSTRAP_SEEDS[name],
        "bootstrap_one_sided_95_lower_bound": boot["lower_one_sided_95"],
        "bootstrap_two_sided_95_ci": [
            boot["lower_two_sided_95"],
            boot["upper_two_sided_95"],
        ],
        "gate_passed": passed,
    }


def evaluate(
    *,
    plan_path: Path,
    lock_path: Path,
    output_path: Path,
    candidate_head: str,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    plan = load(plan_path)
    lock = load(lock_path)
    output = load(output_path)
    rows = list(output.get("rows", []))

    expected_seeds = [int(x) for x in plan["confirmatory_pair_seeds"]]
    actual_seeds = [int(row["pair_seed"]) for row in rows]
    forbidden_field_names = {
        "practice_by_skill",
        "private_practice_state",
        "source_conversation_state",
        "source_seed",
        "source_environment_seed",
        "evaluator_truth",
        "evaluation_answers",
    }
    artifact_audit: list[dict[str, Any]] = []
    for row in rows:
        artifact = row["capability_artifact"]
        text = json.dumps(artifact, sort_keys=True)
        leaked_fields = sorted(
            field for field in forbidden_field_names if f'"{field}":' in text
        )
        source_identity_present = str(row["source_agent_id"]) in text
        artifact_audit.append(
            {
                "pair_seed": row["pair_seed"],
                "leaked_forbidden_fields": leaked_fields,
                "source_identity_present": source_identity_present,
                "private_state_transfer_allowed": artifact["required_substrate"][
                    "private_state_transfer_allowed"
                ],
            }
        )

    gates = {
        "gate_0_candidate_identity": output.get("candidate_head") == candidate_head,
        "gate_1_plan_identity": output.get("plan_sha256") == file_sha256(plan_path)
        and lock.get("plan_sha256") == file_sha256(plan_path),
        "gate_2_pair_count_and_seed_identity": len(rows) == 36
        and actual_seeds == expected_seeds
        and len(set(actual_seeds)) == 36,
        "gate_3_development_confirmatory_seed_disjoint": bool(
            plan["development_confirmatory_seed_disjoint"]
        ),
        "gate_4_skill_alias_balance": plan["skill_alias_balance"]
        == {"skill-a": 12, "skill-b": 12, "skill-c": 12},
        "gate_5_source_destination_identity_disjoint": all(
            row["source_destination_identity_disjoint"] for row in rows
        ),
        "gate_6_private_and_reconstructive_export_absent": all(
            not item["leaked_forbidden_fields"]
            and not item["source_identity_present"]
            and item["private_state_transfer_allowed"] is False
            for item in artifact_audit
        ),
        "gate_7_artifact_schema": all(
            row["capability_artifact"]["schema"] == plan["capability_artifact_schema"]
            for row in rows
        ),
        "gate_8_oracle_product_ineligible": plan["oracle_product_eligible"] is False
        and output["execution_integrity"]["oracle_product_eligible"] is False,
        "gate_9_execution_integrity": bool(
            output["execution_integrity"]["all_source_destination_identities_disjoint"]
        )
        and bool(output["execution_integrity"]["all_forbidden_private_export_keys_absent"]),
        "gate_10_production_historical_substrate_off": plan[
            "production_historical_substrate_enabled"
        ]
        is False
        and output["execution_integrity"]["production_historical_substrate_enabled"]
        is False,
    }

    integrity_passed = all(gates.values())
    scores = {
        arm: [float(row["scores"][arm]) for row in rows]
        for arm in plan["arms"]
    }
    source_uplift = [
        a - b
        for a, b in zip(
            scores["source_developed"], scores["fresh_no_development"], strict=True
        )
    ]
    reproduced_uplift = [
        a - b
        for a, b in zip(
            scores["reproduced_protocol"], scores["fresh_no_development"], strict=True
        )
    ]
    reproduction_gap = [
        a - b
        for a, b in zip(
            scores["reproduced_protocol"], scores["source_developed"], strict=True
        )
    ]
    margin = float(plan["statistical_contract"]["P2"]["noninferiority_margin"])
    P0 = summarize(source_uplift, name="P0_source_development", null_boundary=0.0)
    P1 = summarize(
        reproduced_uplift, name="P1_destination_acquisition", null_boundary=0.0
    )
    P2 = summarize(
        reproduction_gap,
        name="P2_reproduction_fidelity",
        null_boundary=-margin,
    )

    if not integrity_passed:
        code = "D1-S4"
        classification = "d1_integrity_failure_unclassifiable"
    elif not P0["gate_passed"]:
        code = "D1-S0"
        classification = "d1_source_capability_not_established"
    elif not P1["gate_passed"]:
        code = "D1-S1"
        classification = "d1_destination_acquisition_not_established"
    elif not P2["gate_passed"]:
        code = "D1-S2"
        classification = "d1_reproduction_fidelity_not_established"
    else:
        code = "D1-S3"
        classification = "d1_capability_reproduction_supported"

    means = {arm: statistics.mean(values) for arm, values in scores.items()}
    denominator = means["source_developed"] - means["fresh_no_development"]
    fidelity_ratio = (
        (means["reproduced_protocol"] - means["fresh_no_development"]) / denominator
        if denominator != 0
        else None
    )
    by_skill: dict[str, dict[str, float]] = {}
    for skill in ("skill-a", "skill-b", "skill-c"):
        subset = [row for row in rows if row["target_skill"] == skill]
        by_skill[skill] = {
            arm: statistics.mean(float(row["scores"][arm]) for row in subset)
            for arm in plan["arms"]
        }
        by_skill[skill]["artifact_target_match_rate"] = statistics.mean(
            1.0 if row["artifact_target_matches_source_target"] else 0.0
            for row in subset
        )

    result = {
        "schema": "d1-result-v0.1",
        "candidate_head": candidate_head,
        "classification_code": code,
        "classification": classification,
        "scientific_claim": "bounded_candidate_evidence_only_no_registry_self_promotion",
        "gates": gates,
        "P0_source_development": P0,
        "P1_destination_acquisition": P1,
        "P2_reproduction_fidelity": P2,
        "means": means,
        "fidelity_ratio_descriptive": fidelity_ratio,
        "by_skill_descriptive": by_skill,
        "p2_margin": margin,
        "p2_margin_type": plan["statistical_contract"]["P2"]["margin_type"],
        "p2_retention_fraction_conventional": plan["statistical_contract"]["P2"][
            "retention_fraction"
        ],
        "replication_requirement": plan["replication_requirement"],
        "claim_ceiling": plan["claim_ceiling"],
        "pair_count": len(rows),
        "production_historical_substrate_enabled": False,
    }
    audit = {
        "schema": "d1-audit-v0.1",
        "candidate_head": candidate_head,
        "plan_sha256": file_sha256(plan_path),
        "lock_sha256": file_sha256(lock_path),
        "output_sha256": file_sha256(output_path),
        "artifact_audit": artifact_audit,
        "pair_seeds": actual_seeds,
        "classification_code": code,
    }
    manifest = {
        "schema": "d1-evaluation-manifest-v0.1",
        "candidate_head": candidate_head,
        "input_sha256": {
            "plan": file_sha256(plan_path),
            "lock": file_sha256(lock_path),
            "confirmatory_output": file_sha256(output_path),
        },
        "classification_code": code,
        "classification": classification,
    }
    return result, audit, manifest
