"""Normalize run-specific W9-07 public provenance without changing scientific state."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any, Mapping, Sequence

NORMALIZATION_VERSION = "w9-07-semantic-public-provenance-v0.1"
_PROVENANCE_FIELDS = frozenset({"checkpoint_id", "source_evidence_sha256"})


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _scientific_public_payload(candidate: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in candidate.items()
        if key not in _PROVENANCE_FIELDS
    }


def _checkpoint_prefix(value: object) -> str:
    text = str(value)
    marker = "@sha256:"
    return text.split(marker, 1)[0] if marker in text else text


def normalize_candidates(
    candidates: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Replace run-specific hashes with hashes of the frozen scientific public view."""

    grouped: dict[str, list[Mapping[str, Any]]] = {}
    for candidate in candidates:
        grouped.setdefault(str(candidate["field_id"]), []).append(candidate)

    field_digest: dict[str, str] = {}
    field_prefix: dict[str, str] = {}
    for field_id, rows in grouped.items():
        ordered = sorted(rows, key=lambda row: str(row["agent_id"]))
        payloads = [_scientific_public_payload(row) for row in ordered]
        field_digest[field_id] = _sha256(payloads)
        prefixes = {_checkpoint_prefix(row["checkpoint_id"]) for row in ordered}
        if len(prefixes) != 1:
            raise ValueError(
                f"source Field {field_id} has inconsistent checkpoint prefixes: {sorted(prefixes)}"
            )
        field_prefix[field_id] = next(iter(prefixes))

    normalized: list[dict[str, Any]] = []
    for candidate in candidates:
        value = dict(candidate)
        field_id = str(value["field_id"])
        scientific = _scientific_public_payload(value)
        value["source_evidence_sha256"] = _sha256(scientific)
        value["checkpoint_id"] = (
            f"{field_prefix[field_id]}@sha256:{field_digest[field_id]}"
        )
        normalized.append(value)

    return normalized


def normalize_source(input_dir: str | Path, output_dir: str | Path) -> dict[str, Any]:
    """Copy a raw source export and normalize only its public provenance fields."""

    source = Path(input_dir)
    target = Path(output_dir)
    if source.resolve() == target.resolve():
        raise ValueError("normalization input and output directories must differ")
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source, target)

    raw_candidate_path = source / "candidates.jsonl"
    candidate_path = target / "candidates.jsonl"
    raw_candidates = _read_jsonl(raw_candidate_path)
    normalized = normalize_candidates(raw_candidates)
    candidate_path.write_text(
        "".join(
            json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
            + "\n"
            for row in normalized
        ),
        encoding="utf-8",
    )

    # The transform is provenance-only by construction. Fail closed if any
    # scientific public field changed or if the private capsule bytes changed.
    for raw, cooked in zip(raw_candidates, normalized, strict=True):
        if _scientific_public_payload(raw) != _scientific_public_payload(cooked):
            raise AssertionError("W9-07 normalization changed scientific public state")
    raw_private = (source / "capsules.private.jsonl").read_bytes()
    cooked_private = (target / "capsules.private.jsonl").read_bytes()
    if raw_private != cooked_private:
        raise AssertionError("W9-07 normalization changed private source state")

    manifest = {
        "version": NORMALIZATION_VERSION,
        "candidate_count": len(normalized),
        "field_ids": sorted({str(row["field_id"]) for row in normalized}),
        "raw_candidates_sha256": hashlib.sha256(raw_candidate_path.read_bytes()).hexdigest(),
        "normalized_candidates_sha256": hashlib.sha256(candidate_path.read_bytes()).hexdigest(),
        "normalized_scientific_payload_sha256": _sha256(
            [
                _scientific_public_payload(row)
                for row in sorted(
                    normalized,
                    key=lambda row: (str(row["field_id"]), str(row["agent_id"])),
                )
            ]
        ),
    }
    (target / "w9-07-source-normalization.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    manifest = normalize_source(args.input_dir, args.output_dir)
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
