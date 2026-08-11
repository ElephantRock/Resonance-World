from __future__ import annotations

import inspect
import json

import pytest

from resonance_world.w4a_joint_learning import IndividualState, JointEnvironment
from resonance_world.w6_mobility import (
    MobilityContract,
    MobilityRegistry,
    PortableAgentState,
)


def _state(*, evidence: tuple[str, ...] = ("field://home/evidence",)) -> PortableAgentState:
    return PortableAgentState.from_individual(
        IndividualState(
            agent_id="agent-01",
            practice_by_skill={"water": 4, "energy": 2},
        ),
        home_field_id="field-home",
        evidence_refs=evidence,
    )


def _contract(
    contract_id: str,
    mode: str,
    origin: str,
    destination: str,
) -> MobilityContract:
    return MobilityContract(
        contract_id=contract_id,
        agent_id="agent-01",
        mode=mode,  # type: ignore[arg-type]
        origin_field_id=origin,
        destination_field_id=destination,
        evidence_ref=f"world://mobility/{contract_id}",
    )


def test_secondment_moves_availability_without_changing_portable_state() -> None:
    registry = MobilityRegistry()
    state = _state()
    registry.register_home_agent(state)
    before = state.digest()

    event = registry.execute(
        _contract("secondment-1", "secondment", "field-home", "field-host")
    )

    record = registry.record("agent-01")
    assert record.current_field_id == "field-host"
    assert record.home_affiliation is True
    assert record.status == "seconded"
    assert registry.available_agents("field-home") == ()
    assert registry.available_agents("field-host") == ("agent-01",)
    assert record.portable_state.digest() == before
    assert event.state_before_sha256 == event.state_after_sha256 == before


def test_temporary_and_permanent_migration_have_distinct_affiliation_semantics() -> None:
    temporary = MobilityRegistry()
    temporary.register_home_agent(_state())
    temporary.execute(
        _contract(
            "temporary-1",
            "temporary_migration",
            "field-home",
            "field-host",
        )
    )
    assert temporary.record("agent-01").home_affiliation is True
    assert temporary.record("agent-01").status == "temporary_migrant"

    permanent = MobilityRegistry()
    permanent.register_home_agent(_state())
    permanent.execute(
        _contract(
            "permanent-1",
            "permanent_migration",
            "field-home",
            "field-host",
        )
    )
    assert permanent.record("agent-01").home_affiliation is False
    assert permanent.record("agent-01").status == "permanent_migrant"


def test_round_trip_without_returned_learning_is_state_identical() -> None:
    registry = MobilityRegistry()
    state = _state()
    registry.register_home_agent(state)
    initial_state_digest = state.digest()

    registry.execute(
        _contract(
            "temporary-1",
            "temporary_migration",
            "field-home",
            "field-host",
        )
    )
    returned = registry.execute(
        _contract("return-1", "return_migration", "field-host", "field-home")
    )

    record = registry.record("agent-01")
    assert record.current_field_id == "field-home"
    assert record.home_affiliation is True
    assert record.status == "home"
    assert record.portable_state.digest() == initial_state_digest
    assert returned.state_before_sha256 == returned.state_after_sha256


def test_return_migration_can_carry_explicit_agent_owned_learning() -> None:
    registry = MobilityRegistry()
    state = _state()
    registry.register_home_agent(state)
    registry.execute(
        _contract(
            "temporary-1",
            "temporary_migration",
            "field-home",
            "field-host",
        )
    )

    learned = state.with_learning(
        {"water": 2, "mobility": 1},
        evidence_ref="destination://field-host/episodes/1-12",
    )
    returned = registry.execute(
        _contract("return-1", "return_migration", "field-host", "field-home"),
        returned_state=learned,
    )

    practice = registry.record("agent-01").portable_state.to_individual().practice_by_skill
    assert practice == {"energy": 2, "mobility": 1, "water": 6}
    assert returned.state_before_sha256 != returned.state_after_sha256
    assert "destination://field-host/episodes/1-12" in learned.evidence_refs


def test_changed_returned_state_requires_new_destination_evidence() -> None:
    registry = MobilityRegistry()
    state = _state()
    registry.register_home_agent(state)
    registry.execute(
        _contract(
            "temporary-1",
            "temporary_migration",
            "field-home",
            "field-host",
        )
    )
    changed_without_new_evidence = PortableAgentState(
        agent_id="agent-01",
        home_field_id="field-home",
        practice_by_skill=(("energy", 2), ("water", 5)),
        evidence_refs=state.evidence_refs,
    )

    with pytest.raises(ValueError, match="new provenance"):
        registry.execute(
            _contract("return-1", "return_migration", "field-host", "field-home"),
            returned_state=changed_without_new_evidence,
        )


def test_returned_learning_cannot_change_identity_home_or_reduce_practice() -> None:
    registry = MobilityRegistry()
    state = _state()
    registry.register_home_agent(state)
    registry.execute(
        _contract(
            "permanent-1",
            "permanent_migration",
            "field-home",
            "field-host",
        )
    )

    wrong_identity = PortableAgentState(
        agent_id="agent-02",
        home_field_id="field-home",
        practice_by_skill=state.practice_by_skill,
        evidence_refs=("destination://wrong-id",),
    )
    with pytest.raises(ValueError, match="changed agent identity"):
        registry.execute(
            _contract("return-wrong-id", "return_migration", "field-host", "field-home"),
            returned_state=wrong_identity,
        )

    wrong_home = PortableAgentState(
        agent_id="agent-01",
        home_field_id="field-other",
        practice_by_skill=state.practice_by_skill,
        evidence_refs=("destination://wrong-home",),
    )
    with pytest.raises(ValueError, match="changed immutable home"):
        registry.execute(
            _contract("return-wrong-home", "return_migration", "field-host", "field-home"),
            returned_state=wrong_home,
        )

    reduced = PortableAgentState(
        agent_id="agent-01",
        home_field_id="field-home",
        practice_by_skill=(("energy", 2), ("water", 3)),
        evidence_refs=("destination://reduced",),
    )
    with pytest.raises(ValueError, match="cannot reduce"):
        registry.execute(
            _contract("return-reduced", "return_migration", "field-host", "field-home"),
            returned_state=reduced,
        )


def test_transition_validation_rejects_wrong_origin_duplicate_contract_and_mode() -> None:
    registry = MobilityRegistry()
    registry.register_home_agent(_state())

    with pytest.raises(ValueError, match="origin does not match"):
        registry.execute(
            _contract("wrong-origin", "secondment", "field-other", "field-host")
        )

    with pytest.raises(ValueError, match="unsupported mobility mode"):
        _contract("invalid-mode", "teleport", "field-home", "field-host")

    contract = _contract("secondment-1", "secondment", "field-home", "field-host")
    registry.execute(contract)
    with pytest.raises(ValueError, match="already executed"):
        registry.execute(contract)

    with pytest.raises(ValueError, match="outbound mobility must begin"):
        registry.execute(
            _contract(
                "nested-move",
                "temporary_migration",
                "field-host",
                "field-third",
            )
        )


def test_return_requires_agent_to_be_away_and_destination_to_be_home() -> None:
    registry = MobilityRegistry()
    registry.register_home_agent(_state())

    with pytest.raises(ValueError, match="currently away"):
        registry.execute(
            _contract("return-home", "return_migration", "field-home", "field-other")
        )

    registry.execute(
        _contract(
            "temporary-1",
            "temporary_migration",
            "field-home",
            "field-host",
        )
    )
    with pytest.raises(ValueError, match="destination must be"):
        registry.execute(
            _contract("return-wrong", "return_migration", "field-host", "field-third")
        )


def test_individual_mobility_payload_excludes_pair_and_organization_state() -> None:
    state = _state()
    payload = json.dumps(state.as_dict(), sort_keys=True)
    forbidden = {
        "organization_memory",
        "pair_memory",
        "partner_model",
        "relationship_state",
        "module_history",
    }
    assert not any(name in payload for name in forbidden)

    parameters = set(inspect.signature(MobilityRegistry.execute).parameters)
    assert not parameters & forbidden


def test_environment_outcome_law_remains_mobility_blind() -> None:
    parameters = set(inspect.signature(JointEnvironment.evaluate).parameters)
    forbidden = {
        "current_field_id",
        "home_affiliation",
        "home_field_id",
        "migration_history",
        "mobility_mode",
        "time_away",
    }
    assert not parameters & forbidden


def test_registry_snapshot_is_deterministic_and_auditable() -> None:
    first = MobilityRegistry()
    second = MobilityRegistry()
    for registry in (first, second):
        registry.register_home_agent(_state())
        registry.execute(
            _contract("secondment-1", "secondment", "field-home", "field-host")
        )
        registry.execute(
            _contract("return-1", "return_migration", "field-host", "field-home")
        )

    assert first.snapshot() == second.snapshot()
    assert first.digest() == second.digest()
    assert [event.sequence for event in first.events()] == [1, 2]
