"""W5B modular social-capital experiments."""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .w4a_joint_learning import (
    CommunicationPolicy,
    IndividualState,
    JointController,
    JointEnvironment,
    JointLearningSession,
    JointMission,
    RelationshipStateStore,
)
from .w5b_pair_module import (
    PairInstance,
    PairModule,
    capture_pair,
    instantiate_intact,
    instantiate_with_reset,
    replace_member,
)


def _read_json(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain an object")
    return value


def _read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in Path(path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _mean(values: list[float]) -> float:
    return statistics.mean(values) if values else 0.0


def _seed(*parts: object) -> int:
    payload = "|".join(str(part) for part in parts).encode()
    return int.from_bytes(hashlib.sha256(payload).digest()[:4], "big")


def _stable_key(field_id: str, agent_id: str) -> bytes:
    return hashlib.sha256(f"w5b-roster|{field_id}|{agent_id}".encode()).digest()


@dataclass(frozen=True, slots=True)
class ModuleMission:
    module_key: str
    formation: JointMission
    evaluation: JointMission


@dataclass(frozen=True, slots=True)
class FieldDesign:
    field_id: str
    agents: tuple[IndividualState, ...]


def _mission(row: dict[str, Any]) -> JointMission:
    return JointMission(
        str(row["mission_id"]),
        str(row["context"]),
        str(row["lead_skill"]),
        str(row["support_skill"]),
    )


def _module_missions(path: str | Path, phase: str) -> list[ModuleMission]:
    rows = list(_read_json(path)[phase])
    result = []
    for row in rows:
        result.append(
            ModuleMission(
                str(row["module_key"]),
                _mission(dict(row["formation"])),
                _mission(dict(row["evaluation"])),
            )
        )
    if len(result) != 3:
        raise ValueError("W5B requires exactly three module mission families")
    return result


def _group_capsules(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(str(row["field_id"]), []).append(row)
    return grouped


def _load_designs(
    capsules_path: str | Path,
    allowed_fields: list[str],
) -> dict[str, FieldDesign]:
    grouped = _group_capsules(_read_jsonl(capsules_path))
    result: dict[str, FieldDesign] = {}
    for field_id in allowed_fields:
        rows = grouped.get(field_id)
        if rows is None:
            raise ValueError(f"missing field {field_id}")
        agents = [
            IndividualState(
                str(row["agent_id"]),
                {
                    str(skill): int(value)
                    for skill, value in dict(row["practice_by_skill"]).items()
                },
            )
            for row in rows
        ]
        ordered = tuple(
            sorted(agents, key=lambda item: _stable_key(field_id, item.agent_id))
        )
        if len(ordered) != 12:
            raise ValueError("W5B requires exactly 12 source agents per Field")
        result[field_id] = FieldDesign(field_id, ordered)
    return result


def _train_module(
    design: FieldDesign,
    pair_slots: tuple[int, int],
    spec: ModuleMission,
    depth: int,
    bandwidth_bits: int,
    module_index: int,
) -> PairModule:
    first = design.agents[pair_slots[0]]
    second = design.agents[pair_slots[1]]
    relationships = RelationshipStateStore()
    session = JointLearningSession(
        JointEnvironment(),
        JointController(),
        relationships,
        CommunicationPolicy(bandwidth_bits),
    )
    for episode in range(depth):
        session.run_episode(
            first,
            second,
            spec.formation,
            seed=_seed(design.field_id, "w5b-formation", module_index, episode),
        )
    return capture_pair(
        f"w5b-{design.field_id}-{spec.module_key}",
        first,
        second,
        relationships,
        source_field_ids=(design.field_id, design.field_id),
        formation_evidence=(f"w5b://{design.field_id}/{spec.module_key}/formation",),
        capability_profile={spec.module_key: 1.0},
        provenance=(f"field://{design.field_id}",),
    )


def _develop_modules(
    design: FieldDesign,
    missions: list[ModuleMission],
    campaign: dict[str, Any],
) -> list[PairModule]:
    slots = [tuple(int(value) for value in row) for row in campaign["module_pair_slots"]]
    if len(slots) != 3 or any(len(row) != 2 for row in slots):
        raise ValueError("module_pair_slots must define exactly three pairs")
    depth = int(campaign["formation_depth"])
    bandwidth = int(campaign["communication_bandwidth_bits"])
    return [
        _train_module(design, slots[index], spec, depth, bandwidth, index)
        for index, spec in enumerate(missions)
    ]


def _trial_success(
    instance: PairInstance,
    mission: JointMission,
    bandwidth_bits: int,
    *,
    seed: int,
) -> bool:
    controller = JointController()
    environment = JointEnvironment()
    communication = CommunicationPolicy(bandwidth_bits)
    first_message = controller.preferred_role(instance.first, mission)
    second_message = controller.preferred_role(instance.second, mission)
    first_action = controller.choose_action(
        instance.first,
        instance.second,
        mission,
        instance.relationships,
        communication,
        partner_message=second_message,
    )
    second_action = controller.choose_action(
        instance.second,
        instance.first,
        mission,
        instance.relationships,
        communication,
        partner_message=first_message,
    )
    return environment.evaluate(
        instance.first,
        instance.second,
        mission,
        first_action,
        second_action,
        seed=seed,
    )


def _score(
    instance: PairInstance,
    mission: JointMission,
    trials: int,
    bandwidth_bits: int,
    *,
    field_id: str,
    salt: str,
) -> float:
    values = [
        float(
            _trial_success(
                instance,
                mission,
                bandwidth_bits,
                seed=_seed(field_id, salt, trial),
            )
        )
        for trial in range(trials)
    ]
    return _mean(values)


def _composite_score(
    first: PairInstance,
    first_mission: JointMission,
    second: PairInstance,
    second_mission: JointMission,
    trials: int,
    bandwidth_bits: int,
    *,
    field_id: str,
    salt: str,
) -> float:
    values: list[float] = []
    for trial in range(trials):
        first_ok = _trial_success(
            first,
            first_mission,
            bandwidth_bits,
            seed=_seed(field_id, salt, trial, "first"),
        )
        second_ok = _trial_success(
            second,
            second_mission,
            bandwidth_bits,
            seed=_seed(field_id, salt, trial, "second"),
        )
        values.append(float(first_ok and second_ok))
    return _mean(values)


def _classification(effect: float, threshold: float) -> str:
    if effect > threshold:
        return "positive"
    if effect < -threshold:
        return "negative"
    return "null"


def _fresh_instance(first: IndividualState, second: IndividualState) -> PairInstance:
    return PairInstance(
        IndividualState(first.agent_id, dict(first.practice_by_skill)),
        IndividualState(second.agent_id, dict(second.practice_by_skill)),
        RelationshipStateStore(),
        "fresh",
        (),
    )


def _w5b_01(
    design: FieldDesign,
    modules: list[PairModule],
    missions: list[ModuleMission],
    campaign: dict[str, Any],
) -> dict[str, Any]:
    trials = int(campaign["evaluation_trials_per_mission"])
    bandwidth = int(campaign["communication_bandwidth_bits"])
    rows: list[dict[str, Any]] = []
    for index, module in enumerate(modules):
        intact = instantiate_intact(module)
        reset = instantiate_with_reset(module)
        stranger_first = design.agents[6 + 2 * index]
        stranger_second = design.agents[7 + 2 * index]
        strangers = _fresh_instance(stranger_first, stranger_second)
        mission = missions[index].evaluation
        intact_score = _score(
            intact,
            mission,
            trials,
            bandwidth,
            field_id=design.field_id,
            salt=f"w5b01-{index}",
        )
        reset_score = _score(
            reset,
            mission,
            trials,
            bandwidth,
            field_id=design.field_id,
            salt=f"w5b01-{index}",
        )
        stranger_score = _score(
            strangers,
            mission,
            trials,
            bandwidth,
            field_id=design.field_id,
            salt=f"w5b01-{index}",
        )
        rows.append(
            {
                "module_key": missions[index].module_key,
                "intact": intact_score,
                "reset": reset_score,
                "strangers": stranger_score,
                "intact_minus_reset": intact_score - reset_score,
                "intact_minus_strangers": intact_score - stranger_score,
            }
        )
    effect = _mean([float(row["intact_minus_reset"]) for row in rows])
    return {
        "effect": effect,
        "rows": rows,
    }


def _w5b_02(
    design: FieldDesign,
    modules: list[PairModule],
    missions: list[ModuleMission],
    campaign: dict[str, Any],
) -> dict[str, Any]:
    trials = int(campaign["evaluation_trials_per_mission"])
    bandwidth = int(campaign["communication_bandwidth_bits"])
    replacement_slots = [int(value) for value in campaign["replacement_slots"]]
    rows: list[dict[str, Any]] = []
    for index, module in enumerate(modules):
        replacement = design.agents[replacement_slots[index]]
        retiring = module.member_b.agent_id
        inherited = replace_member(module, retiring, replacement)
        fresh = _fresh_instance(inherited.first, inherited.second)
        mission = missions[index].evaluation
        inherited_score = _score(
            inherited,
            mission,
            trials,
            bandwidth,
            field_id=design.field_id,
            salt=f"w5b02-{index}",
        )
        fresh_score = _score(
            fresh,
            mission,
            trials,
            bandwidth,
            field_id=design.field_id,
            salt=f"w5b02-{index}",
        )
        rows.append(
            {
                "module_key": missions[index].module_key,
                "inherited": inherited_score,
                "fresh_relationship": fresh_score,
                "inheritance_effect": inherited_score - fresh_score,
                "retained_state": list(inherited.retained_state),
            }
        )
    effect = _mean([float(row["inheritance_effect"]) for row in rows])
    return {
        "effect": effect,
        "rows": rows,
    }


def _w5b_03(
    design: FieldDesign,
    modules: list[PairModule],
    missions: list[ModuleMission],
    campaign: dict[str, Any],
) -> dict[str, Any]:
    trials = int(campaign["evaluation_trials_per_mission"])
    bandwidth = int(campaign["communication_bandwidth_bits"])
    combinations = ((0, 1), (1, 2), (0, 2))
    rows: list[dict[str, Any]] = []
    for combo_index, (first_index, second_index) in enumerate(combinations):
        first_intact = instantiate_intact(modules[first_index])
        second_intact = instantiate_intact(modules[second_index])
        first_reset = instantiate_with_reset(modules[first_index])
        second_reset = instantiate_with_reset(modules[second_index])
        intact_score = _composite_score(
            first_intact,
            missions[first_index].evaluation,
            second_intact,
            missions[second_index].evaluation,
            trials,
            bandwidth,
            field_id=design.field_id,
            salt=f"w5b03-{combo_index}",
        )
        reset_score = _composite_score(
            first_reset,
            missions[first_index].evaluation,
            second_reset,
            missions[second_index].evaluation,
            trials,
            bandwidth,
            field_id=design.field_id,
            salt=f"w5b03-{combo_index}",
        )
        rows.append(
            {
                "modules": [
                    missions[first_index].module_key,
                    missions[second_index].module_key,
                ],
                "intact": intact_score,
                "reset": reset_score,
                "composition_effect": intact_score - reset_score,
            }
        )
    effect = _mean([float(row["composition_effect"]) for row in rows])
    return {
        "effect": effect,
        "rows": rows,
        "inter_module_state": "absent_by_design",
    }


def _w5b_04(
    design: FieldDesign,
    modules: list[PairModule],
    missions: list[ModuleMission],
    campaign: dict[str, Any],
) -> dict[str, Any]:
    trials = int(campaign["evaluation_trials_per_mission"])
    bandwidth = int(campaign["communication_bandwidth_bits"])
    sizes = [int(value) for value in campaign["library_sizes"]]
    curve: dict[str, float] = {}
    for size in sizes:
        values: list[float] = []
        for index, module in enumerate(modules):
            instance = (
                instantiate_intact(module)
                if index < size
                else instantiate_with_reset(module)
            )
            values.append(
                _score(
                    instance,
                    missions[index].evaluation,
                    trials,
                    bandwidth,
                    field_id=design.field_id,
                    salt=f"w5b04-{index}",
                )
            )
        curve[str(size)] = _mean(values)
    effect = curve[str(max(sizes))] - curve[str(min(sizes))]
    return {
        "effect": effect,
        "library_curve": curve,
        "fixed_agent_count": 6,
    }


def _field_experiments(
    design: FieldDesign,
    missions: list[ModuleMission],
    campaign: dict[str, Any],
) -> dict[str, Any]:
    modules = _develop_modules(design, missions, campaign)
    return {
        "field_id": design.field_id,
        "module_digests": [module.content_sha256() for module in modules],
        "w5b_01": _w5b_01(design, modules, missions, campaign),
        "w5b_02": _w5b_02(design, modules, missions, campaign),
        "w5b_03": _w5b_03(design, modules, missions, campaign),
        "w5b_04": _w5b_04(design, modules, missions, campaign),
    }


def _pooled(rows: list[dict[str, Any]], key: str) -> float:
    return _mean([float(row[key]["effect"]) for row in rows])


def _summary(
    rows: list[dict[str, Any]],
    threshold: float,
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key in ("w5b_01", "w5b_02", "w5b_03", "w5b_04"):
        effect = _pooled(rows, key)
        result[key] = {
            "classification": _classification(effect, threshold),
            "effect": effect,
            "positive_fields": sum(float(row[key]["effect"]) > 0 for row in rows),
            "negative_fields": sum(float(row[key]["effect"]) < 0 for row in rows),
        }
    return result


def discover(
    capsules_path: str | Path,
    missions_path: str | Path,
    campaign_path: str | Path,
    output_dir: str | Path,
) -> dict[str, Any]:
    campaign = _read_json(campaign_path)
    missions = _module_missions(missions_path, "discovery")
    threshold = float(campaign["effect_threshold"])
    designs = _load_designs(capsules_path, list(campaign["discovery_fields"]))
    rows = [
        _field_experiments(design, missions, campaign)
        for _, design in sorted(designs.items())
    ]
    result = {
        "field_results": rows,
        "summary": _summary(rows, threshold),
    }
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    _write_json(output / "w5b-discovery.json", result)
    return result


def _replication_requirement(
    classification: str,
    effect: float,
    field_effects: list[float],
    threshold: float,
    minimum_fields: int,
) -> bool:
    if classification == "positive":
        return effect > threshold and sum(value > 0 for value in field_effects) >= minimum_fields
    if classification == "negative":
        return effect < -threshold and sum(value < 0 for value in field_effects) >= minimum_fields
    return abs(effect) <= threshold


def replicate(
    capsules_path: str | Path,
    missions_path: str | Path,
    campaign_path: str | Path,
    discovery_path: str | Path,
    output_dir: str | Path,
) -> dict[str, Any]:
    campaign = _read_json(campaign_path)
    discovery = _read_json(discovery_path)
    missions = _module_missions(missions_path, "replication")
    threshold = float(campaign["effect_threshold"])
    minimum_fields = int(campaign["minimum_positive_replication_fields"])
    designs = _load_designs(capsules_path, list(campaign["replication_fields"]))
    rows = [
        _field_experiments(design, missions, campaign)
        for _, design in sorted(designs.items())
    ]
    summary = _summary(rows, threshold)
    gates: dict[str, bool] = {}
    for key in ("w5b_01", "w5b_02", "w5b_03", "w5b_04"):
        discovery_class = str(discovery["summary"][key]["classification"])
        field_effects = [float(row[key]["effect"]) for row in rows]
        classification_match = summary[key]["classification"] == discovery_class
        requirements = _replication_requirement(
            discovery_class,
            float(summary[key]["effect"]),
            field_effects,
            threshold,
            minimum_fields,
        )
        gates[key] = classification_match and requirements
        summary[key]["discovery_classification"] = discovery_class
        summary[key]["classification_match"] = classification_match
        summary[key]["replication_requirement"] = requirements
    result = {
        "field_results": rows,
        "replication_gate": all(gates.values()),
        "experiment_gates": gates,
        "summary": summary,
    }
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    _write_json(output / "w5b-05-replication.json", result)
    return result


def synthesize(
    discovery_path: str | Path,
    replication_path: str | Path,
    output_dir: str | Path,
) -> dict[str, Any]:
    discovery = _read_json(discovery_path)
    replication = _read_json(replication_path)
    replicated = bool(replication["replication_gate"])
    modularization = str(discovery["summary"]["w5b_01"]["classification"])
    succession = str(discovery["summary"]["w5b_02"]["classification"])
    if not replicated:
        status = "w5b_discovery_not_replicated"
    elif modularization == "positive" and succession == "positive":
        status = "w5b_social_state_inheritance_replicated"
    elif modularization == "positive":
        status = "w5b_state_modularization_replicated_without_succession"
    elif modularization == "negative":
        status = "w5b_module_state_harm_replicated"
    else:
        status = "w5b_no_state_modularization_detected"
    result = {
        "status": status,
        "replication_gate": replicated,
        "discovery": discovery["summary"],
        "replication": replication["summary"],
    }
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    _write_json(output / "w5b-synthesis.json", result)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    discovery = commands.add_parser("discover")
    discovery.add_argument("capsules", type=Path)
    discovery.add_argument("missions", type=Path)
    discovery.add_argument("campaign", type=Path)
    discovery.add_argument("output", type=Path)

    replication = commands.add_parser("replicate")
    replication.add_argument("capsules", type=Path)
    replication.add_argument("missions", type=Path)
    replication.add_argument("campaign", type=Path)
    replication.add_argument("discovery", type=Path)
    replication.add_argument("output", type=Path)

    synthesis = commands.add_parser("synthesize")
    synthesis.add_argument("discovery", type=Path)
    synthesis.add_argument("replication", type=Path)
    synthesis.add_argument("output", type=Path)

    args = parser.parse_args(argv)
    if args.command == "discover":
        result = discover(args.capsules, args.missions, args.campaign, args.output)
    elif args.command == "replicate":
        result = replicate(
            args.capsules,
            args.missions,
            args.campaign,
            args.discovery,
            args.output,
        )
    else:
        result = synthesize(args.discovery, args.replication, args.output)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
