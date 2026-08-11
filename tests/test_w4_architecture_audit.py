# ruff: noqa: I001

from copy import deepcopy
from pathlib import Path

import pytest

from resonance_world.w4_architecture_audit import load_manifest, validate_manifest


MANIFEST = Path("configs/w4/relationship-state-audit.json")


def test_current_architecture_is_class_a_and_blocks_behavioral_w4() -> None:
    result = validate_manifest(load_manifest(MANIFEST))

    assert result.classification == "A_NO_NATIVE_PAIR_STATE"
    assert result.native_relationship_state_count == 0
    assert result.world_proxy_count == 1
    assert not result.behavioral_w4_allowed
    assert "relationship_reset" in result.blocked_behavioral_operations
    assert "joint_memory_ablation" in result.blocked_behavioral_operations


def test_w3_coordination_exposure_cannot_be_reclassified_as_native_state() -> None:
    manifest = load_manifest(MANIFEST)
    tampered = deepcopy(manifest)
    proxy = next(
        item for item in tampered["primitives"] if item["name"] == "w3_coordination_exposure"
    )
    proxy["origin"] = "field_native"
    proxy["native_relationship_state"] = True

    with pytest.raises(ValueError, match="classification|native_relationship_state"):
        validate_manifest(tampered)


def test_field_evidence_is_not_equivalent_to_learned_pair_state() -> None:
    manifest = load_manifest(MANIFEST)
    interaction = next(
        item
        for item in manifest["primitives"]
        if item["name"] == "requester_winner_interaction_history"
    )

    assert interaction["origin"] == "field_evidence"
    assert interaction["relationship_specific"] is True
    assert interaction["native_relationship_state"] is False
    assert interaction["independently_manipulable"] is False


def test_w4a_must_not_directly_reward_relationship_history() -> None:
    manifest = load_manifest(MANIFEST)
    tampered = deepcopy(manifest)
    tampered["next_phase"]["required_affordances"].remove(
        "no_direct_relationship_success_bonus"
    )

    with pytest.raises(ValueError, match="direct relationship-success bonus"):
        validate_manifest(tampered)


def test_behavioral_w4_cannot_be_enabled_without_native_pair_state() -> None:
    manifest = load_manifest(MANIFEST)
    tampered = deepcopy(manifest)
    tampered["next_phase"]["behavioral_w4_allowed"] = True

    with pytest.raises(ValueError, match="behavioral W4 cannot proceed"):
        validate_manifest(tampered)
