import uuid

from resonance_world.w0_field_runner import deterministic_uuid4


def test_deterministic_uuid4_is_repeatable_and_v4_shaped() -> None:
    first = deterministic_uuid4("seed-101")
    second = deterministic_uuid4("seed-101")

    values = [first() for _ in range(4)]
    assert values == [second() for _ in range(4)]
    assert len(set(values)) == 4
    assert all(isinstance(value, uuid.UUID) for value in values)
    assert all(value.version == 4 for value in values)
    assert all(value.variant == uuid.RFC_4122 for value in values)


def test_deterministic_uuid4_changes_with_seed() -> None:
    assert deterministic_uuid4("a")() != deterministic_uuid4("b")()
