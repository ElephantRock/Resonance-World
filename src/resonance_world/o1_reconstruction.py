"""Researcher-side O1 reconstruction helpers.

This module is deliberately pure: it consumes serialized evidence records and produces
deterministic researcher-side ledgers. It has no ContextGraph import and no participant,
controller, environment, Field, or institutional-state mutation surface.
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from collections.abc import Iterable, Mapping
from typing import Any


def canonical_bytes(value: object) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
    ).encode("utf-8")


def sha256_bytes(value: object) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def family_for_scope(scope_id: str) -> str:
    if scope_id.startswith("o0:"):
        return "R"
    parts = scope_id.split(":")
    if len(parts) >= 2 and parts[0] == "o1" and parts[1] in {"A", "T", "S"}:
        return parts[1]
    raise ValueError(f"unregistered O1 evidence scope: {scope_id!r}")


def claims_to_event_ledger(claims: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    grouped: dict[tuple[str, str, int, str], dict[str, str]] = {}
    for claim in claims:
        scope_id = str(claim["scope_id"])
        subject = str(claim["subject"])
        observed_at = int(claim["observed_at"])
        source_class = str(claim["source_class"])
        key = (scope_id, subject, observed_at, source_class)
        fields = grouped.setdefault(key, {})
        predicate = str(claim["predicate"])
        if predicate in fields:
            raise ValueError(f"duplicate predicate {predicate!r} for {key!r}")
        fields[predicate] = str(claim["object"])

    events = [
        {
            "family": family_for_scope(scope_id),
            "scope_id": scope_id,
            "event_id": subject,
            "observed_at": observed_at,
            "source_class": source_class,
            "fields": dict(sorted(fields.items())),
        }
        for (scope_id, subject, observed_at, source_class), fields in grouped.items()
    ]
    events.sort(
        key=lambda row: (
            str(row["family"]),
            str(row["scope_id"]),
            int(row["observed_at"]),
            str(row["event_id"]),
        )
    )
    return {"schema": "o1-event-ledger-v0.1", "events": events}


def _events(event_ledger: Mapping[str, Any], family: str) -> list[dict[str, Any]]:
    return [
        dict(row)
        for row in event_ledger["events"]
        if str(row["family"]) == family
    ]


def entity_ledger(event_ledger: Mapping[str, Any]) -> dict[str, Any]:
    entities: set[tuple[str, str]] = set()
    relations: set[tuple[str, str, str]] = set()
    for row in event_ledger["events"]:
        family = str(row["family"])
        fields = dict(row["fields"])
        event_id = str(row["event_id"])
        entities.add(("event", event_id))
        if family == "R":
            for key in ("participant_a", "participant_b"):
                entities.add(("agent", str(fields[key])))
                relations.add((event_id, "participant", str(fields[key])))
        elif family == "A":
            entities.add(("organization", str(fields["organization_id"])))
            entities.add(("agent", str(fields["agent_id"])))
            entities.add(("role", str(fields["role_id"])))
            for key in ("notice_1_id", "notice_2_id"):
                entities.add(("authority_notice", str(fields[key])))
                relations.add((event_id, "presents_notice", str(fields[key])))
            if "verified_notice_id" in fields:
                relations.add(
                    (event_id, "world_verifies_notice", str(fields["verified_notice_id"]))
                )
        elif family == "T":
            entities.add(("organization", str(fields["organization_id"])))
            if "generation_id" in fields:
                generation = f"{fields['organization_id']}:{fields['generation_id']}"
                entities.add(("organization_generation", generation))
            member_text = fields.get("member_ids")
            if member_text:
                for member_id in json.loads(member_text):
                    entities.add(("agent", str(member_id)))
                    relations.add((event_id, "member", str(member_id)))
        elif family == "S":
            source_id = fields.get("source_id")
            if source_id:
                entities.add(("source", str(source_id)))
            organization_id = fields.get("organization_id")
            if organization_id:
                entities.add(("organization", str(organization_id)))
            agent_id = fields.get("agent_id")
            if agent_id:
                entities.add(("agent", str(agent_id)))
            if source_id and agent_id:
                relations.add((str(agent_id), "home_source", str(source_id)))
            if (
                organization_id
                and agent_id
                and fields.get("event_type") == "contract_service_right"
            ):
                relations.add((event_id, "contracts_agent", str(agent_id)))
                relations.add((event_id, "serves_organization", str(organization_id)))
            if fields.get("event_type") == "organization_service_cycle":
                for key, predicate in (
                    ("lead_agent_id", "executes_lead"),
                    ("support_agent_id", "executes_support"),
                ):
                    selected_id = fields.get(key)
                    if selected_id:
                        entities.add(("agent", str(selected_id)))
                        relations.add((event_id, predicate, str(selected_id)))

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


def relationship_ledger(event_ledger: Mapping[str, Any]) -> dict[str, Any]:
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in _events(event_ledger, "R"):
        fields = dict(row["fields"])
        first, second = sorted((str(fields["participant_a"]), str(fields["participant_b"])))
        grouped[(str(row["scope_id"]), first, second)].append(row)

    histories = []
    for (scope_id, first, second), rows in sorted(grouped.items()):
        rows.sort(key=lambda row: (int(row["observed_at"]), str(row["event_id"])))
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
        successes = sum(item["outcome"] == "success" for item in interactions)
        histories.append(
            {
                "scope_id": scope_id,
                "participant_pair": [first, second],
                "interaction_count": len(interactions),
                "success_count": successes,
                "failure_count": len(interactions) - successes,
                "interactions": interactions,
            }
        )
    return {"schema": "o1-relationship-ledger-v0.1", "histories": histories}


def authority_ledger(event_ledger: Mapping[str, Any]) -> dict[str, Any]:
    records = []
    for row in _events(event_ledger, "A"):
        fields = dict(row["fields"])
        record = {
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


def organization_lineage(event_ledger: Mapping[str, Any]) -> dict[str, Any]:
    by_org: dict[str, dict[str, Any]] = {}
    for row in _events(event_ledger, "T"):
        fields = dict(row["fields"])
        org = str(fields["organization_id"])
        target = by_org.setdefault(org, {"generations": [], "memory": [], "decisions": []})
        event_type = str(fields["event_type"])
        if event_type == "organization_generation":
            target["generations"].append(
                {
                    "generation_id": str(fields["generation_id"]),
                    "predecessor_generation_id": str(fields["predecessor_generation_id"]),
                    "member_ids": list(json.loads(fields["member_ids"])),
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
    for org, value in sorted(by_org.items()):
        generations = sorted(value["generations"], key=lambda row: row["generation_id"])
        if len(generations) != 2:
            raise ValueError(f"O1 T requires two generations for {org}")
        old = set(generations[0]["member_ids"])
        new = set(generations[1]["member_ids"])
        denominator = len(old)
        turnover = 0.0 if denominator == 0 else 1.0 - len(old & new) / denominator
        organizations.append(
            {
                "organization_id": org,
                "generations": generations,
                "turnover_fraction": turnover,
                "memory": sorted(value["memory"], key=lambda row: row["arm"]),
                "decisions": sorted(value["decisions"], key=lambda row: row["arm"]),
            }
        )
    return {"schema": "o1-organization-lineage-v0.1", "organizations": organizations}


def capability_evidence(event_ledger: Mapping[str, Any]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    grouped_r: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in _events(event_ledger, "R"):
        fields = dict(row["fields"])
        grouped_r[
            (str(fields["context"]), str(fields["lead_skill"]), str(fields["support_skill"]))
        ].append(row)
    for (context, lead_skill, support_skill), events in sorted(grouped_r.items()):
        attempts = len(events)
        successes = sum(str(row["fields"]["outcome"]) == "success" for row in events)
        rows.append(
            {
                "family": "R",
                "context": context,
                "lead_skill": lead_skill,
                "support_skill": support_skill,
                "attempt_count": attempts,
                "success_count": successes,
                "failure_count": attempts - successes,
                "success_fraction": f"{successes}/{attempts}",
            }
        )

    for row in _events(event_ledger, "T"):
        fields = dict(row["fields"])
        if fields.get("event_type") != "post_turnover_decision":
            continue
        attempts = int(fields["evaluation_trials"])
        successes = int(fields["success_count"])
        rows.append(
            {
                "family": "T",
                "context": str(fields["context"]),
                "lead_skill": str(fields["lead_skill"]),
                "support_skill": str(fields["support_skill"]),
                "arm": str(fields["arm"]),
                "organization_id": str(fields["organization_id"]),
                "selected_participants": [
                    str(fields["lead_member_id"]),
                    str(fields["support_member_id"]),
                ],
                "attempt_count": attempts,
                "success_count": successes,
                "failure_count": attempts - successes,
                "success_fraction": f"{successes}/{attempts}",
            }
        )
    rows.sort(
        key=lambda row: (
            str(row["family"]),
            str(row.get("organization_id", "")),
            str(row.get("arm", "")),
            str(row["context"]),
        )
    )
    return {"schema": "o1-capability-evidence-v0.1", "summaries": rows}


def source_sustainability_evidence(event_ledger: Mapping[str, Any]) -> dict[str, Any]:
    source_records = []
    contracts = []
    service_cycles = []
    services = []
    accounting: dict[str, Any] | None = None
    for row in _events(event_ledger, "S"):
        fields = dict(row["fields"])
        event_type = str(fields["event_type"])
        if event_type == "source_agent_public_record":
            source_records.append(
                {
                    "source_id": str(fields["source_id"]),
                    "agent_id": str(fields["agent_id"]),
                    "source_evidence_sha256": str(fields["source_evidence_sha256"]),
                    "dominant_success_skill": str(fields["dominant_success_skill"]),
                    "secondary_success_skill": str(fields["secondary_success_skill"]),
                }
            )
        elif event_type == "contract_service_right":
            contracts.append(
                {
                    "cycle": int(fields["cycle"]),
                    "organization_id": str(fields["organization_id"]),
                    "agent_id": str(fields["agent_id"]),
                    "source_id": str(fields["source_id"]),
                    "price": int(fields["price"]),
                    "lead_skill": str(fields["lead_skill"]),
                    "support_skill": str(fields["support_skill"]),
                }
            )
        elif event_type == "organization_service_cycle":
            attempts = int(fields["attempt_count"])
            successes = int(fields["success_count"])
            service_cycles.append(
                {
                    "cycle": int(fields["cycle"]),
                    "organization_id": str(fields["organization_id"]),
                    "lead_skill": str(fields["lead_skill"]),
                    "support_skill": str(fields["support_skill"]),
                    "lead_agent_id": str(fields["lead_agent_id"]),
                    "support_agent_id": str(fields["support_agent_id"]),
                    "attempt_count": attempts,
                    "success_count": successes,
                    "failure_count": int(fields["failure_count"]),
                    "success_fraction": f"{successes}/{attempts}",
                }
            )
        elif event_type == "organization_service_summary":
            attempts = int(fields["attempt_count"])
            successes = int(fields["success_count"])
            services.append(
                {
                    "organization_id": str(fields["organization_id"]),
                    "attempt_count": attempts,
                    "success_count": successes,
                    "failure_count": int(fields["failure_count"]),
                    "success_fraction": f"{successes}/{attempts}",
                }
            )
        elif event_type == "observable_accounting_summary":
            accounting = {
                "external_agent_cycle_exposures": int(fields["external_agent_cycle_exposures"]),
                "incremental_source_development_compute": str(
                    fields["incremental_source_development_compute"]
                ),
                "mission_execution_compute": str(fields["mission_execution_compute"]),
                "organization_coordination_compute": str(
                    fields["organization_coordination_compute"]
                ),
                "world_regulatory_estimation_compute": str(
                    fields["world_regulatory_estimation_compute"]
                ),
            }
    if accounting is None:
        raise ValueError("O1 S missing observable accounting summary")
    by_cycle: dict[int, int] = defaultdict(int)
    by_source: dict[str, int] = defaultdict(int)
    for contract in contracts:
        by_cycle[int(contract["cycle"])] += 1
        by_source[str(contract["source_id"])] += 1

    service_totals: dict[str, tuple[int, int]] = {}
    for organization_id in sorted({str(row["organization_id"]) for row in service_cycles}):
        rows = [row for row in service_cycles if row["organization_id"] == organization_id]
        service_totals[organization_id] = (
            sum(int(row["success_count"]) for row in rows),
            sum(int(row["attempt_count"]) for row in rows),
        )
    summary_totals = {
        str(row["organization_id"]): (int(row["success_count"]), int(row["attempt_count"]))
        for row in services
    }
    if service_totals != summary_totals:
        raise ValueError("O1 S cycle-level service evidence disagrees with frozen summary")
    return {
        "schema": "o1-source-sustainability-evidence-v0.1",
        "source_records": sorted(
            source_records, key=lambda row: (row["source_id"], row["agent_id"])
        ),
        "contracts": sorted(
            contracts, key=lambda row: (row["cycle"], row["organization_id"], row["agent_id"])
        ),
        "service_cycles": sorted(
            service_cycles, key=lambda row: (row["cycle"], row["organization_id"])
        ),
        "service_summaries": sorted(services, key=lambda row: row["organization_id"]),
        "derived": {
            "contract_count": len(contracts),
            "contracts_per_cycle": [
                {"cycle": cycle, "contract_count": count}
                for cycle, count in sorted(by_cycle.items())
            ],
            "contracts_per_source": [
                {"source_id": source_id, "contract_count": count}
                for source_id, count in sorted(by_source.items())
            ],
            "observable_accounting": accounting,
            "not_observationally_identifiable_metrics": [
                "compute_normalized_world_stock_growth",
                "developmental_efficiency",
                "mean_source_loss_pp",
                "service_efficiency",
                "source_accessible_capability_growth",
            ],
        },
    }


def reconstruct_products(claims: Iterable[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    event = claims_to_event_ledger(claims)
    return {
        "event-ledger.json": event,
        "entity-ledger.json": entity_ledger(event),
        "relationship-ledger.json": relationship_ledger(event),
        "authority-ledger.json": authority_ledger(event),
        "organization-lineage.json": organization_lineage(event),
        "capability-evidence.json": capability_evidence(event),
        "source-sustainability-evidence.json": source_sustainability_evidence(event),
    }
