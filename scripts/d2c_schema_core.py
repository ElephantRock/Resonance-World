"""Pure deterministic task generation for D2c G2 schema generalization."""

from __future__ import annotations

import hashlib
import json
import random
from dataclasses import dataclass
from typing import Any

ACTIONS = ("KAPPA", "MICA", "ORBIT", "VELA")
FEATURE_NAMES = ("f0", "f1", "f2", "f3")
SCHEMA_ORDER = ("parity_pair", "interval_pair", "pairwise_order")
SCHEMA_SEED_BASES = {
    "parity_pair": 4_200_000,
    "interval_pair": 4_400_000,
    "pairwise_order": 4_600_000,
}
PAIRS_PER_SCHEMA = 180
SEED_STEP = 100
SOURCE_OFFSET = 1
DESTINATION_OFFSET = 2
EVALUATION_OFFSET = 3

PUBLIC_ECOLOGY = {
    "parity_pair": (
        "The registered D2c parity-pair family has exactly two hidden controlling feature "
        "coordinates among f0..f3. Each contributes one latent bit equal to the coordinate "
        "value mod 2. The two-bit state is mapped one-to-one to the four opaque action tokens. "
        "The controlling coordinates and action relabeling are local secrets and differ by Field."
    ),
    "interval_pair": (
        "The registered D2c interval-pair family has exactly two hidden controlling feature "
        "coordinates among f0..f3. Each contributes one latent bit indicating whether its value "
        "lies in the registered interval 2 through 5 inclusive. The two-bit state is mapped "
        "one-to-one to the four opaque action tokens. The controlling coordinates and action "
        "relabeling are local secrets and differ by Field."
    ),
    "pairwise_order": (
        "The registered D2c pairwise-order family partitions f0..f3 into two hidden ordered "
        "coordinate pairs. Each pair contributes one latent bit indicating whether the first "
        "coordinate is greater than or equal to the second. The two-bit state is mapped "
        "one-to-one to the four opaque action tokens. Pair identities/order and action relabeling "
        "are local secrets and differ by Field."
    ),
}

DEVELOPMENT_PROTOCOL = {
    "parity_pair": (
        "Use local labeled feedback to infer which two coordinates control outcomes, their parity "
        "states, and the opaque action mapping. Maintain a concise private hypothesis and prefer "
        "rules explaining all labeled examples; do not memorize case IDs."
    ),
    "interval_pair": (
        "Use local labeled feedback to infer which two coordinates control outcomes under the "
        "registered 2..5 interval-membership bits and infer the opaque action mapping. Maintain "
        "a concise private hypothesis; do not memorize case IDs."
    ),
    "pairwise_order": (
        "Use local labeled feedback to infer the two hidden ordered coordinate comparisons and "
        "the opaque action mapping. Maintain a concise private hypothesis and prefer rules that "
        "explain all labeled examples; do not memorize case IDs."
    ),
}


def canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def sha256(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


@dataclass(frozen=True)
class SchemaPolicy:
    schema_id: str
    selectors: tuple[int, ...]
    action_permutation: tuple[str, str, str, str]
    truth_token: str

    def private_record(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "selectors": list(self.selectors),
            "action_permutation": list(self.action_permutation),
            "truth_token": self.truth_token,
        }


def policy_for(schema_id: str, pair_seed: int) -> SchemaPolicy:
    if schema_id not in SCHEMA_ORDER:
        raise ValueError(f"unknown D2c schema: {schema_id}")
    rng = random.Random(pair_seed)
    if schema_id in {"parity_pair", "interval_pair"}:
        selectors = tuple(rng.sample(range(4), 2))
    else:
        order = list(range(4))
        rng.shuffle(order)
        selectors = tuple(order)
    permutation = list(ACTIONS)
    rng.shuffle(permutation)
    token = hashlib.sha256(
        f"d2c-private:{schema_id}:{pair_seed}:{selectors}:{permutation}".encode()
    ).hexdigest()
    return SchemaPolicy(schema_id, selectors, tuple(permutation), token)


def latent_bits(policy: SchemaPolicy, features: tuple[int, int, int, int]) -> tuple[int, int]:
    if policy.schema_id == "parity_pair":
        a, b = policy.selectors
        return features[a] % 2, features[b] % 2
    if policy.schema_id == "interval_pair":
        a, b = policy.selectors
        return int(2 <= features[a] <= 5), int(2 <= features[b] <= 5)
    if policy.schema_id == "pairwise_order":
        a, b, c, d = policy.selectors
        return int(features[a] >= features[b]), int(features[c] >= features[d])
    raise AssertionError("unreachable schema")


def correct_action(policy: SchemaPolicy, features: tuple[int, int, int, int]) -> str:
    b0, b1 = latent_bits(policy, features)
    return policy.action_permutation[b0 + 2 * b1]


def generate_balanced_cases(
    *,
    rng_seed: int,
    count: int,
    prefix: str,
    policy: SchemaPolicy,
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


def features_set(cases: list[dict[str, Any]]) -> set[tuple[int, int, int, int]]:
    return {tuple(int(case["features"][name]) for name in FEATURE_NAMES) for case in cases}


def score_actions(cases: list[dict[str, Any]], actions: list[str]) -> float:
    if len(cases) != len(actions):
        raise ValueError("action count mismatch")
    return sum(
        action == case["correct_action"] for case, action in zip(cases, actions, strict=True)
    ) / len(cases)


def public_case(case: dict[str, Any]) -> dict[str, Any]:
    return {"case_id": case["case_id"], "features": dict(case["features"])}


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


def schema_and_local_index(global_pair_index: int) -> tuple[str, int]:
    if not 0 <= global_pair_index < len(SCHEMA_ORDER) * PAIRS_PER_SCHEMA:
        raise ValueError("global D2c pair index out of range")
    schema_slot, local_index = divmod(global_pair_index, PAIRS_PER_SCHEMA)
    return SCHEMA_ORDER[schema_slot], local_index


def pair_seed_for(schema_id: str, local_pair_index: int) -> int:
    if schema_id not in SCHEMA_SEED_BASES:
        raise ValueError(f"unknown schema: {schema_id}")
    if not 0 <= local_pair_index < PAIRS_PER_SCHEMA:
        raise ValueError("local pair index out of range")
    return SCHEMA_SEED_BASES[schema_id] + local_pair_index * SEED_STEP
