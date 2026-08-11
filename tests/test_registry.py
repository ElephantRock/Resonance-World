from __future__ import annotations

from copy import deepcopy

from resonance_world.adapters import CheckpointJsonAdapter
from resonance_world.registry import WorldRegistry

from test_checkpoint_adapter import checkpoint_bundle


def field_adapter(field_id: str) -> CheckpointJsonAdapter:
    bundle = deepcopy(checkpoint_bundle())
    bundle["field"]["field_id"] = field_id
    for evidence in bundle["evidence"]:
        old_uri = evidence["uri"]
        new_uri = old_uri.replace("field-a", field_id)
        evidence["uri"] = new_uri
    for agent in bundle["agents"]:
        agent["evidence_refs"] = [
            uri.replace("field-a", field_id) for uri in agent["evidence_refs"]
        ]
        for capability in agent["capability_vector"]:
            capability["evidence_refs"] = [
                uri.replace("field-a", field_id) for uri in capability["evidence_refs"]
            ]
        for metric in agent["specialization_metrics"]:
            metric["evidence_refs"] = [
                uri.replace("field-a", field_id) for uri in metric["evidence_refs"]
            ]
    return CheckpointJsonAdapter(bundle)


def test_registry_holds_three_independent_fields() -> None:
    registry = WorldRegistry()
    for field_id in ("field-a", "field-b", "field-c"):
        registry.register(field_adapter(field_id))

    assert registry.field_ids() == ("field-a", "field-b", "field-c")
    assert len(registry.all_passports()) == 3
    assert {
        passport.source_field_id for passport in registry.all_passports()
    } == {"field-a", "field-b", "field-c"}


def test_registry_rejects_duplicate_field_identity() -> None:
    registry = WorldRegistry()
    registry.register(field_adapter("field-a"))

    try:
        registry.register(field_adapter("field-a"))
    except ValueError as exc:
        assert "already registered" in str(exc)
    else:
        raise AssertionError("duplicate Field identity should be rejected")
