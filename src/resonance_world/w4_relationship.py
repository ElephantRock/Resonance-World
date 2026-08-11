"""W4 relationship formation, factorial controls, ablations, and replication."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .w4a_joint_learning import (
    CommunicationPolicy,
    IndividualState,
    JointAction,
    JointController,
    JointEnvironment,
    JointLearningSession,
    JointMission,
    RelationshipStateStore,
)


def _read_json(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain an object")
    return value


def _read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"{path} contains a non-object row")
            rows.append(value)
    return rows


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _mean(values: list[float]) -> float:
    return statistics.mean(values) if values else 0.0


def _mission(row: dict[str, Any]) -> JointMission:
    return JointMission(
        mission_id=str(row["mission_id"]),
        context=str(row["context"]),
        lead_skill=str(row["lead_skill"]),
        support_skill=str(row["support_skill"]),
    )


def _stable_key(field_id: str, agent_id: str) -> bytes:
    return hashlib.sha256(f"w4-assignment|{field_id}|{agent_id}".encode()).digest()


def _seed(*parts: object) -> int:
    digest = hashlib.sha256("|".join(str(part) for part in parts).encode()).digest()
    return int.from_bytes(digest[:4], "big")


@dataclass(frozen=True, slots=True)
class FieldDesign:
    field_id: str
    treated_agents: tuple[IndividualState, ...]
    control_agents: tuple[IndividualState, ...]
    original_pairs: tuple[tuple[IndividualState, IndividualState], ...]
    rotated_pairs: tuple[tuple[IndividualState, IndividualState], ...]
    control_pairs: tuple[tuple[IndividualState, IndividualState], ...]


def _field_design(field_id: str, rows: list[dict[str, Any]]) -> FieldDesign:
    if len(rows) != 12:
        raise ValueError(f"{field_id}: W4 requires exactly 12 agents")
    agents = [
        IndividualState(
            str(row["agent_id"]),
            {str(skill): int(value) for skill, value in row["practice_by_skill"].items()},
        )
        for row in rows
    ]
    ordered = sorted(agents, key=lambda item: _stable_key(field_id, item.agent_id))
    treated = tuple(ordered[:6])
    controls = tuple(ordered[6:])
    original = tuple((treated[index], treated[index + 1]) for index in range(0, 6, 2))
    rotated = (
        (original[0][0], original[1][1]),
        (original[1][0], original[2][1]),
        (original[2][0], original[0][1]),
    )
    control_pairs = tuple((controls[index], controls[index + 1]) for index in range(0, 6, 2))
    original_sets = {frozenset((a.agent_id, b.agent_id)) for a, b in original}
    if any(frozenset((a.agent_id, b.agent_id)) in original_sets for a, b in rotated):
        raise AssertionError("rotated W4 pairs must not contain an original pair")
    return FieldDesign(field_id, treated, controls, original, rotated, control_pairs)


def _group_capsules(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(str(row["field_id"]), []).append(row)
    return grouped


def _train(
    design: FieldDesign,
    missions: list[JointMission],
    depth: int,
    communication: CommunicationPolicy,
) -> RelationshipStateStore:
    store = RelationshipStateStore()
    session = JointLearningSession(JointEnvironment(), JointController(), store, communication)
    for episode_index in range(depth):
        mission = missions[episode_index % len(missions)]
        for pair_index, (first, second) in enumerate(design.original_pairs):
            session.run_episode(
                first,
                second,
                mission,
                seed=_seed(design.field_id, "formation", episode_index, pair_index),
            )
    return store


def _actions(
    store: RelationshipStateStore,
    first: IndividualState,
    second: IndividualState,
    mission: JointMission,
    communication: CommunicationPolicy,
) -> tuple[JointAction, JointAction]:
    controller = JointController()
    first_message = controller.preferred_role(first, mission)
    second_message = controller.preferred_role(second, mission)
    first_action = controller.choose_action(
        first,
        second,
        mission,
        store,
        communication,
        partner_message=second_message,
    )
    second_action = controller.choose_action(
        second,
        first,
        mission,
        store,
        communication,
        partner_message=first_message,
    )
    return first_action, second_action


def _evaluate_pairs(
    field_id: str,
    pairs: tuple[tuple[IndividualState, IndividualState], ...],
    missions: list[JointMission],
    store: RelationshipStateStore,
    communication: CommunicationPolicy,
    trials: int,
    *,
    salt: str,
) -> float:
    environment = JointEnvironment()
    working = copy.deepcopy(store)
    outcomes: list[float] = []
    for pair_index, (first, second) in enumerate(pairs):
        for mission_index, mission in enumerate(missions):
            first_action, second_action = _actions(
                working, first, second, mission, communication
            )
            for trial in range(trials):
                success = environment.evaluate(
                    first,
                    second,
                    mission,
                    first_action,
                    second_action,
                    seed=_seed(field_id, salt, pair_index, mission_index, trial),
                )
                outcomes.append(float(success))
    return _mean(outcomes)


def _evaluate_solo(
    field_id: str,
    pairs: tuple[tuple[IndividualState, IndividualState], ...],
    missions: list[JointMission],
    trials: int,
    *,
    salt: str,
) -> float:
    environment = JointEnvironment()
    outcomes: list[float] = []
    for pair_index, pair in enumerate(pairs):
        for mission_index, mission in enumerate(missions):
            best = max(
                pair,
                key=lambda agent: (
                    environment.role_probability(agent, mission.lead_skill)
                    * environment.role_probability(agent, mission.support_skill),
                    agent.agent_id,
                ),
            )
            lead = JointAction(best.agent_id, "lead")
            support = JointAction(best.agent_id, "support")
            for trial in range(trials):
                success = environment.evaluate(
                    best,
                    best,
                    mission,
                    lead,
                    support,
                    seed=_seed(field_id, salt, pair_index, mission_index, trial),
                )
                outcomes.append(float(success))
    return _mean(outcomes)


def _pair_specific_reset(
    store: RelationshipStateStore,
    pairs: tuple[tuple[IndividualState, IndividualState], ...],
) -> RelationshipStateStore:
    result = copy.deepcopy(store)
    for first, second in pairs:
        result.reset_partner_models(first.agent_id, second.agent_id)
        result.clear_pair_memory(first.agent_id, second.agent_id)
    return result


def _partner_model_ablation(
    store: RelationshipStateStore,
    pairs: tuple[tuple[IndividualState, IndividualState], ...],
) -> RelationshipStateStore:
    result = copy.deepcopy(store)
    for first, second in pairs:
        result.reset_partner_models(first.agent_id, second.agent_id)
    return result


def _pair_memory_ablation(
    store: RelationshipStateStore,
    pairs: tuple[tuple[IndividualState, IndividualState], ...],
) -> RelationshipStateStore:
    result = copy.deepcopy(store)
    for first, second in pairs:
        result.clear_pair_memory(first.agent_id, second.agent_id)
    return result


def _classification(partner_effect: float, general_effect: float, threshold: float) -> str:
    partner = partner_effect > threshold
    general = general_effect > threshold
    if partner and general:
        return "both"
    if partner:
        return "partner_specific"
    if general:
        return "general_teamwork"
    return "neither"


def _field_factorial(
    design: FieldDesign,
    trained: RelationshipStateStore,
    missions: list[JointMission],
    communication: CommunicationPolicy,
    trials: int,
    threshold: float,
    *,
    salt: str,
) -> dict[str, Any]:
    fresh = RelationshipStateStore()
    c1_pre = _evaluate_pairs(
        design.field_id,
        design.original_pairs,
        missions,
        fresh,
        communication,
        trials,
        salt=f"{salt}-pre",
    )
    c2_pre = _evaluate_pairs(
        design.field_id,
        design.rotated_pairs,
        missions,
        fresh,
        communication,
        trials,
        salt=f"{salt}-pre",
    )
    c1 = _evaluate_pairs(
        design.field_id,
        design.original_pairs,
        missions,
        trained,
        communication,
        trials,
        salt=f"{salt}-post",
    )
    c2 = _evaluate_pairs(
        design.field_id,
        design.rotated_pairs,
        missions,
        trained,
        communication,
        trials,
        salt=f"{salt}-post",
    )
    c3 = _evaluate_pairs(
        design.field_id,
        design.rotated_pairs,
        missions,
        RelationshipStateStore(),
        communication,
        trials,
        salt=f"{salt}-post",
    )
    c4 = _evaluate_solo(
        design.field_id,
        design.original_pairs,
        missions,
        trials,
        salt=f"{salt}-post",
    )
    partner_effect = (c1 - c1_pre) - (c2 - c2_pre)
    general_effect = c2 - c3
    return {
        "c1_original_experienced": c1,
        "c1_pre": c1_pre,
        "c2_experienced_repaired": c2,
        "c2_pre": c2_pre,
        "c3_coordination_reset": c3,
        "c4_individual_ceiling": c4,
        "classification": _classification(partner_effect, general_effect, threshold),
        "general_teamwork_effect": general_effect,
        "partner_specific_effect": partner_effect,
        "preexisting_pair_compatibility_delta": c1_pre - c2_pre,
    }


def _pooled_factorial(rows: list[dict[str, Any]], threshold: float) -> dict[str, Any]:
    partner = _mean([float(row["partner_specific_effect"]) for row in rows])
    general = _mean([float(row["general_teamwork_effect"]) for row in rows])
    return {
        "classification": _classification(partner, general, threshold),
        "general_teamwork_effect": general,
        "partner_specific_effect": partner,
        "positive_general_fields": sum(
            float(row["general_teamwork_effect"]) > 0 for row in rows
        ),
        "positive_partner_fields": sum(
            float(row["partner_specific_effect"]) > 0 for row in rows
        ),
        "field_results": rows,
    }


def _ablation_result(
    design: FieldDesign,
    trained: RelationshipStateStore,
    missions: list[JointMission],
    communication: CommunicationPolicy,
    trials: int,
) -> dict[str, float]:
    full = _evaluate_pairs(
        design.field_id,
        design.original_pairs,
        missions,
        trained,
        communication,
        trials,
        salt="ablation",
    )
    no_partner = _evaluate_pairs(
        design.field_id,
        design.original_pairs,
        missions,
        _partner_model_ablation(trained, design.original_pairs),
        communication,
        trials,
        salt="ablation",
    )
    no_memory = _evaluate_pairs(
        design.field_id,
        design.original_pairs,
        missions,
        _pair_memory_ablation(trained, design.original_pairs),
        communication,
        trials,
        salt="ablation",
    )
    general_only = _evaluate_pairs(
        design.field_id,
        design.original_pairs,
        missions,
        _pair_specific_reset(trained, design.original_pairs),
        communication,
        trials,
        salt="ablation",
    )
    fully_reset = _evaluate_pairs(
        design.field_id,
        design.original_pairs,
        missions,
        RelationshipStateStore(),
        communication,
        trials,
        salt="ablation",
    )
    return {
        "full": full,
        "no_pair_memory": no_memory,
        "no_partner_model": no_partner,
        "pair_specific_reset": general_only,
        "full_coordination_reset": fully_reset,
        "pair_specific_reset_effect": full - general_only,
        "general_teamwork_on_original_pair_effect": general_only - fully_reset,
        "pair_memory_contribution": full - no_memory,
        "partner_model_contribution": full - no_partner,
    }


def _load_designs(
    capsules_path: str | Path, allowed_fields: list[str]
) -> dict[str, FieldDesign]:
    grouped = _group_capsules(_read_jsonl(capsules_path))
    result: dict[str, FieldDesign] = {}
    for field_id in allowed_fields:
        if field_id not in grouped:
            raise ValueError(f"missing field {field_id}")
        result[field_id] = _field_design(field_id, grouped[field_id])
    return result


def discover(
    capsules_path: str | Path,
    missions_path: str | Path,
    campaign_path: str | Path,
    output_dir: str | Path,
) -> dict[str, Any]:
    missions_raw = _read_json(missions_path)
    campaign = _read_json(campaign_path)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    formation = [_mission(row) for row in missions_raw["formation"]]
    probes = [_mission(row) for row in missions_raw["formation_probe"]]
    transfer = [_mission(row) for row in missions_raw["transfer"]]
    context_shift = [_mission(row) for row in missions_raw["context_shift"]]
    communication = CommunicationPolicy(int(campaign["communication_bandwidth_bits"]))
    trials = int(campaign["evaluation_trials_per_mission"])
    threshold = float(campaign["effect_threshold"])
    depths = [int(item) for item in campaign["formation_depths"]]
    deep = int(campaign["deep_formation_depth"])

    calibration = _load_designs(capsules_path, list(campaign["calibration_fields"]))
    heldout = _load_designs(capsules_path, list(campaign["discovery_fields"]))

    depth_rows: list[dict[str, Any]] = []
    for field_id, design in calibration.items():
        for depth in depths:
            store = _train(design, formation, depth, communication)
            success = _evaluate_pairs(
                field_id,
                design.original_pairs,
                probes,
                store,
                communication,
                trials,
                salt=f"depth-{depth}",
            )
            depth_rows.append({"depth": depth, "field_id": field_id, "success": success})
    depth_means = {
        str(depth): _mean(
            [float(row["success"]) for row in depth_rows if int(row["depth"]) == depth]
        )
        for depth in depths
    }
    w4_01 = {
        "depth_means": depth_means,
        "deep_minus_zero": depth_means[str(deep)] - depth_means[str(depths[0])],
        "field_depth_rows": depth_rows,
        "fixed_pairing": True,
    }

    checkpoints = [int(item) for item in campaign["learning_checkpoints"]]
    curve = {str(point): depth_means.get(str(point)) for point in checkpoints if str(point) in depth_means}
    w4_02 = {
        "checkpoints": curve,
        "learning_gain": depth_means[str(deep)] - depth_means[str(depths[0])],
    }

    factorial_rows: list[dict[str, Any]] = []
    ablations: list[dict[str, Any]] = []
    transfer_rows: list[dict[str, Any]] = []
    for field_id, design in heldout.items():
        trained = _train(design, formation, deep, communication)
        factorial = _field_factorial(
            design,
            trained,
            transfer,
            communication,
            trials,
            threshold,
            salt="discovery-transfer",
        )
        factorial["field_id"] = field_id
        factorial_rows.append(factorial)

        ablation = _ablation_result(design, trained, transfer, communication, trials)
        ablation["field_id"] = field_id
        ablations.append(ablation)

        same_context = _field_factorial(
            design,
            trained,
            transfer,
            communication,
            trials,
            threshold,
            salt="transfer-same-context",
        )
        unseen_context = _field_factorial(
            design,
            trained,
            context_shift,
            communication,
            trials,
            threshold,
            salt="transfer-unseen-context",
        )
        transfer_rows.append(
            {
                "field_id": field_id,
                "same_context_general_effect": same_context["general_teamwork_effect"],
                "same_context_partner_effect": same_context["partner_specific_effect"],
                "unseen_context_general_effect": unseen_context["general_teamwork_effect"],
                "unseen_context_partner_effect": unseen_context["partner_specific_effect"],
            }
        )

    w4_03 = _pooled_factorial(factorial_rows, threshold)
    w4_04 = {
        "field_results": ablations,
        "general_teamwork_effect": _mean(
            [float(row["general_teamwork_on_original_pair_effect"]) for row in ablations]
        ),
        "pair_specific_reset_effect": _mean(
            [float(row["pair_specific_reset_effect"]) for row in ablations]
        ),
    }
    w4_05 = {
        "pair_memory_contribution": _mean(
            [float(row["pair_memory_contribution"]) for row in ablations]
        ),
        "partner_model_contribution": _mean(
            [float(row["partner_model_contribution"]) for row in ablations]
        ),
        "field_results": ablations,
    }
    w4_06 = {
        "field_results": transfer_rows,
        "same_context_general_effect": _mean(
            [float(row["same_context_general_effect"]) for row in transfer_rows]
        ),
        "same_context_partner_effect": _mean(
            [float(row["same_context_partner_effect"]) for row in transfer_rows]
        ),
        "unseen_context_general_effect": _mean(
            [float(row["unseen_context_general_effect"]) for row in transfer_rows]
        ),
        "unseen_context_partner_effect": _mean(
            [float(row["unseen_context_partner_effect"]) for row in transfer_rows]
        ),
    }
    result = {
        "w4_01": w4_01,
        "w4_02": w4_02,
        "w4_03": w4_03,
        "w4_04": w4_04,
        "w4_05": w4_05,
        "w4_06": w4_06,
        "discovery_classification": w4_03["classification"],
    }
    _write_json(output / "w4-discovery.json", result)
    return result


def replicate(
    capsules_path: str | Path,
    missions_path: str | Path,
    campaign_path: str | Path,
    discovery_path: str | Path,
    output_dir: str | Path,
) -> dict[str, Any]:
    missions_raw = _read_json(missions_path)
    campaign = _read_json(campaign_path)
    discovery = _read_json(discovery_path)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    formation = [_mission(row) for row in missions_raw["formation"]]
    replication_missions = [_mission(row) for row in missions_raw["replication"]]
    communication = CommunicationPolicy(int(campaign["communication_bandwidth_bits"]))
    trials = int(campaign["evaluation_trials_per_mission"])
    threshold = float(campaign["effect_threshold"])
    deep = int(campaign["deep_formation_depth"])
    minimum_fields = int(campaign["minimum_positive_replication_fields"])
    designs = _load_designs(capsules_path, list(campaign["replication_fields"]))

    rows: list[dict[str, Any]] = []
    for field_id, design in designs.items():
        trained = _train(design, formation, deep, communication)
        row = _field_factorial(
            design,
            trained,
            replication_missions,
            communication,
            trials,
            threshold,
            salt="replication",
        )
        row["field_id"] = field_id
        rows.append(row)

    pooled = _pooled_factorial(rows, threshold)
    discovery_classification = str(discovery["discovery_classification"])
    replication_classification = str(pooled["classification"])
    classification_match = discovery_classification == replication_classification

    partner_required = discovery_classification in {"partner_specific", "both"}
    general_required = discovery_classification in {"general_teamwork", "both"}
    partner_fields = int(pooled["positive_partner_fields"])
    general_fields = int(pooled["positive_general_fields"])
    positive_requirements = (
        (not partner_required or partner_fields >= minimum_fields)
        and (not general_required or general_fields >= minimum_fields)
    )
    if discovery_classification == "neither":
        positive_requirements = (
            abs(float(pooled["partner_specific_effect"])) <= threshold
            and abs(float(pooled["general_teamwork_effect"])) <= threshold
        )

    result = {
        **pooled,
        "classification_match": classification_match,
        "discovery_classification": discovery_classification,
        "positive_requirements": positive_requirements,
        "replication_gate": classification_match and positive_requirements,
    }
    _write_json(output / "w4-07-replication.json", result)
    return result


def synthesize(
    discovery_path: str | Path,
    replication_path: str | Path,
    output_dir: str | Path,
) -> dict[str, Any]:
    discovery = _read_json(discovery_path)
    replication = _read_json(replication_path)
    classification = str(discovery["discovery_classification"])
    replicated = bool(replication["replication_gate"])
    if replicated:
        status = {
            "both": "w4_partner_specific_and_general_teamwork_replicated",
            "partner_specific": "w4_partner_specific_capital_replicated",
            "general_teamwork": "w4_general_teamwork_replicated",
            "neither": "w4_no_coordination_capital_detected",
        }[classification]
    else:
        status = "w4_discovery_not_replicated"
    result = {
        "discovery_classification": classification,
        "replication_classification": replication["classification"],
        "replication_gate": replicated,
        "status": status,
        "w4_03_general_teamwork_effect": discovery["w4_03"]["general_teamwork_effect"],
        "w4_03_partner_specific_effect": discovery["w4_03"]["partner_specific_effect"],
        "w4_07_general_teamwork_effect": replication["general_teamwork_effect"],
        "w4_07_partner_specific_effect": replication["partner_specific_effect"],
        "w4_07_positive_general_fields": replication["positive_general_fields"],
        "w4_07_positive_partner_fields": replication["positive_partner_fields"],
    }
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    _write_json(output / "w4-synthesis.json", result)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    discover_parser = subparsers.add_parser("discover")
    discover_parser.add_argument("capsules", type=Path)
    discover_parser.add_argument("missions", type=Path)
    discover_parser.add_argument("campaign", type=Path)
    discover_parser.add_argument("output", type=Path)

    replicate_parser = subparsers.add_parser("replicate")
    replicate_parser.add_argument("capsules", type=Path)
    replicate_parser.add_argument("missions", type=Path)
    replicate_parser.add_argument("campaign", type=Path)
    replicate_parser.add_argument("discovery", type=Path)
    replicate_parser.add_argument("output", type=Path)

    synthesize_parser = subparsers.add_parser("synthesize")
    synthesize_parser.add_argument("discovery", type=Path)
    synthesize_parser.add_argument("replication", type=Path)
    synthesize_parser.add_argument("output", type=Path)

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
