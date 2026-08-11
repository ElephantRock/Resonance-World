"""W5-00 machine-checkable organizational-state audit."""

from __future__ import annotations

import argparse
import inspect
import json
from pathlib import Path

from .w4a_joint_learning import JointEnvironment, RelationshipStateStore

ORGANIZATION_PRIMITIVES = {
    "organization_identity",
    "organization_roster",
    "organization_episode_memory",
    "organization_procedural_memory",
    "organization_routing_memory",
}

FORBIDDEN_ENVIRONMENT_INPUTS = {
    "organization",
    "organization_state",
    "institutional_memory",
    "organization_memory",
    "relationship_state",
    "pair_memory",
    "teamwork_state",
}


def audit(path: str | Path) -> dict[str, object]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    primitives = {str(row["name"]): row for row in data["primitives"]}
    missing = ORGANIZATION_PRIMITIVES - primitives.keys()
    if missing:
        raise AssertionError(f"missing organization primitives: {sorted(missing)}")
    native = [
        name
        for name in ORGANIZATION_PRIMITIVES
        if bool(primitives[name]["persistent"])
    ]
    if native:
        raise AssertionError(f"unexpected native organization state: {native}")
    if data["classification"] != "no_native_organization_state":
        raise AssertionError("W5-00 classification must match the audited architecture")
    if data["behavioral_w5_allowed_without_extension"] is not False:
        raise AssertionError("behavioral W5 must be blocked before an organization substrate exists")

    signature = inspect.signature(JointEnvironment.evaluate)
    leaked = set(signature.parameters) & FORBIDDEN_ENVIRONMENT_INPUTS
    if leaked:
        raise AssertionError(f"outcome law reads organizational/social state: {sorted(leaked)}")

    pair_snapshot = RelationshipStateStore().snapshot()
    if any(key.startswith("organization") for key in pair_snapshot):
        raise AssertionError("W4 pair store cannot be relabeled as organization state")

    return {
        "classification": data["classification"],
        "native_organization_primitive_count": 0,
        "pair_state_is_not_organization_state": True,
        "outcome_law_organization_blind": True,
        "requires_architectural_extension": True,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args(argv)
    print(json.dumps(audit(args.manifest), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
