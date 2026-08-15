"""Pure D2-0 hidden-policy task generation and descriptive calibration metrics."""
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
FAMILIES = (
    "paired_parity_01_23",
    "paired_parity_02_13",
    "paired_parity_03_12",
    "paired_threshold_01_23",
    "overlap_parity_012_123",
    "mixed_parity_threshold",
)


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def sha256(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


@dataclass(frozen=True)
class HiddenPolicy:
    family: str
    flip0: int
    flip1: int
    action_permutation: tuple[str, str, str, str]
    truth_token: str

    def private_record(self) -> dict[str, Any]:
        return {
            "family": self.family,
            "flip0": self.flip0,
            "flip1": self.flip1,
            "action_permutation": list(self.action_permutation),
            "truth_token": self.truth_token,
        }


def policy_for(pair_seed: int) -> HiddenPolicy:
    rng = random.Random(pair_seed)
    family = FAMILIES[rng.randrange(len(FAMILIES))]
    flip0 = rng.randrange(2)
    flip1 = rng.randrange(2)
    permutation = list(ACTIONS)
    rng.shuffle(permutation)
    truth_token = hashlib.sha256(
        f"d2-private-policy:{pair_seed}:{family}:{flip0}:{flip1}:{permutation}".encode()
    ).hexdigest()
    return HiddenPolicy(family, flip0, flip1, tuple(permutation), truth_token)


def _bits(policy: HiddenPolicy, x: tuple[int, int, int, int]) -> tuple[int, int]:
    f0, f1, f2, f3 = x
    if policy.family == "paired_parity_01_23":
        b0 = (f0 + f1) % 2
        b1 = (f2 + f3) % 2
    elif policy.family == "paired_parity_02_13":
        b0 = (f0 + f2) % 2
        b1 = (f1 + f3) % 2
    elif policy.family == "paired_parity_03_12":
        b0 = (f0 + f3) % 2
        b1 = (f1 + f2) % 2
    elif policy.family == "paired_threshold_01_23":
        b0 = int((f0 >= 4) ^ (f1 >= 4))
        b1 = int((f2 >= 4) ^ (f3 >= 4))
    elif policy.family == "overlap_parity_012_123":
        b0 = (f0 + f1 + f2) % 2
        b1 = (f1 + f2 + f3) % 2
    elif policy.family == "mixed_parity_threshold":
        b0 = (f0 + f2) % 2
        b1 = int((f1 >= 4) ^ (f3 >= 4))
    else:
        raise AssertionError(policy.family)
    return b0 ^ policy.flip0, b1 ^ policy.flip1


def correct_action(policy: HiddenPolicy, features: tuple[int, int, int, int]) -> str:
    b0, b1 = _bits(policy, features)
    return policy.action_permutation[b0 + 2 * b1]


def generate_cases(
    *,
    rng_seed: int,
    count: int,
    prefix: str,
    policy: HiddenPolicy,
    exclude_features: set[tuple[int, int, int, int]] | None = None,
) -> list[dict[str, Any]]:
    rng = random.Random(rng_seed)
    excluded = set(exclude_features or set())
    seen: set[tuple[int, int, int, int]] = set()
    cases: list[dict[str, Any]] = []
    while len(cases) < count:
        features = tuple(rng.randrange(8) for _ in FEATURE_NAMES)
        if features in excluded or features in seen:
            continue
        seen.add(features)
        cases.append(
            {
                "case_id": f"{prefix}-{len(cases):03d}",
                "features": dict(zip(FEATURE_NAMES, features, strict=True)),
                "correct_action": correct_action(policy, features),
            }
        )
    return cases


def public_case(case: dict[str, Any]) -> dict[str, Any]:
    return {"case_id": case["case_id"], "features": dict(case["features"])}


def score_actions(cases: list[dict[str, Any]], actions: list[str]) -> float:
    if len(cases) != len(actions):
        raise ValueError("action count mismatch")
    return sum(
        action == case["correct_action"] for case, action in zip(cases, actions, strict=True)
    ) / len(cases)


def labeled_feedback(cases: list[dict[str, Any]], actions: list[str]) -> list[dict[str, Any]]:
    if len(cases) != len(actions):
        raise ValueError("action count mismatch")
    return [
        {
            "case_id": case["case_id"],
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


def features_set(cases: list[dict[str, Any]]) -> set[tuple[int, int, int, int]]:
    return {tuple(int(case["features"][name]) for name in FEATURE_NAMES) for case in cases}


def _mean(values: list[float]) -> float:
    return statistics.fmean(values) if values else math.nan


def _sample_var(values: list[float]) -> float:
    return statistics.variance(values) if len(values) > 1 else math.nan


def _sample_sd(values: list[float]) -> float:
    return statistics.stdev(values) if len(values) > 1 else math.nan


def descriptive_summary(pair_records: list[dict[str, Any]]) -> dict[str, Any]:
    arms = ("fresh", "description_only", "reproduced", "source_developed")
    scores = {
        arm: [float(pair["arms"][arm]["final_score"]) for pair in pair_records] for arm in arms
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


def action_entropy(action_rows: list[list[str]]) -> float:
    flat = [action for row in action_rows for action in row]
    if not flat:
        return math.nan
    counts = {action: flat.count(action) for action in ACTIONS}
    total = len(flat)
    return -sum(
        (count / total) * math.log2(count / total) for count in counts.values() if count
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
