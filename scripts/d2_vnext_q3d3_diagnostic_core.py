"""Fresh deterministic pairwise-only namespace for D2-vNext-Q3-D3 diagnostics."""
from __future__ import annotations

import d2d_acquisition_core as base

ACTIONS = base.ACTIONS
FEATURE_NAMES = base.FEATURE_NAMES
SCHEMA_ORDER = ("pairwise_order",)
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

NAMESPACE = "rw.d2-vnext-q3d3-http-sdk-boundary-diagnostic.v1"
STAGE = "Q3-D3"
SCHEMA_ID = "pairwise_order"
PAIR_COUNT = 8
PAIR_SEED_BASE = 17_000_000


def pair_count() -> int:
    return PAIR_COUNT


def pairs_per_schema() -> int:
    return PAIR_COUNT


def schema_and_local_index(global_pair_index: int) -> tuple[str, int]:
    if not 0 <= global_pair_index < PAIR_COUNT:
        raise ValueError("global D2-vNext-Q3-D3 pair index out of range")
    return SCHEMA_ID, global_pair_index


def pair_seed_for(local_pair_index: int) -> int:
    if not 0 <= local_pair_index < PAIR_COUNT:
        raise ValueError("local D2-vNext-Q3-D3 pair index out of range")
    return PAIR_SEED_BASE + local_pair_index * SEED_STEP
