"""Pure D2-0 learnability-revision task generation and descriptive metrics."""
from __future__ import annotations

import hashlib
import json
import math
import random
import statistics
from dataclasses import dataclass
from typing import Any

ACTIONS = ("KAPPA", "MICA", "ORBIT", "VELA")
FEATURE_NAMES = ("f0", "f1", "f2", "f3")
CHANCE_SCORE = 1.0 / len(ACTIONS)


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def sha256(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


@dataclass(frozen=True)
class LearnablePolicy:
    feature_a: int
    feature_b: int
    action_permutation: tuple[str, str, str, str]
    truth_token: str

    def private_record(self) -> dict[str, Any]:
        return {
            "feature_a": self.feature_a,
            "feature_b": self.feature_b,
            "threshold": 4,
            "action_permutation": list(self.action_permutation),
            "truth_token": self.truth_token,
        }


def policy_for(pair_seed: int) -> LearnablePolicy:
    rng = random.Random(pair_seed)
    feature_a, feature_b = rng.sample(range(len(FEATURE_NAMES)), 2)
    permutation = list(ACTIONS)
    rng.shuffle(permutation)
    token = hashlib.sha256(
        f"d2-r2-private:{pair_seed}:{feature_a}:{feature_b}:{permutation}".encode()
    ).hexdigest()
    return LearnablePolicy(feature_a, feature_b, tuple(permutation), token)


def latent_bits(policy: LearnablePolicy, features: tuple[int, int, int, int]) -> tuple[int, int]:
    return int(features[policy.feature_a] >= 4), int(features[policy.feature_b] >= 4)


def correct_action(policy: LearnablePolicy, features: tuple[int, int, int, int]) -> str:
    b0, b1 = latent_bits(policy, features)
    return policy.action_permutation[b0 + 2 * b1]


def generate_balanced_cases(
    *,
    rng_seed: int,
    count: int,
    prefix: str,
    policy: LearnablePolicy,
    exclude_features: set[tuple[int, int, int, int]] | None = None,
) -> list[dict[str, Any]]:
    if count % 4:
        raise ValueError("count must be divisible by four")
    rng = random.Random(rng_seed)
    excluded = set(exclude_features or set())
    seen: set[tuple[int, int, int, int]] = set()
    quota = {action: count // 4 for action in ACTIONS}
    cases: list[dict[str, Any]] = []
    while len(cases) < count:
        features = tuple(rng.randrange(8) for _ in FEATURE_NAMES)
        if features in excluded or features in seen:
            continue
        action = correct_action(policy, features)
        if quota[action] <= 0:
            continue
        quota[action] -= 1
        seen.add(features)
        cases.append(
            {
                "case_id": f"{prefix}-{len(cases):03d}",
                "features": dict(zip(FEATURE_NAMES, features, strict=True)),
                "correct_action": action,
            }
        )
    return cases


def public_case(case: dict[str, Any]) -> dict[str, Any]:
    return {"case_id": case["case_id"], "features": dict(case["features"])}


def features_set(cases: list[dict[str, Any]]) -> set[tuple[int, int, int, int]]:
    return {
        tuple(int(case["features"][name]) for name in FEATURE_NAMES)
        for case in cases
    }


def score_actions(cases: list[dict[str, Any]], actions: list[str]) -> float:
    if len(cases) != len(actions):
        raise ValueError("action count mismatch")
    return sum(
        action == case["correct_action"]
        for case, action in zip(cases, actions, strict=True)
    ) / len(cases)


def labeled_feedback(cases: list[dict[str, Any]], actions: list[str]) -> list[dict[str, Any]]:
    if len(cases) != len(actions):
        raise ValueError("action count mismatch")
    return [
        {
            "case_id": case["case_id"],
            "features": dict(case["features"]),
            "chosen_action": action,
            "correct": action == case["correct_action"],
            "correct_action": case["correct_action"],
        }
        for case, action in zip(cases, actions, strict=True)
    ]


def unlabeled_history(cases: list[dict[str, Any]], actions: list[str]) -> list[dict[str, Any]]:
    return [
        {"case": public_case(case), "chosen_action": action}
        for case, action in zip(cases, actions, strict=True)
    ]


def _mean(values: list[float]) -> float:
    return statistics.fmean(values) if values else math.nan


def _sample_var(values: list[float]) -> float:
    return statistics.variance(values) if len(values) > 1 else math.nan


def _sample_sd(values: list[float]) -> float:
    return statistics.stdev(values) if len(values) > 1 else math.nan


def descriptive_summary(pair_records: list[dict[str, Any]]) -> dict[str, Any]:
    arms = ("fresh", "description_only", "reproduced", "source_developed")
    scores = {
        arm: [float(pair["arms"][arm]["final_score"]) for pair in pair_records]
        for arm in arms
    }
    contrasts = {
        "p0_source_minus_fresh": [
            pair["arms"]["source_developed"]["final_score"]
            - pair["arms"]["fresh"]["final_score"]
            for pair in pair_records
        ],
        "p1_reproduced_minus_description": [
            pair["arms"]["reproduced"]["final_score"]
            - pair["arms"]["description_only"]["final_score"]
            for pair in pair_records
        ],
        "p2_reproduced_minus_source": [
            pair["arms"]["reproduced"]["final_score"]
            - pair["arms"]["source_developed"]["final_score"]
            for pair in pair_records
        ],
    }
    return {
        "pair_count": len(pair_records),
        "arm_scores": {
            arm: {
                "mean": _mean(values),
                "sample_variance": _sample_var(values),
                "sample_sd": _sample_sd(values),
                "min": min(values),
                "max": max(values),
                "values": values,
            }
            for arm, values in scores.items()
        },
        "paired_contrasts": {
            name: {
                "mean": _mean(values),
                "sample_variance": _sample_var(values),
                "sample_sd": _sample_sd(values),
                "min": min(values),
                "max": max(values),
                "values": values,
            }
            for name, values in contrasts.items()
        },
    }


def development_readiness(pair_records: list[dict[str, Any]]) -> dict[str, Any]:
    source_final = [
        float(pair["arms"]["source_developed"]["final_score"]) for pair in pair_records
    ]
    fresh_final = [float(pair["arms"]["fresh"]["final_score"]) for pair in pair_records]
    first_batches = [
        float(pair["arms"]["source_developed"]["development_batch_scores"][0])
        for pair in pair_records
    ]
    p0 = [s - f for s, f in zip(source_final, fresh_final, strict=True)]
    positives = sum(value > 0.0 for value in p0)
    mean_source = _mean(source_final)
    mean_p0 = _mean(p0)
    trajectory_gain = mean_source - _mean(first_batches)
    gates = {
        "mean_source_at_least_0_50": mean_source >= 0.50,
        "mean_source_minus_fresh_at_least_0_15": mean_p0 >= 0.15,
        "positive_pairs_at_least_6_of_8": positives >= 6,
        "mean_final_minus_first_batch_at_least_0_10": trajectory_gain >= 0.10,
    }
    return {
        "threshold_class": "conventional_development_readiness_not_inferential",
        "chance_score": CHANCE_SCORE,
        "mean_source_final": mean_source,
        "mean_source_minus_fresh": mean_p0,
        "positive_pairs": positives,
        "mean_final_minus_first_batch": trajectory_gain,
        "gates": gates,
        "all_gates_pass": all(gates.values()),
    }


def action_entropy(action_rows: list[list[str]]) -> float:
    flat = [action for row in action_rows for action in row]
    if not flat:
        return math.nan
    total = len(flat)
    counts = {action: flat.count(action) for action in ACTIONS}
    return -sum(
        (count / total) * math.log2(count / total)
        for count in counts.values()
        if count
    )


def sampling_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        grouped.setdefault(str(record["temperature"]), []).append(record)
    result: dict[str, Any] = {}
    for temperature, rows in grouped.items():
        valid_rows = [row for row in rows if row["valid"]]
        tuples = [tuple(row["actions"]) for row in valid_rows]
        action_rows = [list(row["actions"]) for row in valid_rows]
        scores = [float(row["score"]) for row in valid_rows]
        unique_count = len(set(tuples))
        result[temperature] = {
            "replicates": len(rows),
            "valid_contract_rate": len(valid_rows) / len(rows),
            "unique_response_rate": unique_count / len(valid_rows) if valid_rows else 0.0,
            "repeat_response_rate": 1.0 - unique_count / len(valid_rows) if valid_rows else 1.0,
            "action_entropy_bits": action_entropy(action_rows),
            "between_replicate_score_variance": _sample_var(scores),
            "mean_score": _mean(scores),
            "physical_attempts": sum(int(row["physical_attempts"]) for row in rows),
        }
    return result
