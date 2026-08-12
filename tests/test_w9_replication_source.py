import hashlib
import json
from pathlib import Path

from resonance_world import w9_replication_source as source


def _candidate(agent_id: str, evidence_hash: str, checkpoint_hash: str):
    return {
        "agent_id": agent_id,
        "checkpoint_id": f"checkpoint-fixed@sha256:{checkpoint_hash}",
        "field_id": "w4-source-seed-4211",
        "public_features": {"home_success_rate": 0.5, "bid_count": 4.0},
        "public_mission_profile": {
            "dominant_success_skill": "water_systems",
            "secondary_success_skill": None,
        },
        "seed": 4211,
        "source_evidence_sha256": evidence_hash,
    }


def test_normalization_ignores_run_specific_hashes():
    first = [
        _candidate("a", "a" * 64, "1" * 64),
        _candidate("b", "b" * 64, "1" * 64),
    ]
    second = [
        _candidate("a", "c" * 64, "2" * 64),
        _candidate("b", "d" * 64, "2" * 64),
    ]

    normalized_first = source.normalize_candidates(first)
    normalized_second = source.normalize_candidates(second)

    assert normalized_first == normalized_second
    assert normalized_first[0]["source_evidence_sha256"] != "a" * 64
    assert normalized_first[0]["checkpoint_id"].startswith(
        "checkpoint-fixed@sha256:"
    )
    for raw, cooked in zip(first, normalized_first, strict=True):
        assert source._scientific_public_payload(raw) == source._scientific_public_payload(
            cooked
        )


def test_normalize_source_preserves_private_capsule_bytes(tmp_path: Path):
    raw = tmp_path / "raw"
    cooked = tmp_path / "cooked"
    raw.mkdir()
    candidates = [
        _candidate("a", "a" * 64, "1" * 64),
        _candidate("b", "b" * 64, "1" * 64),
    ]
    (raw / "candidates.jsonl").write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in candidates),
        encoding="utf-8",
    )
    private = (
        b'{"agent_id":"a","practice_by_skill":{"water_systems":2}}\n'
        b'{"agent_id":"b","practice_by_skill":{"water_systems":3}}\n'
    )
    (raw / "capsules.private.jsonl").write_bytes(private)
    (raw / "source-fields.json").write_text(
        '[{"field_id":"w4-source-seed-4211","seed":4211}]\n',
        encoding="utf-8",
    )

    manifest = source.normalize_source(raw, cooked)

    assert (cooked / "capsules.private.jsonl").read_bytes() == private
    assert manifest["candidate_count"] == 2
    assert manifest["field_ids"] == ["w4-source-seed-4211"]
    assert manifest["raw_candidates_sha256"] == hashlib.sha256(
        (raw / "candidates.jsonl").read_bytes()
    ).hexdigest()
    assert manifest["normalized_candidates_sha256"] == hashlib.sha256(
        (cooked / "candidates.jsonl").read_bytes()
    ).hexdigest()


def test_normalization_rejects_inconsistent_checkpoint_prefixes():
    candidates = [
        _candidate("a", "a" * 64, "1" * 64),
        {
            **_candidate("b", "b" * 64, "2" * 64),
            "checkpoint_id": f"different-prefix@sha256:{'2' * 64}",
        },
    ]
    try:
        source.normalize_candidates(candidates)
    except ValueError as exc:
        assert "inconsistent checkpoint prefixes" in str(exc)
    else:
        raise AssertionError("expected inconsistent checkpoint prefixes to fail")
