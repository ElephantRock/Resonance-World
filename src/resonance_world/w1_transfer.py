"""Deterministic W1 transfer, selection, adaptation, and replication laboratory."""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import statistics
from pathlib import Path
from typing import Any

_MODEL_FEATURES = (
    "home_success_rate",
    "bid_win_rate",
    "win_share",
    "skill_concentration",
    "skill_entropy",
    "mean_bid_confidence",
    "completed_tasks",
)


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _read_json(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain an object")
    return value


def _read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    rows = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"{path} contains a non-object JSONL row")
        rows.append(value)
    return rows


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = b"".join(_canonical_bytes(row) + b"\n" for row in rows)
    path.write_bytes(payload)
    return hashlib.sha256(payload).hexdigest()


def _uniform(*parts: object) -> float:
    payload = "|".join(str(part) for part in parts).encode("utf-8")
    raw = hashlib.sha256(payload).digest()[:8]
    return int.from_bytes(raw, "big") / 2**64


def _candidate_key(row: dict[str, Any]) -> tuple[str, str]:
    return str(row["field_id"]), str(row["agent_id"])


def _index_rows(
    candidates: list[dict[str, Any]], capsules: list[dict[str, Any]]
) -> tuple[dict[tuple[str, str], dict[str, Any]], dict[tuple[str, str], dict[str, Any]]]:
    public = {_candidate_key(row): row for row in candidates}
    private = {_candidate_key(row): row for row in capsules}
    if len(public) != len(candidates) or len(private) != len(capsules):
        raise ValueError("duplicate candidate/capsule identity")
    if set(public) != set(private):
        raise ValueError("public candidate and private capsule identities do not match")
    for row in candidates:
        if "practice_by_skill" in json.dumps(row, sort_keys=True):
            raise ValueError("private practice leaked into selector-visible candidate")
    return public, private


def _family(config: dict[str, Any], name: str) -> list[dict[str, Any]]:
    families = config.get("families")
    if not isinstance(families, dict) or name not in families:
        raise ValueError(f"unknown destination family: {name}")
    rows = families[name]
    if not isinstance(rows, list) or not rows:
        raise ValueError(f"destination family {name} must be non-empty")
    return rows


def _expected_probability(
    practice: dict[str, float | int],
    requirements: dict[str, float],
    law: dict[str, Any],
) -> float:
    weights = {str(k): float(v) for k, v in requirements.items()}
    total_weight = sum(weights.values())
    if total_weight <= 0:
        raise ValueError("destination task has no positive requirement weight")
    root_practice = sum(
        (weight / total_weight) * math.sqrt(max(0.0, float(practice.get(skill, 0.0))))
        for skill, weight in weights.items()
    )
    return min(
        float(law["maximum_success_probability"]),
        float(law["base_success_probability"])
        + float(law["practice_gain"]) * root_practice,
    )


def _evaluate_agent(
    candidate: dict[str, Any],
    capsule: dict[str, Any],
    config: dict[str, Any],
    family_name: str,
    *,
    trials: int,
    salt: str,
) -> dict[str, Any]:
    tasks = _family(config, family_name)
    law = config["destination_law"]
    practice = {
        str(key): float(value)
        for key, value in dict(capsule["practice_by_skill"]).items()
    }
    successes = 0
    expected_total = 0.0
    per_task: dict[str, list[float]] = {}
    for trial in range(trials):
        task = tasks[trial % len(tasks)]
        requirements = {str(k): float(v) for k, v in task["requirements"].items()}
        probability = _expected_probability(practice, requirements, law)
        expected_total += probability
        succeeded = _uniform(
            "resonance-world-w1",
            salt,
            candidate["field_id"],
            candidate["agent_id"],
            family_name,
            trial,
        ) < probability
        successes += int(succeeded)
        bucket = per_task.setdefault(str(task["task"]), [0.0, 0.0, 0.0])
        bucket[0] += float(succeeded)
        bucket[1] += probability
        bucket[2] += 1.0
    task_rows = {
        name: {
            "expected_success_rate": values[1] / values[2],
            "sampled_success_rate": values[0] / values[2],
            "trials": int(values[2]),
        }
        for name, values in sorted(per_task.items())
    }
    return {
        "agent_id": candidate["agent_id"],
        "checkpoint_id": candidate["checkpoint_id"],
        "expected_success_rate": expected_total / trials,
        "family": family_name,
        "field_id": candidate["field_id"],
        "sampled_success_rate": successes / trials,
        "task_results": task_rows,
        "trials": trials,
    }


def _heuristic_score(candidate: dict[str, Any]) -> float:
    features = candidate["public_features"]
    experience = min(1.0, float(features["completed_tasks"]) / 12.0)
    return (
        0.40 * float(features["home_success_rate"])
        + 0.20 * float(features["bid_win_rate"])
        + 0.10 * float(features["skill_concentration"])
        + 0.10 * (1.0 - float(features["skill_entropy"]))
        + 0.10 * experience
        + 0.10 * float(features["mean_bid_confidence"])
    )


def _group_by_field(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        result.setdefault(str(row["field_id"]), []).append(row)
    for field_rows in result.values():
        field_rows.sort(key=lambda item: str(item["agent_id"]))
    return result


def _random_groups(
    rows: list[dict[str, Any]], *, size: int, repetitions: int, salt: str
) -> list[list[dict[str, Any]]]:
    if size <= 0 or size > len(rows):
        raise ValueError("invalid random group size")
    groups = []
    for rep in range(repetitions):
        ranked = sorted(
            rows,
            key=lambda row: hashlib.sha256(
                f"{salt}|{rep}|{row['field_id']}|{row['agent_id']}".encode()
            ).hexdigest(),
        )
        groups.append(ranked[:size])
    return groups


def _selection_comparison(
    candidate_rows: list[dict[str, Any]],
    result_by_key: dict[tuple[str, str], dict[str, Any]],
    score_by_key: dict[tuple[str, str], float],
    *,
    selected_per_field: int,
    salt: str,
) -> dict[str, Any]:
    fields = _group_by_field(candidate_rows)
    field_results = []
    all_selected: list[float] = []
    all_random: list[float] = []
    for field_id, rows in sorted(fields.items()):
        selected = sorted(
            rows,
            key=lambda row: (
                score_by_key[_candidate_key(row)],
                str(row["agent_id"]),
            ),
            reverse=True,
        )[:selected_per_field]
        selected_values = [
            float(result_by_key[_candidate_key(row)]["sampled_success_rate"])
            for row in selected
        ]
        random_means = []
        for group in _random_groups(
            rows, size=selected_per_field, repetitions=256, salt=f"{salt}:{field_id}"
        ):
            random_means.append(
                statistics.mean(
                    float(result_by_key[_candidate_key(row)]["sampled_success_rate"])
                    for row in group
                )
            )
        selected_mean = statistics.mean(selected_values)
        random_mean = statistics.mean(random_means)
        all_selected.extend(selected_values)
        all_random.extend(random_means)
        field_results.append(
            {
                "field_id": field_id,
                "lift": selected_mean - random_mean,
                "random_group_mean": random_mean,
                "random_tail_probability": sum(
                    value >= selected_mean for value in random_means
                )
                / len(random_means),
                "selected_agent_ids": [row["agent_id"] for row in selected],
                "selected_mean": selected_mean,
            }
        )
    return {
        "field_results": field_results,
        "pooled_lift": statistics.mean(item["lift"] for item in field_results),
        "positive_fields": sum(item["lift"] > 0 for item in field_results),
        "selected_agent_mean": statistics.mean(all_selected),
        "random_group_mean": statistics.mean(all_random),
    }


def _feature_matrix(
    rows: list[dict[str, Any]],
) -> tuple[list[list[float]], list[float], list[float]]:
    raw = [
        [float(row["public_features"][name]) for name in _MODEL_FEATURES]
        for row in rows
    ]
    means = [statistics.mean(column) for column in zip(*raw, strict=True)]
    scales = []
    for index, mean in enumerate(means):
        values = [row[index] for row in raw]
        scale = statistics.pstdev(values)
        scales.append(scale if scale > 1e-12 else 1.0)
    standardized = [
        [1.0, *[(value - means[i]) / scales[i] for i, value in enumerate(row)]]
        for row in raw
    ]
    return standardized, means, scales


def _solve(matrix: list[list[float]], vector: list[float]) -> list[float]:
    n = len(vector)
    work = [list(matrix[i]) + [vector[i]] for i in range(n)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda row: abs(work[row][col]))
        if abs(work[pivot][col]) < 1e-12:
            raise ValueError("singular model matrix")
        work[col], work[pivot] = work[pivot], work[col]
        pivot_value = work[col][col]
        work[col] = [value / pivot_value for value in work[col]]
        for row in range(n):
            if row == col:
                continue
            factor = work[row][col]
            if abs(factor) < 1e-15:
                continue
            work[row] = [
                work[row][idx] - factor * work[col][idx]
                for idx in range(n + 1)
            ]
    return [work[i][n] for i in range(n)]


def _fit_ridge(
    rows: list[dict[str, Any]], targets: list[float], *, ridge: float = 0.25
) -> dict[str, Any]:
    x, means, scales = _feature_matrix(rows)
    width = len(x[0])
    xtx = [[0.0 for _ in range(width)] for _ in range(width)]
    xty = [0.0 for _ in range(width)]
    for vector, target in zip(x, targets, strict=True):
        for i in range(width):
            xty[i] += vector[i] * target
            for j in range(width):
                xtx[i][j] += vector[i] * vector[j]
    for i in range(1, width):
        xtx[i][i] += ridge
    weights = _solve(xtx, xty)
    return {
        "feature_means": dict(zip(_MODEL_FEATURES, means, strict=True)),
        "feature_scales": dict(zip(_MODEL_FEATURES, scales, strict=True)),
        "features": list(_MODEL_FEATURES),
        "model_type": "ridge-linear-v0.1",
        "ridge": ridge,
        "weights": weights,
    }


def _predict(candidate: dict[str, Any], model: dict[str, Any]) -> float:
    values = [1.0]
    for name in model["features"]:
        mean = float(model["feature_means"][name])
        scale = float(model["feature_scales"][name])
        values.append((float(candidate["public_features"][name]) - mean) / scale)
    return sum(float(w) * value for w, value in zip(model["weights"], values, strict=True))


def _ranks(values: list[float]) -> list[float]:
    indexed = sorted(enumerate(values), key=lambda item: item[1])
    result = [0.0] * len(values)
    start = 0
    while start < len(indexed):
        end = start + 1
        while end < len(indexed) and indexed[end][1] == indexed[start][1]:
            end += 1
        rank = (start + 1 + end) / 2.0
        for position in range(start, end):
            result[indexed[position][0]] = rank
        start = end
    return result


def _correlation(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or len(left) < 2:
        return 0.0
    left_mean = statistics.mean(left)
    right_mean = statistics.mean(right)
    numerator = sum(
        (a - left_mean) * (b - right_mean) for a, b in zip(left, right, strict=True)
    )
    left_ss = sum((value - left_mean) ** 2 for value in left)
    right_ss = sum((value - right_mean) ** 2 for value in right)
    if left_ss <= 0 or right_ss <= 0:
        return 0.0
    return numerator / math.sqrt(left_ss * right_ss)


def _spearman(left: list[float], right: list[float]) -> float:
    return _correlation(_ranks(left), _ranks(right))


def _filter_fields(rows: list[dict[str, Any]], allowed: list[str]) -> list[dict[str, Any]]:
    allowed_set = set(allowed)
    result = [row for row in rows if row["field_id"] in allowed_set]
    if {row["field_id"] for row in result} != allowed_set:
        missing = sorted(allowed_set - {row["field_id"] for row in result})
        raise ValueError(f"missing expected fields: {missing}")
    return result


def run_training(
    candidates_path: str | Path,
    capsules_path: str | Path,
    config_path: str | Path,
    destination: str | Path,
) -> dict[str, Any]:
    """Execute W1-02/W1-03 on training Fields and freeze the W1-04 model."""

    candidates = _read_jsonl(candidates_path)
    capsules = _read_jsonl(capsules_path)
    config = _read_json(config_path)
    public, private = _index_rows(candidates, capsules)
    training = _filter_fields(candidates, list(config["training_fields"]))
    trials = int(config["trials_per_agent"])
    results = [
        _evaluate_agent(
            row,
            private[_candidate_key(row)],
            config,
            "alias_a",
            trials=trials,
            salt="w1-02-training",
        )
        for row in training
    ]
    results.sort(key=lambda row: (row["field_id"], row["agent_id"]))
    result_by_key = {_candidate_key(row): row for row in results}
    heuristic_scores = {_candidate_key(row): _heuristic_score(row) for row in training}
    random_control = _selection_comparison(
        training,
        result_by_key,
        heuristic_scores,
        selected_per_field=int(config["selected_per_field"]),
        salt="w1-03-random-control",
    )
    targets = [float(result_by_key[_candidate_key(row)]["sampled_success_rate"]) for row in training]
    model = _fit_ridge(training, targets)
    model.update(
        {
            "frozen_before_discovery_holdout": True,
            "training_candidate_sha256": _sha256(
                [public[_candidate_key(row)] for row in training]
            ),
            "training_fields": list(config["training_fields"]),
            "training_outcomes_sha256": _sha256(results),
        }
    )
    model["model_sha256"] = _sha256({key: value for key, value in model.items() if key != "model_sha256"})

    destination = Path(destination)
    result_sha = _write_jsonl(destination / "w1-02-results.jsonl", results)
    _write_json(destination / "w1-03-random-control.json", random_control)
    _write_json(destination / "w1-04-frozen-model.json", model)
    summary = {
        "model_sha256": model["model_sha256"],
        "training_agent_count": len(training),
        "w1_02_results_sha256": result_sha,
        "w1_03_pooled_lift": random_control["pooled_lift"],
    }
    _write_json(destination / "training-summary.json", summary)
    return summary


def _model_scores(rows: list[dict[str, Any]], model: dict[str, Any]) -> dict[tuple[str, str], float]:
    return {_candidate_key(row): _predict(row, model) for row in rows}


def _evaluate_rows(
    rows: list[dict[str, Any]],
    private: dict[tuple[str, str], dict[str, Any]],
    config: dict[str, Any],
    family: str,
    salt: str,
) -> list[dict[str, Any]]:
    trials = int(config["trials_per_agent"])
    results = [
        _evaluate_agent(
            row,
            private[_candidate_key(row)],
            config,
            family,
            trials=trials,
            salt=salt,
        )
        for row in rows
    ]
    results.sort(key=lambda row: (row["field_id"], row["agent_id"]))
    return results


def _adapt_agent(
    candidate: dict[str, Any],
    capsule: dict[str, Any],
    config: dict[str, Any],
    *,
    family_name: str,
    trials: int,
) -> dict[str, Any]:
    tasks = _family(config, family_name)
    law = config["destination_law"]
    practice = {
        str(key): float(value)
        for key, value in dict(capsule["practice_by_skill"]).items()
    }

    def portfolio() -> float:
        return statistics.mean(
            _expected_probability(
                practice,
                {str(k): float(v) for k, v in task["requirements"].items()},
                law,
            )
            for task in tasks
        )

    initial = portfolio()
    target = min(float(law["maximum_success_probability"]), initial + 0.06)
    latency: int | None = None
    successes = 0
    trajectory = [initial]
    for trial in range(trials):
        task = tasks[trial % len(tasks)]
        requirements = {str(k): float(v) for k, v in task["requirements"].items()}
        probability = _expected_probability(practice, requirements, law)
        succeeded = _uniform(
            "resonance-world-w1-adapt",
            candidate["field_id"],
            candidate["agent_id"],
            family_name,
            trial,
        ) < probability
        successes += int(succeeded)
        total = sum(requirements.values())
        for skill, weight in requirements.items():
            practice[skill] = practice.get(skill, 0.0) + weight / total
        current = portfolio()
        trajectory.append(current)
        if latency is None and current >= target:
            latency = trial + 1
    final = trajectory[-1]
    return {
        "agent_id": candidate["agent_id"],
        "field_id": candidate["field_id"],
        "final_expected_portfolio": final,
        "improvement": final - initial,
        "initial_expected_portfolio": initial,
        "latency_to_plus_0_06": latency if latency is not None else trials + 1,
        "sampled_success_rate": successes / trials,
        "trials": trials,
    }


def run_discovery_holdout(
    candidates_path: str | Path,
    capsules_path: str | Path,
    config_path: str | Path,
    model_path: str | Path,
    campaign_config_path: str | Path,
    destination: str | Path,
) -> dict[str, Any]:
    """Execute W1-04 decision checkpoint plus W1-05/W1-06 diagnostics."""

    candidates = _read_jsonl(candidates_path)
    capsules = _read_jsonl(capsules_path)
    config = _read_json(config_path)
    model = _read_json(model_path)
    campaign_config = _read_json(campaign_config_path)
    _, private = _index_rows(candidates, capsules)
    holdout = _filter_fields(candidates, list(config["discovery_holdout_fields"]))
    scores = _model_scores(holdout, model)

    w104_results = _evaluate_rows(
        holdout, private, config, "alias_a", "w1-04-discovery-holdout"
    )
    w104_by_key = {_candidate_key(row): row for row in w104_results}
    comparison = _selection_comparison(
        holdout,
        w104_by_key,
        scores,
        selected_per_field=int(config["selected_per_field"]),
        salt="w1-04-random-baseline",
    )
    predicted = [scores[_candidate_key(row)] for row in holdout]
    actual = [float(w104_by_key[_candidate_key(row)]["sampled_success_rate"]) for row in holdout]
    rank_correlation = _spearman(predicted, actual)
    gates = campaign_config["decision_gates"]
    w104_pass = (
        comparison["pooled_lift"] >= float(gates["w1_04_min_selected_lift"])
        and rank_correlation >= float(gates["w1_04_min_rank_correlation"])
    )
    w104 = {
        "comparison": comparison,
        "model_sha256": model["model_sha256"],
        "passed": w104_pass,
        "rank_correlation": rank_correlation,
    }

    shift_rows = []
    for family in ("alias_a", "shift_25", "shift_50"):
        results = _evaluate_rows(
            holdout, private, config, family, f"w1-05:{family}"
        )
        by_key = {_candidate_key(row): row for row in results}
        comp = _selection_comparison(
            holdout,
            by_key,
            scores,
            selected_per_field=int(config["selected_per_field"]),
            salt=f"w1-05:{family}:random",
        )
        shift_rows.append(
            {
                "confirmatory": bool(w104_pass),
                "family": family,
                "pooled_lift": comp["pooled_lift"],
                "positive_fields": comp["positive_fields"],
                "selected_agent_mean": comp["selected_agent_mean"],
                "random_group_mean": comp["random_group_mean"],
            }
        )

    selected_keys = set()
    for field_id, rows in _group_by_field(holdout).items():
        selected = sorted(
            rows,
            key=lambda row: (scores[_candidate_key(row)], str(row["agent_id"])),
            reverse=True,
        )[: int(config["selected_per_field"])]
        selected_keys.update(_candidate_key(row) for row in selected)
    adaptation_rows = [
        _adapt_agent(
            row,
            private[_candidate_key(row)],
            config,
            family_name=str(config["adaptation"]["family"]),
            trials=int(config["adaptation"]["trials"]),
        )
        for row in holdout
    ]
    selected_adaptation = [
        row for row in adaptation_rows if (row["field_id"], row["agent_id"]) in selected_keys
    ]
    random_expected = statistics.mean(row["sampled_success_rate"] for row in adaptation_rows)
    w106 = {
        "confirmatory": bool(w104_pass),
        "all_agent_mean_success": random_expected,
        "selected_mean_improvement": statistics.mean(
            row["improvement"] for row in selected_adaptation
        ),
        "selected_mean_latency": statistics.mean(
            row["latency_to_plus_0_06"] for row in selected_adaptation
        ),
        "selected_mean_success": statistics.mean(
            row["sampled_success_rate"] for row in selected_adaptation
        ),
    }

    destination = Path(destination)
    _write_jsonl(destination / "w1-04-results.jsonl", w104_results)
    _write_json(destination / "w1-04-decision.json", w104)
    _write_json(destination / "w1-05-domain-shift.json", shift_rows)
    _write_jsonl(destination / "w1-06-agent-adaptation.jsonl", adaptation_rows)
    _write_json(destination / "w1-06-summary.json", w106)
    summary = {
        "model_sha256": model["model_sha256"],
        "w1_04_passed": w104_pass,
        "w1_04_pooled_lift": comparison["pooled_lift"],
        "w1_04_rank_correlation": rank_correlation,
        "w1_05_confirmatory": bool(w104_pass),
        "w1_06_confirmatory": bool(w104_pass),
    }
    _write_json(destination / "discovery-summary.json", summary)
    return summary


def run_replication(
    candidates_path: str | Path,
    capsules_path: str | Path,
    config_path: str | Path,
    model_path: str | Path,
    campaign_config_path: str | Path,
    destination: str | Path,
) -> dict[str, Any]:
    """Execute W1-07 on unseen source Fields and destination family."""

    candidates = _read_jsonl(candidates_path)
    capsules = _read_jsonl(capsules_path)
    config = _read_json(config_path)
    model = _read_json(model_path)
    campaign_config = _read_json(campaign_config_path)
    _, private = _index_rows(candidates, capsules)
    replication = _filter_fields(candidates, list(config["replication_fields"]))
    scores = _model_scores(replication, model)
    results = _evaluate_rows(
        replication, private, config, "replication_b", "w1-07-unseen-replication"
    )
    by_key = {_candidate_key(row): row for row in results}
    comparison = _selection_comparison(
        replication,
        by_key,
        scores,
        selected_per_field=int(config["selected_per_field"]),
        salt="w1-07-random-baseline",
    )
    predicted = [scores[_candidate_key(row)] for row in replication]
    actual = [float(by_key[_candidate_key(row)]["sampled_success_rate"]) for row in replication]
    rank_correlation = _spearman(predicted, actual)
    gates = campaign_config["decision_gates"]
    passed = (
        comparison["pooled_lift"] >= float(gates["w1_07_min_selected_lift"])
        and comparison["positive_fields"] >= int(gates["w1_07_min_positive_fields"])
        and rank_correlation >= float(gates["w1_07_min_rank_correlation"])
    )
    summary = {
        "comparison": comparison,
        "model_sha256": model["model_sha256"],
        "passed": passed,
        "rank_correlation": rank_correlation,
        "replication_agent_count": len(replication),
    }
    destination = Path(destination)
    _write_jsonl(destination / "w1-07-results.jsonl", results)
    _write_json(destination / "w1-07-summary.json", summary)
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    train = sub.add_parser("train")
    train.add_argument("candidates", type=Path)
    train.add_argument("capsules", type=Path)
    train.add_argument("config", type=Path)
    train.add_argument("output", type=Path)

    holdout = sub.add_parser("holdout")
    holdout.add_argument("candidates", type=Path)
    holdout.add_argument("capsules", type=Path)
    holdout.add_argument("config", type=Path)
    holdout.add_argument("model", type=Path)
    holdout.add_argument("campaign_config", type=Path)
    holdout.add_argument("output", type=Path)

    replication = sub.add_parser("replicate")
    replication.add_argument("candidates", type=Path)
    replication.add_argument("capsules", type=Path)
    replication.add_argument("config", type=Path)
    replication.add_argument("model", type=Path)
    replication.add_argument("campaign_config", type=Path)
    replication.add_argument("output", type=Path)

    args = parser.parse_args(argv)
    if args.command == "train":
        result = run_training(args.candidates, args.capsules, args.config, args.output)
    elif args.command == "holdout":
        result = run_discovery_holdout(
            args.candidates,
            args.capsules,
            args.config,
            args.model,
            args.campaign_config,
            args.output,
        )
    else:
        result = run_replication(
            args.candidates,
            args.capsules,
            args.config,
            args.model,
            args.campaign_config,
            args.output,
        )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
