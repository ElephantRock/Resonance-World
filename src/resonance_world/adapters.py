"""Read-only adapters between exported Field evidence and Resonance World."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol

from resonance_world.protocol import (
    PROTOCOL_VERSION,
    AgentPassport,
    CapabilityScore,
    EvidenceRef,
    FieldDescriptor,
    Metric,
)

JsonObject = dict[str, Any]


def canonical_json_bytes(value: Any) -> bytes:
    """Serialize JSON-compatible evidence deterministically."""

    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def sha256_json(value: Any) -> str:
    """Return the canonical SHA-256 digest of JSON-compatible evidence."""

    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


class FieldAdapter(Protocol):
    """Minimal read-only contract required by the World registry."""

    def descriptor(self) -> FieldDescriptor: ...

    def list_agent_ids(self) -> tuple[str, ...]: ...

    def passport(self, agent_id: str) -> AgentPassport: ...

    def resolve_evidence(self, ref: EvidenceRef) -> Any: ...


class CheckpointJsonAdapter:
    """Read-only adapter for a versioned Field checkpoint evidence bundle.

    The adapter never imports Resonance Field runtime classes and never writes to
    the source bundle. All passport claims must point to evidence contained in the
    bundle's evidence index.
    """

    def __init__(self, bundle: Mapping[str, Any]) -> None:
        self._bundle = deepcopy(dict(bundle))
        self._descriptor = self._parse_descriptor(self._bundle)
        self._issued_at = self._parse_datetime(self._bundle["field"]["issued_at"])
        self._evidence_payloads: dict[str, Any] = {}
        self._evidence_refs: dict[str, EvidenceRef] = {}
        self._load_evidence(self._bundle.get("evidence", []))

        agents = self._bundle.get("agents")
        if not isinstance(agents, list):
            raise ValueError("bundle agents must be a list")
        self._agents: dict[str, JsonObject] = {}
        for agent in agents:
            if not isinstance(agent, dict):
                raise ValueError("each agent record must be an object")
            agent_id = str(agent.get("agent_id", ""))
            if not agent_id:
                raise ValueError("agent_id is required")
            if agent_id in self._agents:
                raise ValueError(f"duplicate agent_id: {agent_id}")
            self._agents[agent_id] = deepcopy(agent)

    @classmethod
    def from_path(cls, path: str | Path) -> CheckpointJsonAdapter:
        """Load a checkpoint without modifying it."""

        with Path(path).open("r", encoding="utf-8") as handle:
            value = json.load(handle)
        if not isinstance(value, dict):
            raise ValueError("checkpoint root must be an object")
        return cls(value)

    def descriptor(self) -> FieldDescriptor:
        return self._descriptor

    def list_agent_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._agents))

    def passport(self, agent_id: str) -> AgentPassport:
        try:
            record = self._agents[agent_id]
        except KeyError as exc:
            raise KeyError(f"unknown agent_id: {agent_id}") from exc

        capability_vector = tuple(
            self._parse_capability(item) for item in record.get("capability_vector", [])
        )
        evidence_refs = self._refs_for_uris(record.get("evidence_refs", []))

        passport = AgentPassport(
            agent_id=agent_id,
            source_field_id=self._descriptor.field_id,
            passport_version=PROTOCOL_VERSION,
            checkpoint_id=self._descriptor.checkpoint_id,
            observed_cycles=int(record.get("observed_cycles", 0)),
            completed_tasks=int(record.get("completed_tasks", 0)),
            success_rate=float(record.get("success_rate", 0.0)),
            capability_vector=capability_vector,
            calibration_metrics=self._parse_metrics(record.get("calibration_metrics", [])),
            adaptation_metrics=self._parse_metrics(record.get("adaptation_metrics", [])),
            specialization_metrics=self._parse_metrics(
                record.get("specialization_metrics", [])
            ),
            collaboration_metrics=self._parse_metrics(record.get("collaboration_metrics", [])),
            home_dependency_score=self._optional_float(record.get("home_dependency_score")),
            portable_capability_score=self._optional_float(
                record.get("portable_capability_score")
            ),
            evidence_refs=evidence_refs,
            issued_at=self._issued_at,
        )
        self._validate_passport_provenance(passport)
        return passport

    def resolve_evidence(self, ref: EvidenceRef) -> Any:
        try:
            registered = self._evidence_refs[ref.uri]
            payload = self._evidence_payloads[ref.uri]
        except KeyError as exc:
            raise KeyError(f"unresolvable evidence uri: {ref.uri}") from exc
        if registered != ref:
            raise ValueError(f"evidence metadata mismatch for {ref.uri}")
        if sha256_json(payload) != ref.sha256:
            raise ValueError(f"evidence digest mismatch for {ref.uri}")
        return deepcopy(payload)

    @staticmethod
    def _parse_descriptor(bundle: Mapping[str, Any]) -> FieldDescriptor:
        field = bundle.get("field")
        if not isinstance(field, dict):
            raise ValueError("bundle field must be an object")
        return FieldDescriptor(
            field_id=str(field.get("field_id", "")),
            field_protocol_version=str(field.get("field_protocol_version", "")),
            runtime_version=str(field.get("runtime_version", "")),
            experiment_id=str(field.get("experiment_id", "")),
            checkpoint_id=str(field.get("checkpoint_id", "")),
        )

    @staticmethod
    def _parse_datetime(raw: Any) -> datetime:
        if not isinstance(raw, str):
            raise ValueError("field issued_at must be an ISO-8601 string")
        value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if value.tzinfo is None:
            raise ValueError("field issued_at must include a timezone")
        return value

    def _load_evidence(self, entries: Any) -> None:
        if not isinstance(entries, list):
            raise ValueError("evidence must be a list")
        for item in entries:
            if not isinstance(item, dict):
                raise ValueError("each evidence entry must be an object")
            uri = str(item.get("uri", ""))
            if not uri:
                raise ValueError("evidence uri is required")
            if uri in self._evidence_refs:
                raise ValueError(f"duplicate evidence uri: {uri}")
            if "payload" not in item:
                raise ValueError(f"evidence payload is required for {uri}")
            payload = deepcopy(item["payload"])
            digest = sha256_json(payload)
            declared = item.get("sha256")
            if declared is not None and declared != digest:
                raise ValueError(f"declared evidence digest mismatch for {uri}")
            ref = EvidenceRef(
                uri=uri,
                sha256=digest,
                kind=str(item.get("kind", "record")),
                source_record_id=(
                    str(item["source_record_id"])
                    if item.get("source_record_id") is not None
                    else None
                ),
            )
            self._evidence_refs[uri] = ref
            self._evidence_payloads[uri] = payload

    def _refs_for_uris(self, raw: Any) -> tuple[EvidenceRef, ...]:
        if not isinstance(raw, list):
            raise ValueError("evidence_refs must be a list")
        refs: list[EvidenceRef] = []
        for uri_value in raw:
            uri = str(uri_value)
            try:
                refs.append(self._evidence_refs[uri])
            except KeyError as exc:
                raise ValueError(f"passport references unknown evidence uri: {uri}") from exc
        return tuple(sorted(refs))

    def _parse_capability(self, raw: Any) -> CapabilityScore:
        if not isinstance(raw, dict):
            raise ValueError("capability entries must be objects")
        return CapabilityScore(
            name=str(raw.get("name", "")),
            score=float(raw.get("score", 0.0)),
            sample_size=int(raw.get("sample_size", 0)),
            evidence_refs=self._refs_for_uris(raw.get("evidence_refs", [])),
        )

    def _parse_metrics(self, raw: Any) -> tuple[Metric, ...]:
        if not isinstance(raw, list):
            raise ValueError("metric collections must be lists")
        metrics = []
        for item in raw:
            if not isinstance(item, dict):
                raise ValueError("metric entries must be objects")
            metrics.append(
                Metric(
                    name=str(item.get("name", "")),
                    value=float(item.get("value", 0.0)),
                    evidence_refs=self._refs_for_uris(item.get("evidence_refs", [])),
                )
            )
        return tuple(sorted(metrics))

    @staticmethod
    def _optional_float(value: Any) -> float | None:
        return None if value is None else float(value)

    def _validate_passport_provenance(self, passport: AgentPassport) -> None:
        referenced = set(passport.evidence_refs)
        for capability in passport.capability_vector:
            referenced.update(capability.evidence_refs)
        for collection in (
            passport.calibration_metrics,
            passport.adaptation_metrics,
            passport.specialization_metrics,
            passport.collaboration_metrics,
        ):
            for metric in collection:
                referenced.update(metric.evidence_refs)
        for ref in referenced:
            self.resolve_evidence(ref)
