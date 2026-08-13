#!/usr/bin/env python3
"""Materialize the frozen O1 two-plane benchmark from accepted historical artifacts.

This script performs no model calls. Plane E contains only registered observable/runtime
projections. Plane K contains evaluator-only answer keys and hidden historical diagnostics.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import zipfile
from collections import defaultdict
from pathlib import Path
from typing import Any

PHASE4C_ARTIFACT_SHA256 = "465c5d07c7e98a33dccedf24c0fb504a82ad54632590ec1fce8eddd1cf57279e"
PHASE5C_ARTIFACT_SHA256 = "e44cc271d688ada78c59a55410f028147c01e6e2954c923d2c42b56419943d4f"
PHASE5C_SOURCE_SHA256 = "2caf65e6f2839f243ad0c6e59f7d12ad196f48ddf79aab7c3cca42b0904f22f6"
W9_ARTIFACT_SHA256 = "550da9bfb7ad64dfde8f2c8c48e4ba75de28fb25097152455d0cd3abd6c0487a"
W9_06_SHA256 = "9e37f426c15fd0dc049fc9da07d25f48dcc6092c1967714b9e90c6274c42f562"

SKILL_ALIAS = {
    "energy_storage": "skill-c",
    "mobility": "skill-f",
    "public_health": "skill-e",
    "supply_networks": "skill-d",
    "urban_heat": "skill-a",
    "water_systems": "skill-b",
}
ALIAS_SKILL = {value: key for key, value in SKILL_ALIAS.items()}
W9_SKILLS = (
    "urban_heat",
    "water_systems",
    "energy_storage",
    "supply_networks",
    "public_health",
    "mobility",
)
W9_ORGANIZATIONS = (
    ("org-alpha", "energy_storage", "mobility"),
    ("org-beta", "water_systems", "public_health"),
    ("org-gamma", "supply_networks", "urban_heat"),
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _zip_text(path: Path, member: str) -> str:
    with zipfile.ZipFile(path) as archive:
        return archive.read(member).decode("utf-8")


def _zip_json(path: Path, member: str) -> dict[str, Any]:
    value = json.loads(_zip_text(path, member))
    if not isinstance(value, dict):
        raise ValueError(f"{member} must contain a JSON object")
    return value


def _zip_jsonl(path: Path, member: str) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in _zip_text(path, member).splitlines()
        if line.strip()
    ]


def _member_alias(field_id: str, agent_id: str) -> str:
    value = hashlib.sha256(f"o1-member|{field_id}|{agent_id}".encode()).hexdigest()[:20]
    return f"member-{value}"


def _w9_alias(agent_id: str) -> str:
    value = hashlib.sha256(f"o1-w9-agent|{agent_id}".encode()).hexdigest()[:20]
    return f"w9-agent-{value}"


def _stable_roster_key(field_id: str, agent_id: str) -> bytes:
    return hashlib.sha256(f"w5-roster|{field_id}|{agent_id}".encode()).digest()


def _authority_planes(artifact: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    payloads = {
        arm: _zip_json(artifact, f"{arm}.json") for arm in ("unsigned", "attested")
    }
    result = _zip_json(artifact, "result.json")
    source = {
        "artifact_id": 9158432521,
        "artifact_sha256": PHASE4C_ARTIFACT_SHA256,
        "workflow_run": 31638087507,
        "world_revision": "b2da04a1cd3ab5fb07dc781cd8b7bb93fab4b0d1",
    }
    events: list[dict[str, Any]] = []
    keys: list[dict[str, str]] = []
    for arm in ("unsigned", "attested"):
        records = payloads[arm]["records"]
        if len(records) != 60:
            raise ValueError("Phase 4C requires 60 records per arm")
        for record in records:
            scenario_id = str(record["scenario_id"])
            case_id = scenario_id.split("::", 1)[0]
            agent_index = int(record["agent_index"])
            case_seed = int(record["trial_seed"]) // 100
            legitimate_first = (case_seed + agent_index) % 2 == 0
            legitimate_id = str(record["legitimate_notice_id"])
            spoof_id = str(record["spoof_notice_id"])
            legitimate_action = str(record["expected_action"])
            spoof_action = str(record["spoof_action"])
            if legitimate_first:
                first_id, first_action = legitimate_id, legitimate_action
                second_id, second_action = spoof_id, spoof_action
            else:
                first_id, first_action = spoof_id, spoof_action
                second_id, second_action = legitimate_id, legitimate_action
            step = record["piano_step"]
            acknowledgement = step["acknowledgement"]
            fields = {
                "event_type": "authority_resolution",
                "organization_id": "resonance-world-atlas",
                "arm": arm,
                "scenario_id": scenario_id,
                "agent_id": f"authority-agent-{agent_index}",
                "role_id": scenario_id,
                "notice_1_id": first_id,
                "notice_1_action": first_action,
                "notice_2_id": second_id,
                "notice_2_action": second_action,
                "controller_action": str(step["action"]),
                "intended_action": str(step["intended_action"]),
                "speech_action": str(step["speech_action"]),
                "policy_result": str(acknowledgement["policy_result"]),
                "outcome_status": str(acknowledgement["outcome_status"]),
                "grounded_success": str(bool(acknowledgement["grounded_success"])).lower(),
                "action_request_id": str(acknowledgement["action_request_id"]),
                "correlation_id": str(acknowledgement["correlation_id"]),
            }
            if arm == "attested":
                fields["verified_notice_id"] = legitimate_id
                fields["rejected_notice_id"] = spoof_id
            events.append(
                {
                    "event_id": f"{arm}:{scenario_id}",
                    "scope_id": f"o1:A:{arm}:{case_id}",
                    "observed_at": agent_index + 1,
                    "source_class": "world_authority_observation",
                    "fields": fields,
                }
            )
            keys.append(
                {
                    "arm": arm,
                    "scenario_id": scenario_id,
                    "expected_action": legitimate_action,
                    "spoof_action": spoof_action,
                    "legitimate_notice_id": legitimate_id,
                    "spoof_notice_id": spoof_id,
                }
            )
    expected = {
        "unsigned_role_failures": round(
            float(result["unsigned"]["agent_role_failure_rate"]) * 60
        ),
        "unsigned_spoof_captures": round(
            float(result["unsigned"]["spoof_capture_rate"]) * 60
        ),
        "attested_role_failures": round(
            float(result["attested"]["agent_role_failure_rate"]) * 60
        ),
        "attested_spoof_captures": round(
            float(result["attested"]["spoof_capture_rate"]) * 60
        ),
        "observations_per_arm": 60,
    }
    return (
        {
            "schema": "o1-plane-e-v0.1",
            "family": "A",
            "source": source,
            "events": events,
        },
        {
            "schema": "o1-plane-k-v0.1",
            "family": "A",
            "source": source,
            "answer_keys": keys,
            "expected_primary": expected,
        },
    )


def _group_capsules(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row["field_id"])].append(row)
    return grouped


def _specialist_pair(
    roster: list[dict[str, Any]], lead_skill: str, support_skill: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    lead = max(
        roster,
        key=lambda row: (int(row["practice_by_skill"].get(lead_skill, 0)), str(row["agent_id"])),
    )
    support = max(
        (row for row in roster if row["agent_id"] != lead["agent_id"]),
        key=lambda row: (
            int(row["practice_by_skill"].get(support_skill, 0)),
            str(row["agent_id"]),
        ),
    )
    return lead, support


def _balanced_pair(
    roster: list[dict[str, Any]], lead_skill: str, support_skill: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    ranked = sorted(
        roster,
        key=lambda row: (
            min(
                int(row["practice_by_skill"].get(lead_skill, 0)),
                int(row["practice_by_skill"].get(support_skill, 0)),
            ),
            str(row["agent_id"]),
        ),
        reverse=True,
    )
    first, second = ranked[:2]
    if int(first["practice_by_skill"].get(lead_skill, 0)) >= int(
        second["practice_by_skill"].get(lead_skill, 0)
    ):
        return first, second
    return second, first


def _turnover_planes(
    live_artifact: Path, source_artifact: Path
) -> tuple[dict[str, Any], dict[str, Any]]:
    arms = {
        arm: _zip_json(live_artifact, f"{arm}.json")
        for arm in ("model_reset", "model_retained")
    }
    result = _zip_json(live_artifact, "result.json")
    capsules = _zip_jsonl(source_artifact, "capsules.private.jsonl")
    grouped = _group_capsules(capsules)
    source = {
        "artifact_id": 9163662793,
        "artifact_sha256": PHASE5C_ARTIFACT_SHA256,
        "source_artifact_id": 9163101495,
        "source_artifact_sha256": PHASE5C_SOURCE_SHA256,
        "workflow_run": 31653879702,
        "world_revision": "da24461e9244dbeb50d85e9fd1c35339726a49a9",
    }
    records = {
        arm: {str(row["unit_id"]): row for row in payload["records"]}
        for arm, payload in arms.items()
    }
    unit_order = [str(row["unit_id"]) for row in arms["model_reset"]["records"]]
    if set(unit_order) != set(records["model_retained"]):
        raise ValueError("Phase 5C arms have different unit identities")

    events: list[dict[str, Any]] = []
    answer_keys: list[dict[str, str]] = []
    for unit_id in unit_order:
        reset = records["model_reset"][unit_id]
        retained = records["model_retained"][unit_id]
        field_id = str(reset["field_id"])
        if field_id != str(retained["field_id"]):
            raise ValueError("Phase 5C paired field mismatch")
        rows = sorted(
            grouped[field_id],
            key=lambda row: _stable_roster_key(field_id, str(row["agent_id"])),
        )
        if len(rows) != 12:
            raise ValueError("Phase 5C source field must contain 12 agents")
        initial = rows[:4]
        replacement = rows[4:8]
        initial_aliases = [_member_alias(field_id, str(row["agent_id"])) for row in initial]
        replacement_aliases = [
            _member_alias(field_id, str(row["agent_id"])) for row in replacement
        ]
        organization_id = f"org-{unit_id}"
        scope_id = f"o1:T:{unit_id}"
        events.extend(
            [
                {
                    "event_id": f"{organization_id}:generation-0",
                    "scope_id": scope_id,
                    "observed_at": 1,
                    "source_class": "world_organization_observation",
                    "fields": {
                        "event_type": "organization_generation",
                        "organization_id": organization_id,
                        "generation_id": "generation-0",
                        "predecessor_generation_id": "",
                        "member_ids": _canonical(initial_aliases),
                        "source_field_id": field_id,
                    },
                },
                {
                    "event_id": f"{organization_id}:generation-1",
                    "scope_id": scope_id,
                    "observed_at": 2,
                    "source_class": "world_organization_observation",
                    "fields": {
                        "event_type": "organization_generation",
                        "organization_id": organization_id,
                        "generation_id": "generation-1",
                        "predecessor_generation_id": "generation-0",
                        "member_ids": _canonical(replacement_aliases),
                        "source_field_id": field_id,
                    },
                },
            ]
        )
        for offset, arm in ((3, "model_reset"), (5, "model_retained")):
            record = records[arm][unit_id]
            visible = record["model_visible"]
            memory = visible["institutional_model_memory"]
            posterior = memory["structural_posterior"]
            forecasts = memory["current_roster_strategy_forecast"]
            preferred = str(record["audit"]["forecast_preferred_strategy"])
            public_mission = str(visible["mission_text"])
            parts = dict(
                item.split("=", 1) for item in public_mission.split("; ")
            )
            lead_alias = str(parts["lead_skill"])
            support_alias = str(parts["support_skill"])
            lead_skill = ALIAS_SKILL[lead_alias]
            support_skill = ALIAS_SKILL[support_alias]
            strategy = str(record["audit"]["chosen_strategy"])
            if strategy == "specialist":
                lead, support = _specialist_pair(replacement, lead_skill, support_skill)
            elif strategy == "balanced":
                lead, support = _balanced_pair(replacement, lead_skill, support_skill)
            else:
                raise ValueError(f"unsupported Phase 5C strategy {strategy}")
            success_count = int(record["audit"]["success_count"])
            trials = int(record["audit"]["evaluation_trials"])
            success_rate = float(record["audit"]["mission_success_rate"])
            grounded = bool(record["audit"]["grounded_success"])
            memory_id = f"{organization_id}:{arm}:memory-summary"
            events.append(
                {
                    "event_id": memory_id,
                    "scope_id": scope_id,
                    "observed_at": offset,
                    "source_class": "world_institutional_state_observation",
                    "fields": {
                        "event_type": "institutional_memory_summary",
                        "organization_id": organization_id,
                        "generation_id": "generation-1",
                        "arm": arm,
                        "evidence_episodes": str(int(posterior["evidence_episodes"])),
                        "role_specific_posterior": str(float(posterior["role_specific"])),
                        "cross_coverage_posterior": str(float(posterior["cross_coverage"])),
                        "forecast_specialist": str(float(forecasts["specialist"])),
                        "forecast_balanced": str(float(forecasts["balanced"])),
                        "forecast_preferred_strategy": preferred,
                    },
                }
            )
            events.append(
                {
                    "event_id": f"{organization_id}:{arm}:decision",
                    "scope_id": scope_id,
                    "observed_at": offset + 1,
                    "source_class": "world_execution_observation",
                    "fields": {
                        "event_type": "post_turnover_decision",
                        "organization_id": organization_id,
                        "generation_id": "generation-1",
                        "unit_id": unit_id,
                        "arm": arm,
                        "context": str(parts["context"]),
                        "lead_skill": lead_alias,
                        "support_skill": support_alias,
                        "member_ids": _canonical(replacement_aliases),
                        "memory_source_ref": memory_id,
                        "forecast_preferred_strategy": preferred,
                        "chosen_strategy": strategy,
                        "intended_strategy": str(record["audit"]["intended_strategy"]),
                        "speech_strategy": str(record["audit"]["speech_strategy"]),
                        "lead_member_id": _member_alias(field_id, str(lead["agent_id"])),
                        "support_member_id": _member_alias(field_id, str(support["agent_id"])),
                        "evaluation_trials": str(trials),
                        "success_count": str(success_count),
                        "mission_success_rate": str(success_rate),
                        "grounded_success": str(grounded).lower(),
                        "acknowledgement": (
                            f"trials={trials}; successes={success_count}; "
                            f"success_rate={success_rate:.8f}; "
                            f"grounded_success={str(grounded).lower()}"
                        ),
                    },
                }
            )
        audit = retained["audit"]
        answer_keys.append(
            {
                "unit_id": unit_id,
                "organization_id": organization_id,
                "hidden_regime": str(audit["hidden_regime"]),
                "target_hypothesis": str(audit["target_hypothesis"]),
                "target_policy": str(audit["target_policy"]),
                "neutral_preferred_policy": str(audit["neutral_preferred_policy"]),
            }
        )
    expected = {
        "dataset_digest": str(result["dataset_digest"]),
        "reset_success_rate": float(result["metrics"]["model_reset"]["mission_success_rate"]),
        "retained_success_rate": float(
            result["metrics"]["model_retained"]["mission_success_rate"]
        ),
        "mean_retained_minus_reset_success_rate": float(
            result["primary"]["mean_retained_minus_reset_success_rate"]
        ),
        "paired_better": int(result["primary"]["paired_better"]),
        "paired_worse": int(result["primary"]["paired_worse"]),
        "paired_ties": int(result["primary"]["paired_ties"]),
        "nonnegative_unit_effects": int(result["primary"]["nonnegative_unit_effects"]),
        "forecast_preference_change_units": int(
            result["mechanism"]["forecast_preference_change_units"]
        ),
        "reset_neutral_forecast_match_units": int(
            result["mechanism"]["reset_neutral_forecast_match_units"]
        ),
        "retained_target_forecast_match_units": int(
            result["mechanism"]["retained_target_forecast_match_units"]
        ),
        "retained_target_posterior_match_units": int(
            result["mechanism"]["retained_target_posterior_match_units"]
        ),
    }
    return (
        {"schema": "o1-plane-e-v0.1", "family": "T", "source": source, "events": events},
        {
            "schema": "o1-plane-k-v0.1",
            "family": "T",
            "source": source,
            "answer_keys": answer_keys,
            "expected_primary": expected,
        },
    )


__all__ = [
    "argparse", "hashlib", "json", "math", "defaultdict", "Path", "Any",
    "PHASE4C_ARTIFACT_SHA256", "PHASE5C_ARTIFACT_SHA256",
    "PHASE5C_SOURCE_SHA256", "W9_ARTIFACT_SHA256", "W9_06_SHA256",
    "SKILL_ALIAS", "ALIAS_SKILL", "W9_SKILLS", "W9_ORGANIZATIONS",
    "_sha256", "_canonical", "_write", "_zip_text", "_zip_json",
    "_zip_jsonl", "_member_alias", "_w9_alias", "_stable_roster_key",
    "_authority_planes", "_group_capsules", "_specialist_pair",
    "_balanced_pair", "_turnover_planes",
]
