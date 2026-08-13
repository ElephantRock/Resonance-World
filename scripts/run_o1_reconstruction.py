#!/usr/bin/env python3
"""Run O1 reconstruction from Plane-E evidence only."""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from resonance_contextgraph import EvidenceStore

from resonance_world.context_graph_adapter import to_evidence_claim
from resonance_world.o1_reconstruction import canonical_bytes, reconstruct_products

O0_EVIDENCE_SHA256 = "7e8ef1c9fcbfbc16eb5e50db477dcacc2b6830af86b50b8cf44c965c21ca456a"
_EMPTY_OBJECT_SENTINEL = "rw-o1-transport:none:v1"
FORBIDDEN_E_FIELDS = {
    "practice_by_skill",
    "hidden_regime",
    "target_hypothesis",
    "target_policy",
    "neutral_preferred_policy",
    "expected_action",
    "spoof_action",
    "legitimate_notice_id",
    "spoof_notice_id",
    "advancement_gate",
    "classification",
}


@dataclass(frozen=True, slots=True)
class _ObservedClaim:
    field_id: str
    subject: str
    predicate: str
    object: str
    observed_by: str
    source_id: str
    source_class: str
    observed_at: int
    confidence: float
    direct: bool


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _encode_transport_object(value: str) -> str:
    """Encode an observed absence without violating ContextGraph's non-empty contract."""
    return _EMPTY_OBJECT_SENTINEL if value == "" else value


def _decode_transport_claims(claims: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Reverse only the registered O1 absence encoding before ledger reconstruction."""
    decoded: list[dict[str, Any]] = []
    for claim in claims:
        row = dict(claim)
        if row.get("object") == _EMPTY_OBJECT_SENTINEL:
            row["object"] = ""
        decoded.append(row)
    return decoded


def _load_plane_e(directory: Path) -> list[dict[str, Any]]:
    planes = []
    observed_families: set[str] = set()
    for path in sorted(directory.glob("*.json")):
        value = _read_json(path)
        if value.get("schema") != "o1-plane-e-v0.1":
            raise ValueError(f"unsupported Plane-E schema in {path}")
        family = str(value.get("family"))
        if family not in {"A", "T", "S"} or family in observed_families:
            raise ValueError(f"invalid or duplicate Plane-E family {family!r}")
        observed_families.add(family)
        for event in value.get("events", []):
            if not isinstance(event, dict):
                raise ValueError(f"{path} contains non-object event")
            fields = event.get("fields")
            if not isinstance(fields, dict) or not fields:
                raise ValueError(f"{path} event requires fields")
            bad = FORBIDDEN_E_FIELDS.intersection(fields)
            if bad:
                raise ValueError(f"Plane E contains evaluator-only fields: {sorted(bad)}")
            if any(not isinstance(item, str) for item in fields.values()):
                raise ValueError("Plane-E field objects must already be canonical strings")
            if _EMPTY_OBJECT_SENTINEL in fields.values():
                raise ValueError("Plane E collides with the reserved O1 absence encoding")
            scope_id = str(event.get("scope_id", ""))
            if not scope_id.startswith(f"o1:{family}:"):
                raise ValueError(f"Plane-E scope/family mismatch: {scope_id!r}")
        planes.append(value)
    if observed_families != {"A", "T", "S"}:
        raise ValueError(f"Plane E missing registered families: {observed_families}")
    return planes


def _generic_claims(planes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    store = EvidenceStore()
    scopes: set[str] = set()
    for plane in planes:
        family = str(plane["family"])
        observer_id = f"resonance-world:o1:{family.lower()}-observer"
        for event in plane["events"]:
            scope_id = str(event["scope_id"])
            subject = str(event["event_id"])
            observed_at = int(event["observed_at"])
            source_class = str(event["source_class"])
            scopes.add(scope_id)
            for predicate, object_value in sorted(dict(event["fields"]).items()):
                source_id = f"{scope_id}:{subject}:{predicate}"
                observed = _ObservedClaim(
                    field_id=scope_id,
                    subject=subject,
                    predicate=str(predicate),
                    object=_encode_transport_object(str(object_value)),
                    observed_by=observer_id,
                    source_id=source_id,
                    source_class=source_class,
                    observed_at=observed_at,
                    confidence=1.0,
                    direct=True,
                )
                store.ingest(to_evidence_claim(observed, delivery=0))
    claims = []
    for scope_id in sorted(scopes):
        claims.extend(asdict(claim) for claim in store.claims(scope_id=scope_id))
    return claims


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--relationship-evidence", required=True, type=Path)
    parser.add_argument("--plane-e-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()

    if _sha256_file(args.relationship_evidence) != O0_EVIDENCE_SHA256:
        raise ValueError("O1 relationship evidence differs from accepted O0 evidence bytes")
    relationship = _read_json(args.relationship_evidence)
    if relationship.get("schema") != "o0-contextgraph-evidence-v0.1":
        raise ValueError("O1 requires accepted O0 evidence schema")
    relationship_claims = relationship.get("claims")
    if not isinstance(relationship_claims, list) or len(relationship_claims) != 2160:
        raise ValueError("O1 requires exactly 2,160 O0 relationship claims")

    planes = _load_plane_e(args.plane_e_dir)
    generic = _generic_claims(planes)
    claims = [*relationship_claims, *generic]
    if len({str(row["claim_id"]) for row in claims}) != len(claims):
        raise ValueError("O1 transport claim identities are not unique")
    if len({str(row["source_id"]) for row in claims}) != len(claims):
        raise ValueError("O1 source identities are not unique")

    # ContextGraph stores a non-empty sentinel for directly observed absent values.
    # Reconstruction reverses that transport encoding using evidence alone; Plane K is
    # still absent, and the frozen Plane-E semantic projection remains unchanged.
    reconstruction_claims = [*relationship_claims, *_decode_transport_claims(generic)]
    products = reconstruct_products(reconstruction_claims)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    evidence = {"schema": "o1-contextgraph-evidence-v0.1", "claims": claims}
    (args.output_dir / "contextgraph-evidence.json").write_bytes(canonical_bytes(evidence))
    for name, value in products.items():
        (args.output_dir / name).write_bytes(canonical_bytes(value))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
