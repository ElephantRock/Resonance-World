"""Execute the preregistered W9-00B source-criticality calibration assay.

The `prepare` command reads public source evidence only and materializes every
prediction before private source state is consulted. The `evaluate` command then
scores those frozen predictions against the private source frontier used only as
holdout truth.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence

from .w7_campaign import _evidence_ref, _public_score
from .w8_campaign import _source_frontier, load_population
from .w9_calibration import (
    CalibrationObservation,
    CalibrationThresholds,
    build_calibration_report,
)
from .w9_criticality import (
    MarginalSourceCostEstimate,
    MissionStratumValue,
    SourceValueEstimate,
    marginal_interaction_pp,
)

PREDICTION_VERSION = "w9-calibration-predictions-v0.1"
RESULT_VERSION = "w9-calibration-result-v0.1"


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _read_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in Path(path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _write_json(path: str | Path, value: object) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _expected_seeds(config: Mapping[str, Any], phase: str) -> list[int]:
    key = f"{phase}_seeds"
    if key not in config:
        raise ValueError(f"unsupported W9 phase: {phase}")
    return [int(seed) for seed in config[key]]


def _field_id(seed: int) -> str:
    return f"w4-source-seed-{seed}"


def _load_public_population(
    source_dir: str | Path,
    *,
    expected_seeds: Sequence[int],
) -> tuple[tuple[dict[str, Any], ...], dict[str, tuple[dict[str, Any], ...]], str]:
    source = Path(source_dir)
    candidate_path = source / "candidates.jsonl"
    candidates = _read_jsonl(candidate_path)
    source_fields = _read_json(source / "source-fields.json")
    if not isinstance(source_fields, list):
        raise ValueError("source-fields.json must be an array")

    public_text = json.dumps(candidates, sort_keys=True)
    if "practice_by_skill" in public_text:
        raise ValueError("private practice leaked into W9 public estimator input")

    expected = sorted(int(seed) for seed in expected_seeds)
    observed = sorted(int(row["seed"]) for row in source_fields)
    if observed != expected:
        raise ValueError(f"source seed mismatch: expected {expected}, observed {observed}")

    expected_fields = {_field_id(seed) for seed in expected}
    by_field: dict[str, list[dict[str, Any]]] = {}
    seen_agents: set[str] = set()
    for candidate in candidates:
        field_id = str(candidate["field_id"])
        agent_id = str(candidate["agent_id"])
        if field_id not in expected_fields:
            raise ValueError(f"unexpected public source Field: {field_id}")
        if agent_id in seen_agents:
            raise ValueError(f"duplicate public candidate: {agent_id}")
        seen_agents.add(agent_id)
        by_field.setdefault(field_id, []).append(candidate)

    expected_agents = len(expected) * 12
    if len(candidates) != expected_agents:
        raise ValueError(
            f"W9 requires {expected_agents} public candidates; got {len(candidates)}"
        )
    if set(by_field) != expected_fields or any(len(rows) != 12 for rows in by_field.values()):
        raise ValueError("W9 requires exactly 12 public candidates in each source Field")

    ordered = tuple(
        sorted(candidates, key=lambda row: (str(row["field_id"]), str(row["agent_id"])))
    )
    grouped = {
        key: tuple(sorted(rows, key=lambda row: str(row["agent_id"])))
        for key, rows in by_field.items()
    }
    candidate_sha256 = hashlib.sha256(candidate_path.read_bytes()).hexdigest()
    return ordered, grouped, candidate_sha256


def _mission_occurrence_weights(config: Mapping[str, Any]) -> tuple[tuple[str, float], ...]:
    missions = list(config["home_service_missions"])
    if not missions:
        raise ValueError("home_service_missions must be non-empty")
    trials = int(config["service_trials"])
    if trials <= 0:
        raise ValueError("service_trials must be positive")
    counts: Counter[str] = Counter()
    order: list[str] = []
    for trial in range(trials):
        skill = str(missions[trial % len(missions)]["skill"])
        counts[skill] += 1
        if skill not in order:
            order.append(skill)
    return tuple((skill, counts[skill] / trials) for skill in order)


def _public_skill_probability(
    candidate: Mapping[str, Any],
    skill: str,
    config: Mapping[str, Any],
) -> float:
    public_config = {"public_selector": dict(config["public_estimator"]["selector"])}
    score = _public_score(dict(candidate), {skill: 1.0}, public_config)
    law = dict(config["source_service_law"])
    base = float(law["base_success_probability"])
    maximum = float(law["maximum_success_probability"])
    value = base + (maximum - base) * score
    return min(maximum, max(base, value))


def _source_value_estimate(
    field_candidates: Sequence[Mapping[str, Any]],
    unavailable_agent_ids: frozenset[str],
    config: Mapping[str, Any],
) -> SourceValueEstimate:
    if not field_candidates:
        raise ValueError("source value estimate requires candidates")
    field_id = str(field_candidates[0]["field_id"])
    available = [
        row for row in field_candidates if str(row["agent_id"]) not in unavailable_agent_ids
    ]
    if not available:
        raise ValueError("source value estimator cannot remove an entire Field")

    strata: list[MissionStratumValue] = []
    for skill, weight in _mission_occurrence_weights(config):
        expected = max(_public_skill_probability(row, skill, config) for row in available)
        strata.append(MissionStratumValue(skill, weight, expected))

    evidence_refs = tuple(sorted(_evidence_ref(dict(row)) for row in field_candidates))
    return SourceValueEstimate(
        source_field_id=field_id,
        unavailable_agent_ids=unavailable_agent_ids,
        strata=tuple(strata),
        evidence_refs=evidence_refs,
    )


def _estimate_marginal_cost(
    field_candidates: Sequence[Mapping[str, Any]],
    *,
    agent_id: str,
    unavailable_agent_ids: frozenset[str],
    config: Mapping[str, Any],
) -> MarginalSourceCostEstimate:
    before = _source_value_estimate(field_candidates, unavailable_agent_ids, config)
    after = _source_value_estimate(
        field_candidates,
        unavailable_agent_ids | {agent_id},
        config,
    )
    return MarginalSourceCostEstimate.from_counterfactuals(
        before=before,
        after=after,
        agent_id=agent_id,
        standard_error_pp=float(config["estimator_residual_se_pp"]),
        conservative_z=float(config["conservative_z"]),
    )


def _prediction_row(
    *,
    context_kind: str,
    estimate: MarginalSourceCostEstimate,
) -> dict[str, Any]:
    return {
        "agent_id": estimate.agent_id,
        "conservative_budget_pp": estimate.budget_cost_pp,
        "context_kind": context_kind,
        "evidence_refs": list(estimate.evidence_refs),
        "predicted_loss_pp": estimate.estimated_loss_pp,
        "source_field_id": estimate.source_field_id,
        "standard_error_pp": estimate.standard_error_pp,
        "unavailable_agent_ids": sorted(estimate.already_unavailable_agent_ids),
    }


def build_prediction_manifest(
    source_dir: str | Path,
    config: Mapping[str, Any],
    *,
    phase: str,
) -> dict[str, Any]:
    """Build every W9-00B prediction without reading private source capsules."""

    expected_seeds = _expected_seeds(config, phase)
    candidates, by_field, candidate_sha256 = _load_public_population(
        source_dir,
        expected_seeds=expected_seeds,
    )
    offset = int(config["principal_context_partner_offset"])
    if offset <= 0 or offset >= 12:
        raise ValueError("principal context partner offset must lie in [1, 11]")

    principal: list[dict[str, Any]] = []
    interactions: list[dict[str, Any]] = []
    for field_id in sorted(by_field):
        rows = by_field[field_id]
        agent_ids = [str(row["agent_id"]) for row in rows]
        unconditional: dict[str, MarginalSourceCostEstimate] = {}
        for agent_id in agent_ids:
            estimate = _estimate_marginal_cost(
                rows,
                agent_id=agent_id,
                unavailable_agent_ids=frozenset(),
                config=config,
            )
            unconditional[agent_id] = estimate
            principal.append(_prediction_row(context_kind="singleton", estimate=estimate))

        for index, agent_id in enumerate(agent_ids):
            partner_id = agent_ids[(index + offset) % len(agent_ids)]
            estimate = _estimate_marginal_cost(
                rows,
                agent_id=agent_id,
                unavailable_agent_ids=frozenset({partner_id}),
                config=config,
            )
            principal.append(_prediction_row(context_kind="cyclic_context", estimate=estimate))

        for agent_id in agent_ids:
            for partner_id in agent_ids:
                if partner_id == agent_id:
                    continue
                conditional = _estimate_marginal_cost(
                    rows,
                    agent_id=agent_id,
                    unavailable_agent_ids=frozenset({partner_id}),
                    config=config,
                )
                interactions.append(
                    {
                        "agent_id": agent_id,
                        "conditioning_agent_id": partner_id,
                        "conditional_predicted_loss_pp": conditional.estimated_loss_pp,
                        "evidence_refs": list(conditional.evidence_refs),
                        "predicted_interaction_pp": marginal_interaction_pp(
                            unconditional=unconditional[agent_id],
                            conditional=conditional,
                        ),
                        "source_field_id": field_id,
                        "unconditional_predicted_loss_pp": (
                            unconditional[agent_id].estimated_loss_pp
                        ),
                    }
                )

    expected_fields = len(expected_seeds)
    expected_agents = expected_fields * 12
    if len(principal) != expected_fields * 24:
        raise AssertionError("principal calibration manifest cardinality mismatch")
    if len(interactions) != expected_fields * 12 * 11:
        raise AssertionError("pairwise interaction manifest cardinality mismatch")

    config_digest = _sha256(config)
    manifest = {
        "agent_count": len(candidates),
        "candidate_sha256": candidate_sha256,
        "config_sha256": config_digest,
        "field_count": expected_fields,
        "field_sha": str(config["field_sha"]),
        "interaction_observation_count": len(interactions),
        "pairwise_interactions": interactions,
        "phase": phase,
        "principal_observation_count": len(principal),
        "principal_observations": principal,
        "seeds": expected_seeds,
        "version": PREDICTION_VERSION,
    }
    if len(candidates) != expected_agents:
        raise AssertionError("public prediction manifest agent count mismatch")
    serialized = json.dumps(manifest, sort_keys=True)
    if "practice_by_skill" in serialized:
        raise AssertionError("private practice leaked into W9 prediction manifest")
    manifest["manifest_sha256"] = _sha256(manifest)
    return manifest


def _thresholds(config: Mapping[str, Any]) -> CalibrationThresholds:
    values = dict(config["calibration"])
    return CalibrationThresholds(
        max_mae_pp=float(values["max_mae_pp"]),
        max_abs_bias_pp=float(values["max_abs_bias_pp"]),
        min_spearman_rho=float(values["min_spearman_rho"]),
        min_high_cost_safe_rate=float(values["min_high_cost_safe_rate"]),
        max_high_cost_underprediction_pp=float(values["max_high_cost_underprediction_pp"]),
    )


def _realized_marginal_cost_pp(
    field_states: Sequence[Any],
    *,
    agent_id: str,
    unavailable_agent_ids: frozenset[str],
    config: Mapping[str, Any],
) -> float:
    before = [
        state for state in field_states if state.agent_id not in unavailable_agent_ids
    ]
    if agent_id not in {state.agent_id for state in before}:
        raise ValueError("realized holdout candidate is not available in the before context")
    after = [state for state in before if state.agent_id != agent_id]
    return (_source_frontier(before, config) - _source_frontier(after, config)) * 100.0


def _interaction_summary(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {
            "mean_absolute_interaction_error_pp": 0.0,
            "mean_absolute_predicted_interaction_pp": 0.0,
            "mean_absolute_realized_interaction_pp": 0.0,
            "mean_predicted_interaction_pp": 0.0,
            "mean_realized_interaction_pp": 0.0,
            "observation_count": 0,
            "positive_realized_interaction_share": 0.0,
        }
    predicted = [float(row["predicted_interaction_pp"]) for row in rows]
    realized = [float(row["realized_interaction_pp"]) for row in rows]
    return {
        "mean_absolute_interaction_error_pp": statistics.mean(
            abs(a - b) for a, b in zip(predicted, realized, strict=True)
        ),
        "mean_absolute_predicted_interaction_pp": statistics.mean(abs(value) for value in predicted),
        "mean_absolute_realized_interaction_pp": statistics.mean(abs(value) for value in realized),
        "mean_predicted_interaction_pp": statistics.mean(predicted),
        "mean_realized_interaction_pp": statistics.mean(realized),
        "observation_count": len(rows),
        "positive_realized_interaction_share": statistics.mean(
            float(value > 0) for value in realized
        ),
    }


def evaluate_prediction_manifest(
    source_dir: str | Path,
    config: Mapping[str, Any],
    predictions: Mapping[str, Any],
    *,
    phase: str,
) -> dict[str, Any]:
    if str(predictions.get("version")) != PREDICTION_VERSION:
        raise ValueError("unsupported W9 prediction manifest version")
    if str(predictions.get("phase")) != phase:
        raise ValueError("prediction manifest phase mismatch")
    if str(predictions.get("field_sha")) != str(config["field_sha"]):
        raise ValueError("prediction manifest Field pin mismatch")
    if str(predictions.get("config_sha256")) != _sha256(config):
        raise ValueError("prediction manifest campaign config mismatch")

    manifest_copy = dict(predictions)
    manifest_sha = str(manifest_copy.pop("manifest_sha256", ""))
    if not manifest_sha or manifest_sha != _sha256(manifest_copy):
        raise ValueError("prediction manifest digest mismatch")

    expected_seeds = _expected_seeds(config, phase)
    population = load_population(source_dir, expected_seeds=expected_seeds)
    states_by_field = population.portable_by_field

    observations: list[CalibrationObservation] = []
    by_field: dict[str, list[CalibrationObservation]] = {}
    observation_rows: list[dict[str, Any]] = []
    for row in list(predictions["principal_observations"]):
        field_id = str(row["source_field_id"])
        agent_id = str(row["agent_id"])
        unavailable = frozenset(str(value) for value in row["unavailable_agent_ids"])
        realized = _realized_marginal_cost_pp(
            states_by_field[field_id],
            agent_id=agent_id,
            unavailable_agent_ids=unavailable,
            config=config,
        )
        observation = CalibrationObservation(
            source_field_id=field_id,
            agent_id=agent_id,
            unavailable_agent_ids=unavailable,
            predicted_loss_pp=float(row["predicted_loss_pp"]),
            conservative_budget_pp=float(row["conservative_budget_pp"]),
            realized_loss_pp=realized,
            evidence_refs=tuple(str(value) for value in row["evidence_refs"]),
        )
        observations.append(observation)
        by_field.setdefault(field_id, []).append(observation)
        observation_rows.append(
            {
                "agent_id": agent_id,
                "conservative_budget_pp": observation.conservative_budget_pp,
                "context_kind": str(row["context_kind"]),
                "evidence_refs": list(observation.evidence_refs),
                "prediction_error_pp": observation.prediction_error_pp,
                "predicted_loss_pp": observation.predicted_loss_pp,
                "realized_loss_pp": observation.realized_loss_pp,
                "source_field_id": field_id,
                "standard_error_pp": float(row["standard_error_pp"]),
                "unavailable_agent_ids": sorted(unavailable),
            }
        )

    thresholds = _thresholds(config)
    report = build_calibration_report(tuple(observations), thresholds=thresholds)
    field_reports = {
        field_id: build_calibration_report(tuple(rows), thresholds=thresholds).as_dict()
        for field_id, rows in sorted(by_field.items())
    }

    interaction_rows: list[dict[str, Any]] = []
    for row in list(predictions["pairwise_interactions"]):
        field_id = str(row["source_field_id"])
        agent_id = str(row["agent_id"])
        partner_id = str(row["conditioning_agent_id"])
        unconditional_realized = _realized_marginal_cost_pp(
            states_by_field[field_id],
            agent_id=agent_id,
            unavailable_agent_ids=frozenset(),
            config=config,
        )
        conditional_realized = _realized_marginal_cost_pp(
            states_by_field[field_id],
            agent_id=agent_id,
            unavailable_agent_ids=frozenset({partner_id}),
            config=config,
        )
        interaction_rows.append(
            {
                **dict(row),
                "conditional_realized_loss_pp": conditional_realized,
                "realized_interaction_pp": conditional_realized - unconditional_realized,
                "unconditional_realized_loss_pp": unconditional_realized,
            }
        )

    result = {
        "agent_count": len(population.portable_by_id),
        "calibration": report.as_dict(),
        "field_calibration": field_reports,
        "field_count": len(population.portable_by_field),
        "field_sha": str(config["field_sha"]),
        "interaction_diagnostic": _interaction_summary(interaction_rows),
        "pairwise_interactions": interaction_rows,
        "phase": phase,
        "prediction_manifest_sha256": manifest_sha,
        "principal_observations": observation_rows,
        "seeds": expected_seeds,
        "version": RESULT_VERSION,
    }
    serialized = json.dumps(result, sort_keys=True)
    if "practice_by_skill" in serialized:
        raise AssertionError("private practice leaked into W9 calibration result")
    result["result_sha256"] = _sha256(result)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare = subparsers.add_parser("prepare")
    prepare.add_argument("--phase", required=True, choices=("discovery", "replication"))
    prepare.add_argument("--source-dir", required=True, type=Path)
    prepare.add_argument("--config", required=True, type=Path)
    prepare.add_argument("--output", required=True, type=Path)

    evaluate = subparsers.add_parser("evaluate")
    evaluate.add_argument("--phase", required=True, choices=("discovery", "replication"))
    evaluate.add_argument("--source-dir", required=True, type=Path)
    evaluate.add_argument("--config", required=True, type=Path)
    evaluate.add_argument("--predictions", required=True, type=Path)
    evaluate.add_argument("--output", required=True, type=Path)

    args = parser.parse_args(argv)
    config = _read_json(args.config)
    if not isinstance(config, dict):
        raise ValueError("W9 campaign config must be an object")

    if args.command == "prepare":
        result = build_prediction_manifest(args.source_dir, config, phase=args.phase)
    else:
        predictions = _read_json(args.predictions)
        if not isinstance(predictions, dict):
            raise ValueError("W9 prediction manifest must be an object")
        result = evaluate_prediction_manifest(
            args.source_dir,
            config,
            predictions,
            phase=args.phase,
        )
    _write_json(args.output, result)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
