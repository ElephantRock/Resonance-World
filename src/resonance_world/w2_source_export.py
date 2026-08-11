"""Build W2 public recruitment profiles and private capsules from Field evidence."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .w1_source_export import export_sources as export_w1_sources


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> str:
    payload = b"".join(_canonical_bytes(row) + b"\n" for row in rows)
    path.write_bytes(payload)
    return hashlib.sha256(payload).hexdigest()


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _successful_skill_labels(outcomes_path: str | Path) -> dict[str, tuple[str | None, str | None]]:
    counts: dict[str, Counter[str]] = defaultdict(Counter)
    with Path(outcomes_path).open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if str(row["success"]).lower() not in {"t", "true", "1", "yes"}:
                continue
            counts[row["winner_agent_id"]][row["required_skill"]] += 1
    labels: dict[str, tuple[str | None, str | None]] = {}
    for agent_id, skill_counts in counts.items():
        ranked = sorted(skill_counts, key=lambda skill: (-skill_counts[skill], skill))
        labels[agent_id] = (
            ranked[0] if ranked else None,
            ranked[1] if len(ranked) > 1 else None,
        )
    return labels


def export_sources(
    runs_path: str | Path,
    outcomes_path: str | Path,
    tasks_path: str | Path,
    bids_path: str | Path,
    destination: str | Path,
) -> dict[str, Any]:
    """Export lossy public specialization labels separately from private practice state."""

    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    labels = _successful_skill_labels(outcomes_path)
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        export_w1_sources(runs_path, outcomes_path, tasks_path, bids_path, tmp_path)
        candidates = _read_jsonl(tmp_path / "candidates.jsonl")
        capsules = _read_jsonl(tmp_path / "capsules.private.jsonl")
        source_fields = json.loads((tmp_path / "source-fields.json").read_text())

    field_map: dict[str, str] = {}
    for row in source_fields:
        field_map[str(row["field_id"])] = f"w2-source-seed-{int(row['seed'])}"
        row["field_id"] = field_map[str(row["field_id"])]

    for candidate in candidates:
        old_field = str(candidate["field_id"])
        candidate["field_id"] = field_map[old_field]
        dominant, secondary = labels.get(str(candidate["agent_id"]), (None, None))
        candidate["public_mission_profile"] = {
            "dominant_success_skill": dominant,
            "secondary_success_skill": secondary,
        }
        if "practice_by_skill" in json.dumps(candidate, sort_keys=True):
            raise AssertionError("private practice leaked into W2 public candidate")

    for capsule in capsules:
        capsule["field_id"] = field_map[str(capsule["field_id"])]

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
    _write_json(destination / "w2-01-source-summary.json", summary)
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("runs", type=Path)
    parser.add_argument("outcomes", type=Path)
    parser.add_argument("tasks", type=Path)
    parser.add_argument("bids", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args(argv)
    result = export_sources(args.runs, args.outcomes, args.tasks, args.bids, args.output)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
