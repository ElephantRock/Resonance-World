def _restricted_allocation(population, offers, config, window_id=window_id):
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
