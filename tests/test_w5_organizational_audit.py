import json
from pathlib import Path

import pytest

from resonance_world.w5_organizational_audit import audit


def test_w5_00_classifies_current_world_as_no_native_organization_state() -> None:
    result = audit("configs/w5/organizational-state-audit.json")
    assert result["classification"] == "no_native_organization_state"
    assert result["native_organization_primitive_count"] == 0
    assert result["pair_state_is_not_organization_state"] is True
    assert result["outcome_law_organization_blind"] is True
    assert result["requires_architectural_extension"] is True


def test_w5_00_rejects_relabeling_pair_memory_as_native_organization_state(tmp_path: Path) -> None:
    source = json.loads(Path("configs/w5/organizational-state-audit.json").read_text())
    for row in source["primitives"]:
        if row["name"] == "organization_episode_memory":
            row["persistent"] = True
            row["source"] = "src/resonance_world/w4a_joint_learning.py:SharedPairMemory"
    path = tmp_path / "tampered.json"
    path.write_text(json.dumps(source), encoding="utf-8")
    with pytest.raises(AssertionError, match="unexpected native organization state"):
        audit(path)
