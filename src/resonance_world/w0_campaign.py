"""Reproducible W0 campaign runner over Resonance Field artifact directories."""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from resonance_world.protocol import PROTOCOL_VERSION, AgentPassport
from resonance_world.registry import WorldRegistry
from resonance_world.resonance_field_artifacts import ResonanceFieldArtifactAdapter


@dataclass(frozen=True, slots=True)
class CohortField:
    field_id: str
    seed: int
    run_id: str
    artifact_name: str
    code_sha: str
    ablation: str


@dataclass(frozen=True, slots=True)
class CohortManifest:
    cohort_id: str
    source_repository: str
    expected_agents_per_field: int
    fields: tuple[CohortField, ...]


def _required_text(value: Any, name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{name} is required")
    return text


def load_cohort_manifest(path: str | Path) -> CohortManifest:
    """Load and validate a versioned W0 cohort manifest."""

    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("cohort manifest must contain a JSON object")
    raw_fields = value.get("fields")
    if not isinstance(raw_fields, list) or not raw_fields:
        raise ValueError("cohort manifest fields must be a non-empty list")

    fields = []
    for index, raw in enumerate(raw_fields):
        if not isinstance(raw, dict):
            raise ValueError(f"fields[{index}] must be an object")
        fields.append(
            CohortField(
                field_id=_required_text(raw.get("field_id"), f"fields[{index}].field_id"),
                seed=int(raw["seed"]),
                run_id=_required_text(raw.get("run_id"), f"fields[{index}].run_id"),
                artifact_name=_required_text(
                    raw.get("artifact_name"), f"fields[{index}].artifact_name"
                ),
                code_sha=_required_text(raw.get("code_sha"), f"fields[{index}].code_sha"),
                ablation=_required_text(raw.get("ablation"), f"fields[{index}].ablation"),
            )
        )

    field_ids = [item.field_id for item in fields]
    run_ids = [item.run_id for item in fields]
    artifact_names = [item.artifact_name for item in fields]
    for name, items in (
        ("field_id", field_ids),
        ("run_id", run_ids),
        ("artifact_name", artifact_names),
    ):
        if len(items) != len(set(items)):
            raise ValueError(f"cohort {name} values must be unique")

    expected_agents = int(value.get("expected_agents_per_field", 0))
    if expected_agents <= 0:
        raise ValueError("expected_agents_per_field must be positive")

    return CohortManifest(
        cohort_id=_required_text(value.get("cohort_id"), "cohort_id"),
        source_repository=_required_text(value.get("source_repository"), "source_repository"),
        expected_agents_per_field=expected_agents,
        fields=tuple(fields),
    )


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _passport_line(passport: AgentPassport) -> bytes:
    return passport.canonical_bytes() + b"\n"


def run_cohort(
    manifest_path: str | Path,
    artifact_root: str | Path,
    output_dir: str | Path,
) -> dict[str, Any]:
    """Register the manifest Fields and export deterministic W0 cohort evidence."""

    manifest = load_cohort_manifest(manifest_path)
    artifact_root = Path(artifact_root)
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)

    registry = WorldRegistry()
    source_rows = []
    adapters: dict[str, ResonanceFieldArtifactAdapter] = {}

    for field in manifest.fields:
        artifact_dir = artifact_root / field.artifact_name
        if not artifact_dir.is_dir():
            raise ValueError(f"missing artifact directory: {artifact_dir}")
        adapter = ResonanceFieldArtifactAdapter(artifact_dir, field_id=field.field_id)
        descriptor = adapter.descriptor()

        if descriptor.checkpoint_id != field.run_id:
            raise ValueError(
                f"{field.field_id} run mismatch: expected {field.run_id}, "
                f"got {descriptor.checkpoint_id}"
            )
        if descriptor.runtime_version != field.code_sha:
            raise ValueError(
                f"{field.field_id} code SHA mismatch: expected {field.code_sha}, "
                f"got {descriptor.runtime_version}"
            )
        expected_suffix = f":{field.ablation}:{field.seed}"
        if not descriptor.experiment_id.endswith(expected_suffix):
            raise ValueError(
                f"{field.field_id} experiment identity does not end with "
                f"{expected_suffix}"
            )
        agent_ids = adapter.list_agent_ids()
        if len(agent_ids) != manifest.expected_agents_per_field:
            raise ValueError(
                f"{field.field_id} population mismatch: expected "
                f"{manifest.expected_agents_per_field}, got {len(agent_ids)}"
            )

        registry.register(adapter)
        adapters[field.field_id] = adapter
        source_rows.append(
            {
                "ablation": field.ablation,
                "artifact_name": field.artifact_name,
                "code_sha": field.code_sha,
                "field_id": field.field_id,
                "run_id": field.run_id,
                "seed": field.seed,
            }
        )

    passports = registry.all_passports()
    passport_bytes = b"".join(_passport_line(passport) for passport in passports)
    passports_path = destination / "passports.jsonl"
    passports_path.write_bytes(passport_bytes)

    field_rows = []
    for field_id in registry.field_ids():
        descriptor = registry.descriptor(field_id)
        field_rows.append(
            {
                "agent_count": len(registry.agent_ids(field_id)),
                "checkpoint_id": descriptor.checkpoint_id,
                "experiment_id": descriptor.experiment_id,
                "field_id": descriptor.field_id,
                "field_protocol_version": descriptor.field_protocol_version,
                "runtime_version": descriptor.runtime_version,
            }
        )

    registry_payload = {
        "cohort_id": manifest.cohort_id,
        "fields": field_rows,
        "source_repository": manifest.source_repository,
        "sources": source_rows,
        "world_protocol_version": PROTOCOL_VERSION,
    }
    registry_bytes = (
        json.dumps(registry_payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    ).encode("utf-8")
    registry_path = destination / "field-registry.json"
    registry_path.write_bytes(registry_bytes)

    evidence_ref_count = 0
    evidence_digests = set()
    for passport in passports:
        refs = list(passport.evidence_refs)
        refs.extend(
            ref
            for capability in passport.capability_vector
            for ref in capability.evidence_refs
        )
        for metrics in (
            passport.calibration_metrics,
            passport.adaptation_metrics,
            passport.specialization_metrics,
            passport.collaboration_metrics,
        ):
            refs.extend(ref for metric in metrics for ref in metric.evidence_refs)
        for ref in refs:
            adapters[passport.source_field_id].resolve_evidence(ref)
            evidence_ref_count += 1
            evidence_digests.add(ref.sha256)

    summary = {
        "cohort_id": manifest.cohort_id,
        "evidence_digest_count": len(evidence_digests),
        "evidence_reference_count": evidence_ref_count,
        "field_count": len(registry.field_ids()),
        "passport_count": len(passports),
        "passports_sha256": _sha256_bytes(passport_bytes),
        "registry_sha256": _sha256_bytes(registry_bytes),
        "source_repository": manifest.source_repository,
        "total_agents": sum(len(registry.agent_ids(item)) for item in registry.field_ids()),
        "world_protocol_version": PROTOCOL_VERSION,
    }
    summary_bytes = (
        json.dumps(summary, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    ).encode("utf-8")
    (destination / "cohort-summary.json").write_bytes(summary_bytes)
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a Resonance World W0 cohort import")
    parser.add_argument("manifest", type=Path)
    parser.add_argument("artifact_root", type=Path)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args(argv)
    summary = run_cohort(args.manifest, args.artifact_root, args.output_dir)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
