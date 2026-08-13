#!/usr/bin/env python3
"""Evaluate the preregistered O1 reconstruction-validity gates."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

from resonance_world.context_graph_runtime import (
    HISTORICAL_SUBSTRATE_ENABLED,
    INTEGRATION_MODE,
    STANDALONE_RELEASE_COMMIT,
)
from resonance_world.o1_reconstruction import canonical_bytes

WORLD_BASE = "1f3c12416b43b5b6b56eb4ce69453b067cae99c6"
PIANO_HEAD = "52aa261f22328918c21798befd494bf42943b4b8"
O0_EVIDENCE_SHA256 = "7e8ef1c9fcbfbc16eb5e50db477dcacc2b6830af86b50b8cf44c965c21ca456a"
O0_TRACE_SHA256 = "dd8b5a30cf9ed85f96fcb9164f16ec3d958d7ccfc10c5ab157079e119978bb40"
FORBIDDEN_PRODUCT_TOKENS = (
    '"practice_by_skill"',
    '"hidden_regime"',
    '"target_hypothesis"',
    '"target_policy"',
    '"neutral_preferred_policy"',
    '"expected_action"',
    '"spoof_action"',
    '"legitimate_notice_id"',
    '"spoof_notice_id"',
    '"advance_beyond_phase5c_decision_relevant_memory"',
)


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_planes(directory: Path, schema: str) -> dict[str, dict[str, Any]]:
    values: dict[str, dict[str, Any]] = {}
    for path in sorted(directory.glob("*.json")):
        value = _read_json(path)
        if value.get("schema") != schema:
            raise ValueError(f"unexpected schema in {path}")
        family = str(value["family"])
        if family in values:
            raise ValueError(f"duplicate family {family}")
        values[family] = value
    if set(values) != {"A", "T", "S"}:
        raise ValueError(f"missing registered plane families: {set(values)}")
    return values


def _expected_r_events(trace: dict[str, Any]) -> list[dict[str, Any]]:
    expected = []
    for unit in trace["units"]:
        condition = str(unit["communication_condition"])
        seed = int(unit["seed"])
        scope_id = f"o0:{condition}:{seed}"
        for ordinal, episode in enumerate(unit["episodes"], 1):
            expected.append(
                {
                    "family": "R",
                    "scope_id": scope_id,
                    "event_id": str(episode["mission_id"]),
                    "observed_at": ordinal,
                    "source_class": "world_observation",
                    "fields": {
                        "action_a": str(episode["action_a"]),
                        "action_b": str(episode["action_b"]),
                        "context": str(episode["context"]),
                        "event_type": "joint_episode",
                        "lead_skill": "planning",
                        "outcome": "success" if bool(episode["success"]) else "failure",
                        "participant_a": str(episode["agent_a"]),
                        "participant_b": str(episode["agent_b"]),
                        "support_skill": "verification",
                    },
                }
            )
    return expected


def _expected_e_events(planes: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    expected = []
    for family in ("A", "T", "S"):
        for event in planes[family]["events"]:
            expected.append(
                {
                    "family": family,
                    "scope_id": str(event["scope_id"]),
                    "event_id": str(event["event_id"]),
                    "observed_at": int(event["observed_at"]),
                    "source_class": str(event["source_class"]),
                    "fields": dict(sorted(dict(event["fields"]).items())),
                }
            )
    return expected


def _canonical_event_ledger(events: list[dict[str, Any]]) -> dict[str, Any]:
    events.sort(
        key=lambda row: (
            str(row["family"]),
            str(row["scope_id"]),
            int(row["observed_at"]),
            str(row["event_id"]),
        )
    )
    return {"schema": "o1-event-ledger-v0.1", "events": events}


def _event_rows(event_ledger: dict[str, Any], family: str) -> list[dict[str, Any]]:
    return [dict(row) for row in event_ledger["events"] if str(row["family"]) == family]


def _expected_entity_ledger(event_ledger: dict[str, Any]) -> dict[str, Any]:
    entities: set[tuple[str, str]] = set()
    relations: set[tuple[str, str, str]] = set()
    for row in event_ledger["events"]:
        family = str(row["family"])
        fields = dict(row["fields"])
        event_id = str(row["event_id"])
        entities.add(("event", event_id))
        if family == "R":
            for key in ("participant_a", "participant_b"):
                agent_id = str(fields[key])
                entities.add(("agent", agent_id))
                relations.add((event_id, "participant", agent_id))
        elif family == "A":
            entities.add(("organization", str(fields["organization_id"])))
            entities.add(("agent", str(fields["agent_id"])))
            entities.add(("role", str(fields["role_id"])))
            for key in ("notice_1_id", "notice_2_id"):
                notice_id = str(fields[key])
                entities.add(("authority_notice", notice_id))
                relations.add((event_id, "presents_notice", notice_id))
            if "verified_notice_id" in fields:
                relations.add(
                    (event_id, "world_verifies_notice", str(fields["verified_notice_id"]))
                )
        elif family == "T":
            entities.add(("organization", str(fields["organization_id"])))
            if "generation_id" in fields:
                entities.add(
                    (
                        "organization_generation",
                        f"{fields['organization_id']}:{fields['generation_id']}",
                    )
                )
            if fields.get("member_ids"):
                for member_id in json.loads(str(fields["member_ids"])):
                    entities.add(("agent", str(member_id)))
                    relations.add((event_id, "member", str(member_id)))
        elif family == "S":
            if fields.get("source_id"):
                entities.add(("source", str(fields["source_id"])))
            if fields.get("organization_id"):
                entities.add(("organization", str(fields["organization_id"])))
            if fields.get("agent_id"):
                entities.add(("agent", str(fields["agent_id"])))
            if fields.get("source_id") and fields.get("agent_id"):
                relations.add(
                    (str(fields["agent_id"]), "home_source", str(fields["source_id"]))
                )
            if (
                fields.get("event_type") == "contract_service_right"
                and fields.get("organization_id")
                and fields.get("agent_id")
            ):
                relations.add((event_id, "contracts_agent", str(fields["agent_id"])))
                relations.add(
                    (event_id, "serves_organization", str(fields["organization_id"]))
                )
            if fields.get("event_type") == "organization_service_cycle":
                for key, predicate in (
                    ("lead_agent_id", "executes_lead"),
                    ("support_agent_id", "executes_support"),
                ):
                    if fields.get(key):
                        entities.add(("agent", str(fields[key])))
                        relations.add((event_id, predicate, str(fields[key])))
    return {
        "schema": "o1-entity-ledger-v0.1",
        "entities": [
            {"entity_type": kind, "entity_id": entity_id}
            for kind, entity_id in sorted(entities)
        ],
        "relations": [
            {"subject": subject, "predicate": predicate, "object": object_id}
            for subject, predicate, object_id in sorted(relations)
        ],
    }


def _expected_relationship_ledger(event_ledger: dict[str, Any]) -> dict[str, Any]:
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for row in _event_rows(event_ledger, "R"):
        fields = dict(row["fields"])
        first, second = sorted((str(fields["participant_a"]), str(fields["participant_b"])))
        grouped.setdefault((str(row["scope_id"]), first, second), []).append(row)
    histories = []
    for (scope_id, first, second), rows in sorted(grouped.items()):
        rows.sort(key=lambda item: (int(item["observed_at"]), str(item["event_id"])))
        interactions = [
            {
                "event_id": str(row["event_id"]),
                "observed_at": int(row["observed_at"]),
                "action_a": str(row["fields"]["action_a"]),
                "action_b": str(row["fields"]["action_b"]),
                "outcome": str(row["fields"]["outcome"]),
            }
            for row in rows
        ]
        success_count = sum(item["outcome"] == "success" for item in interactions)
        histories.append(
            {
                "scope_id": scope_id,
                "participant_pair": [first, second],
                "interaction_count": len(interactions),
                "success_count": success_count,
                "failure_count": len(interactions) - success_count,
                "interactions": interactions,
            }
        )
    return {"schema": "o1-relationship-ledger-v0.1", "histories": histories}


def _expected_authority_ledger(event_ledger: dict[str, Any]) -> dict[str, Any]:
    records = []
    for row in _event_rows(event_ledger, "A"):
        fields = dict(row["fields"])
        record: dict[str, Any] = {
            "scope_id": str(row["scope_id"]),
            "event_id": str(row["event_id"]),
            "observed_at": int(row["observed_at"]),
            "organization_id": str(fields["organization_id"]),
            "arm": str(fields["arm"]),
            "scenario_id": str(fields["scenario_id"]),
            "agent_id": str(fields["agent_id"]),
            "role_id": str(fields["role_id"]),
            "notices": [
                {"notice_id": str(fields["notice_1_id"]), "action": str(fields["notice_1_action"])},
                {"notice_id": str(fields["notice_2_id"]), "action": str(fields["notice_2_action"])},
            ],
            "controller_action": str(fields["controller_action"]),
            "intended_action": str(fields["intended_action"]),
            "speech_action": str(fields["speech_action"]),
            "acknowledgement": {
                "policy_result": str(fields["policy_result"]),
                "outcome_status": str(fields["outcome_status"]),
                "grounded_success": str(fields["grounded_success"]) == "true",
                "action_request_id": str(fields["action_request_id"]),
                "correlation_id": str(fields["correlation_id"]),
            },
        }
        if "verified_notice_id" in fields:
            record["verification"] = {
                "verified_notice_id": str(fields["verified_notice_id"]),
                "rejected_notice_id": str(fields["rejected_notice_id"]),
            }
        records.append(record)
    records.sort(key=lambda row: (row["arm"], row["scenario_id"]))
    return {"schema": "o1-authority-ledger-v0.1", "records": records}


def _expected_organization_lineage(event_ledger: dict[str, Any]) -> dict[str, Any]:
    by_org: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for row in _event_rows(event_ledger, "T"):
        fields = dict(row["fields"])
        organization_id = str(fields["organization_id"])
        target = by_org.setdefault(
            organization_id, {"generations": [], "memory": [], "decisions": []}
        )
        event_type = str(fields["event_type"])
        if event_type == "organization_generation":
            target["generations"].append(
                {
                    "generation_id": str(fields["generation_id"]),
                    "predecessor_generation_id": str(fields["predecessor_generation_id"]),
                    "member_ids": list(json.loads(str(fields["member_ids"]))),
                    "source_field_id": str(fields["source_field_id"]),
                }
            )
        elif event_type == "institutional_memory_summary":
            target["memory"].append(
                {
                    "arm": str(fields["arm"]),
                    "generation_id": str(fields["generation_id"]),
                    "event_id": str(row["event_id"]),
                    "evidence_episodes": int(fields["evidence_episodes"]),
                    "role_specific_posterior": str(fields["role_specific_posterior"]),
                    "cross_coverage_posterior": str(fields["cross_coverage_posterior"]),
                    "forecast_specialist": str(fields["forecast_specialist"]),
                    "forecast_balanced": str(fields["forecast_balanced"]),
                    "forecast_preferred_strategy": str(fields["forecast_preferred_strategy"]),
                }
            )
        elif event_type == "post_turnover_decision":
            target["decisions"].append(
                {
                    "arm": str(fields["arm"]),
                    "unit_id": str(fields["unit_id"]),
                    "generation_id": str(fields["generation_id"]),
                    "context": str(fields["context"]),
                    "lead_skill": str(fields["lead_skill"]),
                    "support_skill": str(fields["support_skill"]),
                    "memory_source_ref": str(fields["memory_source_ref"]),
                    "forecast_preferred_strategy": str(fields["forecast_preferred_strategy"]),
                    "chosen_strategy": str(fields["chosen_strategy"]),
                    "intended_strategy": str(fields["intended_strategy"]),
                    "speech_strategy": str(fields["speech_strategy"]),
                    "lead_member_id": str(fields["lead_member_id"]),
                    "support_member_id": str(fields["support_member_id"]),
                    "evaluation_trials": int(fields["evaluation_trials"]),
                    "success_count": int(fields["success_count"]),
                    "grounded_success": str(fields["grounded_success"]) == "true",
                    "acknowledgement": str(fields["acknowledgement"]),
                }
            )
    organizations = []
    for organization_id, value in sorted(by_org.items()):
        generations = sorted(value["generations"], key=lambda row: row["generation_id"])
        if len(generations) != 2:
            raise AssertionError("canonical O1 T target lacks exactly two generations")
        old_members = set(generations[0]["member_ids"])
        new_members = set(generations[1]["member_ids"])
        turnover = 1.0 - len(old_members & new_members) / len(old_members)
        organizations.append(
            {
                "organization_id": organization_id,
                "generations": generations,
                "turnover_fraction": turnover,
                "memory": sorted(value["memory"], key=lambda row: row["arm"]),
                "decisions": sorted(value["decisions"], key=lambda row: row["arm"]),
            }
        )
    return {"schema": "o1-organization-lineage-v0.1", "organizations": organizations}


__all__ = [
    "argparse", "hashlib", "json", "math", "Path", "Any",
    "HISTORICAL_SUBSTRATE_ENABLED", "INTEGRATION_MODE",
    "STANDALONE_RELEASE_COMMIT", "canonical_bytes", "WORLD_BASE",
    "PIANO_HEAD", "O0_EVIDENCE_SHA256", "O0_TRACE_SHA256",
    "FORBIDDEN_PRODUCT_TOKENS", "_read_json", "_sha256_file",
    "_load_planes", "_expected_r_events", "_expected_e_events",
    "_canonical_event_ledger", "_event_rows", "_expected_entity_ledger",
    "_expected_relationship_ledger", "_expected_authority_ledger",
    "_expected_organization_lineage",
]
