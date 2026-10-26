"""GLM-5.3 per-arm call contract: decision slots versus API sends.

This module is **data and arithmetic only**. It separates the
computational decision slots of the scenario (which exist in the
kernel) from the physical provider sends a scientific run would need,
and pins the per-arm backing policy for the freeze manifest.

Nothing here authorizes a provider call. The send cap of the
integration gate is zero and stays zero until a separate authorization
names the code commit, provider, model, and hard send ceiling.
"""

from __future__ import annotations

from dataclasses import dataclass

from .contract import ACQUISITION_BRANCH, G1V9Contract

PROVIDER = "zai"
MODEL = "glm-5.3"
ENDPOINT_FAMILY = "zai-coding-plan-chat-completions"
RUNTIME_SPEC = "hermes-agent 0.8.0; openai-sdk 2.21.0; httpx 0.28.1 (pinned at authorization)"


@dataclass(frozen=True, slots=True)
class ArmCallContract:
    """The pinned call semantics of one arm for the scientific gate."""

    branch_id: str
    model_backed: bool
    decision_slots: int
    calls_per_decision: int = 1
    reasoning_or_tool_calls: int = 0
    retries_or_replacements: bool = False

    @property
    def model_sends(self) -> int:
        """Physical provider sends this arm would need per world."""

        if not self.model_backed:
            return 0
        return self.decision_slots * self.calls_per_decision


def arm_call_contracts(contract: G1V9Contract) -> dict[str, ArmCallContract]:
    """Return the per-arm call contracts for ``contract``.

    Backing policy (pinned for the freeze candidate): the shared
    acquisition path and arms A, B, C are model-backed; arm D is the
    canonical computational baseline and never calls the provider.
    Exactly one call per decision slot, no reasoning/tool extras, no
    retries or replacements.
    """

    slots = contract.decisions_on_path
    return {
        ACQUISITION_BRANCH: ArmCallContract(
            branch_id=ACQUISITION_BRANCH,
            model_backed=True,
            decision_slots=slots(contract.acquisition_ticks),
        ),
        contract.arm_a_branch: ArmCallContract(
            branch_id=contract.arm_a_branch,
            model_backed=True,
            decision_slots=slots(contract.measurement_ticks),
        ),
        contract.arm_b_branch: ArmCallContract(
            branch_id=contract.arm_b_branch,
            model_backed=True,
            decision_slots=slots(contract.measurement_ticks),
        ),
        contract.arm_c_branch: ArmCallContract(
            branch_id=contract.arm_c_branch,
            model_backed=True,
            decision_slots=slots(
                contract.acquisition_ticks
                + contract.measurement_ticks
                - contract.freeze_tick
            ),
        ),
        contract.arm_d_branch: ArmCallContract(
            branch_id=contract.arm_d_branch,
            model_backed=False,
            decision_slots=slots(
                contract.acquisition_ticks + contract.measurement_ticks
            ),
        ),
    }


def budget_summary(contract: G1V9Contract) -> dict[str, int]:
    """Return the decision-slot versus model-send arithmetic per world."""

    arms = arm_call_contracts(contract)
    decision_slots = sum(arm.decision_slots for arm in arms.values())
    model_sends = sum(arm.model_sends for arm in arms.values())
    computational_slots = decision_slots - model_sends
    return {
        "decision_slots_per_world": decision_slots,
        "model_sends_per_world": model_sends,
        "computational_slots_per_world": computational_slots,
    }
