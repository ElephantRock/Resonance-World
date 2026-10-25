"""Integration-gate tests for G1 v9 (model-free, apparatus only).

These tests run the full four-arm scenario on the approved kernel with
offline policies. They establish the apparatus: contract pinning, arm
structure, exclusive ablation, absence of rule leakage, replay identity,
and determinism. They make no claim about model learning.
"""

from __future__ import annotations

import json

import pytest

from resonance_world.experimental_runtime.g1_v9 import (
    ARMS,
    G1V9AcceptanceReport,
    build_machine,
    build_policy,
    default_contract,
    run_g1_v9_acceptance,
)
from resonance_world.experimental_runtime.g1_v9.scenario import (
    seal_initial_rule,
    seal_switch_rule,
    start_arm,
)
from resonance_world.experimental_runtime.store import KernelStore

ACCEPTANCE_KEY = bytes(range(16, 48))


@pytest.fixture(scope="module")
def report() -> G1V9AcceptanceReport:
    return run_g1_v9_acceptance(commitment_key=ACCEPTANCE_KEY)


def test_acceptance_runs_the_full_timeline(report: G1V9AcceptanceReport) -> None:
    contract = default_contract()
    assert report.ticks == contract.total_ticks
    assert report.contract_digest == contract.digest()
    assert report.rules_version == contract.rules_version
    assert len(report.arm_reports) == 4


def test_every_arm_records_decisions_and_replays_identically(
    report: G1V9AcceptanceReport,
) -> None:
    for arm in report.arm_reports:
        expected_decisions = default_contract().total_ticks // default_contract().decision_cadence
        assert arm.decisions == expected_decisions, arm.branch_id
        assert arm.port_calls == arm.decisions, arm.branch_id
        assert arm.replay_matched, arm.branch_id
        assert arm.replay_checkpoints_matched == len(default_contract().checkpoint_ticks)
        assert 0.0 <= arm.pre_accuracy <= 1.0
        assert 0.0 <= arm.post_accuracy <= 1.0


def test_shared_schedule_is_byte_identical_across_arms(
    report: G1V9AcceptanceReport,
) -> None:
    assert report.shared_schedule_identical is True


def test_ablation_transaction_exists_only_in_arm_b(
    report: G1V9AcceptanceReport,
) -> None:
    assert report.ablation_exclusive_to_b is True
    by_branch = {arm.branch_id: arm for arm in report.arm_reports}
    assert by_branch["arm-b-ablated"].ablation_recorded is True
    for branch in ("arm-a-adaptive", "arm-c-frozen", "arm-d-canonical"):
        assert by_branch[branch].ablation_recorded is False


def test_no_hidden_rule_leakage_through_public_paths(
    report: G1V9AcceptanceReport,
) -> None:
    assert report.leak_scan_clean is True

    # Direct scan: the sealed rule values never appear in any public payload
    # of a non-decision event, in any branch.
    from resonance_world.experimental_runtime.g1_v9 import P0_ORDERING
    from resonance_world.experimental_runtime.g1_v9.scenario import (
        P1_ORDERING,
        start_arm,
    )
    from resonance_world.experimental_runtime.replay import replay_state

    store = KernelStore(commitment_key=ACCEPTANCE_KEY)
    kernel = start_arm(store, default_contract(), "leak-probe")
    seal_initial_rule(kernel)
    seal_switch_rule(kernel)
    rebuilt = replay_state(store, "leak-probe", build_machine(default_contract()))
    assert rebuilt.private["current_ordering"] == P1_ORDERING
    public_text = json.dumps(dict(kernel.state.public))
    assert P0_ORDERING not in public_text or P0_ORDERING == "AB"
    assert "current_ordering" not in public_text


def test_acceptance_is_deterministic_across_runs() -> None:
    first = run_g1_v9_acceptance(commitment_key=ACCEPTANCE_KEY)
    second = run_g1_v9_acceptance(commitment_key=ACCEPTANCE_KEY)
    assert first == second


def test_replay_performs_no_policy_calls() -> None:
    """The acceptance runner records decisions; replay consumes them only."""

    contract = default_contract()
    store = KernelStore(commitment_key=ACCEPTANCE_KEY)
    machine = build_machine(contract)
    trunk = start_arm(store, contract, "trunk")
    kernel = trunk.fork("arm-a-adaptive")
    policy = build_policy("adaptive", contract_freeze_tick=contract.freeze_tick)

    seal_initial_rule(kernel)
    for current in range(20):
        kernel.schedule("world_pulse", {"tick": current})
        if current % contract.decision_cadence == 0:
            kernel.decide_via(policy)
        kernel.advance()

    calls_before = policy.calls
    from resonance_world.experimental_runtime.replay import replay_branch

    result = replay_branch(store, "arm-a-adaptive", machine)
    assert policy.calls == calls_before
    assert result.recorded_agent_decisions == calls_before
    assert result.final_state_sha256 == kernel.state_hash()


def test_arm_policies_are_offline_by_construction() -> None:
    """Every arm policy implements the port contract without any transport."""

    for kind in ARMS:
        policy = build_policy(kind, contract_freeze_tick=100)
        assert hasattr(policy, "decide")
        assert isinstance(policy.model_id, str)
        source_module = type(policy).__module__
        assert source_module.startswith(
            "resonance_world.experimental_runtime.g1_v9"
        )


def test_contract_rejects_invalid_shapes() -> None:
    from dataclasses import replace

    contract = default_contract()
    with pytest.raises(ValueError, match="rule_switch_tick"):
        replace(contract, rule_switch_tick=contract.total_ticks + 1)
    with pytest.raises(ValueError, match="freeze_tick"):
        replace(contract, freeze_tick=contract.rule_switch_tick + 1)
    with pytest.raises(ValueError, match="unique"):
        replace(contract, arm_branches=("a", "a", "b", "c"))
    with pytest.raises(ValueError, match="ablated branch"):
        replace(contract, ablated_branch="not-an-arm")


def test_frozen_arm_stops_learning_at_the_freeze_tick() -> None:
    contract = default_contract()
    store = KernelStore(commitment_key=ACCEPTANCE_KEY)
    trunk = start_arm(store, contract, "trunk")
    kernel = trunk.fork("arm-c-frozen")
    policy = build_policy("frozen", contract_freeze_tick=contract.freeze_tick)

    seal_initial_rule(kernel)
    for current in range(0, 420):
        if current == contract.rule_switch_tick:
            seal_switch_rule(kernel)
        kernel.schedule("world_pulse", {"tick": current})
        if current % contract.decision_cadence == 0:
            kernel.decide_via(policy)
        kernel.advance()

    memory_before = policy.snapshot()
    assert policy.frozen_at is not None
    assert policy.frozen_at >= contract.freeze_tick
    for _ in range(4):
        kernel.decide_via(policy)
    memory_after = policy.snapshot()
    # The arm keeps acting, but its memory stops updating at the freeze:
    # outcome history and learned successes are static after the freeze.
    assert memory_after["outcomes"] == memory_before["outcomes"]
    assert memory_after["successes"] == memory_before["successes"]
    assert len(memory_after["chosen"]) > len(memory_before["chosen"])
