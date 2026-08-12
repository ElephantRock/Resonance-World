"""W9-04 factorial identification of coalition mechanisms."""

from __future__ import annotations

import argparse
import itertools
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from .w8_campaign import (
    W8Population,
    _generate_offers,
    _mean,
    _mission,
    _standalone_structured_rate,
    _structured_expected,
    _structured_rate,
    _unrestricted_allocation,
    load_population,
)

FACTORS = ("D", "R", "C", "V")
RESULT_VERSION = "w9-04-coalition-factorial-result-v0.1"


@dataclass(frozen=True, slots=True)
class SelectedPair:
    first: Any
    second: Any
    selection_score: float
    diversity_fallback: bool


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


def _condition_key(bits: Mapping[str, bool]) -> str:
    return "".join(f"{factor}{int(bool(bits[factor]))}" for factor in FACTORS)


def _conditions() -> tuple[dict[str, bool], ...]:
    return tuple(
        dict(zip(FACTORS, values, strict=True))
        for values in itertools.product((False, True), repeat=len(FACTORS))
    )


def _subset_population(population: W8Population, field_ids: set[str]) -> W8Population:
    candidates = tuple(
        row for row in population.candidates if str(row["field_id"]) in field_ids
    )
    states = {
        agent_id: state
        for agent_id, state in population.portable_by_id.items()
        if state.home_field_id in field_ids
    }
    by_field = {
        field_id: rows
        for field_id, rows in population.portable_by_field.items()
        if field_id in field_ids
    }
    if not candidates or not states:
        raise ValueError("diagnostic population cannot be empty")
    return W8Population(
        candidates=candidates,
        portable_by_id=states,
        portable_by_field=by_field,
        source_fields=tuple(
            row
            for row in population.source_fields
            if str(row.get("field_id", "")) in field_ids
        ),
    )


def _selection_structure(true_structure: str, decomposition: bool) -> str:
    if decomposition:
        return true_structure
    return "nondecomposable"


def _select_pair(
    first_roster: Sequence[Any],
    second_roster: Sequence[Any],
    mission: Any,
    config: Mapping[str, Any],
    *,
    true_structure: str,
    decomposition: bool,
    role_specialization: bool,
    diversity: bool,
) -> SelectedPair | None:
    pairs = [
        (first, second)
        for first in first_roster
        for second in second_roster
        if first.agent_id != second.agent_id
    ]
    if not pairs:
        return None
    fallback = False
    if diversity:
        cross_source = [
            pair for pair in pairs if pair[0].home_field_id != pair[1].home_field_id
        ]
        if cross_source:
            pairs = cross_source
        else:
            fallback = True

    structure = _selection_structure(true_structure, decomposition)
    scored: list[tuple[float, str, str, Any, Any]] = []
    for first, second in pairs:
        first_individual = first.to_individual()
        second_individual = second.to_individual()
        fixed = _structured_expected(
            first_individual,
            second_individual,
            mission,
            config,
            structure=structure,
        )
        if role_specialization:
            score = fixed
        else:
            swapped = _structured_expected(
                second_individual,
                first_individual,
                mission,
                config,
                structure=structure,
            )
            score = 0.5 * (fixed + swapped)
        scored.append((score, first.agent_id, second.agent_id, first, second))
    best = min(scored, key=lambda row: (-row[0], row[1], row[2]))
    return SelectedPair(best[3], best[4], float(best[0]), fallback)


def _execute_condition(
    market: Any,
    config: Mapping[str, Any],
    *,
    phase: str,
    cohort_id: str,
    window_id: str,
    bits: Mapping[str, bool],
) -> dict[str, Any]:
    mission_rows: list[dict[str, Any]] = []
    for row in config["coalition_missions"]:
        coalition_id = str(row["coalition_id"])
        true_structure = str(row["structure"])
        lead_org = str(row["lead_organization_id"])
        support_org = str(row["support_organization_id"])
        mission = _mission(dict(row["mission"]))
        lead_states = list(market.contracted_agents(lead_org, window_id))
        support_states = list(market.contracted_agents(support_org, window_id))
        lead_roster = [state.to_individual() for state in lead_states]
        support_roster = [state.to_individual() for state in support_states]
        salt = f"w9-04:{phase}:{cohort_id}:{coalition_id}"
        pair = _select_pair(
            lead_states,
            support_states,
            mission,
            config,
            true_structure=true_structure,
            decomposition=bool(bits["D"]),
            role_specialization=bool(bits["R"]),
            diversity=bool(bits["V"]),
        )
        if pair is None:
            success = 0.0
            swap_bit = 0
            lead_id = None
            support_id = None
            fallback = False
            selection_score = 0.0
        else:
            lead = pair.first.to_individual()
            support = pair.second.to_individual()
            swap_bit = 0
            if bool(bits["C"]):
                fixed = _structured_expected(
                    lead,
                    support,
                    mission,
                    config,
                    structure=true_structure,
                )
                swapped = _structured_expected(
                    support,
                    lead,
                    mission,
                    config,
                    structure=true_structure,
                )
                if swapped > fixed:
                    lead, support = support, lead
                    swap_bit = 1
            success = _structured_rate(
                lead,
                support,
                mission,
                config,
                structure=true_structure,
                seed_salt=salt,
            )
            lead_id, support_id = lead.agent_id, support.agent_id
            fallback = pair.diversity_fallback
            selection_score = pair.selection_score

        standalone = max(
            _standalone_structured_rate(
                lead_roster,
                mission,
                config,
                structure=true_structure,
                seed_salt=salt,
            ),
            _standalone_structured_rate(
                support_roster,
                mission,
                config,
                structure=true_structure,
                seed_salt=salt,
            ),
        )
        mission_rows.append(
            {
                "best_standalone_success": standalone,
                "coalition_effect_vs_standalone": success - standalone,
                "coalition_id": coalition_id,
                "diversity_fallback": fallback,
                "lead_agent_id": lead_id,
                "selection_score": selection_score,
                "structure": true_structure,
                "success": success,
                "support_agent_id": support_id,
                "swap_bit": swap_bit,
            }
        )
    return {
        "bits": {factor: bool(bits[factor]) for factor in FACTORS},
        "condition": _condition_key(bits),
        "diversity_fallback_count": sum(bool(row["diversity_fallback"]) for row in mission_rows),
        "mean_coalition_effect_vs_standalone": _mean(
            [float(row["coalition_effect_vs_standalone"]) for row in mission_rows]
        ),
        "mean_success": _mean([float(row["success"]) for row in mission_rows]),
        "mission_results": mission_rows,
        "swap_bit_count": sum(int(row["swap_bit"]) for row in mission_rows),
    }


def _run_factorial(
    population: W8Population,
    config: Mapping[str, Any],
    *,
    phase: str,
    cohort_id: str,
) -> dict[str, Any]:
    window_id = f"w9-04:{phase}:{cohort_id}"
    offers = _generate_offers(population, config, window_id=window_id)
    market = _unrestricted_allocation(population, offers, config, window_id=window_id)
    rows = [
        _execute_condition(
            market,
            config,
            phase=phase,
            cohort_id=cohort_id,
            window_id=window_id,
            bits=bits,
        )
        for bits in _conditions()
    ]
    return {
        "cohort_id": cohort_id,
        "condition_results": rows,
        "offer_count": len(offers),
    }


def _condition_map(factorial: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {
        str(row["condition"]): row for row in factorial["condition_results"]
    }


def _mission_rate(row: Mapping[str, Any], mission_index: int) -> float:
    return float(row["mission_results"][mission_index]["success"])


def _main_effects(factorial: Mapping[str, Any], config: Mapping[str, Any]) -> dict[str, Any]:
    rows = _condition_map(factorial)
    missions = list(config["coalition_missions"])
    effects: dict[str, Any] = {}
    for factor in FACTORS:
        contrasts: list[float] = []
        by_mission: list[list[float]] = [[] for _ in missions]
        for bits in _conditions():
            if bits[factor]:
                continue
            off = dict(bits)
            on = dict(bits)
            on[factor] = True
            off_row = rows[_condition_key(off)]
            on_row = rows[_condition_key(on)]
            for index in range(len(missions)):
                delta = (_mission_rate(on_row, index) - _mission_rate(off_row, index)) * 100.0
                contrasts.append(delta)
                by_mission[index].append(delta)
        mission_effects = {
            str(missions[index]["coalition_id"]): _mean(values)
            for index, values in enumerate(by_mission)
        }
        effects[factor] = {
            "main_effect_pp": _mean(contrasts),
            "mission_effects_pp": mission_effects,
            "positive_missions": sum(value > 0 for value in mission_effects.values()),
        }
    return effects


def _two_way_interactions(
    factorial: Mapping[str, Any],
    config: Mapping[str, Any],
) -> dict[str, Any]:
    rows = _condition_map(factorial)
    missions = list(config["coalition_missions"])
    results: dict[str, Any] = {}
    for first_index, first in enumerate(FACTORS):
        for second in FACTORS[first_index + 1 :]:
            other = [factor for factor in FACTORS if factor not in {first, second}]
            by_mission: list[list[float]] = [[] for _ in missions]
            for other_values in itertools.product((False, True), repeat=2):
                base = dict.fromkeys(FACTORS, False)
                for factor, value in zip(other, other_values, strict=True):
                    base[factor] = value
                cells: dict[tuple[bool, bool], Mapping[str, Any]] = {}
                for a, b in itertools.product((False, True), repeat=2):
                    bits = dict(base)
                    bits[first], bits[second] = a, b
                    cells[(a, b)] = rows[_condition_key(bits)]
                for mission_index in range(len(missions)):
                    interaction = (
                        _mission_rate(cells[(True, True)], mission_index)
                        - _mission_rate(cells[(True, False)], mission_index)
                        - _mission_rate(cells[(False, True)], mission_index)
                        + _mission_rate(cells[(False, False)], mission_index)
                    ) * 100.0
                    by_mission[mission_index].append(interaction)
            mission_effects = {
                str(missions[index]["coalition_id"]): _mean(values)
                for index, values in enumerate(by_mission)
            }
            key = f"{first}:{second}"
            results[key] = {
                "interaction_pp": _mean(list(mission_effects.values())),
                "mission_interactions_pp": mission_effects,
                "positive_missions": sum(value > 0 for value in mission_effects.values()),
            }
    return results


def _diagnostic_field_pairs(population: W8Population, seeds: Sequence[int]) -> list[tuple[str, set[str]]]:
    field_ids = [f"w4-source-seed-{int(seed)}" for seed in seeds]
    missing = set(field_ids) - set(population.portable_by_field)
    if missing:
        raise ValueError(f"missing W9-04 source Fields: {sorted(missing)}")
    return [
        (
            f"field-pair-{seeds[index]}-{seeds[(index + 1) % len(seeds)]}",
            {field_ids[index], field_ids[(index + 1) % len(field_ids)]},
        )
        for index in range(len(field_ids))
    ]


def run_w9_04(
    population: W8Population,
    config: Mapping[str, Any],
    *,
    phase: str,
) -> dict[str, Any]:
    seeds = _phase_seeds(config, phase)
    pooled = _run_factorial(population, config, phase=phase, cohort_id="pooled")
    pooled_effects = _main_effects(pooled, config)
    interactions = _two_way_interactions(pooled, config)

    diagnostics: dict[str, Any] = {}
    field_effects: dict[str, dict[str, float]] = {factor: {} for factor in FACTORS}
    for cohort_id, field_ids in _diagnostic_field_pairs(population, seeds):
        subset = _subset_population(population, field_ids)
        factorial = _run_factorial(subset, config, phase=phase, cohort_id=cohort_id)
        effects = _main_effects(factorial, config)
        diagnostics[cohort_id] = {
            "field_ids": sorted(field_ids),
            "main_effects": effects,
        }
        for factor in FACTORS:
            field_effects[factor][cohort_id] = float(effects[factor]["main_effect_pp"])

    selected: list[str] = []
    factor_results: dict[str, Any] = {}
    for factor in FACTORS:
        primary = pooled_effects[factor]
        field_values = field_effects[factor]
        gate = (
            float(primary["main_effect_pp"]) > float(config["factor_main_effect_gate_pp"])
            and int(primary["positive_missions"])
            >= int(config["factor_required_positive_missions"])
            and sum(value > 0 for value in field_values.values())
            >= int(config["factor_required_positive_fields"])
        )
        if gate:
            selected.append(factor)
        factor_results[factor] = {
            **dict(primary),
            "field_effects_pp": field_values,
            "positive_fields": sum(value > 0 for value in field_values.values()),
            "selected_for_K": gate,
        }

    interaction_results: dict[str, Any] = {}
    for key, row in interactions.items():
        material = (
            float(row["interaction_pp"]) > float(config["interaction_gate_pp"])
            and int(row["positive_missions"])
            >= int(config["interaction_required_positive_missions"])
        )
        interaction_results[key] = {**dict(row), "material_positive": material}

    return {
        "K": selected if selected else ["none"],
        "diagnostic_field_pair_results": diagnostics,
        "factor_results": factor_results,
        "interaction_results": interaction_results,
        "phase": phase,
        "pooled_factorial": pooled,
        "version": RESULT_VERSION,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", required=True, choices=("discovery", "replication"))
    parser.add_argument("--source-dir", required=True, type=Path)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    config = _read_json(args.config)
    if not isinstance(config, dict):
        raise ValueError("W9 coalition config must be an object")
    population = load_population(args.source_dir, expected_seeds=_phase_seeds(config, args.phase))
    result = run_w9_04(population, config, phase=args.phase)
    _write_json(args.output, result)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())