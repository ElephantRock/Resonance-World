"""W9-02 mission-level leasing and switching-cost sensitivity."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from .w6_mobility import PortableAgentState
from .w8_campaign import (
    W8Population,
    _generate_offers,
    _market_rosters,
    _mean,
    _organization_mission,
    _source_frontier,
    _source_probability,
    _trial_rate,
    _unrestricted_allocation,
    load_population,
)
from .w8_regulation import CirculationSchedule

RESULT_VERSION = "w9-02-mission-leasing-result-v0.1"


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


def _source_slot_counts(config: Mapping[str, Any]) -> tuple[int, ...]:
    slots = int(config["source_slots_per_window"])
    missions = list(config["home_service_missions"])
    if slots != len(missions):
        raise ValueError("source slot count must equal frozen home mission count")
    counts = [0] * slots
    for trial in range(int(config["service_trials"])):
        counts[trial % slots] += 1
    return tuple(counts)


def _source_value_with_unavailability(
    states: Sequence[PortableAgentState],
    config: Mapping[str, Any],
    *,
    unavailable_by_slot: Mapping[int, set[str]],
) -> float:
    if not states:
        return 0.0
    missions = list(config["home_service_missions"])
    counts = _source_slot_counts(config)
    total = 0.0
    trials = int(config["service_trials"])
    for slot, count in enumerate(counts):
        unavailable = unavailable_by_slot.get(slot, set())
        available = [state for state in states if state.agent_id not in unavailable]
        if not available:
            continue
        skill = str(missions[slot]["skill"])
        total += count * max(_source_probability(state, skill, config) for state in available)
    return total / trials


def _pair_continuity(history: Sequence[tuple[str, str] | None]) -> float:
    pairs = [
        (first, second)
        for first, second in zip(history, history[1:], strict=False)
        if first is not None and second is not None
    ]
    return _mean([float(first == second) for first, second in pairs]) if pairs else 0.0


def _whole_window_external_ids(
    rosters: Mapping[str, Sequence[str]],
    config: Mapping[str, Any],
    *,
    window: int,
    mode: str,
) -> set[str]:
    if mode == "permanent":
        return {agent_id for roster in rosters.values() for agent_id in roster}
    if mode != "4:2":
        return set()
    rule = dict(config["w8_4_2"])
    schedule = CirculationSchedule(
        int(rule["external_windows"]),
        int(rule["home_windows"]),
    )
    offsets = [int(value) for value in rule["roster_offsets"]]
    external: set[str] = set()
    for roster in rosters.values():
        for index, agent_id in enumerate(sorted(roster)):
            if schedule.phase(window + offsets[index % len(offsets)]) == "external":
                external.add(agent_id)
    return external


def _organization_available_ids(
    rosters: Mapping[str, Sequence[str]],
    config: Mapping[str, Any],
    *,
    window: int,
    mode: str,
) -> dict[str, list[str]]:
    if mode in {"lease-zero-recovery", "lease-one-window-recovery", "permanent"}:
        return {org_id: list(roster) for org_id, roster in rosters.items()}
    external = _whole_window_external_ids(rosters, config, window=window, mode=mode)
    return {
        org_id: [agent_id for agent_id in roster if agent_id in external]
        for org_id, roster in rosters.items()
    }


def _base_source_unavailability(
    rosters: Mapping[str, Sequence[str]],
    config: Mapping[str, Any],
    *,
    window: int,
    mode: str,
) -> dict[int, set[str]]:
    slots = int(config["source_slots_per_window"])
    unavailable = {slot: set() for slot in range(slots)}
    if mode in {"permanent", "4:2"}:
        external = _whole_window_external_ids(rosters, config, window=window, mode=mode)
        for slot in unavailable:
            unavailable[slot].update(external)
        return unavailable
    lease_slots = {
        str(org_id): int(slot)
        for org_id, slot in dict(config["lease_organization_slots"]).items()
    }
    for org_id, roster in rosters.items():
        slot = lease_slots[org_id]
        unavailable[slot].update(roster)
    return unavailable


def simulate_w9_02_arm(
    population: W8Population,
    market: Any,
    config: Mapping[str, Any],
    *,
    phase: str,
    window_id: str,
    mode: str,
) -> dict[str, Any]:
    allowed = {
        "permanent",
        "4:2",
        "lease-zero-recovery",
        "lease-one-window-recovery",
    }
    if mode not in allowed:
        raise ValueError(f"unsupported W9-02 mode: {mode}")

    horizon = int(config["horizon_windows"])
    slots = int(config["source_slots_per_window"])
    lease_slots = {
        str(org_id): int(slot)
        for org_id, slot in dict(config["lease_organization_slots"]).items()
    }
    if sorted(lease_slots.values()) != sorted(set(lease_slots.values())):
        raise ValueError("organization lease slots must be distinct")
    if any(slot < 0 or slot >= slots for slot in lease_slots.values()):
        raise ValueError("organization lease slot outside source window")

    rosters = _market_rosters(market, config, window_id)
    states = dict(population.portable_by_id)
    no_learning_states = dict(population.portable_by_id)
    baseline = {
        field_id: _source_frontier(rows, config)
        for field_id, rows in population.portable_by_field.items()
    }
    organization_windows = {org_id: [] for org_id in rosters}
    pair_history: dict[str, list[tuple[str, str] | None]] = {
        org_id: [] for org_id in rosters
    }
    field_loss_windows = {field_id: [] for field_id in population.portable_by_field}
    source_loss_windows: list[float] = []
    source_loss_no_learning_windows: list[float] = []
    external_agent_window_exposures = 0
    source_unavailable_agent_slots = 0
    recovery_idle_source_agent_slots = 0
    learning_events = 0
    forced_substitutions = 0
    total_org_windows = 0
    recovery_ids: set[str] = set()

    org_row_by_id = {
        str(row["organization_id"]): row for row in config["organizations"]
    }
    org_by_slot = {lease_slots[org_id]: org_id for org_id in lease_slots}

    for window in range(horizon):
        available_by_org = _organization_available_ids(
            rosters,
            config,
            window=window,
            mode=mode,
        )
        external_agent_window_exposures += sum(len(ids) for ids in available_by_org.values())
        base_unavailable = _base_source_unavailability(
            rosters,
            config,
            window=window,
            mode=mode,
        )
        unavailable_by_slot = {
            slot: set(agent_ids) for slot, agent_ids in base_unavailable.items()
        }
        if mode == "lease-one-window-recovery" and recovery_ids:
            for slot in range(slots):
                recovery_idle_source_agent_slots += len(
                    recovery_ids - unavailable_by_slot[slot]
                )
                unavailable_by_slot[slot].update(recovery_ids)

        source_unavailable_agent_slots += sum(
            len(agent_ids) for agent_ids in unavailable_by_slot.values()
        )

        next_recovery_ids: set[str] = set()
        slot_source_values = {
            field_id: [0.0] * slots for field_id in population.portable_by_field
        }
        slot_source_values_no_learning = {
            field_id: [0.0] * slots for field_id in population.portable_by_field
        }

        for slot in range(slots):
            org_id = org_by_slot.get(slot)
            if org_id is not None:
                available_ids = available_by_org[org_id]
                mission = _organization_mission(org_row_by_id[org_id])
                result = _trial_rate(
                    [states[agent_id].to_individual() for agent_id in available_ids],
                    mission,
                    config,
                    seed_salt=f"w9-02:{phase}:{window}:{org_id}",
                )
                rate = float(result["success_rate"])
                organization_windows[org_id].append(rate)
                total_org_windows += 1
                lead_id = result["lead_agent_id"]
                support_id = result["support_agent_id"]
                if lead_id and support_id:
                    pair_history[org_id].append((str(lead_id), str(support_id)))
                    delta = int(config["learning_per_executed_role"])
                    states[str(lead_id)] = states[str(lead_id)].with_learning(
                        {mission.lead_skill: delta},
                        evidence_ref=(
                            f"world://w9/{phase}/leasing/{mode}/{window}/{org_id}/lead"
                        ),
                    )
                    states[str(support_id)] = states[str(support_id)].with_learning(
                        {mission.support_skill: delta},
                        evidence_ref=(
                            f"world://w9/{phase}/leasing/{mode}/{window}/{org_id}/support"
                        ),
                    )
                    learning_events += 2
                    next_recovery_ids.update((str(lead_id), str(support_id)))
                else:
                    pair_history[org_id].append(None)
                    forced_substitutions += 1

            mission_skill = str(config["home_service_missions"][slot]["skill"])
            unavailable = unavailable_by_slot[slot]
            for field_id, baseline_states in population.portable_by_field.items():
                available_states = [
                    states[state.agent_id]
                    for state in baseline_states
                    if state.agent_id not in unavailable
                ]
                available_no_learning = [
                    no_learning_states[state.agent_id]
                    for state in baseline_states
                    if state.agent_id not in unavailable
                ]
                if available_states:
                    slot_source_values[field_id][slot] = max(
                        _source_probability(state, mission_skill, config)
                        for state in available_states
                    )
                if available_no_learning:
                    slot_source_values_no_learning[field_id][slot] = max(
                        _source_probability(state, mission_skill, config)
                        for state in available_no_learning
                    )

        counts = _source_slot_counts(config)
        trials = int(config["service_trials"])
        per_field_loss: list[float] = []
        per_field_no_learning_loss: list[float] = []
        for field_id in population.portable_by_field:
            current = sum(
                count * slot_source_values[field_id][slot]
                for slot, count in enumerate(counts)
            ) / trials
            no_learning = sum(
                count * slot_source_values_no_learning[field_id][slot]
                for slot, count in enumerate(counts)
            ) / trials
            loss = baseline[field_id] - current
            no_learning_loss = baseline[field_id] - no_learning
            field_loss_windows[field_id].append(loss)
            per_field_loss.append(loss)
            per_field_no_learning_loss.append(no_learning_loss)
        source_loss_windows.append(_mean(per_field_loss))
        source_loss_no_learning_windows.append(_mean(per_field_no_learning_loss))
        recovery_ids = next_recovery_ids if mode == "lease-one-window-recovery" else set()

    organization_rates = {
        org_id: _mean(values) for org_id, values in organization_windows.items()
    }
    mean_source_loss = _mean(source_loss_windows)
    mean_source_loss_no_learning = _mean(source_loss_no_learning_windows)
    equivalent_unavailable_windows = source_unavailable_agent_slots / slots
    useful_per_unavailable = (
        external_agent_window_exposures / equivalent_unavailable_windows
        if equivalent_unavailable_windows
        else None
    )
    return {
        "external_agent_window_exposures": external_agent_window_exposures,
        "field_mean_source_loss_pp": {
            field_id: _mean(values) * 100.0
            for field_id, values in sorted(field_loss_windows.items())
        },
        "forced_substitution_fraction": (
            forced_substitutions / total_org_windows if total_org_windows else 0.0
        ),
        "learning_events": learning_events,
        "lease_conflict_rate": 0.0,
        "mean_organization_success_pct": _mean(list(organization_rates.values())) * 100.0,
        "mean_source_loss_no_learning_pp": mean_source_loss_no_learning * 100.0,
        "mean_source_loss_pp": mean_source_loss * 100.0,
        "mode": mode,
        "organization_rates_pct": {
            org_id: value * 100.0 for org_id, value in sorted(organization_rates.items())
        },
        "pair_continuity": {
            org_id: _pair_continuity(values)
            for org_id, values in sorted(pair_history.items())
        },
        "recovery_idle_source_agent_slots": recovery_idle_source_agent_slots,
        "returned_learning_contribution_pp": (
            mean_source_loss_no_learning - mean_source_loss
        )
        * 100.0,
        "source_unavailable_agent_slots": source_unavailable_agent_slots,
        "source_unavailable_equivalent_agent_windows": equivalent_unavailable_windows,
        "useful_external_service_per_source_unavailable_window": useful_per_unavailable,
    }


def run_w9_02(
    population: W8Population,
    config: Mapping[str, Any],
    *,
    phase: str,
) -> dict[str, Any]:
    window_id = f"w9-02:{phase}"
    offers = _generate_offers(population, config, window_id=window_id)
    market = _unrestricted_allocation(population, offers, config, window_id=window_id)
    arms = {
        mode: simulate_w9_02_arm(
            population,
            market,
            config,
            phase=phase,
            window_id=window_id,
            mode=mode,
        )
        for mode in (
            "permanent",
            "4:2",
            "lease-zero-recovery",
            "lease-one-window-recovery",
        )
    }
    permanent = arms["permanent"]
    zero = arms["lease-zero-recovery"]
    recovery = arms["lease-one-window-recovery"]
    organization_floor = float(permanent["mean_organization_success_pct"]) - float(
        config["effect_band_pp"]
    )
    source_bound = float(config["source_loss_bound_pp"])
    zero_gate = (
        float(zero["mean_organization_success_pct"]) + 1e-12 >= organization_floor
        and float(zero["mean_source_loss_pp"]) <= source_bound + 1e-12
    )
    recovery_gate = (
        float(recovery["mean_organization_success_pct"]) + 1e-12 >= organization_floor
        and float(recovery["mean_source_loss_pp"]) <= source_bound + 1e-12
    )
    if zero_gate and recovery_gate:
        classification = "robust_sustainable_leasing"
    elif zero_gate:
        classification = "leasing_switching_fragile"
    else:
        classification = "leasing_not_sustainable"
    return {
        "arms": arms,
        "classification": classification,
        "offer_count": len(offers),
        "phase": phase,
        "recovery_gate": recovery_gate,
        "robust_gate": zero_gate and recovery_gate,
        "version": RESULT_VERSION,
        "zero_recovery_gate": zero_gate,
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
        raise ValueError("W9 leasing config must be an object")
    population = load_population(args.source_dir, expected_seeds=_phase_seeds(config, args.phase))
    result = run_w9_02(population, config, phase=args.phase)
    _write_json(args.output, result)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
