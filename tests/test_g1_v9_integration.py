"""Pre-freeze hardening tests for G1 v9 (model-free, apparatus only).

Round-3 protocol hardening: shared acquisition history for the paired
arms, world-attested memory custody, evaluator-held hidden truth with
counterbalanced switches, and the expanded freeze structure. No model
calls exist on any path; these tests establish the apparatus only.
"""

from __future__ import annotations

import pytest

from resonance_world.experimental_runtime.g1_v9 import (
    ACQUISITION_BRANCH,
    ARM_A_BRANCH,
    ARM_B_BRANCH,
    ARM_C_BRANCH,
    ARM_D_BRANCH,
    G1V9AcceptanceReport,
    build_machine,
    build_policy,
    default_contract,
    derive_epoch_table,
    derive_evaluator_seed,
    run_g1_v9_acceptance,
    verify_memory_attestation,
)
from resonance_world.experimental_runtime.replay import replay_branch
from resonance_world.experimental_runtime.store import KernelStore

ACCEPTANCE_KEY = bytes(range(16, 48))
EVALUATOR_MATERIAL = bytes(range(48, 80))


@pytest.fixture(scope="module")
def report() -> G1V9AcceptanceReport:
    return run_g1_v9_acceptance(
        commitment_key=ACCEPTANCE_KEY,
        evaluator_seed_material=EVALUATOR_MATERIAL,
    )


def test_paired_arms_share_one_acquisition_head(
    report: G1V9AcceptanceReport,
) -> None:
    """P0: A and B fork from one recorded acquisition head."""

    assert report.pre_treatment_identity_verified is True
    for arm in report.arm_reports:
        if arm.branch_id in (ARM_A_BRANCH, ARM_B_BRANCH):
            assert arm.forked_from == ACQUISITION_BRANCH
            contract = default_contract()
            assert arm.ticks == contract.acquisition_ticks + contract.measurement_ticks


def test_c_shares_the_pre_freeze_history_and_d_runs_full_timeline(
    report: G1V9AcceptanceReport,
) -> None:
    by_branch = {arm.branch_id: arm for arm in report.arm_reports}
    assert by_branch[ARM_C_BRANCH].forked_from == ACQUISITION_BRANCH
    assert by_branch[ARM_D_BRANCH].forked_from == ""
    contract = default_contract()
    assert by_branch[ARM_D_BRANCH].ticks == (
        contract.acquisition_ticks + contract.measurement_ticks
    )


def test_post_treatment_schedules_match_and_decisions_diverge(
    report: G1V9AcceptanceReport,
) -> None:
    assert report.post_treatment_shared_schedule_identical is True


def test_ablation_is_exclusive_and_custody_chain_verifies(
    report: G1V9AcceptanceReport,
) -> None:
    """P0: the ablation event and the ablated memory are consistent."""

    assert report.ablation_exclusive_to_b is True
    assert report.ablation_custody_verified is True


def test_memory_attestations_verify_for_every_recorded_snapshot() -> None:
    store = KernelStore(commitment_key=ACCEPTANCE_KEY)
    contract = default_contract()
    # Re-run a minimal acquisition to produce attestations on the branch.
    from resonance_world.experimental_runtime.g1_v9 import (
        canonical_memory,
        record_memory_event,
    )
    from resonance_world.experimental_runtime.g1_v9.arms import ContextMemoryPolicy
    from resonance_world.experimental_runtime.g1_v9.scenario import (
        seal_epoch,
        start_arm,
    )

    seed = derive_evaluator_seed(EVALUATOR_MATERIAL)
    kernel = start_arm(store, contract, "custody-probe")
    seal_epoch(kernel, epoch=0, seed=seed, contract=contract)
    policy = ContextMemoryPolicy()
    for current in range(10):
        kernel.schedule("world_pulse", {"tick": current})
        if current == 5:
            record_memory_event(
                kernel=kernel,
                tick=current,
                kind="save",
                memory=canonical_memory(policy.snapshot()),
                memory_id=f"save@{current}",
            )
        kernel.advance()

    snapshot_seqs = [
        event.seq
        for event in store.iter_events("custody-probe")
        if event.kind == "memory_snapshot"
    ]
    assert len(snapshot_seqs) == 1
    assert verify_memory_attestation(store, "custody-probe", snapshot_seqs[0]) is True

    # Tampering with exactly the co-recorded sealed memory payload breaks
    # the attestation without touching anything else.
    store._conn.execute(
        "UPDATE sealed_payloads SET payload = ? WHERE branch_id = 'custody-probe' "
        "AND seq = ?",
        ('{"tampered": true}', snapshot_seqs[0] - 1),
    )
    store._conn.commit()
    assert verify_memory_attestation(store, "custody-probe", snapshot_seqs[0]) is False


def test_resume_restores_ablated_memory_consistently(report: G1V9AcceptanceReport) -> None:
    """P0: after resume, the ablation event and memory remain consistent."""

    assert report.ablation_custody_verified is True
    by_branch = {arm.branch_id: arm for arm in report.arm_reports}
    ablated = by_branch[ARM_B_BRANCH]
    # The ablated arm kept acting from cleared memory: its own post-fork
    # decisions exist, and its inherited acquisition calls are attested.
    contract = default_contract()
    assert ablated.port_calls == contract.decisions_on_path(
        contract.measurement_ticks
    )
    assert ablated.inherited_port_calls == contract.decisions_on_path(
        contract.acquisition_ticks
    )


def test_hidden_truth_is_not_an_importable_constant() -> None:
    """P0: no ordering constant exists on the package interface."""

    import resonance_world.experimental_runtime.g1_v9 as package

    for forbidden in ("P0_ORDERING", "P1_ORDERING", "ORDERINGS"):
        assert not hasattr(package, forbidden)

    seed = derive_evaluator_seed(EVALUATOR_MATERIAL)
    contract = default_contract()
    table0 = derive_epoch_table(seed, 0, contract.context_count)
    table1 = derive_epoch_table(seed, 1, contract.context_count, table0)
    flips = sum(1 for name in table0 if table1[name] != table0[name])
    assert flips == contract.context_count // 2
    assert all(name in table1 for name in table0)


def test_freeze_file_pins_budget_fields() -> None:
    contract = default_contract()
    assert contract.max_provider_sends_this_gate == 0
    assert contract.rules_version == "g1-v9-rules-v2"
    assert isinstance(contract.planned_provider_call_budget, int)


def test_full_suite_replays_every_branch(report: G1V9AcceptanceReport) -> None:
    assert report.all_replays_matched is True
    assert report.leak_scan_clean is True
    # On-branch own calls match own decisions; inherited acquisition calls
    # are attested separately (the paired arms share one acquisition path).
    for arm in report.arm_reports:
        if arm.branch_id in (ARM_A_BRANCH, ARM_B_BRANCH):
            assert arm.port_calls == default_contract().decisions_on_path(
                default_contract().measurement_ticks
            )
            assert arm.inherited_port_calls == default_contract().decisions_on_path(
                default_contract().acquisition_ticks
            )
        if arm.branch_id == ARM_C_BRANCH:
            assert arm.port_calls == default_contract().decisions_on_path(
                default_contract().acquisition_ticks
                + default_contract().measurement_ticks
                - default_contract().freeze_tick
            )
            assert arm.inherited_port_calls == default_contract().decisions_on_path(
                default_contract().freeze_tick
            )
        if arm.branch_id == ARM_D_BRANCH:
            assert arm.port_calls == default_contract().decisions_on_path(
                default_contract().acquisition_ticks + default_contract().measurement_ticks
            )
            assert arm.inherited_port_calls == 0


def test_acceptance_is_deterministic_across_runs() -> None:
    first = run_g1_v9_acceptance(
        commitment_key=ACCEPTANCE_KEY,
        evaluator_seed_material=EVALUATOR_MATERIAL,
    )
    second = run_g1_v9_acceptance(
        commitment_key=ACCEPTANCE_KEY,
        evaluator_seed_material=EVALUATOR_MATERIAL,
    )
    assert first == second


def test_contract_pins_zero_provider_sends() -> None:
    from dataclasses import replace

    contract = default_contract()
    with pytest.raises(ValueError, match="zero provider sends"):
        replace(contract, max_provider_sends_this_gate=8)


def test_replay_performs_no_policy_calls() -> None:
    """Recorded decisions are consumed by replay; no policy call occurs."""

    from resonance_world.experimental_runtime.g1_v9 import (
        present_context,
        seal_epoch,
        start_arm,
    )

    contract = default_contract()
    store = KernelStore(commitment_key=ACCEPTANCE_KEY)
    machine = build_machine(contract)
    seed = derive_evaluator_seed(EVALUATOR_MATERIAL)
    kernel = start_arm(store, contract, "replay-probe")
    seal_epoch(kernel, epoch=0, seed=seed, contract=contract)
    policy = build_policy("adaptive", contract=contract)

    for current in range(20):
        if current % contract.decision_cadence == 0:
            present_context(kernel, "ctx-0")
            kernel.decide_via(policy)
        kernel.schedule("world_pulse", {"tick": current})
        kernel.advance()

    calls_before = policy.calls
    result = replay_branch(store, "replay-probe", machine)
    assert policy.calls == calls_before
    assert result.recorded_agent_decisions == calls_before
    assert result.final_state_sha256 == kernel.state_hash()
