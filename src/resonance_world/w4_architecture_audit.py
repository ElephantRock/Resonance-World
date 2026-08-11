"""Validate the W4-00 relationship-state architecture boundary."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

ArchitectureClass = Literal[
    "A_NO_NATIVE_PAIR_STATE",
    "B_IMPLICIT_PAIR_STATE",
    "C_EXPLICIT_PAIR_STATE",
]
Origin = Literal["field_native", "field_evidence", "world_derived_proxy", "absent"]


@dataclass(frozen=True, slots=True)
class Primitive:
    name: str
    origin: Origin
    scope: str
    persistent: bool
    relationship_specific: bool
    independently_manipulable: bool
    native_relationship_state: bool
    direct_outcome_effect: bool = False

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> Primitive:
        return cls(
            name=str(value["name"]),
            origin=value["origin"],
            scope=str(value["scope"]),
            persistent=bool(value["persistent"]),
            relationship_specific=bool(value["relationship_specific"]),
            independently_manipulable=bool(value["independently_manipulable"]),
            native_relationship_state=bool(value["native_relationship_state"]),
            direct_outcome_effect=bool(value.get("direct_outcome_effect", False)),
        )

    @property
    def qualifies_as_native_relationship_state(self) -> bool:
        return (
            self.origin == "field_native"
            and self.persistent
            and self.relationship_specific
            and self.independently_manipulable
        )


@dataclass(frozen=True, slots=True)
class AuditResult:
    classification: ArchitectureClass
    native_relationship_state_count: int
    world_proxy_count: int
    blocked_behavioral_operations: tuple[str, ...]
    behavioral_w4_allowed: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "behavioral_w4_allowed": self.behavioral_w4_allowed,
            "blocked_behavioral_operations": list(self.blocked_behavioral_operations),
            "classification": self.classification,
            "native_relationship_state_count": self.native_relationship_state_count,
            "world_proxy_count": self.world_proxy_count,
        }


def load_manifest(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("audit manifest must contain an object")
    return value


def validate_manifest(manifest: dict[str, Any]) -> AuditResult:
    primitives_raw = manifest.get("primitives")
    if not isinstance(primitives_raw, list) or not primitives_raw:
        raise ValueError("audit manifest requires primitives")

    primitives = [Primitive.from_mapping(dict(item)) for item in primitives_raw]
    names = [item.name for item in primitives]
    if len(names) != len(set(names)):
        raise ValueError("audit primitive names must be unique")

    for raw, primitive in zip(primitives_raw, primitives, strict=True):
        provenance = raw.get("provenance")
        if not isinstance(provenance, dict):
            raise ValueError(f"{primitive.name}: provenance is required")
        for key in ("repository", "commit", "path", "evidence"):
            if not str(provenance.get(key, "")).strip():
                raise ValueError(f"{primitive.name}: provenance.{key} is required")

        if primitive.native_relationship_state != primitive.qualifies_as_native_relationship_state:
            raise ValueError(
                f"{primitive.name}: native_relationship_state does not match provenance semantics"
            )

        if primitive.origin == "world_derived_proxy" and primitive.native_relationship_state:
            raise ValueError(f"{primitive.name}: World proxy cannot be Field-native state")

    proxy = next((item for item in primitives if item.name == "w3_coordination_exposure"), None)
    if proxy is None:
        raise ValueError("W3 coordination proxy must be audited explicitly")
    if proxy.origin != "world_derived_proxy" or not proxy.direct_outcome_effect:
        raise ValueError("W3 coordination exposure must remain labeled as an outcome-affecting proxy")

    native = [item for item in primitives if item.native_relationship_state]
    classification = str(manifest.get("classification", ""))
    expected: ArchitectureClass
    if not native:
        expected = "A_NO_NATIVE_PAIR_STATE"
    elif all(item.independently_manipulable for item in native):
        expected = "C_EXPLICIT_PAIR_STATE"
    else:
        expected = "B_IMPLICIT_PAIR_STATE"
    if classification != expected:
        raise ValueError(f"classification must be {expected}, got {classification}")

    blocked = tuple(str(item) for item in manifest.get("blocked_behavioral_operations", []))
    required_blocked = {
        "relationship_reset",
        "joint_memory_ablation",
        "partner_policy_ablation",
        "portable_pair_capsule_transfer",
    }
    if not required_blocked.issubset(set(blocked)):
        raise ValueError("current audit must block undefined pair-state operations")

    next_phase = manifest.get("next_phase")
    if not isinstance(next_phase, dict):
        raise ValueError("next_phase is required")
    behavioral_allowed = bool(next_phase.get("behavioral_w4_allowed", True))
    if expected == "A_NO_NATIVE_PAIR_STATE" and behavioral_allowed:
        raise ValueError("behavioral W4 cannot proceed while pair state is absent")

    required_affordances = set(str(item) for item in next_phase.get("required_affordances", []))
    if "no_direct_relationship_success_bonus" not in required_affordances:
        raise ValueError("W4A must prohibit a direct relationship-success bonus")

    clarification = manifest.get("w3_clarification")
    if not isinstance(clarification, dict):
        raise ValueError("w3_clarification is required")
    if bool(clarification.get("field_native_relationship_capital_demonstrated", True)):
        raise ValueError("W3 must not be labeled Field-native relationship capital")

    return AuditResult(
        classification=expected,
        native_relationship_state_count=len(native),
        world_proxy_count=sum(item.origin == "world_derived_proxy" for item in primitives),
        blocked_behavioral_operations=blocked,
        behavioral_w4_allowed=behavioral_allowed,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)

    result = validate_manifest(load_manifest(args.manifest))
    payload = json.dumps(result.as_dict(), indent=2, sort_keys=True) + "\n"
    if args.output is None:
        print(payload, end="")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
