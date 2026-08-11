"""W5 persistent-organization and institutional-memory experiments."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from .w4a_joint_learning import (
    CommunicationPolicy,
    IndividualState,
    JointController,
    JointEnvironment,
    JointLearningSession,
    JointMission,
    RelationshipStateStore,
)
from .w5a_organization import (
    STRATEGIES,
    OrganizationController,
    OrganizationEpisode,
    OrganizationState,
    Strategy,
)

Regime = Literal["specialist", "balanced"]


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


def _uniform(*parts: object) -> float:
    payload = "|".join(str(part) for part in parts).encode()
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big") / 2**64


def _stable_key(field_id: str, agent_id: str) -> bytes:
    return hashlib.sha256(f"w5-roster|{field_id}|{agent_id}".encode()).digest()


@dataclass(frozen=True, slots=True)
class InstitutionMission:
    public: JointMission
    regime: Regime


@dataclass(frozen=True, slots=True)
class FieldDesign:
    field_id: str
    initial_members: tuple[IndividualState, ...]
    replacement_pool: tuple[IndividualState, ...]

    def replacement_roster(self, count: int) -> list[IndividualState]:
        if count < 0 or count > len(self.initial_members):
            raise ValueError("invalid turnover count")
        retained = list(self.initial_members[: len(self.initial_members) - count])
        replacements = list(self.replacement_pool[:count])
        return retained + replacements


def _mission(row: dict[str, Any]) -> InstitutionMission:
    return InstitutionMission(
        public=JointMission(
            mission_id=str(row["mission_id"]),
            context=str(row["context"]),
            lead_skill=str(row["lead_skill"]),
            support_skill=str(row["support_skill"]),
        ),
        regime=str(row["regime"]),  # type: ignore[arg-type]
    )


def _field_design(field_id: str, rows: list[dict[str, Any]], roster_size: int) -> FieldDesign:
    agents = [
        IndividualState(
            str(row["agent_id"]),
            {str(skill): int(value) for skill, value in row["practice_by_skill"].items()},
        )
        for row in rows
    ]
    ordered = sorted(agents, key=lambda item: _stable_key(field_id, item.agent_id))
    if len(ordered) != 12 or roster_size != 4:
        raise ValueError("W5 requires 12 source agents and a four-member organization")
    return FieldDesign(field_id, tuple(ordered[:4]), tuple(ordered[4:]))


def _group_capsules(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(str(row["field_id"]), []).append(row)
    return grouped


def _load_designs(
    capsules_path: str | Path,
    allowed_fields: list[str],
    roster_size: int,
) -> dict[str, FieldDesign]:
    grouped = _group_capsules(_read_jsonl(capsules_path))
    result: dict[str, FieldDesign] = {}
    for field_id in allowed_fields:
        if field_id not in grouped:
            raise ValueError(f"missing field {field_id}")
        result[field_id] = _field_design(field_id, grouped[field_id], roster_size)
    return result


@dataclass(frozen=True, slots=True)
class InstitutionEnvironment:
    joint: JointEnvironment = JointEnvironment()

    def evaluate(
        self,
        first: IndividualState,
        second: IndividualState,
        mission: InstitutionMission,
        *,
        seed: int,
    ) -> bool:
        public = mission.public
        if mission.regime == "specialist":
            from .w4a_joint_learning import JointAction

            return self.joint.evaluate(
                first,
                second,
                public,
                JointAction(first.agent_id, "lead"),
                JointAction(second.agent_id, "support"),
                seed=seed,
            )

        first_cross = (
            self.joint.role_probability(first, public.lead_skill)
            * self.joint.role_probability(first, public.support_skill)
        ) ** 0.5
        second_cross = (
            self.joint.role_probability(second, public.lead_skill)
            * self.joint.role_probability(second, public.support_skill)
        ) ** 0.5
        first_ok = _uniform("w5-balanced", public.mission_id, seed, "first") < first_cross
        second_ok = _uniform("w5-balanced", public.mission_id, seed, "second") < second_cross
        return first_ok and second_ok


def _forced_decision(
    organization: OrganizationState,
    mission: JointMission,
    strategy: Strategy,
):
    forced = copy.deepcopy(organization)
    forced.memory.strategy_attempts[mission.context] = {
        item: int(item == strategy) for item in STRATEGIES
    }
    forced.memory.strategy_successes[mission.context] = {
        item: int(item == strategy) for item in STRATEGIES
    }
    return OrganizationController().select(forced, mission)


def _train(
    organization: OrganizationState,
    missions: list[InstitutionMission],
    depth: int,
    strategy_order: list[Strategy],
    *,
    salt: str,
) -> None:
    environment = InstitutionEnvironment()
    for round_index in range(depth):
        for mission_index, mission in enumerate(missions):
            for strategy_index, strategy in enumerate(strategy_order):
                decision = _forced_decision(organization, mission.public, strategy)
                success = environment.evaluate(
                    decision.lead,
                    decision.support,
                    mission,
                    seed=_seed(
                        organization.organization_id,
                        salt,
                        round_index,
                        mission_index,
                        strategy_index,
                    ),
                )
                organization.memory.observe(
                    OrganizationEpisode(
                        mission_id=mission.public.mission_id,
                        context=mission.public.context,
                        strategy=strategy,
                        lead_agent_id=decision.lead.agent_id,
                        support_agent_id=decision.support.agent_id,
                        success=success,
                    )
                )


def _evaluate(
    organization: OrganizationState,
    missions: list[InstitutionMission],
    trials: int,
    *,
    salt: str,
) -> float:
    controller = OrganizationController()
    environment = InstitutionEnvironment()
    outcomes: list[float] = []
    for mission_index, mission in enumerate(missions):
        decision = controller.select(organization, mission.public)
        for trial in range(trials):
            outcomes.append(
                float(
                    environment.evaluate(
                        decision.lead,
                        decision.support,
                        mission,
                        seed=_seed(
                            organization.organization_id,
                            salt,
                            mission_index,
                            trial,
                        ),
                    )
                )
            )
    return _mean(outcomes)


def _organization(
    design: FieldDesign,
    organization_id: str,
    members: list[IndividualState] | None = None,
) -> OrganizationState:
    roster = members if members is not None else list(design.initial_members)
    return OrganizationState(organization_id, {item.agent_id: item for item in roster})


def _classification(effect: float, threshold: float) -> str:
    if effect > threshold:
        return "institutional_memory"
    if effect < -threshold:
        return "institutional_harm"
    return "no_institutional_memory"


def _field_turnover_factorial(
    design: FieldDesign,
    formation: list[InstitutionMission],
    evaluation: list[InstitutionMission],
    depth: int,
    trials: int,
    strategy_order: list[Strategy],
    threshold: float,
) -> dict[str, Any]:
    organization_id = f"w5-org-{design.field_id}"
    trained = _organization(design, organization_id)
    _train(trained, formation, depth, strategy_order, salt="formation")

    same_members = copy.deepcopy(trained)
    c1 = _evaluate(same_members, evaluation, trials, salt="factorial")

    replacement_roster = design.replacement_roster(len(design.initial_members))
    retained = copy.deepcopy(trained)
    retained.replace_members(replacement_roster)
    c2 = _evaluate(retained, evaluation, trials, salt="factorial")

    reset = copy.deepcopy(retained)
    reset.reset_memory()
    c3 = _evaluate(reset, evaluation, trials, salt="factorial")

    fresh = _organization(design, f"fresh-{design.field_id}", replacement_roster)
    c4 = _evaluate(fresh, evaluation, trials, salt="factorial")

    effect = c2 - c3
    return {
        "c1_same_members_retained_memory": c1,
        "c2_replacement_members_retained_memory": c2,
        "c3_same_replacement_members_memory_reset": c3,
        "c4_fresh_organization_same_replacement_members": c4,
        "classification": _classification(effect, threshold),
        "institutional_memory_effect": effect,
    }


def _pair_handoff(
    design: FieldDesign,
    formation: list[InstitutionMission],
    evaluation: list[InstitutionMission],
    depth: int,
    trials: int,
) -> dict[str, float]:
    first, second, stranger_a, stranger_b = design.replacement_pool[4:8]
    communication = CommunicationPolicy(1)
    relationships = RelationshipStateStore()
    session = JointLearningSession(
        JointEnvironment(),
        JointController(),
        relationships,
        communication,
    )
    for episode_index in range(depth):
        mission = formation[episode_index % len(formation)].public
        session.run_episode(
            first,
            second,
            mission,
            seed=_seed(design.field_id, "pair-formation", episode_index),
        )

    def score(
        pair: tuple[IndividualState, IndividualState],
        store: RelationshipStateStore,
        salt: str,
    ) -> float:
        environment = JointEnvironment()
        controller = JointController()
        values: list[float] = []
        for mission_index, spec in enumerate(evaluation):
            mission = spec.public
            for trial in range(trials):
                first_message = controller.preferred_role(pair[0], mission)
                second_message = controller.preferred_role(pair[1], mission)
                first_action = controller.choose_action(
                    pair[0],
                    pair[1],
                    mission,
                    store,
                    communication,
                    partner_message=second_message,
                )
                second_action = controller.choose_action(
                    pair[1],
                    pair[0],
                    mission,
                    store,
                    communication,
                    partner_message=first_message,
                )
                values.append(
                    float(
                        environment.evaluate(
                            pair[0],
                            pair[1],
                            mission,
                            first_action,
                            second_action,
                            seed=_seed(design.field_id, salt, mission_index, trial),
                        )
                    )
                )
        return _mean(values)

    intact = score((first, second), relationships, "pair-handoff")
    reset = score((first, second), RelationshipStateStore(), "pair-handoff")
    strangers = score((stranger_a, stranger_b), RelationshipStateStore(), "pair-handoff")
    return {
        "intact_pair": intact,
        "same_pair_relationship_reset": reset,
        "stranger_pair": strangers,
        "intact_minus_reset": intact - reset,
        "intact_minus_strangers": intact - strangers,
    }


def _decompose_memory(
    trained: OrganizationState,
    evaluation: list[InstitutionMission],
    trials: int,
) -> dict[str, float]:
    full = _evaluate(trained, evaluation, trials, salt="memory-decomposition")

    no_archive = copy.deepcopy(trained)
    no_archive.memory.episodes.clear()
    archive_removed = _evaluate(
        no_archive, evaluation, trials, salt="memory-decomposition"
    )

    no_continuity = copy.deepcopy(trained)
    no_continuity.memory.last_successful_pair.clear()
    continuity_removed = _evaluate(
        no_continuity, evaluation, trials, salt="memory-decomposition"
    )

    no_procedure = copy.deepcopy(trained)
    no_procedure.memory.strategy_attempts.clear()
    no_procedure.memory.strategy_successes.clear()
    procedure_removed = _evaluate(
        no_procedure, evaluation, trials, salt="memory-decomposition"
    )

    reset = copy.deepcopy(trained)
    reset.reset_memory()
    fully_reset = _evaluate(reset, evaluation, trials, salt="memory-decomposition")

    return {
        "full": full,
        "archive_removed": archive_removed,
        "continuity_removed": continuity_removed,
        "procedure_removed": procedure_removed,
        "fully_reset": fully_reset,
        "archive_contribution": full - archive_removed,
        "continuity_contribution": full - continuity_removed,
        "procedure_contribution": full - procedure_removed,
        "total_memory_contribution": full - fully_reset,
    }


def discover(
    capsules_path: str | Path,
    missions_path: str | Path,
    campaign_path: str | Path,
    output_dir: str | Path,
) -> dict[str, Any]:
    missions_raw = _read_json(missions_path)["discovery"]
    campaign = _read_json(campaign_path)
    formation = [_mission(row) for row in missions_raw["formation"]]
    evaluation = [_mission(row) for row in missions_raw["evaluation"]]
    roster_size = int(campaign["roster_size"])
    trials = int(campaign["evaluation_trials_per_mission"])
    threshold = float(campaign["effect_threshold"])
    depth = int(campaign["deep_history_depth"])
    depths = [int(item) for item in campaign["history_depths"]]
    strategy_order = [str(item) for item in campaign["formation_strategy_order"]]

    calibration = _load_designs(
        capsules_path, list(campaign["calibration_fields"]), roster_size
    )
    heldout = _load_designs(capsules_path, list(campaign["discovery_fields"]), roster_size)

    formation_rows: list[dict[str, Any]] = []
    curve: dict[str, float] = {}
    for history_depth in depths:
        values: list[float] = []
        fresh_values: list[float] = []
        for field_id, design in calibration.items():
            organization = _organization(design, f"curve-{field_id}")
            _train(
                organization,
                formation,
                history_depth,
                strategy_order,  # type: ignore[arg-type]
                salt=f"curve-{history_depth}",
            )
            persistent = _evaluate(
                organization,
                evaluation,
                trials,
                salt=f"curve-eval-{history_depth}",
            )
            fresh = _organization(design, f"curve-{field_id}")
            fresh_score = _evaluate(
                fresh,
                evaluation,
                trials,
                salt=f"curve-eval-{history_depth}",
            )
            values.append(persistent)
            fresh_values.append(fresh_score)
            formation_rows.append(
                {
                    "depth": history_depth,
                    "field_id": field_id,
                    "persistent": persistent,
                    "fresh": fresh_score,
                    "lift": persistent - fresh_score,
                }
            )
        curve[str(history_depth)] = _mean(values)

    w5_01 = {
        "persistent_mean": curve[str(depth)],
        "fresh_mean": _mean(
            [
                float(row["fresh"])
                for row in formation_rows
                if int(row["depth"]) == depth
            ]
        ),
    }
    w5_01["formation_lift"] = float(w5_01["persistent_mean"]) - float(
        w5_01["fresh_mean"]
    )
    w5_02 = {
        "history_curve": curve,
        "rows": formation_rows,
        "deep_minus_zero": curve[str(depth)] - curve[str(depths[0])],
    }

    factorial_rows: list[dict[str, Any]] = []
    pair_rows: list[dict[str, Any]] = []
    decomposition_rows: list[dict[str, Any]] = []
    turnover_rows: list[dict[str, Any]] = []
    for field_id, design in heldout.items():
        factorial = _field_turnover_factorial(
            design,
            formation,
            evaluation,
            depth,
            trials,
            strategy_order,  # type: ignore[arg-type]
            threshold,
        )
        factorial["field_id"] = field_id
        factorial_rows.append(factorial)

        pair_result = _pair_handoff(
            design,
            formation,
            evaluation,
            int(campaign["pair_training_depth"]),
            trials,
        )
        pair_result["field_id"] = field_id
        pair_rows.append(pair_result)

        trained = _organization(design, f"decompose-{field_id}")
        _train(
            trained,
            formation,
            depth,
            strategy_order,  # type: ignore[arg-type]
            salt="decomposition-formation",
        )
        trained.replace_members(design.replacement_roster(roster_size))
        decomposition = _decompose_memory(trained, evaluation, trials)
        decomposition["field_id"] = field_id
        decomposition_rows.append(decomposition)

        for turnover_count in [int(item) for item in campaign["turnover_counts"]]:
            retained = _organization(design, f"turnover-{field_id}")
            _train(
                retained,
                formation,
                depth,
                strategy_order,  # type: ignore[arg-type]
                salt="turnover-formation",
            )
            retained.replace_members(design.replacement_roster(turnover_count))
            retained_score = _evaluate(
                retained,
                evaluation,
                trials,
                salt=f"turnover-{turnover_count}",
            )
            reset = copy.deepcopy(retained)
            reset.reset_memory()
            reset_score = _evaluate(
                reset,
                evaluation,
                trials,
                salt=f"turnover-{turnover_count}",
            )
            turnover_rows.append(
                {
                    "field_id": field_id,
                    "turnover_count": turnover_count,
                    "turnover_fraction": turnover_count / roster_size,
                    "retained": retained_score,
                    "reset": reset_score,
                    "memory_effect": retained_score - reset_score,
                }
            )

    institutional_effect = _mean(
        [float(row["institutional_memory_effect"]) for row in factorial_rows]
    )
    discovery_classification = _classification(institutional_effect, threshold)
    w5_03 = {
        "classification": discovery_classification,
        "institutional_memory_effect": institutional_effect,
        "positive_fields": sum(
            float(row["institutional_memory_effect"]) > 0 for row in factorial_rows
        ),
        "field_results": factorial_rows,
    }
    w5_04 = {
        "intact_minus_reset": _mean(
            [float(row["intact_minus_reset"]) for row in pair_rows]
        ),
        "intact_minus_strangers": _mean(
            [float(row["intact_minus_strangers"]) for row in pair_rows]
        ),
        "field_results": pair_rows,
    }
    w5_05 = {
        "archive_contribution": _mean(
            [float(row["archive_contribution"]) for row in decomposition_rows]
        ),
        "continuity_contribution": _mean(
            [float(row["continuity_contribution"]) for row in decomposition_rows]
        ),
        "procedure_contribution": _mean(
            [float(row["procedure_contribution"]) for row in decomposition_rows]
        ),
        "total_memory_contribution": _mean(
            [float(row["total_memory_contribution"]) for row in decomposition_rows]
        ),
        "field_results": decomposition_rows,
    }
    w5_06 = {
        "rows": turnover_rows,
        "mean_effect_by_turnover": {
            str(count): _mean(
                [
                    float(row["memory_effect"])
                    for row in turnover_rows
                    if int(row["turnover_count"]) == count
                ]
            )
            for count in [int(item) for item in campaign["turnover_counts"]]
        },
    }
    result = {
        "discovery_classification": discovery_classification,
        "w5_01": w5_01,
        "w5_02": w5_02,
        "w5_03": w5_03,
        "w5_04": w5_04,
        "w5_05": w5_05,
        "w5_06": w5_06,
    }
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    _write_json(output / "w5-discovery.json", result)
    return result


def replicate(
    capsules_path: str | Path,
    missions_path: str | Path,
    campaign_path: str | Path,
    discovery_path: str | Path,
    output_dir: str | Path,
) -> dict[str, Any]:
    missions_raw = _read_json(missions_path)["replication"]
    campaign = _read_json(campaign_path)
    discovery = _read_json(discovery_path)
    formation = [_mission(row) for row in missions_raw["formation"]]
    evaluation = [_mission(row) for row in missions_raw["evaluation"]]
    roster_size = int(campaign["roster_size"])
    trials = int(campaign["evaluation_trials_per_mission"])
    threshold = float(campaign["effect_threshold"])
    depth = int(campaign["deep_history_depth"])
    strategy_order = [str(item) for item in campaign["formation_strategy_order"]]
    minimum_fields = int(campaign["minimum_positive_replication_fields"])
    designs = _load_designs(
        capsules_path, list(campaign["replication_fields"]), roster_size
    )

    rows: list[dict[str, Any]] = []
    for field_id, design in designs.items():
        row = _field_turnover_factorial(
            design,
            formation,
            evaluation,
            depth,
            trials,
            strategy_order,  # type: ignore[arg-type]
            threshold,
        )
        row["field_id"] = field_id
        rows.append(row)

    effect = _mean([float(row["institutional_memory_effect"]) for row in rows])
    classification = _classification(effect, threshold)
    discovery_classification = str(discovery["discovery_classification"])
    positive_fields = sum(float(row["institutional_memory_effect"]) > 0 for row in rows)
    negative_fields = sum(float(row["institutional_memory_effect"]) < 0 for row in rows)

    if discovery_classification == "institutional_memory":
        requirements = effect > threshold and positive_fields >= minimum_fields
    elif discovery_classification == "institutional_harm":
        requirements = effect < -threshold and negative_fields >= minimum_fields
    else:
        requirements = abs(effect) <= threshold

    result = {
        "classification": classification,
        "classification_match": classification == discovery_classification,
        "discovery_classification": discovery_classification,
        "field_results": rows,
        "institutional_memory_effect": effect,
        "negative_fields": negative_fields,
        "positive_fields": positive_fields,
        "replication_gate": classification == discovery_classification and requirements,
    }
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    _write_json(output / "w5-07-replication.json", result)
    return result


def synthesize(
    discovery_path: str | Path,
    replication_path: str | Path,
    output_dir: str | Path,
) -> dict[str, Any]:
    discovery = _read_json(discovery_path)
    replication = _read_json(replication_path)
    replicated = bool(replication["replication_gate"])
    classification = str(discovery["discovery_classification"])
    if replicated:
        status = {
            "institutional_memory": "w5_institutional_memory_replicated",
            "institutional_harm": "w5_institutional_memory_harm_replicated",
            "no_institutional_memory": "w5_no_institutional_memory_detected",
        }[classification]
    else:
        status = "w5_discovery_not_replicated"
    result = {
        "status": status,
        "discovery_classification": classification,
        "replication_classification": replication["classification"],
        "replication_gate": replicated,
        "w5_03_institutional_memory_effect": discovery["w5_03"][
            "institutional_memory_effect"
        ],
        "w5_07_institutional_memory_effect": replication["institutional_memory_effect"],
        "w5_07_positive_fields": replication["positive_fields"],
        "w5_07_negative_fields": replication["negative_fields"],
    }
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    _write_json(output / "w5-synthesis.json", result)
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
