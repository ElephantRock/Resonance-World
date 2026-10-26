"""Machine-checkable contract for the G1 v9 world-time adaptation scenario.

Pre-freeze hardening edition: the contract now pins the shared-acquisition
topology (A/B share one acquisition path and fork only at the treatment
point), the multi-context evaluation design, and the call-budget fields of
the later freeze file. It is data, not behaviour; the runner validates its
schedule against these values before executing anything.

This gate authorizes no provider execution of any kind.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from resonance_world.adapters import sha256_json

CONTRACT_SCHEMA = "g1-v9-contract-v2"

SCENARIO_ID = "g1-v9-world-time-adaptation"

#: Virtual ticks of the shared acquisition path (A/B common history).
ACQUISITION_TICKS = 500
#: Virtual ticks of the paired post-treatment measurement (A and B).
MEASUREMENT_TICKS = 500
#: Frozen-policy snapshot tick (arm C forks here and stops learning).
FREEZE_TICK = 400
#: One agent decision every DECISION_CADENCE ticks.
DECISION_CADENCE = 5
#: Number of independent task contexts (counterbalanced at the switch).
CONTEXT_COUNT = 4
#: Checkpoint ticks on the acquisition path.
CHECKPOINT_TICKS = (250, 400, 500)
#: Checkpoint ticks inside the paired measurement (absolute ticks).
MEASUREMENT_CHECKPOINTS = (750, 1000)

#: Branch ids. The acquisition branch is the shared A/B history.
ACQUISITION_BRANCH = "acquisition"
ARM_A_BRANCH = "arm-a-adaptive"
ARM_B_BRANCH = "arm-b-ablated"
ARM_C_BRANCH = "arm-c-frozen"
ARM_D_BRANCH = "arm-d-canonical"

#: Rules provenance pinned into the machine fingerprint.
RULES_VERSION = "g1-v9-rules-v2"

#: Planned provider call budget for the later scientific gate (frozen there).
PLANNED_PROVIDER_CALL_BUDGET = 0
#: Maximum physical provider sends authorized by THIS gate (none).
MAX_PROVIDER_SENDS_THIS_GATE = 0


@dataclass(frozen=True, slots=True)
class G1V9Contract:
    """The pinned, digestable definition of one G1 v9 integration gate."""

    scenario_id: str = SCENARIO_ID
    acquisition_ticks: int = ACQUISITION_TICKS
    measurement_ticks: int = MEASUREMENT_TICKS
    freeze_tick: int = FREEZE_TICK
    decision_cadence: int = DECISION_CADENCE
    context_count: int = CONTEXT_COUNT
    acquisition_checkpoints: tuple[int, ...] = field(default=CHECKPOINT_TICKS)
    measurement_checkpoints: tuple[int, ...] = field(default=MEASUREMENT_CHECKPOINTS)
    arm_a_branch: str = ARM_A_BRANCH
    arm_b_branch: str = ARM_B_BRANCH
    arm_c_branch: str = ARM_C_BRANCH
    arm_d_branch: str = ARM_D_BRANCH
    rules_version: str = RULES_VERSION
    external_dependencies: tuple[tuple[str, str], ...] = ()
    max_provider_sends_this_gate: int = MAX_PROVIDER_SENDS_THIS_GATE
    planned_provider_call_budget: int = PLANNED_PROVIDER_CALL_BUDGET

    def __post_init__(self) -> None:
        if self.acquisition_ticks <= 0 or self.measurement_ticks <= 0:
            raise ValueError("acquisition and measurement ticks must be positive")
        if not 0 < self.freeze_tick < self.acquisition_ticks:
            raise ValueError("freeze_tick must lie inside the acquisition path")
        if self.decision_cadence <= 0:
            raise ValueError("decision_cadence must be positive")
        if self.context_count < 2:
            raise ValueError("context_count must allow counterbalancing")
        if self.context_count % 2 != 0:
            raise ValueError("context_count must be even for balanced switching")
        if self.max_provider_sends_this_gate != 0:
            raise ValueError("the integration gate authorizes zero provider sends")
        for tick in self.acquisition_checkpoints:
            if not 0 < tick <= self.acquisition_ticks:
                raise ValueError("acquisition checkpoints must lie on the path")
        for tick in self.measurement_checkpoints:
            if not self.acquisition_ticks < tick <= self.acquisition_ticks + self.measurement_ticks:
                raise ValueError("measurement checkpoints must lie in the measurement tail")

    @property
    def arm_branches(self) -> tuple[str, ...]:
        return (self.arm_a_branch, self.arm_b_branch, self.arm_c_branch, self.arm_d_branch)

    @property
    def ablated_branch(self) -> str:
        return self.arm_b_branch

    def decisions_on_path(self, ticks: int) -> int:
        """Return the number of prescribed decisions on a path of ``ticks``."""

        return ticks // self.decision_cadence

    def digest(self) -> str:
        """Return the canonical contract digest for freeze records."""

        return sha256_json(
            {
                "schema": CONTRACT_SCHEMA,
                "scenario_id": self.scenario_id,
                "acquisition_ticks": self.acquisition_ticks,
                "measurement_ticks": self.measurement_ticks,
                "freeze_tick": self.freeze_tick,
                "decision_cadence": self.decision_cadence,
                "context_count": self.context_count,
                "acquisition_checkpoints": list(self.acquisition_checkpoints),
                "measurement_checkpoints": list(self.measurement_checkpoints),
                "arm_a_branch": self.arm_a_branch,
                "arm_b_branch": self.arm_b_branch,
                "arm_c_branch": self.arm_c_branch,
                "arm_d_branch": self.arm_d_branch,
                "rules_version": self.rules_version,
                "external_dependencies": [
                    {"name": name, "version": version}
                    for name, version in self.external_dependencies
                ],
                "max_provider_sends_this_gate": self.max_provider_sends_this_gate,
                "planned_provider_call_budget": self.planned_provider_call_budget,
            }
        )

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
