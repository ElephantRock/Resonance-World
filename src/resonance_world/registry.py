"""Registry for independently operating Fields observed by Resonance World."""

from __future__ import annotations

from resonance_world.adapters import FieldAdapter
from resonance_world.protocol import AgentPassport, FieldDescriptor


class WorldRegistry:
    """Register Fields without granting World mutation access to them."""

    def __init__(self) -> None:
        self._adapters: dict[str, FieldAdapter] = {}

    def register(self, adapter: FieldAdapter) -> FieldDescriptor:
        descriptor = adapter.descriptor()
        if descriptor.field_id in self._adapters:
            raise ValueError(f"field already registered: {descriptor.field_id}")
        self._adapters[descriptor.field_id] = adapter
        return descriptor

    def field_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._adapters))

    def descriptor(self, field_id: str) -> FieldDescriptor:
        return self._adapter(field_id).descriptor()

    def agent_ids(self, field_id: str) -> tuple[str, ...]:
        return self._adapter(field_id).list_agent_ids()

    def passport(self, field_id: str, agent_id: str) -> AgentPassport:
        passport = self._adapter(field_id).passport(agent_id)
        if passport.source_field_id != field_id:
            raise ValueError(
                f"passport source mismatch: expected {field_id}, "
                f"got {passport.source_field_id}"
            )
        return passport

    def all_passports(self) -> tuple[AgentPassport, ...]:
        passports = []
        for field_id in self.field_ids():
            for agent_id in self.agent_ids(field_id):
                passports.append(self.passport(field_id, agent_id))
        return tuple(passports)

    def _adapter(self, field_id: str) -> FieldAdapter:
        try:
            return self._adapters[field_id]
        except KeyError as exc:
            raise KeyError(f"unknown field_id: {field_id}") from exc
