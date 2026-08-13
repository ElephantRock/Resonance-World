"""Independent evaluator-side provenance rules for the frozen O2 query contract."""

from __future__ import annotations

from collections import defaultdict
from typing import Any


def event_support(
    template: str,
    query_id: str,
    events: list[dict[str, Any]],
    value: Any,
) -> list[str]:
    by_kind: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in events:
        by_kind[str(row["kind"])].append(row)
    for rows in by_kind.values():
        rows.sort(key=lambda row: (int(row["interval"]), int(row["ordinal"])))

    performance = by_kind.get("performance", [])
    turnover = by_kind.get("turnover", [])
    generation = by_kind.get("generation_transition", [])
    interaction = by_kind.get("interaction", [])
    relation_state = by_kind.get("relation_state", [])
    source_state = by_kind.get("source_public_state", [])
    service = by_kind.get("service", [])

    if query_id == "first_success_interval":
        return sorted(
            str(row["event_id"])
            for row in performance
            if value is None or int(row["interval"]) <= int(value)
        )
    if query_id in {
        "success_count_trajectory",
        "per_member_success_trajectory",
        "carrier_set_by_interval",
        "contribution_vector",
        "maximum_contributing_members",
        "maximum_contribution_share",
    }:
        return sorted(str(row["event_id"]) for row in performance)
    if query_id == "first_multi_carrier_interval":
        return sorted(
            str(row["event_id"])
            for row in performance
            if value is None or int(row["interval"]) <= int(value)
        )
    if query_id == "departing_carrier_id":
        return sorted(str(row["event_id"]) for row in turnover)
    if query_id == "pre_departure_success_counts":
        boundary = int(turnover[0]["interval"])
        selected = [row for row in performance if int(row["interval"]) < boundary]
        return sorted(
            [str(turnover[0]["event_id"]), *[str(row["event_id"]) for row in selected]]
        )
    if query_id == "post_departure_success_counts":
        boundary = int(turnover[0]["interval"])
        selected = [row for row in performance if int(row["interval"]) >= boundary]
        return sorted(
            [str(turnover[0]["event_id"]), *[str(row["event_id"]) for row in selected]]
        )
    if query_id == "recovery_interval" and template == "D1":
        boundary = int(turnover[0]["interval"])
        selected = [
            row
            for row in performance
            if int(row["interval"]) >= boundary
            and (value is None or int(row["interval"]) <= int(value))
        ]
        return sorted(
            [str(turnover[0]["event_id"]), *[str(row["event_id"]) for row in selected]]
        )
    if query_id == "generation_transition_interval":
        return sorted(str(row["event_id"]) for row in generation)
    if query_id == "post_turnover_success_trajectory":
        boundary = int(generation[0]["interval"])
        selected = [row for row in performance if int(row["interval"]) >= boundary]
        return sorted(
            [str(generation[0]["event_id"]), *[str(row["event_id"]) for row in selected]]
        )
    if query_id == "first_recovered_interval":
        boundary = int(generation[0]["interval"])
        selected = [
            row
            for row in performance
            if int(row["interval"]) >= boundary
            and (value is None or int(row["interval"]) <= int(value))
        ]
        return sorted(
            [str(generation[0]["event_id"]), *[str(row["event_id"]) for row in selected]]
        )
    if query_id in {"decision_provenance_chain", "provenance_crosses_generation_boundary"}:
        decision = by_kind["decision"][-1]
        chain = [str(item) for item in decision.get("provenance_event_ids", [])]
        return sorted(
            [str(generation[0]["event_id"]), str(decision["event_id"]), *chain]
        )
    if query_id in {"pair_interaction_intervals", "pair_ids"}:
        return sorted(str(row["event_id"]) for row in interaction)
    if query_id in {"relation_active_intervals", "rupture_event_id", "reformation_event_id"}:
        return sorted(str(row["event_id"]) for row in relation_state)
    if query_id == "first_negative_public_trajectory_interval":
        return sorted(
            str(row["event_id"])
            for row in source_state
            if value is None or int(row["interval"]) <= int(value)
        )
    if query_id == "recovery_interval" and template == "S1":
        return sorted(
            str(row["event_id"])
            for row in source_state
            if value is None or int(row["interval"]) <= int(value)
        )
    if query_id in {
        "service_success_trajectory",
        "failure_intervals",
        "prefix_cumulative_failures",
    }:
        return sorted(str(row["event_id"]) for row in service)
    raise ValueError(f"no registered support rule for {template}/{query_id}")


def structural_plane_k_exclusion(value: Any) -> bool:
    forbidden_keys = {"template", "variant", "distinguishing_answers"}
    if isinstance(value, dict):
        if forbidden_keys.intersection(value):
            return False
        return all(structural_plane_k_exclusion(item) for item in value.values())
    if isinstance(value, list):
        return all(structural_plane_k_exclusion(item) for item in value)
    return True
