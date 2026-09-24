"""Fresh deterministic namespace for D2-vNext-Q2 acquisition qualification."""

from __future__ import annotations

import d2d_acquisition_core as base

ACTIONS = base.ACTIONS
FEATURE_NAMES = base.FEATURE_NAMES
SCHEMA_ORDER = base.SCHEMA_ORDER
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

NAMESPACE = "rw.d2-vnext-q2-empty-regeneration-qualification.v1"
STAGE_A = "Q2-A"
STAGE_B = "Q2-B"
STAGES = (STAGE_A, STAGE_B)
PAIRS_PER_SCHEMA_BY_STAGE = {STAGE_A: 16, STAGE_B: 96}

STAGE_SCHEMA_SEED_BASES = {
    STAGE_A: {
        "threshold_at_4": 13_000_000,
        "parity_pair": 13_200_000,
        "interval_pair": 13_400_000,
        "pairwise_order": 13_600_000,
    },
    STAGE_B: {
        "threshold_at_4": 14_000_000,
        "parity_pair": 14_200_000,
        "interval_pair": 14_400_000,
        "pairwise_order": 14_600_000,
    },
}


def pairs_per_schema(stage: str) -> int:
    try:
        return PAIRS_PER_SCHEMA_BY_STAGE[stage]
    except KeyError as exc:
        raise ValueError(f"unknown D2-vNext-Q2 stage: {stage}") from exc


def pair_count(stage: str) -> int:
    return len(SCHEMA_ORDER) * pairs_per_schema(stage)


def schema_and_local_index(stage: str, global_pair_index: int) -> tuple[str, int]:
    """Interleave schemas so every consecutive 16-pair shard has four of each schema."""
    count = pair_count(stage)
    if not 0 <= global_pair_index < count:
        raise ValueError("global D2-vNext-Q2 pair index out of range")
    schema_slot = global_pair_index % len(SCHEMA_ORDER)
    local_index = global_pair_index // len(SCHEMA_ORDER)
    return SCHEMA_ORDER[schema_slot], local_index


def pair_seed_for(stage: str, schema_id: str, local_pair_index: int) -> int:
    try:
        bases = STAGE_SCHEMA_SEED_BASES[stage]
    except KeyError as exc:
        raise ValueError(f"unknown D2-vNext-Q2 stage: {stage}") from exc
    if schema_id not in bases:
        raise ValueError(f"unknown D2-vNext-Q2 schema: {schema_id}")
    if not 0 <= local_pair_index < pairs_per_schema(stage):
        raise ValueError("local D2-vNext-Q2 pair index out of range")
    return bases[schema_id] + local_pair_index * SEED_STEP
