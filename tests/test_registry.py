from resonance_world.adapters import CheckpointJsonAdapter
from resonance_world.registry import WorldRegistry

from tests.fixtures import checkpoint_bundle


def field_adapter(field_id: str) -> CheckpointJsonAdapter:
    return CheckpointJsonAdapter(checkpoint_bundle(field_id))


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
