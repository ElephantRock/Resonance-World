"""Regression tests for the independent review findings on PR #311.

Each test class maps to one review finding. These tests fail on commit
``c75bb430`` and must pass on every follow-up commit.
"""

from __future__ import annotations

import sqlite3

import pytest

from resonance_world.experimental_runtime.kernel import WorldKernel
from resonance_world.experimental_runtime.scenario import (
    ScriptedPolicy,
    build_machine,
    drive,
    start_kernel,
)
from resonance_world.experimental_runtime.store import KernelStore


def test_duplicate_decision_is_rejected_after_being_recorded() -> None:
    """P0-3: the answered set must be updated once a decision is recorded."""

    store = KernelStore()
    kernel = start_kernel(store)
    request = kernel.request_decision()
    kernel.record_decision(request, {"action": "harvest"}, model_id="test-model")

    with pytest.raises(ValueError, match="already answered"):
        kernel.record_decision(request, {"action": "maintain"}, model_id="test-model")

    second = [event for event in kernel.events() if event.kind == "agent_decision"]
    assert len(second) == 1
    assert second[0].payload["decision"]["action"] == "harvest"


def test_forged_request_from_another_branch_is_rejected() -> None:
    parent_store = KernelStore()
    parent = start_kernel(parent_store)
    drive(parent, ticks=5, policy=ScriptedPolicy())
    child = parent.fork("child")

    request = parent.request_decision()
    with pytest.raises(ValueError, match="different branch"):
        child.record_decision(request, {"action": "harvest"}, model_id="test-model")


def test_stale_request_is_rejected_after_the_world_advances() -> None:
    store = KernelStore()
    kernel = start_kernel(store)
    request = kernel.request_decision()
    kernel.advance()

    with pytest.raises(ValueError, match="stale"):
        kernel.record_decision(request, {"action": "harvest"}, model_id="test-model")


def test_request_not_matching_latest_observation_is_rejected() -> None:
    store = KernelStore()
    kernel = start_kernel(store)
    first = kernel.request_decision()
    second = kernel.request_decision()
    assert first.request_id != second.request_id

    with pytest.raises(ValueError, match="latest recorded observation"):
        kernel.record_decision(first, {"action": "harvest"}, model_id="test-model")
    kernel.record_decision(second, {"action": "harvest"}, model_id="test-model")


def test_answered_requests_survive_resume() -> None:
    store = KernelStore()
    kernel = start_kernel(store)
    policy = ScriptedPolicy()
    drive(kernel, ticks=10, policy=policy)
    kernel.checkpoint("head")

    resumed = WorldKernel.resume(
        store=store, branch_id="main", machine=build_machine(), checkpoint_name="head"
    )
    answered = resumed._answered_requests
    assert len(answered) == 2  # ticks 4 and 9 carry decisions

    stale = resumed.request_decision()
    # A reconstructed kernel must not accept the pre-resume answered set as new.
    assert stale.request_id not in answered
    resumed.record_decision(stale, {"action": "maintain"}, model_id="test-model")
    with pytest.raises(ValueError, match="already answered"):
        resumed.record_decision(stale, {"action": "harvest"}, model_id="test-model")


# ---------------------------------------------------------------------------
# P0-4: atomicity of world transition and storage
# ---------------------------------------------------------------------------


class _FailingStore(KernelStore):
    """A store whose next append can be made to fail on demand."""

    def __init__(self) -> None:
        super().__init__()
        self.fail_next = False
        self.failures = 0

    def append_event(self, branch_id, event, *, sealed_payload=None):  # type: ignore[override]
        if self.fail_next:
            self.fail_next = False
            self.failures += 1
            import sqlite3

            raise sqlite3.OperationalError("injected storage failure")
        return super().append_event(branch_id, event, sealed_payload=sealed_payload)


def test_world_does_not_advance_when_storage_fails() -> None:
    """P0-4: a failed append must leave the live engine at the logged state."""

    store = _FailingStore()
    kernel = start_kernel(store)
    first = kernel.emit("world_effect", {"tick": 0})
    hash_after_first = kernel.state_hash()
    count_after_first = kernel.event_count

    store.fail_next = True
    with pytest.raises(sqlite3.OperationalError, match="injected"):
        kernel.emit("world_effect", {"tick": 0})

    assert kernel.state_hash() == hash_after_first
    assert kernel.event_count == count_after_first
    assert len(kernel.events()) == count_after_first

    # The failed sequence number is not consumed: the next event takes it.
    second = kernel.emit("world_effect", {"tick": 0})
    assert second.seq == first.seq + 1
    assert kernel.event_count == count_after_first + 1


def test_sealed_state_is_not_committed_when_storage_fails() -> None:
    store = _FailingStore()
    kernel = start_kernel(store)
    drive(kernel, ticks=4, policy=ScriptedPolicy())
    sealed_before = dict(kernel._sealed)
    state_hash = kernel.state_hash()
    store_count = store.event_count("main")

    store.fail_next = True
    kernel.schedule(
        "assessment",
        {"epoch": 99, "stress": 9},
        source="external",
        visibility="private",
    )
    with pytest.raises(sqlite3.OperationalError, match="injected"):
        kernel.advance()

    assert kernel.state_hash() == state_hash
    assert kernel._sealed == sealed_before
    assert store.event_count("main") == store_count


def test_log_stays_verifiable_after_recovered_storage_failure() -> None:
    from resonance_world.experimental_runtime.replay import replay_branch

    store = _FailingStore()
    kernel = start_kernel(store)
    drive(kernel, ticks=6, policy=ScriptedPolicy())
    store.fail_next = True
    with pytest.raises(sqlite3.OperationalError, match="injected"):
        kernel.emit("world_effect", {"tick": kernel.tick})
    drive(kernel, ticks=2, policy=ScriptedPolicy())

    result = replay_branch(store, "main", build_machine())
    assert result.final_state_sha256 == kernel.state_hash()
    assert result.all_checkpoints_matched or not result.checkpoint_verifications


# ---------------------------------------------------------------------------
# P0-1: confidentiality of sealed payloads and state digests
# ---------------------------------------------------------------------------


def _kernel_with_secret_kind(store) -> WorldKernel:
    """A kernel whose machine also reduces an opaque private 'secret' kind."""

    machine = build_machine()
    machine.register("secret", lambda state, event, sealed: state)
    return WorldKernel.create(
        "secret-test",
        machine,
        store=store,
        initial_public={"stock": 1},
        initial_private={"hidden_threshold": 6},
    )


def test_low_entropy_sealed_payload_cannot_be_brute_forced(tmp_path) -> None:
    """P0-1: a short secret must not be guessable from its commitment."""

    from resonance_world.adapters import sha256_json

    alphabet = "K7AB"  # includes the true secret; 16-candidate space
    secret = "K7"
    store = KernelStore(tmp_path / "world.sqlite3")
    kernel = _kernel_with_secret_kind(store)
    kernel.emit("secret", {"code": secret}, source="external", visibility="private")

    sealed_event = next(
        event for event in store.iter_events("main") if event.visibility == "private"
    )
    commitment = sealed_event.payload_sha256

    # Bare digests verify guesses directly: none may match, even the true one.
    assert sha256_json({"code": secret}) != commitment
    keyed_matches = []
    for first in alphabet:
        for second in alphabet:
            guess = {"code": first + second}
            assert sha256_json(guess) != commitment
            if store.commit_payload(guess) == commitment:
                keyed_matches.append(guess["code"])

    # A key holder can verify the true payload; a keyless attacker cannot
    # test any guess against the published commitment at all.
    assert keyed_matches == [secret]


def test_public_log_and_state_digests_carry_no_sealed_plaintext(tmp_path) -> None:
    import sqlite3

    store = KernelStore(tmp_path / "world.sqlite3")
    kernel = _kernel_with_secret_kind(store)
    kernel.emit("secret", {"code": "K7"}, source="external", visibility="private")
    kernel.state_hash()
    store.close()

    connection = sqlite3.connect(str(tmp_path / "world.sqlite3"))
    rows = connection.execute(
        "SELECT payload FROM events WHERE branch_id = 'main'"
    ).fetchall()
    connection.close()
    for row in rows:
        assert row[0] is None or "K7" not in row[0]


def test_commitment_key_custody_modes(tmp_path) -> None:
    from resonance_world.experimental_runtime.store import KernelStore as KS

    key = bytes(range(16, 48))
    first = KS(commitment_key=key)
    second = KS(commitment_key=key)
    assert first.commitment_key == key
    assert first.commit_payload({"x": 1}) == second.commit_payload({"x": 1})

    world_path = tmp_path / "custody.sqlite3"
    persisted = KS(world_path, commitment_key=key, persist_commitment_key=True)
    persisted.close()
    reopened = KS(world_path)
    assert reopened.commitment_key == key

    with pytest.raises(ValueError, match="does not match"):
        KS(world_path, commitment_key=bytes(range(48, 80)))


def test_invalid_commitment_keys_are_rejected() -> None:
    from resonance_world.experimental_runtime.store import KernelStore as KS

    with pytest.raises(ValueError, match="16 to 64 bytes"):
        KS(commitment_key=b"short")
    with pytest.raises(ValueError, match="16 to 64 bytes"):
        KS(commitment_key=b"x" * 65)


def test_legacy_store_files_are_rejected(tmp_path) -> None:
    import sqlite3

    world_path = tmp_path / "legacy.sqlite3"
    store = KernelStore(world_path)
    store.close()
    connection = sqlite3.connect(str(world_path))
    connection.execute(
        "UPDATE meta SET value = 'world-kernel-store-v1' WHERE key = 'schema_version'"
    )
    connection.commit()
    connection.close()

    from resonance_world.experimental_runtime.store import KernelStore as KS

    with pytest.raises(ValueError, match="schema"):
        KS(world_path)
