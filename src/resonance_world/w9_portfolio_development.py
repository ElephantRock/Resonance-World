"""W9-03 native Field portfolio-development planning and execution.

Portfolio targets are selected from pre-development public evidence only. During the
additional native Field cycles World changes only the required-skill demand schedule;
requesters, candidates, bids, settlement, success, evidence, traces, and the identity
that develops remain owned by the pinned Field implementation.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import replace
from pathlib import Path
from typing import Any, Mapping

from .w9_calibration_execution import (
    _load_public_population,
    _public_skill_probability,
)

PLAN_VERSION = "w9-03-portfolio-plan-v0.1"
RUN_VERSION = "w9-03-portfolio-development-runs-v0.1"


def _read_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _write_json(path: str | Path, value: object) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _phase_seeds(config: Mapping[str, Any], phase: str) -> list[int]:
    key = f"{phase}_seeds"
    if key not in config:
        raise ValueError(f"unsupported W9 phase: {phase}")
    return [int(value) for value in config[key]]


def build_portfolio_plan(
    source_dir: str | Path,
    config: Mapping[str, Any],
    *,
    phase: str,
) -> dict[str, Any]:
    """Select under-covered mission strata without reading private Field state."""

    seeds = _phase_seeds(config, phase)
    candidates, by_field, candidate_sha256 = _load_public_population(
        source_dir,
        expected_seeds=seeds,
    )
    skills = [str(row["skill"]) for row in config["home_service_missions"]]
    target_count = int(config["portfolio_target_strata"])
    if target_count <= 0 or target_count > len(skills):
        raise ValueError("portfolio target count outside frozen mission-stratum range")
    probability_threshold = float(config["diagnostic_probability_threshold"])

    fields: list[dict[str, Any]] = []
    for field_id in sorted(by_field):
        rows = by_field[field_id]
        diagnostics: list[dict[str, Any]] = []
        for skill in skills:
            probabilities = sorted(
                (
                    _public_skill_probability(row, skill, config)
                    for row in rows
                ),
                reverse=True,
            )
            if len(probabilities) < 2:
                raise ValueError("portfolio redundancy requires at least two source agents")
            best, second = probabilities[0], probabilities[1]
            qualifying = sum(value >= probability_threshold for value in probabilities)
            diagnostics.append(
                {
                    "best_probability": best,
                    "diagnostic_redundancy_ratio": float(qualifying),
                    "qualifying_agent_count": qualifying,
                    "redundancy_gap_pp": (best - second) * 100.0,
                    "second_probability": second,
                    "skill": skill,
                }
            )
        ranked = sorted(
            diagnostics,
            key=lambda row: (-float(row["redundancy_gap_pp"]), str(row["skill"])),
        )
        seed_text = field_id.rsplit("-", 1)[-1]
        fields.append(
            {
                "field_id": field_id,
                "seed": int(seed_text),
                "selected_strata": [str(row["skill"]) for row in ranked[:target_count]],
                "strata": sorted(diagnostics, key=lambda row: str(row["skill"])),
            }
        )

    result = {
        "agent_count": len(candidates),
        "candidate_sha256": candidate_sha256,
        "field_count": len(fields),
        "fields": fields,
        "phase": phase,
        "seeds": seeds,
        "version": PLAN_VERSION,
    }
    if "practice_by_skill" in json.dumps(result, sort_keys=True):
        raise AssertionError("private practice leaked into W9 portfolio plan")
    return result


def _run_arm(
    *,
    connection: Any,
    lifecycle_config: Any,
    config_hash: str,
    campaign_config: Mapping[str, Any],
    field_sha: str,
    seed: int,
    mode: str,
    selected_strata: tuple[str, ...],
) -> dict[str, Any]:
    from resonance.experiments import lifecycle_campaign as lc
    from resonance.experiments.lifecycle_config import high_practice_environment
    from resonance.experiments.phase_boundary_campaign import reference_policy

    if mode not in {"portfolio", "matched-compute-control"}:
        raise ValueError(f"unsupported development mode: {mode}")
    base_cycles = int(campaign_config["base_source_cycles"])
    development_cycles = int(campaign_config["development_cycles"])
    total_cycles = base_cycles + development_cycles
    environment = high_practice_environment(
        lifecycle_config,
        cycles=total_cycles,
        shift_period=lifecycle_config.integration.environment.shift_period,
    )
    integration = replace(
        lifecycle_config.integration,
        name=str(campaign_config["development_campaign_name"]),
        environment=environment,
    )
    arm_label = (
        f"w9-portfolio-seed{seed}"
        if mode == "portfolio"
        else f"w9-compute-control-seed{seed}"
    )
    arm = lc.LifecycleArmSpec(
        label=arm_label,
        policy=reference_policy(),
        environment=environment,
        lifecycle=lc.LifecycleSpec(mode="immortal"),
        public_trace_confidence_weight=lifecycle_config.public_trace_confidence_weight,
        retrieval_top_k=lifecycle_config.retrieval_top_k,
        diversified_lineages=lifecycle_config.diversified_lineages,
        knowledge_signal_threshold=lifecycle_config.knowledge_signal_threshold,
    )

    original_domain_index = lc._domain_index
    domains = tuple(str(value) for value in environment.domains)
    if any(skill not in domains for skill in selected_strata):
        raise ValueError("portfolio plan contains a skill outside the pinned Field domains")

    def portfolio_domain_index(*args: object) -> int:
        """Preserve Field domain selection except for the frozen extra-cycle schedule.

        The pinned lifecycle runner calls ``_domain_index(seed, cycle, domain_count)``.
        Some Field invariant helpers bind the imported symbol as a unary cycle callback;
        support that equivalent calling convention using this arm's already-frozen seed
        and domain count. Both paths resolve to the same deterministic domain index.
        """

        if len(args) == 3:
            seed_value = int(args[0])
            cycle = int(args[1])
            domain_count = int(args[2])
        elif len(args) == 1:
            seed_value = seed
            cycle = int(args[0])
            domain_count = len(domains)
        else:
            raise TypeError(
                "W9 portfolio domain hook expects cycle or (seed, cycle, domain_count)"
            )
        if cycle < base_cycles or mode != "portfolio":
            return original_domain_index(seed_value, cycle, domain_count)
        target_skill = selected_strata[(cycle - base_cycles) % len(selected_strata)]
        target_index = domains.index(target_skill)
        regime = cycle // environment.shift_period
        return (target_index - regime) % domain_count

    lc._domain_index = portfolio_domain_index
    try:
        result = lc.run_lifecycle_arm(
            connection,
            config=integration,
            config_hash=config_hash,
            experiment_number=63,
            arm=arm,
            seed=seed,
            code_sha=field_sha,
        )
    finally:
        lc._domain_index = original_domain_index

    return {
        "arm_label": arm_label,
        "development_cycles": development_cycles,
        "mode": mode,
        "run_id": str(result["run_id"]),
        "seed": seed,
        "selected_strata": list(selected_strata),
        "field_invariants": result["invariants"],
    }


def execute_portfolio_development(
    *,
    dsn: str,
    source_config_path: str | Path,
    campaign_config: Mapping[str, Any],
    plan: Mapping[str, Any],
) -> dict[str, Any]:
    """Execute portfolio and matched-compute native Field arms."""

    import psycopg
    from resonance.experiments.lifecycle_config import load_lifecycle_config

    if str(plan.get("version")) != PLAN_VERSION:
        raise ValueError("unsupported W9 portfolio plan version")
    phase = str(plan["phase"])
    expected_seeds = _phase_seeds(campaign_config, phase)
    if [int(value) for value in plan["seeds"]] != expected_seeds:
        raise ValueError("portfolio plan seed mismatch")

    lifecycle_config, config_hash = load_lifecycle_config(Path(source_config_path))
    field_sha = str(campaign_config["field_sha"])
    rows: list[dict[str, Any]] = []
    with psycopg.connect(dsn, autocommit=True) as connection:
        connection.row_factory = psycopg.rows.dict_row
        for field in sorted(plan["fields"], key=lambda row: int(row["seed"])):
            seed = int(field["seed"])
            selected = tuple(str(value) for value in field["selected_strata"])
            for mode in ("matched-compute-control", "portfolio"):
                rows.append(
                    _run_arm(
                        connection=connection,
                        lifecycle_config=lifecycle_config,
                        config_hash=config_hash,
                        campaign_config=campaign_config,
                        field_sha=field_sha,
                        seed=seed,
                        mode=mode,
                        selected_strata=selected,
                    )
                )
    return {
        "development_compute_units_per_field": int(
            campaign_config["development_resident_agent_cycle_units_per_field"]
        ),
        "development_tasks_per_field": int(campaign_config["development_cycles"]),
        "field_sha": field_sha,
        "phase": phase,
        "runs": rows,
        "version": RUN_VERSION,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    plan_parser = subparsers.add_parser("plan")
    plan_parser.add_argument("--phase", required=True, choices=("discovery", "replication"))
    plan_parser.add_argument("--source-dir", required=True, type=Path)
    plan_parser.add_argument("--config", required=True, type=Path)
    plan_parser.add_argument("--output", required=True, type=Path)

    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("--dsn", required=True)
    run_parser.add_argument("--source-config", required=True, type=Path)
    run_parser.add_argument("--config", required=True, type=Path)
    run_parser.add_argument("--plan", required=True, type=Path)
    run_parser.add_argument("--output", required=True, type=Path)

    args = parser.parse_args(argv)
    config = _read_json(args.config)
    if not isinstance(config, dict):
        raise ValueError("W9 portfolio config must be an object")
    if args.command == "plan":
        result = build_portfolio_plan(args.source_dir, config, phase=args.phase)
    else:
        plan = _read_json(args.plan)
        if not isinstance(plan, dict):
            raise ValueError("W9 portfolio plan must be an object")
        result = execute_portfolio_development(
            dsn=args.dsn,
            source_config_path=args.source_config,
            campaign_config=config,
            plan=plan,
        )
    _write_json(args.output, result)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
