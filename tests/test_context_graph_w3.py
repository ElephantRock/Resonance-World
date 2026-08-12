import csv
from pathlib import Path

from resonance_world.context_graph_w3 import (
    compile_context,
    evaluate_arm,
    generate_queries,
    infer_shared_requesters,
    load_w3_evidence,
    shuffle_topology,
)


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _fixture(tmp_path: Path):
    runs = tmp_path / "runs.csv"
    outcomes = tmp_path / "outcomes.csv"
    tasks = tmp_path / "tasks.csv"
    _write_csv(
        runs,
        ["run_id", "seed", "arm_label"],
        [{"run_id": "run-1", "seed": 484, "arm_label": "immortal_control"}],
    )
    _write_csv(
        tasks,
        ["run_id", "task_id", "requester_agent_id"],
        [
            {"run_id": "run-1", "task_id": "t1", "requester_agent_id": "requester-x"},
            {"run_id": "run-1", "task_id": "t2", "requester_agent_id": "requester-x"},
            {"run_id": "run-1", "task_id": "t3", "requester_agent_id": "requester-y"},
            {"run_id": "run-1", "task_id": "t4", "requester_agent_id": "requester-z"},
        ],
    )
    _write_csv(
        outcomes,
        ["run_id", "task_id", "winner_agent_id", "created_at"],
        [
            {
                "run_id": "run-1",
                "task_id": "t1",
                "winner_agent_id": "winner-a",
                "created_at": "1",
            },
            {
                "run_id": "run-1",
                "task_id": "t2",
                "winner_agent_id": "winner-b",
                "created_at": "2",
            },
            {
                "run_id": "run-1",
                "task_id": "t3",
                "winner_agent_id": "winner-a",
                "created_at": "3",
            },
            {
                "run_id": "run-1",
                "task_id": "t4",
                "winner_agent_id": "winner-b",
                "created_at": "4",
            },
        ],
    )
    fields = load_w3_evidence(runs, outcomes, tasks)
    field = fields["w3-source-seed-484"]
    query = generate_queries(field, limit=10, salt="test")[0]
    return fields, field, query


def test_graph_recovers_two_hop_shared_requester_without_belief_mutation(
    tmp_path: Path,
) -> None:
    fields, field, query = _fixture(tmp_path)
    before = field.belief_snapshot()
    graph = evaluate_arm(fields, [query], arm="shared_graph", budget=8, salt="test")
    isolated = evaluate_arm(fields, [query], arm="isolated", budget=8, salt="test")

    assert graph.recall == 1.0
    assert graph.false_positive_rate == 0.0
    assert isolated.recall == 0.0
    assert field.belief_snapshot() == before


def test_flat_context_is_matched_in_size_but_does_not_use_two_hop_topology(
    tmp_path: Path,
) -> None:
    _fields, field, query = _fixture(tmp_path)
    flat = compile_context(field, query, arm="pooled_flat", budget=4, salt="flat")
    graph = compile_context(field, query, arm="shared_graph", budget=4, salt="graph")

    assert len(flat) == len(graph) == 4
    assert infer_shared_requesters(graph, query) == query.expected_requesters
    assert infer_shared_requesters(flat, query) != query.expected_requesters


def test_shuffled_graph_preserves_claim_count_and_predicates_but_changes_topology(
    tmp_path: Path,
) -> None:
    _fields, field, _query = _fixture(tmp_path)
    shuffled = shuffle_topology(field.claims, salt="shuffle")

    assert len(shuffled) == len(field.claims)
    assert sorted(claim.predicate for claim in shuffled) == sorted(
        claim.predicate for claim in field.claims
    )
    original_edges = {
        (claim.subject, claim.object)
        for claim in field.claims
        if claim.predicate == "requested_by"
    }
    shuffled_edges = {
        (claim.subject, claim.object)
        for claim in shuffled
        if claim.predicate == "requested_by"
    }
    assert shuffled_edges != original_edges
