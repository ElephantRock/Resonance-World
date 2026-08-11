from __future__ import annotations

import json
from pathlib import Path

from resonance_world.resonance_field_artifacts import (
    FIELD_ARTIFACT_PROTOCOL_VERSION,
    ResonanceFieldArtifactAdapter,
)


def write_artifacts(root: Path, *, agent_count: int = 2) -> None:
    summary = {
        "run_id": "run-001",
        "name": "first-emergence-v0.1",
        "ablation": "full",
        "seed": 101,
        "config_hash": "config-hash",
        "code_sha": "abc123",
        "cycles": 40,
        "agents": agent_count,
        "metrics": {"behavioral_specialization": 0.4},
    }
    (root / "experiment.json").write_text(
        json.dumps(summary, sort_keys=True), encoding="utf-8"
    )
    (root / "agents.csv").write_text(
        "agent_slot,agent_id,initial_credits,ending_balance,compute_spent\n"
        "0,agent-01,100,70,30\n"
        "1,agent-02,100,60,40\n",
        encoding="utf-8",
    )
    events = [
        {
            "event_id": "event-01",
            "agent_id": "agent-01",
            "occurred_at": "2026-01-01T00:00:00+00:00",
            "proposed_action": "WRITE_TRACE",
            "policy_result": "allow",
            "outcome_status": "completed",
            "confidence": 0.8,
            "request_id": "request-01",
            "correlation_id": "correlation-01",
            "retrieved_trace_ids": [],
            "output_trace_ids": ["trace-01"],
            "compute_spent": 1,
        },
        {
            "event_id": "event-02",
            "agent_id": "agent-01",
            "occurred_at": "2026-01-01T00:00:01+00:00",
            "proposed_action": "QUERY_SUBSTRATE",
            "policy_result": "allow",
            "outcome_status": "completed",
            "confidence": 0.7,
            "request_id": "request-02",
            "correlation_id": "correlation-02",
            "retrieved_trace_ids": ["trace-02"],
            "output_trace_ids": [],
            "compute_spent": 1,
        },
        {
            "event_id": "event-03",
            "agent_id": "agent-02",
            "occurred_at": "2026-01-01T00:00:02+00:00",
            "proposed_action": "BID_TASK",
            "policy_result": "allow",
            "outcome_status": "completed",
            "confidence": 0.9,
            "request_id": "request-03",
            "correlation_id": "correlation-03",
            "retrieved_trace_ids": [],
            "output_trace_ids": [],
            "compute_spent": 1,
        },
    ]
    (root / "events.jsonl").write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in events),
        encoding="utf-8",
    )
    (root / "tasks.csv").write_text(
        "task_id,requester_agent_id,budget,status,awarded_agent_id,created_at,awarded_at,completed_at\n"
        "task-01,agent-01,10,completed,agent-02,2026-01-01T00:00:00+00:00,2026-01-01T00:00:02+00:00,2026-01-01T00:00:03+00:00\n",
        encoding="utf-8",
    )
    (root / "traces.csv").write_text(
        "trace_id,author_agent_id,kind,created_at,initial_energy,energy_anchor,half_life_seconds,confidence,quality_score\n"
        "trace-01,agent-01,OBSERVATION,2026-01-01T00:00:00+00:00,0.75,0.75,60,0.8,0.7\n"
        "trace-02,agent-02,HYPOTHESIS,2026-01-01T00:00:01+00:00,0.75,0.75,60,0.8,0.7\n",
        encoding="utf-8",
    )


def test_existing_field_artifacts_produce_evidence_backed_passports(tmp_path: Path) -> None:
    write_artifacts(tmp_path)
    adapter = ResonanceFieldArtifactAdapter(tmp_path, field_id="field-a")

    descriptor = adapter.descriptor()
    assert descriptor.field_id == "field-a"
    assert descriptor.field_protocol_version == FIELD_ARTIFACT_PROTOCOL_VERSION
    assert adapter.list_agent_ids() == ("agent-01", "agent-02")

    passport = adapter.passport("agent-02")
    assert passport.observed_cycles == 40
    assert passport.completed_tasks == 1
    assert passport.success_rate == 1.0
    assert passport.portable_capability_score is None
    assert passport.capability_vector[0].name == "task-execution"
    assert passport.capability_vector[0].sample_size == 1
    assert passport.collaboration_metrics[0].value == 1.0

    for ref in passport.evidence_refs + passport.capability_vector[0].evidence_refs:
        assert adapter.resolve_evidence(ref) is not None


def test_artifact_adapter_rejects_population_mismatch(tmp_path: Path) -> None:
    write_artifacts(tmp_path, agent_count=20)

    try:
        ResonanceFieldArtifactAdapter(tmp_path)
    except ValueError as exc:
        assert "population mismatch" in str(exc)
    else:
        raise AssertionError("population mismatch should be rejected")
