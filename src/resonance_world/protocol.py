"""Versioned, evidence-backed protocol objects for the Field/World boundary."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from typing import Any

PROTOCOL_VERSION = "0.1"


def _require_unit_interval(name: str, value: float | None) -> None:
    if value is not None and not 0.0 <= value <= 1.0:
        raise ValueError(f"{name} must be between 0 and 1")


@dataclass(frozen=True, slots=True, order=True)
class EvidenceRef:
    """Immutable reference to evidence retained by the source Field."""

    uri: str
    sha256: str
    kind: str = "record"
    source_record_id: str | None = None

    def __post_init__(self) -> None:
        if not self.uri:
            raise ValueError("evidence uri is required")
        if len(self.sha256) != 64 or any(c not in "0123456789abcdef" for c in self.sha256):
            raise ValueError("sha256 must be a lowercase 64-character hexadecimal digest")


@dataclass(frozen=True, slots=True, order=True)
class Metric:
    """Named normalized or raw metric with optional evidence linkage."""

    name: str
    value: float
    evidence_refs: tuple[EvidenceRef, ...] = ()

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("metric name is required")


@dataclass(frozen=True, slots=True, order=True)
class CapabilityScore:
    """Evidence-backed capability estimate derived from observed behavior."""

    name: str
    score: float
    sample_size: int
    evidence_refs: tuple[EvidenceRef, ...] = ()

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("capability name is required")
        _require_unit_interval("capability score", self.score)
        if self.sample_size < 0:
            raise ValueError("sample_size must be non-negative")


@dataclass(frozen=True, slots=True)
class FieldDescriptor:
    """Stable identity for one observed Field checkpoint."""

    field_id: str
    field_protocol_version: str
    runtime_version: str
    experiment_id: str
    checkpoint_id: str

    def __post_init__(self) -> None:
        for name in (
            "field_id",
            "field_protocol_version",
            "runtime_version",
            "experiment_id",
            "checkpoint_id",
        ):
            if not getattr(self, name):
                raise ValueError(f"{name} is required")


@dataclass(frozen=True, slots=True)
class AgentPassport:
    """Portable, evidence-backed summary of demonstrated agent capability."""

    agent_id: str
    source_field_id: str
    passport_version: str
    checkpoint_id: str
    observed_cycles: int
    completed_tasks: int
    success_rate: float
    capability_vector: tuple[CapabilityScore, ...]
    calibration_metrics: tuple[Metric, ...] = ()
    adaptation_metrics: tuple[Metric, ...] = ()
    specialization_metrics: tuple[Metric, ...] = ()
    collaboration_metrics: tuple[Metric, ...] = ()
    home_dependency_score: float | None = None
    portable_capability_score: float | None = None
    evidence_refs: tuple[EvidenceRef, ...] = ()
    issued_at: datetime = datetime(1970, 1, 1, tzinfo=timezone.utc)

    def __post_init__(self) -> None:
        if not self.agent_id:
            raise ValueError("agent_id is required")
        if not self.source_field_id:
            raise ValueError("source_field_id is required")
        if not self.passport_version:
            raise ValueError("passport_version is required")
        if not self.checkpoint_id:
            raise ValueError("checkpoint_id is required")
        if self.observed_cycles < 0 or self.completed_tasks < 0:
            raise ValueError("counts must be non-negative")
        _require_unit_interval("success_rate", self.success_rate)
        _require_unit_interval("home_dependency_score", self.home_dependency_score)
        _require_unit_interval("portable_capability_score", self.portable_capability_score)
        if self.issued_at.tzinfo is None:
            raise ValueError("issued_at must be timezone-aware")

        capability_names = [item.name for item in self.capability_vector]
        if len(capability_names) != len(set(capability_names)):
            raise ValueError("capability names must be unique")

    def to_dict(self) -> dict[str, Any]:
        """Return a deterministic JSON-compatible representation."""

        def evidence(ref: EvidenceRef) -> dict[str, Any]:
            return {
                "kind": ref.kind,
                "sha256": ref.sha256,
                "source_record_id": ref.source_record_id,
                "uri": ref.uri,
            }

        def metric(item: Metric) -> dict[str, Any]:
            return {
                "evidence_refs": [evidence(ref) for ref in sorted(item.evidence_refs)],
                "name": item.name,
                "value": item.value,
            }

        def capability(item: CapabilityScore) -> dict[str, Any]:
            return {
                "evidence_refs": [evidence(ref) for ref in sorted(item.evidence_refs)],
                "name": item.name,
                "sample_size": item.sample_size,
                "score": item.score,
            }

        return {
            "adaptation_metrics": [metric(item) for item in sorted(self.adaptation_metrics)],
            "agent_id": self.agent_id,
            "calibration_metrics": [metric(item) for item in sorted(self.calibration_metrics)],
            "capability_vector": [
                capability(item) for item in sorted(self.capability_vector)
            ],
            "checkpoint_id": self.checkpoint_id,
            "collaboration_metrics": [
                metric(item) for item in sorted(self.collaboration_metrics)
            ],
            "completed_tasks": self.completed_tasks,
            "evidence_refs": [evidence(ref) for ref in sorted(self.evidence_refs)],
            "home_dependency_score": self.home_dependency_score,
            "issued_at": self.issued_at.astimezone(timezone.utc).isoformat(),
            "passport_version": self.passport_version,
            "portable_capability_score": self.portable_capability_score,
            "source_field_id": self.source_field_id,
            "specialization_metrics": [
                metric(item) for item in sorted(self.specialization_metrics)
            ],
            "success_rate": self.success_rate,
            "observed_cycles": self.observed_cycles,
        }

    def canonical_bytes(self) -> bytes:
        """Canonical form used for repeatability checks and content hashing."""

        return json.dumps(
            self.to_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
