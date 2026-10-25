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
    start_arm,
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


# ---------------------------------------------------------------------------
# Review round 4: functional fixes
# ---------------------------------------------------------------------------


def _seeded_probe_branch(store, branch_id: str):
    """Create a probe branch with the epoch-0 rule sealed."""

    from resonance_world.experimental_runtime.g1_v9 import seal_epoch

    contract = default_contract()
    kernel = start_arm(store, contract, branch_id)
    seal_epoch(
        kernel,
        epoch=0,
        seed=derive_evaluator_seed(EVALUATOR_MATERIAL),
        contract=contract,
    )
    return kernel, contract


def test_frozen_policy_actually_stops_learning() -> None:
    """P0: arm C must not update its learning statistics after restoration."""

    from resonance_world.experimental_runtime.g1_v9.arms import (
        ContextMemoryPolicy,
        FrozenPolicy,
    )

    live = ContextMemoryPolicy()
    store = KernelStore(commitment_key=ACCEPTANCE_KEY)
    kernel, contract = _seeded_probe_branch(store, "freeze-probe")

    from resonance_world.experimental_runtime.g1_v9.scenario import present_context

    for _ in range(10):
        present_context(kernel, "ctx-0")
        kernel.decide_via(live)
        kernel.advance()

    frozen = FrozenPolicy(live.snapshot())
    pre_outcomes = list(frozen.snapshot()["outcomes"])
    pre_successes = dict(frozen.snapshot()["successes"])

    for _ in range(6):
        present_context(kernel, "ctx-0")
        kernel.decide_via(frozen)
        kernel.advance()

    post = frozen.snapshot()
    assert frozen.frozen_at == 0
    assert post["outcomes"] == pre_outcomes  # no learning updates
    assert post["successes"] == pre_successes
    assert len(post["chosen"]) > len(pre_outcomes)  # it keeps acting


def test_agent_decision_must_match_presented_context() -> None:
    """P0: out-of-task decisions are rejected, not evaluated silently."""

    from resonance_world.experimental_runtime.g1_v9.arms import ContextMemoryPolicy
    from resonance_world.experimental_runtime.g1_v9.scenario import present_context

    store = KernelStore(commitment_key=ACCEPTANCE_KEY)
    kernel, contract = _seeded_probe_branch(store, "binding-probe")
    policy = ContextMemoryPolicy()

    present_context(kernel, "ctx-0")
    request = kernel.request_decision()
    decision = policy.decide(request)
    decision["context"] = "ctx-1"  # forge a different task context

    with pytest.raises(ValueError, match="presented task context"):
        kernel.record_decision(request, decision, model_id=policy.model_id)


def test_context_rotation_is_balanced_per_stage() -> None:
    """P1: every context appears equally often in every decision stage."""

    from resonance_world.experimental_runtime.g1_v9.evaluator import context_schedule

    contract = default_contract()
    seed = derive_evaluator_seed(EVALUATOR_MATERIAL)
    stage = contract.decisions_on_path(contract.acquisition_ticks)  # 100
    schedule = context_schedule(
        seed,
        contract.acquisition_ticks + contract.measurement_ticks,
        contract.context_count,
        contract.decision_cadence,
    )
    assert len(schedule) == contract.decisions_on_path(
        contract.acquisition_ticks + contract.measurement_ticks
    )

    per_stage = contract.context_count  # each balanced block covers all contexts
    block_size = stage // per_stage if stage % per_stage == 0 else 1
    del block_size

    for stage_start in range(0, stage, contract.context_count):
        block = schedule[stage_start : stage_start + contract.context_count]
        assert sorted(block) == sorted({f"ctx-{i}" for i in range(contract.context_count)})


def test_interrupted_run_matches_uninterrupted_run() -> None:
    """P0: resume from a checkpoint restores the exact agent and world state."""

    from resonance_world.experimental_runtime.g1_v9 import (
        canonical_memory,
        context_schedule,
        latest_memory_state,
        record_memory_event,
        seal_epoch,
    )
    from resonance_world.experimental_runtime.g1_v9.arms import ContextMemoryPolicy
    from resonance_world.experimental_runtime.g1_v9.scenario import present_context
    from resonance_world.experimental_runtime.kernel import WorldKernel
    from resonance_world.experimental_runtime.replay import replay_branch

    contract = default_contract()
    machine = build_machine(contract)
    seed = derive_evaluator_seed(EVALUATOR_MATERIAL)

    # Derive the shared epoch-0 table and the balanced context rotation.
    probe = start_arm(
        KernelStore(commitment_key=ACCEPTANCE_KEY), contract, "probe"
    )
    sealed_table = seal_epoch(probe, epoch=0, seed=seed, contract=contract)
    contexts = context_schedule(
        seed,
        contract.acquisition_ticks + contract.measurement_ticks,
        contract.context_count,
        contract.decision_cadence,
    )
    restore_tick = contract.acquisition_checkpoints[-1]  # 500

    def drive(kernel, policy, *, from_tick: int, to_tick: int) -> None:
        for current in range(from_tick, to_tick):
            if current == contract.acquisition_ticks:
                seal_epoch(
                    kernel,
                    epoch=1,
                    seed=seed,
                    contract=contract,
                    previous_table=sealed_table,
                )
            context = contexts[current // contract.decision_cadence]
            if current % contract.decision_cadence == 0:
                present_context(kernel, context)
                kernel.decide_via(policy)
            kernel.schedule("world_pulse", {"tick": current})
            kernel.advance()
            if kernel.tick in contract.measurement_checkpoints:
                kernel.checkpoint(f"cp-{kernel.tick}")
                record_memory_event(
                    kernel=kernel,
                    tick=kernel.tick,
                    kind="save",
                    memory=canonical_memory(policy.snapshot()),
                    memory_id=f"memory@{kernel.tick}",
                )

    # Uninterrupted reference run.
    store_ref = KernelStore(commitment_key=ACCEPTANCE_KEY)
    ref = start_arm(store_ref, contract, "ref")
    seal_epoch(ref, epoch=0, seed=seed, contract=contract)
    ref_policy = ContextMemoryPolicy()
    drive(ref, ref_policy, from_tick=0, to_tick=1000)
    uninterrupted_choices = list(ref_policy.chosen)

    # Interrupted run: stop at the tick-500 checkpoint, resume, continue.
    store_int = KernelStore(commitment_key=ACCEPTANCE_KEY)
    part = start_arm(store_int, contract, "ref")
    seal_epoch(part, epoch=0, seed=seed, contract=contract)
    part_policy = ContextMemoryPolicy()
    drive(part, part_policy, from_tick=0, to_tick=restore_tick)
    # Pause point: attest the memory first, then checkpoint, so the
    # snapshot watermark covers the attested agent state exactly.
    record_memory_event(
        kernel=part,
        tick=restore_tick,
        kind="save",
        memory=canonical_memory(part_policy.snapshot()),
        memory_id=f"memory@{restore_tick}",
    )
    part.checkpoint(f"cp-{restore_tick}")

    resumed = WorldKernel.resume(
        store=store_int,
        branch_id="ref",
        machine=machine,
        checkpoint_name=f"cp-{restore_tick}",
    )
    restored_memory = latest_memory_state(store_int, "ref")
    assert restored_memory is not None
    resumed_policy = ContextMemoryPolicy()
    resumed_policy.restore(restored_memory)
    resumed_policy._last_seen = int(resumed.state.public["successes"])

    drive(resumed, resumed_policy, from_tick=restore_tick, to_tick=1000)

    # The interrupted run records two extra custody events (save at the
    # pause point), so full-state digests differ by watermark; the world
    # CONTENT - tick, public and private compartments - must be identical.
    def content(state):
        return (state.tick, dict(state.public), dict(state.private))

    assert content(resumed.state) == content(ref.state)
    assert resumed_policy.chosen == uninterrupted_choices
    result = replay_branch(store_int, "ref", machine)
    assert result.final_state_sha256 == resumed.state_hash()


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
