from collections import defaultdict
from typing import Any

ALL_LONGITUDINAL_QUERY_IDS = (
    "performance_baseline",
    "pre_departure_success_counts",
    "post_departure_success_counts",
    "recovery_interval",
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

NEGATIVE_CONTROLS = (
    "control_1",
    "control_2",
    "control_3",
)

NOT_IDENTIFIABLE = "NOT_IDENTIFIABLE"


def _rows(events: list[dict[str, Any]], type_name: str) -> list[dict[str, Any]]:
    return [e for e in events if e.get("type") == type_name]


def _answer(value: Any, support: list[str]) -> dict[str, Any]:
    return {"value": value, "support": support}


def _performance_answers(events: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    answers: dict[str, dict[str, Any]] = {}
    performance = _rows(events, "performance")
    if performance:
        baseline_row = performance[0]
        baseline = int(baseline_row["successes"])
        support = [str(baseline_row["event_id"])]
        answers["performance_baseline"] = _answer(baseline, support)
        values = [int(row.get("successes", 0)) for row in performance]
        support = [str(row["event_id"]) for row in performance]
        answers["pre_departure_success_trajectory"] = _answer(values, support)
    return answers


def _turnover_answers(events: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    answers: dict[str, dict[str, Any]] = {}
    turnover = _rows(events, "turnover_transition")
    performance = _rows(events, "performance")
    if turnover:
        transition = turnover[0]
        interval = int(transition["interval"])
        support_transition = [str(transition["event_id"])]
        answers["turnover_transition_interval"] = _answer(interval, support_transition)
        after = [row for row in performance if int(row["interval"]) >= interval]
        before_values = [int(row.get("successes", 0)) for row in performance if int(row["interval"]) < interval]
        after_values = [int(row.get("successes", 0)) for row in after]
        answers["pre_departure_success_counts"] = _answer(
            before_values,
            support_transition + [str(row["event_id"]) for row in performance if int(row["interval"]) < interval],
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
