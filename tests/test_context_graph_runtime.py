"""Release-contract tests for World -> Resonance ContextGraph v0.1.0."""

from __future__ import annotations

import inspect
from dataclasses import dataclass

import pytest

pytest.importorskip("resonance_contextgraph")

from resonance_contextgraph import CheckpointObservation

import resonance_world.context_graph_adapter as adapter
import resonance_world.context_graph_runtime as runtime


@dataclass(frozen=True)
class Claim:
    field_id: str = "field:test"
    subject: str = "agent:a"
    predicate: str = "membership_state"
    object: str = "active"
    observed_by: str = "observer:x"
    source_id: str = "source:1"
    source_class: str = "direct_observation"
    observed_at: int = 10
    confidence: float = 1.0
    direct: bool = True


@dataclass(frozen=True)
class Mission:
    mission_id: str = "mission:test"
    lead_skill: str = "skill:a"
    support_skill: str = "skill:b"


def test_runtime_facade_points_to_stable_observer_release() -> None:
    assert runtime.STANDALONE_REPOSITORY == "ElephantRock/Resonance-ContextGraph"
    assert runtime.STANDALONE_RELEASE == "v0.1.0"
    assert runtime.STANDALONE_RELEASE_COMMIT == "b896891108fd954869a8cd0423f6e8440ab0cdc0"
    assert runtime.STANDALONE_RELEASE_WORKFLOW_RUN == 31641381598
    assert runtime.RELEASE_PARITY_RUN == 31641586497
    assert runtime.INTEGRATION_MODE == "observer-only"
    assert runtime.HISTORICAL_SUBSTRATE_ENABLED is False


def test_adapter_has_no_legacy_or_evaluator_dependency() -> None:
    source = inspect.getsource(adapter)
    forbidden = {
        "context_graph_w3",
        "context_graph_w5",
        "practice_by_skill",
        "JointEnvironment",
        "_oracle_pair",
        ".states",
    }
    assert not {token for token in forbidden if token in source}


def test_structural_claim_and_mission_mapping() -> None:
    claim = adapter.to_evidence_claim(Claim(), delivery=0)
    mission = adapter.to_mission_spec(Mission())

    assert claim.scope_id == "field:test"
    assert claim.source_id == "source:1"
    assert claim.claim_id.startswith("rw-contextgraph-delivery:v1:")
    assert claim.claim_id != claim.source_id
    assert mission.mission_id == "mission:test"
    assert mission.lead_skill == "skill:a"
    assert mission.support_skill == "skill:b"


def test_public_mapper_requires_and_uses_delivery_ordinal() -> None:
    claim = Claim()
    first = adapter.to_evidence_claim(claim, delivery=0)
    second = adapter.to_evidence_claim(claim, delivery=1)

    assert first.source_id == second.source_id == "source:1"
    assert first.claim_id != second.claim_id
    assert first.claim_id.endswith(":0")
    assert second.claim_id.endswith(":1")

    with pytest.raises(TypeError):
        adapter.to_evidence_claim(claim)  # type: ignore[call-arg]


def test_repeated_delivery_gets_unique_transport_identity() -> None:
    store = adapter.build_evidence_store((Claim(), Claim(object="inactive")))
    claims = store.claims(scope_id="field:test")

    assert store.size == 2
    assert [claim.source_id for claim in claims] == ["source:1", "source:1"]
    assert len({claim.claim_id for claim in claims}) == 2
    assert all(claim.claim_id.startswith("rw-contextgraph-delivery:v1:") for claim in claims)
    assert claims[0].claim_id.endswith(":0")
    assert claims[1].claim_id.endswith(":1")


def test_transport_identity_cannot_collide_with_suffix_shaped_source_id() -> None:
    source_like_generated_suffix = "source:1#delivery:1"
    store = adapter.build_evidence_store(
        (
            Claim(source_id="source:1"),
            Claim(source_id="source:1", object="inactive"),
            Claim(
                subject="agent:b",
                source_id=source_like_generated_suffix,
                object="active",
            ),
        )
    )
    claims = store.claims(scope_id="field:test")

    assert store.size == 3
    assert len({claim.claim_id for claim in claims}) == 3
    assert source_like_generated_suffix in {claim.source_id for claim in claims}
    assert source_like_generated_suffix not in {claim.claim_id for claim in claims}


def test_balanced_scheduler_uses_only_observable_event_counts() -> None:
    available = (("agent:a", "skill:a"), ("agent:b", "skill:a"), ("agent:c", "skill:a"))
    counts = {
        ("agent:a", "skill:a"): 3,
        ("agent:b", "skill:a"): 2,
        ("agent:c", "skill:a"): 4,
    }
    assert adapter.next_balanced_cell(
        field_id="field:test",
        available=available,
        reconciled_event_counts=counts,
    ) == ("agent:b", "skill:a")


def test_stopper_preserves_executed_nonnegative_margin_condition() -> None:
    pair = ("agent:a::agent:b",)
    negative_margin = (
        CheckpointObservation(48, pair, minimum_selected_role_score_margin=0.2),
        CheckpointObservation(60, pair, minimum_selected_role_score_margin=-0.01),
    )
    positive_margin = (
        CheckpointObservation(48, pair, minimum_selected_role_score_margin=0.2),
        CheckpointObservation(60, pair, minimum_selected_role_score_margin=0.01),
    )

    blocked = adapter.choose_stopping_point(negative_margin)
    allowed = adapter.choose_stopping_point(positive_margin)

    assert blocked.stop is False
    assert blocked.budget == 60
    assert blocked.reason == "continue"
    assert allowed.stop is True
    assert allowed.budget == 60
    assert allowed.reason == "pair_stability"


def test_stopper_rejects_legacy_pair_vector_tuples() -> None:
    legacy_history = ((48, ("agent:a::agent:b",)), (60, ("agent:a::agent:b",)))

    with pytest.raises(TypeError, match="complete CheckpointObservation"):
        adapter.choose_stopping_point(legacy_history)  # type: ignore[arg-type]
