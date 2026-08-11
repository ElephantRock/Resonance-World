"""Compatibility adapter for Resonance Field's existing experiment artifacts."""

from __future__ import annotations

import csv
import json
from collections import Counter
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from typing import Any

from resonance_world.adapters import CheckpointJsonAdapter, FieldAdapter, sha256_json
from resonance_world.protocol import AgentPassport, EvidenceRef, FieldDescriptor

FIELD_ARTIFACT_PROTOCOL_VERSION = "resonance-field-experiment-artifacts-v0.1"


def _load_json_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} must contain a JSON object")
    return value


def _load_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise ValueError(f"missing Resonance Field artifact: {path.name}")
    with path.open(newline="", encoding="utf-8") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise ValueError(f"missing Resonance Field artifact: {path.name}")
    rows = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"{path.name}:{line_number} must contain a JSON object")
        rows.append(value)
    return rows


def _first_timestamp(rows: Iterable[dict[str, Any]], key: str) -> datetime | None:
    values = []
    for row in rows:
        raw = row.get(key)
        if not raw:
            continue
        value = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        if value.tzinfo is None:
            raise ValueError(f"artifact timestamp {key} must include a timezone")
        values.append(value)
    return min(values) if values else None


def _issued_at(
    events: list[dict[str, Any]],
    tasks: list[dict[str, str]],
    traces: list[dict[str, str]],
) -> datetime:
    candidates = [
        _first_timestamp(events, "occurred_at"),
        _first_timestamp(tasks, "created_at"),
        _first_timestamp(traces, "created_at"),
    ]
    present = [value for value in candidates if value is not None]
    if not present:
        raise ValueError("Field artifacts contain no timezone-aware timestamp")
    return min(present)


def _required_text(value: Any, name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"experiment.json missing {name}")
    return text


def _evidence_entry(
    *, field_id: str, kind: str, source_record_id: str, payload: Any
) -> dict[str, Any]:
    uri = f"field://{field_id}/evidence/{kind}/{source_record_id}"
    return {
        "uri": uri,
        "kind": kind,
        "source_record_id": source_record_id,
        "sha256": sha256_json(payload),
        "payload": payload,
    }


def build_resonance_field_checkpoint(
    artifact_dir: str | Path, *, field_id: str | None = None
) -> dict[str, Any]:
    """Convert a canonical Resonance Field artifact directory into a W0 bundle."""

    root = Path(artifact_dir)
    summary_path = root / "experiment.json"
    if not summary_path.exists():
        raise ValueError("missing Resonance Field artifact: experiment.json")

    summary = _load_json_object(summary_path)
    agents = _load_csv(root / "agents.csv")
    events = _load_jsonl(root / "events.jsonl")
    tasks = _load_csv(root / "tasks.csv")
    traces = _load_csv(root / "traces.csv")

    run_id = _required_text(summary.get("run_id"), "run_id")
    resolved_field_id = field_id or f"rf-{run_id}"
    name = _required_text(summary.get("name"), "name")
    ablation = _required_text(summary.get("ablation"), "ablation")
    seed = _required_text(summary.get("seed"), "seed")
    code_sha = _required_text(summary.get("code_sha"), "code_sha")
    cycles = int(summary.get("cycles", 0))
    expected_agents = int(summary.get("agents", 0))
    if cycles <= 0 or expected_agents <= 0:
        raise ValueError("experiment.json cycles and agents must be positive")
    if len(agents) != expected_agents:
        raise ValueError(
            f"agents.csv population mismatch: expected {expected_agents}, got {len(agents)}"
        )

    # The Field run_id identifies the logical seeded experiment, but independent
    # reproductions may contain fresh opaque UUIDs. A checkpoint must therefore
    # identify the exact evidence bundle, not merely the logical run.
    checkpoint_digest = sha256_json(
        {
            "agents": agents,
            "events": events,
            "experiment": summary,
            "tasks": tasks,
            "traces": traces,
        }
    )
    checkpoint_id = f"{run_id}@sha256:{checkpoint_digest}"

    issued_at = _issued_at(events, tasks, traces)
    evidence: list[dict[str, Any]] = []
    evidence_by_key: dict[tuple[str, str], str] = {}

    def add_evidence(kind: str, source_record_id: str, payload: Any) -> str:
        entry = _evidence_entry(
            field_id=resolved_field_id,
            kind=kind,
            source_record_id=source_record_id,
            payload=payload,
        )
        key = (kind, source_record_id)
        if key in evidence_by_key:
            raise ValueError(f"duplicate artifact evidence identity: {kind}/{source_record_id}")
        evidence.append(entry)
        evidence_by_key[key] = str(entry["uri"])
        return str(entry["uri"])

    summary_uri = add_evidence("experiment", run_id, summary)

    agent_uri: dict[str, str] = {}
    for row in agents:
        agent_id = _required_text(row.get("agent_id"), "agents.csv agent_id")
        if agent_id in agent_uri:
            raise ValueError(f"duplicate agent_id in agents.csv: {agent_id}")
        agent_uri[agent_id] = add_evidence("agent", agent_id, row)

    event_uris_by_agent: dict[str, list[str]] = {agent_id: [] for agent_id in agent_uri}
    event_rows_by_agent: dict[str, list[dict[str, Any]]] = {
        agent_id: [] for agent_id in agent_uri
    }
    for index, row in enumerate(events):
        event_id = _required_text(row.get("event_id"), f"events.jsonl row {index} event_id")
        agent_id = _required_text(row.get("agent_id"), f"events.jsonl row {index} agent_id")
        if agent_id not in agent_uri:
            raise ValueError(f"event references unknown experiment agent: {agent_id}")
        uri = add_evidence("decision-event", event_id, row)
        event_uris_by_agent[agent_id].append(uri)
        event_rows_by_agent[agent_id].append(row)

    task_uris: dict[str, str] = {}
    for row in tasks:
        task_id = _required_text(row.get("task_id"), "tasks.csv task_id")
        task_uris[task_id] = add_evidence("market-task", task_id, row)

    trace_uris_by_agent: dict[str, list[str]] = {agent_id: [] for agent_id in agent_uri}
    for row in traces:
        trace_id = _required_text(row.get("trace_id"), "traces.csv trace_id")
        author = str(row.get("author_agent_id") or "").strip()
        uri = add_evidence("trace", trace_id, row)
        if author in trace_uris_by_agent:
            trace_uris_by_agent[author].append(uri)

    passport_rows = []
    for agent_id in sorted(agent_uri):
        awarded_tasks = [
            row for row in tasks if str(row.get("awarded_agent_id") or "").strip() == agent_id
        ]
        completed_tasks = [row for row in awarded_tasks if row.get("status") == "completed"]
        task_success_rate = (
            len(completed_tasks) / len(awarded_tasks) if awarded_tasks else 0.0
        )
        awarded_task_uris = [task_uris[str(row["task_id"])] for row in awarded_tasks]

        action_rows = event_rows_by_agent[agent_id]
        action_counts = Counter(
            str(row.get("proposed_action") or "")
            for row in action_rows
            if row.get("proposed_action")
        )
        action_concentration = (
            max(action_counts.values()) / sum(action_counts.values()) if action_counts else 0.0
        )
        requester_count = len(
            {
                str(row.get("requester_agent_id") or "").strip()
                for row in awarded_tasks
                if str(row.get("requester_agent_id") or "").strip()
            }
        )

        passport_rows.append(
            {
                "agent_id": agent_id,
                "observed_cycles": cycles,
                "completed_tasks": len(completed_tasks),
                "success_rate": task_success_rate,
                "capability_vector": [
                    {
                        "name": "task-execution",
                        "score": task_success_rate,
                        "sample_size": len(awarded_tasks),
                        "evidence_refs": awarded_task_uris,
                    }
                ],
                "calibration_metrics": [],
                "adaptation_metrics": [],
                "specialization_metrics": [
                    {
                        "name": "action-concentration",
                        "value": action_concentration,
                        "evidence_refs": event_uris_by_agent[agent_id],
                    },
                    {
                        "name": "authored-trace-count",
                        "value": float(len(trace_uris_by_agent[agent_id])),
                        "evidence_refs": trace_uris_by_agent[agent_id],
                    },
                ],
                "collaboration_metrics": [
                    {
                        "name": "distinct-requesters-served",
                        "value": float(requester_count),
                        "evidence_refs": awarded_task_uris,
                    }
                ],
                "home_dependency_score": None,
                "portable_capability_score": None,
                "evidence_refs": [summary_uri, agent_uri[agent_id]],
            }
        )

    return {
        "field": {
            "field_id": resolved_field_id,
            "field_protocol_version": FIELD_ARTIFACT_PROTOCOL_VERSION,
            "runtime_version": code_sha,
            "experiment_id": f"{name}:{ablation}:{seed}",
            "checkpoint_id": checkpoint_id,
            "issued_at": issued_at.isoformat(),
        },
        "agents": passport_rows,
        "evidence": evidence,
    }


class ResonanceFieldArtifactAdapter(FieldAdapter):
    """Read-only W0 adapter over canonical Resonance Field experiment artifacts."""

    def __init__(self, artifact_dir: str | Path, *, field_id: str | None = None) -> None:
        bundle = build_resonance_field_checkpoint(artifact_dir, field_id=field_id)
        self._delegate = CheckpointJsonAdapter(bundle)

    def descriptor(self) -> FieldDescriptor:
        return self._delegate.descriptor()

    def list_agent_ids(self) -> tuple[str, ...]:
        return self._delegate.list_agent_ids()

    def passport(self, agent_id: str) -> AgentPassport:
        return self._delegate.passport(agent_id)

    def resolve_evidence(self, ref: EvidenceRef) -> Any:
        return self._delegate.resolve_evidence(ref)
