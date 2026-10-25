"""Machine-checkable contract for the G1 v9 world-time adaptation scenario.

The contract pins the timeline, the arms, the measurement schedule, and the
rule provenance of the G1 v9 integration gate. It is data, not behaviour:
the runner validates its schedule against these values before executing
anything, and the scenario machine is built with the contract's
``rules_version`` so every branch fingerprint is bound to these rules.

This gate authorizes no provider execution of any kind.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from resonance_world.adapters import sha256_json

CONTRACT_SCHEMA = "g1-v9-contract-v1"

SCENARIO_ID = "g1-v9-world-time-adaptation"

#: Total virtual ticks per experimental branch.
TOTAL_TICKS = 1_000
#: World tick at which the hidden rule switches from P0 to P1.
RULE_SWITCH_TICK = 500
#: Frozen-policy snapshot tick (arm C stops learning here).
FREEZE_TICK = 400
#: One agent decision every DECISION_CADENCE ticks.
DECISION_CADENCE = 5
#: Checkpoint ticks recorded on every branch.
CHECKPOINT_TICKS = (250, 500, 750)

#: Public, harmless ordering labels (the hidden rule selects which is rewarded).
ORDERINGS = ("AB", "BA")

#: Branch ids, in canonical arm order A, B, C, D.
ARM_BRANCHES = (
    "arm-a-adaptive",
    "arm-b-ablated",
    "arm-c-frozen",
    "arm-d-canonical",
)

#: The branch that receives the explicit ablation transaction.
ABLATED_BRANCH = "arm-b-ablated"

#: Rules provenance pinned into the machine fingerprint.
RULES_VERSION = "g1-v9-rules-v1"


@dataclass(frozen=True, slots=True)
class G1V9Contract:
    """The pinned, digestable definition of one G1 v9 integration gate."""

    scenario_id: str = SCENARIO_ID
    total_ticks: int = TOTAL_TICKS
    rule_switch_tick: int = RULE_SWITCH_TICK
    freeze_tick: int = FREEZE_TICK
    decision_cadence: int = DECISION_CADENCE
    checkpoint_ticks: tuple[int, ...] = field(default=CHECKPOINT_TICKS)
    arm_branches: tuple[str, ...] = field(default=ARM_BRANCHES)
    ablated_branch: str = ABLATED_BRANCH
    rules_version: str = RULES_VERSION
    external_dependencies: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        if self.total_ticks <= 0:
            raise ValueError("total_ticks must be positive")
        if not 0 < self.rule_switch_tick < self.total_ticks:
            raise ValueError("rule_switch_tick must lie inside the run")
        if not 0 < self.freeze_tick <= self.rule_switch_tick:
            raise ValueError("freeze_tick must precede the rule switch")
        if self.decision_cadence <= 0:
            raise ValueError("decision_cadence must be positive")
        if len(set(self.arm_branches)) != len(self.arm_branches):
            raise ValueError("arm branches must be unique")
        if self.ablated_branch not in self.arm_branches:
            raise ValueError("ablated branch must be one of the arms")
        for tick in self.checkpoint_ticks:
            if not 0 < tick <= self.total_ticks:
                raise ValueError("checkpoint ticks must lie inside the run")

    def digest(self) -> str:
        """Return the canonical contract digest for freeze records."""

        return sha256_json(
            {
                "schema": CONTRACT_SCHEMA,
                "scenario_id": self.scenario_id,
                "total_ticks": self.total_ticks,
                "rule_switch_tick": self.rule_switch_tick,
                "freeze_tick": self.freeze_tick,
                "decision_cadence": self.decision_cadence,
                "checkpoint_ticks": list(self.checkpoint_ticks),
                "arm_branches": list(self.arm_branches),
                "ablated_branch": self.ablated_branch,
                "rules_version": self.rules_version,
                "external_dependencies": [
                    {"name": name, "version": version}
                    for name, version in self.external_dependencies
                ],
            }
        )

    def epoch_of(self, tick: int) -> int:
        """Return the rule epoch (0 = P0, 1 = P1) governing ``tick``."""

        if tick < 0 or tick >= self.total_ticks:
            raise ValueError("tick outside the contracted run")
        return 0 if tick < self.rule_switch_tick else 1

    def with_fingerprint_kwargs(self) -> dict[str, object]:
        """Keyword arguments binding a StateMachine to this contract."""

        return {
            "rules_version": self.rules_version,
            "external_dependencies": {
                name: version for name, version in self.external_dependencies
            },
        }


def default_contract() -> G1V9Contract:
    """Return the default pinned contract for the integration gate."""

    return G1V9Contract()
