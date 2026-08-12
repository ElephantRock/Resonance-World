"""Execute the preregistered deterministic context-graph fixture."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from resonance_world.context_graph_experiment import (
    ConditionMetrics,
    ContextGraphExperiment,
    EvidenceClaim,
    SharedDependencyQuery,
    WorldFact,
)


def _read_json(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain an object")
    return value


def _write_json(path: str | Path, value: object) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _metric_row(metrics: ConditionMetrics) -> dict[str, object]:
    return {
        "policy": metrics.policy,
        "true_answers": metrics.true_answers,
        "false_answers": metrics.false_answers,
        "possible_answers": metrics.possible_answers,
        "exact_queries": metrics.exact_queries,
        "query_count": metrics.query_count,
        "cross_agent_answers": metrics.cross_agent_answers,
        "provenance_completeness": metrics.provenance_completeness,
        "recall": metrics.recall,
        "false_positive_rate": metrics.false_positive_rate,
        "exact_query_rate": metrics.exact_query_rate,
    }


def run(config_path: str | Path, output_path: str | Path) -> dict[str, object]:
    config = _read_json(config_path)
    fixture = config["fixture"]
    context_policy = config["context_policy"]
    experiment = ContextGraphExperiment()

    for row in fixture["canonical_facts"]:
        experiment.world.add(
            WorldFact(
                subject=str(row["subject"]),
                predicate=str(row["predicate"]),
                object=str(row["object"]),
            )
        )

    for row in fixture["evidence_claims"]:
        experiment.ingest(
            EvidenceClaim(
                subject=str(row["subject"]),
                predicate=str(row["predicate"]),
                object=str(row["object"]),
                source_id=str(row["source_id"]),
                observed_by=str(row["observed_by"]),
                confidence=float(row["confidence"]),
                direct=bool(row["direct"]),
                observed_at=row.get("observed_at"),
                valid_from=row.get("valid_from"),
                valid_until=row.get("valid_until"),
            )
        )

    queries = [
        SharedDependencyQuery(
            query_id=str(row["query_id"]),
            agent_id=str(row["agent_id"]),
            left=str(row["left"]),
            right=str(row["right"]),
            predicate=str(row["predicate"]),
        )
        for row in fixture["queries"]
    ]

    before_beliefs = experiment.belief_snapshot()
    max_hops = int(context_policy["max_hops"])
    min_confidence = float(context_policy["min_confidence"])
    isolated = experiment.evaluate(
        queries,
        policy="isolated",
        max_hops=max_hops,
        min_confidence=min_confidence,
    )
    shared = experiment.evaluate(
        queries,
        policy="shared_evidence",
        max_hops=max_hops,
        min_confidence=min_confidence,
    )
    belief_contamination = int(experiment.belief_snapshot() != before_beliefs)
    raw_contradictions = experiment.evidence.contradictions()
    filtered_contradictions = experiment.evidence.contradictions(
        min_confidence=min_confidence
    )

    gates = config["success_gates"]
    gate_results = {
        "shared_recall_min": shared.recall >= float(gates["shared_recall_min"]),
        "isolated_recall_max": isolated.recall <= float(gates["isolated_recall_max"]),
        "shared_false_positive_rate_max": shared.false_positive_rate
        <= float(gates["shared_false_positive_rate_max"]),
        "shared_provenance_completeness_min": shared.provenance_completeness
        >= float(gates["shared_provenance_completeness_min"]),
        "cross_agent_answers_min": shared.cross_agent_answers
        >= int(gates["cross_agent_answers_min"]),
        "raw_contradiction_groups_min": len(raw_contradictions)
        >= int(gates["raw_contradiction_groups_min"]),
        "filtered_contradiction_groups_max": len(filtered_contradictions)
        <= int(gates["filtered_contradiction_groups_max"]),
        "belief_contamination_max": belief_contamination
        <= int(gates["belief_contamination_max"]),
    }

    result: dict[str, object] = {
        "version": "context-graph-fixture-result-v0.1",
        "config_version": config["version"],
        "conditions": {
            "isolated": _metric_row(isolated),
            "shared_evidence": _metric_row(shared),
        },
        "diagnostics": {
            "raw_contradiction_groups": len(raw_contradictions),
            "filtered_contradiction_groups": len(filtered_contradictions),
            "belief_contamination": belief_contamination,
        },
        "gate_results": gate_results,
        "passed": all(gate_results.values()),
    }
    _write_json(output_path, result)
    print(json.dumps(result, indent=2, sort_keys=True))
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        default="experiments/context_graph/experiment.json",
    )
    parser.add_argument(
        "--output",
        default="output/context_graph/result.json",
    )
    args = parser.parse_args()
    result = run(args.config, args.output)
    if not result["passed"]:
        raise SystemExit("context-graph fixture failed preregistered gates")


if __name__ == "__main__":
    main()
