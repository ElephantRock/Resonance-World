from __future__ import annotations

import json
from pathlib import Path

from scripts.materialize_o2_benchmarks import materialize


def test_o2_materialization_matches_preoutcome_lock(tmp_path: Path) -> None:
    lock = json.loads(Path("research/o2/apparatus-lock.json").read_text())
    generated = materialize(tmp_path / "o2")

    assert generated["semantic_template_count"] == 10
    assert generated["collision_pair_count"] == 40
    assert generated["history_count"] == 80

    for name, expected in lock["roots"].items():
        actual = generated["roots"][name]
        assert actual["file_count"] == expected["file_count"]
        assert actual["manifest_root_sha256"] == expected["manifest_root_sha256"]


def test_o2_r0_twins_are_byte_identical(tmp_path: Path) -> None:
    root = tmp_path / "o2"
    materialize(root)

    pairs: dict[str, list[bytes]] = {}
    for path in sorted((root / "r0").glob("*.json")):
        pair_id = path.name.split("--", 1)[0]
        pairs.setdefault(pair_id, []).append(path.read_bytes())

    assert len(pairs) == 40
    assert all(len(rows) == 2 and rows[0] == rows[1] for rows in pairs.values())


def test_o2_plane_e_excludes_template_and_variant_keys(tmp_path: Path) -> None:
    root = tmp_path / "o2"
    materialize(root)

    paths = sorted((root / "plane_e").glob("*.json"))
    assert len(paths) == 80
    for path in paths:
        doc = json.loads(path.read_text())
        assert "template" not in doc
        assert "variant" not in doc
        for event in doc["events"]:
            assert "template" not in event
            assert "variant" not in event
