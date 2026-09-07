"""Fresh deterministic namespace for the D2d-S2 acquisition calibration."""

from __future__ import annotations

import d2d_acquisition_core as base

ACTIONS = base.ACTIONS
FEATURE_NAMES = base.FEATURE_NAMES
SCHEMA_ORDER = base.SCHEMA_ORDER
PAIRS_PER_SCHEMA = base.PAIRS_PER_SCHEMA
SEED_STEP = base.SEED_STEP
DEVELOPMENT_OFFSET = base.DEVELOPMENT_OFFSET
EVALUATION_OFFSET = base.EVALUATION_OFFSET
DEVELOPMENT_MAX_COUNT = base.DEVELOPMENT_MAX_COUNT
EVALUATION_COUNT = base.EVALUATION_COUNT
PUBLIC_ECOLOGY = base.PUBLIC_ECOLOGY
DEVELOPMENT_PROTOCOL = base.DEVELOPMENT_PROTOCOL
SchemaPolicy = base.SchemaPolicy
canonical_bytes = base.canonical_bytes
sha256 = base.sha256
policy_for = base.policy_for
latent_bits = base.latent_bits
correct_action = base.correct_action
generate_balanced_cases = base.generate_balanced_cases
features_set = base.features_set
public_case = base.public_case
labeled_feedback = base.labeled_feedback
score_actions = base.score_actions
oracle_instruction = base.oracle_instruction

SCHEMA_SEED_BASES = {
    "threshold_at_4": 6_000_000,
    "parity_pair": 6_200_000,
    "interval_pair": 6_400_000,
    "pairwise_order": 6_600_000,
}


def schema_and_local_index(global_pair_index: int) -> tuple[str, int]:
    pair_count = len(SCHEMA_ORDER) * PAIRS_PER_SCHEMA
    if not 0 <= global_pair_index < pair_count:
        raise ValueError("global D2d-S2 pair index out of range")
    schema_slot, local_index = divmod(global_pair_index, PAIRS_PER_SCHEMA)
    return SCHEMA_ORDER[schema_slot], local_index


def pair_seed_for(schema_id: str, local_pair_index: int) -> int:
    if schema_id not in SCHEMA_SEED_BASES:
        raise ValueError(f"unknown D2d-S2 schema: {schema_id}")
    if not 0 <= local_pair_index < PAIRS_PER_SCHEMA:
        raise ValueError("local D2d-S2 pair index out of range")
    return SCHEMA_SEED_BASES[schema_id] + local_pair_index * SEED_STEP
