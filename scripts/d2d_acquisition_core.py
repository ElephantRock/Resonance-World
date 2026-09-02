"""Pure deterministic task generation for D2d source capability acquisition."""

from __future__ import annotations

import hashlib
import json
import random
from dataclasses import dataclass
from typing import Any

ACTIONS = ("KAPPA", "MICA", "ORBIT", "VELA")
FEATURE_NAMES = ("f0", "f1", "f2", "f3")
SCHEMA_ORDER = ("threshold_at_4", "parity_pair", "interval_pair", "pairwise_order")
SCHEMA_SEED_BASES = {
    "threshold_at_4": 5_000_000,
    "parity_pair": 5_200_000,
    "interval_pair": 5_400_000,
    "pairwise_order": 5_600_000,
}
PAIRS_PER_SCHEMA = 96
SEED_STEP = 100
DEVELOPMENT_OFFSET = 11
EVALUATION_OFFSET = 41
DEVELOPMENT_MAX_COUNT = 160
EVALUATION_COUNT = 32

PUBLIC_ECOLOGY = {
    "threshold_at_4": (
        "This Field has exactly two hidden controlling feature coordinates among f0..f3. "
        "Each contributes one latent bit indicating whether its value is at least 4. "
        "The two-bit state is mapped one-to-one to the four opaque action tokens. "
        "The controlling coordinates and action relabeling are local secrets and differ by Field."
    ),
    "parity_pair": (
        "This Field has exactly two hidden controlling feature coordinates among f0..f3. "
        "Each contributes one latent bit equal to the coordinate value mod 2. "
        "The two-bit state is mapped one-to-one to the four opaque action tokens. "
        "The controlling coordinates and action relabeling are local secrets and differ by Field."
    ),
    "interval_pair": (
        "This Field has exactly two hidden controlling feature coordinates among f0..f3. "
        "Each contributes one latent bit indicating whether its value lies in 2 through 5 inclusive. "
        "The two-bit state is mapped one-to-one to the four opaque action tokens. "
        "The controlling coordinates and action relabeling are local secrets and differ by Field."
    ),
    "pairwise_order": (
        "This Field partitions f0..f3 into two hidden ordered coordinate pairs. "
        "Each pair contributes one latent bit indicating whether the first coordinate is greater "
        "than or equal to the second. The two-bit state is mapped one-to-one to the four opaque "
        "action tokens. Pair identities/order and action relabeling are local secrets and differ "
        "by Field."
    ),
}

DEVELOPMENT_PROTOCOL = {
    "threshold_at_4": (
        "Use local labeled feedback to infer the two controlling coordinates, their >=4 states, "
        "and the opaque action mapping. Maintain a concise private hypothesis and prefer rules "
        "explaining all labeled examples; do not memorize case IDs."
    ),
    "parity_pair": (
        "Use local labeled feedback to infer the two controlling coordinates, their parity states, "
        "and the opaque action mapping. Maintain a concise private hypothesis and prefer rules "
        "explaining all labeled examples; do not memorize case IDs."
    ),
    "interval_pair": (
        "Use local labeled feedback to infer the two controlling coordinates under the registered "
        "2..5 interval-membership bits and infer the opaque action mapping. Maintain a concise "
        "private hypothesis; do not memorize case IDs."
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
        raise ValueError(f"unknown D2d schema: {schema_id}")
    rng = random.Random(pair_seed)
    if schema_id in {"threshold_at_4", "parity_pair", "interval_pair"}:
        selectors = tuple(rng.sample(range(4), 2))
    else:
        order = list(range(4))
        rng.shuffle(order)
        selectors = tuple(order)
    permutation = list(ACTIONS)
    rng.shuffle(permutation)
    token = hashlib.sha256(
        f"d2d-private:{schema_id}:{pair_seed}:{selectors}:{permutation}".encode()
    ).hexdigest()
    return SchemaPolicy(schema_id, selectors, tuple(permutation), token)


def latent_bits(
    policy: SchemaPolicy, features: tuple[int, int, int, int]
) -> tuple[int, int]:
    if policy.schema_id == "threshold_at_4":
        a, b = policy.selectors
        return int(features[a] >= 4), int(features[b] >= 4)
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
    return {
        tuple(int(case["features"][name]) for name in FEATURE_NAMES)
        for case in cases
    }


def public_case(case: dict[str, Any]) -> dict[str, Any]:
    return {"case_id": case["case_id"], "features": dict(case["features"])}


def labeled_feedback(
    cases: list[dict[str, Any]], actions: list[str]
) -> list[dict[str, Any]]:
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


def score_actions(cases: list[dict[str, Any]], actions: list[str]) -> float:
    if len(cases) != len(actions):
        raise ValueError("action count mismatch")
    if any(action not in ACTIONS for action in actions):
        raise ValueError("unknown action")
    return sum(
        action == case["correct_action"]
        for case, action in zip(cases, actions, strict=True)
    ) / len(cases)


def schema_and_local_index(global_pair_index: int) -> tuple[str, int]:
    pair_count = len(SCHEMA_ORDER) * PAIRS_PER_SCHEMA
    if not 0 <= global_pair_index < pair_count:
        raise ValueError("global D2d pair index out of range")
    schema_slot, local_index = divmod(global_pair_index, PAIRS_PER_SCHEMA)
    return SCHEMA_ORDER[schema_slot], local_index


def pair_seed_for(schema_id: str, local_pair_index: int) -> int:
    if schema_id not in SCHEMA_SEED_BASES:
        raise ValueError(f"unknown schema: {schema_id}")
    if not 0 <= local_pair_index < PAIRS_PER_SCHEMA:
        raise ValueError("local pair index out of range")
    return SCHEMA_SEED_BASES[schema_id] + local_pair_index * SEED_STEP


def oracle_instruction(policy: SchemaPolicy) -> str:
    if policy.schema_id == "threshold_at_4":
        rule = "Each selected coordinate contributes 1 iff its value is >= 4."
    elif policy.schema_id == "parity_pair":
        rule = "Each selected coordinate contributes its value modulo 2."
    elif policy.schema_id == "interval_pair":
        rule = "Each selected coordinate contributes 1 iff its value is in 2..5 inclusive."
    else:
        a, b, c, d = policy.selectors
        rule = (
            f"The ordered comparisons are f{a} >= f{b} and f{c} >= f{d}; "
            "each comparison contributes one bit."
        )
    selectors = ", ".join(f"f{i}" for i in policy.selectors)
    mapping = {
        "00": policy.action_permutation[0],
        "10": policy.action_permutation[1],
        "01": policy.action_permutation[2],
        "11": policy.action_permutation[3],
    }
    return (
        "Oracle diagnostic: use the exact private Field policy. "
        f"Schema={policy.schema_id}; selectors/order={selectors}. {rule} "
        "Index the action mapping as bit0 + 2*bit1. "
        f"Mapping={json.dumps(mapping, sort_keys=True, separators=(',', ':'))}. "
        "Do not infer a different rule."
    )
