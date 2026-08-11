from resonance_world.adapters import sha256_json


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
    task_uri = f"field://{field_id}/evidence/task-9"
    metric_uri = f"field://{field_id}/evidence/metric-1"
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
                        "evidence_refs": [metric_uri],
                    }
                ],
                "calibration_metrics": [],
                "adaptation_metrics": [],
                "specialization_metrics": [
                    {
                        "name": "award-mutual-information",
                        "value": 0.42,
                        "evidence_refs": [metric_uri],
                    }
                ],
                "collaboration_metrics": [],
                "home_dependency_score": 0.3,
                "portable_capability_score": None,
                "evidence_refs": [task_uri],
            }
        ],
        "evidence": [
            {
                "uri": task_uri,
                "kind": "task-result",
                "source_record_id": "task-9",
                "sha256": sha256_json(task_payload),
                "payload": task_payload,
            },
            {
                "uri": metric_uri,
                "kind": "metric",
                "source_record_id": "metric-1",
                "sha256": sha256_json(metric_payload),
                "payload": metric_payload,
            },
        ],
    }
