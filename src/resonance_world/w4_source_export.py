"""Build W4 individual-state sources from immutable Resonance Field evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any

from .w2_source_export import export_sources as export_w2_sources


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> str:
    payload = b"".join(_canonical_bytes(row) + b"\n" for row in rows)
    path.write_bytes(payload)
    return hashlib.sha256(payload).hexdigest()


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def export_sources(
    runs_path: str | Path,
    outcomes_path: str | Path,
    tasks_path: str | Path,
    bids_path: str | Path,
    destination: str | Path,
) -> dict[str, Any]:
    """Reuse the proven W2 capsule derivation and relabel it for W4 provenance."""

    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        export_w2_sources(runs_path, outcomes_path, tasks_path, bids_path, tmp_path)
        candidates = _read_jsonl(tmp_path / "candidates.jsonl")
        capsules = _read_jsonl(tmp_path / "capsules.private.jsonl")
        source_fields = json.loads((tmp_path / "source-fields.json").read_text())

    field_map: dict[str, str] = {}
    for row in source_fields:
        old = str(row["field_id"])
        new = f"w4-source-seed-{int(row['seed'])}"
        field_map[old] = new
        row["field_id"] = new

    for row in candidates:
        row["field_id"] = field_map[str(row["field_id"])]
        if "practice_by_skill" in json.dumps(row, sort_keys=True):
            raise AssertionError("private practice leaked into W4 public source")
    for row in capsules:
        row["field_id"] = field_map[str(row["field_id"])]

    candidates.sort(key=lambda row: (row["field_id"], row["agent_id"]))
    capsules.sort(key=lambda row: (row["field_id"], row["agent_id"]))
    source_fields.sort(key=lambda row: row["field_id"])

    candidate_sha = _write_jsonl(destination / "candidates.jsonl", candidates)
    capsule_sha = _write_jsonl(destination / "capsules.private.jsonl", capsules)
    _write_json(destination / "source-fields.json", source_fields)
    summary = {
        "agent_count": len(candidates),
        "candidate_sha256": candidate_sha,
        "capsule_sha256": capsule_sha,
        "field_count": len(source_fields),
        "seeds": sorted(int(row["seed"]) for row in source_fields),
    }
    _write_json(destination / "w4-source-summary.json", summary)
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("runs", type=Path)
    parser.add_argument("outcomes", type=Path)
    parser.add_argument("tasks", type=Path)
    parser.add_argument("bids", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args(argv)
    result = export_sources(
        args.runs, args.outcomes, args.tasks, args.bids, args.output
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
