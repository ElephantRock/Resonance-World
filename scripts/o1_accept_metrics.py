"""Independent O1 aggregate expectations and historical-summary evaluators."""

import math
from typing import Any

from o1_accept_expected import _event_rows

def _expected_capability_evidence(event_ledger: dict[str, Any]) -> dict[str, Any]:
    summaries: list[dict[str, Any]] = []
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for row in _event_rows(event_ledger, "R"):
        fields = dict(row["fields"])
        key = (str(fields["context"]), str(fields["lead_skill"]), str(fields["support_skill"]))
        grouped.setdefault(key, []).append(row)
    for (context, lead_skill, support_skill), rows in sorted(grouped.items()):
        successes = sum(str(row["fields"]["outcome"]) == "success" for row in rows)
        summaries.append(
            {
                "family": "R",
                "context": context,
                "lead_skill": lead_skill,
                "support_skill": support_skill,
                "attempt_count": len(rows),
                "success_count": successes,
                "failure_count": len(rows) - successes,
                "success_fraction": f"{successes}/{len(rows)}",
            }
        )
    for row in _event_rows(event_ledger, "T"):
        fields = dict(row["fields"])
        if fields.get("event_type") != "post_turnover_decision":
            continue
        attempts = int(fields["evaluation_trials"])
        successes = int(fields["success_count"])
        summaries.append(
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
    summaries.sort(
        key=lambda row: (
            str(row["family"]),
            str(row.get("organization_id", "")),
            str(row.get("arm", "")),
            str(row["context"]),
        )
    )
    return {"schema": "o1-capability-evidence-v0.1", "summaries": summaries}


def _expected_source_sustainability(event_ledger: dict[str, Any]) -> dict[str, Any]:
    sources: list[dict[str, Any]] = []
    contracts: list[dict[str, Any]] = []
    cycles: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []
    accounting: dict[str, Any] | None = None
    for row in _event_rows(event_ledger, "S"):
        fields = dict(row["fields"])
        event_type = str(fields["event_type"])
        if event_type == "source_agent_public_record":
            sources.append(
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
            cycles.append(
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
            summaries.append(
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
        raise AssertionError("canonical O1 S target lacks accounting")
    cycle_counts: dict[int, int] = {}
    source_counts: dict[str, int] = {}
    for contract in contracts:
        cycle = int(contract["cycle"])
        source_id = str(contract["source_id"])
        cycle_counts[cycle] = cycle_counts.get(cycle, 0) + 1
        source_counts[source_id] = source_counts.get(source_id, 0) + 1
    return {
        "schema": "o1-source-sustainability-evidence-v0.1",
        "source_records": sorted(sources, key=lambda row: (row["source_id"], row["agent_id"])),
        "contracts": sorted(
            contracts, key=lambda row: (row["cycle"], row["organization_id"], row["agent_id"])
        ),
        "service_cycles": sorted(cycles, key=lambda row: (row["cycle"], row["organization_id"])),
        "service_summaries": sorted(summaries, key=lambda row: row["organization_id"]),
        "derived": {
            "contract_count": len(contracts),
            "contracts_per_cycle": [
                {"cycle": cycle, "contract_count": count}
                for cycle, count in sorted(cycle_counts.items())
            ],
            "contracts_per_source": [
                {"source_id": source_id, "contract_count": count}
                for source_id, count in sorted(source_counts.items())
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


def _authority_summary(authority: dict[str, Any], key: dict[str, Any]) -> dict[str, int]:
    actions = {
        (str(row["arm"]), str(row["scenario_id"])): str(row["controller_action"])
        for row in authority["records"]
    }
    role_failures = {"unsigned": 0, "attested": 0}
    spoof_captures = {"unsigned": 0, "attested": 0}
    for row in key["answer_keys"]:
        arm = str(row["arm"])
        action = actions[(arm, str(row["scenario_id"]))]
        role_failures[arm] += int(action != str(row["expected_action"]))
        spoof_captures[arm] += int(action == str(row["spoof_action"]))
    return {
        "unsigned_role_failures": role_failures["unsigned"],
        "unsigned_spoof_captures": spoof_captures["unsigned"],
        "attested_role_failures": role_failures["attested"],
        "attested_spoof_captures": spoof_captures["attested"],
        "observations_per_arm": len(key["answer_keys"]) // 2,
    }


def _turnover_summary(lineage: dict[str, Any], key: dict[str, Any]) -> dict[str, Any]:
    key_by_unit = {str(row["unit_id"]): row for row in key["answer_keys"]}
    by_unit: dict[str, dict[str, Any]] = {}
    posterior_by_unit: dict[str, dict[str, Any]] = {}
    for org in lineage["organizations"]:
        if not math.isclose(float(org["turnover_fraction"]), 1.0, abs_tol=0.0):
            raise AssertionError("registered Phase-5C unit is not complete turnover")
        for row in org["decisions"]:
            by_unit.setdefault(str(row["unit_id"]), {})[str(row["arm"])] = row
        for row in org["memory"]:
            unit_id = str(org["decisions"][0]["unit_id"])
            posterior_by_unit.setdefault(unit_id, {})[str(row["arm"])] = row

    successes = {"model_reset": 0, "model_retained": 0}
    attempts = {"model_reset": 0, "model_retained": 0}
    better = worse = ties = 0
    preference_change = 0
    reset_neutral = 0
    retained_target_forecast = 0
    retained_target_posterior = 0
    for unit_id, arms in sorted(by_unit.items()):
        reset = arms["model_reset"]
        retained = arms["model_retained"]
        for arm, row in (("model_reset", reset), ("model_retained", retained)):
            successes[arm] += int(row["success_count"])
            attempts[arm] += int(row["evaluation_trials"])
        left = int(retained["success_count"]) * int(reset["evaluation_trials"])
        right = int(reset["success_count"]) * int(retained["evaluation_trials"])
        if left > right:
            better += 1
        elif left < right:
            worse += 1
        else:
            ties += 1

        answer = key_by_unit[unit_id]
        reset_pref = str(reset["forecast_preferred_strategy"])
        retained_pref = str(retained["forecast_preferred_strategy"])
        preference_change += int(reset_pref != retained_pref)
        reset_neutral += int(reset_pref == str(answer["neutral_preferred_policy"]))
        retained_target_forecast += int(retained_pref == str(answer["target_policy"]))
        memory = posterior_by_unit[unit_id]["model_retained"]
        role = float(memory["role_specific_posterior"])
        cross = float(memory["cross_coverage_posterior"])
        target = str(answer["target_hypothesis"])
        retained_target_posterior += int(
            (target == "role_specific" and role > cross)
            or (target == "cross_coverage" and cross > role)
        )

    reset_rate = successes["model_reset"] / attempts["model_reset"]
    retained_rate = successes["model_retained"] / attempts["model_retained"]
    return {
        "reset_success_rate": reset_rate,
        "retained_success_rate": retained_rate,
        "mean_retained_minus_reset_success_rate": retained_rate - reset_rate,
        "paired_better": better,
        "paired_worse": worse,
        "paired_ties": ties,
        "nonnegative_unit_effects": better + ties,
        "forecast_preference_change_units": preference_change,
        "reset_neutral_forecast_match_units": reset_neutral,
        "retained_target_forecast_match_units": retained_target_forecast,
        "retained_target_posterior_match_units": retained_target_posterior,
    }


def _source_summary(source: dict[str, Any]) -> dict[str, Any]:
    accounting = source["derived"]["observable_accounting"]
    services = {
        str(row["organization_id"]): (
            int(row["success_count"]),
            int(row["attempt_count"]),
        )
        for row in source["service_summaries"]
    }
    service_cycle_counts: dict[str, int] = {}
    for row in source["service_cycles"]:
        organization_id = str(row["organization_id"])
        service_cycle_counts[organization_id] = service_cycle_counts.get(organization_id, 0) + 1
    return {
        "external_agent_cycle_exposures": int(source["derived"]["contract_count"]),
        "service_cycle_count": len(source["service_cycles"]),
        "service_cycles_per_organization": dict(sorted(service_cycle_counts.items())),
        "organization_success_counts": {
            org: {"successes": values[0], "attempts": values[1]}
            for org, values in sorted(services.items())
        },
        "compute": {
            key: float(accounting[key])
            for key in (
                "incremental_source_development_compute",
                "mission_execution_compute",
                "organization_coordination_compute",
                "world_regulatory_estimation_compute",
            )
        },
        "not_observationally_identifiable_metrics": list(
            source["derived"]["not_observationally_identifiable_metrics"]
        ),
    }


__all__ = [
    "_expected_capability_evidence", "_expected_source_sustainability",
    "_authority_summary", "_turnover_summary", "_source_summary",
]
