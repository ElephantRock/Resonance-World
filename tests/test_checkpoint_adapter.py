from __future__ import annotations

from resonance_world.adapters import CheckpointJsonAdapter, sha256_json


def checkpoint_bundle(field_id: str = "field-a") -> dict:
    task_payload = {
        "agent_id": "agent-01",
        "task_id": "task-9",
        "outcome": "success",
    }
    metric_payload = {
        "agent_id": "agent-01",
        "metric": "domain-alpha-success",
        "value": 0.875,
        "sample_size": 16,
    }
    return {
        "field": {
            "field_id": field_id,
            "field_protocol_version": "field-evidence-v1",
            "runtime_version": "0.1-test",
            "experiment_id": "w0-fixture",
            "checkpoint_id": "checkpoint-001",
            "issued_at": "2026-08-11T03:00:00Z",
        },
        "agents": [
            {
                "agent_id": "agent-01",
                "observed_cycles": 180,
                "completed_tasks": 16,
                "success_rate": 0.875,
                "capability_vector": [
                    {
                        "name": "domain-alpha",
                        "score": 0.875,
                        "sample_size": 16,
                        "evidence_refs": ["field://field-a/evidence/metric-1"],
                    }
                ],
                "calibration_metrics": [],
                "adaptation_metrics": [],
                "specialization_metrics": [
                    {
                        "name": "award-mutual-information",
                        "value": 0.42,
                        "evidence_refs": ["field://field-a/evidence/metric-1"],
                    }
                ],
                "collaboration_metrics": [],
                "home_dependency_score": 0.3,
                "portable_capability_score": None,
                "evidence_refs": ["field://field-a/evidence/task-9"],
            }
        ],
        "evidence": [
            {
                "uri": "field://field-a/evidence/task-9",
                "kind": "task-result",
                "source_record_id": "task-9",
                "sha256": sha256_json(task_payload),
                "payload": task_payload,
            },
            {
                "uri": "field://field-a/evidence/metric-1",
                "kind": "metric",
                "source_record_id": "metric-1",
                "sha256": sha256_json(metric_payload),
                "payload": metric_payload,
            },
        ],
    }


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
