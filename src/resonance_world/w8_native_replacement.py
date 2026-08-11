# ruff: noqa: E501
"""Native Field succession assay for W8-03.

World controls only the preregistered vacancy/unavailability schedule. The production
Field lifecycle runner still owns task generation, bidding, settlement, reputation,
traces, successor identities, practice updates and success outcomes.
"""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from dataclasses import replace
from pathlib import Path
from typing import Any, Mapping, Sequence


def _write_json(path: str | Path, value: Any) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _practice_vector(rows: Sequence[Mapping[str, Any]], skills: Sequence[str]) -> dict[str, int]:
    counts = Counter(str(row["required_skill"]) for row in rows)
    return {skill: int(counts.get(skill, 0)) for skill in skills}


def _cosine(first: Mapping[str, int], second: Mapping[str, int]) -> float:
    skills = sorted(set(first) | set(second))
    dot = sum(float(first.get(skill, 0)) * float(second.get(skill, 0)) for skill in skills)
    a = math.sqrt(sum(float(first.get(skill, 0)) ** 2 for skill in skills))
    b = math.sqrt(sum(float(second.get(skill, 0)) ** 2 for skill in skills))
    if a == 0 and b == 0:
        return 1.0
    if a == 0 or b == 0:
        return 0.0
    return dot / (a * b)


def _dominant_two(practice: Mapping[str, int]) -> tuple[str | None, str | None]:
    ranked = sorted(practice, key=lambda skill: (-int(practice[skill]), skill))
    positive = [skill for skill in ranked if int(practice[skill]) > 0]
    return (
        positive[0] if positive else None,
        positive[1] if len(positive) > 1 else None,
    )


def _lcs_share(first: Sequence[str], second: Sequence[str]) -> float:
    if not first and not second:
        return 1.0
    if not first or not second:
        return 0.0
    previous = [0] * (len(second) + 1)
    for left in first:
        current = [0]
        for index, right in enumerate(second, start=1):
            if left == right:
                current.append(previous[index - 1] + 1)
            else:
                current.append(max(previous[index], current[-1]))
        previous = current
    return previous[-1] / max(len(first), len(second))


def _run_one(
    *,
    connection: Any,
    source_config_path: Path,
    field_sha: str,
    target: Mapping[str, Any],
    basis_points: int,
    funded_cycles: int,
    extracted: bool,
) -> dict[str, Any]:
    # Field imports are intentionally runtime-only so ordinary World unit tests do not
    # acquire a dependency on the separately pinned Resonance Field checkout.
    from resonance.experiments import lifecycle_campaign as lc
    from resonance.experiments.lifecycle_config import (
        high_practice_environment,
        load_lifecycle_config,
    )
    from resonance.experiments.phase_boundary_campaign import reference_policy

    lifecycle_config, config_hash = load_lifecycle_config(source_config_path)
    vacancy_cycle = 72
    total_cycles = vacancy_cycle + funded_cycles
    if funded_cycles <= 0:
        raise ValueError("native replacement run requires at least one funded cycle")
    environment = high_practice_environment(
        lifecycle_config,
        cycles=total_cycles,
        shift_period=lifecycle_config.integration.environment.shift_period,
    )
    integration = replace(
        lifecycle_config.integration,
        name=f"{lifecycle_config.integration.name}-w8-replacement",
        environment=environment,
    )
    arm_name = "extracted" if extracted else "vacancy-only"
    arm = lc.LifecycleArmSpec(
        label=(
            f"w8-{arm_name}-seed{int(target['seed'])}-slot{int(target['target_slot'])}"
            f"-bp{basis_points}-cycles{funded_cycles}"
        ),
        policy=reference_policy(),
        environment=environment,
        lifecycle=lc.LifecycleSpec(mode="retirement", lifetime_cycles=9999),
        public_trace_confidence_weight=lifecycle_config.public_trace_confidence_weight,
        retrieval_top_k=lifecycle_config.retrieval_top_k,
        diversified_lineages=lifecycle_config.diversified_lineages,
        knowledge_signal_threshold=lifecycle_config.knowledge_signal_threshold,
    )
    target_slot = int(target["target_slot"])
    blocked = (
        set(int(value) for value in target.get("additional_unavailable_slots", ()))
        if extracted
        else set()
    )
    original_exit = lc.should_exit
    original_candidates = lc._candidate_slots
    original_requester = lc._requester_slot

    def targeted_exit(
        spec: Any,
        *,
        seed: int,
        cycle: int,
        slot: int,
        born_cycle: int,
    ) -> bool:
        del spec, seed, born_cycle
        return cycle == vacancy_cycle and slot == target_slot

    def available_requester(env: Any, seed: int, cycle: int) -> int:
        requester = original_requester(env, seed, cycle)
        if cycle < vacancy_cycle or requester not in blocked:
            return requester
        eligible = [slot for slot in range(env.agents) if slot not in blocked]
        return min(
            eligible,
            key=lambda slot: (lc._draw(seed, cycle, slot, "w8-requester-fill"), slot),
        )

    def available_candidates(
        seed: int,
        cycle: int,
        *,
        agents: int,
        requester_slot: int,
        count: int,
    ) -> list[int]:
        if cycle < vacancy_cycle or not blocked:
            return original_candidates(
                seed,
                cycle,
                agents=agents,
                requester_slot=requester_slot,
                count=count,
            )
        ranked = original_candidates(
            seed,
            cycle,
            agents=agents,
            requester_slot=requester_slot,
            count=agents - 1,
        )
        selected = [slot for slot in ranked if slot not in blocked][:count]
        if len(selected) != count:
            raise ValueError("W8 extraction leaves too few active candidate slots")
        return selected

    lc.should_exit = targeted_exit
    lc._candidate_slots = available_candidates
    lc._requester_slot = available_requester
    try:
        result = lc.run_lifecycle_arm(
            connection,
            config=integration,
            config_hash=config_hash,
            experiment_number=63,
            arm=arm,
            seed=int(target["seed"]),
            code_sha=field_sha,
        )
    finally:
        lc.should_exit = original_exit
        lc._candidate_slots = original_candidates
        lc._requester_slot = original_requester

    run_id = str(result["run_id"])
    event = connection.execute(
        """
        SELECT agent_id, successor_agent_id, cycle, slot
        FROM lifecycle_events
        WHERE run_id = %s AND slot = %s
        ORDER BY cycle
        """,
        (run_id, target_slot),
    ).fetchone()
    if event is None:
        raise ValueError("targeted native vacancy failed to create a successor")
    predecessor_id = str(event["agent_id"])
    successor_id = str(event["successor_agent_id"])
    rows = connection.execute(
        """
        SELECT cycle, required_skill, winner_agent_id, winner_slot, success
        FROM integration_campaign_outcomes
        WHERE run_id = %s
        ORDER BY cycle
        """,
        (run_id,),
    ).fetchall()
    rows = [dict(row) for row in rows]
    skills = list(environment.domains)
    predecessor_rows = [
        row
        for row in rows
        if int(row["cycle"]) < vacancy_cycle
        and str(row["winner_agent_id"]) == predecessor_id
    ]
    successor_rows = [
        row
        for row in rows
        if int(row["cycle"]) >= vacancy_cycle
        and str(row["winner_agent_id"]) == successor_id
    ]
    predecessor_practice = _practice_vector(predecessor_rows, skills)
    successor_practice = _practice_vector(successor_rows, skills)
    predecessor_success_sequence = [
        str(row["required_skill"]) for row in predecessor_rows if bool(row["success"])
    ]
    successor_success_sequence = [
        str(row["required_skill"]) for row in successor_rows if bool(row["success"])
    ]
    source_target = {
        str(skill): int(value)
        for skill, value in dict(target["source_target_practice_by_skill"]).items()
    }
    predecessor_dom = _dominant_two(predecessor_practice)
    successor_dom = _dominant_two(successor_practice)
    source_dom = _dominant_two(source_target)
    state = {
        "agent_id": successor_id,
        "home_field_id": str(target["field_id"]),
        "practice_by_skill": successor_practice,
        "evidence_refs": [
            f"field://{field_sha}/w8-native-replacement/{run_id}",
            f"world://w8/replacement/{arm_name}/bp{basis_points}",
        ],
    }
    return {
        "run_id": run_id,
        "arm": arm_name,
        "basis_points": basis_points,
        "funded_cycles": funded_cycles,
        "target_slot": target_slot,
        "blocked_slots": sorted(blocked),
        "predecessor_agent_id": predecessor_id,
        "successor_agent_id": successor_id,
        "predecessor_practice_by_skill": predecessor_practice,
        "successor_practice_by_skill": successor_practice,
        "source_target_practice_by_skill": source_target,
        "source_target_vs_assay_predecessor_cosine": _cosine(
            source_target, predecessor_practice
        ),
        "successor_vs_source_target_cosine": _cosine(successor_practice, source_target),
        "successor_vs_assay_predecessor_cosine": _cosine(
            successor_practice, predecessor_practice
        ),
        "dominant_match_to_source": successor_dom[0] == source_dom[0],
        "secondary_match_to_source": successor_dom[1] == source_dom[1],
        "predecessor_successful_sequence": predecessor_success_sequence,
        "successor_successful_sequence": successor_success_sequence,
        "successful_sequence_lcs_share": _lcs_share(
            predecessor_success_sequence,
            successor_success_sequence,
        ),
        "successor_state": state,
        "field_invariants": result["invariants"],
    }


def run_assay(
    *,
    dsn: str,
    source_config_path: str | Path,
    plan_path: str | Path,
    campaign_config_path: str | Path,
    output_path: str | Path,
) -> dict[str, Any]:
    import psycopg

    plan = json.loads(Path(plan_path).read_text(encoding="utf-8"))
    campaign = json.loads(Path(campaign_config_path).read_text(encoding="utf-8"))
    field_sha = str(campaign["field_sha"])
    dividend = dict(campaign["dividend"])
    basis_values = [
        int(value)
        for value in (
            dividend["sensitivity_basis_points"][0],
            dividend["primary_basis_points"],
            dividend["sensitivity_basis_points"][1],
        )
    ]
    basis_values = list(dict.fromkeys(basis_values))
    cost_per_cycle = int(dividend["development_credit_per_cycle"])
    if cost_per_cycle <= 0:
        raise ValueError("development_credit_per_cycle must be positive")

    result: dict[str, Any] = {
        "status": "completed",
        "field_sha": field_sha,
        "phase": str(plan["phase"]),
        "basis_points": {},
    }
    with psycopg.connect(dsn, autocommit=True) as connection:
        connection.row_factory = psycopg.rows.dict_row
        for basis_points in basis_values:
            field_rows: list[dict[str, Any]] = []
            for target in plan["targets"]:
                total_price = sum(int(value) for value in target["contract_prices"])
                dividend_amount = total_price * basis_points // 10_000
                funded_cycles = dividend_amount // cost_per_cycle
                row: dict[str, Any] = {
                    "field_id": str(target["field_id"]),
                    "seed": int(target["seed"]),
                    "target_agent_id": str(target["target_agent_id"]),
                    "target_slot": int(target["target_slot"]),
                    "additional_unavailable_slots": list(
                        target["additional_unavailable_slots"]
                    ),
                    "contract_price_total": total_price,
                    "dividend_amount": dividend_amount,
                    "funded_cycles": funded_cycles,
                }
                if funded_cycles <= 0:
                    row["status"] = "no_funded_replacement_development"
                    row["extracted_successor_state"] = None
                    row["vacancy_only_successor_state"] = None
                    field_rows.append(row)
                    continue
                vacancy = _run_one(
                    connection=connection,
                    source_config_path=Path(source_config_path),
                    field_sha=field_sha,
                    target=target,
                    basis_points=basis_points,
                    funded_cycles=funded_cycles,
                    extracted=False,
                )
                extracted = _run_one(
                    connection=connection,
                    source_config_path=Path(source_config_path),
                    field_sha=field_sha,
                    target=target,
                    basis_points=basis_points,
                    funded_cycles=funded_cycles,
                    extracted=True,
                )
                row.update(
                    {
                        "status": "native_successor_developed",
                        "vacancy_only": vacancy,
                        "extracted": extracted,
                        "vacancy_only_successor_state": vacancy["successor_state"],
                        "extracted_successor_state": extracted["successor_state"],
                        "extracted_vs_vacancy_successor_cosine": _cosine(
                            extracted["successor_practice_by_skill"],
                            vacancy["successor_practice_by_skill"],
                        ),
                        "extracted_vs_vacancy_cosine_distance": 1.0
                        - _cosine(
                            extracted["successor_practice_by_skill"],
                            vacancy["successor_practice_by_skill"],
                        ),
                    }
                )
                field_rows.append(row)
            developed = [
                row
                for row in field_rows
                if row.get("status") == "native_successor_developed"
            ]
            result["basis_points"][str(basis_points)] = {
                "fields": field_rows,
                "developed_fields": len(developed),
                "mean_extracted_vs_vacancy_cosine_distance": (
                    sum(
                        float(row["extracted_vs_vacancy_cosine_distance"])
                        for row in developed
                    )
                    / len(developed)
                    if developed
                    else 0.0
                ),
                "mean_successor_vs_source_target_cosine": (
                    sum(
                        float(row["extracted"]["successor_vs_source_target_cosine"])
                        for row in developed
                    )
                    / len(developed)
                    if developed
                    else 0.0
                ),
                "dominant_match_share": (
                    sum(bool(row["extracted"]["dominant_match_to_source"]) for row in developed)
                    / len(developed)
                    if developed
                    else 0.0
                ),
                "mean_successful_sequence_lcs_share": (
                    sum(
                        float(row["extracted"]["successful_sequence_lcs_share"])
                        for row in developed
                    )
                    / len(developed)
                    if developed
                    else 0.0
                ),
            }
    _write_json(output_path, result)
    return result


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dsn", required=True)
    parser.add_argument("--source-config", required=True)
    parser.add_argument("--plan", required=True)
    parser.add_argument("--campaign-config", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    result = run_assay(
        dsn=args.dsn,
        source_config_path=args.source_config,
        plan_path=args.plan,
        campaign_config_path=args.campaign_config,
        output_path=args.output,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
