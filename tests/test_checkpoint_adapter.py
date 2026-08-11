from __future__ import annotations

from resonance_world.adapters import CheckpointJsonAdapter, sha256_json
from tests.fixtures import checkpoint_bundle


def test_passport_is_evidence_backed_and_deterministic() -> None:
    bundle = checkpoint_bundle()
    first = CheckpointJsonAdapter(bundle)
    second = CheckpointJsonAdapter(bundle)

    passport = first.passport("agent-01")

    assert passport.source_field_id == "field-a"
    assert passport.completed_tasks == 16
    assert passport.portable_capability_score is None
    assert passport.capability_vector[0].name == "domain-alpha"
    assert passport.canonical_bytes() == second.passport("agent-01").canonical_bytes()

    for ref in passport.evidence_refs + passport.capability_vector[0].evidence_refs:
        payload = first.resolve_evidence(ref)
        assert sha256_json(payload) == ref.sha256


def test_adapter_rejects_tampered_evidence() -> None:
    bundle = checkpoint_bundle()
    bundle["evidence"][0]["payload"]["outcome"] = "failure"

    try:
        CheckpointJsonAdapter(bundle)
    except ValueError as exc:
        assert "digest mismatch" in str(exc)
    else:
        raise AssertionError("tampered evidence should be rejected")
