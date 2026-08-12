"""CG-1: context-graph retrieval over immutable W3 raw event evidence.

The experiment reconstructs local evidence from W3 task/outcome records rather than
using W3's derived pair edges.  The held-out query asks which requester identities
were served by *both* members of a winner pair.  Answering requires two-hop traversal:

    winner -> completed task -> requester

The four arms differ only in context assembly.  Canonical answers are scored from the
immutable event record and never injected into evidence or agent belief state.
"""

from __future__ import annotations

import csv
import hashlib
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from itertools import combinations
from pathlib import Path
from typing import Any, Literal

from .context_graph_experiment import BeliefGraph, EvidenceClaim

CG1Arm = Literal["isolated", "pooled_flat", "shared_graph", "shuffled_graph"]
ARMS: tuple[CG1Arm, ...] = (
    "isolated",
    "pooled_flat",
    "shared_graph",
    "shuffled_graph",
)


def _read_csv(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open(newline="", encoding="utf-8") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _stable_rank(*parts: object) -> bytes:
    return hashlib.sha256("|".join(str(part) for part in parts).encode()).digest()


def _entity(kind: str, field_id: str, value: str) -> str:
    return f"{kind}:{field_id}:{value}"


def _claim_key(claim: EvidenceClaim) -> tuple[str, str, str, str, str]:
    return (
        claim.subject,
        claim.predicate,
        claim.object,
        claim.source_id,
        claim.observed_by,
    )


@dataclass(frozen=True, slots=True)
class CG1Query:
    query_id: str
    field_id: str
    agent_id: str
    left: str
    right: str
    expected_requesters: frozenset[str]


@dataclass(slots=True)
class W3FieldEvidence:
    field_id: str
    claims: tuple[EvidenceClaim, ...]
    winner_to_requesters: dict[str, frozenset[str]]
    beliefs: dict[str, BeliefGraph] = field(default_factory=dict)

    def belief_snapshot(self) -> dict[str, tuple[object, ...]]:
        return {
            agent_id: graph.snapshot()
            for agent_id, graph in sorted(self.beliefs.items())
        }


@dataclass(frozen=True, slots=True)
class CG1Metrics:
    arm: CG1Arm
    query_count: int
    true_answers: int
    false_answers: int
    possible_answers: int
    exact_queries: int
    cross_observer_answers: int
    context_claims: int
    provenance_completeness: float

    @property
    def recall(self) -> float:
        return self.true_answers / self.possible_answers if self.possible_answers else 1.0

    @property
    def false_positive_rate(self) -> float:
        total = self.true_answers + self.false_answers
        return self.false_answers / total if total else 0.0

    @property
    def exact_query_rate(self) -> float:
        return self.exact_queries / self.query_count if self.query_count else 1.0

    @property
    def mean_context_claims(self) -> float:
        return self.context_claims / self.query_count if self.query_count else 0.0

    @property
    def context_efficiency(self) -> float:
        return self.true_answers / self.context_claims if self.context_claims else 0.0


def verify_source_hashes(paths: dict[str, str | Path], expected: dict[str, str]) -> None:
    missing = set(expected) - set(paths)
    if missing:
        raise ValueError(f"missing source paths for: {sorted(missing)}")
    for name, wanted in expected.items():
        actual = sha256_file(paths[name])
        if actual != wanted:
            raise ValueError(f"{name} sha256 mismatch: expected {wanted}, got {actual}")


def load_w3_evidence(
    runs_path: str | Path,
    outcomes_path: str | Path,
    tasks_path: str | Path,
) -> dict[str, W3FieldEvidence]:
    """Materialize local winner evidence and canonical requester service relations."""

    runs = _read_csv(runs_path)
    outcomes = _read_csv(outcomes_path)
    tasks = _read_csv(tasks_path)
    run_to_field = {
        row["run_id"]: f"w3-source-seed-{int(row['seed'])}"
        for row in runs
        if row.get("arm_label") == "immortal_control"
    }
    if not run_to_field:
        raise ValueError("no W3 immortal-control source runs found")

    requester_by_task = {
        (row["run_id"], row["task_id"]): row["requester_agent_id"]
        for row in tasks
    }
    claims_by_field: dict[str, list[EvidenceClaim]] = defaultdict(list)
    requesters_by_winner: dict[str, dict[str, set[str]]] = defaultdict(
        lambda: defaultdict(set)
    )

    for row in outcomes:
        run_id = row["run_id"]
        if run_id not in run_to_field:
            continue
        winner = row.get("winner_agent_id", "")
        requester = requester_by_task.get((run_id, row["task_id"]), "")
        if not winner or not requester:
            continue
        field_id = run_to_field[run_id]
        winner_entity = _entity("agent", field_id, winner)
        requester_entity = _entity("agent", field_id, requester)
        task_entity = _entity("task", field_id, row["task_id"])
        observed_at = row.get("created_at") or None
        claims_by_field[field_id].append(
            EvidenceClaim(
                subject=winner_entity,
                predicate="completed",
                object=task_entity,
                source_id=f"w3:{run_id}:outcome:{row['task_id']}",
                observed_by=winner_entity,
                confidence=1.0,
                direct=True,
                observed_at=observed_at,
            )
        )
        claims_by_field[field_id].append(
            EvidenceClaim(
                subject=task_entity,
                predicate="requested_by",
                object=requester_entity,
                source_id=f"w3:{run_id}:task:{row['task_id']}",
                observed_by=winner_entity,
                confidence=1.0,
                direct=True,
                observed_at=observed_at,
            )
        )
        requesters_by_winner[field_id][winner_entity].add(requester_entity)

    result: dict[str, W3FieldEvidence] = {}
    for field_id in sorted(claims_by_field):
        claims = tuple(sorted(claims_by_field[field_id], key=_claim_key))
        beliefs: dict[str, BeliefGraph] = {}
        for claim in claims:
            graph = beliefs.setdefault(claim.observed_by, BeliefGraph(claim.observed_by))
            graph.observe(claim)
        result[field_id] = W3FieldEvidence(
            field_id=field_id,
            claims=claims,
            winner_to_requesters={
                winner: frozenset(values)
                for winner, values in sorted(requesters_by_winner[field_id].items())
            },
            beliefs=beliefs,
        )
    return result


def generate_queries(
    field: W3FieldEvidence,
    *,
    limit: int,
    salt: str,
) -> tuple[CG1Query, ...]:
    candidates: list[CG1Query] = []
    winners = sorted(field.winner_to_requesters)
    for left, right in combinations(winners, 2):
        expected = field.winner_to_requesters[left] & field.winner_to_requesters[right]
        if not expected:
            continue
        digest = hashlib.sha256(f"{salt}|{field.field_id}|{left}|{right}".encode()).hexdigest()
        candidates.append(
            CG1Query(
                query_id=f"cg1-{digest[:16]}",
                field_id=field.field_id,
                agent_id=left,
                left=left,
                right=right,
                expected_requesters=frozenset(expected),
            )
        )
    candidates.sort(key=lambda row: _stable_rank(salt, row.query_id))
    if limit <= 0:
        return tuple(candidates)
    return tuple(candidates[:limit])


def shuffle_topology(
    claims: Sequence[EvidenceClaim],
    *,
    salt: str,
) -> tuple[EvidenceClaim, ...]:
    """Permute requester targets while preserving task degree and requester marginals."""

    requester_indexes = [
        index for index, claim in enumerate(claims) if claim.predicate == "requested_by"
    ]
    if len(requester_indexes) < 2:
        return tuple(claims)
    ordered = sorted(
        requester_indexes,
        key=lambda index: _stable_rank(salt, *_claim_key(claims[index])),
    )
    objects = [claims[index].object for index in ordered]
    shift = 1 + int.from_bytes(_stable_rank(salt, "shift")[:4], "big") % (len(objects) - 1)
    rotated = objects[shift:] + objects[:shift]
    replacements = dict(zip(ordered, rotated, strict=True))
    output: list[EvidenceClaim] = []
    for index, claim in enumerate(claims):
        if index not in replacements:
            output.append(claim)
            continue
        output.append(
            EvidenceClaim(
                subject=claim.subject,
                predicate=claim.predicate,
                object=replacements[index],
                source_id=claim.source_id,
                observed_by=claim.observed_by,
                confidence=claim.confidence,
                direct=claim.direct,
                observed_at=claim.observed_at,
                valid_from=claim.valid_from,
                valid_until=claim.valid_until,
            )
        )
    return tuple(output)


def _fill_to_budget(
    selected: Iterable[EvidenceClaim],
    pool: Sequence[EvidenceClaim],
    *,
    budget: int,
    salt: str,
) -> tuple[EvidenceClaim, ...]:
    if budget <= 0:
        raise ValueError("context budget must be positive")
    output: list[EvidenceClaim] = []
    seen: set[tuple[str, str, str, str, str]] = set()
    for claim in selected:
        key = _claim_key(claim)
        if key in seen:
            continue
        output.append(claim)
        seen.add(key)
        if len(output) >= budget:
            return tuple(output)
    remaining = sorted(
        (claim for claim in pool if _claim_key(claim) not in seen),
        key=lambda claim: _stable_rank(salt, *_claim_key(claim)),
    )
    for claim in remaining:
        output.append(claim)
        if len(output) >= budget:
            break
    return tuple(output)


def _path_bundles(
    claims: Sequence[EvidenceClaim],
    agent_id: str,
) -> list[tuple[EvidenceClaim, ...]]:
    completed = sorted(
        (
            claim
            for claim in claims
            if claim.subject == agent_id and claim.predicate == "completed"
        ),
        key=_claim_key,
    )
    by_task: dict[str, list[EvidenceClaim]] = defaultdict(list)
    for claim in claims:
        if claim.predicate == "requested_by":
            by_task[claim.subject].append(claim)
    bundles: list[tuple[EvidenceClaim, ...]] = []
    for completion in completed:
        linked = sorted(by_task.get(completion.object, []), key=_claim_key)
        bundles.append(tuple([completion, *linked]))
    return bundles


def _graph_selected(
    claims: Sequence[EvidenceClaim], query: CG1Query
) -> tuple[EvidenceClaim, ...]:
    left = _path_bundles(claims, query.left)
    right = _path_bundles(claims, query.right)
    output: list[EvidenceClaim] = []
    for index in range(max(len(left), len(right))):
        if index < len(left):
            output.extend(left[index])
        if index < len(right):
            output.extend(right[index])
    return tuple(output)


def compile_context(
    field: W3FieldEvidence,
    query: CG1Query,
    *,
    arm: CG1Arm,
    budget: int,
    salt: str,
    shuffled_claims: Sequence[EvidenceClaim] | None = None,
) -> tuple[EvidenceClaim, ...]:
    if arm == "isolated":
        local = tuple(
            claim for claim in field.claims if claim.observed_by == query.agent_id
        )
        return _fill_to_budget(
            _graph_selected(local, query),
            local,
            budget=budget,
            salt=f"{salt}:isolated:{query.query_id}",
        )

    pool = tuple(shuffled_claims) if arm == "shuffled_graph" else field.claims
    if arm in {"shared_graph", "shuffled_graph"}:
        selected = _graph_selected(pool, query)
    elif arm == "pooled_flat":
        selected = tuple(
            claim
            for claim in pool
            if claim.subject in {query.left, query.right}
            or claim.object in {query.left, query.right}
        )
    else:
        raise ValueError(f"unknown CG-1 arm: {arm}")
    return _fill_to_budget(
        selected,
        pool,
        budget=budget,
        salt=f"{salt}:{arm}:{query.query_id}",
    )


def infer_shared_requesters(
    context: Iterable[EvidenceClaim], query: CG1Query
) -> frozenset[str]:
    rows = tuple(context)

    def served(agent_id: str) -> set[str]:
        tasks = {
            claim.object
            for claim in rows
            if claim.subject == agent_id and claim.predicate == "completed"
        }
        return {
            claim.object
            for claim in rows
            if claim.subject in tasks and claim.predicate == "requested_by"
        }

    return frozenset(served(query.left) & served(query.right))


def evaluate_arm(
    fields: dict[str, W3FieldEvidence],
    queries: Iterable[CG1Query],
    *,
    arm: CG1Arm,
    budget: int,
    salt: str,
) -> CG1Metrics:
    query_rows = tuple(queries)
    true_answers = 0
    false_answers = 0
    possible_answers = 0
    exact_queries = 0
    cross_observer_answers = 0
    context_claims = 0
    complete_provenance = 0

    shuffled_by_field = {
        field_id: shuffle_topology(field.claims, salt=f"{salt}:{field_id}")
        for field_id, field in fields.items()
    }

    for query in query_rows:
        field = fields[query.field_id]
        context = compile_context(
            field,
            query,
            arm=arm,
            budget=budget,
            salt=salt,
            shuffled_claims=shuffled_by_field[query.field_id],
        )
        predicted = infer_shared_requesters(context, query)
        expected = query.expected_requesters
        true = predicted & expected
        false = predicted - expected
        true_answers += len(true)
        false_answers += len(false)
        possible_answers += len(expected)
        exact_queries += int(predicted == expected)
        context_claims += len(context)
        complete_provenance += sum(
            bool(claim.source_id and claim.observed_by) for claim in context
        )

        for requester in true:
            supporting_observers: set[str] = set()
            for agent_id in (query.left, query.right):
                tasks = {
                    claim.object
                    for claim in context
                    if claim.subject == agent_id and claim.predicate == "completed"
                }
                if any(
                    claim.subject in tasks
                    and claim.predicate == "requested_by"
                    and claim.object == requester
                    for claim in context
                ):
                    supporting_observers.add(agent_id)
            cross_observer_answers += int(len(supporting_observers) == 2)

    provenance = complete_provenance / context_claims if context_claims else 1.0
    return CG1Metrics(
        arm=arm,
        query_count=len(query_rows),
        true_answers=true_answers,
        false_answers=false_answers,
        possible_answers=possible_answers,
        exact_queries=exact_queries,
        cross_observer_answers=cross_observer_answers,
        context_claims=context_claims,
        provenance_completeness=provenance,
    )


def metrics_row(metrics: CG1Metrics) -> dict[str, object]:
    return {
        "arm": metrics.arm,
        "query_count": metrics.query_count,
        "true_answers": metrics.true_answers,
        "false_answers": metrics.false_answers,
        "possible_answers": metrics.possible_answers,
        "exact_queries": metrics.exact_queries,
        "cross_observer_answers": metrics.cross_observer_answers,
        "context_claims": metrics.context_claims,
        "mean_context_claims": metrics.mean_context_claims,
        "provenance_completeness": metrics.provenance_completeness,
        "recall": metrics.recall,
        "false_positive_rate": metrics.false_positive_rate,
        "exact_query_rate": metrics.exact_query_rate,
        "context_efficiency": metrics.context_efficiency,
    }


def phase_queries(
    fields: dict[str, W3FieldEvidence],
    field_ids: Sequence[str],
    *,
    limit_per_field: int,
    salt: str,
) -> tuple[CG1Query, ...]:
    output: list[CG1Query] = []
    for field_id in field_ids:
        if field_id not in fields:
            raise ValueError(f"missing source field: {field_id}")
        output.extend(
            generate_queries(
                fields[field_id],
                limit=limit_per_field,
                salt=f"{salt}:{field_id}",
            )
        )
    return tuple(output)


def run_cg1(
    source_paths: dict[str, str | Path],
    config: dict[str, Any],
) -> dict[str, object]:
    verify_source_hashes(source_paths, config["source"]["raw_sha256"])
    fields = load_w3_evidence(
        source_paths["runs.csv"],
        source_paths["outcomes.csv"],
        source_paths["tasks.csv"],
    )
    budget = int(config["context"]["claim_budget"])
    query_limit = int(config["queries"]["max_per_field"])
    salt = str(config["version"])
    phases: dict[str, object] = {}
    belief_before = {
        field_id: field.belief_snapshot() for field_id, field in fields.items()
    }

    for phase, seeds in (
        ("calibration", config["source"]["calibration_seeds"]),
        ("evaluation", config["source"]["evaluation_seeds"]),
    ):
        field_ids = [f"w3-source-seed-{int(seed)}" for seed in seeds]
        queries = phase_queries(
            fields,
            field_ids,
            limit_per_field=query_limit,
            salt=f"{salt}:{phase}",
        )
        metrics = {
            arm: evaluate_arm(fields, queries, arm=arm, budget=budget, salt=f"{salt}:{phase}")
            for arm in ARMS
        }
        phases[phase] = {
            "field_ids": field_ids,
            "query_count": len(queries),
            "metrics": {arm: metrics_row(row) for arm, row in metrics.items()},
        }

    belief_after = {
        field_id: field.belief_snapshot() for field_id, field in fields.items()
    }
    belief_contamination = int(belief_after != belief_before)
    evaluation = phases["evaluation"]
    assert isinstance(evaluation, dict)
    metric_rows = evaluation["metrics"]
    assert isinstance(metric_rows, dict)
    isolated = metric_rows["isolated"]
    flat = metric_rows["pooled_flat"]
    graph = metric_rows["shared_graph"]
    shuffled = metric_rows["shuffled_graph"]
    gates = config["success_gates"]

    graph_efficiency_ratio = (
        float(graph["context_efficiency"]) / float(flat["context_efficiency"])
        if float(flat["context_efficiency"]) > 0
        else float("inf")
    )
    nonisolated_context_matched = all(
        float(metric_rows[arm]["mean_context_claims"]) == budget
        for arm in ("pooled_flat", "shared_graph", "shuffled_graph")
    )
    gate_results = {
        "evaluation_query_count_min": int(evaluation["query_count"])
        >= int(gates["evaluation_query_count_min"]),
        "graph_recall_lift_over_isolated_min": float(graph["recall"])
        - float(isolated["recall"])
        >= float(gates["graph_recall_lift_over_isolated_min"]),
        "graph_recall_lift_over_flat_min": float(graph["recall"])
        - float(flat["recall"])
        >= float(gates["graph_recall_lift_over_flat_min"]),
        "graph_recall_lift_over_shuffled_min": float(graph["recall"])
        - float(shuffled["recall"])
        >= float(gates["graph_recall_lift_over_shuffled_min"]),
        "graph_efficiency_ratio_over_flat_min": graph_efficiency_ratio
        >= float(gates["graph_efficiency_ratio_over_flat_min"]),
        "graph_false_positive_rate_max": float(graph["false_positive_rate"])
        <= float(gates["graph_false_positive_rate_max"]),
        "graph_provenance_completeness_min": float(graph["provenance_completeness"])
        >= float(gates["graph_provenance_completeness_min"]),
        "belief_contamination_max": belief_contamination
        <= int(gates["belief_contamination_max"]),
        "nonisolated_context_budget_matched": nonisolated_context_matched,
    }

    return {
        "version": "context-graph-cg1-w3-result-v0.1",
        "config_version": config["version"],
        "source": config["source"],
        "phases": phases,
        "diagnostics": {
            "belief_contamination": belief_contamination,
            "graph_efficiency_ratio_over_flat": graph_efficiency_ratio,
            "nonisolated_context_budget_matched": nonisolated_context_matched,
            "field_claim_counts": {
                field_id: len(field.claims) for field_id, field in sorted(fields.items())
            },
        },
        "gate_results": gate_results,
        "passed": all(gate_results.values()),
    }
