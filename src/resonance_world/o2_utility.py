"""Deterministic observer-side analysis for the preregistered O2 corpus.

The module consumes admissible event history only. It never accepts evaluator Plane K,
final result labels, template identities, or hidden scientific state.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from typing import Any

from resonance_contextgraph import EvidenceStore

from .context_graph_adapter import to_evidence_claim

NOT_IDENTIFIABLE = "not_observationally_identifiable"
NEGATIVE_CONTROLS = (
    "latent_private_field_capability",
    "counterfactual_member_necessity",
    "hidden_constructor_template_regime",
    "evaluator_variant_identity",
    "private_relationship_store_state",
    "hidden_w9_source_frontier_state",
    "future_unobserved_outcome",
    "provenance_implies_causal_benefit",
)
ALL_LONGITUDINAL_QUERY_IDS = (
    "first_success_interval",
    "success_count_trajectory",
    "per_member_success_trajectory",
    "first_multi_carrier_interval",
    "carrier_set_by_interval",
    "departing_carrier_id",
    "pre_departure_success_counts",
    "post_departure_success_counts",
    "recovery_interval",
    "contribution_vector",
    "maximum_contributing_members",
    "maximum_contribution_share",
    "generation_transition_interval",
    "post_turnover_success_trajectory",
    "first_recovered_interval",
    "decision_provenance_chain",
    "provenance_crosses_generation_boundary",
    "pair_interaction_intervals",
    "pair_ids",
    "relation_active_intervals",
    "rupture_event_id",
    "reformation_event_id",
    "first_negative_public_trajectory_interval",
    "service_success_trajectory",
    "failure_intervals",
    "prefix_cumulative_failures",
)


def canonical_bytes(value: Any) -> bytes:
    """Serialize one authoritative O2 product deterministically."""
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
    ).encode()


@dataclass(frozen=True, slots=True)
class _ObservedClaim:
    field_id: str
    subject: str
    predicate: str
    object: str
    observed_by: str
    source_id: str
    source_class: str
    observed_at: int
    confidence: float
    direct: bool


def _encoded(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _decoded(value: str) -> Any:
    return json.loads(value)


def ingest_history(history: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Round-trip one Plane-E history through the accepted ContextGraph evidence store."""
    if history.get("schema") != "o2-plane-e-history-v0.1":
        raise ValueError("unsupported O2 Plane-E history schema")
    history_id = str(history["history_id"])
    events = history.get("events")
    if not isinstance(events, list) or not events:
        raise ValueError("O2 Plane-E history requires events")

    store = EvidenceStore()
    for event in events:
        if not isinstance(event, dict):
            raise ValueError("O2 event must be an object")
        event_id = str(event["event_id"])
        ordinal = int(event["ordinal"])
        for field, value in sorted(event.items()):
            source_id = f"o2:{history_id}:{event_id}:{field}"
            observed = _ObservedClaim(
                field_id=history_id,
                subject=event_id,
                predicate=f"o2.event.{field}",
                object=_encoded(value),
                observed_by="resonance-world:o2-observer",
                source_id=source_id,
                source_class="world-observation",
                observed_at=ordinal,
                confidence=1.0,
                direct=True,
            )
            store.ingest(to_evidence_claim(observed, delivery=0))

    claims = [asdict(claim) for claim in store.claims(scope_id=history_id)]
    reconstructed: dict[str, dict[str, Any]] = defaultdict(dict)
    for claim in claims:
        predicate = str(claim["predicate"])
        if not predicate.startswith("o2.event."):
            raise ValueError("unexpected O2 ContextGraph predicate")
        field = predicate.removeprefix("o2.event.")
        reconstructed[str(claim["subject"])][field] = _decoded(str(claim["object"]))

    rows = list(reconstructed.values())
    rows.sort(key=lambda row: (int(row["ordinal"]), str(row["event_id"])))
    return claims, rows


def _answer(value: Any, support: list[str]) -> dict[str, Any]:
    return {"value": value, "support_event_ids": sorted(dict.fromkeys(support))}


def _rows(events: list[dict[str, Any]], kind: str) -> list[dict[str, Any]]:
    return sorted(
        (row for row in events if row.get("kind") == kind),
        key=lambda row: (int(row["interval"]), int(row["ordinal"])),
    )


def _performance_answers(events: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    performance = _rows(events, "performance")
    if not performance:
        return {}
    answers: dict[str, dict[str, Any]] = {}
    success_rows = [row for row in performance if int(row.get("successes", 0)) > 0]
    first = int(success_rows[0]["interval"]) if success_rows else None
    first_support = [
        str(row["event_id"])
        for row in performance
        if first is None or int(row["interval"]) <= first
    ]
    answers["first_success_interval"] = _answer(first, first_support)

    max_interval = max(int(row["interval"]) for row in performance)
    success_by_interval = [0] * max_interval
    for row in performance:
        success_by_interval[int(row["interval"]) - 1] += int(row.get("successes", 0))
    performance_support = [str(row["event_id"]) for row in performance]
    answers["success_count_trajectory"] = _answer(success_by_interval, performance_support)

    member_rows = [row for row in events if isinstance(row.get("member_ids"), list)]
    members = sorted({str(member) for row in member_rows for member in row["member_ids"]})
    if members:
        trajectory = {member: [0] * max_interval for member in members}
        carrier_seen: set[str] = set()
        carrier_sets: list[list[str]] = []
        first_multi: int | None = None
        by_interval: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for row in performance:
            by_interval[int(row["interval"])].append(row)
            member = row.get("subject_id")
            if member in trajectory:
                trajectory[str(member)][int(row["interval"]) - 1] += int(
                    row.get("successes", 0)
                )
        for interval in range(1, max_interval + 1):
            for row in by_interval.get(interval, []):
                if int(row.get("successes", 0)) > 0 and row.get("subject_id") is not None:
                    carrier_seen.add(str(row["subject_id"]))
            carrier_sets.append(sorted(carrier_seen))
            if first_multi is None and len(carrier_seen) > 1:
                first_multi = interval
        answers["per_member_success_trajectory"] = _answer(trajectory, performance_support)
        multi_support = [
            str(row["event_id"])
            for row in performance
            if first_multi is None or int(row["interval"]) <= first_multi
        ]
        answers["first_multi_carrier_interval"] = _answer(first_multi, multi_support)
        answers["carrier_set_by_interval"] = _answer(carrier_sets, performance_support)

    counts = Counter(
        str(row["subject_id"])
        for row in performance
        if row.get("subject_id") is not None and int(row.get("successes", 0)) > 0
    )
    if members:
        vector = {member: counts.get(member, 0) for member in members}
        maximum = max(vector.values()) if vector else 0
        maximum_members = sorted(
            member for member, count in vector.items() if count == maximum
        )
        denominator = sum(vector.values())
        answers["contribution_vector"] = _answer(vector, performance_support)
        answers["maximum_contributing_members"] = _answer(
            maximum_members, performance_support
        )
        answers["maximum_contribution_share"] = _answer(
            {"numerator": maximum, "denominator": denominator}, performance_support
        )
    return answers


def _turnover_answers(events: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    answers: dict[str, dict[str, Any]] = {}
    performance = _rows(events, "performance")
    turnover = _rows(events, "turnover")
    if turnover:
        transition = turnover[0]
        interval = int(transition["interval"])
        support_transition = [str(transition["event_id"])]
        departing = transition.get("departing_member_id")
        answers["departing_carrier_id"] = _answer(departing, support_transition)
        before = [row for row in performance if int(row["interval"]) < interval]
        after = [row for row in performance if int(row["interval"]) >= interval]
        before_values = [int(row.get("successes", 0)) for row in before]
        after_values = [int(row.get("successes", 0)) for row in after]
        answers["pre_departure_success_counts"] = _answer(
            before_values,
            support_transition + [str(row["event_id"]) for row in before],
        )
        answers["post_departure_success_counts"] = _answer(
            after_values,
            support_transition + [str(row["event_id"]) for row in after],
        )
        recovered = next(
            (
                int(row["interval"])
                for row in after
                if int(row.get("successes", 0)) > 0
            ),
            None,
        )
        recovery_rows = [
            row
            for row in after
            if recovered is None or int(row["interval"]) <= recovered
        ]
        answers["recovery_interval"] = _answer(
            recovered,
            support_transition + [str(row["event_id"]) for row in recovery_rows],
        )

    generation = _rows(events, "generation_transition")
    if generation:
        transition = generation[0]
        interval = int(transition["interval"])
        support_transition = [str(transition["event_id"])]
        answers["generation_transition_interval"] = _answer(interval, support_transition)
        after = [row for row in performance if int(row["interval"]) >= interval]
        after_values = [int(row.get("successes", 0)) for row in after]
        answers["post_turnover_success_trajectory"] = _answer(
            after_values,
            support_transition + [str(row["event_id"]) for row in after],
        )
        recovered = next(
            (
                int(row["interval"])
                for row in after
                if int(row.get("successes", 0)) > 0
            ),
            None,
        )
        recovery_rows = [
            row
            for row in after
            if recovered is None or int(row["interval"]) <= recovered
        ]
        answers["first_recovered_interval"] = _answer(
            recovered,
            support_transition + [str(row["event_id"]) for row in recovery_rows],
        )

        event_by_id = {str(row["event_id"]): row for row in events}
        decisions = _rows(events, "decision")
        if decisions:
            decision = decisions[-1]
            chain = [str(item) for item in decision.get("provenance_event_ids", [])]
            support = [str(decision["event_id"]), str(transition["event_id"]), *chain]
            answers["decision_provenance_chain"] = _answer(chain, support)
            crosses = any(
                int(event_by_id[event_id]["interval"]) < interval
                for event_id in chain
                if event_id in event_by_id
            )
            answers["provenance_crosses_generation_boundary"] = _answer(crosses, support)
    return answers


def _relationship_answers(events: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    answers: dict[str, dict[str, Any]] = {}
    interactions = _rows(events, "interaction")
    if interactions:
        grouped: dict[str, list[dict[str, int]]] = defaultdict(list)
        for row in interactions:
            relationship_id = str(row["relationship_id"])
            grouped[relationship_id].append(
                {
                    "interval": int(row["interval"]),
                    "successes": int(row.get("successes", 0)),
                }
            )
        support = [str(row["event_id"]) for row in interactions]
        answers["pair_interaction_intervals"] = _answer(
            {key: grouped[key] for key in sorted(grouped)}, support
        )
        answers["pair_ids"] = _answer(sorted(grouped), support)

    states = _rows(events, "relation_state")
    if states:
        relation_support = [str(row["event_id"]) for row in states]
        max_interval = max(int(row["interval"]) for row in events)
        changes = {int(row["interval"]): bool(row["active"]) for row in states}
        active = False
        active_intervals: list[int] = []
        for interval in range(1, max_interval + 1):
            if interval in changes:
                active = changes[interval]
            if active:
                active_intervals.append(interval)
        answers["relation_active_intervals"] = _answer(
            active_intervals, relation_support
        )
        rupture = next((row for row in states if not bool(row["active"])), None)
        reformation = None
        if rupture is not None:
            rupture_interval = int(rupture["interval"])
            reformation = next(
                (
                    row
                    for row in states
                    if bool(row["active"]) and int(row["interval"]) > rupture_interval
                ),
                None,
            )
        answers["rupture_event_id"] = _answer(
            None if rupture is None else str(rupture["event_id"]), relation_support
        )
        answers["reformation_event_id"] = _answer(
            None if reformation is None else str(reformation["event_id"]),
            relation_support,
        )
    return answers


def _source_answers(events: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    answers: dict[str, dict[str, Any]] = {}
    public_states = _rows(events, "source_public_state")
    services = _rows(events, "service")
    if public_states:
        baseline = int(public_states[0]["public_resource"])
        first_negative: int | None = None
        recovery: int | None = None
        previous = baseline
        for row in public_states[1:]:
            value = int(row["public_resource"])
            interval = int(row["interval"])
            if first_negative is None and value < previous:
                first_negative = interval
            if first_negative is not None and recovery is None and value >= baseline:
                recovery = interval
            previous = value
        negative_support = [
            str(row["event_id"])
            for row in public_states
            if first_negative is None or int(row["interval"]) <= first_negative
        ]
        recovery_support = [
            str(row["event_id"])
            for row in public_states
            if recovery is None or int(row["interval"]) <= recovery
        ]
        answers["first_negative_public_trajectory_interval"] = _answer(
            first_negative, negative_support
        )
        answers["recovery_interval"] = _answer(recovery, recovery_support)
    if services:
        service_support = [str(row["event_id"]) for row in services]
        trajectory = [int(row.get("successes", 0)) for row in services]
        failures = [
            int(row["interval"]) for row in services if int(row.get("successes", 0)) == 0
        ]
        running = 0
        prefix: list[int] = []
        for value in trajectory:
            running += int(value == 0)
            prefix.append(running)
        answers["service_success_trajectory"] = _answer(trajectory, service_support)
        answers["failure_intervals"] = _answer(failures, service_support)
        answers["prefix_cumulative_failures"] = _answer(prefix, service_support)
    return answers


def analyze_events(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Return every longitudinal fact deterministically identifiable from the events."""
    answers: dict[str, dict[str, Any]] = {}
    for part in (
        _performance_answers(events),
        _turnover_answers(events),
        _relationship_answers(events),
        _source_answers(events),
    ):
        answers.update(part)
    return {
        "answers": answers,
        "negative_controls": {key: NOT_IDENTIFIABLE for key in NEGATIVE_CONTROLS},
    }


def analyze_r0(pair_id: str) -> dict[str, Any]:
    """Return the registered aggregate-only epistemic result for one collision pair."""
    return {
        "pair_id": pair_id,
        "answers": {key: NOT_IDENTIFIABLE for key in ALL_LONGITUDINAL_QUERY_IDS},
        "negative_controls": {key: NOT_IDENTIFIABLE for key in NEGATIVE_CONTROLS},
    }
